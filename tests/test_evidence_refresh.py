"""Eligibility and link identity must remain correct after sparse source polls."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from internship_watch.cli import export
from internship_watch.runner import run_once
from internship_watch.storage import Store


def listing(**changes):
    job = {"source_id": "feed-one", "employer": "Example", "title": "Software Engineering Intern",
           "location": "New York, NY, United States", "description": "",
           "description_url": "https://example.com/jobs/1", "application_url": "https://example.com/jobs/1"}
    job.update(changes)
    return job


class EvidenceRefreshTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "jobs.sqlite3"
        self.filters = {"countries": ["US"], "degrees": ["bachelor"], "allow_unstated_eligibility": True}
        self.config = {"database": str(self.path), "sources": [{"id": "feed"}],
                       "filters": self.filters, "initial_run": "silent"}

    def test_enriched_degree_exclusion_survives_sparse_refresh_and_restart(self):
        sender = Mock()
        def validator(job, client):
            return {"status": "open", "final_description_url": job["description_url"],
                    "final_application_url": job["application_url"],
                    "description": "This internship requires a PhD degree in Computer Science."}
        with patch("internship_watch.runner.heartbeat"):
            for jobs in ([], [listing()], [listing()], [listing()]):
                run_once(self.config, collector=lambda s, c, jobs=jobs: jobs, client=Mock(),
                         validator=validator, sender=sender)
        store = Store(self.path)
        try:
            row = store.rows("SELECT * FROM jobs")[0]
            self.assertEqual(row["classification"], "exclude")
            self.assertIn("PhD", row["description"])
            self.assertEqual(store.rows("SELECT COUNT(*) n FROM outbox")[0]["n"], 0)
            sender.send.assert_not_called()
        finally:
            store.close()

    def test_changed_location_and_filter_policy_do_not_keep_old_inclusion(self):
        store = Store(self.path)
        try:
            with store.transaction():
                jid, _ = store.upsert_job("feed", listing(), {}, 1, filters=self.filters)
                store.upsert_job("feed", listing(location="Unknown"), {}, 2, filters=self.filters)
            row = store.rows("SELECT * FROM jobs WHERE id=?", (jid,))[0]
            self.assertEqual(row["classification"], "ambiguous")
            self.assertEqual(json.loads(row["evidence"])["eligibility"]["countries"], [])
            with store.transaction():
                store.upsert_job("feed", listing(), {}, 3, filters=self.filters)
                strict = dict(self.filters, allow_unstated_eligibility=False)
                store.upsert_job("feed", listing(), {}, 4, filters=strict)
            self.assertEqual(store.rows("SELECT classification FROM jobs")[0]["classification"], "ambiguous")
        finally:
            store.close()

    def test_employer_summary_is_enriched_and_cannot_erase_degree_restriction(self):
        summary = "Join our software engineering internship and build useful products."
        source_job = listing(description=summary, evidence={"provider": "apple", "description_kind": "employer_search_summary"})
        sender = Mock()
        def validator(job, client):
            return {"status": "open", "final_description_url": job["description_url"],
                    "final_application_url": job["application_url"],
                    "description": "This internship requires a PhD degree in Computer Science. You will build software."}
        with patch("internship_watch.runner.heartbeat"):
            for jobs in ([], [source_job], [source_job], [source_job]):
                run_once(self.config, collector=lambda s, c, jobs=jobs: jobs, client=Mock(),
                         validator=validator, sender=sender)
        store = Store(self.path)
        try:
            row = store.rows("SELECT * FROM jobs")[0]
            self.assertEqual(row["classification"], "exclude")
            self.assertIn("requires a PhD", row["description"])
            canonical = json.loads(row["payload"])
            self.assertEqual(canonical["evidence"]["description_kind"], "validated_destination")
            raw = json.loads(store.rows("SELECT payload FROM source_records")[0]["payload"])
            self.assertEqual(raw["description"], summary)
            self.assertEqual(raw["evidence"]["description_kind"], "employer_search_summary")
            self.assertEqual(source_job["evidence"]["description_kind"], "employer_search_summary")
            self.assertEqual(source_job["description"], summary)
            sender.send.assert_not_called()
        finally:
            store.close()

    def test_changed_title_requires_fresh_description_and_destination_check(self):
        store = Store(self.path)
        try:
            old = listing(description="This internship requires a PhD degree.")
            with store.transaction():
                jid, _ = store.upsert_job("feed", old, {}, 1, filters=self.filters)
                store.record_check(jid, {"status": "open", "final_description_url": old["description_url"],
                                        "final_application_url": old["application_url"]}, "2099-01-01")
                store.upsert_job("feed", listing(title="Product Management Intern"), {}, 2, filters=self.filters)
            row = store.rows("SELECT * FROM jobs WHERE id=?", (jid,))[0]
            self.assertEqual(row["description"], "")
            self.assertEqual(row["status"], "unverified")
            self.assertIsNone(row["next_check"])
            self.assertIsNone(row["final_url"])
            self.assertEqual(len(store.rows("SELECT * FROM link_checks")), 1)
        finally:
            store.close()

    def test_changed_employer_invalidates_expected_identity(self):
        store = Store(self.path)
        try:
            with store.transaction():
                jid, _ = store.upsert_job("feed", listing(), {}, 1, filters=self.filters)
                store.record_check(jid, {"status": "open"}, "2099-01-01")
                store.upsert_job("feed", listing(employer="Different Company"), {}, 2, filters=self.filters)
            self.assertEqual(store.rows("SELECT status FROM jobs")[0]["status"], "unverified")
        finally:
            store.close()

    def test_export_preserves_malformed_and_injected_values_without_executing_them(self):
        store = Store(self.path)
        try:
            title = '\"><script>alert("bad")</script>'
            with store.transaction():
                store.upsert_job("feed", listing(title=title, employer="=dangerous", description_url="https://[bad"),
                                 {"decision": "include", "category": "software"}, 1)
            directory = Path(self.temp.name) / "export"
            export(store, directory)
            document = (directory / "jobs.html").read_text(encoding="utf-8")
            self.assertNotIn(title, document)
            self.assertIn("&lt;script&gt;", document)
            self.assertNotIn('href="https://[bad"', document)
            self.assertIn("'=dangerous", (directory / "jobs.csv").read_text(encoding="utf-8-sig"))
            self.assertEqual(json.loads((directory / "jobs.json").read_text(encoding="utf-8"))[0]["title"], title)
            self.assertIn('<option value="include">All matches</option>', document)
        finally:
            store.close()

    def test_legacy_alias_suppresses_existing_canonical_job_and_pending_delivery(self):
        store = Store(self.path)
        try:
            legacy_path = Path(self.temp.name) / "seen.json"
            legacy_path.write_text(json.dumps({"ids": ["gh-example-123"]}), encoding="utf-8")
            store.import_legacy(legacy_path)
            with store.transaction():
                first = listing(source_id="simplify-abc", description_url="https://boards.greenhouse.io/example/jobs/123",
                                application_url="https://boards.greenhouse.io/example/jobs/123")
                jid, _ = store.upsert_job("feed", first, {"decision": "include"}, 1)
                store.queue("new:" + jid, "job", {"title": "New internship"})
                direct = dict(first, source_id="gh-example-123")
                alias_jid, _ = store.upsert_job("direct", direct, {"decision": "include"}, 2)
            self.assertEqual(alias_jid, jid)
            self.assertEqual(store.rows("SELECT baseline FROM jobs")[0]["baseline"], 1)
            self.assertEqual(store.rows("SELECT status FROM outbox")[0]["status"], "cancelled")
            self.assertEqual(store.rows("SELECT COUNT(*) n FROM outbox WHERE status='delivered'")[0]["n"], 0)
        finally:
            store.close()


if __name__ == "__main__":
    unittest.main()

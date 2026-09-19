"""Persistent discovery history and validation invalidation regressions."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from internship_watch.storage import Store


class StorageHistoryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / "jobs.db"
        self.store = Store(self.path)
        self.job = {"source_id": "job-1", "employer": "Example", "title": "Software Engineer Intern",
                    "description_url": "https://example.com/jobs/1", "application_url": "https://example.com/applications/1",
                    "description": "An internship building software."}
        self.classification = {"decision": "include", "category": "software", "evidence": ["Internship title"]}

    def tearDown(self):
        self.store.close()
        self.directory.cleanup()

    def insert(self, job=None, classification=None, source="example"):
        with self.store.transaction():
            return self.store.upsert_job(source, job or self.job, classification or self.classification, 1)[0]

    def mark_open(self, jid):
        with self.store.transaction():
            self.store.record_check(jid, {"status": "open", "final_description_url": self.job["description_url"],
                                         "final_application_url": self.job["application_url"]}, "2099-01-01T00:00:00+00:00")

    def test_unchanged_polls_update_last_seen_without_repeating_history(self):
        with patch("internship_watch.storage.now", return_value="2026-09-18T00:00:00+00:00"):
            jid = self.insert()
        with patch("internship_watch.storage.now", return_value="2026-09-18T01:00:00+00:00"):
            for _ in range(10):
                self.insert()
        self.assertEqual(len(self.store.rows("SELECT * FROM observations")), 1)
        row = self.store.rows("SELECT * FROM jobs WHERE id=?", (jid,))[0]
        self.assertEqual(row["first_seen"], "2026-09-18T00:00:00+00:00")
        self.assertEqual(row["last_seen"], "2026-09-18T01:00:00+00:00")

    def test_description_and_classification_changes_get_separate_observations(self):
        self.insert()
        changed = dict(self.job, description="An internship building backend APIs.")
        self.insert(changed)
        classification = dict(self.classification, category="data_engineering")
        self.insert(changed, classification)
        self.insert(changed, classification)
        self.assertEqual(len(self.store.rows("SELECT * FROM observations")), 3)

    def test_source_aliases_do_not_cause_repeated_history(self):
        alias = dict(self.job, source_id="job-2")
        for _ in range(3):
            self.insert()
            self.insert(alias)
            self.insert(alias, source="feed")
        self.assertEqual(len(self.store.rows("SELECT * FROM jobs")), 1)
        self.assertEqual(len(self.store.rows("SELECT * FROM observations")), 3)

    def test_material_destination_changes_invalidate_check_but_keep_history(self):
        for field in ("description_url", "application_url"):
            with self.subTest(field=field):
                jid = self.insert()
                self.mark_open(jid)
                self.insert(dict(self.job, **{field: "https://example.com/new-destination/1"}))
                row = self.store.rows("SELECT * FROM jobs WHERE id=?", (jid,))[0]
                self.assertEqual(row["status"], "unverified")
                for key in ("final_url", "final_application_url", "last_checked", "next_check"):
                    self.assertIsNone(row[key])
                self.assertTrue(self.store.rows("SELECT * FROM link_checks WHERE job_id=?", (jid,)))

    def test_tracking_only_url_change_keeps_verified_check(self):
        jid = self.insert()
        self.mark_open(jid)
        changed = dict(self.job, description_url=self.job["description_url"] + "?utm_source=Simplify",
                       application_url=self.job["application_url"] + "?utm_campaign=internships")
        self.insert(changed)
        row = self.store.rows("SELECT * FROM jobs WHERE id=?", (jid,))[0]
        self.assertEqual(row["status"], "open")
        self.assertEqual(row["next_check"], "2099-01-01T00:00:00+00:00")

    def test_restart_keeps_identity_history_pending_delivery_and_verified_state(self):
        jid = self.insert()
        self.mark_open(jid)
        with self.store.transaction():
            self.store.queue("new:" + jid, "job", {"title": "New internship"})
        self.store.close()
        self.store = Store(self.path)
        self.assertEqual(self.insert(), jid)
        self.assertEqual(len(self.store.rows("SELECT * FROM observations")), 1)
        self.assertEqual(self.store.rows("SELECT status FROM jobs")[0]["status"], "open")
        self.assertEqual(self.store.rows("SELECT status FROM outbox")[0]["status"], "pending")


if __name__ == "__main__":
    unittest.main()

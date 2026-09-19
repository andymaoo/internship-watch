"""Capacity-aware retries preserve short retries for temporary access failures."""
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

from internship_watch.runner import recheck_policy, run_once, validation_candidates
from internship_watch.storage import Store
from tests.test_notification_policy import checked, listing


def unresolved(job, evidence, http_status=None):
    checks = [{"kind": kind, "requested_url": job[field], "status": "unverified", "evidence": list(evidence)}
              for kind, field in (("description", "description_url"), ("application", "application_url"))]
    if http_status:
        for check in checks:
            check["http_status"] = http_status
    return dict(checked(job, "unverified", "unverified"), checks=checks)


class ValidationScheduleTests(unittest.TestCase):
    def test_included_matches_precede_older_ambiguous_in_each_fair_group(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / "jobs.sqlite3")
            try:
                ids = {}
                with store.transaction():
                    for group, baseline, last_checked in ((0, False, None), (1, True, None), (2, False, "2026-01-01T00:00:00+00:00")):
                        for decision, first_seen in (("ambiguous", "2025-01-01T00:00:00+00:00"), ("include", "2026-01-01T00:00:00+00:00")):
                            job = listing(group * 100 + (1 if decision == "ambiguous" else 2))
                            jid, _ = store.upsert_job("one", job, {"decision": decision, "positive_opportunity_evidence": True}, 1, baseline=baseline)
                            store.db.execute("UPDATE jobs SET first_seen=?,last_checked=?,next_check=NULL WHERE id=?", (first_seen, last_checked, jid))
                            ids[(group, decision)] = jid
                    store.db.execute("INSERT OR REPLACE INTO meta VALUES('validation_rotation','0')")
                selected = validation_candidates(store, 6)
                self.assertEqual([row["id"] for row in selected[:3]], [ids[(group, "include")] for group in range(3)])
                self.assertEqual([row["id"] for row in selected[3:]], [ids[(group, "ambiguous")] for group in range(3)])
            finally:
                store.close()

    def test_repeat_stable_denial_waits_longer_but_changed_title_gets_fresh_check(self):
        with tempfile.TemporaryDirectory() as directory, patch("internship_watch.runner.heartbeat"):
            path = str(Path(directory) / "jobs.sqlite3")
            config = {"database": path, "sources": [{"id": "one"}], "initial_run": "silent",
                      "unverified_recheck_seconds": 3600, "blocked_recheck_seconds": 21600}
            item = listing(123)
            def run(value):
                validator = Mock(side_effect=lambda job, _: unresolved(job, ["robots_disallowed"]))
                summary = run_once(config, collector=lambda *_: [value], validator=validator, client=Mock(), sender=Mock())
                self.assertEqual(validator.call_count, 1)
                store = Store(path)
                row = store.rows("SELECT * FROM jobs")[0]
                last = json.loads(store.rows("SELECT result FROM link_checks ORDER BY id DESC LIMIT 1")[0]["result"])
                store.close()
                delay = (datetime.fromisoformat(row["next_check"]) - datetime.fromisoformat(row["last_checked"])).total_seconds()
                return delay, summary, last
            first, _, _ = run(item)
            self.assertEqual(first, 3600)
            store = Store(path)
            with store.transaction():
                store.db.execute("UPDATE jobs SET next_check='2000-01-01'")
            store.close()
            second, summary, result = run(item)
            self.assertEqual(second, 21600)
            self.assertEqual(summary["recheck_classes"], {"persistent_access_or_content_problem": 1})
            self.assertEqual(result["status"], "unverified")
            # An identity change must not inherit a six-hour wait or count the old
            # role's blocked check as a consecutive failure for this role.
            third, _, result = run(dict(item, title="Software Backend Engineering Intern 123"))
            self.assertEqual(third, 3600)
            self.assertEqual(result["recheck_reason"], "first_or_transient_unverified")

    def test_temporary_failures_keep_short_retry_after_prior_stable_failures(self):
        job = listing(123)
        config = {"unverified_recheck_seconds": 300, "blocked_recheck_seconds": 7200}
        prior = unresolved(job, ["blocked_rate_limited_or_temporary_http_failure"], 403)
        self.assertEqual(recheck_policy(prior, config, prior)[0], 7200)
        for result in (
            unresolved(job, ["blocked_rate_limited_or_temporary_http_failure"], 429),
            unresolved(job, ["blocked_rate_limited_or_temporary_http_failure"], 503),
            unresolved(job, ["access_failure:Timeout"]),
            unresolved(job, ["access_failure:AccessRestricted", "robots_policy_unavailable_or_denied_http"]),
            unresolved(job, ["access_failure:AccessRestricted", "host_cooldown_active"]),
        ):
            with self.subTest(result=result["checks"][0]["evidence"]):
                self.assertEqual(recheck_policy(result, config, prior), (300, "first_or_transient_unverified"))
                self.assertEqual(recheck_policy(result, config, result), (300, "first_or_transient_unverified"))

    def test_persistent_content_problem_and_recovery_are_scheduled_separately(self):
        job = listing(123)
        result = unresolved(job, ["missing_meaningful_description_or_application"])
        self.assertEqual(recheck_policy(result, {}, result), (21600, "persistent_access_or_content_problem"))
        self.assertEqual(recheck_policy(checked(job), {}, result), (86400, "verified_open"))
        self.assertEqual(recheck_policy(checked(job, "closed", "unverified"), {}, result), (604800, "posting_closed"))

    def test_successful_posting_api_fallback_ignores_prior_page_timeout_for_retry_class(self):
        job = listing(123)
        result = unresolved(job, ["blocked_rate_limited_or_temporary_http_failure"], 403)
        result["posting_status"] = "open"
        result["checks"][0] = {"kind": "description", "status": "unverified", "evidence": ["access_failure:Timeout"]}
        result["checks"].insert(1, {"kind": "posting_api", "status": "open", "evidence": ["fresh_documented_public_posting_api"]})
        self.assertEqual(recheck_policy(result, {}, result), (21600, "persistent_access_or_content_problem"))


if __name__ == "__main__":
    unittest.main()

"""Durable notification policy: posting evidence is separate from application access."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from internship_watch.delivery import deliver_pending
from internship_watch.runner import run_once
from internship_watch.storage import Store


def listing(number):
    return {"source_id": "job-" + str(number), "employer": "Example", "title": "Software Engineering Intern " + str(number),
            "location": "New York, United States", "description": "Software internship for enrolled bachelor students. Build software services.",
            "employment_type": "Intern", "description_url": f"https://boards.greenhouse.io/example/jobs/{number}",
            "application_url": f"https://boards.greenhouse.io/example/jobs/{number}/application"}


def checked(job, posting="open", application="open"):
    status = "closed" if "closed" in (posting, application) else ("open" if posting == application == "open" else "unverified")
    return {"status": status, "posting_status": posting, "application_status": application,
            "final_description_url": job["description_url"], "final_application_url": job["application_url"], "checks": []}


class NotificationPolicyTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = str(Path(temp.name) / "jobs.sqlite3")
        self.config = {"database": self.path, "sources": [{"id": "one"}], "validation_budget": 30,
                       "initial_run": "silent", "awaiting_digest_seconds": 900}
        self.sender = Mock()
        self.sender.send.return_value = "provider-receipt"
        patcher = patch("internship_watch.runner.heartbeat")
        patcher.start(); self.addCleanup(patcher.stop)

    def rows(self, query, args=()):
        store = Store(self.path)
        try:
            return store.rows(query, args)
        finally:
            store.close()

    def sql(self, query, args=()):
        store = Store(self.path)
        try:
            with store.transaction():
                store.db.execute(query, args)
        finally:
            store.close()

    def run_jobs(self, jobs, posting="open", application="open", validator=None):
        return run_once(self.config, collector=lambda *_: jobs, client=Mock(), sender=self.sender,
                        validator=validator or (lambda job, _: checked(job, posting, application)))

    def test_verified_posting_alerts_even_if_application_is_unverified(self):
        self.run_jobs([listing(1)])
        summary = self.run_jobs([listing(1), listing(2)], application="unverified")
        self.sender.send.assert_called_once()
        message = self.sender.send.call_args.args[0]
        self.assertEqual(message["title"], "New internship")
        self.assertIn("application access UNVERIFIED", message["body"])
        row = self.rows("SELECT * FROM outbox")[0]
        self.assertEqual((row["status"], row["receipt_id"]), ("delivered", "provider-receipt"))
        self.assertEqual(summary["metrics"]["discovery_to_notification_decision"]["count"], 1)
        self.assertEqual(summary["metrics"]["notification_pending"], 0)

    def test_unverified_digest_does_not_suppress_later_verified_immediate_alert(self):
        self.run_jobs([listing(1)])
        self.run_jobs([listing(1), listing(2)], posting="unverified", application="unverified")
        self.assertIn("Unverified", self.sender.send.call_args.args[0]["title"])
        self.assertEqual(len(self.rows("SELECT * FROM digest_jobs")), 1)
        original_decision = self.rows("SELECT notification_decided_at FROM jobs WHERE baseline=0")[0]["notification_decided_at"]
        self.run_jobs([listing(1), listing(2)])
        self.assertEqual(self.sender.send.call_count, 1)  # no duplicate digest and recheck is not due
        self.sql("UPDATE jobs SET next_check='2000-01-01' WHERE baseline=0")
        self.run_jobs([listing(1), listing(2)], application="unverified")
        self.assertEqual(self.sender.send.call_count, 2)
        self.assertEqual(self.sender.send.call_args.args[0]["title"], "New internship")
        self.assertEqual(len(self.rows("SELECT * FROM outbox WHERE status='delivered'")), 2)
        self.assertEqual(self.rows("SELECT notification_decided_at FROM jobs WHERE baseline=0")[0]["notification_decided_at"], original_decision)
        self.run_jobs([listing(1), listing(2)])
        self.assertEqual(self.sender.send.call_count, 2)

    def test_closed_application_is_digest_only_and_short_recheck(self):
        self.run_jobs([listing(1)])
        self.run_jobs([listing(1), listing(2)], application="closed")
        self.assertIn("Unverified", self.sender.send.call_args.args[0]["title"])
        self.assertIn("application: closed", self.sender.send.call_args.args[0]["body"])
        row = self.rows("SELECT * FROM jobs WHERE baseline=0")[0]
        self.assertEqual(row["posting_status"], "open")
        from datetime import datetime
        self.assertLessEqual((datetime.fromisoformat(row["next_check"]) - datetime.fromisoformat(row["last_checked"])).total_seconds(), 3601)
        self.sql("UPDATE jobs SET next_check='2000-01-01' WHERE baseline=0")
        self.run_jobs([listing(1), listing(2)])
        self.assertEqual(self.sender.send.call_args.args[0]["title"], "New internship")

    def test_failed_digest_retries_after_restart_and_removes_closed_members(self):
        self.run_jobs([listing(1)])
        self.sender.send.side_effect = RuntimeError("temporary failure")
        self.run_jobs([listing(1), listing(2), listing(3)], posting="unverified", application="unverified")
        self.assertEqual(len(self.rows("SELECT * FROM outbox")), 1)
        self.assertEqual(len(self.rows("SELECT * FROM digest_jobs")), 2)
        self.sql("UPDATE jobs SET posting_status='closed' WHERE original_url LIKE '%/2'")
        self.sql("UPDATE outbox SET next_attempt='2000-01-01'")
        self.sender.reset_mock(); self.sender.send.side_effect = None
        store = Store(self.path)
        deliver_pending(store, self.sender); store.close()
        self.sender.send.assert_called_once()
        body = self.sender.send.call_args.args[0]["body"]
        self.assertNotIn("Intern 2", body)
        self.assertIn("Intern 3", body)
        self.assertEqual(len(self.rows("SELECT * FROM digest_jobs")), 1)
        self.assertEqual(self.rows("SELECT attempts,status FROM outbox")[0], {"attempts": 2, "status": "delivered"})

    def test_pending_digest_is_cancelled_when_all_members_excluded(self):
        self.run_jobs([listing(1)])
        self.sender.send.side_effect = RuntimeError("temporary failure")
        self.run_jobs([listing(1), listing(2)], posting="unverified", application="unverified")
        self.sql("UPDATE jobs SET classification='exclude' WHERE baseline=0")
        self.sql("UPDATE outbox SET next_attempt='2000-01-01'")
        self.sender.reset_mock(); self.sender.send.side_effect = None
        store = Store(self.path)
        deliver_pending(store, self.sender); store.close()
        self.sender.send.assert_not_called()
        self.assertEqual(self.rows("SELECT status FROM outbox")[0]["status"], "cancelled")
        self.assertEqual(self.rows("SELECT * FROM digest_jobs"), [])

    def test_digest_interval_holds_only_new_members_without_repeats(self):
        self.run_jobs([listing(1)])
        self.run_jobs([listing(1), listing(2)], posting="unverified", application="unverified")
        self.run_jobs([listing(1), listing(2), listing(3)], posting="unverified", application="unverified")
        self.assertEqual(self.sender.send.call_count, 1)
        self.sql("UPDATE meta SET value='2000-01-01' WHERE key='awaiting_digest_due'")
        self.run_jobs([listing(1), listing(2), listing(3)], posting="unverified", application="unverified")
        self.assertEqual(self.sender.send.call_count, 2)
        body = self.sender.send.call_args.args[0]["body"]
        self.assertIn("Intern 3", body)
        self.assertNotIn("Intern 2", body)

    def test_initial_backlog_is_one_report_with_access_labels_and_no_individuals(self):
        self.config["initial_run"] = "digest"
        self.run_jobs([listing(1), listing(2)], posting="open", application="unverified")
        self.run_jobs([listing(1), listing(2)])
        self.sender.send.assert_called_once()
        body = self.sender.send.call_args.args[0]["body"]
        self.assertIn("Initial backlog: 2", body)
        self.assertIn("application: unverified", body)
        self.assertEqual(self.rows("SELECT * FROM digest_jobs"), [])
        self.assertEqual(self.rows("SELECT kind FROM outbox"), [{"kind": "digest"}])

    def test_initial_digest_summarizes_categories_and_lists_verified_postings_first(self):
        self.config["initial_run"] = "digest"
        unknown = dict(listing(1), employer="AAA Unverified")
        verified = dict(listing(2), employer="ZZZ Verified", title="Product Manager Intern")
        self.run_jobs([unknown, verified], validator=lambda job, _: checked(job,
                      "open" if job["source_id"] == "job-2" else "unverified"))
        self.sender.send.assert_called_once()
        message = self.sender.send.call_args.args[0]
        body = message["body"]
        self.assertIn("Software engineering 1", body)
        self.assertIn("Product management 1", body)
        self.assertLess(body.index("ZZZ Verified"), body.index("AAA Unverified"))
        self.assertLess(len(message["title"] + "\n" + body), 1950)

    def test_budget_one_rotation_services_new_backlog_and_due_rechecks(self):
        self.config["validation_budget"] = 1
        seen = []
        def validator(job, _):
            seen.append(job["source_id"])
            return checked(job, "unverified", "unverified")
        self.run_jobs([listing(1), listing(2)], validator=validator)
        first = seen[0]
        self.sql("UPDATE jobs SET next_check='2000-01-01' WHERE last_checked IS NOT NULL")
        self.run_jobs([listing(1), listing(2), listing(3)], validator=validator)
        self.run_jobs([listing(1), listing(2), listing(3), listing(4)], validator=validator)
        self.run_jobs([listing(1), listing(2), listing(3), listing(4), listing(5)], validator=validator)
        self.assertEqual(len(seen), 4)
        self.assertEqual(seen.count(first), 2)  # due recheck got a turn
        self.assertTrue(any(value in seen for value in ("job-3", "job-4", "job-5")))
        self.assertIn("job-1", seen); self.assertIn("job-2", seen)  # backlog also got a turn

    def test_automatic_export_runs_after_durable_delivery(self):
        self.config["export_directory"] = "private-export"
        with patch("internship_watch.cli.export", return_value={"jobs": 1}) as export:
            summary = self.run_jobs([listing(1)])
        export.assert_called_once()
        self.assertEqual(summary["export"], {"jobs": 1})
        saved = json.loads(self.rows("SELECT summary FROM runs")[0]["summary"])
        self.assertIn("export", saved)
        self.assertIn("timings_seconds", saved)


if __name__ == "__main__":
    unittest.main()

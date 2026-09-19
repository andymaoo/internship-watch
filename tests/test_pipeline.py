import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from internship_watch.delivery import Discord, Ntfy, NotConfigured, RetryLater, deliver_pending
from internship_watch.locking import AlreadyRunning, run_lock
from internship_watch.runner import run_once
from internship_watch.storage import Store


def job(identity="123456", title="Software Engineering Intern"):
    return {"source_id": "gh-example-" + identity, "employer": "Example", "title": title,
            "location": "New York, NY, United States", "description": "As an intern you will build software. " * 10,
            "employment_type": "Intern", "description_url": f"https://boards.greenhouse.io/example/jobs/{identity}",
            "application_url": f"https://boards.greenhouse.io/example/jobs/{identity}"}


def verified(job, client):
    return {"status": "open", "final_description_url": job["description_url"],
            "final_application_url": job["application_url"], "checks": [{"evidence": ["fixture"]}]}


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = str(Path(self.temp.name) / "jobs.sqlite3")
        self.config = {"database": self.path, "sources": [{"id": "one", "expect_nonempty": True}],
                       "validation_budget": 100, "initial_run": "silent", "failure_threshold": 2}
        self.sender = Mock()
        self.heartbeat = patch("internship_watch.runner.heartbeat")
        self.heartbeat.start(); self.addCleanup(self.heartbeat.stop)

    def run_jobs(self, jobs, **kwargs):
        return run_once(self.config, collector=lambda source, client: jobs, client=Mock(), validator=verified,
                        sender=kwargs.get("sender", self.sender))

    def rows(self, sql):
        store = Store(self.path)
        try:
            return store.rows(sql)
        finally:
            store.close()

    def test_complete_path_silent_import_new_job_delivery_and_restart(self):
        self.run_jobs([job()])
        self.sender.send.assert_not_called()
        self.run_jobs([job(), job("222222")])
        self.sender.send.assert_called_once()
        self.assertEqual(self.rows("SELECT status FROM outbox")[0]["status"], "delivered")
        self.run_jobs([job(), job("222222")])
        self.assertEqual(self.sender.send.call_count, 1)
        self.assertEqual(len(self.rows("SELECT * FROM jobs")), 2)
        self.assertEqual(len(self.rows("SELECT * FROM runs")), 3)

    def test_sparse_source_refreshes_validated_eligibility_and_can_recover(self):
        self.config["filters"] = {"degrees": ["bachelor"]}
        sparse = dict(job(), description="")
        bachelor = "This software internship is for currently enrolled bachelor students. You will develop software services."
        doctoral = "This software internship requires a PhD. Only doctoral students are eligible. You will develop software services."

        def run_with(result):
            validator = Mock(return_value=result)
            run_once(self.config, collector=lambda source, client: [sparse], client=Mock(), validator=validator, sender=self.sender)
            return validator

        def due():
            store = Store(self.path)
            with store.transaction():
                store.db.execute("UPDATE jobs SET next_check='2000-01-01'")
            store.close()

        run_with(dict(verified(sparse, None), description=bachelor))
        self.assertEqual(self.rows("SELECT classification FROM jobs")[0]["classification"], "include")
        due()
        run_with(dict(verified(sparse, None), description=doctoral))
        row = self.rows("SELECT classification,description FROM jobs")[0]
        self.assertEqual(row, {"classification": "exclude", "description": doctoral})
        due()
        blocked = run_with({"status": "unverified", "checks": [{"evidence": ["blocked"]}]})
        blocked.assert_called_once()
        self.assertEqual(self.rows("SELECT classification,description FROM jobs")[0], row)
        due()
        recovered = run_with(dict(verified(sparse, None), description=bachelor))
        recovered.assert_called_once()
        self.assertEqual(self.rows("SELECT classification,description FROM jobs")[0], {"classification": "include", "description": bachelor})
        self.sender.send.assert_not_called()  # baseline remains a silent import

    def test_failed_delivery_is_durable_and_retried_after_restart(self):
        self.run_jobs([job()])
        self.sender.send.side_effect = RuntimeError("network failed")
        self.run_jobs([job(), job("222222")])
        pending = self.rows("SELECT * FROM outbox")[0]
        self.assertEqual((pending["status"], pending["attempts"]), ("pending", 1))
        store = Store(self.path)
        with store.transaction():
            store.db.execute("UPDATE outbox SET next_attempt='2000-01-01'")
        self.sender.send.side_effect = None
        deliver_pending(store, self.sender)
        store.close()
        self.assertEqual(self.rows("SELECT status FROM outbox")[0]["status"], "delivered")

    def test_initial_digest_is_one_message_across_sources_not_a_flood(self):
        self.config["initial_run"] = "digest"
        self.config["sources"].append({"id": "two"})
        self.run_jobs([job()])
        self.run_jobs([job()])
        self.sender.send.assert_called_once()
        self.assertIn("Example", self.sender.send.call_args.args[0]["body"])
        self.assertEqual(len(self.rows("SELECT * FROM outbox")), 1)

    def test_held_job_does_not_starve_later_ready_delivery(self):
        self.run_jobs([job()])
        self.sender.send.side_effect = RuntimeError("failed")
        self.run_jobs([job(), job("222222"), job("333333")])
        store = Store(self.path)
        with store.transaction():
            store.db.execute("UPDATE jobs SET status='unverified',posting_status='unverified' WHERE title IS NOT NULL AND original_url LIKE '%222222'")
            store.db.execute("UPDATE outbox SET next_attempt='2000-01-01'")
        self.sender.reset_mock(); self.sender.send.side_effect = None
        delivered = deliver_pending(store, self.sender, limit=1)
        store.close()
        self.assertEqual(delivered["delivered"], 1)
        self.assertIn("333333", self.sender.send.call_args.args[0]["body"])

    def test_rate_limit_cooldown_survives_restart_and_protects_other_messages(self):
        store = Store(self.path)
        with store.transaction():
            store.queue("a", "digest", {"title": "A"})
            store.queue("b", "digest", {"title": "B"})
        self.sender.send.side_effect = RetryLater(3600)
        deliver_pending(store, self.sender)
        store.close()
        self.sender.send.assert_called_once()
        self.sender.reset_mock(); self.sender.send.side_effect = None
        store = Store(self.path)
        result = deliver_pending(store, self.sender)
        store.close()
        self.sender.send.assert_not_called()
        self.assertIn("cooldown_until", result)

    def test_source_outages_persist_and_alert_once_until_recovered(self):
        self.run_jobs([job()])
        def fail(source, client):
            raise TimeoutError("timed out")
        for _ in range(3):
            run_once(self.config, collector=fail, client=Mock(), sender=self.sender)
        self.assertEqual(len(self.rows("SELECT * FROM outbox WHERE kind='incident'")), 1)
        self.assertEqual(len(self.rows("SELECT * FROM jobs")), 1)
        self.run_jobs([job()])
        for _ in range(2):
            run_once(self.config, collector=fail, client=Mock(), sender=self.sender)
        self.assertEqual(len(self.rows("SELECT * FROM outbox WHERE kind='incident' AND dedupe_key LIKE 'incident:source:%'")), 2)
        self.assertEqual(len(self.rows("SELECT * FROM outbox WHERE kind='incident' AND dedupe_key LIKE 'recovery:%'")), 1)

    def test_incident_recovery_cancels_unsent_alarm(self):
        store = Store(self.path)
        with store.transaction():
            store.incident("source:one", True, "Source unavailable")
        self.sender.send.side_effect = RuntimeError("delivery failed")
        deliver_pending(store, self.sender)
        with store.transaction():
            store.incident("source:one", False, "Recovered")
            store.db.execute("UPDATE outbox SET next_attempt='2000-01-01'")
        self.sender.reset_mock(); self.sender.send.side_effect = None
        deliver_pending(store, self.sender)
        store.close()
        self.sender.send.assert_not_called()
        self.assertEqual(self.rows("SELECT status FROM outbox")[0]["status"], "cancelled")

    def test_reopened_incident_cancels_failed_recovery_before_delivery(self):
        store = Store(self.path)
        with store.transaction():
            store.incident("source:one", True, "one failed")
        deliver_pending(store, self.sender)
        with store.transaction():
            store.incident("source:one", False, "Old failure wording should not be reused")
        self.sender.send.side_effect = RuntimeError("recovery transport failed")
        deliver_pending(store, self.sender)
        recovery = store.rows("SELECT * FROM outbox WHERE dedupe_key='recovery:source:one:1'")[0]
        self.assertIn("source:one", json.loads(recovery["payload"])["body"])
        self.assertNotIn("Old failure wording", json.loads(recovery["payload"])["body"])
        with store.transaction():
            store.incident("source:one", True, "one failed again")
            store.db.execute("UPDATE outbox SET next_attempt='2000-01-01'")
        self.sender.reset_mock(); self.sender.send.side_effect = None
        deliver_pending(store, self.sender)
        self.sender.send.assert_called_once()
        self.assertEqual(self.sender.send.call_args.args[0]["body"], "one failed again")
        self.assertEqual(store.rows("SELECT status FROM outbox WHERE dedupe_key='recovery:source:one:1'")[0]["status"], "cancelled")
        store.close()

    def test_source_first_success_after_initial_failure_is_silent(self):
        self.config["sources"].append({"id": "two"})
        def first(source, client):
            if source["id"] == "two":
                raise TimeoutError("outage")
            return [job()]
        run_once(self.config, collector=first, client=Mock(), validator=verified, sender=self.sender)
        run_once(self.config, collector=lambda s, c: [job("123456" if s["id"] == "one" else "222222")],
                 client=Mock(), validator=verified, sender=self.sender)
        self.sender.send.assert_not_called()

    def test_repeated_empty_results_alert(self):
        self.run_jobs([job()])
        self.run_jobs([]); self.run_jobs([]); self.run_jobs([])
        self.assertEqual(len(self.rows("SELECT * FROM incidents WHERE key='empty:one'")), 1)
        self.assertEqual(self.rows("SELECT status FROM jobs")[0]["status"], "open")

    def test_legacy_seen_is_not_claimed_delivered(self):
        p = Path(self.temp.name) / "seen.json"
        p.write_text(json.dumps({"ids": [job("222222")["source_id"]]}))
        self.run_jobs([job()])
        store = Store(self.path); store.import_legacy(p); store.close()
        self.run_jobs([job(), job("222222")])
        self.sender.send.assert_not_called()
        self.assertEqual(self.rows("SELECT COUNT(*) n FROM legacy_seen")[0]["n"], 1)
        self.assertEqual(self.rows("SELECT COUNT(*) n FROM outbox")[0]["n"], 0)

    def test_closed_pending_job_is_cancelled_not_delivered(self):
        self.run_jobs([job()])
        self.sender.send.side_effect = RuntimeError("failed")
        self.run_jobs([job(), job("222222")])
        store = Store(self.path)
        with store.transaction():
            store.db.execute("UPDATE jobs SET status='closed',posting_status='closed' WHERE baseline=0")
            store.db.execute("UPDATE outbox SET next_attempt='2000-01-01'")
        self.sender.reset_mock(); self.sender.send.side_effect = None
        deliver_pending(store, self.sender)
        store.close()
        self.sender.send.assert_not_called()
        self.assertEqual(self.rows("SELECT status FROM outbox")[0]["status"], "cancelled")

    def test_lock_rejects_overlap_and_recovers(self):
        with run_lock(self.path + ".lock"):
            with self.assertRaises(AlreadyRunning):
                with run_lock(self.path + ".lock"):
                    pass
        with run_lock(self.path + ".lock"):
            pass

    def test_persistent_delivery_failure_signals_independent_monitor(self):
        self.run_jobs([job()])
        self.sender.send.side_effect = RuntimeError("failed")
        self.run_jobs([job(), job("222222")])
        store = Store(self.path)
        with store.transaction():
            store.db.execute("UPDATE outbox SET next_attempt='2000-01-01'")
        store.close()
        with patch("internship_watch.runner.heartbeat") as heartbeat:
            self.run_jobs([job(), job("222222")])
        heartbeat.assert_any_call("/fail")


class ProviderTests(unittest.TestCase):
    @patch.dict("os.environ", {"NTFY_URL": "https://ntfy.sh/test"}, clear=True)
    @patch("internship_watch.delivery.requests.post")
    def test_ntfy_requires_success_ack_not_merely_returned_response(self, post):
        post.return_value = Mock(status_code=500)
        post.return_value.raise_for_status.side_effect = RuntimeError("500")
        with self.assertRaises(RuntimeError):
            Ntfy().send({"title": "x", "body": "y"})
        self.assertEqual(post.call_args.kwargs["timeout"], 15)

    @patch.dict("os.environ", {"DISCORD_WEBHOOK_URL": "https://discord.com/api/webhooks/123/token"}, clear=True)
    @patch("internship_watch.delivery.requests.post")
    def test_discord_requests_saved_message_and_disables_mentions(self, post):
        post.return_value = Mock(status_code=200)
        post.return_value.json.return_value = {"id": "receipt"}
        self.assertEqual(Discord().send({"title": "@everyone", "body": "x"}), "receipt")
        self.assertEqual(post.call_args.kwargs["params"], {"wait": "true"})
        self.assertEqual(post.call_args.kwargs["json"]["allowed_mentions"], {"parse": []})

    @patch.dict("os.environ", {}, clear=True)
    def test_missing_credentials_do_not_simulate_delivery(self):
        with self.assertRaises(NotConfigured):
            Discord().send({"title": "x"})


if __name__ == "__main__":
    unittest.main()

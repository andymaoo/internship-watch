"""A local time budget must not become a batch of one-hour access failures."""
import json
import tempfile
import time
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

import requests

from internship_watch.http import HttpClient, WorkBudgetExhausted
from internship_watch.links import validate_job
from internship_watch.runner import run_once
from internship_watch.storage import Store
from tests.test_links import JOB, Client, page, response
from tests.test_notification_policy import listing, checked


class WorkBudgetTests(unittest.TestCase):
    def test_real_network_failure_is_retained_if_retry_would_exceed_budget(self):
        client = HttpClient(session=Mock(), resolve_dns=False, min_interval=0, backoff=2)
        failure = requests.ReadTimeout('Remote read timed out')
        client.session.request.side_effect = failure
        client.deadline = time.monotonic() + 1
        with self.assertRaises(requests.ReadTimeout) as raised:
            client.get('https://example.org/jobs/12345')
        self.assertIs(raised.exception, failure)
        self.assertEqual(client.session.request.call_count, 1)

    def test_pacing_deferral_makes_no_request_and_does_not_cache_robots_denial(self):
        client = HttpClient(session=Mock(), resolve_dns=False, min_interval=2)
        client.deadline = time.monotonic() + 1
        client._last_request['example.org'] = time.monotonic()
        with self.assertRaises(WorkBudgetExhausted):
            client.get('https://example.org/jobs/12345', respect_robots=True)
        client.session.request.assert_not_called()
        self.assertEqual(client._robots, {})

    def test_page_and_public_api_budget_deferrals_are_distinct_from_timeouts(self):
        for url in [JOB['description_url'], 'https://boards.greenhouse.io/example/jobs/12345',
                    'https://jobs.smartrecruiters.com/Example/123456']:
            with self.subTest(url=url):
                client = Mock()
                client._posting_api_cache = {}
                client.get.side_effect = WorkBudgetExhausted('No time for pacing')
                result = validate_job(dict(JOB, description_url=url, application_url=url), client)
                self.assertEqual(result['posting_status'], 'unverified')
                self.assertTrue(all(c['evidence'] == ['work_budget_exhausted'] for c in result['checks']))
        client = Client({JOB['description_url']: requests.Timeout('Network read failed'),
                         JOB['application_url']: requests.Timeout('Network read failed')})
        result = validate_job(JOB, client)
        self.assertTrue(all(c['evidence'] == ['access_failure:Timeout'] for c in result['checks']))

    def test_partial_posting_verification_survives_application_budget_deferral(self):
        client = Client({JOB['description_url']: response(page()),
                         JOB['application_url']: WorkBudgetExhausted('Run budget')})
        result = validate_job(JOB, client)
        self.assertEqual(result['posting_status'], 'open')
        self.assertEqual(result['application_status'], 'unverified')
        self.assertIn('work_budget_exhausted', result['checks'][-1]['evidence'])
        self.assertTrue(result['description'])

    def test_unstarted_checks_preserve_prior_validation_and_remain_due_after_restart(self):
        with tempfile.TemporaryDirectory() as directory, patch('internship_watch.runner.heartbeat'):
            path = str(Path(directory) / 'jobs.db')
            config = dict(database=path, sources=[{'id': 'one'}], initial_run='silent')
            jobs = [listing(12345), listing(12346)]
            run_once(config, collector=lambda *_: jobs, validator=lambda j, _: checked(j),
                     client=Mock(), sender=Mock())
            store = Store(path)
            with store.transaction():
                store.db.execute("UPDATE jobs SET next_check='2000-01-01'")
            before = store.rows('SELECT id,posting_status,application_status,last_checked,next_check FROM jobs ORDER BY id')
            prior_checks = store.rows('SELECT * FROM link_checks')
            store.close()
            client = Mock(); client._posting_api_cache = {}
            client.get.side_effect = WorkBudgetExhausted('No time for pacing')
            summary = run_once(config, collector=lambda *_: jobs, client=client, sender=Mock())
            self.assertEqual(summary['checked'], 0)
            self.assertEqual(summary['validation_budget_deferred'], 1)
            # Reopening the store simulates the next worker process.
            store = Store(path)
            self.assertEqual(store.rows('SELECT id,posting_status,application_status,last_checked,next_check FROM jobs ORDER BY id'), before)
            self.assertEqual(store.rows('SELECT * FROM link_checks'), prior_checks)
            store.close()
            # Exactly one job was considered, not the entire due batch.
            self.assertLessEqual(client.get.call_count, 3)

    def test_partial_verified_job_notifies_now_and_retries_at_next_poll(self):
        with tempfile.TemporaryDirectory() as directory, patch('internship_watch.runner.heartbeat'):
            path = str(Path(directory) / 'jobs.db')
            config = dict(database=path, sources=[{'id': 'one'}], initial_run='silent', poll_seconds=300)
            sender = Mock(); sender.send.return_value = 'receipt'
            run_once(config, collector=lambda *_: [listing(12345)], validator=lambda j, _: checked(j),
                     client=Mock(), sender=sender)
            def partial(job, client):
                result = checked(job, 'open', 'unverified')
                result['checks'] = [dict(kind='description', status='open', evidence=['expected_job_identity_verified']),
                                    dict(kind='application', status='unverified', evidence=['work_budget_exhausted'])]
                return result
            summary = run_once(config, collector=lambda *_: [listing(12345), listing(12346)],
                               validator=partial, client=Mock(), sender=sender)
            sender.send.assert_called_once()
            self.assertEqual(sender.send.call_args.args[0]['title'], 'New internship')
            self.assertEqual(summary['recheck_classes'], {'work_budget_deferred': 1})
            store = Store(path)
            row = store.rows('SELECT last_checked,next_check FROM jobs WHERE baseline=0')[0]
            delay = (datetime.fromisoformat(row['next_check']) - datetime.fromisoformat(row['last_checked'])).total_seconds()
            self.assertEqual(delay, 300)
            self.assertEqual(json.loads(store.rows('SELECT result FROM link_checks ORDER BY id DESC LIMIT 1')[0]['result'])['posting_status'], 'open')
            store.close()


if __name__ == '__main__':
    unittest.main()

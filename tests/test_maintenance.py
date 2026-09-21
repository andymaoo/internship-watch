import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import Mock, patch

from internship_watch.delivery import deliver_pending
from internship_watch.maintenance import (Repairs, anomaly_reasons, audit_public_feeds, inspect_backups,
    inspect_sources, publish, run_maintenance, schedule_canary, inspect_agent_review)
from internship_watch.runner import run_once
from internship_watch.safeguards import ContractError, collection_profile, record_sample
from internship_watch.storage import Store, now
from tests.test_pipeline import job, verified


class MaintenanceTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.main = Store(self.root / 'jobs.sqlite3')
        self.monitor = Store(self.root / 'maintenance.sqlite3')
        self.addCleanup(self.main.close)
        self.addCleanup(self.monitor.close)
        self.repairs = Repairs(self.monitor)
        self.source = {'id': 'example', 'type': 'greenhouse', 'slug': 'example'}
        self.config = {'database': str(self.main.path), 'sources': [self.source],
            'export_directory': str(self.root / 'export'), 'maintenance': {'feed_metadata_audit': False},
            'validation_budget': 0}
        self.profile = collection_profile([job(str(n)) for n in range(100)])

    def samples(self, profiles):
        with self.main.transaction():
            for profile in profiles:
                self.main.record_source(self.source['id'], count=profile['count'] if profile else None, error=None if profile else 'timeout')
                record_sample(self.main, self.source, 1, profile=profile, error=None if profile else 'timeout')

    def ticket(self, key):
        row = self.monitor.db.execute('SELECT * FROM repair_tickets WHERE key=?', (key,)).fetchone()
        return dict(row) if row else None

    def test_recovery_grace_persists_and_a_relapse_restarts_it(self):
        def observe(active, stamp):
            with patch('internship_watch.maintenance.now',return_value=stamp):
                Repairs(self.monitor).observe('validation-lag',active,'warning',{},'Review',recovery_seconds=1800)
        observe(True,'2026-09-21T01:00:00+00:00')
        observe(False,'2026-09-21T01:15:00+00:00')
        self.assertEqual(self.ticket('validation-lag')['state'],'open')
        observe(False,'2026-09-21T01:30:00+00:00')
        self.assertEqual(self.ticket('validation-lag')['state'],'open')
        observe(True,'2026-09-21T01:35:00+00:00')
        observe(False,'2026-09-21T01:45:00+00:00')
        observe(False,'2026-09-21T02:00:00+00:00')
        self.assertEqual(self.ticket('validation-lag')['state'],'open')
        observe(False,'2026-09-21T02:15:00+00:00')
        self.assertEqual(self.ticket('validation-lag')['state'],'resolved')
        self.assertEqual(self.monitor.db.execute("SELECT COUNT(*) FROM repair_events WHERE ticket='validation-lag'").fetchone()[0],2)

    def test_backlog_trend_tolerates_a_small_dip_and_recovery_needs_non_growth(self):
        from internship_watch.maintenance import validation_backlog_growing
        self.assertTrue(validation_backlog_growing([730,725,728,690,680,650],False))
        self.assertTrue(validation_backlog_growing([701,710,709,700,690,680],True))
        self.assertFalse(validation_backlog_growing([650,670,680,685,690,700],True))
        self.assertFalse(validation_backlog_growing([730,None,720],False))

    def test_collection_contract_rejects_duplicate_ids_before_storage(self):
        sender = Mock()
        with patch('internship_watch.runner.heartbeat'):
            result = run_once(self.config, collector=lambda s,c: [job(),job()], client=Mock(), sender=sender)
        self.assertEqual(result['sources']['example']['status'], 'failed')
        self.assertEqual(self.main.db.execute('SELECT COUNT(*) FROM jobs').fetchone()[0], 0)
        sample = self.main.db.execute('SELECT * FROM source_samples').fetchone()
        self.assertIn('Duplicate source identifier', sample['error'])

    def test_missing_identity_fails_but_malformed_url_is_profile_evidence(self):
        for field in ('source_id', 'employer', 'title'):
            value = job(); value.pop(field)
            with self.assertRaises(ContractError):
                collection_profile([value])
        value = job(); value.update(description_url='broken', application_url='broken')
        self.assertEqual(collection_profile([value])['url_fraction'], 0)

    def test_empty_source_is_valid_contract_not_proof_of_coverage(self):
        self.assertEqual(collection_profile([])['count'], 0)

    def test_telemetry_retention_is_bounded(self):
        self.samples([self.profile] * 110)
        self.assertEqual(self.main.db.execute('SELECT COUNT(*) FROM source_samples').fetchone()[0], 96)

    def test_three_distinct_bad_polls_required(self):
        low = dict(self.profile, count=10)
        self.assertEqual(anomaly_reasons(self.profile, [low, low], {}), [])
        self.assertEqual(anomaly_reasons(self.profile, [low, None, low], {}), [])
        self.assertIn('result_count_drop', anomaly_reasons(self.profile, [low]*3, {}))

    def test_configured_five_polls_do_not_resolve_existing_anomaly_early(self):
        self.samples([self.profile]*3)
        inspect_sources(self.main.db,self.repairs,self.config)
        self.repairs.observe('contract:example',True,'warning',{},'Review fixture')
        self.samples([None,self.profile,self.profile,self.profile])
        config = dict(self.config,maintenance={'anomaly_consecutive_polls':5})
        inspect_sources(self.main.db,self.repairs,config)
        self.assertEqual(self.ticket('contract:example')['state'],'open')

    def test_agent_review_expiry_recovers_only_after_recorded_review(self):
        inspect_agent_review(self.repairs,self.config)
        self.assertEqual(self.ticket('agent-review-stale')['state'],'open')
        (self.root/'agent-review.json').write_text(json.dumps({'at':now(),'summary':'Completed a real review'}))
        inspect_agent_review(self.repairs,self.config)
        self.assertEqual(self.ticket('agent-review-stale')['state'],'resolved')

    def test_recovered_transient_errors_remain_available_to_daily_review(self):
        self.samples([None,self.profile,self.profile,self.profile])
        inspect_sources(self.main.db,self.repairs,self.config)
        self.assertEqual(self.ticket('intermittent:example')['state'],'open')
        self.assertEqual(self.ticket('intermittent:example')['severity'],'info')
        self.assertEqual(self.monitor.db.execute('SELECT COUNT(*) FROM outbox').fetchone()[0],0)
        self.samples([self.profile]*96)
        inspect_sources(self.main.db,self.repairs,self.config)
        ticket=self.ticket('intermittent:example')
        self.assertEqual(ticket['state'],'resolved')
        self.assertIn('timeout',ticket['evidence'])

    def test_worker_outage_groups_source_staleness_into_one_alert(self):
        self.repairs.observe('worker-stale',True,'critical',{},'Inspect worker')
        inspect_sources(self.main.db,self.repairs,self.config)
        self.assertIsNone(self.ticket('stale-source:example'))
        self.assertEqual(self.monitor.db.execute('SELECT COUNT(*) FROM outbox').fetchone()[0],1)

    def test_sparse_feed_descriptions_are_not_false_alarms(self):
        sparse = dict(self.profile, description_fraction=0)
        self.assertNotIn('description_fraction_drop', anomaly_reasons(sparse, [sparse]*3, {}))
        self.assertIn('description_fraction_drop', anomaly_reasons(self.profile, [sparse]*3, {}))

    def test_destination_host_change_needs_review(self):
        changed = dict(self.profile, hosts=['new.example.org'])
        self.assertIn('new_destination_host', anomaly_reasons(self.profile, [changed]*3, {}))

    def test_baseline_does_not_learn_sustained_breakage_and_alerts_dedupe(self):
        self.samples([self.profile]*3)
        inspect_sources(self.main.db, self.repairs, self.config)
        low = dict(self.profile, count=10)
        self.samples([low]*3)
        for _ in range(5):
            inspect_sources(self.main.db, self.repairs, self.config)
        self.assertEqual(self.ticket('contract:example')['state'], 'open')
        self.assertEqual(self.ticket('contract:example')['occurrences'], 1)
        self.assertEqual(self.monitor.db.execute('SELECT COUNT(*) FROM outbox').fetchone()[0], 1)
        baseline = json.loads(self.monitor.db.execute('SELECT profile FROM source_baselines').fetchone()[0])
        self.assertEqual(baseline['count'], 100)

    def test_source_error_cannot_resolve_partial_result_incident(self):
        self.samples([self.profile]*3)
        inspect_sources(self.main.db, self.repairs, self.config)
        self.samples([dict(self.profile,count=2)]*3)
        inspect_sources(self.main.db, self.repairs, self.config)
        self.samples([None]*3)
        inspect_sources(self.main.db, self.repairs, self.config)
        self.assertEqual(self.ticket('contract:example')['state'], 'open')

    def test_failed_alert_survives_reopen_and_recovery_is_delivered_once(self):
        self.repairs.observe('test', True, 'warning', {'error':'fixture'}, 'Repair fixture')
        sender = Mock(); sender.send.side_effect = RuntimeError('temporary')
        deliver_pending(self.monitor, sender)
        self.monitor.close()
        self.monitor = Store(self.root/'maintenance.sqlite3')
        self.repairs = Repairs(self.monitor)
        with self.monitor.transaction():
            self.monitor.db.execute("UPDATE outbox SET next_attempt='2000-01-01'")
        sender.send.side_effect = None; sender.send.return_value = 'saved-receipt'
        self.assertEqual(deliver_pending(self.monitor,sender)['delivered'], 1)
        self.repairs.observe('test', False, 'warning', {}, 'Recovered')
        self.assertEqual(deliver_pending(self.monitor,sender)['delivered'], 1)
        self.repairs.observe('test', False, 'warning', {}, 'Recovered')
        self.assertEqual(deliver_pending(self.monitor,sender)['delivered'], 0)
        self.assertEqual(self.ticket('test')['state'], 'resolved')
        self.monitor.close()

    def test_local_backup_cannot_satisfy_offhost_requirement(self):
        for folder in ('local-backups','backups'):
            destination = self.root/folder
            destination.mkdir()
            (destination/'last-success.json').write_text(json.dumps({'at':now(), 'local_only':True,
                'restored_database_verified':True,'snapshot_id':None}))
        inspect_backups(self.repairs,self.config)
        self.assertIsNone(self.ticket('backup:local'))
        self.assertEqual(self.ticket('backup:offhost')['state'], 'open')

    def test_stale_or_unverified_backup_is_reported(self):
        destination = self.root/'backups'; destination.mkdir()
        (destination/'last-success.json').write_text(json.dumps({'at':'2000-01-01', 'local_only':False,
                'restored_database_verified':True,'snapshot_id':'abc'}))
        inspect_backups(self.repairs,self.config)
        self.assertEqual(self.ticket('backup:offhost')['state'], 'open')

    def test_weekly_canary_is_durable_and_uses_worker_delivery(self):
        one = schedule_canary(self.main.db, self.monitor, {})
        self.assertEqual(one['status'], 'pending')
        schedule_canary(self.main.db, self.monitor, {})
        self.assertEqual(self.main.db.execute('SELECT COUNT(*) FROM outbox').fetchone()[0], 1)
        sender = Mock(); sender.send.return_value = 'discord-id'
        deliver_pending(self.main, sender)
        self.assertEqual(schedule_canary(self.main.db,self.monitor,{})['receipt_id'], 'discord-id')

    def test_report_escapes_untrusted_source_text(self):
        self.repairs.observe('<script>bad()</script>', True, 'warning', {'title':'<img onerror=bad()>'}, 'Review')
        publish(self.monitor,self.root,{'at':now()})
        text = (self.root/'maintenance.html').read_text(encoding='utf8')
        self.assertNotIn('<img onerror', text)
        self.assertNotIn('<script>bad()', text)

    def test_missing_main_database_is_not_recreated_and_alert_uses_separate_store(self):
        config = dict(self.config, database=str(self.root/'missing.sqlite3'), maintenance={
            'state_database':str(self.root/'separate.sqlite3'), 'feed_metadata_audit':False})
        with patch('internship_watch.maintenance.heartbeat') as beat:
            result = run_maintenance(config, sender=Mock())
        self.assertFalse(Path(config['database']).exists())
        self.assertIn('storage_error',result['checks'])
        self.assertTrue(any(call.args == ('/fail',) for call in beat.call_args_list))
        self.assertTrue((self.root/'export/maintenance.html').exists())

    def test_full_path_canary_then_supervisor_restart_no_duplicate(self):
        with patch('internship_watch.runner.heartbeat'), patch('internship_watch.maintenance.heartbeat'):
            for _ in range(3):
                run_once(self.config,collector=lambda s,c:[job()],client=Mock(),sender=Mock(),validator=verified)
            first = run_maintenance(self.config,sender=Mock())
            self.assertEqual(first['checks']['sources']['with_live_samples'],1)
            run_once(self.config,collector=lambda s,c:[job()],client=Mock(),sender=Mock(),validator=verified)
            second = run_maintenance(self.config,sender=Mock())
        self.assertEqual(second['checks']['notification_canary']['status'],'delivered')
        self.assertEqual(self.main.db.execute("SELECT COUNT(*) FROM outbox WHERE dedupe_key LIKE 'maintenance-canary:%'").fetchone()[0],1)
        self.assertEqual(second['delivery']['delivered'],0)

    def test_feed_migration_and_staleness_detected_with_cached_daily_calls(self):
        source = {'id':'simplify','type':'simplify','url':'https://raw.githubusercontent.com/owner/old/dev/listings.json'}
        config = dict(self.config,sources=[source])
        client = Mock()
        response = Mock(); response.json.return_value = {'full_name':'owner/new','archived':False}
        commits = Mock(); commits.json.return_value = [{'sha':'abc','commit':{'committer':{'date':'2000-01-01T00:00:00Z'}}}]
        client.get.side_effect = [response,commits]
        result = audit_public_feeds(self.repairs,config,client)
        self.assertNotIn('error', result)
        self.assertEqual(self.ticket('feed-route:simplify')['state'],'open')
        self.assertEqual(self.ticket('feed-stale:simplify')['state'],'open')
        audit_public_feeds(self.repairs,config,client)
        self.assertEqual(client.get.call_count,2)

    def test_feed_access_failure_stays_unverified_and_retries_bounded(self):
        config = dict(self.config,sources=[{'id':'simplify','type':'simplify','url':'https://raw.githubusercontent.com/a/b/dev/file.json'}])
        client = Mock(); client.get.side_effect = TimeoutError('fixture')
        for _ in range(3):
            result = audit_public_feeds(self.repairs,config,client)
            previous = dict(result,at='2000-01-01')
            with self.monitor.transaction():
                self.monitor.db.execute("INSERT OR REPLACE INTO meta VALUES('feed_audit',?)",(json.dumps(previous),))
        self.assertEqual(self.ticket('feed-audit-access')['state'],'open')
        self.assertEqual(result['error'],'TimeoutError')


if __name__ == '__main__':
    unittest.main()

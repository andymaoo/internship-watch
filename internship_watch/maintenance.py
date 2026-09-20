"""Independent maintenance supervisor. Source content is evidence, never code.

Read the worker DB, retain accepted baselines and repair tickets in a separate
SQLite DB, deliver deduplicated alerts, and publish a private repair report.
No automated patching, filter relaxation, or source-access bypass lives here.
"""
import argparse
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import html
import json
import os
from pathlib import Path
import shutil
import sqlite3
import statistics
import tempfile
import time
import traceback
from urllib.parse import quote, urlsplit

from .delivery import configured_sender, deliver_pending, heartbeat
from .locking import AlreadyRunning, run_lock
from .safeguards import source_revision
from .storage import Store, dump, now


SCHEMA = '''
CREATE TABLE IF NOT EXISTS repair_tickets(key TEXT PRIMARY KEY,severity TEXT NOT NULL,
 state TEXT NOT NULL,first_seen TEXT NOT NULL,last_seen TEXT NOT NULL,resolved_at TEXT,
 occurrences INTEGER NOT NULL,evidence TEXT NOT NULL,action TEXT NOT NULL,signature TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS repair_events(id INTEGER PRIMARY KEY,ticket TEXT NOT NULL,
 at TEXT NOT NULL,event TEXT NOT NULL,evidence TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS source_baselines(source TEXT PRIMARY KEY,revision TEXT NOT NULL,
 accepted_at TEXT NOT NULL,profile TEXT NOT NULL,reason TEXT NOT NULL);
'''


def age(value, current=None):
    if not value:
        return float('inf')
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return max(0, ((current or datetime.now(timezone.utc)) - parsed).total_seconds())


def atomic_json(path, value):
    atomic_text(path, json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def atomic_text(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix='.' + path.name, dir=path.parent)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
            stream.write(value)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class Repairs:
    def __init__(self, store):
        self.store = store
        store.db.executescript(SCHEMA)

    def observe(self, key, active, severity, evidence, action, alert=True):
        previous = self.store.db.execute('SELECT * FROM repair_tickets WHERE key=?', (key,)).fetchone()
        if not active and not previous:
            return
        stamp = now()
        signature = hashlib.sha256(dump(evidence).encode()).hexdigest()
        state = 'open' if active else 'resolved'
        changed = not previous or previous['state'] != state or (active and previous['signature'] != signature)
        with self.store.transaction():
            if active:
                self.store.db.execute('INSERT INTO repair_tickets VALUES(?,?,?,?,?,NULL,1,?,?,?) '
                    'ON CONFLICT(key) DO UPDATE SET severity=excluded.severity,state=excluded.state,last_seen=excluded.last_seen,'
                    'resolved_at=NULL,occurrences=repair_tickets.occurrences+?,evidence=excluded.evidence,'
                    'action=excluded.action,signature=excluded.signature',
                    (key, severity, state, stamp, stamp, dump(evidence), action, signature, int(changed)))
            else:
                self.store.db.execute("UPDATE repair_tickets SET state='resolved',resolved_at=? WHERE key=? AND state!='resolved'", (stamp, key))
            if changed:
                self.store.db.execute('INSERT INTO repair_events(ticket,at,event,evidence) VALUES(?,?,?,?)',
                                      (key, stamp, state, dump(evidence)))
                # Preserve the latest 50 observations for each issue, including
                # recurrences, without retaining every unchanged poll forever.
                self.store.db.execute('DELETE FROM repair_events WHERE ticket=? AND id NOT IN '
                    '(SELECT id FROM repair_events WHERE ticket=? ORDER BY id DESC LIMIT 50)', (key, key))
            if alert:
                self.store.incident('maintenance:' + key, active,
                    f'Maintenance [{severity}]: {key}\n{dump(evidence)[:950]}\nNext: {action[:450]}\nDetails: private maintenance.html report.')


def anomaly_reasons(baseline, recent, settings):
    """Require consecutive successful *polls*, not three supervisor invocations."""
    required = settings.get('anomaly_consecutive_polls', 3)
    if len(recent) < required or any(row is None for row in recent[:required]):
        return []
    recent = recent[:required]
    reasons = []
    count = baseline['count']
    if count >= settings.get('volume_minimum', 20) and all(
            row['count'] < count * settings.get('volume_ratio', 0.5) for row in recent):
        reasons.append('result_count_drop')
    for field in ('description_fraction', 'location_fraction', 'url_fraction'):
        if baseline.get(field, 0) >= 0.7 and all(row['count'] and row.get(field, 0) < 0.2 for row in recent):
            reasons.append(field + '_drop')
    old_hosts = set(baseline.get('hosts', []))
    if old_hosts and all(row['count'] and set(row.get('hosts', [])) - old_hosts for row in recent):
        reasons.append('new_destination_host')
    return reasons


def inspect_sources(db, repairs, config):
    settings = config.get('maintenance', {})
    required = settings.get('anomaly_consecutive_polls', 3)
    sources = [s for s in config['sources'] if s.get('enabled', True)]
    checked = 0
    worker_incident = repairs.store.db.execute("SELECT state FROM repair_tickets WHERE key='worker-stale'").fetchone()
    worker_stale = worker_incident and worker_incident['state'] == 'open'
    for source in sources:
        key, revision = source['id'], source_revision(source)
        state = db.execute('SELECT * FROM source_state WHERE source=?', (key,)).fetchone()
        state = dict(state) if state else {}
        failures = state.get('failures', 0)
        repairs.observe('source:' + key, failures >= config.get('failure_threshold', 3), 'warning',
            {'source': key, 'last_error': state.get('last_error'), 'failures': failures,
             'last_success': state.get('last_success')},
            'Reproduce the adapter failure under existing rate/access rules; add a regression test before repair.', alert=False)
        rows = db.execute('SELECT * FROM source_samples WHERE source=? AND revision=? ORDER BY id DESC LIMIT 96', (key, revision)).fetchall()
        samples = [json.loads(row['profile']) if row['profile'] and not row['error'] else None for row in rows]
        # A dead worker is one incident, not hundreds of source-staleness alerts.
        # Existing per-source incidents wait for real observations to resume.
        if not worker_stale:
            repairs.observe('stale-source:' + key,
                age(state.get('last_attempt')) > settings.get('source_stale_seconds', 1800), 'warning',
                {'source': key, 'last_attempt': state.get('last_attempt')}, 'Check scheduling, disabled sources and collection time budgets.')
        errors = [{'at': row['checked_at'], 'run_id': row['run_id'], 'error': row['error']} for row in rows if row['error']]
        # Retain transient failures even after recovery, for the daily review.
        repairs.observe('intermittent:' + key, bool(errors), 'info', {'source': key, 'recent_error_count': len(errors), 'examples': errors[:5]},
            'Review recurring errors and reproduce suspected parser/pagination defects. A transient timeout alone does not justify a code change.', alert=False)
        if not rows:
            continue  # New runtime needs samples; absence never resolves an old incident.
        checked += 1
        baseline = repairs.store.db.execute('SELECT * FROM source_baselines WHERE source=?', (key,)).fetchone()
        if not baseline or baseline['revision'] != revision:
            if len(samples) >= 3 and all(samples[:3]):
                # A new source/config establishes a baseline after three actual
                # successes. A zero board remains valid, but cannot prove coverage.
                profile = dict(samples[0])
                profile['count'] = statistics.median(row['count'] for row in samples[:3])
                with repairs.store.transaction():
                    repairs.store.db.execute('INSERT OR REPLACE INTO source_baselines VALUES(?,?,?,?,?)',
                        (key, revision, now(), dump(profile), 'Three successful polls for this source configuration'))
            continue
        accepted = json.loads(baseline['profile'])
        reasons = anomaly_reasons(accepted, samples, settings)
        if source.get('type') == 'simplify':
            reasons = [reason for reason in reasons if reason != 'new_destination_host']
        ticket = 'contract:' + key
        # A failed poll is not evidence that a previous partial-result problem recovered.
        if len(samples) < required or any(row is None for row in samples[:required]):
            continue
        repairs.observe(ticket, bool(reasons), 'warning',
            {'source': key, 'reasons': reasons, 'baseline': accepted, 'latest': samples[:3], 'run_id': rows[0]['run_id']},
            'Check upstream schema/pagination and official careers URL. A legitimate seasonal drop needs an explicitly reviewed new baseline.')
        # Follow sustained growth, but do not gradually normalize a declining
        # count or missing-field problem into the accepted reference.
        if not reasons and all(row['count'] > accepted['count'] * 1.2 for row in samples[:3]):
            accepted['count'] = statistics.median(row['count'] for row in samples[:3])
            with repairs.store.transaction():
                repairs.store.db.execute('UPDATE source_baselines SET profile=?,accepted_at=? WHERE source=?', (dump(accepted), now(), key))
    return {'enabled': len(sources), 'with_live_samples': checked}


def inspect_worker(db, repairs, config):
    settings = config.get('maintenance', {})
    last = db.execute("SELECT * FROM runs WHERE status IN ('ok','degraded') ORDER BY id DESC LIMIT 1").fetchone()
    completed = last['finished_at'] if last else None
    repairs.observe('worker-stale', age(completed) > settings.get('worker_stale_seconds', 1200), 'critical',
        {'last_completed': completed}, 'Inspect systemd and disk/database health; restart only after identifying the failure.')
    runs = db.execute("SELECT summary FROM runs WHERE status IN ('ok','degraded') ORDER BY id DESC LIMIT 6").fetchall()
    summaries = [json.loads(row['summary'] or '{}') for row in runs]
    times = [row.get('timings_seconds', {}).get('total', 0) for row in summaries]
    repairs.observe('polling-overrun', len(times) >= 3 and all(t > config.get('poll_seconds', 300) * 1.5 for t in times[:3]), 'warning',
        {'recent_seconds': times[:3], 'target_seconds': config.get('poll_seconds', 300)},
        'Inspect slow sources and validation workload; preserve request limits and no-overlap locking.')
    due = db.execute("SELECT COUNT(*) count,MIN(COALESCE(next_check,first_seen)) oldest FROM jobs WHERE classification='include' "
                     "AND (next_check IS NULL OR next_check<=?)", (now(),)).fetchone()
    stale = bool(due['count']) and age(due['oldest']) > settings.get('validation_lag_seconds', 7200)
    repairs.observe('validation-lag', stale, 'warning', {'qualifying_due': due['count'], 'oldest_due': due['oldest']},
        'Inspect validation throughput and access failures. Pending checks remain unverified; do not force open/closed statuses.')
    backlog = [s.get('metrics', {}).get('validation_due') for s in summaries]
    growth = len(backlog) == 6 and all(isinstance(n, int) for n in backlog) and all(a > b for a, b in zip(backlog, backlog[1:])) and backlog[0] - backlog[-1] >= 50
    repairs.observe('validation-backlog-growth', growth, 'warning', {'recent_due': backlog}, 'Investigate sustained backlog growth and prioritize qualifying new records.')
    failures = db.execute("SELECT COUNT(*) count,MIN(created_at) oldest,MAX(attempts) attempts FROM outbox WHERE status='pending' AND attempts>0").fetchone()
    repairs.observe('worker-notification-failure', bool(failures['count']) and (failures['attempts'] >= 3 or age(failures['oldest']) > 3600), 'critical',
        dict(failures), 'Check the private webhook configuration and provider status; keep failed messages queued.')
    return {'last_completed': completed, 'latest_run': last['id'] if last else None,
            'recent_run_seconds': times, 'qualifying_validation_due': due['count']}


def inspect_backups(repairs, config):
    settings = config.get('maintenance', {})
    base = Path(config['database']).parent
    results = {}
    for kind, folder in [('local', 'local-backups'), ('offhost', 'backups')]:
        path = Path(settings.get(kind + '_backup_status', str(base / folder / 'last-success.json')))
        try:
            result = json.loads(path.read_text(encoding='utf-8'))
            valid = result.get('restored_database_verified') is True and (kind != 'offhost' or
                      (result.get('local_only') is False and bool(result.get('snapshot_id'))))
            recent = age(result.get('at')) <= settings.get('backup_max_age_seconds', 129600)
        except (OSError, ValueError, TypeError):
            result, valid, recent = {}, False, False
        results[kind] = {'valid_restore': valid, 'recent': recent, 'at': result.get('at')}
        repairs.observe('backup:' + kind, not (valid and recent), 'warning', results[kind],
            'Inspect the backup service and restore proof.' if kind == 'local' else
            'Configure the private off-host bucket credentials in /etc/internship-watch-backup.env, then run and verify the backup service.')
    return results


def inspect_agent_review(repairs, config):
    path = Path(config['database']).parent / 'agent-review.json'
    try:
        result = json.loads(path.read_text(encoding='utf-8'))
        stale = age(result.get('at')) > config.get('maintenance', {}).get('agent_review_max_age_seconds', 3*86400)
    except (OSError, ValueError, TypeError):
        result, stale = {}, True
    repairs.observe('agent-review-stale', stale, 'warning', {'last_review': result.get('at')},
        'Open Codex on the Windows PC and check the daily maintenance follow-up, SSH access and usage availability. Azure checks still operate independently.')
    return result


def audit_public_feeds(repairs, config, client=None):
    """Daily metadata check independent of whether an old feed still parses."""
    from .http import HttpClient
    key = 'feed_audit'
    previous = repairs.store.db.execute('SELECT value FROM meta WHERE key=?', (key,)).fetchone()
    previous = json.loads(previous['value']) if previous else {}
    interval = 3600 if previous.get('error') else 86400
    if age(previous.get('at')) < interval:
        return dict(previous, cached=True)
    own = client is None
    client = client or HttpClient(**config.get('http', {}))
    client.deadline = time.monotonic() + 45
    result = {'at': now(), 'feeds': []}
    try:
        for source in config.get('sources', []):
            if source.get('type') != 'simplify' or not source.get('enabled', True):
                continue
            parsed = urlsplit(source['url'])
            parts = parsed.path.strip('/').split('/', 3)
            if parsed.hostname != 'raw.githubusercontent.com' or len(parts) != 4:
                raise ValueError('Unsupported public feed route; review source configuration')
            owner, repo, branch, path = parts
            api = 'https://api.github.com/repos/' + quote(owner, safe='') + '/' + quote(repo, safe='')
            response = client.get(api, respect_robots=False, allow_redirects=True)
            response.raise_for_status()
            metadata = response.json()
            response = client.get(api + '/commits', params={'sha': branch, 'path': path, 'per_page': 1}, respect_robots=False, allow_redirects=True)
            response.raise_for_status()
            commits = response.json()
            if not isinstance(commits, list) or not commits:
                raise ValueError('Configured feed path has no commit on the configured branch')
            committed = commits[0]['commit']['committer']['date']
            evidence = {'source': source['id'], 'configured_repository': owner+'/'+repo,
                'canonical_repository': metadata['full_name'], 'archived': metadata.get('archived'),
                'branch': branch, 'path': path, 'last_feed_commit': committed, 'commit': commits[0]['sha']}
            repairs.observe('feed-route:' + source['id'], bool(metadata.get('archived')) or metadata['full_name'].casefold() != (owner+'/'+repo).casefold(),
                'warning', evidence, 'Review the canonical repository, season and branch before updating the feed; retain job identities and notification history.')
            repairs.observe('feed-stale:' + source['id'], age(committed) > config.get('maintenance', {}).get('feed_stale_seconds', 14*86400),
                'warning', evidence, 'Check whether the public feed moved to a new season or stopped exporting. No change in the feed does not prove there are no new jobs.')
            result['feeds'].append(evidence)
        repairs.observe('feed-audit-access', False, 'warning', {}, 'Retry GitHub metadata checks under its rate limits.')
    except Exception as exc:
        result.update(error=type(exc).__name__, failures=previous.get('failures', 0)+1)
        repairs.observe('feed-audit-access', result['failures'] >= 3, 'warning', result,
            'Check GitHub API availability, feed repository/branch/path and access limits. Collection status remains independently monitored.')
    finally:
        if own:
            client.close()
    with repairs.store.transaction():
        repairs.store.db.execute('INSERT OR REPLACE INTO meta VALUES(?,?)', (key, dump(result)))
    return result


def schedule_canary(db, store, settings):
    """A weekly receipt proves the real worker's durable delivery route."""
    week = datetime.now(timezone.utc).strftime('%G-W%V')
    key = 'maintenance-canary:' + week
    if not settings.get('notification_canary', True):
        return None
    db.execute("INSERT OR IGNORE INTO outbox(dedupe_key,kind,payload,created_at,next_attempt) VALUES(?,?,?,?,?)",
        (key, 'digest', dump({'title': 'Internship Watch weekly delivery check',
         'body': 'Scheduled maintenance test: the worker delivered this through its normal persistent notification queue. No application action is needed.'}), now(), now()))
    db.commit()
    receipt = db.execute('SELECT status,attempts,created_at,delivered_at,receipt_id FROM outbox WHERE dedupe_key=?', (key,)).fetchone()
    return dict(receipt)


def publish(store, directory, summary):
    tickets = store.rows('SELECT * FROM repair_tickets ORDER BY state,first_seen DESC')
    for ticket in tickets:
        ticket['evidence'] = json.loads(ticket['evidence'])
    report = dict(summary, tickets=tickets)
    atomic_json(Path(directory) / 'maintenance.json', report)
    esc = lambda value: html.escape(str(value or ''), quote=True)
    rows = ''.join('<tr><td>' + esc(t['state']) + '</td><td>' + esc(t['severity']) + '</td><td>' + esc(t['key']) +
        '</td><td>' + esc(t['last_seen']) + '</td><td>' + esc(t['action']) + '<details><summary>Evidence</summary><pre>' +
        esc(json.dumps(t['evidence'], indent=2)) + '</pre></details></td></tr>' for t in tickets)
    page = '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
    page += '<title>Maintenance — Internship Watch</title><style>body{font:16px system-ui;margin:2rem;color:#17243a;background:#f6f7fb}td,th{padding:.7rem;border:1px solid #ccd;vertical-align:top;text-align:left}table{border-collapse:collapse}pre{white-space:pre-wrap;overflow-wrap:anywhere}input{padding:.7rem;margin:1rem 0}</style>'
    page += '<h1>Maintenance and repair backlog</h1><p><a href="jobs.html">Jobs</a> · <a href="maintenance.json">Evidence JSON</a></p><p>Checked ' + esc(summary['at']) + '. Source changes are observations requiring review; they are not automatically confirmed bugs. A passing monitor cannot prove complete market coverage.</p>'
    page += '<input id="q" placeholder="Filter issues" aria-label="Filter issues"><table><thead><tr><th>State</th><th>Severity</th><th>Issue</th><th>Last observed</th><th>Next step</th></tr></thead><tbody>' + rows + '</tbody></table>'
    page += '<script>document.getElementById("q").addEventListener("input",function(){for(const r of document.querySelectorAll("tbody tr"))r.hidden=!r.textContent.toLowerCase().includes(this.value.toLowerCase());});</script></html>'
    atomic_text(Path(directory) / 'maintenance.html', page)
    return report


def run_maintenance(config, sender=None):
    settings = config.get('maintenance', {})
    base = Path(config['database']).parent
    path = Path(settings.get('state_database', str(base / 'maintenance.sqlite3')))
    output = Path(config.get('export_directory', str(base / 'export')))
    with run_lock(str(path) + '.lock'):
        store = Store(path)
        repairs = Repairs(store)
        try:
            return _run(config, repairs, output, sender or configured_sender(config))
        finally:
            store.close()


def _run(config, repairs, output, sender):
    started = time.monotonic()
    settings = config.get('maintenance', {})
    store = repairs.store
    summary = {'at': now(), 'mode': 'independent supervisor', 'checks': {}}
    try:
        heartbeat('/start', env_name='MAINTENANCE_HEALTHCHECKS_PING_URL')
        summary['monitor_configured'] = bool(os.environ.get('MAINTENANCE_HEALTHCHECKS_PING_URL'))
    except Exception:
        summary['monitor_configured'] = True
        summary['heartbeat_start_failed'] = True
    try:
        with closing(sqlite3.connect(Path(config['database']).resolve().as_uri() + '?mode=rw', uri=True, timeout=10)) as db:
            db.row_factory = sqlite3.Row
            # The monitor never creates a replacement jobs DB if storage goes missing.
            summary['checks']['worker'] = inspect_worker(db, repairs, config)
            summary['checks']['sources'] = inspect_sources(db, repairs, config)
            canary = schedule_canary(db, store, settings)
            summary['checks']['notification_canary'] = canary
            repairs.observe('notification-canary', bool(canary and canary['status'] != 'delivered' and age(canary['created_at']) > 1800),
                'critical', canary, 'Inspect the worker outbox and Discord delivery; this weekly canary must receive a saved message receipt.')
            marker = store.db.execute("SELECT value FROM meta WHERE key='integrity_checked_at'").fetchone()
            if not marker or age(marker['value']) > 86400:
                integrity = [tuple(row) for row in db.execute('PRAGMA quick_check')]
                if integrity != [('ok',)]:
                    raise sqlite3.DatabaseError('Database quick_check failed')
                with store.transaction():
                    store.db.execute("INSERT OR REPLACE INTO meta VALUES('integrity_checked_at',?)", (now(),))
            repairs.observe('storage', False, 'critical', {}, 'Inspect SQLite integrity, permissions and free space.')
    except Exception as exc:
        # Do not leak arbitrary exception text (which can contain credentials).
        summary['checks']['storage_error'] = type(exc).__name__
        frame = traceback.extract_tb(exc.__traceback__)[-1]
        repairs.observe('storage', True, 'critical', {'error_type': type(exc).__name__, 'code_location': Path(frame.filename).name + ':' + str(frame.lineno)},
            'Read the host journal privately; inspect SQLite integrity, permissions, disk space and monitor compatibility. Existing records were not replaced.')
    usage = shutil.disk_usage(Path(config['database']).parent)
    minimum = settings.get('disk_min_free_bytes', 2 * 1024**3)
    repairs.observe('disk-space', usage.free < minimum or usage.free / usage.total < 0.1, 'critical',
        {'free_bytes': usage.free, 'total_bytes': usage.total}, 'Free reviewed old artifacts or increase storage; preserve the live DB and verified backups.')
    report_path = output / 'jobs.html'
    report_age = max(0, time.time() - report_path.stat().st_mtime) if report_path.exists() else None
    repairs.observe('report-stale', report_age is None or report_age > settings.get('report_stale_seconds', 1800), 'warning',
        {'age_seconds': round(report_age) if report_age is not None else None}, 'Check the worker export stage and filesystem permissions.')
    summary['checks']['backups'] = inspect_backups(repairs, config)
    if settings.get('agent_review_monitor', False):
        summary['checks']['agent_review'] = inspect_agent_review(repairs, config)
    if settings.get('feed_metadata_audit', True):
        summary['checks']['public_feeds'] = audit_public_feeds(repairs, config)
    gaps = [c['company'] for c in config.get('company_watchlist', []) if not c.get('direct_sources')]
    repairs.observe('coverage-gaps', bool(gaps), 'info', {'companies': gaps},
        'Weekly review: look for permitted structured employer routes. Public-feed-only coverage remains incomplete.', alert=False)
    repairs.observe('independent-monitor-unconfigured', not summary['monitor_configured'], 'warning', {},
        'Set MAINTENANCE_HEALTHCHECKS_PING_URL in /etc/internship-watch.env to a separate Healthchecks check with email alerts.')
    week = datetime.now(timezone.utc).strftime('%G-W%V')
    outstanding = store.rows("SELECT key FROM repair_tickets WHERE state='open' AND severity!='info' ORDER BY first_seen")
    # Weekly reminder starts after one week, avoiding an initial duplicate of
    # the incident alert. Stable keys survive supervisor restarts.
    first = store.db.execute("SELECT value FROM meta WHERE key='maintenance_started_at'").fetchone()
    with store.transaction():
        if not first:
            store.db.execute("INSERT INTO meta VALUES('maintenance_started_at',?)", (now(),))
        elif outstanding and age(first['value']) > 7*86400:
            store.queue('maintenance-reminder:' + week, 'digest', {'title': 'Outstanding maintenance issues',
                'body': f'{len(outstanding)} unresolved issues. ' + ', '.join(t['key'] for t in outstanding)[:1300] + '\nSee the private maintenance report. Previously reported issues are grouped in this weekly reminder.'})
    summary['delivery'] = deliver_pending(store, sender, limit=20)
    open_tickets = store.rows("SELECT key,severity FROM repair_tickets WHERE state='open'")
    summary['open_issues'] = len(open_tickets)
    critical = any(t['severity'] == 'critical' for t in open_tickets)
    pending_failed = store.db.execute("SELECT COUNT(*) FROM outbox WHERE status='pending' AND attempts>0").fetchone()[0]
    summary['seconds'] = round(time.monotonic() - started, 3)
    publish(store, output, summary)
    atomic_json(Path(store.path).parent / 'maintenance-last-run.json', summary)
    try:
        heartbeat('/fail' if critical or pending_failed else '', env_name='MAINTENANCE_HEALTHCHECKS_PING_URL')
    except Exception:
        summary['heartbeat_end_failed'] = True
    return summary


def main(argv=None):
    from .cli import load_config, load_env
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    parser.add_argument('--env-file')
    parser.add_argument('--accept-baseline', help='Source ID; requires reviewed evidence in --reason')
    parser.add_argument('--reason')
    parser.add_argument('--record-agent-review', action='store_true', help='Record an actually completed agent review; requires --reason')
    args = parser.parse_args(argv)
    if args.env_file:
        load_env(args.env_file)
    config = load_config(args.config)
    if args.record_agent_review:
        if not args.reason or len(args.reason.strip()) < 20:
            parser.error('A concrete completed review summary of at least 20 characters is required')
        atomic_json(Path(config['database']).parent / 'agent-review.json', {'at': now(), 'summary': args.reason})
        print(dump({'agent_review_recorded': True}))
        return
    if args.accept_baseline:
        if not args.reason or len(args.reason.strip()) < 20:
            parser.error('A concrete review reason of at least 20 characters is required')
        source = next(s for s in config['sources'] if s['id'] == args.accept_baseline)
        path = config.get('maintenance', {}).get('state_database', str(Path(config['database']).parent / 'maintenance.sqlite3'))
        with run_lock(path + '.lock'), closing(sqlite3.connect(Path(config['database']).resolve().as_uri()+'?mode=ro', uri=True)) as db:
            row = db.execute('SELECT profile FROM source_samples WHERE source=? AND revision=? AND error IS NULL ORDER BY id DESC LIMIT 1',
                             (source['id'], source_revision(source))).fetchone()
            if not row:
                raise RuntimeError('No successful live sample for the configured source')
            store = Store(path)
            try:
                Repairs(store)
                with store.transaction():
                    store.db.execute('INSERT OR REPLACE INTO source_baselines VALUES(?,?,?,?,?)',
                        (source['id'], source_revision(source), now(), row[0], args.reason))
                    store.db.execute('INSERT INTO repair_events(ticket,at,event,evidence) VALUES(?,?,?,?)',
                        ('contract:'+source['id'], now(), 'baseline reviewed', dump({'reason': args.reason, 'profile': json.loads(row[0])})))
            finally:
                store.close()
        print(dump({'baseline_accepted': source['id']}))
        return
    try:
        print(dump(run_maintenance(config)))
    except AlreadyRunning:
        print(dump({'skipped': 'Maintenance already running'}))
    except Exception:
        # Independent missing-success deadline also catches failure of this DB,
        # report writing, or the monitor itself. No secret traceback is printed.
        try:
            heartbeat('/fail', env_name='MAINTENANCE_HEALTHCHECKS_PING_URL')
        except Exception:
            pass
        print(dump({'failed': 'Maintenance supervisor failed; inspect host configuration privately'}))
        raise SystemExit(1)


if __name__ == '__main__':
    main()

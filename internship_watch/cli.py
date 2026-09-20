"""Inspect/export locally; daemon for an always-on host, no public dashboard."""
import argparse
import csv
import html
import json
import logging
import os
import sys
import time
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

from .delivery import configured_sender, deliver_pending, heartbeat
from .http import allow_url
from .locking import AlreadyRunning, run_lock
from .runner import run_once
from .storage import Store, dump, now


def load_env(path):
    """Explicit private file only; no shell interpolation or credential logging."""
    allowed = {"DISCORD_WEBHOOK_URL", "OPS_DISCORD_WEBHOOK_URL", "HEALTHCHECKS_PING_URL", "MAINTENANCE_HEALTHCHECKS_PING_URL",
               "BACKUP_HEALTHCHECKS_PING_URL", "RESTIC_REPOSITORY", "RESTIC_PASSWORD_FILE",
               "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_DEFAULT_REGION", "RESTIC_CACHE_DIR",
               "NTFY_URL", "NTFY_TOKEN", "OPS_NTFY_URL", "OPS_NTFY_TOKEN"}
    seen = set()
    for number, line in enumerate(Path(path).read_text(encoding="utf-8-sig").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, sep, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if not sep or key not in allowed or key in seen:
            raise ValueError(f"Invalid/duplicate private environment field on line {number}")
        seen.add(key)
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        os.environ[key] = value


def load_config(path):
    config = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if config.get("poll_seconds", 300) < 60:
        raise ValueError("poll_seconds must be at least 60")
    ids = [s["id"] for s in config["sources"]]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate source IDs")
    # Paths are relative to the config file, not an arbitrary service cwd.
    config["database"] = str((Path(path).resolve().parent / config.get("database", "data/jobs.sqlite3")).resolve())
    if config.get("export_directory"):
        config["export_directory"] = str((Path(path).resolve().parent / config["export_directory"]).resolve())
    maintenance = config.get('maintenance', {})
    for name in ('state_database', 'local_backup_status', 'offhost_backup_status'):
        if maintenance.get(name):
            maintenance[name] = str((Path(path).resolve().parent / maintenance[name]).resolve())
    for name in ('anomaly_consecutive_polls', 'volume_minimum', 'worker_stale_seconds', 'source_stale_seconds',
                 'validation_lag_seconds', 'report_stale_seconds', 'backup_max_age_seconds', 'disk_min_free_bytes', 'feed_stale_seconds', 'agent_review_max_age_seconds'):
        if name in maintenance and (not isinstance(maintenance[name], int) or isinstance(maintenance[name], bool) or maintenance[name] <= 0):
            raise ValueError(f'maintenance.{name} must be a positive integer')
    if not 0 < maintenance.get('volume_ratio', 0.5) < 1:
        raise ValueError('maintenance.volume_ratio must be between zero and one')
    if maintenance.get('anomaly_consecutive_polls', 3) > 96:
        raise ValueError('maintenance.anomaly_consecutive_polls exceeds retained poll history (96)')
    return config


def export(store, directory, config=None):
    """Publish complete individual files; write HTML last so readers never see truncation."""
    output = Path(directory)
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".export-", dir=output.parent) as temporary:
        result = _export(store, temporary, config)
        files = sorted(Path(temporary).iterdir(), key=lambda p: p.name == "jobs.html")
        for path in files:
            os.replace(path, output / path.name)
    return dict(result, directory=str(output.resolve()))


def _export(store, directory, config=None):
    output = Path(directory)
    output.mkdir(parents=True, exist_ok=True)
    rows = store.rows("SELECT * FROM jobs WHERE classification='include' OR (classification='ambiguous' "
                      "AND json_extract(evidence,'$.positive_opportunity_evidence')=1) ORDER BY first_seen DESC,title")
    columns = ["id", "employer", "title", "category", "location", "classification", "status", "posting_status", "application_status", "posting_date",
               "first_seen", "last_seen", "last_checked", "original_url", "final_url", "application_url",
               "final_application_url", "description", "employment_type", "evidence", "baseline", "first_qualifying_at", "notification_decided_at"]
    with (output / "jobs.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        # Keep spreadsheet formula interpretation out of untrusted employer text.
        writer.writerows({k: "'" + v if isinstance(v, str) and v.startswith(("=", "+", "-", "@", "\t", "\r")) else v
                          for k, v in row.items()} for row in rows)
    (output / "jobs.json").write_text(dump(rows), encoding="utf-8")
    sources = store.rows("SELECT * FROM source_state ORDER BY source")
    if config:
        known_sources = {row["source"] for row in sources}
        for source in config.get("sources", []):
            if not source.get("enabled", True):
                sources.append({"source": source["id"], "status": "disabled", "reason": source.get("disabled_reason", "Disabled in configuration")})
            elif source["id"] not in known_sources:
                sources.append({"source": source["id"], "status": "not_checked"})
    checks = store.rows("SELECT j.id,j.employer,j.title,j.classification,j.status,j.posting_status,j.application_status,j.original_url,j.application_url,j.final_url,"
                        "j.final_application_url,j.first_seen,j.last_checked,c.result FROM jobs j LEFT JOIN link_checks c "
                        "ON c.id=(SELECT MAX(id) FROM link_checks WHERE job_id=j.id) WHERE j.classification='include' OR "
                        "(j.classification='ambiguous' AND json_extract(j.evidence,'$.positive_opportunity_evidence')=1) ORDER BY j.title")
    (output / "link-validation.json").write_text(dump(checks), encoding="utf-8")
    (output / "sources.json").write_text(dump(sources), encoding="utf-8")
    def esc(value):
        return html.escape(str(value or ""), quote=True)
    body = []
    for row in rows:
        if row["classification"] == "exclude":
            continue
        url = row["final_url"] or row["original_url"] or ""
        try:
            allow_url(url, resolve_dns=False)
            safe = True
        except (ValueError, TypeError):
            safe = False
        link = f'<a href="{esc(url)}" rel="noreferrer noopener" target="_blank">{esc(row["title"])}</a>' if safe else esc(row["title"])
        reasons = "; ".join(json.loads(row["evidence"]).get("reasons", []))
        app_url = row["final_application_url"] or row["application_url"] or ""
        app_link = ""
        try:
            allow_url(app_url, resolve_dns=False)
            app_link = f'<small><a href="{esc(app_url)}" rel="noreferrer noopener" target="_blank">Application destination</a></small>'
        except (ValueError, TypeError):
            pass
        body.append(f'<tr data-state="{esc(row["classification"])} {esc(row["posting_status"])}"><td data-label="Employer">{esc(row["employer"])}</td><td data-label="Role">{link}{app_link}</td>'
                    f'<td data-label="Category">{esc(row["category"])}</td><td data-label="Location">{esc(row["location"])}</td><td data-label="Status / reasons">{esc(row["classification"])} / posting: {esc(row["posting_status"])} / application: {esc(row["application_status"])}'
                    f'<small>{esc(reasons)}</small></td><td data-label="First seen">{esc(row["first_seen"])}</td><td data-label="Last checked">{esc(row["last_checked"] or "Not checked yet")}</td></tr>')
    page = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Internship Watch</title><style>body{font:15px system-ui;margin:32px;color:#15283d;background:#f5f7fb}h1{margin-bottom:6px}
input,select{padding:10px;margin:8px 12px 18px 0;max-width:100%;box-sizing:border-box}table{border-collapse:collapse;background:white;width:100%}td,th{padding:12px;text-align:left;border-bottom:1px solid #dbe2eb}th{background:#e5edf7}a{color:#165ba8}small{display:block;color:#657489;max-width:340px}tr[hidden]{display:none}
@media(max-width:900px){body{margin:20px}thead{display:none}table,tbody,tr,td{display:block}table{background:transparent}tr{background:white;border:1px solid #dbe2eb;border-radius:8px;margin:16px 0;padding:8px}td{padding:7px 8px;border:0;overflow-wrap:anywhere}td:before{content:attr(data-label);display:block;font-size:11px;text-transform:uppercase;letter-spacing:.04em;color:#657489;margin-bottom:3px}td:first-child{font-weight:700}input,select{width:100%;margin:8px 0}small{max-width:none}}</style>
<h1>Internship Watch</h1><p>Internships and configured research programs. Posting validity and application accessibility are checked separately. Verified matches have a verified employer posting; application access may still need review or a browser.</p>
<p>Confirm the recruiting cohort and employer eligibility requirements before applying; an available form alone does not prove a cohort is still recruiting.</p>
<p>Exported __DATE__. <a href="jobs.csv">CSV</a> · <a href="jobs.json">Full records</a> · <a href="link-validation.json">Link evidence</a> · <a href="sources.json">Source health</a> · <a href="coverage.html">Company coverage</a> · <a href="maintenance.html">Maintenance</a></p>
<input id="search" type="search" aria-label="Search jobs" placeholder="Company, role, location"><select id="filter" aria-label="Listing status"><option value="include open">Verified matches</option><option value="include">All matches</option><option value="ambiguous">Needs review</option><option value="">All collected candidates</option></select><span id="count"></span>
<table><thead><tr><th>Employer</th><th>Role</th><th>Category</th><th>Location</th><th>Status / reasons</th><th>First seen</th><th>Last checked</th></tr></thead><tbody>__ROWS__</tbody></table>
<script>const search=document.getElementById('search'),filter=document.getElementById('filter');function refresh(){let n=0;for(const row of document.querySelectorAll('tbody tr')){row.hidden=!(row.textContent.toLowerCase().includes(search.value.toLowerCase())&&row.dataset.state.includes(filter.value));if(!row.hidden)n++;}document.getElementById('count').textContent=n+' listings';}search.addEventListener('input',refresh);filter.addEventListener('change',refresh);refresh();</script></html>'''
    (output / "jobs.html").write_text(page.replace("__DATE__", esc(now())).replace("__ROWS__", "".join(body)), encoding="utf-8")
    from .coverage import export_coverage
    export_coverage(store, output, config or {})
    return {"jobs": len(rows), "directory": str(output.resolve())}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--env-file", help="Private KEY=value file; values never printed")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("run", help="Collect, check links, and deliver once")
    sub.add_parser("daemon", help="Poll on a fixed interval; skip overlaps")
    sub.add_parser("status")
    p = sub.add_parser("export"); p.add_argument("--output", default="data/export")
    p = sub.add_parser("import-seen"); p.add_argument("path")
    p = sub.add_parser("backup"); p.add_argument("path")
    p = sub.add_parser("test-notification"); p.add_argument("--operational", action="store_true")
    sub.add_parser("test-failure-alert", help="Send a labeled operational test alert and mark heartbeat failed")
    sub.add_parser("drain", help="Retry due notifications without collecting")
    args = parser.parse_args(argv)
    if args.env_file:
        load_env(args.env_file)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    config = load_config(args.config)
    if args.command in ("run", "daemon"):
        while True:
            started = time.monotonic()
            try:
                print(dump(run_once(config)), flush=True)
            except AlreadyRunning:
                logging.warning("Skipped overlap")
            except Exception:
                if args.command == "run":
                    raise
                logging.exception("Poll failed; will retry next interval")
            if args.command == "run":
                return
            time.sleep(max(1, config.get("poll_seconds", 300) - (time.monotonic() - started)))
    elif args.command in ("test-notification", "test-failure-alert"):
        operational = args.command == "test-failure-alert" or args.operational
        receipt = configured_sender(config).send({"title": "Internship Watch TEST", "body": "Operational alert test — no real outage." if operational else "Notification delivery test."}, operational=operational)
        if args.command == "test-failure-alert":
            heartbeat("/fail")
        print(dump({"acknowledged": True, "message_id": receipt, "operational": operational}))
    else:
        store = Store(config["database"])
        try:
            if args.command == "status":
                result = {"runs": store.rows("SELECT * FROM runs ORDER BY id DESC LIMIT 5"),
                          "sources": store.rows("SELECT * FROM source_state"),
                          "jobs": store.rows("SELECT classification,status,COUNT(*) count FROM jobs GROUP BY classification,status"),
                          "notifications": store.rows("SELECT status,COUNT(*) count FROM outbox GROUP BY status"),
                          "incidents": store.rows("SELECT * FROM incidents WHERE active=1")}
            elif args.command == "export":
                result = export(store, args.output, config)
            elif args.command == "backup":
                store.backup(args.path); result = {"backup": args.path}
            elif args.command == "import-seen":
                with run_lock(config["database"] + ".lock"):
                    result = {"legacy_ids_imported": store.import_legacy(args.path)}
            elif args.command == "drain":
                with run_lock(config["database"] + ".lock"):
                    result = deliver_pending(store, configured_sender(config))
            print(dump(result))
        finally:
            store.close()


if __name__ == "__main__":
    main()

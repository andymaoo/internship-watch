"""One collection transaction per source, independent link checks, durable outbox."""
import json
import logging
import os
import time
from datetime import datetime, timedelta, timezone

from .classify import classify
from .delivery import configured_sender, deliver_pending, heartbeat
from .links import validate_job
from .locking import run_lock
from .storage import Store, dump, now, url_identity

log = logging.getLogger(__name__)


def later(seconds):
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat(timespec="seconds")


def job_message(row):
    url = row.get("final_application_url") or row.get("application_url") or row["original_url"]
    return {"title": "New internship", "body": f"{row['employer']} — {row['title']}\n{row['location']}\n{url}", "url": url}


def run_once(config, collector=None, client=None, validator=validate_job, sender=None):
    from .http import HttpClient
    from .sources import collect
    collector = collector or collect
    owns_client = client is None
    client = client or HttpClient(**config.get("http", {}))
    sender = sender or configured_sender(config)
    db_path = config.get("database", "data/jobs.sqlite3")
    try:
        with run_lock(str(db_path) + ".lock"):
            return _run(config, db_path, collector, client, validator, sender)
    finally:
        if owns_client:
            client.close()


def _run(config, db_path, collector, client, validator, sender):
    store = None
    run_id = None
    try:
        store = Store(db_path)
        rate_state = store.db.execute("SELECT value FROM meta WHERE key='http_rate_limits'").fetchone()
        if rate_state and callable(getattr(client, "load_rate_limits", None)):
            client.load_rate_limits(json.loads(rate_state["value"]))
        with store.transaction():
            # An incomplete prior run is retained as evidence after a crash.
            store.db.execute("UPDATE runs SET status='interrupted',finished_at=? WHERE status='running'", (now(),))
            run_id = store.db.execute("INSERT INTO runs(started_at,status) VALUES(?,'running')", (now(),)).lastrowid
        try:
            heartbeat("/start")
        except Exception as exc:
            log.warning("Heartbeat start failed: %s", exc)
        summary = {"sources": {}, "checked": 0, "run_id": run_id}
        threshold = config.get("failure_threshold", 3)
        initial = config.get("initial_run", "silent")
        if initial not in ("silent", "digest"):
            raise ValueError("initial_run must be silent or digest")
        for source in config.get("sources", []):
            if not source.get("enabled", True):
                continue
            key = source["id"]
            previous = store.source_state(key)
            try:
                jobs = collector(source, client)
                if not isinstance(jobs, list):
                    raise ValueError("Source returned a non-list result")
                with store.transaction():
                    for job in jobs:
                        classification = classify(job, config.get("filters", {}))
                        candidate = classification["decision"] == "include" or (
                            classification["decision"] == "ambiguous" and classification.get("positive_opportunity_evidence"))
                        if not candidate:
                            known = store.db.execute("SELECT 1 FROM source_records WHERE source=? AND source_id=?",
                                                     (key, str(job["source_id"]))).fetchone()
                            for field in ("description_url", "application_url"):
                                identity = url_identity(job.get(field))
                                if identity and store.db.execute("SELECT 1 FROM identities WHERE identity=?", ("url:" + identity,)).fetchone():
                                    known = True
                            if not known:
                                continue  # Keep candidates, while still applying later exclusion evidence.
                        store.upsert_job(key, job, classification, run_id,
                                         baseline=not previous["initialized"], filters=config.get("filters", {}))
                    state = store.record_source(key, count=len(jobs))
                    store.incident("source:" + key, False, "Recovered")
                    suspicious_empty = len(jobs) == 0 and (previous.get("last_count", 0) or previous["empty_runs"]
                                                               or source.get("expect_nonempty", False))
                    store.incident("empty:" + key, bool(suspicious_empty and state["empty_runs"] >= threshold),
                                   f"{key}: {state['empty_runs']} consecutive empty collections; verify source access/schema")
                summary["sources"][key] = {"count": len(jobs), "status": "ok"}
                log.info("source=%s status=ok count=%s", key, len(jobs))
            except Exception as exc:
                # HTTP source exceptions may carry public job URLs; secrets never enter adapters.
                detail = f"{type(exc).__name__}: {exc}"[:500]
                with store.transaction():
                    state = store.record_source(key, error=detail)
                    store.incident("source:" + key, state["failures"] >= threshold,
                                   f"{key}: failed {state['failures']} consecutive runs. {detail}")
                summary["sources"][key] = {"status": "failed", "error": detail}
                log.warning("source=%s status=failed error=%s", key, detail)
        # Previously discovered jobs are rechecked even if collection is temporarily down.
        limit = config.get("validation_budget", 100)
        pending = store.rows("SELECT * FROM jobs WHERE (classification='include' OR (classification='ambiguous' AND "
                             "json_extract(evidence,'$.positive_opportunity_evidence')=1) OR (classification='exclude' AND "
                             "json_extract(payload,'$.evidence.description_kind')='validated_destination')) AND "
                             "(next_check IS NULL OR next_check<=?) ORDER BY CASE WHEN classification='exclude' THEN 1 ELSE 0 END,baseline,last_checked IS NOT NULL,"
                             "CASE WHEN classification='include' THEN 0 ELSE 1 END,last_checked LIMIT ?",
                             (now(), limit))
        validation_deadline = time.monotonic() + config.get("validation_seconds", 60)
        client.deadline = validation_deadline
        for row in pending:
            if time.monotonic() >= validation_deadline:
                break
            job = json.loads(row["payload"])
            try:
                result = validator(job, client)
            except Exception as exc:
                result = {"status": "unverified", "checks": [{"error": f"{type(exc).__name__}: {exc}"[:300]}]}
            if result.get("status") not in ("open", "closed", "unverified"):
                result = {"status": "unverified", "checks": [{"error": "Invalid validator result"}]}
            delay = config.get("link_recheck_seconds", 86400) if result["status"] == "open" else (
                config.get("closed_recheck_seconds", 604800) if result["status"] == "closed" else config.get("unverified_recheck_seconds", 3600))
            with store.transaction():
                store.record_check(row["id"], result, later(delay))
                if result.get("description") and (not job.get("description") or
                        (job.get("evidence") or {}).get("description_kind") in {"employer_search_summary", "validated_destination"}):
                    job["description"] = result["description"]
                    job["evidence"] = dict(job.get("evidence") or {})
                    job["evidence"]["description_kind"] = "validated_destination"
                    decision = classify(job, config.get("filters", {}))
                    store.db.execute("UPDATE jobs SET description=?,payload=?,classification=?,category=?,evidence=? WHERE id=?",
                                     (job["description"], dump(job), decision["decision"], decision.get("category"), dump(decision), row["id"]))
            summary["checked"] += 1
        client.deadline = None
        with store.transaction():
            rate_snapshot = getattr(client, "rate_limits", lambda: None)()
            if isinstance(rate_snapshot, dict):
                store.db.execute("INSERT OR REPLACE INTO meta VALUES('http_rate_limits',?)", (dump(rate_snapshot),))
            if initial == "digest" and any(s["status"] == "ok" for s in summary["sources"].values()):
                matches = store.rows("SELECT * FROM jobs WHERE baseline=1 AND classification='include' ORDER BY employer,title")
                verified = [r for r in matches if r["status"] == "open"]
                lines = [f"{len(matches)} imported matches; {len(verified)} currently have both destinations verified. "
                         f"{len(matches) - len(verified)} are closed, unverified, or pending checks."]
                lines.extend(f"{r['employer']}: {r['title']}\n{r['final_application_url'] or r['application_url']}" for r in verified[:8])
                lines.append("This is one initial digest. Export jobs.html/CSV for the full list and pending checks.")
                store.queue("initial:digest", "digest", {"title": "Initial internship digest", "body": "\n\n".join(lines)[:1900]})
            for row in store.rows("SELECT * FROM jobs WHERE baseline=0 AND classification='include' AND status='open'"):
                store.queue("new:" + row["id"], "job", job_message(row))
        summary["delivery"] = deliver_pending(store, sender, limit=config.get("delivery_budget", 100))
        with store.transaction():
            failures = store.db.execute("SELECT COUNT(*) FROM outbox WHERE status='pending' AND attempts>=?", (threshold,)).fetchone()[0]
            store.incident("notifications", failures > 0, f"{failures} notifications remain undelivered after at least {threshold} attempts. Check credentials and provider access.")
            status = "degraded" if any(s["status"] != "ok" for s in summary["sources"].values()) or failures else "ok"
            store.db.execute("UPDATE runs SET finished_at=?,status=?,summary=? WHERE id=?", (now(), status, dump(summary), run_id))
        # Notify dead-man service only after database commit and completed pipeline.
        try:
            if failures or (summary["sources"] and all(s["status"] == "failed" for s in summary["sources"].values())):
                heartbeat("/fail")
            else:
                heartbeat()
        except Exception as exc:
            log.warning("Heartbeat completion failed: %s", exc)
        return summary
    except Exception as exc:
        log.exception("Run failed")
        try:
            heartbeat("/fail")
        except Exception:
            pass
        # Storage may be unable to dedupe/queue. The independent monitor owns
        # this incident transition, so repeated failed cycles cannot spam.
        raise
    finally:
        if store:
            store.close()

"""One collection transaction per source, independent link checks, durable outbox."""
import json
import logging
import time
from datetime import datetime, timedelta, timezone

from .classify import classify
from .delivery import configured_sender, deliver_pending, heartbeat, job_message
from .links import validate_job
from .locking import run_lock
from .storage import Store, dump, now, split_statuses, url_identity

log = logging.getLogger(__name__)


def later(seconds):
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat(timespec="seconds")



VALIDATION_CANDIDATE = ("(classification='include' OR (classification='ambiguous' AND "
                        "json_extract(evidence,'$.positive_opportunity_evidence')=1) OR "
                        "(classification='exclude' AND json_extract(payload,'$.evidence.description_kind')='validated_destination'))")


def validation_candidates(store, limit):
    """Round-robin new discoveries, imported backlog, and due rechecks.

    The persisted rotation also gives each group turns with a budget of one.
    Rechecks are oldest-first, so a repeatedly blocked URL cannot monopolize it.
    """
    due = VALIDATION_CANDIDATE + " AND (next_check IS NULL OR next_check<=?)"
    predicates = ("last_checked IS NULL AND baseline=0", "last_checked IS NULL AND baseline=1", "last_checked IS NOT NULL")
    groups = [store.rows("SELECT * FROM jobs WHERE " + due + " AND " + predicate +
                         " ORDER BY CASE classification WHEN 'include' THEN 0 WHEN 'ambiguous' THEN 1 ELSE 2 END,"
                         "COALESCE(last_checked,first_seen),id LIMIT ?", (now(), limit)) for predicate in predicates]
    state = store.db.execute("SELECT value FROM meta WHERE key='validation_rotation'").fetchone()
    rotation = int(state["value"]) % 3 if state else 0
    pending = []
    while len(pending) < limit and any(groups):
        for offset in range(3):
            group = (rotation + offset) % 3
            if groups[group]:
                row = groups[group].pop(0)
                row["_validation_group"] = group
                pending.append(row)
                rotation = (group + 1) % 3
                break
    return pending


def queue_notifications(store, config, run_id, source_succeeded):
    stamp = now()
    # These are policy decision timestamps, distinct from source discovery and
    # delivery receipts. A digest receipt never consumes the immediate key.
    store.db.execute("UPDATE jobs SET first_qualifying_at=COALESCE(first_qualifying_at,?),"
                     "notification_decided_at=COALESCE(notification_decided_at,?) WHERE classification='include'", (stamp, stamp))
    if config.get("initial_run", "silent") == "digest" and source_succeeded:
        store.queue("initial:digest", "digest", {"digest_type": "initial", "decided_at": stamp})
    for row in store.rows("SELECT * FROM jobs WHERE baseline=0 AND classification='include' "
                          "AND posting_status='open' AND application_status!='closed'"):
        store.queue("new:" + row["id"], "job", dict(job_message(row), decided_at=stamp))
    awaiting = store.rows("SELECT j.* FROM jobs j WHERE baseline=0 AND classification='include' "
                          "AND posting_status!='closed' AND (posting_status!='open' OR application_status='closed') "
                          "AND NOT EXISTS (SELECT 1 FROM digest_jobs d WHERE d.job_id=j.id) "
                          "AND NOT EXISTS (SELECT 1 FROM outbox o WHERE o.dedupe_key='new:'||j.id AND o.status='delivered') "
                          "ORDER BY first_seen,id")
    next_digest = store.db.execute("SELECT value FROM meta WHERE key='awaiting_digest_due'").fetchone()
    if awaiting and (not next_digest or next_digest["value"] <= stamp):
        key = "awaiting:" + str(run_id)
        store.queue(key, "digest", {"digest_type": "awaiting", "decided_at": stamp})
        outbox_id = store.db.execute("SELECT id FROM outbox WHERE dedupe_key=?", (key,)).fetchone()[0]
        store.db.executemany("INSERT INTO digest_jobs(outbox_id,job_id) VALUES(?,?)", ((outbox_id, row["id"]) for row in awaiting))
        store.db.execute("INSERT OR REPLACE INTO meta VALUES('awaiting_digest_due',?)",
                         (later(max(0, config.get("awaiting_digest_seconds", 900))),))



def stable_unverified_signature(result):
    """Identify repeated structural/access problems; never slow transient failures."""
    posting, application = split_statuses(result)
    checks = result.get("checks", [])
    selected = []
    if posting != "open":
        selected.extend(check for check in checks if check.get("kind") in ("description", "posting_api"))
    if application != "open":
        applications = [check for check in checks if check.get("kind") == "application"]
        selected.extend(applications[-1:])
    if not selected:
        return None
    families = {
        "robots_disallowed": "robots", "login_required": "login",
        "access_challenge": "challenge", "access_challenge_with_not_found_http_status": "challenge",
        "expected_job_identity_not_verified": "identity", "generic_page_not_job_specific": "identity",
        "redirected_to_different_job_identifier": "identity", "apply_link_points_to_different_job_identifier": "identity",
        "missing_meaningful_description_or_application": "description", "application_destination_not_verified": "application",
        "malformed_or_unsafe_url": "url", "unsafe_or_malformed_redirect": "url",
        "public_api_description_insufficient": "description", "public_api_employer_mismatch": "identity",
        "public_api_identifier_mismatch": "identity", "public_api_canonical_url_mismatch": "identity",
        "public_api_title_mismatch": "identity", "exact_job_absent_from_public_api": "api_absent",
        "public_api_unavailable:404": "api_absent", "public_api_unavailable:410": "api_absent",
    }
    signature = set()
    for check in selected:
        if check.get("status") == "open":
            continue
        evidence = check.get("evidence", [])
        http_status = check.get("http_status", 0) or 0
        if (http_status in (408, 425, 429) or http_status >= 500 or check.get("error") or
                any(value in evidence for value in ("host_cooldown_active", "robots_policy_unavailable_or_denied_http"))):
            return None
        reasons = {families[value] for value in evidence if value in families}
        if http_status in (401, 403, 451):
            reasons.add("blocked_http")
        if check.get("kind") == "application" and check.get("status") == "closed":
            reasons.add("application_closed")
        if not reasons:
            return None  # Unknown errors remain on the short retry schedule.
        destination = check.get("requested_url") or check.get("final_url") or ""
        signature.add((check.get("kind"), url_identity(destination) or destination, tuple(sorted(reasons))))
    return frozenset(signature) or None


def recheck_policy(result, config, previous=None):
    posting, application = split_statuses(result)
    if posting == application == "open":
        return config.get("link_recheck_seconds", 86400), "verified_open"
    if posting == "closed":
        return config.get("closed_recheck_seconds", 604800), "posting_closed"
    short = config.get("unverified_recheck_seconds", 3600)
    signature = stable_unverified_signature(result)
    if signature and previous and signature == stable_unverified_signature(previous):
        return max(short, config.get("blocked_recheck_seconds", 43200)), "persistent_access_or_content_problem"
    return short, "first_or_transient_unverified"


def pipeline_metrics(store):
    stamp = now()
    pending = store.rows("SELECT COUNT(*) count,MIN(COALESCE(next_check,first_seen)) oldest FROM jobs WHERE "
                         + VALIDATION_CANDIDATE + " AND (next_check IS NULL OR next_check<=?)", (stamp,))[0]
    def seconds_since(value):
        if not value:
            return None
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return max(0, (datetime.fromisoformat(stamp) - parsed).total_seconds())
    delays = store.rows("SELECT (julianday(first_qualifying_at)-julianday(first_seen))*86400 qualify_seconds,"
                        "(julianday(notification_decided_at)-julianday(first_seen))*86400 decision_seconds "
                        "FROM jobs WHERE baseline=0 AND notification_decided_at IS NOT NULL")
    def latency(column):
        values = sorted(max(0, row[column]) for row in delays if row[column] is not None)
        return {"count": len(values), "p50_seconds": round(values[len(values)//2], 3) if values else None,
                "max_seconds": round(max(values), 3) if values else None}
    return {"validation_due": pending["count"], "oldest_validation_due_seconds": seconds_since(pending["oldest"]),
            "posting_unverified": store.db.execute("SELECT COUNT(*) FROM jobs WHERE classification='include' AND posting_status='unverified'").fetchone()[0],
            "new_awaiting_digest": store.db.execute("SELECT COUNT(*) FROM jobs j WHERE baseline=0 AND classification='include' AND posting_status!='closed' "
                "AND (posting_status!='open' OR application_status='closed') AND NOT EXISTS(SELECT 1 FROM digest_jobs d WHERE d.job_id=j.id)").fetchone()[0],
            "notification_pending": store.db.execute("SELECT COUNT(*) FROM outbox WHERE status='pending'").fetchone()[0],
            "discovery_to_qualification": latency("qualify_seconds"), "discovery_to_notification_decision": latency("decision_seconds")}


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
    started = time.monotonic()
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
        collection_started = time.monotonic()
        for source in config.get("sources", []):
            if not source.get("enabled", True):
                continue
            key = source["id"]
            source_started = time.monotonic()
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
                summary["sources"][key] = {"count": len(jobs), "status": "ok", "seconds": round(time.monotonic()-source_started, 3)}
                log.info("source=%s status=ok count=%s", key, len(jobs))
            except Exception as exc:
                # HTTP source exceptions may carry public job URLs; secrets never enter adapters.
                detail = f"{type(exc).__name__}: {exc}"[:500]
                with store.transaction():
                    state = store.record_source(key, error=detail)
                    store.incident("source:" + key, state["failures"] >= threshold,
                                   f"{key}: failed {state['failures']} consecutive runs. {detail}")
                summary["sources"][key] = {"status": "failed", "error": detail, "seconds": round(time.monotonic()-source_started, 3)}
                log.warning("source=%s status=failed error=%s", key, detail)
        # Previously discovered jobs are rechecked even if collection is temporarily down.
        summary["timings_seconds"] = {"collection": round(time.monotonic()-collection_started, 3)}
        validation_started = time.monotonic()
        pending = validation_candidates(store, max(0, config.get("validation_budget", 100)))
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
            previous_check = store.db.execute("SELECT result FROM link_checks WHERE job_id=? ORDER BY id DESC LIMIT 1",
                                              (row["id"],)).fetchone() if row["last_checked"] else None
            delay, recheck_reason = recheck_policy(result, config, json.loads(previous_check["result"]) if previous_check else None)
            result = dict(result, recheck_seconds=delay, recheck_reason=recheck_reason)
            recheck_counts = summary.setdefault("recheck_classes", {})
            recheck_counts[recheck_reason] = recheck_counts.get(recheck_reason, 0) + 1
            with store.transaction():
                store.record_check(row["id"], result, later(delay))
                store.db.execute("INSERT OR REPLACE INTO meta VALUES('validation_rotation',?)", (str((row["_validation_group"]+1)%3),))
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
        summary["timings_seconds"]["validation"] = round(time.monotonic()-validation_started, 3)
        notification_started = time.monotonic()
        with store.transaction():
            rate_snapshot = getattr(client, "rate_limits", lambda: None)()
            if isinstance(rate_snapshot, dict):
                store.db.execute("INSERT OR REPLACE INTO meta VALUES('http_rate_limits',?)", (dump(rate_snapshot),))
            queue_notifications(store, config, run_id, any(s["status"] == "ok" for s in summary["sources"].values()))
        summary["delivery"] = deliver_pending(store, sender, limit=config.get("delivery_budget", 100))
        summary["timings_seconds"]["notification"] = round(time.monotonic()-notification_started, 3)
        if config.get("export_directory"):
            from .cli import export
            export_started = time.monotonic()
            summary["export"] = export(store, config["export_directory"], config)
            summary["timings_seconds"]["export"] = round(time.monotonic()-export_started, 3)
        summary["metrics"] = pipeline_metrics(store)
        summary["timings_seconds"]["total"] = round(time.monotonic()-started, 3)
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

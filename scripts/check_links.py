"""Resumable destination audit: python scripts/check_links.py --refresh-open.

Uses six sessions with shared per-host pacing and robots policy. This is audit
tooling, not the unattended runner. No notifications are sent.
"""
import argparse
from collections import Counter, defaultdict, deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
import re
from pathlib import Path
import sys
import threading
import time
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from internship_watch.classify import classify
from internship_watch.http import HttpClient
from internship_watch.links import validate_job, VALIDATOR_VERSION
from internship_watch.storage import url_identity


def identity_keys(job):
    """Match storage aliases; a shared unknown application is not job identity."""
    description_key = url_identity(job.get("description_url"))
    application_key = url_identity(job.get("application_url"))
    keys = [description_key] if description_key else []
    known_ats = lambda key: bool(key and key.startswith(("gh:", "lever:", "ashby:")))
    if application_key and application_key != description_key and known_ats(application_key) and not known_ats(description_key):
        keys.append(application_key)
    return keys


def bounded_workers(value):
    number = int(value)
    if not 1 <= number <= 12:
        raise argparse.ArgumentTypeError("workers must be between 1 and 12")
    return number


def same_expected_job(saved, job):
    normalized = lambda value: re.sub(r"\W+", "", str(value or "").casefold())
    return all(normalized(saved.get(field)) == normalized(job.get(field))
               for field in ("employer", "title"))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "data/source-audit/source-jobs.json")
    parser.add_argument("--config", type=Path, default=ROOT / "config.example.json")
    parser.add_argument("--output", type=Path, default=ROOT / "data/link-audit/checks.jsonl")
    parser.add_argument("--workers", type=bounded_workers, default=6)
    parser.add_argument("--refresh-open", action="store_true")
    parser.add_argument("--refresh-closed", action="store_true", help="Recheck previous closure evidence")
    parser.add_argument("--summary-only", action="store_true")
    parser.add_argument("--report", type=Path, default=ROOT / "data/link-audit/report.json")
    args = parser.parse_args(argv)
    config = json.loads(Path(args.config).read_text(encoding="utf-8-sig"))
    filters = dict(config.get("filters", {}))
    jobs = json.loads(Path(args.input).read_text(encoding="utf-8-sig"))
    output = Path(args.output)
    output.parent.mkdir(parents=True,exist_ok=True)
    args.report.parent.mkdir(parents=True,exist_ok=True)
    latest, enriched = {}, {}
    if output.exists():
        for line in output.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
                latest[row["key"]] = row
                if row["result"].get("description"):
                    for source_id in row["source_ids"]:
                        enriched[source_id] = row
            except (ValueError,KeyError):
                raise SystemExit("Invalid checkpoint line; preserve file and repair before resuming")
    groups, identities, decisions, candidate_decisions = [], {}, Counter(), Counter()
    classifications = []
    for job in jobs:
        previous_description = enriched.get(job["source_id"])
        if (not job.get("description") or job.get("evidence",{}).get("description_kind") == "employer_search_summary") and previous_description and same_expected_job(previous_description, job):
            job = dict(job,description=previous_description["result"]["description"])
        classification = classify(job, filters)
        decisions[classification["decision"]] += 1
        classifications.append({"source_id":job["source_id"], "source":job.get("source"),
                                "employer":job["employer"],"title":job["title"],
                                "location":job.get("location"),"classification":classification})
        if classification["decision"] == "exclude" or not classification["positive_opportunity_evidence"]:
            continue
        candidate_decisions[classification["decision"]] += 1
        urls = identity_keys(job)
        source_identity = "source:" + str(job.get("source", "")) + ":" + job["source_id"]
        found = {identities[key] for key in [source_identity] + urls if key in identities}
        if len(found) > 1:
            # A record bridging two known positions is conflicting evidence.
            # Mirror storage: retain only this source identity and do not unite
            # the already distinct groups or overwrite their URL aliases.
            urls = []
            matched = identities.get(source_identity)
        else:
            matched = next(iter(found), None)
        if matched is None:
            matched = len(groups)
            key = urls[0] if urls else source_identity
            groups.append({"key":hashlib.sha256(key.encode()).hexdigest()[:24],"job":job,
                           "classification":classification,"source_ids":[]})
        group = groups[matched]
        group["source_ids"].append(job["source_id"])
        if len(job.get("description") or "") > len(group["job"].get("description") or ""):
            group["job"] = job
            group["classification"] = classification
        for url in [source_identity] + urls:
            identities[url] = matched
    (output.parent / "classifications.json").write_text(json.dumps(classifications,ensure_ascii=False),encoding="utf-8")
    audit = {"at":datetime.now(timezone.utc).isoformat(),"filters":filters,
             "discovered":len(jobs),"decisions":dict(decisions),
             "candidate_decisions":dict(candidate_decisions),"unique_candidates":len(groups)}
    (output.parent / "classification-summary.json").write_text(json.dumps(audit,indent=2),encoding="utf-8")
    completed = set(latest)
    statuses = Counter(row["result"]["status"] for row in latest.values())
    grouped = defaultdict(deque)
    for group in groups:
        previous = latest.get(group["key"],{})
        needs_refresh = (args.refresh_open and previous.get("result",{}).get("status") == "open"
                         and previous["result"].get("validator_version",1) < VALIDATOR_VERSION)
        needs_refresh = needs_refresh or (args.refresh_closed and previous.get("result",{}).get("status") == "closed")
        needs_refresh = needs_refresh or bool(previous and not same_expected_job(previous, group["job"]))
        if group["key"] not in completed or needs_refresh:
            host = urlsplit(group["job"].get("description_url") or "").netloc
            grouped[host].append(group)
    queue = []
    while grouped:
        for host in list(grouped):
            queue.append(grouped[host].popleft())
            if not grouped[host]:
                del grouped[host]
    shared_lock, host_locks, last_request, intervals, robots = threading.Lock(), {}, {}, {}, {}
    cooldowns, failure_counts = {}, {}
    rate_state_path = output.with_suffix(".rate-limits.json")
    if rate_state_path.exists():
        state = json.loads(rate_state_path.read_text(encoding="utf-8"))
        cooldowns.update({host:until for host,until in state.get("host_cooldowns",{}).items() if until > time.time()})
        failure_counts.update(state.get("host_failure_counts",{}))

    def save_rate_state():
        with shared_lock:
            state = {"host_cooldowns":{host:until for host,until in cooldowns.items() if until > time.time()},
                     "host_failure_counts":dict(failure_counts)}
        rate_state_path.write_text(json.dumps(state,indent=2),encoding="utf-8")
    local = threading.local()
    http = dict(config.get("http", {}))
    # Respect the operator's HTTP settings; restrictions are never bypassed.

    class AuditClient(HttpClient):
        def _pace(self,url):
            host = self._host(url)
            with shared_lock:
                lock = host_locks.setdefault(host,threading.Lock())
            with lock:
                delay = max(self.min_interval,intervals.get(host,0))
                wait = last_request.get(host,0) + delay - time.monotonic()
                if wait > 0:
                    self._sleep(wait)
                last_request[host] = time.monotonic()

    def check(group):
        if not hasattr(local,"client"):
            local.client = AuditClient(**http)
            local.client._robots = robots
            local.client._host_intervals = intervals
            local.client._last_request = last_request
            local.client._lock = shared_lock
            local.client.host_cooldowns = cooldowns
            local.client.host_failure_counts = failure_counts
        job = group["job"]
        try:
            result = validate_job(job,local.client)
        except Exception as exc:
            result = {"status":"unverified","checked_at":datetime.now(timezone.utc).isoformat(),
                      "validator_version":VALIDATOR_VERSION,"checks":[{"evidence":["validation_exception:"+type(exc).__name__]}]}
        if result.get("description") and (not job.get("description") or job.get("evidence",{}).get("description_kind") == "employer_search_summary"):
            job = dict(job,description=result["description"])
        return {"key":group["key"],"source_ids":group["source_ids"],
                "employer":job["employer"],"title":job["title"],
                "classification":classify(job,filters),"result":result}

    print(json.dumps(dict(audit,resuming=len(completed),remaining=len(queue))),flush=True)
    started = time.monotonic()
    if args.summary_only:
        queue = []
    with output.open("a",encoding="utf-8") as stream, ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = [executor.submit(check,group) for group in queue]
        for number,future in enumerate(as_completed(futures),1):
            row = future.result()
            stream.write(json.dumps(row,ensure_ascii=False)+"\n")
            stream.flush()
            previous = latest.get(row["key"])
            if previous:
                statuses[previous["result"]["status"]] -= 1
            latest[row["key"]] = row
            statuses[row["result"]["status"]] += 1
            if number % 30 == 0 or number == len(queue):
                save_rate_state()
                print(json.dumps({"completed_this_run":number,"remaining":len(queue)-number,"seconds":round(time.monotonic()-started),"statuses":dict(statuses)}),flush=True)
    print("Live audit complete: "+str(output),flush=True)
    save_rate_state()
    report_rows, matrix, per_source = [], Counter(), defaultdict(Counter)
    source_names = {job["source_id"]:job.get("source",job["source_id"].split("-",1)[0]) for job in jobs}
    for group in groups:
        previous = latest.get(group["key"])
        job = group["job"]
        if previous and same_expected_job(previous, job) and previous["result"].get("description") and (not job.get("description") or job.get("evidence",{}).get("description_kind") == "employer_search_summary"):
            job = dict(job,description=previous["result"]["description"])
        classification = classify(job,filters)
        result = previous["result"] if previous else {"status":"never_checked","checks":[]}
        status = result["status"]
        if previous and not same_expected_job(previous, job):
            status = "requires_current_identity"
        if status == "open" and result.get("validator_version",1) < VALIDATOR_VERSION:
            status = "requires_current_validator"
        decision = classification["decision"]
        matrix[decision+"_"+status] += 1
        for source in {source_names.get(s,"unknown") for s in group["source_ids"]}:
            per_source[source][decision+"_"+status] += 1
        report_rows.append({"key":group["key"],"source_ids":group["source_ids"],
                           "employer":job["employer"],"title":job["title"],
                           "description_url":job.get("description_url"),"application_url":job.get("application_url"),
                           "classification":classification,"report_status":status,"result":result})
    current_keys = {group["key"] for group in groups}
    excluded_checked = [row for key,row in latest.items() if key not in current_keys]
    included_open = matrix["include_open"]
    unresolved = sum(n for key,n in matrix.items() if key.split("_",1)[0] != "exclude" and key.split("_",1)[1] in {"unverified","never_checked","requires_current_validator","requires_current_identity"})
    summary = dict(audit, matrix=dict(matrix), included_open=included_open,
                   unresolved_link_checks=unresolved,
                   classification_needs_review=sum(n for key,n in matrix.items() if key.startswith("ambiguous_")),
                   no_longer_candidate_checks=len(excluded_checked),
                   per_source={key:dict(value) for key,value in per_source.items()},
                   note="Counts are unique exact-URL/ATS identities. Open means description and application form verified by current validator. Unverified includes access restrictions and missing application evidence; these are not closed. Original source counts include duplicates. This is a live snapshot, not a deployment or market-completeness claim.")
    report = {"summary":summary,"rows":report_rows,
              "previously_checked_no_longer_candidates":[{"key":r["key"],"source_ids":r["source_ids"],"employer":r["employer"],"title":r["title"]} for r in excluded_checked]}
    Path(args.report).write_text(json.dumps(report,ensure_ascii=False),encoding="utf-8")
    Path(args.report).with_suffix(".summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"report":str(args.report),"included_open":included_open,"unresolved_link_checks":unresolved,"matrix":dict(matrix)}),flush=True)


if __name__ == "__main__":
    main()

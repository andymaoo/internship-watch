"""Acknowledged ntfy delivery. Secrets are environment variables, never job data."""
import json
import os
import hashlib
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit

import requests

from .storage import now


class NotConfigured(RuntimeError):
    pass


class RetryLater(RuntimeError):
    def __init__(self, seconds):
        self.seconds = max(1, float(seconds))
        super().__init__(f"Provider rate limit; retry after {self.seconds:g} seconds")


def retry_after(response):
    value = response.headers.get("Retry-After", "60")
    try:
        return max(1, float(value))
    except (TypeError, ValueError):
        try:
            return max(1, (parsedate_to_datetime(value) - datetime.now(timezone.utc)).total_seconds())
        except (TypeError, ValueError):
            return 60


class Discord:
    def __init__(self, timeout=15):
        self.timeout = timeout
        self.last_send = 0

    def send(self, payload, operational=False):
        url = os.environ.get("OPS_DISCORD_WEBHOOK_URL" if operational else "DISCORD_WEBHOOK_URL", "")
        if operational and not url:
            url = os.environ.get("DISCORD_WEBHOOK_URL", "")
        if not url:
            raise NotConfigured("Discord webhook is not configured; delivery stays queued")
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.hostname not in ("discord.com", "discordapp.com") or not parsed.path.startswith("/api/webhooks/"):
            raise ValueError("Expected an HTTPS Discord incoming webhook URL")
        time.sleep(max(0, self.last_send + 0.5 - time.monotonic()))
        self.last_send = time.monotonic()
        body = {"content": (str(payload.get("title", "Internship update")) + "\n" + str(payload.get("body", "")))[:1950],
                "allowed_mentions": {"parse": []}}
        try:
            response = requests.post(url, params={"wait": "true"}, json=body, timeout=self.timeout, allow_redirects=False)
            if response.status_code == 429:
                try:
                    delay = response.json().get("retry_after", 60)
                except ValueError:
                    delay = 60
                raise RetryLater(delay)
            response.raise_for_status()
            if not 200 <= response.status_code < 300:
                raise RuntimeError(f"Discord HTTP {response.status_code}")
            ack = response.json()
            if not ack.get("id"):
                raise RuntimeError("Discord did not acknowledge a saved message")
            return ack["id"]
        except requests.RequestException as exc:
            raise RuntimeError(f"Discord transport failed ({type(exc).__name__})") from None


def configured_sender(config):
    channel = config.get("notifications", {}).get("channel", "discord")
    if channel == "discord":
        return Discord()
    if channel == "ntfy":
        return Ntfy()
    raise ValueError("notifications.channel must be discord or ntfy")


class Ntfy:
    def __init__(self, timeout=15):
        self.timeout = timeout

    def send(self, payload, operational=False):
        url = os.environ.get("OPS_NTFY_URL" if operational else "NTFY_URL", "")
        if operational and not url:
            url = os.environ.get("NTFY_URL", "")
        if not url:
            raise NotConfigured("Notification URL is not configured; delivery stays queued")
        parsed = urlsplit(url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("NTFY_URL must be an HTTPS topic URL without credentials in the URL")
        token = os.environ.get("OPS_NTFY_TOKEN" if operational else "NTFY_TOKEN", "")
        if operational and not token:
            token = os.environ.get("NTFY_TOKEN", "")
        headers = {"Content-Type": "application/json"}
        if payload.get("_delivery_key"):
            headers["X-Sequence-ID"] = hashlib.sha256(payload["_delivery_key"].encode()).hexdigest()[:32]
        if token:
            headers["Authorization"] = "Bearer " + token
        # JSON avoids Unicode-in-header errors and newline injection from external titles.
        body = {"topic": parsed.path.strip("/"), "title": str(payload.get("title", "Internship update"))[:200],
                "message": str(payload.get("body", ""))[:3500], "priority": 4 if operational else 3,
                "tags": ["warning" if operational else "briefcase"]}
        if payload.get("url"):
            body["click"] = payload["url"]
        base = f"{parsed.scheme}://{parsed.netloc}"
        try:
            response = requests.post(base, json=body, headers=headers, timeout=self.timeout, allow_redirects=False)
            if response.status_code == 429:
                raise RetryLater(retry_after(response))
            response.raise_for_status()
            if not 200 <= response.status_code < 300:
                raise RuntimeError(f"Notification HTTP {response.status_code}")
            ack = response.json()
            if not ack.get("id") or ack.get("event") != "message":
                raise RuntimeError("Notification service did not acknowledge a message")
            return ack["id"]
        except requests.RequestException as exc:
            # requests exceptions often include secret topic URLs. Do not persist them.
            raise RuntimeError(f"Notification transport failed ({type(exc).__name__})") from None



def job_message(row):
    """Posting evidence is independent from application access."""
    row = dict(row)
    application = row.get("application_status", "unverified")
    url = row.get("final_application_url") or row.get("application_url") or row["original_url"]
    label = ("Posting verified; application verified." if application == "open" else
             "Posting verified; application access UNVERIFIED. Check the application destination manually.")
    return {"title": "New internship", "body": f"{row['employer']} — {row['title']}\n{row['location']}\n{label}\n{url}", "url": url}


def digest_message(store, row):
    """Refresh queued digests so a delayed delivery never recommends excluded jobs."""
    payload = json.loads(row["payload"])
    kind = payload.get("digest_type")
    if kind not in ("initial", "awaiting"):
        return payload  # Operational/testing digests retain their original body.
    if kind == "initial":
        jobs = store.rows("SELECT * FROM jobs WHERE baseline=1 AND classification='include' ORDER BY employer,title")
        posting_open = sum(j["posting_status"] == "open" for j in jobs)
        closed = sum(j["posting_status"] == "closed" for j in jobs)
        app_unverified = sum(j["posting_status"] == "open" and j["application_status"] == "unverified" for j in jobs)
        lines = [f"Initial backlog: {len(jobs)} matching records. {posting_open} postings verified open; "
                 f"{closed} postings closed; {len(jobs)-posting_open-closed} postings unverified. "
                 f"{app_unverified} open postings have unverified application access."]
        category_labels = {"software_engineering": "Software engineering", "data_analysis": "Data analysis",
                           "data_engineering": "Data engineering", "data_science": "Data science",
                           "ml_ai": "ML/AI", "quantitative": "Quant", "product_management": "Product management"}
        categories = Counter(j["category"] or "other" for j in jobs)
        if categories:
            lines.append("Categories: " + "; ".join(f"{category_labels.get(category, category)} {count}"
                         for category, count in sorted(categories.items())))
        shown = sorted((j for j in jobs if j["posting_status"] != "closed"),
                       key=lambda j: (j["posting_status"] != "open", j["application_status"] != "open",
                                      j["application_status"] == "closed", j["employer"], j["title"]))
        title = "Initial internship backlog — one grouped report"
    else:
        jobs = store.rows("SELECT j.* FROM digest_jobs d JOIN jobs j ON j.id=d.job_id WHERE d.outbox_id=? "
                          "AND j.baseline=0 AND j.classification='include' AND j.posting_status!='closed' "
                          "AND (j.posting_status!='open' OR j.application_status='closed') "
                          "AND NOT EXISTS (SELECT 1 FROM outbox o WHERE o.dedupe_key='new:'||j.id AND o.status='delivered') "
                          "ORDER BY j.first_seen,j.employer,j.title", (row["id"],))
        keep = {j["id"] for j in jobs}
        with store.transaction():
            for member in store.rows("SELECT job_id FROM digest_jobs WHERE outbox_id=?", (row["id"],)):
                if member["job_id"] not in keep:
                    store.db.execute("DELETE FROM digest_jobs WHERE outbox_id=? AND job_id=?", (row["id"], member["job_id"]))
        if not jobs:
            return None
        lines = [f"{len(jobs)} newly discovered matches await verification. These are NOT confirmed available internships. "
                 "Posting access may be blocked, a check may be pending, or the application destination may be closed."]
        shown = jobs
        title = "Unverified internship digest — needs review"
    # One grouped message, with the complete membership preserved in SQLite.
    # Bound text before delivery rather than relying on provider truncation.
    listed = 0
    for job in shown:
        link = job["final_url"] or job["original_url"] or job["application_url"]
        line = (f"{job['employer']}: {job['title']}\n"
                f"Posting: {job['posting_status']}; application: {job['application_status']}\n{link}")
        if len("\n\n".join(lines)) + len(line) > 1550:
            break
        lines.append(line)
        listed += 1
    if len(shown) > listed:
        lines.append(f"{len(shown)-listed} more matches are included in this grouped report.")
    lines.append("Browse the private jobs export for the full list and link evidence. A later verified new posting can still send its own alert.")
    return dict(payload, title=title, body="\n\n".join(lines))


def deliver_pending(store, sender, limit=100, retry_base_seconds=60):
    result = {"delivered": 0, "failed": 0, "unconfigured": 0}
    cooldown = store.db.execute("SELECT value FROM meta WHERE key='delivery_cooldown'").fetchone()
    if cooldown and cooldown["value"] > now():
        result["cooldown_until"] = cooldown["value"]
        return result
    with store.transaction():
        store.db.execute("UPDATE outbox SET status='cancelled',last_error='Posting closed or no longer eligible' "
                         "WHERE status='pending' AND kind='job' AND dedupe_key LIKE 'new:%' AND EXISTS "
                         "(SELECT 1 FROM jobs j WHERE j.id=substr(outbox.dedupe_key,5) "
                         "AND (j.classification='exclude' OR j.posting_status='closed'))")
    due = store.rows("SELECT o.* FROM outbox o LEFT JOIN jobs j ON j.id=substr(o.dedupe_key,5) "
                     "WHERE o.status='pending' AND o.next_attempt<=? AND (o.kind!='job' OR "
                     "(j.classification='include' AND j.posting_status='open' AND j.application_status!='closed')) ORDER BY "
                     "CASE WHEN o.kind='incident' THEN 0 ELSE 1 END,o.id LIMIT ?", (now(), limit))
    for row in due:
        if row["kind"] == "job" and row["dedupe_key"].startswith("new:"):
            job = store.db.execute("SELECT * FROM jobs WHERE id=?", (row["dedupe_key"][4:],)).fetchone()
            if not job or job["classification"] == "exclude" or job["posting_status"] == "closed":
                with store.transaction():
                    store.db.execute("UPDATE outbox SET status='cancelled',last_error='Posting closed or no longer eligible' WHERE id=?", (row["id"],))
                continue
            if job["classification"] != "include" or job["posting_status"] != "open" or job["application_status"] == "closed":
                continue
        try:
            payload = json.loads(row["payload"])
            if row["kind"] == "job" and row["dedupe_key"].startswith("new:"):
                payload = dict(payload, **job_message(job))
            elif row["kind"] == "digest":
                payload = digest_message(store, row)
                if payload is None:
                    with store.transaction():
                        store.db.execute("UPDATE outbox SET status='cancelled',last_error='No remaining unverified eligible members' WHERE id=?", (row["id"],))
                    continue
            payload["_delivery_key"] = row["dedupe_key"]
            receipt = sender.send(payload, operational=row["kind"] == "incident")
        except Exception as exc:
            attempts = row["attempts"] + 1
            delay = min(86400, retry_base_seconds * (2 ** min(attempts - 1, 10)))
            if isinstance(exc, RetryLater):
                delay = max(delay, exc.seconds)
            due_at = (datetime.now(timezone.utc) + timedelta(seconds=delay)).isoformat(timespec="seconds")
            with store.transaction():
                store.db.execute("UPDATE outbox SET attempts=?,next_attempt=?,last_error=? WHERE id=?",
                                 (attempts, due_at, str(exc)[:300], row["id"]))
                if isinstance(exc, RetryLater):
                    store.db.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('delivery_cooldown',?)", (due_at,))
            result["unconfigured" if isinstance(exc, NotConfigured) else "failed"] += 1
            if isinstance(exc, RetryLater):
                break
        else:
            with store.transaction():
                store.db.execute("UPDATE outbox SET status='delivered',attempts=attempts+1,delivered_at=?,last_error=NULL,payload=?,receipt_id=? WHERE id=?",
                                 (now(), json.dumps(payload, ensure_ascii=False), str(receipt) if receipt is not None else None, row["id"]))
            result["delivered"] += 1
    return result


def heartbeat(suffix="", env_name="HEALTHCHECKS_PING_URL"):
    url = os.environ.get(env_name, "")
    if not url:
        return False
    if urlsplit(url).scheme != "https":
        raise ValueError("Heartbeat URL must use HTTPS")
    try:
        response = requests.get(url.rstrip("/") + suffix, timeout=10, allow_redirects=False)
        response.raise_for_status()
        if not 200 <= response.status_code < 300:
            raise RuntimeError("Heartbeat was not acknowledged")
        return True
    except requests.RequestException as exc:
        raise RuntimeError(f"Heartbeat transport failed ({type(exc).__name__})") from None

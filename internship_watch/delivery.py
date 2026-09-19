"""Acknowledged ntfy delivery. Secrets are environment variables, never job data."""
import json
import os
import hashlib
import time
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


def deliver_pending(store, sender, limit=100, retry_base_seconds=60):
    result = {"delivered": 0, "failed": 0, "unconfigured": 0}
    cooldown = store.db.execute("SELECT value FROM meta WHERE key='delivery_cooldown'").fetchone()
    if cooldown and cooldown["value"] > now():
        result["cooldown_until"] = cooldown["value"]
        return result
    with store.transaction():
        store.db.execute("UPDATE outbox SET status='cancelled',last_error='Job closed or no longer eligible' "
                         "WHERE status='pending' AND kind='job' AND dedupe_key LIKE 'new:%' AND EXISTS "
                         "(SELECT 1 FROM jobs j WHERE j.id=substr(outbox.dedupe_key,5) AND (j.classification='exclude' OR j.status='closed'))")
    due = store.rows("SELECT o.* FROM outbox o LEFT JOIN jobs j ON j.id=substr(o.dedupe_key,5) "
                     "WHERE o.status='pending' AND o.next_attempt<=? AND (o.kind!='job' OR "
                     "(j.classification='include' AND j.status='open')) ORDER BY "
                     "CASE WHEN o.kind='incident' THEN 0 ELSE 1 END,o.id LIMIT ?", (now(), limit))
    for row in due:
        if row["kind"] == "job" and row["dedupe_key"].startswith("new:"):
            job_id = row["dedupe_key"][4:]
            job = store.db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            if not job or job["classification"] == "exclude" or job["status"] == "closed":
                with store.transaction():
                    store.db.execute("UPDATE outbox SET status='cancelled',last_error='Job closed or no longer eligible' WHERE id=?", (row["id"],))
                continue
            if job["classification"] != "include" or job["status"] != "open":
                continue  # Hold until its destination and eligibility are verified again.
        try:
            payload = json.loads(row["payload"])
            if row["kind"] == "job" and row["dedupe_key"].startswith("new:"):
                payload["url"] = job["final_application_url"] or job["application_url"]
                payload["body"] = f"{job['employer']} — {job['title']}\n{job['location']}\n{payload['url']}"
            payload["_delivery_key"] = row["dedupe_key"]
            sender.send(payload, operational=row["kind"] == "incident")
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
                break  # Respect a provider-wide cooldown, not only this message.
        else:
            with store.transaction():
                store.db.execute("UPDATE outbox SET status='delivered',attempts=attempts+1,delivered_at=?,last_error=NULL WHERE id=?",
                                 (now(), row["id"]))
            result["delivered"] += 1
    return result


def heartbeat(suffix=""):
    url = os.environ.get("HEALTHCHECKS_PING_URL", "")
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

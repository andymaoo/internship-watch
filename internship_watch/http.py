"""Bounded, paced HTTP for public sources and link verification.

No authentication or access-control workarounds. Webpage callers must set
respect_robots=True. API callers use only the documented public endpoints.
"""
from __future__ import annotations

import ipaddress
import math
import socket
import threading
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin, urlsplit

import requests
from protego import Protego


class AccessRestricted(requests.RequestException):
    """A source restriction or unavailable robots policy prevents checking."""


def allow_url(url: str, *, resolve_dns: bool = True) -> str:
    """Reject credentials, local/private destinations and unsupported schemes."""
    if not isinstance(url, str) or any(ord(c) <= 32 or ord(c) == 127 for c in url) or "\\" in url:
        raise ValueError("Malformed URL")
    parsed = urlsplit(url)
    if parsed.scheme not in {"https", "http"} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Expected a public HTTP(S) URL without credentials")
    if parsed.port not in {None, 80, 443}:
        raise ValueError("Nonstandard URL port")
    host = parsed.hostname.rstrip(".").lower()
    if host in {"localhost", "localhost.localdomain"} or host.endswith((".local", ".internal", ".localhost")):
        raise ValueError("Private destination rejected")
    try:
        addresses = [ipaddress.ip_address(host)]
    except ValueError:
        if not resolve_dns:
            return url
        try:
            addresses = [ipaddress.ip_address(row[4][0]) for row in socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)]
        except OSError as exc:
            raise requests.ConnectionError(f"DNS lookup failed for {host}") from exc
    if not addresses or any(not address.is_global for address in addresses):
        raise ValueError("Private or nonpublic destination rejected")
    return url


class HttpClient:
    def __init__(self, timeout: float = 20, connect_timeout: float = 10,
                 retries: int = 2, min_interval: float = 1.0,
                 backoff: float = 1.0, max_retry_after: float = 60,
                 max_redirects: int = 8, user_agent: str = "InternshipWatch/1.0 (+personal internship discovery)",
                 resolve_dns: bool = True, session=None, deadline: float | None = None,
                 forbidden_threshold: int = 3, forbidden_cooldown: float = 300,
                 blocked_hosts: dict[str, str] | None = None, **kwargs):
        if kwargs:
            raise ValueError(f"Unknown HTTP settings: {', '.join(sorted(kwargs))}")
        if timeout <= 0 or connect_timeout <= 0 or not 0 <= retries <= 5 or min_interval < 0 or max_redirects < 0:
            raise ValueError("Invalid bounded HTTP configuration")
        if forbidden_threshold < 0 or forbidden_cooldown < 0:
            raise ValueError("Invalid HTTP access-failure circuit configuration")
        if blocked_hosts is not None and not isinstance(blocked_hosts, dict):
            raise ValueError("blocked_hosts must map exact hostnames to policy reasons")
        self.blocked_hosts = {}
        for host, reason in (blocked_hosts or {}).items():
            if (not isinstance(host, str) or not host or
                    any(character not in "abcdefghijklmnopqrstuvwxyz0123456789.-" for character in host.lower()) or
                    not host.rstrip(".") or not isinstance(reason, str) or not reason.strip()):
                raise ValueError("blocked_hosts must map exact hostnames to policy reasons")
            self.blocked_hosts[host.rstrip(".").lower()] = reason.strip()
        self.timeout = (connect_timeout, timeout)
        self.retries, self.min_interval = retries, min_interval
        self.backoff, self.max_retry_after = backoff, max_retry_after
        self.max_redirects, self.resolve_dns = max_redirects, resolve_dns
        self.user_agent = user_agent
        self.deadline = deadline
        self.forbidden_threshold, self.forbidden_cooldown = forbidden_threshold, forbidden_cooldown
        # Wall-clock epochs can be persisted across processes/restarts. Audit
        # worker clients may share these dictionaries and _lock explicitly.
        self.host_cooldowns: dict[str, float] = {}
        self.host_failure_counts: dict[str, int] = {}
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": user_agent})
        self._last_request = {}
        self._host_intervals = {}
        self._robots = {}
        self._lock = threading.Lock()

    def close(self):
        self.session.close()

    def fork(self):
        """Independent HTTP session with shared pacing, policy and cooldown state."""
        child = HttpClient(timeout=self.timeout[1], connect_timeout=self.timeout[0], retries=self.retries,
            min_interval=self.min_interval, backoff=self.backoff, max_retry_after=self.max_retry_after,
            max_redirects=self.max_redirects, user_agent=self.user_agent, resolve_dns=self.resolve_dns,
            forbidden_threshold=self.forbidden_threshold, forbidden_cooldown=self.forbidden_cooldown,
            blocked_hosts=self.blocked_hosts)
        for name in ('_lock', '_last_request', '_host_intervals', '_robots', 'host_cooldowns', 'host_failure_counts'):
            setattr(child, name, getattr(self, name))
        return child

    @staticmethod
    def _host(url):
        return (urlsplit(url).hostname or "").rstrip(".").lower()

    def rate_limits(self):
        """JSON-safe snapshot; the runner owns durable storage of this value."""
        with self._lock:
            return {"host_cooldowns": {host: until for host, until in self.host_cooldowns.items() if until > time.time()},
                    "host_failure_counts": {host: count for host, count in self.host_failure_counts.items() if count > 0}}

    def load_rate_limits(self, snapshot):
        """Restore/merge a persisted snapshot without replacing shared maps."""
        if not isinstance(snapshot, dict):
            return
        cooldowns = snapshot.get("host_cooldowns", {})
        failures = snapshot.get("host_failure_counts", {})
        with self._lock:
            if isinstance(cooldowns, dict):
                for host, until in cooldowns.items():
                    if isinstance(host, str) and isinstance(until, (int, float)) and math.isfinite(until) and until > time.time():
                        self.host_cooldowns[host] = max(until, self.host_cooldowns.get(host, 0))
            if isinstance(failures, dict):
                for host, count in failures.items():
                    if isinstance(host, str) and isinstance(count, int) and count > 0:
                        self.host_failure_counts[host] = max(count, self.host_failure_counts.get(host, 0))

    def _check_cooldown_locked(self, host):
        until = self.host_cooldowns.get(host, 0)
        if until > time.time():
            raise AccessRestricted(f"Host {host} is cooling down until Unix time {until:.3f}; check deferred")
        if until:
            self.host_cooldowns.pop(host, None)

    def _check_cooldown(self, url):
        with self._lock:
            self._check_cooldown_locked(self._host(url))

    def _check_source_policy(self, url):
        host = self._host(url)
        reason = self.blocked_hosts.get(host)
        if reason:
            error = AccessRestricted(f"Automated access to {host} is disabled by source policy: {reason}")
            error.source_policy_reason = reason
            error.restricted_host = host
            raise error

    @staticmethod
    def _retry_after_seconds(response, default):
        value = response.headers.get("Retry-After")
        if not value:
            return default
        try:
            delay = float(value)
        except ValueError:
            try:
                parsed = parsedate_to_datetime(value)
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                delay = parsed.timestamp() - time.time()
            except (ValueError, TypeError, OverflowError):
                return default
        return max(0, delay) if math.isfinite(delay) else default

    def _record_response(self, url, response):
        host = self._host(url)
        with self._lock:
            if response.status_code == 403:
                count = self.host_failure_counts.get(host, 0) + 1
                self.host_failure_counts[host] = count
                if self.forbidden_threshold and count >= self.forbidden_threshold:
                    self.host_cooldowns[host] = max(self.host_cooldowns.get(host, 0), time.time() + self.forbidden_cooldown)
                    self.host_failure_counts[host] = 0
            else:
                # The breaker requires consecutive forbidden responses; a 404
                # for one posting must not make an entire public board fail.
                self.host_failure_counts.pop(host, None)
            if response.status_code == 429:
                # Preserve the full server delay even above max_retry_after.
                # Do not immediately retry this or another URL on the host.
                delay = self._retry_after_seconds(response, 60)
                self.host_cooldowns[host] = max(self.host_cooldowns.get(host, 0), time.time() + delay)

    def _remaining(self):
        if self.deadline is None:
            return None
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise requests.Timeout("HTTP work deadline exhausted")
        return remaining

    def _sleep(self, delay):
        remaining = self._remaining()
        if remaining is not None and delay >= remaining:
            raise requests.Timeout("HTTP work deadline cannot accommodate pacing or retry delay")
        if delay > 0:
            time.sleep(delay)
        self._remaining()

    def _bounded_timeout(self, configured):
        remaining = self._remaining()
        if remaining is None:
            return configured
        # Divide the remainder across connection and read phases; requests has
        # no native absolute wall-clock deadline. Check again after the call.
        if isinstance(configured, (int, float)):
            configured = (configured, configured)
        return tuple(min(value or remaining / 2, remaining / 2) for value in configured)

    def _pace(self, url):
        host = self._host(url)
        with self._lock:
            self._check_cooldown_locked(host)
            interval = max(self.min_interval, self._host_intervals.get(host, 0))
            wait = self._last_request.get(host, 0) + interval - time.monotonic()
            if wait > 0:
                self._sleep(wait)
            self._check_cooldown_locked(host)
            self._last_request[host] = time.monotonic()

    def robots_allowed(self, url: str) -> bool:
        self._check_source_policy(url)
        self._check_cooldown(url)
        parsed = urlsplit(allow_url(url, resolve_dns=self.resolve_dns))
        origin = f"{parsed.scheme}://{parsed.netloc}"
        cached = self._robots.get(origin)
        if cached and time.monotonic() - cached[0] < 3600:
            policy = cached[1]
        else:
            try:
                response = self.get(origin + "/robots.txt", respect_robots=False, raise_for_status=False)
                if response.status_code in {404, 410}:
                    policy = True
                elif response.status_code == 200 and "<html" not in response.text[:500].lower():
                    # RFC 9309 path/query matching, wildcards, longest match and
                    # merged agent groups. Python 3.12's RobotFileParser turns
                    # a literal '/?' rule into '/', falsely denying every URL.
                    policy = Protego.parse(response.text)
                    delay = policy.crawl_delay(self.user_agent) or policy.crawl_delay("*") or 0
                    rate = policy.request_rate(self.user_agent) or policy.request_rate("*")
                    if rate and rate.requests:
                        delay = max(delay, rate.seconds / rate.requests)
                    self._host_intervals[self._host(url)] = delay
                else:
                    policy = False
            except (requests.RequestException, ValueError):
                policy = False
            self._robots[origin] = (time.monotonic(), policy)
        return policy if isinstance(policy, bool) else policy.can_fetch(url, self.user_agent)

    def _retry_delay(self, response, attempt):
        value = response.headers.get("Retry-After") if response is not None else None
        if value:
            try:
                delay = float(value)
            except ValueError:
                try:
                    delay = (parsedate_to_datetime(value) - datetime.now(timezone.utc)).total_seconds()
                except (ValueError, TypeError):
                    delay = self.backoff * 2 ** attempt
            # A long server pause should defer this run, not be shortened.
            if delay > self.max_retry_after:
                return None
            return max(0, delay)
        return min(self.max_retry_after, self.backoff * 2 ** attempt)

    def request(self, method: str, url: str, *, respect_robots=False,
                allow_redirects=True, raise_for_status=True, retry_post=False, **kwargs):
        method = method.upper()
        kwargs.setdefault("timeout", self.timeout)
        retries = self.retries if method in {"GET", "HEAD"} or retry_post else 0
        history = []
        for redirect in range(self.max_redirects + 1):
            self._remaining()
            self._check_source_policy(url)
            self._check_cooldown(url)
            allow_url(url, resolve_dns=self.resolve_dns)
            if respect_robots:
                # Requests appends params after this point. Evaluate the actual
                # query now so a ?page= restriction cannot be skipped by using
                # params={"page": 2} instead of an already assembled URL.
                policy_url = requests.Request(method, url, params=kwargs.get("params")).prepare().url
                if not self.robots_allowed(policy_url):
                    raise AccessRestricted("Robots policy disallows access or could not be verified", request=None)
            response = None
            for attempt in range(retries + 1):
                self._remaining()
                self._check_cooldown(url)
                self._pace(url)
                self._check_cooldown(url)
                try:
                    call_kwargs = dict(kwargs, timeout=self._bounded_timeout(kwargs["timeout"]))
                    response = self.session.request(method, url, allow_redirects=False, **call_kwargs)
                    self._record_response(url, response)
                    self._remaining()
                except (requests.Timeout, requests.ConnectionError):
                    if attempt >= retries:
                        raise
                    self._sleep(self._retry_delay(None, attempt))
                    continue
                if response.status_code == 429 or response.status_code not in {408, 500, 502, 503, 504} or attempt >= retries:
                    break
                delay = self._retry_delay(response, attempt)
                if delay is None:
                    break
                response.close()
                self._sleep(delay)
            if allow_redirects and response.status_code in {301, 302, 303, 307, 308} and response.headers.get("Location"):
                if redirect >= self.max_redirects:
                    raise requests.TooManyRedirects("Redirect limit reached", response=response)
                next_url = urljoin(response.url or url, response.headers["Location"])
                if urlsplit(url).scheme == "https" and urlsplit(next_url).scheme != "https":
                    raise ValueError("HTTPS downgrade redirect rejected")
                if urlsplit(url).netloc != urlsplit(next_url).netloc:
                    headers = kwargs.get("headers", {})
                    kwargs["headers"] = {k: v for k, v in headers.items() if k.lower() not in {"authorization", "cookie", "proxy-authorization"}}
                    kwargs.pop("auth", None)
                if response.status_code == 303 or (response.status_code in {301, 302} and method == "POST"):
                    method = "GET"
                    kwargs.pop("data", None)
                    kwargs.pop("json", None)
                kwargs.pop("params", None)
                history.append(response)
                response.close()
                url = next_url
                continue
            if raise_for_status:
                response.raise_for_status()
            response.history = history
            return response
        raise requests.TooManyRedirects("Redirect limit reached")

    def get(self, url: str, **kwargs):
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs):
        return self.request("POST", url, **kwargs)

"""Check job identity and content at both destinations, never equating 200 with open."""
from __future__ import annotations

from datetime import datetime, timezone
from html.parser import HTMLParser
import ipaddress
import json
import re
from urllib.parse import parse_qs, unquote, urljoin, urlsplit

import requests

from .classify import plain

VALIDATOR_VERSION = 4


class Page(HTMLParser):
    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.visible, self.headings, self.scripts = [], [], []
        self.content, self.semantic = [], []
        self.script = None
        self.hidden = 0
        self.heading = 0
        self.navigation = 0
        self.semantic_depth = 0
        self.elements = []
        self.has_form = False
        self.form_depth = 0
        self.form_text = []
        self.application_input = False
        self.anchors = []
        self.anchor = None
        self.feed(text[:2_000_000])

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        semantic = tag in {"main", "article"} or bool(re.search(r"(?:job[-_ ]?description|posting[-_ ]?content|job[-_ ]?content|description[-_ ]?content)", attrs.get("class", "") + " " + attrs.get("id", ""), re.I))
        if tag not in {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}:
            self.elements.append((tag, semantic))
            if semantic:
                self.semantic_depth += 1
        if tag in {"nav", "footer", "header"}:
            self.navigation += 1
        if tag in {"script", "style", "noscript"}:
            self.hidden += 1
        if tag == "script" and "ld+json" in attrs.get("type", ""):
            self.script = []
        if tag in {"h1", "title"}:
            self.heading += 1
        if tag == "form":
            self.has_form = True
            self.form_depth += 1
        if tag == "input" and self.form_depth and (attrs.get("type") == "file" or re.search(r"resume|curriculum|(?:^|[_-])cv(?:$|[_-])", attrs.get("name", "") + " " + attrs.get("id", ""), re.I)):
            self.application_input = True
        if tag == "a" and attrs.get("href"):
            self.anchor = [attrs["href"], []]
        if tag == "iframe" and re.search(r"/(?:embed/job_app|apply|application)(?:[/?#]|$)", attrs.get("src", ""), re.I):
            self.anchors.append((attrs["src"], "Embedded application form"))

    def handle_endtag(self, tag):
        if tag == "form":
            self.form_depth = max(0, self.form_depth - 1)
        if tag == "a" and self.anchor is not None:
            self.anchors.append((self.anchor[0], plain(" ".join(self.anchor[1]))))
            self.anchor = None
        for index in range(len(self.elements)-1, -1, -1):
            if self.elements[index][0] == tag:
                self.semantic_depth -= sum(1 for _, sem in self.elements[index:] if sem)
                del self.elements[index:]
                break
        if tag in {"nav", "footer", "header"}:
            self.navigation = max(0, self.navigation - 1)
        if tag == "script" and self.script is not None:
            self.scripts.append("".join(self.script))
            self.script = None
        if tag in {"script", "style", "noscript"}:
            self.hidden = max(0, self.hidden - 1)
        if tag in {"h1", "title"}:
            self.heading = max(0, self.heading - 1)

    def handle_data(self, data):
        if self.form_depth and not self.hidden:
            self.form_text.append(data)
        if self.anchor is not None:
            self.anchor[1].append(data)
        if self.script is not None:
            self.script.append(data)
        if not self.hidden:
            self.visible.append(data)
            if self.heading:
                self.headings.append(data)
            elif not self.navigation and not self.form_depth:
                self.content.append(data)
                if self.semantic_depth:
                    self.semantic.append(data)

    @property
    def text(self):
        return plain(" ".join(self.visible))

    def postings(self):
        def walk(value):
            if isinstance(value, list):
                for item in value:
                    yield from walk(item)
            if isinstance(value, dict):
                kind = value.get("@type", [])
                if "JobPosting" in (kind if isinstance(kind, list) else [kind]):
                    yield value
                for item in value.values():
                    if isinstance(item, (dict, list)):
                        yield from walk(item)
        for script in self.scripts:
            try:
                yield from walk(json.loads(script))
            except (ValueError, TypeError):
                continue


def normalized(value):
    return re.sub(r"[^a-z0-9]+", " ", plain(value).lower()).strip()


def valid_url(url):
    if not isinstance(url, str) or re.search(r"[\x00-\x20\x7f]", url):
        return False
    try:
        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
            return False
        if parsed.hostname.lower() in {"localhost", "localhost.localdomain"} or parsed.hostname.lower().endswith((".local", ".localhost", ".internal")):
            return False
        try:
            if not ipaddress.ip_address(parsed.hostname).is_global:
                return False
        except ValueError:
            pass
        parsed.port  # also rejects malformed port syntax
        return True
    except ValueError:
        return False


def url_ids(url):
    parsed = urlsplit(url)
    ids = set()
    for key, values in parse_qs(parsed.query).items():
        if key.lower() in {"gh_jid", "jobid", "job_id", "reqid", "requisitionid", "jid", "id"}:
            ids.update(normalized(v) for v in values if len(v) >= 3)
    for part in unquote(parsed.path).split("/"):
        # Whole numeric IDs, UUIDs, and job-detail slugs with numeric IDs.
        if re.fullmatch(r"\d{4,}", part) or re.search(r"[0-9a-f]{8}-[0-9a-f-]{27,}", part, re.I):
            ids.add(normalized(part))
        for match in re.findall(r"(?:^|[-_])([A-Z]*\d{5,})(?=$|[-_])", part):
            if match:
                ids.add(normalized(match))
    return ids


def generic_url(url):
    parsed = urlsplit(url)
    if url_ids(url):
        return False
    parts = [p for p in parsed.path.lower().split("/") if p]
    if parsed.hostname in {"jobs.ashbyhq.com", "jobs.lever.co", "jobs.eu.lever.co", "job-boards.greenhouse.io", "boards.greenhouse.io"} and len(parts) <= 1:
        return True
    generic = {"jobs", "careers", "career", "search", "opportunities", "openings", "en", "en-us", "en-gb", "us", "job-search", "jobsearch", "results"}
    return not parts or all(p in generic for p in parts)


def meaningful_description(text):
    text = plain(text)
    return len(text) >= 120 and len(text.split()) >= 18 and bool(re.search(
        r"\b(?:responsibilit|qualification|requirements?|you will|you'll|your (?:role|work|duties)|about (?:the )?(?:role|job)|(?:the|this) (?:role|position|internship)|as an? (?:\w+\s+){0,5}intern|duties)\w*\b", text, re.I))


EXPIRED = re.compile(r"\b(?:this (?:job|position|role|posting|vacancy) (?:is |has been |was )?(?:no longer available|no longer accepting|closed|filled|removed|expired)|(?:job|position|posting) (?:has )?expired|no longer accepting applications|the job you (?:are looking for|requested) (?:is no longer|could not be)|job not found|position not found)\b", re.I)
BLOCKED = re.compile(r"\b(?:verify you are (?:a )?human|access denied|request blocked|checking your browser|enable javascript and cookies|captcha|unusual traffic|security verification)\b", re.I)
LOGIN = re.compile(r"\b(?:sign in to (?:apply|continue|view)|log in to (?:apply|continue|view)|login required|authentication required)\b", re.I)


def _check(job, url, kind, client, cache):
    check = {"kind": kind, "requested_url": url, "final_url": None,
             "status": "unverified", "evidence": []}
    if not valid_url(url):
        check["evidence"].append("malformed_or_unsafe_url")
        return check
    try:
        if url not in cache:
            try:
                cache[url] = client.get(url, allow_redirects=True, respect_robots=True, raise_for_status=False)
            except (requests.RequestException, OSError, ValueError, TimeoutError) as exc:
                cache[url] = exc
        response = cache[url]
        if isinstance(response, Exception):
            raise response
    except (requests.RequestException, OSError, ValueError, TimeoutError) as exc:
        response = getattr(exc, "response", None)
        if response is None:
            check["evidence"].append("access_failure:" + type(exc).__name__)
            return check
    check["http_status"] = response.status_code
    check["final_url"] = response.url or url
    if not valid_url(check["final_url"]):
        check["evidence"].append("unsafe_or_malformed_redirect")
        return check
    if response.status_code in {404, 410}:
        if BLOCKED.search(Page(response.text).text):
            check["evidence"].append("access_challenge_with_not_found_http_status")
            return check
        check.update(status="closed", evidence=["http_not_found_or_gone"])
        return check
    if response.status_code in {401, 403, 408, 425, 429, 451} or response.status_code >= 500:
        check["evidence"].append("blocked_rate_limited_or_temporary_http_failure")
        return check
    if response.status_code < 200 or response.status_code >= 300:
        check["evidence"].append("unexpected_http_status")
        return check
    page = Page(response.text)
    text = page.text
    application_links = []
    for href, label in page.anchors:
        if re.search(r"\b(?:apply(?: now| for (?:this|the) (?:job|position|role))?|submit (?:an? )?application|embedded application form)\b", label, re.I):
            target = urljoin(check["final_url"], href)
            if valid_url(target):
                application_links.append({"url":target, "text":label[:100]})
    application_links.sort(key=lambda link: (
        bool(url_ids(link["url"]).intersection(url_ids(url))),
        not generic_url(link["url"]),
        bool(re.fullmatch(r"apply(?: now| for (?:this|the) (?:job|position|role))?|submit application", link["text"], re.I))), reverse=True)
    check["application_links"] = application_links
    if BLOCKED.search(text):
        check["evidence"].append("access_challenge")
        return check
    if LOGIN.search(text):
        check["evidence"].append("login_required")
        return check
    expired = EXPIRED.search(text)
    if expired:
        check.update(status="closed", evidence=["explicit_expiry:" + expired.group(0)])
        return check
    postings = list(page.postings())
    expected = normalized(job.get("title"))
    employer = normalized(job.get("employer") or job.get("company"))
    title_match = bool(expected and expected in normalized(" ".join(page.headings)))
    body_title_match = bool(expected and expected in normalized(text))
    employer_match = bool(employer and employer in normalized(text))
    expected_ids = url_ids(url)
    destination_ids = url_ids(check["final_url"])
    same_id = bool(expected_ids.intersection(destination_ids))
    description = ""
    structured_match = None
    for posting in postings:
        candidate_title = normalized(posting.get("title"))
        if expected and (candidate_title == expected or expected in candidate_title):
            organization = posting.get("hiringOrganization", {})
            org_name = normalized(organization.get("name")) if isinstance(organization, dict) else normalized(organization)
            if org_name and employer and employer not in org_name and org_name not in employer:
                continue
            structured_match = posting
            description = plain(posting.get("description"))
            title_match = True
            employer_match = employer_match or bool(org_name)
            break
    if structured_match:
        check["evidence"].append("matching_JobPosting_schema")
        valid_through = structured_match.get("validThrough")
        if valid_through:
            try:
                date = datetime.fromisoformat(str(valid_through).replace("Z", "+00:00"))
                if date.tzinfo is None:
                    date = date.replace(tzinfo=timezone.utc)
                if date < datetime.now(timezone.utc):
                    check.update(status="closed", evidence=check["evidence"] + ["JobPosting_validThrough_expired:" + str(valid_through)])
                    return check
            except ValueError:
                check["evidence"].append("invalid_validThrough")
    if check["final_url"] != url and generic_url(check["final_url"]) and not structured_match:
        check.update(status="closed", evidence=check["evidence"] + ["redirect_to_generic_careers_page"])
        return check
    if generic_url(check["final_url"]) and not structured_match:
        check["evidence"].append("generic_page_not_job_specific")
        return check
    if expected_ids and destination_ids and not same_id:
        check["evidence"].append("redirected_to_different_job_identifier")
        return check
    identity = bool(structured_match or (title_match and (same_id or employer_match)) or (body_title_match and same_id and employer_match))
    if not identity:
        check["evidence"].append("expected_job_identity_not_verified")
        return check
    check["evidence"].append("expected_job_identity_verified")
    if not description:
        # Navigation, footer links, and the expected title cannot substitute for
        # a job description. Prefer an article/main or explicit description div.
        description = plain(" ".join(page.semantic or page.content))
    application_form = page.has_form and (page.application_input or bool(re.search(r"\b(?:resume|cv|submit application|apply for this job)\b", plain(" ".join(page.form_text)), re.I)))
    if kind == "application" and application_form:
        check["status"] = "open"
        check["evidence"].append("job_specific_application_form_present")
    elif kind == "application":
        check["evidence"].append("application_destination_not_verified")
    elif meaningful_description(description):
        check.update(status="open", description=description[:50_000])
        check["evidence"].append("meaningful_description_present")
    else:
        check["evidence"].append("missing_meaningful_description_or_application")
    return check


def validate_job(job: dict, client) -> dict:
    """Client must enforce timeout/retries/public DNS and robots restrictions.

    A shared URL is fetched once but assessed for both purposes. A blocked or
    missing destination is unverified; closure requires affirmative evidence.
    """
    description_url = job.get("description_url") or job.get("url")
    application_url = job.get("application_url") or description_url
    cache = {}
    checks = [_check(job, description_url, "description", client, cache)]
    visited = set()
    current = application_url
    for _ in range(4):
        visited.add(current)
        application_check = _check(job, current, "application", client, cache)
        checks.append(application_check)
        if application_check["status"] in {"open", "closed"}:
            break
        if "expected_job_identity_verified" not in application_check["evidence"]:
            break
        target = next((link["url"] for link in application_check.get("application_links", [])
                       if link["url"] not in visited and link["url"].split("#")[0] != current.split("#")[0]), None)
        if not target:
            break
        if (urlsplit(target).netloc == urlsplit(current).netloc and url_ids(target) and url_ids(current)
                and not url_ids(target).intersection(url_ids(current))):
            application_check["evidence"].append("apply_link_points_to_different_job_identifier")
            break
        application_check["evidence"].append("followed_job_page_apply_link")
        current = target
    statuses = [checks[0]["status"], checks[-1]["status"]]
    status = "closed" if "closed" in statuses else "open" if all(s == "open" for s in statuses) else "unverified"
    result = {"status": status, "description_url": description_url,
              "application_url": application_url,
              "final_description_url": checks[0]["final_url"],
              "final_application_url": checks[-1]["final_url"],
              "checked_at": datetime.now(timezone.utc).isoformat(), "validator_version": VALIDATOR_VERSION, "checks": checks}
    if checks[0].get("description") and checks[0]["status"] == "open":
        result["description"] = checks[0]["description"]
    return result

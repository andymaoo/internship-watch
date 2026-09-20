"""Public structured source adapters. Collection never title-filters jobs.

Preserve identifiers and evidence first; the classifier decides eligibility.
Failure to prove completeness raises SourceError and never masquerades as [].
"""
from __future__ import annotations

import html
import re
from datetime import datetime, timezone
from urllib.parse import quote, urlsplit


class SourceError(RuntimeError):
    pass


def _text(value):
    if value is None:
        return ""
    return str(value).strip()


def _description(value):
    value = html.unescape(html.unescape(_text(value)))
    value = re.sub(r"<\s*(?:br|/p|/li|/div|/h[1-6])\s*/?>", "\n", value, flags=re.I)
    return html.unescape(re.sub(r"<[^>]+>", " ", value)).strip()


def _json(client, url, **kwargs):
    response = client.get(url, **kwargs)
    response.raise_for_status()
    try:
        return response.json()
    except ValueError as exc:
        raise SourceError("Source returned invalid JSON") from exc


def _required(item, *keys):
    if not isinstance(item, dict) or any(item.get(key) in (None, "") for key in keys):
        raise SourceError(f"Job lacks required fields: {', '.join(keys)}")


def _jobs_list(payload, key=None):
    if key:
        if not isinstance(payload, dict) or key not in payload:
            raise SourceError(f"Expected object containing {key}")
        payload = payload[key]
    if not isinstance(payload, list):
        raise SourceError("Expected a jobs array")
    return payload


def _base(source, prefix, identity, title, description_url, *, description="", application_url=None,
          locations=None, employment_type=None, posting_date=None, evidence=None, season=None):
    # Greenhouse multi-select metadata (including HRT's Job Type) is an array.
    # Keep the original metadata in evidence, but persist a scalar in SQLite.
    if isinstance(employment_type, list):
        if not all(isinstance(value, str) for value in employment_type):
            raise SourceError("Employment type array must contain strings")
        employment_type = "; ".join(dict.fromkeys(value.strip() for value in employment_type if value.strip())) or None
    elif employment_type is not None and not isinstance(employment_type, str):
        raise SourceError("Employment type must be a string or string array")
    locations = list(dict.fromkeys(_text(item) for item in (locations or []) if _text(item)))
    evidence = evidence or {}
    address = evidence.get("address") or {}
    postal = address.get("postalAddress", address) if isinstance(address, dict) else {}
    return {"source_id": f"{prefix}-{identity}", "employer": source.get("employer", source.get("name", source.get("slug", source["id"]))),
            "title": _text(title), "description": _description(description), "location": "; ".join(locations),
            "locations": locations, "employment_type": employment_type, "description_url": description_url,
            "application_url": application_url or description_url, "posting_date": posting_date,
            "evidence": evidence, "season": season, "active": True, "address": address,
            "country": postal.get("addressCountry") if isinstance(postal, dict) else None,
            "is_remote": evidence.get("is_remote"), "workplace_type": evidence.get("workplace_type")}


def _check_unexpected_pagination(payload):
    if any(payload.get(key) for key in ("next", "nextPage", "next_page", "nextCursor", "next_cursor", "hasMore")):
        raise SourceError("Unexpected pagination in full-board endpoint; adapter update required")


def greenhouse(source, client):
    slug = source["slug"]
    data = _json(client, f"https://boards-api.greenhouse.io/v1/boards/{quote(slug, safe='')}/jobs", params={"content": "true"})
    items = _jobs_list(data, "jobs")
    _check_unexpected_pagination(data)
    total = data.get("meta", {}).get("total")
    if total is not None and total != len(items):
        raise SourceError(f"Incomplete Greenhouse board: total={total}, received={len(items)}")
    jobs = []
    for item in items:
        _required(item, "id", "title", "absolute_url")
        metadata = item.get("metadata") or []
        employment_type = None
        for field in metadata:
            if isinstance(field, dict) and re.search(r"employment|commitment|job.?type", field.get("name", ""), re.I):
                employment_type = field.get("value")
        jobs.append(_base(source, "gh", f"{slug}-{item['id']}", item["title"], item["absolute_url"],
            description=item.get("content"), locations=[(item.get("location") or {}).get("name", "")], employment_type=employment_type,
            evidence={"provider": "greenhouse", "provider_job_id": str(item["id"]), "requisition_id": item.get("requisition_id"),
                      "source_updated_at": item.get("updated_at"), "metadata": metadata,
                      "departments": item.get("departments", []), "offices": item.get("offices", [])}))
    return jobs


def lever(source, client):
    slug = source["slug"]
    api_host = "api.eu.lever.co" if source.get("region") == "eu" else "api.lever.co"
    size, maximum = int(source.get("page_size", 100)), int(source.get("max_pages", 100))
    if not 1 <= size <= 1000 or not 1 <= maximum <= 1000:
        raise SourceError("Invalid Lever pagination bounds")
    jobs, seen, offset = [], set(), 0
    for page in range(maximum):
        items = _jobs_list(_json(client, f"https://{api_host}/v0/postings/{quote(slug, safe='')}", params={"mode": "json", "skip": offset, "limit": size}))
        if not items:
            return jobs
        for item in items:
            _required(item, "id", "text", "hostedUrl")
            if item["id"] in seen:
                raise SourceError("Lever repeated a job across pages; pagination is unstable")
            seen.add(item["id"])
            categories = item.get("categories") or {}
            description = item.get("descriptionPlain") or item.get("description", "")
            description += "\n" + "\n".join(f"{entry.get('text', '')}\n{entry.get('content', '')}" for entry in item.get("lists", []))
            description += "\n" + (item.get("additionalPlain") or item.get("additional", ""))
            # Lever createdAt is creation time, not documented employer publication.
            jobs.append(_base(source, "lv", f"{slug}-{item['id']}", item["text"], item["hostedUrl"],
                description=description, application_url=item.get("applyUrl"), locations=[categories.get("location", "")], employment_type=categories.get("commitment"),
                evidence={"provider": "lever", "provider_job_id": item["id"], "source_created_at": item.get("createdAt"), "categories": categories, "workplace_type": item.get("workplaceType")}))
        offset += len(items)
    raise SourceError(f"Lever reached {maximum} pages without proving end of board")


def ashby(source, client):
    slug = source["slug"]
    data = _json(client, f"https://api.ashbyhq.com/posting-api/job-board/{quote(slug, safe='')}")
    items = _jobs_list(data, "jobs")
    _check_unexpected_pagination(data)
    if data.get("apiVersion", "1") != "1":
        raise SourceError("Unsupported Ashby API version")
    jobs = []
    for item in items:
        _required(item, "title", "jobUrl")
        if item.get("isListed") is False:
            continue
        identity = item.get("id") or urlsplit(item["jobUrl"]).path.rstrip("/").split("/")[-1]
        if not identity:
            raise SourceError("Missing Ashby job identity")
        locations = [item.get("location", "")] + [location.get("location", "") for location in item.get("secondaryLocations", [])]
        jobs.append(_base(source, "ab", f"{slug}-{identity}", item["title"], item["jobUrl"],
            description=item.get("descriptionPlain") or item.get("descriptionHtml"), application_url=item.get("applyUrl"),
            locations=locations, employment_type=item.get("employmentType"), posting_date=item.get("publishedAt"),
            evidence={"provider": "ashby", "provider_job_id": identity, "posting_date_kind": "last_published", "is_remote": item.get("isRemote"),
                      "workplace_type": item.get("workplaceType"), "address": item.get("address"), "secondary_locations": item.get("secondaryLocations", []),
                      "department": item.get("department"), "team": item.get("team")}))
    return jobs


def simplify(source, client):
    items = _jobs_list(_json(client, source["url"]))
    companies = {name.casefold() for name in source.get("companies", [])}
    jobs = []
    for item in items:
        _required(item, "id", "company_name", "title", "url")
        if not isinstance(item.get("active"), bool) or not isinstance(item.get("is_visible"), bool):
            raise SourceError("Simplify active/is_visible schema missing or changed")
        if not item["is_visible"] or not item["active"]:
            continue
        if companies and item["company_name"].casefold() not in companies:
            continue
        row_source = dict(source, employer=item["company_name"])
        jobs.append(_base(row_source, "simplify", item["id"], item["title"], item["url"],
            description=item.get("description", ""), application_url=item.get("application_url", item["url"]),
            locations=item.get("locations", []), employment_type=item.get("employment_type"), season=item.get("terms", []),
            evidence={"provider": "simplify", "feed_url": source["url"], "feed_internship_context": True,
                      "source_added_at": item.get("date_posted"), "source_updated_at": item.get("date_updated"), "source_active": item["active"],
                      "category": item.get("category"), "sponsorship": item.get("sponsorship"), "degrees": item.get("degrees", []),
                      "upstream_source": item.get("source"), "terms": item.get("terms", [])}))
    return jobs


class _WebSession:
    """Adapt repaired legacy code while honoring webpage policies and identity."""
    def __init__(self, client):
        self.client = client

    def _request(self, method, url, **kwargs):
        headers = kwargs.get("headers", {})
        kwargs["headers"] = {k: v for k, v in headers.items() if k.lower() != "user-agent" and not k.lower().startswith("sec-")}
        kwargs["respect_robots"] = True
        # Keep the operator's centrally configured timeout.
        kwargs.pop("timeout", None)
        if method == "post":
            kwargs["retry_post"] = True  # only the read-only search operation
        return getattr(self.client, method)(url, **kwargs)

    def get(self, url, **kwargs):
        return self._request("get", url, **kwargs)

    def post(self, url, **kwargs):
        return self._request("post", url, **kwargs)


def apple(source, client):
    from apple_scraper import fetch_apple_internships
    requested_locations = source.get("location_filters", ["postLocation-USA"])
    records = fetch_apple_internships(max_pages=source.get("max_pages", 100), locations=requested_locations, session=_WebSession(client))
    return [_apple_job(source, item) for item in records]


def _apple_job(source, item):
    record = item.get("source_record", {})
    requested_locations = source.get("location_filters", ["postLocation-USA"])
    locations = []
    for location in record.get("locations", []):
        if isinstance(location, dict):
            locations.append(", ".join(dict.fromkeys(value for value in (location.get("city"), location.get("stateProvince"), location.get("countryName")) if value)) or location.get("name", ""))
    # The configured server query establishes country if the search result omits it.
    if not any(locations) and requested_locations == ["postLocation-USA"]:
        locations = ["United States"]
    country = "USA" if requested_locations == ["postLocation-USA"] else None
    return _base(dict(source, employer="Apple"), "apple", item["id"], item["title"], item["url"],
        locations=locations, description=record.get("jobSummary", ""), posting_date=record.get("postDateInGMT"),
        evidence={"provider": "apple", "provider_job_id": item["id"], "description_kind": "employer_search_summary",
            "posting_date_kind": "employer_postDateInGMT", "address": {"postalAddress": {"addressCountry": country}},
            "search_query": "internship", "location_filters": requested_locations, "source_record": record})


ADAPTERS = {"greenhouse": greenhouse, "lever": lever, "ashby": ashby, "simplify": simplify, "apple": apple}

def collect(source: dict, client) -> list[dict]:
    from . import employer_sources
    from . import platform_sources
    from . import finance_sources
    for name in ("deshaw", "trexquant", "groupone", "bankofamerica", "icims_board", "panagora", "finance_avature", "moodys", "renaissance"):
        ADAPTERS[name] = getattr(finance_sources, name)
    for name in ('workday', 'jibe', 'atlassian', 'jobvite', 'oracle'):
        ADAPTERS[name] = getattr(platform_sources, name)
    for name in ('smartrecruiters', 'eightfold', 'snap', 'uber', 'amazon', 'rippling', 'bloomberg', 'bytedance', 'tiktok'):
        ADAPTERS[name] = getattr(employer_sources, name)
    if source.get("type") not in ADAPTERS:
        raise SourceError(f"Unsupported or quarantined adapter: {source.get('type')}")
    jobs = ADAPTERS[source["type"]](source, client)
    identities = [job["source_id"] for job in jobs]
    if len(identities) != len(set(identities)):
        raise SourceError("Source returned duplicate stable IDs")
    return jobs

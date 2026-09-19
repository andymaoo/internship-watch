"""Read one public Google posting, never its restricted search pagination.

Google renders an individual posting as public ``ds:0`` page data alongside
unrelated search results (``ds:1``). Only the URL-bound detail record is usable.
No RPC, session token, undocumented timestamp semantics, or browser identity is
needed. A changed schema is an unverified check, not an empty or closed job.
"""
from __future__ import annotations

import json
import re
from urllib.parse import parse_qs, urlsplit

from .classify import degree_evidence, plain


class GoogleDetailError(ValueError):
    pass


def google_job_id(url):
    try:
        parsed = urlsplit(url)
        if (parsed.scheme != "https" or parsed.hostname != "www.google.com"
                or parsed.username or parsed.password or parsed.port not in {None, 443}):
            return None
    except (TypeError, ValueError):
        return None
    match = re.fullmatch(r"/about/careers/applications/jobs/results/(\d{8,})(?:-[a-zA-Z0-9-]+)?/?", parsed.path)
    return match.group(1) if match else None


def _normal(value):
    return re.sub(r"[^a-z0-9]+", " ", plain(value).lower()).strip()


def google_title_matches(expected, actual):
    """Bind a known feed suffix only after the caller verifies the exact job ID."""
    expected = re.sub(r"\s+-\s+Multiple Teams\s*$", "", expected or "", flags=re.I)
    expected = re.sub(r"^(Data Scientist) Intern - (Product)$", r"\1 \2 Intern", expected, flags=re.I)
    aliases = {"engineering": "engineer", "internship": "intern", "internships": "intern", "apprenticeship": "apprentice"}
    wanted = [aliases.get(word, word) for word in _normal(expected).split()]
    observed = [aliases.get(word, word) for word in _normal(actual).split()]
    if len(wanted) < 3:
        return False
    # Never remove "intern": prior experience in the description is not proof
    # that a permanent position is an internship.
    if "intern" in wanted and "intern" not in observed:
        return False
    iterator = iter(observed)
    return all(any(word == candidate for candidate in iterator) for word in wanted)


def parse_google_detail(text, url):
    identity = google_job_id(url)
    if not identity:
        raise GoogleDetailError("not_google_job_detail")
    markers = list(re.finditer(r"AF_initDataCallback\(\{\s*key:\s*'ds:0',\s*hash:\s*'[^']*',\s*data:", text))
    if len(markers) != 1:
        raise GoogleDetailError("detail_schema_missing_or_ambiguous")
    try:
        payload, _ = json.JSONDecoder().raw_decode(text[markers[0].end():].lstrip())
    except (ValueError, RecursionError) as exc:
        raise GoogleDetailError("detail_json_invalid") from exc
    if not isinstance(payload, list) or len(payload) != 1 or not isinstance(payload[0], list):
        raise GoogleDetailError("detail_schema_changed")
    row = payload[0]
    if len(row) != 21:
        raise GoogleDetailError("detail_schema_changed")
    if not isinstance(row[0], str) or row[0] != identity:
        raise GoogleDetailError("detail_identifier_mismatch")
    if row[7] != "Google":
        raise GoogleDetailError("detail_employer_mismatch")
    if not isinstance(row[1], str) or not row[1].strip():
        raise GoogleDetailError("detail_title_missing")
    fields = {}
    for index in (3, 4, 10, 15, 18, 19):
        value = row[index]
        if value is None and index in {15, 18}:
            fields[index] = ""
        elif isinstance(value, list) and len(value) == 2 and value[0] is None and isinstance(value[1], str):
            fields[index] = plain(value[1])
        else:
            raise GoogleDetailError("detail_description_schema_changed")
    if not fields[4] or not fields[10] or not fields[19]:
        raise GoogleDetailError("detail_description_incomplete")
    if not isinstance(row[9], list) or not row[9]:
        raise GoogleDetailError("detail_locations_missing")
    locations = []
    for value in row[9]:
        if not isinstance(value, list) or len(value) < 6 or not isinstance(value[0], str) or not isinstance(value[5], str):
            raise GoogleDetailError("detail_locations_schema_changed")
        locations.append({"name": value[0], "country": value[5]})
    try:
        application = urlsplit(row[2])
        query = parse_qs(application.query)
        if (application.scheme != "https" or application.netloc != "www.google.com"
                or application.path != "/about/careers/applications/signin"
                or not query.get("jobId") or len(query.get("title", [])) != 1
                or len(_normal(query["title"][0]).split()) < 2
                or not (_normal(row[1]) == _normal(query["title"][0])
                        or _normal(row[1]).startswith(_normal(query["title"][0]) + " "))):
            raise ValueError("unbound application")
    except (TypeError, ValueError, AttributeError) as exc:
        raise GoogleDetailError("detail_application_identity_mismatch") from exc
    degrees, _, _ = degree_evidence({"description": fields[19]}, row[1], fields[19], {})
    return {
        "id": identity, "title": row[1], "employer": "Google",
        "description": "\n\n".join(part for part in (
            fields[15], "About the job\n" + fields[10],
            "Responsibilities\n" + fields[3], fields[4], fields[18],
            "Minimum qualifications\n" + fields[19]) if part),
        "application_url": row[2], "locations": locations,
        "minimum_qualifications": fields[19], "degrees": degrees,
        "posting_url": f"https://www.google.com/about/careers/applications/jobs/results/{identity}",
    }


def apply_google_eligibility(job, proof):
    """Prefer exact employer qualifications over sparse community degree tags.

    The original feed remains in source_records/observations. Preserve this
    narrow proof on refresh only for the same Google requisition and role.
    """
    if (not isinstance(proof, dict) or proof.get("kind") != "google_public_detail"
            or proof.get("job_id") != google_job_id(job.get("description_url"))
            or _normal(job.get("employer")) != "google"
            or not google_title_matches(job.get("title"), proof.get("title", ""))
            or not isinstance(proof.get("minimum_qualifications"), str)
            or not proof["minimum_qualifications"].strip()
            or not proof.get("degrees")
            or (job.get("evidence") or {}).get("provider") != "simplify"):
        return False
    job["evidence"] = dict(job.get("evidence") or {})
    job["evidence"]["validated_google_eligibility"] = dict(proof)
    job["evidence"]["degrees"] = list(proof["degrees"])
    if "degrees" in job:
        job["degrees"] = list(proof["degrees"])
    return True

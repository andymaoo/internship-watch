"""Evidence extraction for staging the member feed, independent of private filters."""
import re

from .classify import (CATEGORY_PATTERNS, COOP, HARDWARE, HARDWARE_DUTIES, INTERN,
                       US_CITIES, US_STATES, countries_in, country_code, plain)
from .member_routes import member_route

GRAD = re.compile(r"\b(?:new[- ]grad(?:uate)?s?|graduate (?:program(?:me)?|scheme)|university graduate|recent graduates?)\b", re.I)
IB = re.compile(r"\binvestment[- ]banking\b", re.I)
REMOTE = re.compile(r"\b(?:remote|work from anywhere)\b", re.I)
HYBRID = re.compile(r"\b(?:hybrid|on[- ]site|in[- ]office)\b", re.I)
REGION = re.compile(r"\b(?:EMEA|APAC|Europe|Asia[- ]Pacific|Latin America|Australia|Singapore|Ireland|Netherlands|Switzerland|New Zealand)\b", re.I)
US = re.compile(rf"\b(?:{US_CITIES})\b|,\s*(?:{'|'.join(US_STATES)})(?:\b|$)", re.I)
RESTRICTION = re.compile(
    r"\b(?:must (?:be (?:currently )?(?:based|located)|reside|live|work) in|"
    r"remote (?:work )?(?:is )?(?:only (?:available )?in|limited to|restricted to))\s+([^.;!?]{1,120})",
    re.I,
)
NO_US = re.compile(r"\b(?:excluding|except|not available in) (?:the )?(?:US|USA|United States)\b", re.I)


def geography(job: dict) -> tuple[bool | None, bool]:
    location = plain(job.get("location"))
    evidence = job.get("evidence") or {}
    if not isinstance(evidence, dict):
        evidence = {}
    workplace = plain(job.get("workplace_type") or job.get("workplaceType") or evidence.get("workplace_type"))
    description = plain(job.get("description"))
    location_fields = f"{location} {workplace}"
    remote = bool(not HYBRID.search(location_fields) and
                  (job.get("is_remote") is True or REMOTE.search(location_fields)))
    if remote and NO_US.search(description + " " + location_fields):
        return False, remote
    if remote:
        for scope in RESTRICTION.findall(description):
            countries = countries_in(scope)
            if "US" not in countries and not US.search(scope) and (countries or REGION.search(scope)):
                return False, remote
    raw_countries = job.get("countries") or job.get("country") or evidence.get("country") or []
    if isinstance(raw_countries, str):
        raw_countries = [raw_countries]
    countries = countries_in(location) | {country_code(value) for value in raw_countries if plain(value)}
    # Explicit foreign countries take precedence over shared city names
    # (e.g. London, UK or Berkeley, Canada).
    if "US" in countries or (not countries and US.search(location)):
        return True, remote
    if countries or REGION.search(location):
        return False, remote
    return None, remote


def opportunity_type(job: dict) -> str:
    title = plain(job.get("title"))
    employment = plain(job.get("employment_type"))
    description = plain(job.get("description"))
    labels = f"{title} {employment}"
    intern = bool(INTERN.search(labels) or re.search(
        r"\bthis (?:role|position) is an? (?:paid )?internship\b", description, re.I))
    grad = bool(GRAD.search(labels) or re.search(
        r"\bthis (?:role|position|program) is (?:designed )?for (?:new|recent) graduates\b",
        description, re.I))
    if intern and (grad or re.search(r"\bnot an? internship\b", description, re.I)):
        return ""
    if intern:
        return "internship"
    if grad and not COOP.search(labels):
        return "new_grad"
    return ""


def category(job: dict) -> str:
    title = plain(job.get("title"))
    description = plain(job.get("description"))
    if HARDWARE.search(title) or HARDWARE_DUTIES.search(description):
        return ""
    if IB.search(title):
        return "investment_banking"
    return next((name for name, pattern in CATEGORY_PATTERNS if pattern.search(title)), "")


def preview_member_listing(job: dict) -> dict:
    """Return explicit staging labels and a route only if delivery checks pass."""
    us, remote = geography(job)
    kind, topic = opportunity_type(job), category(job)
    return dict(us_eligible=us, remote=remote, opportunity_type=kind, category=topic,
                route=member_route(us_eligible=us, remote=remote, opportunity_type=kind,
                                   category=topic, posting_status=job.get("posting_status", ""),
                                   application_status=job.get("application_status", "")))

"""Evidence extraction for staging the member feed, independent of private filters."""
import re

from .classify import (CATEGORY_PATTERNS, COOP, HARDWARE, HARDWARE_DUTIES, INTERN,
                       US_CITIES, US_STATES, countries_in, country_code, plain, degree_evidence)
from .member_routes import member_route

GRAD = re.compile(
    r"\b(?:new[- ](?:college[- ])?grad(?:uate)?s?|"
    r"(?:university|college|recent) grad(?:uate)?s?|graduate (?:program(?:me)?|scheme)|"
    r"graduate (?:quant(?:itative)? (?:trader|researcher|developer)|"
    r"(?:software|machine learning|data) engineer|data scientist))\b", re.I,
)
GRAD_ROLE = re.compile(
    r"\bthis (?:role|position|program(?:me)?) is "
    r"(?:(?:specifically )?(?:designed|intended) for|for|open to) "
    r"(?:new|recent|upcoming) (?:college |university )?graduates?\b", re.I,
)
GRAD_COHORT = re.compile(
    r'\b(?:you|candidates?|applicants?|students?|must|expected|graduation date)[^.!?]{0,160}'
    r'\b(?:graduat\w*|complet\w* (?:your|their|an?) (?:undergraduate |bachelor.?s? )?degree)[^.!?]{0,100}\b20\d{2}\b',re.I)
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
SENIOR = re.compile(r'\b(?:senior|sr\.?|staff|principal|director|vice president|head of|lead consultant|manager,? consulting)\b', re.I)
BUSINESS_CATEGORIES = (
    ('product_strategy', re.compile(r'\b(?:product (?:development )?strateg(?:y|ist)|product operations|product development analyst)\b',re.I)),
    ('technology_consulting', re.compile(r'\b(?:(?:technology|technical|digital|IT|implementation|solutions?) consult(?:ant|ing)|technology (?:development )?analyst)\b',re.I)),
    ('strategy_consulting', re.compile(r'\b(?:(?:strategy|strategic|management) consult(?:ant|ing)|strategy analyst|associate consultant)\b',re.I)),
    ('business_analysis', re.compile(r'\b(?:business (?:systems? )?analyst|business analysis|business operations analyst)\b',re.I)),
)


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
    if IB.search(title) and re.search(r"\bsummer (?:analyst|associate)\b", title, re.I):
        intern = intern or bool(re.search(
            r"\b(?:our|this|the) (?:summer )?internship program\b", description, re.I))
    evidence = job.get('evidence') or {}
    intern = intern or evidence.get('feed_internship_context') is True
    if SENIOR.search(title) and not intern:
        return ''
    grad = bool(GRAD.search(labels) or GRAD_ROLE.search(description) or (not intern and GRAD_COHORT.search(description))
                or evidence.get('feed_new_grad_context') is True
                or re.search(r'\b(?:entry[- ]level|campus hire|university hire)\b',title,re.I))
    if grad and re.search(r'\b(?:at least|minimum(?: of)?|requires?)\s+(?:[3-9]|\d{2,})\+?\s+years?\b|\b(?:[3-9]|\d{2,})\+?\s+years?[^.!?]{0,100}\brequired\b',description,re.I):
        return ''
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
    business = next((name for name,pattern in BUSINESS_CATEGORIES if pattern.search(title)), '')
    if business:
        return business
    ordinary=next((name for name, pattern in CATEGORY_PATTERNS if pattern.search(title)), '')
    if ordinary:
        return ordinary
    if re.search(r'\b(?:research|energy|economic|market) analyst\b',title,re.I) and (
        re.search(r'\b(?:economics|finance|business|strategy)\b',title,re.I)
        or re.search(r'\b(?:economic|management|strategy) consulting\b',description,re.I)):
        return 'business_analysis'
    if re.search(r'\b(?:consultant|associate|consulting analyst)\b',title,re.I) and re.search(
        r'\b(?:consulting firm|management consulting|strategy consulting|client service team)\b',description,re.I):
        return 'strategy_consulting'
    return ''


def preview_member_listing(job: dict) -> dict:
    """Return explicit staging labels and a route only if delivery checks pass."""
    decision = classify_member(job)
    us, remote = decision['us_eligible'], decision['remote']
    kind, topic = decision['opportunity_type'], decision['category']
    return dict(us_eligible=us, remote=remote, opportunity_type=kind, category=topic,
                route=member_route(us_eligible=us, remote=remote, opportunity_type=kind,
                                   category=topic, posting_status=job.get("posting_status", ""),
                                   application_status=job.get("application_status", "")) if decision['decision']=='include' else None)


def classify_member(job: dict, _filters=None) -> dict:
    """Classify before link checking; preserve uncertain remote evidence."""
    us, remote = geography(job)
    kind, topic = opportunity_type(job), category(job)
    allowed = us is not False and (us is True or remote)
    degrees, preferred, details = degree_evidence(job,plain(job.get('title')),plain(job.get('description')),job.get('evidence') or {})
    graduate_details=[d for d in details if d['degree'] in {'master','phd'} and d['kind']=='required_or_allowed']
    required_context=any(d['field']!='description' or re.search(
        r'\b(?:required|requires?|must|pursu\w*|enroll\w*|candidate|qualifications?|education|degree|graduate)\b|\bPh\.?D\.?\s+in\b',
        d['value'],re.I) for d in graduate_details)
    graduate_required = bool(required_context and 'bachelor' not in degrees)
    title_degrees, _, _ = degree_evidence({'description':''},plain(job.get('title')),'',{})
    graduate_required |= bool(set(title_degrees)&{'master','phd'} and 'bachelor' not in title_degrees)
    for clause in re.split(r'(?<=[.!?])\s+|\n',str(job.get('description') or '')):
        if re.search(r'\b(?:must|required|requires|minimum)\b',clause,re.I):
            required, _, _ = degree_evidence({'description':clause},'',plain(clause),{})
            graduate_required |= bool(set(required)&{'master','phd'} and 'bachelor' not in required)
    return {"decision": "include" if allowed and kind and topic and not graduate_required else "exclude",
            "category": topic, "opportunity_type": kind,
            "us_eligible": us, "remote": remote,
            "positive_opportunity_evidence": bool(kind),
            "degrees":degrees,"degree_preferences":preferred,"degree_evidence":details,
            "graduate_degree_required":graduate_required}

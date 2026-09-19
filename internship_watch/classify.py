"""Conservative, explainable internship classification; no company-level hardware ban."""
from __future__ import annotations

import html
import re


def plain(value) -> str:
    if isinstance(value, (list, tuple, set)):
        return " ".join(plain(v) for v in value)
    if isinstance(value, dict):
        return " ".join(plain(v) for v in value.values())
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(str(value or "")))).strip()


INTERN = re.compile(r"\bintern(?:ship)?s?\b", re.I)
COOP = re.compile(r"\bco[ -]?op(?:erative education)?\b", re.I)
FULLTIME = re.compile(r"\b(?:full[ -]?time|permanent|regular employee)\b", re.I)
NEWGRAD = re.compile(r"\b(?:new[ -]?grad(?:uate)?s?|graduate (?:program|programme|scheme)|entry[ -]?level)\b", re.I)
HARDWARE = re.compile(r"\b(?:hardware|electrical|electronics|mechanical|firmware|ASIC|RTL|FPGA|VLSI|silicon|physical design|chip design|circuit|PCB|RF engineer|RFIC|mixed[ -]signal|mechatronics?|component engineering|warheads?|munitions?|ordnance|propulsion|EWIS|wiring harness|harness engineer)\b", re.I)
HARDWARE_DUTIES = re.compile(r"\b(?:design|develop|test|verify|verification of|layout of|validate|validation of)\w*(?:\s+\w+){0,6}\s+(?:analog circuits?|digital circuits?|printed circuit boards?|PCB(?: layouts?)?|ASICs?|RTL|FPGAs?|silicon|mechanical components?|electrical systems?)\b", re.I)
PHYSICAL_DUTIES = re.compile(r"\b(?:(?:develop(?:ing)?|improv(?:e|ing))(?:\s+\w+){0,5}\s+semiconductor fabrication|(?:support|perform|conduct)(?:\s+\w+){0,5}\s+hardware (?:testing|debugging)|(?:assemble|modify)(?:\s+\w+){0,4}\s+electronic controls|(?:perform|conduct)(?:\s+\w+){0,4}\s+component (?:evaluations?|qualifications?|failure analysis)|(?:analog|mixed[ -]signal)(?:\s+\w+){0,2}\s+circuit (?:analysis|design|simulation|verification))\b", re.I)
SOFTWARE_DUTIES = re.compile(r"\b(?:develop|build|train|implement|write|optimize)(?:\s+\w+){0,5}\s+(?:software|machine learning models?|AI models?|neural networks?|backend services?|Python (?:software|code)|computer code)\b", re.I)
SOFTWARE = re.compile(r"\b(?:software|back[ -]?end|full[ -]?stack|front[ -]?end|SWE|SDE|programmer|application develop|web develop)\w*\b", re.I)
ML = re.compile(r"\b(?:machine learning|deep learning|artificial intelligence|ML|AI|NLP|computer vision|reinforcement learning|large language models?|LLM|applied scientist)\b", re.I)
CATEGORY_PATTERNS = [
    ("product_management", re.compile(r"\b(?:product manag(?:er|ement)|associate product|technical product manager)\b", re.I)),
    ("quantitative", re.compile(r"\b(?:quant(?:itative)?(?:\s+\w+){0,2}\s+(?:trad(?:er|ing)|research|develop|engineer)|algorithmic trading|systematic trading)\w*\b", re.I)),
    ("ml_ai", ML),
    ("data_science", re.compile(r"\bdata scien(?:ce|tist)\b", re.I)),
    ("data_engineering", re.compile(r"\b(?:data|analytics) engineer(?:ing)?\b", re.I)),
    ("data_analysis", re.compile(r"\b(?:data analy(?:st|sis|tics)|business intelligence)\b", re.I)),
    ("software_engineering", SOFTWARE),
]
COUNTRIES = {
    "US": ["united states", "united states of america", "usa", "u.s.", "us"],
    "CA": ["canada", "canadian"], "GB": ["united kingdom", "uk", "great britain"],
    "DE": ["germany", "deutschland"], "FR": ["france"], "IN": ["india"],
    "AU": ["australia"], "SG": ["singapore"], "NL": ["netherlands"],
    "IE": ["ireland"], "CH": ["switzerland"], "JP": ["japan"],
    "CN": ["china"], "TW": ["taiwan"], "HK": ["hong kong"],
    "IL": ["israel"], "ES": ["spain"], "SE": ["sweden"],
    "PL": ["poland"], "BR": ["brazil"], "MX": ["mexico"],
}
DEGREES = {
    "bachelor": r"\b(?:bachelor(?:'s)?|undergraduate|B\.?S\.?|BSc|B\.?A\.?)\b",
    "master": r"\b(?:master(?:'s)?|M\.?S\.?|MSc|MBA|M\.?A\.?)\b",
    "phd": r"\b(?:Ph\.?D\.?s?|doctorates?|doctoral|postdoctoral)\b",
    "associate": r"\bassociate(?:'s)? degree\b",
}
US_STATES = "AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC".split()
US_STATE_NAMES = "Alabama|Alaska|Arizona|Arkansas|California|Colorado|Connecticut|Delaware|Florida|Georgia|Hawaii|Idaho|Illinois|Indiana|Iowa|Kansas|Kentucky|Louisiana|Maine|Maryland|Massachusetts|Michigan|Minnesota|Mississippi|Missouri|Montana|Nebraska|Nevada|New Hampshire|New Jersey|New Mexico|New York|North Carolina|North Dakota|Ohio|Oklahoma|Oregon|Pennsylvania|Rhode Island|South Carolina|South Dakota|Tennessee|Texas|Utah|Vermont|Virginia|Washington|West Virginia|Wisconsin|Wyoming"
US_CITIES = r"San Francisco|New York City|NYC|Seattle|Boston|San Jose|Mountain View|Palo Alto|Menlo Park|Sunnyvale|Redmond|Bellevue|Los Angeles|San Diego|Austin|Chicago|Pittsburgh|Philadelphia|Atlanta|Dallas|Houston|Raleigh|Durham|Santa Clara|Cupertino|Berkeley|Washington,? D\.?C\.?"
STUDENT_YEARS = {"freshman":r"freshm[ae]n|first[- ]year", "sophomore":r"sophomores?|second[- ]year", "junior":r"juniors?|third[- ]year", "senior":r"seniors?|fourth[- ]year"}


def country_code(value):
    value = plain(value).lower().strip()
    for code, aliases in COUNTRIES.items():
        if value == code.lower() or value in aliases:
            return code
    return value.upper()


def countries_in(text):
    found = set()
    for code, aliases in COUNTRIES.items():
        for alias in aliases:
            # "CA" means California in many boards; never infer Canada from it.
            if re.search(r"(?<!\w)" + re.escape(alias) + r"(?!\w)", text, re.I):
                found.add(code)
                break
    return found


def _seasons(text):
    matches = re.findall(r"\b(summer|fall|autumn|winter|spring)[\s/-]*(20\d{2})?\b", text, re.I)
    return sorted({season.lower().replace("autumn", "fall") + (year or "") for season, year in matches})


def _season_key(value):
    return re.sub(r"[^a-z0-9]", "", str(value).lower().replace("autumn", "fall"))


def degree_evidence(job, title, description, source_evidence):
    """Separate degree requirements from optional/negated degree mentions."""
    required, preferred, evidence = set(), set(), []
    structured = plain(job.get("degrees") or source_evidence.get("degrees"))
    raw = html.unescape(str(job.get("description") or ""))
    raw = re.sub(r"</?(?:p|li|br|div|h[1-6])\b[^>]*>", "\n", raw, flags=re.I)
    raw = re.sub(r"<[^>]+>", " ", raw)
    # Application dropdown options describe the candidate, not allowed degree
    # requirements. EEO disability examples can also contain the abbreviation MS.
    # Retain employer qualifications before recognizable form sections.
    raw = re.split(r"\b(?:Submit your application\s+(?:Resume\s*/\s*CV|Full name)|Apply for this job\s*(?:\*?\s*indicates a required field|Autofill my application|First Name)|Voluntary Self[- ]Identification|Voluntary Self Identification|Disabilities include)\b",raw,maxsplit=1,flags=re.I)[0]
    heading_pattern = re.compile(r"(?im)^\s*(preferred qualifications|nice to have|desired qualifications|required qualifications|minimum qualifications|basic qualifications|requirements|education)\s*:?\s*$")
    headings = [(m.start(),m.group(1).lower()) for m in heading_pattern.finditer(raw)]
    for degree, pattern in DEGREES.items():
        for field, value in [("title",title),("structured_degrees",structured)]:
            if re.search(pattern,value,re.I):
                required.add(degree)
                evidence.append({"degree":degree,"field":field,"kind":"required_or_allowed","value":value[:300]})
        for match in re.finditer(pattern,raw,re.I):
            left = max(raw.rfind(char,0,match.start()) for char in ".!?;\n") + 1
            right_options = [raw.find(char,match.end()) for char in ".!?;\n"]
            right = min((index for index in right_options if index >= 0),default=len(raw))
            prefix, suffix = raw[left:match.start()], raw[match.end():right]
            if re.search(r"\b(?:what degree are you|degree (?:currently )?enrolled|level of education|highest (?:level of )?(?:education|degree))\b",prefix[-250:],re.I):
                continue
            # "but" ends one qualification clause; an alternative joined by
            # "or" remains together (e.g. Master's or PhD preferred).
            suffix = re.split(r"\bbut\b",suffix,1,flags=re.I)[0]
            prior_headings = [heading for index,heading in headings if index < match.start()]
            optional_heading = bool(prior_headings and prior_headings[-1] in {"preferred qualifications","nice to have","desired qualifications"})
            negated = bool(re.search(r"\b(?:no|without|(?:do|does) not (?:need|require)|don['â€™]t (?:need|require)|need not have|not required to have)(?: to have)?(?: an?| any| prior)?\s*$",prefix,re.I)
                           or re.search(r"^\s*(?:degree\s+)?(?:(?:is|are)\s+)?(?:not (?:required|necessary|a requirement)|isn't required)\b",suffix,re.I))
            optional = bool(optional_heading or re.search(r"\b(?:preferred|preferable|desired|optional|a plus|nice.to.have)\b",suffix[:90],re.I)
                            or re.search(r"\b(?:prefer|preferred|desired)(?:\s+\w+){0,5}\s*$",prefix,re.I))
            if re.search(r"\b(?:must|require[sd]?)\b",prefix,re.I) or re.search(r"^\s*(?:degree\s+)?(?:(?:is|are)\s+)?required\b",suffix,re.I):
                optional = False
            kind = "not_required" if negated else "preferred" if optional else "required_or_allowed"
            evidence.append({"degree":degree,"field":"description","kind":kind,"value":plain(raw[left:right])[:450]})
            if kind == "required_or_allowed":
                required.add(degree)
            elif kind == "preferred":
                preferred.add(degree)
    return sorted(required), sorted(preferred), evidence


def classify(job: dict, filters: dict | None = None) -> dict:
    filters = filters or {}
    title = plain(job.get("title"))
    description = plain(job.get("description"))
    employment = plain(job.get("employment_type"))
    source_evidence = job.get("evidence") if isinstance(job.get("evidence"), dict) else {}
    text = title + ". " + description
    evidence, excludes, unknown = [], [], []

    def record(field, value, kind):
        evidence.append({"field": field, "value": plain(value)[:500], "kind": kind})

    coop = bool(COOP.search(title) or COOP.search(employment))
    title_intern = bool(INTERN.search(title))
    structured_intern = bool(INTERN.search(employment))
    program = bool(filters.get("include_research_programs") and (
        re.search(r"\b(?:fellow(?:ship)?s?|residen(?:cy|ts?)|research program(?:me)?s?)\b", title, re.I)
        and (ML.search(text) or re.search(r"\bresearch\b", text, re.I)))
        and not re.search(r"\b(?:manager|director|coordinator|operations|legal|medical|clinical|neurosurgeon|surgeon|physician|nurse)\b", title, re.I))
    description_match = re.search(r"\b(?:this (?:position|role|opportunity) is (?:an? )?(?:\w+\s+){0,3}internship|this internship|as an? (?:\w+\s+){0,5}intern\b|(?:seeking|hiring|looking for) (?:an? )?(?:\w+\s+){0,5}intern\b)", description, re.I)
    negated = re.search(r"\b(?:not an? internship|not (?:an? )?intern(?:ship)? (?:role|position)|permanent (?:role|position)|regular full[ -]?time (?:role|position))\b", text, re.I)
    if title_intern:
        record("title", title, "internship")
    if structured_intern:
        record("employment_type", employment, "internship")
    feed_context = bool(source_evidence.get("feed_internship_context"))
    if feed_context:
        record("source", "Listed in an internship-specific feed; job-level evidence still required", "internship_feed_context")
    if coop:
        record("title/employment_type", title + " / " + employment, "co_op")
    if description_match:
        record("description", description_match.group(0), "internship")
    if program:
        record("title/description", title + " / " + description[:200], "research_program")
    internship = title_intern or structured_intern or bool(description_match) or coop
    if negated:
        record("description/title", negated.group(0), "contradictory_employment")
        if internship or program:
            unknown.append("Conflicting internship and permanent/non-internship evidence")
        else:
            excludes.append("Explicitly not an internship")
    if NEWGRAD.search(title) and not title_intern and not coop:
        excludes.append("New-graduate/entry-level career position")
    if (re.search(r"\bgraduate\b", title, re.I) and employment.casefold() == 'regular'
            and not title_intern and not structured_intern and not coop and not program):
        excludes.append("Graduate career position with structured regular employment")
    if not internship and not program and re.search(r"\b(?:senior|staff|principal|director|head of|vice president|lead)\b", title, re.I):
        excludes.append("Senior career position with no internship/program evidence")
    if not internship and not program:
        if FULLTIME.search(employment) or FULLTIME.search(title):
            excludes.append("Full-time/permanent position with no positive internship evidence")
        else:
            unknown.append("No positive evidence that this position is an internship")
    elif FULLTIME.search(employment):
        record("employment_type", employment, "full_time_hours_do_not_override_internship_or_program")
    if coop and not filters.get("include_coop", True):
        excludes.append("Co-op excluded by configuration")
    if program and re.search(r"\bfull[ -]time employee\b", description, re.I) and not re.search(r"\b(?:\d+\s*(?:months?|weeks?)|fixed[ -]term|temporary|limited duration)\b", description, re.I):
        excludes.append("Full-time employee career pathway without temporary research-program duration")
    employer_key = plain(job.get("employer") or job.get("company")).casefold()
    if filters.get("companies") and employer_key not in {plain(v).casefold() for v in filters["companies"]}:
        excludes.append("Employer outside configured company allowlist")
    if employer_key in {plain(v).casefold() for v in filters.get("exclude_companies", [])}:
        excludes.append("Employer excluded by configuration")

    # Role headings separate duties from employer boilerplate. In particular,
    # a defense company's AI platform does not make a physical test co-op AI.
    role_description = re.split(r"\b(?:about (?:the|this) (?:job|role)|what you['â€™]ll do|your responsibilities|key (?:job )?responsibilities|responsibilities(?=\s*:))\b",
                                description, maxsplit=1, flags=re.I)[-1]
    role_description = re.split(r"\b(?:required qualifications|preferred qualifications|our benefits|protecting yourself from recruitment scams)\b",
                                role_description, maxsplit=1, flags=re.I)[0]
    # Prefer actual duties over an earlier "About the role" introduction.
    role_description = re.split(r"\b(?:what you['’]ll do|key (?:job )?responsibilities|your responsibilities)\b",
                                role_description, maxsplit=1, flags=re.I)[-1]
    category = next((name for name, pattern in CATEGORY_PATTERNS if pattern.search(title)), None)
    if re.search(r"\b(?:program|project) manag(?:er|ement)\b", title, re.I) and category != 'product_management':
        excludes.append("Program/project management is outside the requested product-management family")
    trading_title = bool(re.search(r"\btrad(?:er|ing)\b", title, re.I))
    if category is None and trading_title:
        quantitative_duties = next((sentence for sentence in re.split(r"[.!?;]", description)
            if re.search(r"\b(?:you|your|interns?|responsibilit\w*|projects?|build|develop\w*|analy\w*|research|assist|perform)\b", sentence, re.I)
            and re.search(r"\b(?:quantitative|statistical|algorithmic|automated trading|mathematical|probability|back[ -]?test\w*|(?:trading|predictive) models?|data analysis|analytics dashboards?)\b", sentence, re.I)), None)
        if quantitative_duties:
            category = "quantitative"
            record("description", quantitative_duties, "quantitative_trading_responsibilities")
    unrelated_research = bool(re.search(r"\b(?:user research|UX research|market research|clinical research|medical fellow|legal fellow|neurosurgeon|surgeon|physician|nurse)\b", title, re.I))
    # Use descriptions for generic research/engineering titles, not incidental
    # mentions of colleagues in unrelated roles such as sales/HR internships.
    if category is None and not unrelated_research and re.search(r"\b(?:research|scientist|engineer|developer|technical|student|fellow|resident)\w*\b", title, re.I):
        category = next((name for name, pattern in CATEGORY_PATTERNS if pattern.search(role_description)), None)
        if category == 'product_management':
            # Mentions of collaborating with PMs do not make an engineer a PM.
            category = None
        if category == 'software_engineering' and not SOFTWARE_DUTIES.search(role_description):
            unknown.append("Generic role mentions software without clear software-development duties")
        if category:
            record("description", role_description[:350], "role_category")
    elif category:
        record("title", title, "role_category")
    if unrelated_research and category is None:
        excludes.append("Research discipline outside requested software/data/AI/quant families")
    hardware_title = bool(HARDWARE.search(title))
    hardware_duties = next((m for m in HARDWARE_DUTIES.finditer(description)
                           if not re.search(r"\b(?:software|code|tools?|models?|python)\b", m.group(0), re.I)), None)
    if hardware_duties is None:
        hardware_duties = next((m for m in PHYSICAL_DUTIES.finditer(description)
                               if not re.search(r"\b(?:software|code|tools?|models?|python)\b",m.group(0),re.I)),None)
    explicit_software_duties = SOFTWARE_DUTIES.search(role_description)
    if hardware_title and not SOFTWARE.search(title) and not ML.search(title):
        if explicit_software_duties:
            unknown.append("Hardware-focused title with substantive software/AI duties needs review")
        else:
            excludes.append("Hardware-focused title/responsibilities")
    elif hardware_duties:
        record("description", hardware_duties.group(0), "hardware_responsibilities")
        if SOFTWARE.search(title) or ML.search(title) or explicit_software_duties:
            unknown.append("Mixed software/AI and hardware responsibilities need review")
        else:
            excludes.append("Hardware-focused responsibilities")
    if category is None:
        if trading_title or re.search(r"\b(?:research|scientist|engineer|developer|technical|student)\w*\b", title, re.I):
            unknown.append("Role family unclear; responsibilities needed")
        else:
            excludes.append("Role outside configured internship families")
    configured_categories = filters.get("categories", [])
    aliases = {"software":"software_engineering", "ml":"ml_ai", "ai":"ml_ai", "quant":"quantitative", "product":"product_management"}
    configured_categories = [aliases.get(c, c) for c in configured_categories]
    if configured_categories and category and category not in configured_categories:
        excludes.append("Role category excluded by configuration")

    location = plain(job.get("locations") or job.get("location"))
    country_values = job.get("countries") or job.get("country") or source_evidence.get("country") or []
    if isinstance(country_values, str):
        country_values = [country_values]
    countries = sorted({country_code(c) for c in country_values} | countries_in(location))
    us_location = re.search(r",\s*(?:" + "|".join(US_STATES) + r")(?:\s+\d{5})?(?=[,; /]|$)", location)
    us_named = re.search(r"\b(?:" + US_STATE_NAMES + "|" + US_CITIES + r")\b", location, re.I)
    # City/state inference is recorded, never applied to free-form descriptions.
    # Explicit foreign-country names win over ambiguous city names.
    if not countries and (us_location or us_named):
        countries = ["US"]
        record("location", location, "US_city_or_state_evidence")
    workplace = plain(job.get("workplace_type") or job.get("workplaceType") or source_evidence.get("workplace_type")) + " " + location
    remote = True if re.search(r"\bremote\b", workplace, re.I) else False if re.search(r"\b(?:on[ -]?site|hybrid)\b", workplace, re.I) else None
    if job.get("is_remote") is not None and not re.search(r"\b(?:hybrid|on[ -]?site)\b", workplace, re.I):
        remote = bool(job["is_remote"])
    seasons = _seasons(title + " " + plain(job.get("season")))
    # Only explicit seasonal internship phrases in descriptions count.
    if not seasons:
        seasons = _seasons(" ".join(re.findall(r"\b(?:summer|fall|autumn|winter|spring)\s+20\d{2}(?:\s+\w+){0,3}\s+intern(?:ship)?\b", description, re.I)))
    degrees, preferred_degrees, degree_details = degree_evidence(job,title,description,source_evidence)
    grad_clauses = re.findall(r"\bgraduat\w*[^.!?;]{0,120}", description, re.I)
    graduation_years = set()
    for clause in grad_clauses:
        years = [int(y) for y in re.findall(r"\b20\d{2}\b", clause)]
        if len(years) == 2 and re.search(r"between|through|\bto\b|20\d{2}\s*[-â€“]\s*20\d{2}", clause, re.I) and years[1] - years[0] in range(0, 8):
            graduation_years.update(range(years[0], years[1] + 1))
        else:
            graduation_years.update(years)
    eligibility = {"countries": countries, "remote": remote, "seasons": seasons,
                   "degrees": degrees, "graduation_years": sorted(graduation_years),
                   "degree_preferences":preferred_degrees, "degree_evidence":degree_details,
                   "graduation_evidence": grad_clauses, "co_op": coop,
                   "work_authorization": "unknown"}
    sentences = re.split(r"[.!?;\n]", description)
    year_clauses = [title] + [s for s in sentences if re.search(r"\b(?:must|open to|eligible|eligibility|only|exclusively|seeking|enrolled|currently|students?)\b", s, re.I)]
    year_context = []
    cleaned_year_clauses = []
    rising = {"sophomore":"freshman","junior":"sophomore","senior":"junior"}
    for clause in year_clauses:
        cleaned = re.sub(r"\bsenior(?:[- ]level)?(?:\s+(?:software|data|research|technical|product|engineering))*\s+(?:engineers?|researchers?|scientists?|leaders?|managers?|staff|employees|developers?|executives?|mentors?|traders?|team members?)\b", "experienced professionals", clause, flags=re.I)
        def rising_year(match):
            current = rising[match.group(1).lower()]
            year_context.append({"phrase":match.group(0),"current_student_year":current})
            return current
        cleaned = re.sub(r"\brising\s+(sophomore|junior|senior)s?\b",rising_year,cleaned,flags=re.I)
        cleaned_year_clauses.append(cleaned)
    student_years = [name for name, pattern in STUDENT_YEARS.items() if any(re.search(r"\b(?:" + pattern + r")\b", clause, re.I) for clause in cleaned_year_clauses)]
    eligibility["student_years"] = student_years
    eligibility["student_year_context"] = year_context
    eligibility["student_year_evidence"] = [c.strip()[:500] for c in year_clauses if any(re.search(r"\b(?:" + p + r")\b", c, re.I) for p in STUDENT_YEARS.values())]
    authorization = next((s for s in sentences if re.search(r"visa sponsorship|work authori[sz]ation|authori[sz]ed to work|citizenship", s, re.I)), None)
    if authorization:
        eligibility["work_authorization"] = authorization.strip()
    eligibility["sponsorship"] = "not_available" if re.search(r"(?:no|not|unable to|cannot)[^.!?]{0,40}(?:sponsor|sponsorship)", description, re.I) else "unknown"
    # Work authorization and no need for sponsorship do not establish citizenship
    # or an active clearance. Match affirmative requirements, not EEO boilerplate.
    authorization_text = re.sub(r"\bU\.?S\.(?=\s|$)", "US", description, flags=re.I)
    authorization_clauses = re.split(r"[.!?;]", authorization_text)
    citizenship_requirements = []
    for clause in authorization_clauses:
        if not re.search(r"\bcitizen(?:ship|s)?\b", clause, re.I):
            continue
        for code, aliases in COUNTRIES.items():
            country_pattern = "(?:" + "|".join(re.escape(v) for v in [code] + aliases if v != "u.s.") + ")"
            citizen_pattern = country_pattern + r"\s+citizen(?:ship|s)?"
            required = re.search(r"\b(?:must|required to|need to|shall)\s+(?:be|hold|have|possess)\s+(?:an?\s+)?" + citizen_pattern + r"\b|\b" + citizen_pattern + r"(?:\s+or\s+permanent residents?)?\s*(?:\(?\s*(?:is |are )?required|only\b)|\b(?:only|restricted to|limited to)\s+" + citizen_pattern + r"\b", clause, re.I)
            if required:
                alternative = bool(re.search(r"\bor\b[^;]{0,45}\b(?:permanent residents?|green card|nationals?)\b", clause, re.I))
                citizenship_requirements.append({"country":code,"evidence":clause.strip()[:600],"permanent_residence_alternative":alternative})
    eligibility["citizenship_requirements"] = citizenship_requirements
    supplied_citizenships = {country_code(c) for c in filters.get("citizenships", [])}
    for requirement in citizenship_requirements:
        record("description", requirement["evidence"], "required_citizenship")
        if requirement["country"] not in supplied_citizenships:
            if supplied_citizenships and not requirement["permanent_residence_alternative"]:
                excludes.append("Required citizenship does not match configured citizenships")
            else:
                unknown.append("Required citizenship/permanent residency is not established by work authorization")
    required_clearance = []
    for clause in authorization_clauses:
        if not re.search(r"\b(?:must|requir\w*|mandatory|qualification\w*)\b", clause, re.I) or not re.search(r"\bclearance\b", clause, re.I):
            continue
        can_obtain = bool(re.search(r"\b(?:ability|able|eligible|eligibility)\s+(?:to\s+)?(?:obtain|receive|qualify)|\bobtain(?:ing)?\s+(?:an?\s+)?(?:security\s+)?clearance", clause, re.I))
        active = bool(re.search(r"\b(?:active|current|existing|maintain|hold|possess)\b", clause, re.I))
        if active or can_obtain:
            required_clearance.append({"evidence":clause.strip()[:600],"active_required":active and not can_obtain,"ability_to_obtain":can_obtain})
    eligibility["security_clearance_requirements"] = required_clearance
    for requirement in required_clearance:
        record("description", requirement["evidence"], "required_security_clearance")
        if filters.get("has_security_clearance") is not True:
            if requirement["active_required"] and filters.get("has_security_clearance") is False:
                excludes.append("Active security clearance required but not held")
            else:
                unknown.append("Required security-clearance eligibility has not been established")

    def match_filter(key, available, desired, allow_unstated=False):
        if not desired:
            return
        if not available and not allow_unstated:
            unknown.append(f"Unknown {key}; configured filter cannot be verified")
        elif not available:
            record("eligibility", key + " is unstated", "unverified_eligibility_allowed_by_configuration")
        elif not set(available).intersection(desired):
            excludes.append(f"{key.capitalize()} does not match configured filter")

    match_filter("geography", countries, [country_code(c) for c in filters.get("countries", [])])
    allow_unstated = filters.get("allow_unstated_eligibility", False)
    title_degrees = [degree for degree, pattern in DEGREES.items() if re.search(pattern,title,re.I)]
    if title_degrees:
        match_filter("explicit title degree eligibility", title_degrees, [str(d).lower() for d in filters.get("degrees", [])])
    match_filter("degree eligibility", degrees, [str(d).lower() for d in filters.get("degrees", [])], allow_unstated)
    match_filter("graduation year", graduation_years, [int(y) for y in filters.get("graduation_years", [])], allow_unstated)
    match_filter("student year", student_years, [str(y).lower() for y in filters.get("student_years", [])], allow_unstated)
    if filters.get("requires_sponsorship") is True and eligibility["sponsorship"] == "not_available":
        excludes.append("Employer does not offer required sponsorship")
    wanted_seasons = [_season_key(s) for s in filters.get("seasons", [])]
    if wanted_seasons:
        if not seasons:
            unknown.append("Unknown season; configured filter cannot be verified")
        elif not any(a == b or (not re.search(r"\d", b) and a.startswith(b)) for a in seasons for b in wanted_seasons):
            if any(not re.search(r"\d", a) for a in seasons):
                unknown.append("Season year is unknown")
            else:
                excludes.append("Season does not match configured filter")
    remote_policy = filters.get("remote_policy", "any")
    if remote_policy in {"only", "exclude"}:
        if remote is None:
            unknown.append("Remote status is unknown")
        elif remote != (remote_policy == "only"):
            excludes.append("Remote policy does not match configured filter")
    if remote and filters.get("remote_eligible_countries"):
        # Remote does not mean worldwide work authorization; a country stated
        # on the listing is required. Never infer eligibility from employer.
        match_filter("remote geography", countries, [country_code(c) for c in filters["remote_eligible_countries"]])
    decision = "exclude" if excludes else "ambiguous" if unknown else "include"
    return {"decision": decision, "category": category, "evidence": evidence,
            "positive_opportunity_evidence": bool(internship or program or feed_context),
            "opportunity_kind": "co_op" if coop else "internship" if internship else "research_program" if program else "unknown",
            "reasons": excludes + unknown, "eligibility": eligibility}

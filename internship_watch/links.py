"""Check job identity and content at both destinations, never equating 200 with open."""
from __future__ import annotations

from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
import ipaddress
import json
import re
import time
from urllib.parse import parse_qs, quote, unquote, urljoin, urlsplit

import requests

from .classify import plain
from .http import WorkBudgetExhausted
from .google_source import GoogleDetailError, google_job_id, google_title_matches, parse_google_detail

VALIDATOR_VERSION = 12


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


def title_compatible(expected, actual, *, same_identifier=False):
    """Allow word variants/additions only after independently binding the job ID."""
    expected, actual = normalized(expected), normalized(actual)
    if expected and expected in actual:
        return True
    if not same_identifier:
        return False
    aliases = {'engineering':'engineer', 'internship':'intern', 'internships':'intern', 'interns':'intern'}
    wanted = [aliases.get(word,word) for word in expected.split()]
    observed = [aliases.get(word,word) for word in actual.split()]
    if len(wanted) < 3:
        return False
    # Ordered token subsequence is deliberately narrower than fuzzy matching.
    iterator = iter(observed)
    return all(any(word == candidate for candidate in iterator) for word in wanted)


def employer_compatible(expected, actual, url):
    import unicodedata
    expected = unicodedata.normalize('NFKD',str(expected or '')).encode('ascii','ignore').decode()
    actual = unicodedata.normalize('NFKD',str(actual or '')).encode('ascii','ignore').decode()
    expected, actual = normalized(expected), normalized(actual)
    if not actual or not expected or expected in actual or actual in expected:
        return True
    host = urlsplit(url).hostname or ''
    # Observed legal hiring entities, bound to the reviewed employer tenant.
    legal_aliases = {
        ('cmegroup.wd1.myworkdayjobs.com','cme group'): {'cme chicago mercantile exchange inc'},
        ('spgi.wd5.myworkdayjobs.com','s p global'): {'1115 kensho technologies llc'},
        ('pimco.wd1.myworkdayjobs.com','pimco'): {'0200 pacific investment mgt co llc'},
        ('bmo.wd3.myworkdayjobs.com','bmo capital markets'): {'bank of montreal'},
    }
    if actual in legal_aliases.get((host,expected),set()):
        return True
    brand = expected.split()[0]
    # Workday uses legal subsidiaries in schema. Require the distinctive employer
    # brand in both the legal name AND the independently bound tenant hostname.
    return bool(len(brand) >= 3 and brand not in {'the','bank','united','general','global'}
                and host.endswith('.myworkdayjobs.com') and host.split('.')[0] == brand
                and brand in actual.split())


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
    if parsed.hostname in {"jobs.ashbyhq.com", "jobs.lever.co", "jobs.eu.lever.co", "job-boards.greenhouse.io", "boards.greenhouse.io", "job-boards.eu.greenhouse.io", "boards.eu.greenhouse.io"} and len(parts) <= 1:
        return True
    generic = {"jobs", "careers", "career", "search", "opportunities", "openings", "en", "en-us", "en-gb", "us", "job-search", "jobsearch", "results"}
    return not parts or all(p in generic for p in parts)


def meaningful_description(text):
    text = plain(text).replace("\u2019", "'")
    return len(text) >= 120 and len(text.split()) >= 18 and bool(re.search(
        r"\b(?:responsibilit|qualification|requirements?|you will|you'll|your (?:role|work|duties)|about (?:the )?(?:role|job)|(?:the|this) (?:role|position|internship)|role details|interns will (?:work|contribute|develop|be mentored)|interns (?:interact|sit|gain|participate|design|develop|build)|as an? (?:\w+\s+){0,5}intern|as (?:\w+\s+){0,4}interns|duties)\w*\b", text, re.I))


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
        if isinstance(exc, WorkBudgetExhausted):
            check['evidence'].append('work_budget_exhausted')
            return check
        response = getattr(exc, "response", None)
        if response is None:
            check["evidence"].append("access_failure:" + type(exc).__name__)
            if isinstance(exc, ValueError):
                check['failure_detail'] = str(exc)[:200]
            if type(exc).__name__ == 'AccessRestricted':
                if getattr(exc, 'source_policy_reason', None):
                    check['evidence'].append('configured_source_policy_restriction')
                    check['failure_detail'] = f"{exc.restricted_host}: {exc.source_policy_reason}"[:200]
                elif 'cooling down' in str(exc):
                    check['evidence'].append('host_cooldown_active')
                else:
                    parsed=urlsplit(url)
                    policy=getattr(client,'_robots',{}).get(parsed.scheme+'://'+parsed.netloc)
                    if policy:
                        check['evidence'].append('robots_policy_unavailable_or_denied_http' if policy[1] is False else 'robots_disallowed')
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
    if LOGIN.search(text) or (kind == 'application' and re.search(r'/(?:login|sign-in|signin)(?:/|$)',urlsplit(check['final_url']).path,re.I)):
        check["evidence"].append("login_required")
        return check
    expired = EXPIRED.search(text)
    if expired:
        check.update(status="closed", evidence=["explicit_expiry:" + expired.group(0)])
        return check
    if google_job_id(url):
        # The page also renders unrelated search results. Do not let their
        # headings or descriptions validate a missing/changed detail record.
        if google_job_id(check["final_url"]) != google_job_id(url):
            check["evidence"].append("google_detail_redirect_identity_mismatch")
            return check
        try:
            detail = parse_google_detail(response.text, check["final_url"])
        except GoogleDetailError as exc:
            check["evidence"].append("google_public_detail:" + str(exc))
            return check
        if normalized(job.get("employer") or job.get("company")) != "google":
            check["evidence"].append("google_public_detail:expected_employer_mismatch")
            return check
        if (not google_title_matches(job.get("title"), detail["title"])
                or not any(normalized(detail["title"]) in normalized(heading) for heading in page.headings)):
            check["evidence"].append("google_public_detail:title_mismatch")
            return check
        if not meaningful_description(detail["description"]):
            check["evidence"].append("google_public_detail:description_insufficient")
            return check
        check.update(title=detail["title"], posting_url=detail["posting_url"],
                     application_url=detail["application_url"],
                     application_links=[{"url":detail["application_url"],"text":"Apply"}],
                     evidence=["fresh_employer_public_detail", "exact_google_job_identifier_employer_and_title_verified",
                               "expected_job_identity_verified", "meaningful_description_present"])
        if kind == "description":
            check.update(status="open", description=detail["description"][:50_000])
            check["google_eligibility"] = {"kind":"google_public_detail", "job_id":detail["id"],
                                          "title":detail["title"], "degrees":detail["degrees"],
                                          "minimum_qualifications":detail["minimum_qualifications"],
                                          "posting_url":detail["posting_url"]}
        else:
            check["evidence"].append("application_destination_not_verified")
        return check
    postings = list(page.postings())
    expected = normalized(job.get("title"))
    employer = normalized(job.get("employer") or job.get("company"))
    expected_ids = url_ids(url)
    destination_ids = url_ids(check["final_url"])
    same_id = bool(expected_ids.intersection(destination_ids))
    title_match = any(title_compatible(expected,heading,same_identifier=same_id) for heading in page.headings)
    body_title_match = bool(expected and expected in normalized(text))
    employer_match = bool(employer and employer in normalized(text))
    description = ""
    structured_match = None
    for posting in postings:
        candidate_title = normalized(posting.get("title"))
        if title_compatible(expected,candidate_title,same_identifier=same_id):
            organization = posting.get("hiringOrganization", {})
            org_name = normalized(organization.get("name")) if isinstance(organization, dict) else normalized(organization)
            if not employer_compatible(job.get('employer') or job.get('company'),
                    organization.get('name') if isinstance(organization,dict) else organization,check['final_url']):
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
        if not plain(' '.join(page.content)) and '<script' in response.text.lower():
            check['evidence'].append('javascript_shell_or_client_rendered_content')
        return check
    check["evidence"].append("expected_job_identity_verified")
    if not description:
        # Navigation, footer links, and the expected title cannot substitute for
        # a job description. Prefer an article/main or explicit description div.
        description = plain(" ".join(page.semantic or page.content))
    if (kind=='description' and urlsplit(check['final_url']).hostname=='bankcampuscareers.tal.net'
            and employer_compatible(job.get('employer'),'Bank of America',check['final_url'])):
        # Tal.net wraps the role detail in a form; the generic parser correctly
        # excludes forms, but this labelled employer description is not a CV form.
        posting_id=re.search(r'/opp/(\d+)(?:-|/)',urlsplit(check['final_url']).path)
        if (posting_id and re.search(r'\bProgram ID\s+'+posting_id[1]+r'\b',text)
                and title_match and 'Program description ' in text):
            description=text.split('Program description ',1)[1].split('View Cookie / Data Protection Notice',1)[0]
            check['evidence'].append('exact_talnet_program_description_field')
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
        if len(description)<120 and '<script' in response.text.lower():
            check['evidence'].append('javascript_shell_or_client_rendered_content')
    return check


def provider_spec(url, job=None):
    """Recognize documented public ATS namespaces; never guess an employer slug."""
    if not valid_url(url):
        return None
    from .employer_validation import spec_for
    employer_spec = spec_for(url)
    if employer_spec:
        return employer_spec
    parsed=urlsplit(url); host=parsed.hostname.lower(); parts=parsed.path.strip('/').split('/')
    if host in {'jobs.lever.co','jobs.eu.lever.co','jobs.ashbyhq.com'} and len(parts)>=2:
        board,identity=parts[:2]
        if board not in {'.','..'} and re.fullmatch(r'[A-Za-z0-9_.-]+',board) and re.fullmatch(r'[0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}',identity):
            provider='ashby' if host=='jobs.ashbyhq.com' else 'lever'
            api=(f'https://api.ashbyhq.com/posting-api/job-board/{quote(board,safe="")}' if provider=='ashby'
                 else f'https://{"api.eu.lever.co" if host=="jobs.eu.lever.co" else "api.lever.co"}/v0/postings/{quote(board,safe="")}/{identity}')
            return {'provider':provider,'board':board,'id':identity,'canonical':f'https://{host}/{board}/{identity}','api':api}
    board=identity=None
    if host in {'job-boards.greenhouse.io','boards.greenhouse.io','job-boards.eu.greenhouse.io','boards.eu.greenhouse.io'}:
        if len(parts)>=3 and parts[1]=='jobs' and parts[2].isdigit():
            board,identity=parts[0],parts[2]
        elif parts==['embed','job_app']:
            query=parse_qs(parsed.query);board=(query.get('for') or [None])[0];identity=(query.get('token') or [None])[0]
    elif job and job.get('evidence',{}).get('provider')=='greenhouse':
        match=re.fullmatch(r'gh-(.+)-(\d+)',str(job.get('source_id','')))
        if match and match.group(2) in url_ids(url):
            board,identity=match.groups()
    if board and identity and board not in {'.','..'} and re.fullmatch(r'[A-Za-z0-9_.-]+',board) and identity.isdigit():
        return {'provider':'greenhouse','board':board,'id':identity,
                'canonical':f'https://{"job-boards.eu.greenhouse.io" if host.endswith(".eu.greenhouse.io") else "job-boards.greenhouse.io"}/{board}/jobs/{identity}',
                'api':f'https://boards-api.greenhouse.io/v1/boards/{quote(board,safe="")}/jobs/{identity}'}
    return None


def _prune_posting_cache(cache, maximum=64):
    """A long-lived worker must not retain every full ATS response forever."""
    expired=[key for key,entry in cache.items() if time.monotonic()-entry[0]>=300]
    for key in expired:
        body=cache.pop(key)[1]
        close=getattr(body,'close',None)
        if callable(close):close()
    while len(cache)>maximum:
        body=cache.pop(next(iter(cache)))[1]
        close=getattr(body,'close',None)
        if callable(close):close()


def _api_posting(job, spec, client):
    """Fresh documented ATS data can prove a posting, never application access."""
    if spec['provider'] in {'smartrecruiters', 'eightfold', 'snap', 'workday', 'ubs'}:
        from .employer_validation import check_posting
        return check_posting(job, spec, client)
    check={'kind':'posting_api','requested_url':spec['api'],'final_url':None,'status':'unverified','evidence':[]}
    try:
        cached=getattr(client,'_posting_api_cache',None)
        if cached is None:
            cached={};setattr(client,'_posting_api_cache',cached)
        _prune_posting_cache(cached)
        entry=cached.get(spec['api'])
        if not entry or time.monotonic()-entry[0]>=300:
            response=client.get(spec['api'],allow_redirects=True,respect_robots=False,raise_for_status=False)
            entry=(time.monotonic(),response,datetime.now(timezone.utc).isoformat())
            cached[spec['api']]=entry
            _prune_posting_cache(cached)
        _,response,fetched_at=entry
        check.update(http_status=response.status_code,final_url=response.url,fetched_at=fetched_at)
        if response.status_code!=200:
            check['evidence'].append('public_api_unavailable:'+str(response.status_code));return check
        if urlsplit(response.url or spec['api']).netloc != urlsplit(spec['api']).netloc:
            check['evidence'].append('public_api_unexpected_redirect');return check
        data=response.json()
    except (requests.RequestException,OSError,ValueError,TimeoutError) as exc:
        check['evidence'].append('work_budget_exhausted' if isinstance(exc, WorkBudgetExhausted)
                                 else 'public_api_failure:'+type(exc).__name__);return check
    if not isinstance(data,dict):
        check['evidence'].append('public_api_invalid_schema');return check
    if spec['provider']=='ashby':
        items=data.get('jobs')
        if not isinstance(items,list) or any(data.get(k) for k in ('next','nextPage','hasMore','nextCursor')) or data.get('apiVersion','1')!='1':
            check['evidence'].append('public_api_invalid_or_incomplete_schema');return check
        items=[item for item in items if isinstance(item,dict) and provider_spec(item.get('jobUrl')) and
               provider_spec(item['jobUrl'])['board']==spec['board'] and provider_spec(item['jobUrl'])['id']==spec['id']]
        if len(items)!=1:
            check['evidence'].append('exact_job_absent_from_public_api');return check
        item=items[0];title=item.get('title');posting_url=item.get('jobUrl');application=item.get('applyUrl')
        description=plain(item.get('descriptionHtml') or item.get('descriptionPlain'))
    elif spec['provider']=='lever':
        item=data;title=item.get('text');posting_url=item.get('hostedUrl');application=item.get('applyUrl')
        description=plain((item.get('descriptionPlain') or item.get('description') or '')+' '+
                          ' '.join(str(part.get('text',''))+' '+str(part.get('content','')) for part in item.get('lists',[]) if isinstance(part,dict))+' '+
                          (item.get('additionalPlain') or item.get('additional') or ''))
    else:
        item=data;title=item.get('title');posting_url=item.get('absolute_url');application=posting_url
        description=plain(unescape(str(item.get('content') or '')))
        if not employer_compatible(job.get('employer'),item.get('company_name'),posting_url or spec['canonical']):
            check['evidence'].append('public_api_employer_mismatch');return check
    if spec['provider']!='ashby' and str(item.get('id'))!=spec['id']:
        check['evidence'].append('public_api_identifier_mismatch');return check
    returned=provider_spec(posting_url)
    if not valid_url(posting_url) or not url_ids(posting_url).intersection({normalized(spec['id'])}) or (returned and (returned['provider'],returned['board'],returned['id'])!=(spec['provider'],spec['board'],spec['id'])):
        check['evidence'].append('public_api_canonical_url_mismatch');return check
    if spec['provider']!='greenhouse' and not returned:
        check['evidence'].append('public_api_canonical_url_mismatch');return check
    employment=[item.get('employmentType'),(item.get('categories') or {}).get('commitment')]
    employment += [field.get('value') for field in item.get('metadata') or [] if isinstance(field,dict) and
                   re.search(r'employment|commitment|job.?type',str(field.get('name','')),re.I)]
    api_internship=bool(re.search(r'\b(?:intern(?:ship)?|co[ -]?op)\b',plain(employment),re.I))
    wanted_role=re.sub(r'\bintern(?:ship)?s?\b','',normalized(job.get('title'))).strip()
    title_verified=title_compatible(job.get('title'),title,same_identifier=True)
    if not title_verified and api_internship and len(wanted_role.split())>=2:
        title_verified=title_compatible(wanted_role,title,same_identifier=True)
    if not title_verified:
        check['evidence'].append('public_api_title_mismatch');return check
    if not meaningful_description(description):
        check['evidence'].append('public_api_description_insufficient');return check
    check.update(status='open',posting_url=posting_url,description=description[:50_000],title=title,
                 evidence=['fresh_documented_public_posting_api','exact_board_job_identifier_and_title_verified','meaningful_description_present'])
    if api_internship:
        check['evidence'].append('fresh_api_structured_internship_employment')
        check['employment_type_evidence']=employment
    if valid_url(application) and url_ids(application).intersection({normalized(spec['id'])}):
        check['application_url']=application
    return check


def validate_job(job: dict, client) -> dict:
    """Client must enforce timeout/retries/public DNS and robots restrictions.

    A shared URL is fetched once but assessed for both purposes. A blocked or
    missing destination is unverified; closure requires affirmative evidence.
    """
    description_url = job.get("description_url") or job.get("url")
    application_url = job.get("application_url") or description_url
    cache = {}
    spec=provider_spec(description_url,job)
    posting_url=description_url
    if spec and (urlsplit(description_url).path.rstrip('/').endswith(('/apply','/application','/embed/job_app'))):
        posting_url=spec['canonical']
    posting_check=_check(job,posting_url,'description',client,cache)
    if posting_url!=description_url:
        posting_check['evidence'].append('recognized_ats_application_url_replaced_for_description')
    checks=[posting_check]
    api_check=None
    if spec and (posting_check['status']=='unverified' or
                 'http_not_found_or_gone' in posting_check['evidence']):
        api_check=_api_posting(job,spec,client)
        checks.append(api_check)
        if api_check['status'] in {'open', 'closed'}:
            if posting_check['status']=='closed' and api_check['status']=='open':
                api_check['evidence'].append('employer_api_active_but_posting_page_unavailable')
            posting_check=api_check
    visited = set()
    current = (posting_check.get('application_url') if posting_check['status']=='open' else None) or application_url
    for _ in range(4):
        visited.add(current)
        application_check = _check(job, current, "application", client, cache)
        checks.append(application_check)
        if current!=application_url and api_check and current==api_check.get('application_url'):
            application_check['evidence'].append('application_destination_from_public_posting_api')
        elif current!=application_url and current==posting_check.get('application_url'):
            application_check['evidence'].append('application_destination_from_employer_public_page')
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
    if (job.get('evidence') or {}).get('application_identity_conflict'):
        checks[-1]['status']='unverified'
        checks[-1]['evidence'].append('employer_posting_and_application_requisition_conflict')
    statuses = [posting_check['status'], checks[-1]["status"]]
    status = "closed" if "closed" in statuses else "open" if all(s == "open" for s in statuses) else "unverified"
    result = {"status": status, "posting_status":statuses[0],"application_status":statuses[1],
              "description_url": description_url,
              "application_url": application_url,
              "final_description_url": posting_check.get('posting_url') or posting_check["final_url"],
              "final_application_url": checks[-1]["final_url"],
              "checked_at": datetime.now(timezone.utc).isoformat(), "validator_version": VALIDATOR_VERSION, "checks": checks}
    if posting_check.get("description") and posting_check["status"] == "open":
        result["description"] = posting_check["description"]
        if posting_check.get("google_eligibility"):
            result["google_eligibility"] = dict(posting_check["google_eligibility"], checked_at=result["checked_at"])
    return result

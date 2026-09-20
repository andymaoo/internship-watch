"""UBS's public student BrassRing search; no candidate/account operations."""
import re
from html.parser import HTMLParser
from urllib.parse import urlsplit, parse_qs, urlencode

from .sources import SourceError, _base, _description

BASE = 'https://jobs.ubs.com'
LANDING = BASE + '/TGnewUI/Search/home/HomeWithPreLoad?partnerid=25008&siteid=5131&PageType=searchResults&SearchType=linkquery&LinkID=15232'
API = BASE + '/TgNewUI/Search/Ajax/'


def identity(url):
    try:
        parsed = urlsplit(url)
        q = {k.lower(): v for k, v in parse_qs(parsed.query).items()}
        if (parsed.scheme != 'https' or parsed.hostname != 'jobs.ubs.com'
                or parsed.username or parsed.password
                or parsed.path.lower() != '/tgnewui/search/home/homewithpreload'
                or q.get('partnerid') != ['25008'] or q.get('pagetype') != ['JobDetails']):
            return None
        site, job = q.get('siteid', []), q.get('jobid', [])
        if len(site) == len(job) == 1 and site[0].isdigit() and job[0].isdigit():
            return site[0], job[0]
    except (ValueError, TypeError):
        pass
    return None


def canonical(site, job):
    return BASE + '/TGnewUI/Search/home/HomeWithPreLoad?' + urlencode(
        dict(partnerid='25008', siteid=site, PageType='JobDetails', jobid=job))


class _Inputs(HTMLParser):
    def __init__(self, text):
        super().__init__(); self.fields = {}; self.feed(text)

    def handle_starttag(self, tag, attrs):
        item = dict(attrs)
        if tag == 'input':
            for key in (item.get('id'), item.get('name')):
                if key:
                    self.fields[key] = item.get('value', '')


class PublicSearch:
    def __init__(self, client):
        self.client = client
        response = client.get(LANDING, respect_robots=True)
        response.raise_for_status()
        self.fields = _Inputs(response.text).fields
        if (self.fields.get('partnerId') != '25008' or self.fields.get('siteId') != '5131'
                or not self.fields.get('CookieValue') or not self.fields.get('__RequestVerificationToken')):
            raise SourceError('UBS public search session/schema unavailable')

    def post(self, endpoint, payload):
        # Anonymous session/CSRF values stay in memory, never in job evidence.
        response = self.client.post(API + endpoint, json=payload,
            headers={'RFT': self.fields['__RequestVerificationToken']},
            respect_robots=True, retry_post=True)
        response.raise_for_status()
        if urlsplit(response.url).hostname != 'jobs.ubs.com':
            raise SourceError('UBS public search redirected away from employer')
        data = response.json()
        if not isinstance(data, dict):
            raise SourceError('UBS public search schema changed')
        return data

    def rows(self):
        f = self.fields
        data = self.post('MatchedJobs', dict(PartnerId='25008', SiteId='5131',
            Keyword='', Location='', KeywordCustomSolrFields='', LocationCustomSolrFields='',
            FacetFilterFields=None, TurnOffHttps=False, Latitude=0, Longitude=0,
            PowerSearchOptions={'PowerSearchOption': []}, encryptedsessionvalue=f['CookieValue']))
        total = data.get('JobsCount')
        if (not isinstance(total, int) or isinstance(total, bool) or not 0 <= total <= 2000
                or not any(x.get('Name') == 'LastUpdated' for x in data.get('SortFields', []))):
            raise SourceError('UBS public count/order changed')
        # Explicitly sort page ONE too: the default first page uses another order.
        seen = set(); rows = []
        for number in range(1, 41):
            data = self.post('ProcessSortAndShowMoreJobs', dict(partnerId='25008', siteId='5131',
                keyword='', location='', keywordCustomSolrFields='', locationCustomSolrFields='',
                linkId=f.get('linkId', ''), Latitude=0, Longitude=0,
                facetfilterfields={'Facet': []}, powersearchoptions={'PowerSearchOption': []},
                SortType='LastUpdated', pageNumber=number, encryptedSessionValue=f['CookieValue']))
            batch = (data.get('Jobs') or {}).get('Job')
            if data.get('JobsCount') != total or not isinstance(batch, list):
                raise SourceError('UBS search changed during pagination')
            for row in batch:
                fields = _questions(row.get('Questions'), 'QuestionName', 'Value')
                key = identity(row.get('Link'))
                if key != (fields.get('siteid'), fields.get('reqid')) or not key or key in seen:
                    raise SourceError('UBS search repeated or mismatched posting identity')
                seen.add(key); rows.append((row, fields))
            if len(rows) == total:
                return rows
            if not batch or len(rows) > total:
                break
        raise SourceError('UBS incomplete search pagination')

    def detail(self, site, job):
        data = self.post('JobDetails', dict(partnerId='25008', siteId='5131', jobid=job,
            configMode=self.fields.get('configMode', ''), jobSiteId=site, turnOffHttps=False))
        item = (data.get('ServiceResponse') or {}).get('Jobdetails')
        if not isinstance(item, dict):
            raise SourceError('UBS exact public detail unavailable')
        fields = _questions(item.get('JobDetailQuestions'), 'VerityZone', 'AnswerValue')
        if (identity(item.get('Link')) != (site, job)
                or (fields.get('siteid'), fields.get('reqid')) != (site, job)
                or item.get('isSocialReferralJobRestricted') is not False
                or not isinstance(item.get('isActive'), bool)
                or _description(item.get('Title')) != _description(fields.get('jobtitle'))):
            raise SourceError('UBS public detail identity/state changed')
        return item, fields


def _questions(items, key, value):
    if not isinstance(items, list):
        raise SourceError('UBS public fields missing')
    result = {}
    for item in items:
        name = item.get(key)
        if not name or name in result:
            raise SourceError('UBS duplicate/missing public field name')
        result[name] = str(item.get(value) or '')
    return result


def description(fields):
    # Exclude generic company, diversity and application-form boilerplate.
    return '\n'.join(_description(fields.get(k)) for k in
        ('jobdescription', 'formtext58', 'formtext59', 'formtext63'))


def ubs(source, client):
    if source.get('country_scope') not in (None, ['US']):
        raise SourceError('Unreviewed UBS country scope')
    search = PublicSearch(client); rows = search.rows(); jobs = []
    for row, fields in rows:
        if row.get('isSocialReferralJobRestricted') is not False:
            continue
        if source.get('country_scope') == ['US'] and not fields.get('formtext23', '').startswith('United States'):
            continue
        site, job = identity(row['Link']); detail = False
        if re.search(r'\b(?:intern(?:ship)?|summer|research|fellow|residen(?:t|cy))\b', fields.get('jobtitle', ''), re.I):
            item, fields = search.detail(site, job); detail = True
            if item['isActive'] is False:
                continue
        jobs.append(_base(source, 'ubs', site+'-'+job, _description(fields['jobtitle']), canonical(site, job),
            description=description(fields), locations=[', '.join(filter(None,
                (fields.get('formtext2'), fields.get('formtext23'))))],
            evidence=dict(provider='ubs', provider_job_id=job, board=site,
                employer_requisition=fields.get('autoreq'), source_updated_at=fields.get('lastupdated'),
                description_kind='employer_public_detail' if detail else 'employer_search_summary',
                search_total=len(rows), scope='student_and_graduate_directory')))
    return jobs

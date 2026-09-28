"""Public Société Générale careers search and exact employer job schema."""
import json
import re
from datetime import datetime
from urllib.parse import urlsplit, parse_qs

from .sources import SourceError, _base, _description

BASE = 'https://careers.societegenerale.com'
PROFILE = 'https://api.socgen.com/business-support/it-for-it-support/cognitive-service-knowledge/api/v1/search-profile'


def identity(url):
    try:
        parsed = urlsplit(url)
        if parsed.scheme != 'https' or parsed.username or parsed.password:
            return None
        if parsed.hostname == 'careers.societegenerale.com':
            match = re.fullmatch(r'/en/job-offers/[^/]+-([A-Z0-9]{8})-en', parsed.path)
            if match:
                return match[1]
        if parsed.hostname == 'socgen.taleo.net' and parsed.path == '/careersection/sgcareers/jobapply.ftl':
            job = parse_qs(parsed.query).get('job', [])
            if len(job) == 1 and re.fullmatch(r'[A-Z0-9]{8}', job[0]):
                return job[0]
    except (ValueError, TypeError):
        pass
    return None


def socgen(source, client):
    from .links import Page, title_compatible, employer_compatible
    if source.get('country_scope') != ['US']:
        raise SourceError('Unreviewed Societe Generale country scope')
    response = client.get(BASE+'/en', respect_robots=True); response.raise_for_status()
    match = re.search(r'<script[^>]*data-drupal-selector="drupal-settings-json"[^>]*>(.*?)</script>', response.text, re.S)
    if not match:
        raise SourceError('Societe Generale public settings unavailable')
    settings = json.loads(match[1])
    if (settings.get('quantum', {}).get('base_url') != PROFILE.rsplit('/', 1)[0]
            or not settings.get('csrfToken')):
        raise SourceError('Societe Generale public search configuration changed')
    # Exactly the public website's anonymous search-token flow. No login,
    # account/profile operations or token values in persistent evidence.
    response = client.get(BASE+'/sg-careers-offers/get-token', respect_robots=True,
        headers={'X-Requested-With':'XMLHttpRequest', 'X-CSRF-Token':settings['csrfToken']})
    response.raise_for_status(); token = response.json().get('token')
    if not isinstance(token, str) or not token:
        raise SourceError('Societe Generale public search token unavailable')
    headers = {'X-Proxy-URL':PROFILE, 'Authorization-API':'Bearer '+token}
    rows=[]; seen=set(); total=None
    for number in range(1, 101):
        body = dict(profile='ces_profile_sgcareers', lang='en', responseType='SearchResult',
            query=dict(advanced=[dict(type='simple',name='sourcestr6',op='eq',value='job'),
                                 dict(type='multi',name='sourcecsv1',op='eq',values=['USA'])],
                       skipCount=10,skipFrom=(number-1)*10,sort='sourcedatetime1.desc'))
        response = client.post(BASE+'/search-proxy.php', json=body, headers=headers,
                               respect_robots=True, retry_post=True)
        response.raise_for_status(); data=response.json()
        count = data.get('TotalCount'); batch=(data.get('Result') or {}).get('Docs')
        if (data.get('methodresult') != 'ok' or not isinstance(count,int) or isinstance(count,bool)
                or not 0 <= count <= 1000 or not isinstance(batch,list)
                or data.get('CurrentPage') != number or data.get('DocumentsThisPage') != len(batch)
                or data.get('PageCount') != (count+9)//10):
            raise SourceError('Societe Generale search pagination/schema changed')
        if total is not None and total != count:
            raise SourceError('Societe Generale result count changed during pagination')
        total = count
        for row in batch:
            job = identity(row.get('url1'))
            if (not job or job != row.get('sourcestr4') or row.get('sourcestr12') != job+'-en'
                    or row.get('sourcestr6') != 'job' or job in seen):
                raise SourceError('Societe Generale repeated/mismatched job identity')
            seen.add(job); rows.append(row)
        if len(rows) == total:
            break
        if not batch or len(rows) > total:
            raise SourceError('Societe Generale incomplete search results')
    if len(rows) != total:
        raise SourceError('Societe Generale pagination limit exceeded')
    jobs=[]
    for row in rows:
        job=row['sourcestr4']; url=row['url1']; title=row['title']; desc=row.get('sourcestr13','')
        employment=row.get('sourcestr8'); posting_date=None; application=url
        evidence=dict(provider='socgen',provider_job_id=job,search_total=total,
            search_publication_date=row.get('sourcedatetime1'),description_kind='employer_search_summary')
        if re.search(r'\b(?:intern(?:ship)?|co[ -]?op|summer|fellow|residen(?:cy|t))\b', title+' '+str(employment or ''), re.I):
            response=client.get(url,respect_robots=True,raise_for_status=False)
            if identity(response.url) != job:
                raise SourceError('Societe Generale detail redirected to another posting')
            if response.status_code in (404,410):
                # Search indexes can retain a withdrawn requisition. Preserve the
                # observation, not an inferred open/closed state; the validator
                # checks its exact destination independently before notification.
                evidence.update(detail_http_status=response.status_code,
                                detail_final_url=response.url)
            else:
                response.raise_for_status()
                page=Page(response.text)
                items=[x for x in page.postings() if (x.get('identifier') or {}).get('value')==job]
                if len(items)!=1:
                    raise SourceError('Societe Generale expected public job schema unavailable')
                item=items[0]
                if (not title_compatible(title,item.get('title'),same_identifier=True)
                        or not employer_compatible(source['employer'],(item.get('hiringOrganization') or {}).get('name'),url)
                        or not item.get('description')):
                    raise SourceError('Societe Generale job title/employer/description mismatch')
                desc=re.split(r'Why join us|Business insight',_description(item['description']),maxsplit=1)[0]
                employment=item.get('employmentType') or employment
                if item.get('datePosted'):
                    posting_date=datetime.strptime(item['datePosted'],'%Y/%m/%d').date().isoformat()
                apps=list(dict.fromkeys(target for target,_ in page.anchors if identity(target)==job
                                        and urlsplit(target).hostname=='socgen.taleo.net'))
                if len(apps)>1:raise SourceError('Societe Generale multiple application destinations')
                if apps:application=apps[0]
                evidence.update(description_kind='employer_public_detail',posting_date_kind='employer_schema_datePosted',
                                employer_schema_date=item.get('datePosted'),valid_through=item.get('validThrough'))
        jobs.append(_base(source,'socgen',job,title,url,description=desc,application_url=application,
            locations=[row.get('sourcestr7','')],employment_type=employment,posting_date=posting_date,evidence=evidence))
    return jobs

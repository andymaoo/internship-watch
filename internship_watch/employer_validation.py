"""Exact-job public employer data, independent of application-form access."""
import re
from datetime import datetime, timezone
from urllib.parse import urlsplit, parse_qs, urlencode, quote

from .employer_sources import EIGHTFOLD_HOSTS


def spec_for(url):
    parsed = urlsplit(url)
    host, parts = parsed.hostname, parsed.path.strip('/').split('/')
    if host == 'jobs.smartrecruiters.com' and len(parts) == 2:
        match = re.fullmatch(r'(\d+)(?:-.*)?', parts[1])
        if match and re.fullmatch(r'[A-Za-z0-9_-]+', parts[0]):
            board, identity = parts[0], match[1]
            return dict(provider='smartrecruiters', board=board, id=identity,
                        canonical=f'https://jobs.smartrecruiters.com/{board}/{identity}',
                        api=f'https://api.smartrecruiters.com/v1/companies/{quote(board)}/postings/{identity}')
    for domain, base in EIGHTFOLD_HOSTS.items():
        # Netflix's legacy API has a different detail contract; use its page.
        if domain == 'netflix.com':
            continue
        match = re.match(r'^/careers/job/(\d+)(?:/|$)', parsed.path)
        if host == urlsplit(base).hostname and match:
            return dict(provider='eightfold', board=domain, id=match[1],
                        canonical=base+'/careers/job/'+match[1], respect_robots=True,
                        api=base+'/api/pcsx/position_details?'+urlencode({'domain':domain,'position_id':match[1]}))
    identity = (parse_qs(parsed.query).get('id') or [''])[0]
    if host == 'careers.snap.com' and parsed.path == '/job' and re.fullmatch(r'[A-Za-z0-9_-]+', identity):
        return dict(provider='snap', board='snap', id=identity, canonical=url, respect_robots=True,
                    api='https://careers.snap.com/api/job_details?'+urlencode({'id':identity}))
    return None


def check_posting(job, spec, client):
    from .links import plain, meaningful_description, title_compatible, employer_compatible, valid_url
    check = dict(kind='posting_api', requested_url=spec['api'], final_url=None, status='unverified', evidence=[])
    try:
        response = client.get(spec['api'], respect_robots=spec.get('respect_robots', False), raise_for_status=False)
        check.update(http_status=response.status_code, final_url=response.url, fetched_at=datetime.now(timezone.utc).isoformat())
        if response.status_code != 200:
            check['evidence'] = ['public_api_unavailable:'+str(response.status_code)]
            return check
        if urlsplit(response.url).netloc != urlsplit(spec['api']).netloc:
            raise ValueError('Unexpected public API redirect')
        data = response.json()
        provider = spec['provider']
        if provider == 'smartrecruiters':
            item = data
            if item.get('visibility') != 'PUBLIC' or item.get('active') is not True:
                raise ValueError('Public active posting not confirmed')
            if (item.get('company') or {}).get('identifier') != spec['board'] or not employer_compatible(job.get('employer'),item['company'].get('name'),spec['canonical']):
                raise ValueError('Employer mismatch')
            title, url, application = item.get('name'), item.get('postingUrl'), item.get('applyUrl')
            sections = (item.get('jobAd') or {}).get('sections') or {}
            description = plain(' '.join(str(v.get('text') or '') for v in sections.values() if isinstance(v,dict)))
        elif provider == 'eightfold':
            if data.get('status') != 200:
                raise ValueError('Unsuccessful Eightfold detail')
            item = data.get('data') or {}
            title = item.get('name')
            url = item.get('publicUrl') or spec['canonical']
            description = plain(item.get('jobDescription'))
            application = None
            if not employer_compatible(job.get('employer'),spec['board'].split('.')[0],url):
                raise ValueError('Employer mismatch')
        else:
            item = data.get('body') or {}
            if item.get('jobPostingSite') != 'Snap Inc.' or item.get('External_Posting') != '1':
                raise ValueError('Public Snap posting not confirmed')
            if not employer_compatible(job.get('employer'),'Snap',spec['canonical']):
                raise ValueError('Employer mismatch')
            title, url = item.get('title'), spec['canonical']
            application = item.get('External_Apply_URL')
            description = plain(item.get('jobDescription'))
        if str(item.get('id')) != spec['id']:
            raise ValueError('Posting identifier mismatch')
        returned = spec_for(url) if valid_url(url) else None
        if not returned or (returned['provider'],returned['board'],returned['id']) != (provider,spec['board'],spec['id']):
            raise ValueError('Canonical job URL mismatch')
        if not title_compatible(job.get('title'), title, same_identifier=True):
            raise ValueError('Posting title mismatch')
        if not meaningful_description(description):
            raise ValueError('Missing meaningful description')
        check.update(status='open', posting_url=url, title=title, description=description[:50_000],
                     evidence=['fresh_public_employer_detail','exact_employer_job_identifier_and_title_verified','meaningful_description_present'])
        if application and valid_url(application) and spec['id'].lower() in application.lower():
            check['application_url'] = application
    except Exception as exc:
        check['evidence'] = ['public_employer_detail_unverified:'+type(exc).__name__+':'+str(exc)[:160]]
    return check

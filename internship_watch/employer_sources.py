"""Public employer search services, with explicit scope and completeness checks.

SmartRecruiters is a documented public API. The other endpoints are observed
read-only career-site requests, so robots policy applies to every request.
"""
import re
import html
from datetime import datetime, timezone
from urllib.parse import quote, urljoin, urlsplit

from .sources import SourceError, _base, _json, _jobs_list, _required, _check_unexpected_pagination


EIGHTFOLD_HOSTS = {
    'nvidia.com': 'https://jobs.nvidia.com',
    'microsoft.com': 'https://apply.careers.microsoft.com',
    'netflix.com': 'https://explore.jobs.netflix.net',
    'paypal.com': 'https://paypal.eightfold.ai',
}


def _bounds(source):
    maximum = source.get('max_pages', 100)
    if not isinstance(maximum, int) or not 1 <= maximum <= 500:
        raise SourceError('Invalid pagination bound')
    return maximum


def _total(value):
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise SourceError('Missing or invalid result total')
    return value


def _date(timestamp):
    if timestamp is None:
        return None
    try:
        return datetime.fromtimestamp(float(timestamp), timezone.utc).isoformat()
    except (ValueError, TypeError, OverflowError, OSError) as exc:
        raise SourceError('Invalid employer timestamp') from exc


def smartrecruiters(source, client):
    board = source['slug']
    base = f'https://api.smartrecruiters.com/v1/companies/{quote(board, safe="")}/postings'
    jobs, seen, offset, expected = [], set(), 0, None
    for _ in range(_bounds(source)):
        data = _json(client, base, params={'limit': 100, 'offset': offset})
        items = _jobs_list(data, 'content')
        total = _total(data.get('totalFound'))
        if expected is not None and total != expected:
            raise SourceError('SmartRecruiters total changed during pagination')
        expected = total
        if data.get('offset') != offset or not items and offset < total:
            raise SourceError('SmartRecruiters skipped or truncated a page')
        for item in items:
            _required(item, 'id', 'name', 'company', 'location')
            identity = str(item['id'])
            if identity in seen or item['company'].get('identifier') != board or item.get('visibility') != 'PUBLIC':
                raise SourceError('Repeated, private, or wrong-employer SmartRecruiters posting')
            seen.add(identity)
            loc = item['location']
            jobs.append(_base(source, 'sr', f'{board}-{identity}', item['name'],
                f'https://jobs.smartrecruiters.com/{quote(board, safe="")}/{identity}',
                locations=[loc.get('fullLocation') or ', '.join(str(loc.get(k) or '') for k in ('city','region','country'))],
                employment_type=(item.get('typeOfEmployment') or {}).get('label'), posting_date=item.get('releasedDate'),
                evidence={'provider': 'smartrecruiters', 'provider_job_id': identity, 'board': board,
                          'posting_date_kind': 'employer_releasedDate', 'description_kind': 'employer_search_summary',
                          'address': {'addressCountry': loc.get('country')}, 'is_remote': loc.get('remote')}))
        offset += len(items)
        if offset == total:
            return jobs
        if offset > total:
            raise SourceError('SmartRecruiters returned more jobs than declared')
    raise SourceError('SmartRecruiters pagination cap reached')


class EightfoldPaginationChanged(SourceError):
    pass


def eightfold(source, client):
    retries = source.get('pagination_retries', 0)
    if type(retries) is not int or not 0 <= retries <= 1:
        raise SourceError('Eightfold pagination retries must be zero or one')
    for attempt in range(retries + 1):
        try:
            return _eightfold_once(source, client)
        except EightfoldPaginationChanged:
            if attempt == retries:
                raise
            # Discard the entire incomplete attempt. Never silently union pages
            # with missing IDs; the retry must independently prove completeness.


def _eightfold_once(source, client):
    overlap = source.get('page_overlap', 0)
    if type(overlap) is not int or not 0 <= overlap <= 9:
        raise SourceError('Eightfold page overlap must be between zero and nine')
    domain = source['domain']
    if domain not in EIGHTFOLD_HOSTS:
        raise SourceError('Unreviewed Eightfold host')
    base = EIGHTFOLD_HOSTS[domain]
    legacy = source.get('api_variant') == 'apply'
    searches = source.get('searches')
    if not isinstance(searches, list) or not searches or len(searches) > 10:
        raise SourceError('Explicit bounded Eightfold search scopes required')
    jobs = {}
    for search in searches:
        if not isinstance(search, dict) or any(not (k == 'query' or k.startswith('filter_')) for k in search):
            raise SourceError('Invalid Eightfold search parameters')
        seen, start, expected = set(), 0, None
        for _ in range(_bounds(source)):
            params = dict(search, domain=domain, start=start)
            if source.get('sort_by'):
                if legacy or source['sort_by'] not in ('relevance','timestamp'):
                    raise SourceError('Unreviewed Eightfold sort order')
                params['sort_by']=source['sort_by']
            if legacy:
                params['num'] = 100
            payload = _json(client, base + ('/api/apply/v2/jobs' if legacy else '/api/pcsx/search'),
                            params=params, respect_robots=True)
            data = payload if legacy else payload.get('data')
            if not isinstance(data, dict):
                raise SourceError('Eightfold search schema changed')
            if source.get('sort_by') and data.get('sortBy')!=source['sort_by']:
                raise SourceError('Eightfold did not honor requested sort order')
            items = _jobs_list(data, 'positions')
            total = _total(data.get('count'))
            if expected is not None and total != expected:
                raise EightfoldPaginationChanged('Eightfold total changed during pagination')
            expected = total
            if not items and start < total:
                raise EightfoldPaginationChanged('Eightfold returned an empty page before declared end')
            added = 0
            for item in items:
                _required(item, 'id', 'name')
                identity = str(item['id'])
                if item.get('isPrivate') is True:
                    raise SourceError('Private Eightfold posting in public search')
                if identity in seen and not overlap:
                    raise EightfoldPaginationChanged(f'Repeated Eightfold posting {identity} at offset {start}, scope {search}')
                canonical = urljoin(base, item.get('canonicalPositionUrl') or item.get('positionUrl') or f'/careers/job/{identity}')
                matched = re.fullmatch(r'/careers/job/(\d+)(?:/.*)?', urlsplit(canonical).path)
                if (urlsplit(canonical).netloc != urlsplit(base).netloc or urlsplit(canonical).scheme != 'https' or
                        not identity.isdigit() or not matched or matched[1] != identity):
                    raise SourceError('Eightfold job URL disagrees with identity')
                candidate = _base(source, 'ef', f'{domain}-{identity}', item['name'], canonical,
                    locations=item.get('standardizedLocations') or item.get('locations') or [item.get('location', '')],
                    posting_date=_date(item.get('postedTs')),
                    evidence={'provider': 'eightfold', 'provider_job_id': identity, 'domain': domain,
                              'posting_date_kind': 'employer_postedTs' if item.get('postedTs') else None,
                              'description_kind': 'employer_search_summary', 'search_scope': searches,
                              'ats_job_id': item.get('atsJobId') or item.get('ats_job_id'),
                              'workplace_type': item.get('workLocationOption') or item.get('work_location_option')})
                if identity in seen:
                    if jobs[identity] != candidate:
                        raise EightfoldPaginationChanged('Eightfold posting changed between overlapping pages')
                else:
                    seen.add(identity); added += 1; jobs[identity] = candidate
            end = start + len(items)
            if end == total:
                if len(seen) != total:
                    raise EightfoldPaginationChanged('Eightfold unique posting count is incomplete')
                break
            if end > total:
                raise SourceError('Eightfold returned more jobs than declared')
            if not added:
                raise EightfoldPaginationChanged('Eightfold page made no progress')
            start += max(1, len(items) - overlap)
        else:
            raise SourceError('Eightfold pagination cap reached')
    return list(jobs.values())


def snap(source, client):
    data = _json(client, 'https://careers.snap.com/api/jobs', respect_robots=True)
    items = _jobs_list(data, 'body')
    _check_unexpected_pagination(data)
    if not isinstance(data.get('aggs'), dict) or 'type' not in data['aggs']:
        raise SourceError('Snap full-board schema changed')
    jobs = []
    for row in items:
        item = row.get('_source', {})
        _required(item, 'id', 'title', 'absolute_url')
        if item.get('External_Posting') != '1' or item.get('jobPostingSite') != 'Snap Inc.':
            raise SourceError('Unexpected Snap posting visibility or employer')
        identity = str(item['id'])
        jobs.append(_base(source, 'snap', identity, item['title'], f'https://careers.snap.com/job?id={quote(identity)}',
            application_url=item['absolute_url'], employment_type=item.get('employment_type'),
            locations=[loc.get('location') or loc.get('name') for loc in item.get('offices', [])],
            evidence={'provider': 'snap', 'provider_job_id': identity, 'description_kind': 'employer_search_summary',
                      'source_index': row.get('_index')}))
    return jobs


def uber(source, client):
    jobs, seen, expected = [], set(), None
    for page in range(1, _bounds(source) + 1):
        data = _json(client, 'https://jobs.uber.com/api/jobs/search/', params={'page': page, 'pagesize': 100}, respect_robots=True)
        total = _total(data.get('totalJobs'))
        items = _jobs_list(data, 'jobs')
        if data.get('page') != page or expected is not None and total != expected or not items and len(jobs) < total:
            raise SourceError('Uber unstable or truncated pagination')
        expected = total
        for item in items:
            _required(item, 'Id', 'Title', 'Urls')
            identity = str(item['Id'])
            if identity in seen:
                raise SourceError('Uber repeated a posting across pages')
            seen.add(identity)
            urls = [entry['Url'] for entry in item['Urls'] if entry.get('IsDefault') and entry.get('Url')]
            if len(urls) != 1:
                raise SourceError('Uber canonical URL missing or ambiguous')
            jobs.append(_base(source, 'uber', identity, item['Title'], urljoin('https://jobs.uber.com', urls[0]),
                description=item.get('Description'), employment_type=item.get('WorkPattern') or item.get('ContractType'),
                locations=[', '.join(str(loc.get(k)) for k in ('City','Region','Country') if loc.get(k)) for loc in item.get('Locations', [])],
                posting_date=item.get('DisplayDate'),
                evidence={'provider': 'uber', 'provider_job_id': identity, 'posting_date_kind': 'employer_DisplayDate', 'is_remote': item.get('Remote')}))
        if len(jobs) == total:
            return jobs
        if len(jobs) > total or page >= _total(data.get('totalPages')):
            raise SourceError('Uber total disagrees with final page')
    raise SourceError('Uber pagination cap reached')


def amazon(source, client):
    jobs = {}
    for query in source.get('queries', ['intern', 'co-op', 'fellowship', 'residency', 'student']):
        seen, offset, expected = set(), 0, None
        for _ in range(_bounds(source)):
            data = _json(client, 'https://www.amazon.jobs/en/search.json',
                         params={'base_query': query, 'offset': offset, 'result_limit': 100}, respect_robots=True)
            if data.get('error'):
                raise SourceError('Amazon search returned an error')
            total = _total(data.get('hits'))
            items = _jobs_list(data, 'jobs')
            if expected is not None and total != expected or not items and offset < total:
                raise SourceError('Amazon unstable or truncated pagination')
            expected = total
            for item in items:
                _required(item, 'id', 'title', 'job_path')
                identity = str(item['id'])
                if identity in seen:
                    raise SourceError('Amazon repeated a posting across pages')
                seen.add(identity)
                url = urljoin('https://www.amazon.jobs', item['job_path'])
                description = '\n'.join(str(item.get(k) or '') for k in ('description','basic_qualifications','preferred_qualifications'))
                jobs[identity] = _base(source, 'amazon', identity, item['title'], url,
                    description=description, employment_type='Internship' if item.get('is_intern') is True else item.get('job_schedule_type'),
                    locations=[item.get('location') or ', '.join(str(item.get(k) or '') for k in ('city','state','country_code'))],
                    posting_date=item.get('posted_date'),
                    evidence={'provider': 'amazon', 'provider_job_id': identity, 'posting_date_kind': 'employer_posted_date',
                              'search_scope': source.get('queries'), 'structured_is_intern': item.get('is_intern'),
                              'address': {'addressCountry': item.get('country_code')}})
            offset += len(items)
            if offset == total:
                break
            if offset > total:
                raise SourceError('Amazon total disagrees with records')
        else:
            raise SourceError('Amazon pagination cap reached')
    return list(jobs.values())


def rippling(source, client):
    """Only the public careers index, using the website's public search-only key."""
    app, index = source['app_id'], source['index']
    if not re.fullmatch(r'[A-Z0-9]{10}', app) or index != 'careers_en-US_production':
        raise SourceError('Unreviewed Rippling public index')
    url = f'https://{app.lower()}-dsn.algolia.net/1/indexes/{index}/query'
    jobs, objects, expected = {}, set(), None
    for page in range(_bounds(source)):
        response = client.post(url, json={'query': '', 'hitsPerPage': 100, 'page': page}, retry_post=True,
                               headers={'X-Algolia-Application-Id': app, 'X-Algolia-API-Key': source['public_search_key']})
        response.raise_for_status()
        data = response.json()
        total = _total(data.get('nbHits'))
        items = _jobs_list(data, 'hits')
        if (data.get('page') != page or data.get('exhaustiveNbHits') is False or
                expected is not None and total != expected or not items and len(objects) < total):
            raise SourceError('Rippling unstable or incomplete public index')
        expected = total
        for item in items:
            _required(item, 'jobId', 'name', 'url', 'objectID')
            if item['objectID'] in objects:
                raise SourceError('Rippling repeated a search object across pages')
            objects.add(item['objectID'])
            identity = item['jobId']
            if item['url'] != 'https://ats.rippling.com/rippling/jobs/' + identity:
                raise SourceError('Rippling public job URL/identity mismatch')
            if identity in jobs:
                job = jobs[identity]
                if job['title'] != item['name'].strip():
                    raise SourceError('Rippling location variants disagree on job title')
                job['locations'] = sorted(set(job['locations'] + item.get('locationNames', [])))
                job['location'] = '; '.join(job['locations'])
            else:
                jobs[identity] = _base(source, 'rippling', identity, item['name'], item['url'],
                    locations=item.get('locationNames', []),
                    evidence={'provider': 'rippling', 'provider_job_id': identity, 'is_remote': item.get('isRemote'),
                              'description_kind': 'employer_search_summary', 'locations': item.get('locations', [])})
        if len(objects) == total:
            return list(jobs.values())
        if len(objects) > total or page + 1 >= _total(data.get('nbPages')):
            raise SourceError('Rippling search cap/total disagrees with collected objects')
    raise SourceError('Rippling pagination cap reached')


def bloomberg(source, client):
    """Follow the public Avature page links, checking its declared result total."""
    from .sources import _description
    url = 'https://bloomberg.avature.net/careers/SearchJobs/?jobRecordsPerPage=12&jobOffset=0'
    jobs, expected, visited, pages, rows_read = {}, None, set(), set(), 0
    for _ in range(_bounds(source)):
        if url in visited or not url.startswith('https://bloomberg.avature.net/careers'):
            raise SourceError('Bloomberg pagination loop or unexpected destination')
        visited.add(url)
        response = client.get(url, respect_robots=True)
        response.raise_for_status()
        text = response.text
        match = re.search(r'aria-label="([\d,]+) results"', text)
        if not match:
            raise SourceError('Bloomberg result total missing; possible challenge/schema change')
        total = int(match[1].replace(',', ''))
        if expected is not None and total != expected:
            raise SourceError('Bloomberg result total changed during pagination')
        expected = total
        page_ids = []
        for article in re.findall(r'<article\b[^>]*class="[^"]*article--result[^"]*"[^>]*>(.*?)</article>', text, re.S):
            link = re.search(r'<a\b[^>]*href="(https://bloomberg.avature.net/careers/JobDetail/[^"?#]+/(\d+))"[^>]*>(.*?)</a>', article, re.S)
            location = re.search(r'<span class="list-item-location">(.*?)</span>', article, re.S)
            if not link or link[2] in page_ids:
                raise SourceError('Bloomberg missing or repeated identity within a page')
            page_ids.append(link[2])
            record = _base(source, 'bloomberg', link[2], _description(link[3]), html.unescape(link[1]),
                locations=[_description(location[1])] if location else [],
                evidence={'provider': 'bloomberg', 'provider_job_id': link[2], 'description_kind': 'employer_search_summary'})
            if link[2] in jobs and (jobs[link[2]]['title'], jobs[link[2]]['description_url']) != (record['title'], record['description_url']):
                raise SourceError('Bloomberg repeated requisition has conflicting identity')
            jobs[link[2]] = record
        if tuple(page_ids) in pages or not page_ids and total:
            raise SourceError('Bloomberg repeated/empty page before declared end')
        pages.add(tuple(page_ids))
        rows_read += len(page_ids)
        next_link = re.search(r'<a\b[^>]*href="([^"]+)"[^>]*aria-label="Go to Next Page[^>]*>', text, re.S)
        if not next_link:
            if rows_read != total:
                raise SourceError('Bloomberg final count differs from declared total')
            for job in jobs.values():
                job['evidence'].update(source_rows=rows_read, source_unique_jobs=len(jobs),
                                       overlapping_source_rows=rows_read-len(jobs))
            return list(jobs.values())
        url = html.unescape(next_link[1])
    raise SourceError('Bloomberg pagination cap reached')


def bytedance(source, client):
    return _byte_supplier(source, client, 'bytedance')


def tiktok(source, client):
    # This public supplier endpoint currently returns the shared ByteDance
    # group index, including explicitly ByteDance-branded roles. Its hostname
    # is provenance, not evidence that every record's employer is TikTok.
    jobs = _byte_supplier(dict(source, employer='ByteDance'), client, 'tiktok')
    for job in jobs:
        job['evidence']['employer_scope'] = 'parent_group; subsidiary_not_verified'
    return jobs


def _byte_supplier(source, client, brand):
    base, career = ('https://api.lifeattiktok.com', 'https://lifeattiktok.com') if brand=='tiktok' else ('https://jobs.bytedance.com','https://joinbytedance.com')
    jobs, seen, offset, expected = [], set(), 0, None
    for _ in range(_bounds(source)):
        response = client.post(base+'/api/v1/public/supplier/search/job/posts',
            json={'keyword': source.get('query', 'intern'), 'limit': 1000, 'offset': offset},
            headers={'accept-language': 'en-US', 'website-path': 'en', 'Origin': career},
            respect_robots=True, retry_post=True)
        response.raise_for_status()
        payload = response.json()
        if payload.get('code') != 0 or not isinstance(payload.get('data'), dict):
            raise SourceError('ByteDance search returned an error/schema change')
        data = payload['data']
        items = _jobs_list(data, 'job_post_list')
        total = _total(data.get('count'))
        if expected is not None and expected != total or not items and offset < total:
            raise SourceError('ByteDance unstable or truncated pagination')
        expected = total
        for item in items:
            _required(item, 'id', 'title', 'city_info')
            identity = str(item['id'])
            if identity in seen or not identity.isdigit():
                raise SourceError(f'ByteDance invalid/repeated posting ID {identity} at offset {offset}')
            seen.add(identity)
            loc, parts = item['city_info'], []
            for _ in range(5):
                if not isinstance(loc, dict):
                    break
                if loc.get('en_name'):
                    parts.append(loc['en_name'])
                loc = loc.get('parent')
            jobs.append(_base(source, brand, identity, item['title'], career+'/search/' + identity,
                description='\n'.join(str(item.get(k) or '') for k in ('description', 'requirement')),
                locations=[', '.join(dict.fromkeys(parts))], employment_type=(item.get('recruit_type') or {}).get('en_name'),
                evidence={'provider': brand, 'provider_job_id': identity, 'requisition_id': item.get('code'),
                          'search_scope': source.get('query', 'intern')}))
        offset += len(items)
        if offset == total:
            return jobs
        if offset > total:
            raise SourceError('ByteDance total disagrees with records')
    raise SourceError('ByteDance pagination cap reached')

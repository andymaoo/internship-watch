"""Public career-site search adapters; never use candidate or account endpoints."""
import re
from urllib.parse import urlsplit, quote

from .sources import SourceError, _base, _json, _jobs_list, _required, _description
from .employer_sources import _bounds, _total

ATLASSIAN_PORTALS = {'careers-americas.icims.com', 'globalcareers-atlassian.icims.com',
    'careers-apac-atlassian.icims.com', 'campus-globalcareers-atlassian.icims.com',
    'campus-americas.icims.com'}

ORACLE_BASE = 'https://eeho.fa.us2.oraclecloud.com'
ORACLE_SITE = 'CX_45001'


def oracle(source, client):
    """Oracle's public Student/Intern worker-type search, all advertised pages."""
    endpoint = ORACLE_BASE+'/hcmRestApi/resources/latest/'
    jobs, seen, offset, expected = [], set(), 0, None
    for _ in range(_bounds(source)):
        data = _json(client,endpoint+'recruitingCEJobRequisitions',respect_robots=True,
            params={'onlyData':'true','expand':'requisitionList.secondaryLocations,requisitionList.requisitionFlexFields',
                'finder':f'findReqs;siteNumber={ORACLE_SITE},limit=100,offset={offset},selectedFlexFieldsFacets="AttributeChar4|Student/Intern",sortBy=POSTING_DATES_DESC'})
        envelopes = _jobs_list(data,'items')
        if len(envelopes)!=1:
            raise SourceError('Oracle search envelope changed')
        result = envelopes[0]
        items, total = _jobs_list(result,'requisitionList'), _total(result.get('TotalJobsCount'))
        if result.get('SiteNumber')!=ORACLE_SITE or result.get('Offset')!=offset or expected is not None and expected!=total:
            raise SourceError('Oracle site or pagination total changed')
        expected=total
        for item in items:
            _required(item,'Id','Title','PrimaryLocation')
            identity=str(item['Id'])
            if not identity.isdigit() or identity in seen:
                raise SourceError('Oracle missing or repeated posting identity')
            seen.add(identity)
            details=item
            detail = _json(client,endpoint+'recruitingCEJobRequisitionDetails',respect_robots=True,
                params={'onlyData':'true','expand':'all','finder':f'ById;Id="{identity}",siteNumber={ORACLE_SITE}'})
            matches=_jobs_list(detail,'items')
            if len(matches)!=1 or str(matches[0].get('Id'))!=identity or matches[0].get('Title')!=item['Title']:
                raise SourceError('Oracle posting changed between search and detail')
            details=matches[0]
            description='\n'.join(str(details.get(k) or '') for k in
                ('ExternalDescriptionStr','ExternalResponsibilitiesStr','ExternalQualificationsStr'))
            url=ORACLE_BASE+f'/hcmUI/CandidateExperience/en/sites/{ORACLE_SITE}/job/{identity}'
            locations=[details['PrimaryLocation']]+[x['Name'] for x in details.get('secondaryLocations',[]) if isinstance(x,dict) and x.get('Name')]
            jobs.append(_base(source,'oracle',ORACLE_SITE+'-'+identity,item['Title'],url,
                description=description,locations=locations,posting_date=details.get('ExternalPostedStartDate') or item.get('PostedDate'),
                employment_type=details.get('JobType') or 'Student/Intern',evidence=dict(provider='oracle',provider_job_id=identity,
                address={'addressCountry':details.get('PrimaryLocationCountry')},posting_date_kind='employer_posted_date',
                description_kind='employer_public_detail' if details is not item else 'employer_search_summary',
                requisition_type=details.get('RequisitionType'),posting_end=details.get('ExternalPostedEndDate'))))
        offset+=len(items)
        if offset==total:
            return jobs
        if not items or offset>total:
            raise SourceError('Oracle search truncated or overfilled')
    raise SourceError('Oracle pagination cap reached')


def atlassian(source, client):
    items = _jobs_list(_json(client,'https://www.atlassian.com/endpoint/careers/listings',respect_robots=True))
    jobs=[]; seen={}
    for item in items:
        _required(item,'id','title','locations','portalJobPost')
        identity=str(item['id']);portal=item['portalJobPost']
        if identity in seen:
            if seen[identity]!=item:
                raise SourceError('Atlassian duplicate requisition has conflicting content')
            continue
        seen[identity]=item
        if not identity.isdigit() or str(portal.get('id'))!=identity or not isinstance(item['locations'],list):
            raise SourceError('Atlassian posting identity/location schema changed')
        application=portal.get('portalUrl','');p=urlsplit(application)
        if p.hostname not in ATLASSIAN_PORTALS or not p.path.startswith('/jobs/'+identity+'/'):
            raise SourceError('Atlassian returned an unreviewed application destination')
        description='\n'.join(str(item.get(k) or '') for k in ('overview','responsibilities','qualifications'))
        jobs.append(_base(source,'atlassian',identity,item['title'],
            'https://www.atlassian.com/company/careers/details/'+identity,
            application_url=application,description=description,locations=item['locations'],
            employment_type='Internship' if item.get('category')=='Interns' else None,
            evidence=dict(provider='atlassian',provider_job_id=identity,category=item.get('category'),
                          source_updated_at=portal.get('updatedDate'))))
    return jobs


def jobvite(source, client):
    slug=source['slug']
    if not re.fullmatch(r'[A-Za-z0-9_-]+',slug):
        raise SourceError('Invalid Jobvite board')
    response=client.get('https://jobs.jobvite.com/'+slug+'/jobs',respect_robots=True)
    response.raise_for_status();page=response.text
    if re.search(r'jv-pagination|rel=[\"\x27]next|load-more',page,re.I):
        raise SourceError('Jobvite introduced pagination; adapter review required')
    rows=re.findall(r'<tr\b[^>]*>(.*?)</tr>',page,re.S|re.I)
    jobs=[]
    for row in rows:
        if 'jv-job-list-name' not in row:
            continue
        link=re.search(r'<a\s+href=[\"\x27](/'+re.escape(slug)+r'/job/([A-Za-z0-9_-]+))[\"\x27][^>]*>(.*?)</a>',row,re.S|re.I)
        loc=re.search(r'<td[^>]*class=[\"\x27]jv-job-list-location[\"\x27][^>]*>(.*?)</td>',row,re.S|re.I)
        if not link or not loc:
            raise SourceError('Jobvite job row schema changed')
        jobs.append(_base(source,'jobvite',slug+'-'+link[2],_description(link[3]),
            'https://jobs.jobvite.com'+link[1],locations=[re.sub(r'\s+',' ',_description(loc[1])).strip()],
            evidence=dict(provider='jobvite',provider_job_id=link[2],board=slug,description_kind='employer_search_summary')))
    if not jobs and not re.search(r'no (?:current )?open (?:positions|jobs)',page,re.I):
        raise SourceError('Jobvite full job list missing; empty result unproven')
    return jobs


def workday_spec(url):
    p = urlsplit(url)
    if not re.fullmatch(r'[a-z0-9-]+\.wd\d+\.myworkdayjobs\.com', p.hostname or ''):
        return None
    parts = p.path.strip('/').split('/')
    if parts and re.fullmatch(r'[a-z]{2}-[A-Z]{2}', parts[0]):
        parts = parts[1:]
    if len(parts)>2 and parts[1]=='job' and parts[-1] == 'apply':
        parts = parts[:-1]
    if not parts or not re.fullmatch(r'[A-Za-z0-9_-]+', parts[0]):
        return None
    base = 'https://' + p.hostname
    # CCI's public board HTML declares tenant "osv_cci" on a hyphenated host.
    tenant = {'osv-cci.wd1.myworkdayjobs.com':'osv_cci'}.get(p.hostname,p.hostname.split('.')[0])
    site = parts[0]
    spec = dict(provider='workday', board=tenant+'/'+site, tenant=tenant, site=site,
                base=base, canonical=base+'/'+site, api=base+'/wday/cxs/'+tenant+'/'+site)
    if len(parts) > 2 and parts[1] == 'job':
        tail = parts[-1]
        if '_' not in tail or not tail.rsplit('_', 1)[1]:
            return None
        spec.update(id=tail.rsplit('_', 1)[1], path='/'+'/'.join(parts[1:]),
                    canonical=base+'/'+site+'/'+'/'.join(parts[1:]))
    elif len(parts) != 1:
        return None
    return spec


def workday_detail(spec, client):
    data = _json(client, spec['api']+spec['path'], respect_robots=True)
    info = data.get('jobPostingInfo')
    if not isinstance(info, dict):
        raise SourceError('Missing Workday jobPostingInfo')
    returned = workday_spec(info.get('externalUrl', ''))
    if (not returned or returned.get('id') != spec['id'] or returned['board'] != spec['board']
            or returned['base'] != spec['base'] or info.get('jobPostingSiteId') != spec['site']):
        raise SourceError('Workday returned a different posting/site')
    _required(info, 'id', 'title', 'jobDescription', 'jobReqId')
    # Workday posting instances may append -1, -2 etc. Keep those distinct.
    if spec['id'] != info['jobReqId'] and not re.fullmatch(re.escape(info['jobReqId'])+r'-\d+', spec['id']):
        raise SourceError('Workday requisition mismatch')
    return data


def workday(source, client):
    spec = workday_spec(source['url'])
    if not spec or 'id' in spec:
        raise SourceError('Expected a public Workday board URL')
    queries = source.get('queries', ['intern', 'co-op', 'fellowship', 'residency'])
    if not isinstance(queries, list) or not queries or len(queries) > 8 or not all(isinstance(q,str) for q in queries):
        raise SourceError('Explicit bounded Workday search queries required')
    applied = dict(source.get('applied_facets', {}))
    searches = [(q, applied, None) for q in queries]
    if source.get('opportunity_facets') or source.get('country_scope'):
        # Resolve public facet IDs each poll: these are tenant-specific and can
        # change. Do not confuse International with Intern, or a location with
        # a worker type. Supplement structured internships with program queries.
        response = client.post(spec['api']+'/jobs', json=dict(limit=20,offset=0,
            searchText='',appliedFacets={}), respect_robots=True,retry_post=True)
        response.raise_for_status(); discovery = response.json()
        _jobs_list(discovery,'jobPostings'); _total(discovery.get('total'))
        if source.get('country_scope'):
            if source['country_scope'] != ['US']:
                raise SourceError('Only reviewed US Workday country scope is supported')
            country = next((f for f in discovery.get('facets',[]) if f.get('facetParameter') in ('locationCountry','Country')),None)
            values = [] if country is None else [v for v in country.get('values',[])
                if v.get('descriptor') in ('United States', 'United States of America', 'USA')]
            if len(values)==1 and isinstance(values[0].get('id'),str) and values[0]['id']:
                applied[country['facetParameter']] = [values[0]['id']]
            # Missing country facets fall back to the complete global scope;
            # the usual geographic classifier remains authoritative.
            searches = [(q, applied, None) for q in queries]
        worker_facet = source.get('worker_type_facet','workerSubType')
        if worker_facet not in ('workerSubType','company'):
            raise SourceError('Unreviewed Workday worker-type facet')
        facet = next((f for f in discovery.get('facets',[]) if f.get('facetParameter')==worker_facet),None)
        values = [] if facet is None else [v for v in facet.get('values',[])
            if re.search(r'\b(?:intern(?:ship)?|student worker|co[ -]?op)\b',v.get('descriptor',''),re.I)]
        if values and source.get('opportunity_facets'):
            if not all(isinstance(v.get('id'),str) and v['id'] for v in values):
                raise SourceError('Workday worker-type facet identity changed')
            scope = 'internship_worker_type' if all(re.search(r'\bintern',v['descriptor'],re.I) for v in values) else 'opportunity_worker_type'
            searches = [('',dict(applied,**{worker_facet:[v['id'] for v in values]}),scope)]
            searches += [(q,applied,None) for q in queries if q!='intern']
    jobs = {}
    for query, facets, scope in searches:
        offset, expected, seen = 0, None, set()
        for _ in range(_bounds(source)):
            response = client.post(spec['api']+'/jobs', json=dict(limit=20, offset=offset,
                searchText=query, appliedFacets=facets),
                headers={'Accept-Language':'en-US'}, respect_robots=True, retry_post=True)
            response.raise_for_status()
            data = response.json()
            items, total = _jobs_list(data, 'jobPostings'), _total(data.get('total'))
            # Workday sends total=0 on subsequent nonempty pages. The first
            # page supplies the count; later positive totals must still agree.
            if expected is not None and total not in (0, expected):
                raise SourceError('Workday total changed during pagination')
            if expected is None:
                expected = total
            if not items and offset < expected:
                raise SourceError('Workday truncated a search page')
            for item in items:
                _required(item, 'title', 'externalPath')
                path = item['externalPath']
                if not isinstance(path, str) or not path.startswith('/job/') or '..' in path or '?' in path:
                    raise SourceError('Invalid Workday posting path')
                url = spec['canonical']+path
                job_spec = workday_spec(url)
                if not job_spec or job_spec['id'] in seen:
                    raise SourceError('Missing or repeated Workday posting identity')
                identity = job_spec['id']; seen.add(identity)
                candidate = _base(source, 'wd', spec['board']+'-'+identity, item['title'], url,
                    locations=[item.get('locationsText','')], employment_type='Internship' if scope=='internship_worker_type' else None,
                    evidence=dict(provider='workday',
                    provider_job_id=identity, board=spec['board'], search_query=query,
                    description_kind='employer_search_summary', relative_posted_on=item.get('postedOn'),
                    structured_opportunity_scope=scope))
                prior = jobs.get(identity)
                if prior and (prior['title'] != candidate['title'] or prior['description_url'] != url):
                    raise SourceError('Conflicting Workday posting across searches')
                if not prior or scope:
                    jobs[identity] = candidate
            offset += len(items)
            if offset == expected:
                break
            if offset > expected:
                raise SourceError('Workday returned more rows than declared')
        else:
            raise SourceError('Workday pagination cap reached')
    # Public search has no description/structured employment type. Enrich explicit
    # opportunity titles, retaining all other search rows without inventing evidence.
    for job in jobs.values():
        if not job['evidence'].get('structured_opportunity_scope') and not re.search(r'\b(?:intern(?:ship)?s?|co[ -]?op|fellow(?:ship)?|residen(?:t|cy)|research program)\b',job['title'],re.I):
            continue
        info = workday_detail(workday_spec(job['description_url']), client)['jobPostingInfo']
        if info['title'] != job['title']:
            # Search indexes can lag a title edit. workday_detail has already
            # checked exact tenant/site, posting instance and requisition ID.
            job['evidence']['search_title'] = job['title']
            job['title'] = info['title']
        if info.get('posted') is False:
            continue  # retain search observation; live validator decides closure
        country = (info.get('country') or {}).get('descriptor')
        location = info.get('location') or job['location']
        locations = [location] + [x for x in info.get('additionalLocations',[]) if isinstance(x,str)]
        job.update(description=_description(info['jobDescription']), location='; '.join(locations),
                   locations=locations, country=country, employment_type=info.get('workerSubType') or job.get('employment_type') or info.get('timeType'))
        job['evidence'].update(description_kind='employer_public_detail', employer_start_date=info.get('startDate'),
                               address={'addressCountry':country}, requisition_id=info['jobReqId'])
    return list(jobs.values())


def jibe(source, client):
    """iCIMS/Jibe public search used by AMD and GitHub career-site UIs."""
    base = source['url'].rstrip('/')
    if urlsplit(base).path not in ('', '/'):
        raise SourceError('Expected career-site origin')
    jobs = {}
    for query in source.get('queries', ['intern','co-op','fellow','residency']):
        seen, expected = set(), None
        for page in range(1, _bounds(source)+1):
            data = _json(client, base+'/api/jobs', params={'keywords':query,'page':page,'limit':100,'lang':'en-us'}, respect_robots=True)
            items, total = _jobs_list(data,'jobs'), _total(data.get('totalCount'))
            if expected is not None and expected != total:
                raise SourceError('iCIMS total changed during pagination')
            expected = total
            for entry in items:
                item = entry.get('data') if isinstance(entry,dict) else None
                _required(item,'slug','req_id','title','description')
                identity = str(item['req_id'])
                if identity in seen or not re.fullmatch(r'[A-Za-z0-9_-]+', str(item['slug'])):
                    raise SourceError('Repeated or malformed iCIMS identity')
                if item.get('internal') is True or item.get('searchable') is False:
                    raise SourceError('Nonpublic iCIMS result')
                seen.add(identity)
                url = base+'/jobs/'+quote(str(item['slug']),safe='')
                candidate = _base(source,'icims',urlsplit(base).hostname+'-'+identity,item['title'],url,
                    description=item.get('description'),application_url=item.get('apply_url'),
                    locations=[', '.join(str(item.get(k) or '') for k in ('city','state','country')).strip(', ')],
                    posting_date=item.get('posted_date'),evidence=dict(provider='jibe',provider_job_id=identity,
                    address={'addressCountry':item.get('country_code') or item.get('country')},
                    categories=item.get('categories'),posting_date_kind='employer_posted_date',search_query=query))
                prior = jobs.get(identity)
                if prior and (prior['title']!=candidate['title'] or prior['description_url']!=url):
                    raise SourceError('Conflicting iCIMS identity across queries')
                jobs[identity]=candidate
            if len(seen)==total:
                break
            if not items or len(seen)>total:
                raise SourceError('iCIMS truncated or overfilled search')
        else:
            raise SourceError('iCIMS pagination cap reached')
    return list(jobs.values())

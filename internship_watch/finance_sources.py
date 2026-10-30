"""Reviewed public finance employer feeds and small career-board pages."""
import json
import re
from urllib.parse import urljoin, urlsplit, parse_qs, urlencode
from html import unescape
from datetime import datetime
from .sources import SourceError, _base, _json, _jobs_list, _required, _description, _check_unexpected_pagination


def deshaw(source, client):
    response = client.get('https://www.deshaw.com/careers', respect_robots=True)
    response.raise_for_status()
    match = re.search(r'<script\b[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>', response.text, re.S)
    if not match:
        raise SourceError('D. E. Shaw public careers data missing')
    data = json.loads(match[1]).get('props', {}).get('pageProps', {})
    if data.get('jobsFetchingError') is not False:
        raise SourceError('D. E. Shaw reported a collection error')
    jobs = []
    # internalJobs is intentionally never inspected or imported.
    for group in ('internships', 'regularJobs'):
        for entry in _jobs_list(data, group):
            item = entry.get('data')
            _required(item, 'id', 'displayName', 'jobUrl', 'jobMetadata', 'jobDescription')
            if item.get('activeOnJobsListing') is not True:
                continue
            identity, slug = str(item['id']), item['jobUrl']
            if not identity.isdigit() or not re.fullmatch(r'[A-Za-z0-9-]+-'+identity, slug):
                raise SourceError('D. E. Shaw public posting identity changed')
            meta, desc = item['jobMetadata'], item['jobDescription']
            description = '\n'.join(_description(desc.get(k)) for k in ('websiteDescription','responsibilitiesHtml','peopleWeAreLookingForHtml','peopleWeAreLookingForStr'))
            jobs.append(_base(source,'deshaw',identity,item['displayName'],
                'https://www.deshaw.com/careers/'+slug.lower(), description=description,
                employment_type=meta.get('workStatus'), locations=[x['name'] for x in meta.get('jobLocations',[]) if x.get('name')],
                evidence=dict(provider='deshaw',provider_job_id=identity,public_group=group,
                    department=item.get('department'),valid_through=item.get('validToDate'),
                    for_recent_graduates=meta.get('forRecentGraduates'),description_kind='employer_public_detail')))
    return jobs


def trexquant(source, client):
    base='https://www.trexquant.com/api/get-jobs'
    data = _json(client,base,respect_robots=True)
    _check_unexpected_pagination(data)
    items=_jobs_list(data,'jobs'); jobs=[]
    for item in items:
        _required(item,'shortcode','title','state','location')
        if item['state']!='published' or item.get('confidential') or item.get('sample'):
            continue
        identity=item['shortcode']
        if not re.fullmatch('[A-Z0-9]+',identity):
            raise SourceError('Trexquant public shortcode changed')
        details=item
        if re.search(r'\b(?:intern(?:ship)?|researcher|fellow|residen(?:cy|t))\b',item['title'],re.I):
            details=_json(client,base,params={'shortcode':identity},respect_robots=True)
            if details.get('shortcode')!=identity or details.get('title')!=item['title'] or details.get('state')!='published' or details.get('confidential'):
                raise SourceError('Trexquant public detail identity/state changed')
        locations = [', '.join(str(x.get(k) or '') for k in ('city','state','country_name')).strip(', ') for x in item.get('locations',[]) if not x.get('hidden')]
        location=item['location']
        jobs.append(_base(source,'trexquant',identity,item['title'],
            'https://apply.workable.com/trexquant/j/'+identity+'/',
            application_url='https://apply.workable.com/trexquant/j/'+identity+'/apply/',
            description=details.get('full_description') or details.get('description',''),
            locations=locations or [location.get('location_str','')],employment_type=item.get('employment_type'),
            evidence=dict(provider='trexquant',provider_job_id=identity,department=item.get('department'),
                source_created_at=item.get('created_at'),source_updated_at=item.get('updated_at'),
                address={'addressCountry':location.get('country_code')},is_remote=location.get('telecommuting'),
                description_kind='employer_public_detail' if details is not item else 'employer_search_summary')))
    return jobs


def groupone(source,client):
    from .links import Page
    url='https://group1.com/careers/'
    response=client.get(url,respect_robots=True);response.raise_for_status()
    page=Page(response.text)
    if 'Current Job Listings' not in page.text:
        raise SourceError('Group One current listings marker missing')
    if re.search(r'rel=["\x27]next|load.more.jobs',response.text,re.I):
        raise SourceError('Group One introduced pagination')
    jobs=[];seen=set()
    for target,title in page.anchors:
        match=re.fullmatch(r'https://group1\.applicantpro\.com/jobs/(\d+)(?:\.html)?/?',target)
        if not match or match[1] in seen:continue
        identity=match[1];seen.add(identity)
        response=client.get(target,respect_robots=True);response.raise_for_status()
        postings=list(Page(response.text).postings())
        matching=[x for x in postings if re.fullmatch(r'https://group1\.applicantpro\.com/jobs/'+identity+r'(?:\.html)?/?',x.get('url',''))]
        if not matching:
            # An employer index can retain an expired application link. Preserve
            # the observed listing for independent validation without inventing
            # a description, location, employment type or closed status.
            jobs.append(_base(source,'groupone',identity,title,target,
                evidence=dict(provider='groupone',provider_job_id=identity,
                    description_kind='employer_search_summary',detail_unverified='expected_job_schema_missing')))
            continue
        if len(matching)!=1:raise SourceError('Group One conflicting job schemas')
        item=matching[0];_required(item,'title','description','jobLocation')
        # The index can lag the provider's title edits. The numeric ID and exact
        # employer namespace above establish the current detail's identity.
        locations=item['jobLocation'];locations=locations if isinstance(locations,list) else [locations]
        addresses=[x.get('address',{}) for x in locations]
        jobs.append(_base(source,'groupone',identity,item['title'],item['url'],description=item['description'],
            employment_type=item.get('employmentType'),posting_date=item.get('datePosted'),
            locations=[', '.join(str(x.get(k) or '') for k in ('addressLocality','addressRegion','addressCountry')).strip(', ') for x in addresses],
            evidence=dict(provider='groupone',provider_job_id=identity,address=addresses[0] if addresses else {},
                posting_date_kind='employer_schema_datePosted',valid_through=item.get('validThrough'),description_kind='employer_public_detail')))
    if not jobs and not re.search(r'no (?:current )?(?:jobs|openings|positions)',page.text,re.I):
        raise SourceError('Group One empty board could not be verified')
    return jobs


def bankofamerica(source,client):
    from .links import Page
    from .employer_sources import _bounds
    base='https://bankcampuscareers.tal.net'
    url=base+'/vx/lang-en-GB/mobile-0/brand-4/candidate/jobboard/vacancy/1/adv/'
    if source.get('country_scope'):
        if source['country_scope']!=['US']:raise SourceError('Unreviewed Bank of America country scope')
        r=client.get(url,respect_robots=True);r.raise_for_status()
        scopes=[]
        for block in re.findall(r'<li\b[^>]*class=["\x27]search-filter-value[^"\x27]*["\x27][^>]*>(.*?)</li>',r.text,re.S|re.I):
            label=re.search(r'<span\b[^>]*class=["\x27]facet_label["\x27][^>]*>(.*?)</span>',block,re.S|re.I)
            control=re.search(r'<input\b[^>]*name=["\x27]([A-Za-z0-9_]+)["\x27][^>]*value=["\x27](\d+)["\x27]',block,re.I)
            if label and control and _description(label[1])=='United States of America':scopes.append(control.groups())
        if len(scopes)!=1:raise SourceError('Bank of America US facet missing; scope cannot be verified')
        url+='?'+urlencode(dict(scopes))
    jobs={};expected=None;visited=set()
    for _ in range(_bounds(source)):
        if url in visited:raise SourceError('Bank of America repeated pagination URL')
        visited.add(url)
        response=client.get(url,respect_robots=True);response.raise_for_status();page=Page(response.text)
        count=re.search(r'\b(\d+) results? match!',page.text)
        if not count:raise SourceError('Bank of America public result count missing or challenge page')
        total=int(count[1])
        if expected is not None and expected!=total:raise SourceError('Bank of America result count changed')
        expected=total
        rows=re.findall(r'<tr\b[^>]*data-oppid=["\x27](\d+)["\x27][^>]*>(.*?)</tr>',response.text,re.S|re.I)
        added=0
        for identity,html in rows:
            row=Page(html);links=[(u,t) for u,t in row.anchors if '/opp/'+identity+'-' in u]
            if len(links)!=1:raise SourceError('Bank of America job row changed')
            target,title=links[0];target=re.sub(r'/xf-[^/]+','',target)
            if urlsplit(target).hostname!='bankcampuscareers.tal.net':raise SourceError('Bank of America unexpected employer namespace')
            cells=re.findall(r'<td\b[^>]*>(.*?)</td>',html,re.S|re.I)
            if len(cells)!=3:raise SourceError('Bank of America location column changed')
            loc=_description(cells[2])
            candidate=_base(source,'bofa',identity,title,target,locations=[loc],
                evidence=dict(provider='bankofamerica',provider_job_id=identity,description_kind='employer_search_summary'))
            if identity in jobs:
                if jobs[identity]!=candidate:raise SourceError('Bank of America conflicting duplicate posting')
                continue
            jobs[identity]=candidate;added+=1
        next_links=[urljoin(response.url,u) for u,t in page.anchors if t.strip()=='Next page']
        if not next_links:
            if len(jobs)!=expected:raise SourceError('Bank of America public board was truncated')
            break
        if len(set(next_links))!=1 or not added or urlsplit(next_links[0]).hostname!=urlsplit(base).hostname:
            raise SourceError('Bank of America pagination changed')
        url=next_links[0]
    else:raise SourceError('Bank of America pagination cap reached')
    # Enrich technical/research/trading programs. Other finance careers remain
    # observable search records, not falsely classified as quantitative roles.
    for job in jobs.values():
        if not re.search(r'\b(?:technology|software|engineering|quantitative|research|trading|data|product)\b',job['title'],re.I):continue
        r=client.get(job['description_url'],respect_robots=True);r.raise_for_status();page=Page(r.text);text=page.text
        identity=job['evidence']['provider_job_id']
        if not re.search(r'\bProgram ID\s+'+identity+r'\b',text) or job['title'] not in text:
            raise SourceError('Bank of America detail identity/title missing')
        employment=re.search(r'\bProgram type (.*?) Entry level\b',text)
        country=re.search(r'\bLocation (United States of America|.*?) (?:States|City)\b',text)
        description=text.split('Program description ',1)
        if not employment or not country or len(description)!=2:
            raise SourceError('Bank of America detail fields changed')
        job.update(employment_type=employment[1],country=country[1],description=description[1].split('View Cookie / Data Protection Notice',1)[0])
        job['evidence'].update(address={'addressCountry':country[1]},description_kind='employer_public_detail')
    return list(jobs.values())


def icims_board(source,client):
    from .links import Page
    from .employer_sources import _bounds
    host=source['host']
    if host not in {'careers-gtsx.icims.com','uscareers-msci.icims.com'}:
        raise SourceError('Unreviewed iCIMS board')
    base='https://'+host
    jobs={};page_count=None
    for offset in range(_bounds(source)):
        response=client.get(base+'/jobs/search',params={'ss':1,'in_iframe':1,'pr':offset},respect_robots=True)
        response.raise_for_status();page=Page(response.text)
        marker=re.search(r'\bPage (\d+) of (\d+)\b',page.text)
        if not marker:
            if offset==0 and re.search(r'There are currently no (?:jobs|job openings)',page.text,re.I):return []
            raise SourceError('iCIMS public paging marker missing')
        current,total=map(int,marker.groups())
        if current!=offset+1 or page_count is not None and page_count!=total:
            raise SourceError('iCIMS public pagination changed')
        page_count=total;added=0
        for target,title in page.anchors:
            match=re.fullmatch(r'https://'+re.escape(host)+r'/jobs/(\d+)/[^?]+(?:\?.*)?',target)
            if not match:continue
            identity=match[1]
            if identity in jobs:raise SourceError('iCIMS repeated job across pages')
            target=target.split('?')[0];title=re.sub(r'^Job Title\s+','',title)
            jobs[identity]=_base(source,'icims',host+'-'+identity,title,target,
                evidence=dict(provider='icims_board',provider_job_id=identity,board=host,description_kind='employer_search_summary'))
            added+=1
        if current==total:break
        if not added:raise SourceError('iCIMS empty page before end')
    else:raise SourceError('iCIMS page cap reached')
    for identity,job in jobs.items():
        # Other titles cannot prove internship eligibility from this search.
        # Keep the summary and enrich opportunities, including related research.
        if not re.search(r'\b(?:intern(?:ship)?|summer|co[ -]?op|fellow|residen(?:t|cy)|research program)\b',job['title'],re.I):continue
        r=client.get(job['description_url'],respect_robots=True);r.raise_for_status()
        matching=[x for x in Page(r.text).postings() if re.match(r'https://'+re.escape(host)+r'/jobs/'+identity+r'/',x.get('url',''))]
        if len(matching)!=1:raise SourceError('iCIMS exact job schema missing')
        item=matching[0];_required(item,'title','description','jobLocation')
        locs=item['jobLocation'];locs=locs if isinstance(locs,list) else [locs]
        addresses=[x.get('address',{}) for x in locs]
        job.update(title=item['title'],description=_description(item['description']),employment_type=item.get('employmentType'),posting_date=item.get('datePosted'),
            locations=[', '.join(str(x.get(k) or '') for k in ('addressLocality','addressRegion','addressCountry')).strip(', ') for x in addresses])
        job['location']='; '.join(job['locations']);job['country']=addresses[0].get('addressCountry') if addresses else None
        job['evidence'].update(description_kind='employer_public_detail',valid_through=item.get('validThrough'),posting_date_kind='employer_schema_datePosted')
    return list(jobs.values())


def panagora(source,client):
    from .links import Page
    from .employer_sources import _bounds
    url='https://www.panagora.com/careers/';jobs={};visited=set()
    for _ in range(_bounds(source)):
        if url in visited:raise SourceError('PanAgora repeated page')
        visited.add(url);r=client.get(url,respect_robots=True);r.raise_for_status();p=Page(r.text)
        if 'Open Positions' not in p.text:raise SourceError('PanAgora listing marker missing')
        if re.search('load.more|infinite.scroll',r.text,re.I):raise SourceError('PanAgora dynamic pagination needs review')
        for block in re.findall(r'<article\b[^>]*>(.*?)</article>',r.text,re.S|re.I):
            links=[(urljoin(url,u),t) for u,t in Page(block).anchors if re.fullmatch(r'https://www\.panagora\.com/careers/[^/?#]+/',urljoin(url,u))]
            title=re.search(r'<h2\b[^>]*>(.*?)</h2>',block,re.S|re.I)
            if len(links)!=1 or not title:raise SourceError('PanAgora public job row changed')
            target=links[0][0];slug=urlsplit(target).path.rstrip('/').split('/')[-1]
            if slug in jobs:raise SourceError('PanAgora repeated job across pages')
            description=client.get(target,respect_robots=True);description.raise_for_status();detail=Page(description.text)
            jobs[slug]=_base(source,'panagora',slug,_description(title[1]),target,
                description=' '.join(detail.semantic),evidence=dict(provider='panagora',provider_job_id=slug,description_kind='employer_public_detail'))
        next_links=[urljoin(url,u) for u,t in p.anchors if t.strip().lower() in ('next','next page','next »')]
        if not next_links:break
        if len(set(next_links))!=1 or not re.fullmatch(r'https://www\.panagora\.com/careers/page/\d+/',next_links[0]):raise SourceError('PanAgora pagination changed')
        url=next_links[0]
    else:raise SourceError('PanAgora pagination cap reached')
    if not jobs and not re.search('no (?:open positions|jobs found|current openings)',p.text,re.I):raise SourceError('PanAgora empty result unproven')
    return list(jobs.values())


def finance_avature(source, client):
    """Reviewed public Two Sigma directory and Macquarie campus directory."""
    from .links import Page
    from .employer_sources import _bounds
    board=source['board']
    if board=='twosigma':
        url='https://careers.twosigma.com/careers/OpenRoles'
        pattern=r'https://careers\.twosigma\.com/careers/JobDetail/[^/?]+/(\d+)'
    elif board=='macquarie':
        url='https://recruitment.macquarie.com/en_US/careers/SearchJobs/?7959=%5B421070%2C421069%5D&7959_format=14495&listFilterMode=1&jobRecordsPerPage=9&'
        pattern=r'https://recruitment\.macquarie\.com/en_US/careers/JobDetail\?jobId=(\d+)'
    else:raise SourceError('Unreviewed finance Avature board')
    host=urlsplit(url).hostname;jobs={};visited=set();expected=None
    for _ in range(_bounds(source)):
        if url in visited:raise SourceError('Finance Avature repeated pagination')
        visited.add(url);r=client.get(url,respect_robots=True);r.raise_for_status();p=Page(r.text)
        if board=='macquarie':
            count=re.search(r'\b\d+-\d+ of (\d+) results\b',p.text)
            if not count:
                # Avature omits the displayed range when the entire result set
                # fits on one page. Only trust its dedicated results legend;
                # arbitrary body text or an access challenge is not a total.
                legends=re.findall(r'<div\b[^>]*class=["\x27][^"\x27]*\blist-controls__text__legend\b[^"\x27]*["\x27][^>]*>(.*?)</div>',r.text,re.S|re.I)
                if len(legends)==1:
                    count=re.fullmatch(r'(\d+)\s+results?',_description(legends[0]))
            if not count:raise SourceError('Macquarie result count missing')
            if expected is not None and expected!=int(count[1]):raise SourceError('Macquarie result count changed')
            expected=int(count[1])
        rows=re.findall(r'<article\b[^>]*class="[^"]*article--result[^\"]*"[^>]*>(.*?)</article>',r.text,re.S)
        added=0
        for row in rows:
            links=[(u,t) for u,t in Page(row).anchors if re.fullmatch(pattern,u) and t.strip().lower() not in ('view role','view details')]
            if len(links)!=1:raise SourceError('Finance Avature result row changed')
            target,title=links[0];identity=re.fullmatch(pattern,target)[1]
            if identity in jobs:raise SourceError('Finance Avature duplicate across pages')
            candidate=_base(source,board,identity,title,target,evidence=dict(provider='finance_avature',board=board,provider_job_id=identity,description_kind='employer_search_summary'))
            if board=='twosigma':
                spans=[_description(x) for x in re.findall(r'<span class="paragraph_inner-span">(.*?)</span>',row,re.S)]
                if len(spans)!=3:raise SourceError('Two Sigma role metadata changed')
                candidate.update(location=spans[0],locations=[spans[0]],employment_type=spans[2]);candidate['evidence']['department']=spans[1]
            jobs[identity]=candidate;added+=1
        next_tags=re.findall(r'<a\b[^>]*class="[^"]*paginationNextLink[^\"]*"[^>]*>',r.text,re.S)
        if not next_tags:
            if board=='macquarie' and len(jobs)!=expected:raise SourceError('Macquarie campus directory truncated')
            if not rows and not re.search('no (?:results|jobs|roles|open positions)',p.text,re.I):raise SourceError('Finance Avature empty result unproven')
            break
        if len(next_tags)!=1 or not added:raise SourceError('Finance Avature pagination changed')
        match=re.search(r'href="([^"]+)"',next_tags[0]);next_url=unescape(match[1]) if match else ''
        if urlsplit(next_url).hostname!=host:raise SourceError('Finance Avature unexpected next host')
        url=next_url
    else:raise SourceError('Finance Avature page cap reached')
    for identity,job in jobs.items():
        # Current full-time roles stay visible as summaries. Enrich campus
        # opportunities; only their own title/type/description proves eligibility.
        if not re.search(r'intern|summer|co[ -]?op|fellow|residen',job['title']+' '+str(job.get('employment_type') or ''),re.I):continue
        r=client.get(job['description_url'],respect_robots=True);r.raise_for_status();p=Page(r.text)
        heading=[_description(x) for x in re.findall(r'<h[1-3]\b[^>]*>(.*?)</h[1-3]>',r.text,re.S)]
        if board=='twosigma':
            title_meta=re.search(r'<meta property="og:title" content="([^"]+)"',r.text)
            canonical=re.search(r'<meta property="og:url" content="([^"]+)"',r.text)
            if not canonical or unescape(canonical[1])!=job['description_url']:raise SourceError('Two Sigma canonical identity changed')
            heading=[unescape(title_meta[1])] if title_meta else []
        if job['title'] not in heading:raise SourceError('Finance Avature detail title changed')
        if board=='twosigma':
            if 'Position Summary ' not in p.text:raise SourceError('Two Sigma description missing')
            description=p.text.split('Position Summary ',1)[1].split('Back to list',1)[0].split('Learn more about Two Sigma',1)[0]
            applications=[u for u,t in p.anchors if t=='Apply' and urlsplit(u).hostname==host and parse_qs(urlsplit(u).query).get('jobId')==[identity]]
        else:
            if not re.search(r'\bJob ID '+identity+r'\b',p.text):raise SourceError('Macquarie detail identity changed')
            main=re.search(r'<main\b[^>]*>(.*?)</main>',r.text,re.S)
            if not main:raise SourceError('Macquarie description missing')
            description=Page(main[1]).text
            loc=re.search(r'Additional office locations (.*?) Job ID',description)
            if not loc:raise SourceError('Macquarie location missing')
            job.update(location=loc[1],locations=[loc[1]])
            applications=[u for u,t in p.anchors if t=='Apply now' and urlsplit(u).hostname==host and parse_qs(urlsplit(u).query).get('jobId')==[identity]]
            date=re.search(r'Job ID \d+ Date (\d{2}-[A-Za-z]{3}-\d{4})',description)
            if date:
                job['posting_date']=datetime.strptime(date[1],'%d-%b-%Y').date().isoformat()
                job['evidence']['posting_date_kind']='employer_displayed_date'
                job['evidence']['employer_displayed_date']=date[1]
        if len(set(applications))!=1:raise SourceError('Finance Avature exact application link missing')
        job.update(description=description,application_url=applications[0]);job['evidence']['description_kind']='employer_public_detail'
    return list(jobs.values())


def moodys(source,client):
    from .links import Page
    from .employer_sources import _bounds
    base='https://careers.moodys.com';url=base+'/en/category/students-and-early-careers-jobs/49841/9383648/1'
    jobs={};visited=set();expected=None
    for page_number in range(1,_bounds(source)+1):
        if url in visited:raise SourceError('Moody\'s repeated page')
        visited.add(url);r=client.get(url,respect_robots=True);r.raise_for_status()
        tag=re.search(r'<section\b[^>]*id="search-results"[^>]*>',r.text)
        attrs=dict(re.findall(r'data-([a-z-]+)="([^"]*)"',tag[0])) if tag else {}
        if int(attrs.get('current-page',0))!=page_number:raise SourceError('Moody\'s current page missing or repeated')
        total=int(attrs['total-results']);pages=int(attrs['total-pages'])
        if expected is not None and total!=expected:raise SourceError('Moody\'s result count changed')
        expected=total
        if total==0:
            if jobs:raise SourceError('Moody\'s directory became empty during pagination')
            return []
        listing=re.search(r'<ul\b[^>]*id="search-results-jobs"[^>]*>(.*?)<nav\b[^>]*id="pagination-bottom"',r.text,re.S)
        if not listing:raise SourceError('Moody\'s result list missing')
        for target,title in Page(listing[1]).anchors:
            match=re.fullmatch(r'/en/job/[^/]+/[^/]+/49841/(\d+)',target)
            if not match:continue
            identity=match[1]
            if identity in jobs:raise SourceError('Moody\'s duplicate across pages')
            jobs[identity]=_base(source,'moodys',identity,title,base+target,evidence=dict(provider='moodys',provider_job_id=identity))
        if page_number==pages or total==0:
            if len(jobs)!=total:raise SourceError('Moody\'s results truncated')
            break
        next_link=re.search(r'<a\b[^>]*class="next"[^>]*href="([^"]+)"',r.text)
        if not next_link:raise SourceError('Moody\'s next page missing')
        url=urljoin(base,unescape(next_link[1]))
        if not url.startswith(base+'/en/category/'):raise SourceError('Moody\'s pagination namespace changed')
    else:raise SourceError('Moody\'s page cap reached')
    for job in jobs.values():
        r=client.get(job['description_url'],respect_robots=True);r.raise_for_status();p=Page(r.text)
        matching=[x for x in p.postings() if x.get('url')==job['description_url']]
        if len(matching)!=1 or matching[0].get('title')!=job['title']:raise SourceError('Moody\'s exact job schema missing')
        item=matching[0];_required(item,'description','identifier')
        addresses=[x.get('address',{}) for x in item.get('jobLocation',[]) if isinstance(x,dict)]
        displayed_location=None
        if not addresses:
            location_pairs=re.findall(
                r'<h1\b[^>]*class="[^"]*\bjob-description__heading\b[^"]*"[^>]*>(.*?)</h1>\s*'
                r'<p\b[^>]*class="[^"]*\bjob-description__job-location-info\b[^"]*"[^>]*>(.*?)</p>',
                r.text,re.S)
            displayed_locations=[_description(value) for heading,value in location_pairs
                                 if _description(heading)==item['title'] and _description(value)]
            if len(displayed_locations)!=1:raise SourceError('Moody\'s job location missing')
            displayed_location=displayed_locations[0]
        applications={u for u,t in p.anchors if t=='Apply now' and urlsplit(u).hostname=='career8.successfactors.com' and parse_qs(urlsplit(u).query).get('company')==['MoodysProd'] and re.fullmatch(r'\d+',parse_qs(urlsplit(u).query).get('jobId',[''])[0])}
        if len(applications)!=1:raise SourceError('Moody\'s application identity missing for '+job['source_id'])
        application=next(iter(applications));application_id=parse_qs(urlsplit(application).query)['jobId'][0]
        if application_id!=str(item['identifier']):
            job['evidence']['application_identity_conflict']={'posting_requisition':str(item['identifier']),'application_requisition':application_id}
        locations=[', '.join(str(x.get(k) or '') for k in ('addressLocality','addressRegion','addressCountry')).strip(', ') for x in addresses]
        if displayed_location:
            locations=[displayed_location]
        job.update(description=_description(item['description']),locations=locations,location='; '.join(locations),country=addresses[0].get('addressCountry') if addresses else None,employment_type=item.get('employmentType'),posting_date=item.get('datePosted'),application_url=application)
        job['evidence'].update(description_kind='employer_public_detail',posting_date_kind='employer_schema_datePosted',requisition_id=str(item['identifier']))
        if displayed_location:job['evidence']['location_kind']='employer_displayed_detail'
        if item.get('datePosted'):
            job['evidence']['employer_schema_datePosted']=item['datePosted']
            try:job['posting_date']=datetime.strptime(item['datePosted'],'%Y-%m-%d').date().isoformat()
            except ValueError:pass
        displayed=re.search(r'\bPosted (\d{2}/\d{2}/\d{4})',p.text)
        if displayed:job['evidence']['employer_displayed_date']=displayed[1]
    return list(jobs.values())


def renaissance(source,client):
    from .links import Page
    base='https://www.rentec.com';url=base+'/Careers.action?jobs=true'
    r=client.get(url,respect_robots=True);r.raise_for_status();p=Page(r.text)
    if 'Jobs' not in p.text or re.search('pagination|load.more',r.text,re.I):raise SourceError('Renaissance directory changed')
    jobs={}
    for target,title in p.anchors:
        match=re.fullmatch(r'/Careers\.action\?jobs=true&selectedPosition=([A-Za-z0-9]+)',target)
        if not match:continue
        identity=match[1]
        if identity in jobs:raise SourceError('Renaissance duplicate job key')
        r=client.get(base+target,respect_robots=True);r.raise_for_status()
        title_loc=re.search(r'<h1 class="h1-mktg">(.*?)</h1>\s*<div class="h4-mktg mt-4">(.*?)</div>',r.text,re.S)
        if not title_loc or _description(title_loc[1])!=title:raise SourceError('Renaissance detail identity/title missing')
        body=Page(r.text).text
        if 'Responsibilities ' not in body or 'Apply Now ' not in body:raise SourceError('Renaissance description missing')
        description=body.split('Responsibilities ',1)[1].split('Apply Now ',1)[0]
        jobs[identity]=_base(source,'renaissance',identity,title,base+target,description=description,locations=[_description(title_loc[2])],evidence=dict(provider='renaissance',provider_job_id=identity,description_kind='employer_public_detail'))
    if not jobs and not re.search('no (?:open positions|current openings)',p.text,re.I):raise SourceError('Renaissance empty directory unproven')
    return list(jobs.values())

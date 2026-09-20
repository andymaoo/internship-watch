"""HSBC's public campus programme finder and employer-linked job details."""
import re
from datetime import datetime
from html import unescape
from html.parser import HTMLParser
from urllib.parse import urlsplit, urljoin, parse_qs

from .sources import SourceError, _base, _description
from .employer_sources import _bounds

BASE = 'https://www.hsbc.com/careers/students-and-graduates/find-a-programme'
API = 'https://www.hsbc.com/api/programmes/get-programmes'


class _Fields(HTMLParser):
    """Capture named public text fields, including nested markup."""
    VOID = {'area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'}

    def __init__(self, markup):
        super().__init__(convert_charrefs=True)
        self.stack, self.fields, self.active = [], {}, []
        self.feed(markup)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in self.VOID:
            return
        self.stack.append(tag)
        names = set(attrs.get('class','').split())
        names &= {'program-location','program-text__destination','program-text__short-description',
                  'jobdescription','program-text__group--type','program-text__group--opening',
                  'program-text__group--closing','program-text__group--start'}
        if attrs.get('itemprop') == 'title':
            names.add('job-title')
        for name in names:
            parts = []
            self.fields.setdefault(name,[]).append(parts)
            self.active.append((len(self.stack),parts))

    def handle_endtag(self, tag):
        if tag in self.stack:
            index = len(self.stack)-1-self.stack[::-1].index(tag)
            self.active = [(depth,parts) for depth,parts in self.active if depth <= index]
            del self.stack[index:]

    def handle_data(self, value):
        for _,parts in self.active:
            parts.append(value)

    def one(self, name):
        values = self.fields.get(name,[])
        if len(values) != 1:
            raise SourceError('HSBC missing or repeated field: '+name)
        value = ' '.join(' '.join(values[0]).split())
        if not value:
            raise SourceError('HSBC empty field: '+name)
        return value


def identity(url):
    p = urlsplit(url)
    if p.scheme != 'https' or p.hostname != 'apply.careers.hsbc.com' or p.username or p.password or p.port not in (None,443):
        return None
    match = re.fullmatch(r'/emergingtalent/job/[^/]+/(\d+)/?', p.path)
    # Public job and its employer-linked application share the numeric identity.
    match = match or re.fullmatch(r'/talentcommunity/apply/(\d+)/?', p.path)
    if not match:
        return None
    for key,values in parse_qs(p.query).items():
        if key.lower() in {'job','jobid','job_id','requisitionid'} and any(v != match[1] for v in values):
            return None
    return match[1]


def _date(value, label):
    value = value.removeprefix(label).strip()
    value = re.sub(r'(\d+)(?:st|nd|rd|th)\b',r'\1',value)
    try:
        return datetime.strptime(value,'%d %b %Y').date().isoformat()
    except ValueError as exc:
        raise SourceError('HSBC programme date format changed') from exc


def _card(markup):
    from .links import Page
    ids = re.findall(r'<li\b[^>]*\bid="programme-(\d+)-en_GB"',markup)
    if len(ids) != 1:
        raise SourceError('HSBC programme card identity missing')
    fields = _Fields(markup)
    title = fields.one('program-text__destination').removesuffix(' (opens in new window)').strip()
    links = {u for u,t in Page(markup).anchors if identity(u)}
    if len(links) != 1:
        raise SourceError('HSBC programme must link one employer job')
    url = next(iter(links)); job_id = identity(url)
    if not urlsplit(url).path.startswith('/emergingtalent/job/'):
        raise SourceError('HSBC index linked an application without a posting')
    return dict(programme_id=ids[0], job_id=job_id, title=title, url=url,
                location=fields.one('program-location'),
                summary=fields.one('program-text__short-description'),
                employment_type=fields.one('program-text__group--type').removeprefix('Programme type').strip(),
                opening=_date(fields.one('program-text__group--opening'),'Opening Date'),
                closing=_date(fields.one('program-text__group--closing'),'Closing Date'))


def _detail(item, client):
    from .links import Page, title_compatible, meaningful_description, EXPIRED, BLOCKED
    r = client.get(item['url'],respect_robots=True)
    r.raise_for_status()
    if identity(r.url) != item['job_id']:
        raise SourceError('HSBC detail redirected to a different posting')
    page = Page(r.text)
    if EXPIRED.search(page.text) or BLOCKED.search(page.text):
        raise SourceError('HSBC listed detail is unavailable; availability unverified')
    fields = _Fields(r.text)
    title = fields.one('job-title')
    if not title_compatible(item['title'],title,same_identifier=True):
        raise SourceError('HSBC detail title does not match the listed job')
    description = fields.one('jobdescription')
    if not meaningful_description(description):
        raise SourceError('HSBC detail responsibilities are missing')
    applications = {urljoin(r.url,u) for u,t in page.anchors
                    if urlsplit(urljoin(r.url,u)).path.startswith('/talentcommunity/apply/')}
    if len(applications) != 1 or identity(next(iter(applications))) != item['job_id']:
        raise SourceError('HSBC application identity differs from its posting')
    return title,description,next(iter(applications))


def hsbc(source, client):
    r = client.get(BASE,respect_robots=True);r.raise_for_status()
    settings = re.findall(r'data-component="ProgramFinder"\s+data-props-settings="([a-f0-9-]+)"\s+data-props-skip="(\d+)"\s+data-props-take="(\d+)"\s+data-props-total-count="(\d+)"',r.text)
    if len(settings) != 1:
        raise SourceError('HSBC public programme finder configuration missing')
    setting,initial,take,total = settings[0]
    initial,take,total = int(initial),int(take),int(total)
    if not 0 < take <= 100 or total > 10000:
        raise SourceError('HSBC public pagination bounds changed')
    blocks = re.findall(r'<li\b[^>]*\bid="programme-\d+-en_GB"[^>]*>.*?</li>',r.text,re.S)
    if len(blocks) != min(initial,total):
        raise SourceError('HSBC initial programme page is incomplete')
    cards,job_ids = {},set()

    def add(markup):
        card = _card(markup)
        if card['programme_id'] in cards or card['job_id'] in job_ids:
            raise SourceError('HSBC repeated programme or posting identity')
        cards[card['programme_id']] = card
        job_ids.add(card['job_id'])

    for block in blocks:
        add(block)
    # The observed page counts the optional promotional card in DOM item count,
    # while skip and the declared total count only actual programmes.
    grid = re.search(r'<ul\b[^>]*class="program-finder-grid"[^>]*>(.*?)</ul>',r.text,re.S)
    if not grid:
        raise SourceError('HSBC programme grid missing')
    dom_count = len(re.findall(r'<li\b',grid[1]))
    for _ in range(_bounds(source)):
        if len(cards) == total:
            break
        response = client.get(API,params={'skip':len(cards),'take':take,'count':dom_count,'s':setting},respect_robots=True)
        response.raise_for_status();parts=response.json()
        if not isinstance(parts,list) or not parts or any(not isinstance(v,str) for v in parts):
            raise SourceError('HSBC programme pagination returned an invalid or empty page')
        before = len(cards)
        for part in parts:
            if re.search(r'\bid="programme-\d+-en_GB"',part):
                add(part)
            elif not re.search(r'class="content-card"',part):
                raise SourceError('HSBC unknown programme pagination row')
        dom_count += len(parts)
        if len(cards) == before or len(cards) > total:
            raise SourceError('HSBC programme pagination count changed')
    if len(cards) != total:
        raise SourceError('HSBC incomplete programme pagination')
    jobs=[]
    for item in cards.values():
        description=item['summary'];title=item['title'];application=item['url'];kind='employer_search_summary'
        # All programmes were paginated. Only in-scope US opportunity candidates
        # need an additional page request; campus graduate programmes stay explicit.
        if re.search(r'\b(?:USA|United States)\b',item['location']) and re.search(r'intern|work placement|research|fellow',item['employment_type']+' '+title,re.I):
            title,description,application=_detail(item,client);kind='employer_public_detail'
        jobs.append(_base(source,'hsbc',item['job_id'],title,item['url'],description=description,
                          application_url=application,locations=[item['location']],employment_type=item['employment_type'],
                          posting_date=item['opening'],evidence=dict(provider='hsbc',provider_job_id=item['job_id'],
                          programme_id=item['programme_id'],description_kind=kind,valid_through=item['closing'],
                          posting_date_kind='employer_programme_opening_date',public_scope='campus_programme_finder')))
    return jobs

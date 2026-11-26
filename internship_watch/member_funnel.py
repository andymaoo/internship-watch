"""Reproducible member expansion; personal source definitions and filters stay intact."""
from copy import deepcopy
from pathlib import Path
import re

BROAD = {'greenhouse','lever','ashby','smartrecruiters','simplify','bankofamerica'}


def build_funnel(primary, member, additions, targets):
    primary, member = deepcopy(primary),deepcopy(member)
    original=deepcopy(primary)
    sources={s['id']:deepcopy(s) for s in member['sources']}
    for source in primary['sources']:
        if source.get('enabled',True) and source['type'] in BROAD and source['id']!='greenhouse-oldmissioncapital':
            sources.setdefault(source['id'],deepcopy(source))
    for source in additions:
        if source.get('enabled',True):
            if source['id'] in sources and source != sources[source['id']]:
                raise ValueError('Conflicting source definition: '+source['id'])
            sources.setdefault(source['id'],deepcopy(source))
    primary_by_id={s['id']:s for s in primary['sources']}
    shared=[sid for sid,s in sources.items() if s==primary_by_id.get(sid) and s['type'] in BROAD]
    directory=str(Path(primary['database']).parent/'source-snapshots')
    primary['source_snapshots']=dict(mode='write',directory=directory,sources=shared,max_age_seconds=600)
    member['source_snapshots']=dict(mode='read',directory=directory,sources=shared,max_age_seconds=600)
    member.update(sources=list(sources.values()),poll_seconds=300,collection_workers=2,
                  validation_seconds=30,validation_workers=2,validation_budget=40)
    # Keep slow/restricted employers on their existing safer source cadence.
    member['source_poll_seconds']={s['id']:1800 for s in sources.values() if s['type'] in {'workday','icims_board'}}
    normalize=lambda name:re.sub('[^a-z0-9]','',name.casefold())
    member['company_watchlist']=[]
    for company in targets['companies']:
        names={normalize(company['name']),company['id']}
        direct=[s['id'] for s in sources.values() if s['type']!='simplify' and
                (normalize(s.get('employer','')) in names or s['id'] in company.get('registry_sources',[]))]
        note='Fields: '+', '.join(company['fields'])+'. A research target, not guaranteed full employer coverage.'
        if company['name']=='Accenture':
            direct += [s['id'] for s in sources.values() if s.get('employer')=='Accenture Federal Services']
            note+=' Federal Services routes cover that subsidiary only.'
        member['company_watchlist'].append(dict(company=company['name'],fields=company['fields'],
            direct_sources=sorted(set(direct)),feed_sources=[s['id'] for s in sources.values() if s['type']=='simplify'],
            official_root=company['official_root'],note=note))
    primary.setdefault('maintenance',{}).update(member_database=member['database'],member_stale_seconds=1200,member_quiet_seconds=604800)
    assert primary['sources']==original['sources'] and primary.get('filters')==original.get('filters')
    return primary,member

import pytest
from internship_watch.member_evidence import classify_member, preview_member_listing
from internship_watch.sources import collect
from tests.test_sources import Client

@pytest.mark.parametrize('title,route',[
 ('Technology Consultant - New Grad','new-grad-tech-consulting'),
 ('Strategy Consulting Intern','intern-strategy-consulting'),
 ('Product Development Strategist - New Grad','new-grad-product-strategy'),
 ('Business Analyst - Entry Level','new-grad-business-analysis'),
 ('Technical Product Manager - New Grad','new-grad-pm'),
 ('Senior Business Analyst - New Grad',None),
 ('Business Analyst',None),
])
def test_business_role_routing(title,route):
    assert preview_member_listing(dict(title=title,location='New York, NY',posting_status='open'))['route']==route

@pytest.mark.parametrize('description,title,include',[
 ("Master's degree required.",'Software Engineer - New Grad',False),
 ('PhD required.','Software Engineer - New Grad',False),
 ("Bachelor's or master's degree required.",'Software Engineer - New Grad',True),
 ("Bachelor's degree required. Master's preferred.",'Software Engineer - New Grad',True),
 ("Bachelor's degree required. Master's degree is required for this role.",'Software Engineer - New Grad',False),
 ('','Graduate Quantitative Researcher (PhD)',False),
 ('','Graduate Quantitative Researcher (BS/MS)',True),
 ('No PhD required.','Software Engineer - New Grad',True),
])
def test_graduate_degree_requirement(description,title,include):
    decision=classify_member(dict(title=title,description=description,location='New York, NY'))
    assert (decision['decision']=='include') is include

def test_newgrad_feed_context_does_not_claim_internship_or_posting_date():
    row=dict(id='1',company_name='Example',title='Business Analyst',url='https://example.org/jobs/1',active=True,is_visible=True,locations=['New York, NY'])
    job=collect(dict(id='ng',type='simplify',url='https://example.org/feed',opportunity_type='new_grad'),Client([row]))[0]
    assert job['evidence']['feed_new_grad_context']
    assert not job['evidence']['feed_internship_context']
    assert job['posting_date'] is None
    assert classify_member(job)['opportunity_type']=='new_grad'

def test_direct_feed_identity_keeps_newgrad_context_and_rejects_senior_change(tmp_path):
    from internship_watch.storage import Store
    store=Store(tmp_path/'jobs.sqlite3')
    direct=dict(source_id='gh-test-1',title='Business Analyst',employer='Example',description='Business process analysis.',location='New York, NY',description_url='https://job-boards.greenhouse.io/test/jobs/1',application_url='https://job-boards.greenhouse.io/test/jobs/1',evidence={'provider':'greenhouse','provider_job_id':'1'})
    feed=direct|dict(source_id='simplify-1',evidence={'provider':'simplify','feed_new_grad_context':True})
    with store.transaction():
        store.upsert_job('direct',direct,classify_member(direct),1,filters={},classifier=classify_member)
        jid,_=store.upsert_job('feed',feed,classify_member(feed),1,filters={},classifier=classify_member)
        row=store.db.execute('select classification from jobs where id=?',(jid,)).fetchone()
        assert row[0]=='include'
        store.upsert_job('direct',direct,classify_member(direct),2,filters={},classifier=classify_member)
        assert store.db.execute('select classification from jobs where id=?',(jid,)).fetchone()[0]=='include'
        senior=direct|dict(title='Senior Business Analyst')
        store.upsert_job('direct',senior,classify_member(senior),3,filters={},classifier=classify_member)
        assert store.db.execute('select classification from jobs where id=?',(jid,)).fetchone()[0]=='exclude'
    store.close()

def test_graduate_colleagues_are_not_a_degree_requirement():
    row=dict(title='Software Engineer - New Grad',location='Seattle, WA',description='Our team includes PhDs and experienced developers.')
    assert classify_member(row)['decision']=='include'

def test_curated_feed_does_not_override_required_experience_or_seniority():
    row=dict(title='Business Analyst',location='Boston, MA',description='Requires 5 years of consulting experience.',evidence={'feed_new_grad_context':True})
    assert classify_member(row)['decision']=='exclude'
    assert classify_member(row|dict(title='Senior Business Analyst',description=''))['decision']=='exclude'

def test_independent_member_monitor_detects_stopped_worker_and_quiet_intake(tmp_path):
    import sqlite3
    from internship_watch.storage import Store
    from internship_watch.maintenance import Repairs,inspect_member
    jobs=Store(tmp_path/'member.sqlite3');repairs_store=Store(tmp_path/'repairs.sqlite3');repairs=Repairs(repairs_store)
    with jobs.transaction():jobs.db.execute("INSERT INTO runs(started_at,finished_at,status,summary) VALUES('2000-01-01T00:00:00+00:00','2000-01-01T00:00:00+00:00','ok','{}')")
    inspect_member(repairs,dict(maintenance={'member_database':str(jobs.path)}))
    keys={r[0] for r in repairs_store.db.execute("SELECT key FROM repair_tickets WHERE state='open'")}
    assert {'member-worker-stale','member-newgrad-quiet'} <= keys
    assert 'member-storage' not in keys
    assert inspect_member(repairs,dict(maintenance={'member_database':str(tmp_path/'missing.sqlite3')}))=={'storage_unverified':True}
    assert not (tmp_path/'missing.sqlite3').exists()
    jobs.close();repairs_store.close()

def test_member_rule_changes_do_not_flush_personal_classification_cache(tmp_path,monkeypatch):
    from pathlib import Path
    from internship_watch.storage import Store
    from internship_watch.classify import classify
    original=Path.read_bytes;version=[b'one']
    def changed(path):return original(path)+(version[0] if path.name=='member_evidence.py' else b'')
    monkeypatch.setattr(Path,'read_bytes',changed)
    p=tmp_path/'personal.sqlite3';row=dict(source_id='1',title='Software Intern',location='New York, NY')
    s=Store(p)
    with s.transaction():s.classify_cached('board',row,{},classify)
    before=s.db.execute('select fingerprint from classification_cache').fetchone()[0];s.close()
    version[0]=b'two';s=Store(p)
    with s.transaction():s.classify_cached('board',row,{},classify)
    assert s.db.execute('select fingerprint from classification_cache').fetchone()[0]==before
    s.close()

def test_expansion_preserves_personal_filters_and_reuses_sources_without_duplication():
    from internship_watch.member_funnel import build_funnel
    p=dict(database='/state/private.sqlite3',filters={'degrees':['bachelor']},sources=[dict(id='gh',type='greenhouse',slug='observed',employer='Example')])
    m=dict(database='/member/jobs.sqlite3',sources=[p['sources'][0]],member_feed=True)
    targets=dict(companies=[dict(id='example',name='Example',fields=['business_analysis'],official_root='https://example.org')])
    a,b=build_funnel(p,m,[],targets)
    assert len(b['sources'])==1 and b['poll_seconds']==300
    assert a['sources']==p['sources'] and a['filters']==p['filters']
    assert 'source_snapshots' not in p and 'source_snapshots' not in m
    assert b['source_snapshots']['sources']==['gh']
    assert b['company_watchlist'][0]['direct_sources']==['gh']

def test_company_catalog_has_fifty_targets_per_field_and_no_duplicate_sources():
    import json
    from pathlib import Path
    catalog=json.loads(Path('config/business-employer-targets.json').read_text())
    assert len(catalog['fields'])==5
    assert all(len(names)==len(set(names))==50 for names in catalog['fields'].values())
    assert len({c['id'] for c in catalog['companies']})==len(catalog['companies'])
    sources=json.loads(Path('config/business-sources.json').read_text())
    assert len({s['id'] for s in sources})==len(sources)
    assert not any('internal' in s.get('host','') or s.get('host')=='www.icims.com' for s in sources)

@pytest.mark.parametrize('title,description,kind,category',[
 ('Research Analyst (Economics & Finance)','Candidates must be graduating between December 2026 and June 2027.','new_grad','business_analysis'),
 ('Energy Analyst Intern (Economics)','Working toward an undergraduate degree.','internship','business_analysis'),
 ('Associate Consultant','This consulting firm is hiring candidates graduating in 2027.','new_grad','strategy_consulting'),
 ('Business Analyst','Our founder graduated in 1998.','', 'business_analysis'),
])
def test_cohort_and_economic_business_research_evidence(title,description,kind,category):
    row=dict(title=title,description=description,location='Boston, MA')
    d=classify_member(row)
    assert d['opportunity_type']==kind and d['category']==category

def test_internship_cohort_does_not_turn_intern_into_mixed_newgrad_listing():
    d=classify_member(dict(title='Business Analyst Intern',description='Candidates must be graduating in 2027.',location='Boston, MA'))
    assert d['decision']=='include' and d['opportunity_type']=='internship'

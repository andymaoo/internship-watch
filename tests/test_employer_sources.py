import copy
from contextlib import closing
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from internship_watch.sources import collect, SourceError
from internship_watch.employer_validation import spec_for, check_posting
from internship_watch.runner import run_once, collections
from internship_watch.http import HttpClient
from internship_watch.storage import Store, url_identity
from tests.test_sources import Client, Response
from tests.test_pipeline import job, verified


class BothClient(Client):
    post = Client.get


def sr(identity):
    return dict(id=str(identity), name='Product Manager Intern', company={'identifier':'Example','name':'Example'},
                visibility='PUBLIC', location={'fullLocation':'New York, NY, United States','country':'us'},
                typeOfEmployment={'label':'Internship'})


def ef(identity):
    return dict(id=identity, name='Software Engineering Intern', locations=['US, CA, Santa Clara'],
                positionUrl='/careers/job/'+str(identity), atsJobId='JR'+str(identity))


class EmployerSourceTests(unittest.TestCase):
    def test_smartrecruiters_complete_pages_and_private_rejection(self):
        source=dict(id='sr',type='smartrecruiters',slug='Example')
        client=Client(dict(offset=0,totalFound=2,content=[sr(1)]),dict(offset=1,totalFound=2,content=[sr(2)]))
        rows=collect(source,client)
        self.assertEqual(len(rows),2)
        self.assertEqual(client.calls[1][1]['params']['offset'],1)
        self.assertEqual(rows[0]['employment_type'],'Internship')
        self.assertIsNone(rows[0]['posting_date'])
        for bad in [dict(sr(1),visibility='INTERNAL'),dict(sr(1),company={'identifier':'Other'})]:
            with self.assertRaises(SourceError):collect(source,Client(dict(offset=0,totalFound=1,content=[bad])))

    def test_smartrecruiters_changed_total_or_duplicate_fails(self):
        source=dict(id='sr',type='smartrecruiters',slug='Example')
        for second in [dict(offset=1,totalFound=3,content=[sr(2)]),dict(offset=1,totalFound=2,content=[sr(1)]),dict(offset=1,totalFound=2,content=[])]:
            with self.assertRaises(SourceError):
                collect(source,Client(dict(offset=0,totalFound=2,content=[sr(1)]),second))

    def test_eightfold_scope_pagination_and_overlap_between_searches(self):
        source=dict(id='ef',type='eightfold',domain='nvidia.com',searches=[{'filter_job_type':'intern (fixed term)'},{'query':'intern'}])
        client=Client({'data':{'count':2,'positions':[ef(1)]}},{'data':{'count':2,'positions':[ef(2)]}}, {'data':{'count':1,'positions':[ef(1)]}})
        rows=collect(source,client)
        self.assertEqual(len(rows),2)
        self.assertEqual(client.calls[1][1]['params']['start'],1)
        self.assertTrue(all(kwargs['respect_robots'] for _,kwargs in client.calls))
        self.assertIsNone(rows[0]['posting_date'])
        self.assertEqual(rows[0]['evidence']['ats_job_id'],'JR1')

    def test_eightfold_never_accepts_truncated_or_wrong_job_url(self):
        source=dict(id='ef',type='eightfold',domain='microsoft.com',searches=[{'query':'intern'}],max_pages=1)
        for data in [{'count':2,'positions':[ef(1)]},{'count':1,'positions':[dict(ef(1),positionUrl='/careers/job/2')]},{'count':1,'positions':[]}]:
            with self.assertRaises(SourceError):collect(source,Client({'data':data}))

    def test_eightfold_explicit_sort_must_be_honored_and_still_rejects_duplicates(self):
        source=dict(id='ef',type='eightfold',domain='nvidia.com',searches=[{'query':'intern'}],sort_by='timestamp')
        first={'data':{'sortBy':'timestamp','count':2,'positions':[ef(1)]}}
        second={'data':{'sortBy':'timestamp','count':2,'positions':[ef(2)]}}
        client=Client(first,second)
        self.assertEqual(len(collect(source,client)),2)
        self.assertTrue(all(k['params']['sort_by']=='timestamp' for u,k in client.calls))
        with self.assertRaises(SourceError):collect(source,Client(first,first))
        with self.assertRaises(SourceError):collect(source,Client({'data':{'sortBy':'relevance','count':1,'positions':[ef(1)]}}))

    def test_uber_pagination_is_bounded_and_retains_description(self):
        item=dict(Id='1',Title='Software Intern',Urls=[{'IsDefault':True,'Url':'/en/jobs/1/'}],Description='Build software during this internship.',Locations=[{'City':'Seattle','Country':'United States'}])
        client=Client(dict(totalJobs=1,totalPages=1,page=1,jobs=[item]))
        rows=collect(dict(id='uber',type='uber'),client)
        self.assertEqual(rows[0]['description_url'],'https://jobs.uber.com/en/jobs/1/')
        self.assertIn('internship',rows[0]['description'])
        with self.assertRaises(SourceError):collect(dict(id='uber',type='uber'),Client(dict(totalJobs=2,totalPages=1,page=1,jobs=[item])))

    def test_amazon_reads_qualifications_and_deduplicates_search_scopes(self):
        item=dict(id='1',title='Software Intern',job_path='/en/jobs/1/software-intern',is_intern=True,
                  description='Software internship.',basic_qualifications='Must be a PhD student.',country_code='USA')
        client=Client(dict(hits=1,jobs=[item]),dict(hits=1,jobs=[item]))
        rows=collect(dict(id='amazon',type='amazon',queries=['intern','student']),client)
        self.assertEqual(len(rows),1)
        self.assertIn('PhD',rows[0]['description'])
        self.assertEqual(rows[0]['employment_type'],'Internship')
        self.assertTrue(client.calls[0][1]['respect_robots'])

    def test_rippling_location_variants_are_one_job_but_distinct_ids_stay_separate(self):
        def row(oid,jid,location):return dict(objectID=oid,jobId=jid,name='Software Intern',url='https://ats.rippling.com/rippling/jobs/'+jid,locationNames=[location])
        client=BothClient(dict(nbHits=3,nbPages=2,page=0,hits=[row('1','a','New York'),row('2','a','Seattle')]),dict(nbHits=3,nbPages=2,page=1,hits=[row('3','b','Seattle')]))
        rows=collect(dict(id='r',type='rippling',app_id='1234567890',index='careers_en-US_production',public_search_key='public-fixture'),client)
        self.assertEqual(len(rows),2)
        self.assertEqual(rows[0]['locations'],['New York','Seattle'])

    def test_bytedance_preserves_employment_and_nested_country(self):
        item=dict(id='123',title='AI Research Intern',description='Research machine learning.',requirement='Bachelor student.',recruit_type={'en_name':'Intern'},city_info={'en_name':'Seattle','parent':{'en_name':'Washington','parent':{'en_name':'United States'}}})
        client=BothClient(dict(code=0,data={'count':1,'job_post_list':[item]}))
        rows=collect(dict(id='bd',type='bytedance'),client)
        self.assertEqual(rows[0]['employment_type'],'Intern')
        self.assertIn('United States',rows[0]['location'])
        self.assertIn('Bachelor',rows[0]['description'])
        self.assertEqual(client.calls[0][1]['headers']['website-path'],'en')

    def test_snap_full_board_schema_and_intern_evidence(self):
        item=dict(id='R123',title='AI Research Intern',absolute_url='https://wd1.myworkdaysite.com/recruiting/snapchat/snap/job/Seattle/AI-Intern_R123',External_Posting='1',jobPostingSite='Snap Inc.',employment_type='Intern',offices=[{'location':'Seattle, WA'}])
        rows=collect(dict(id='snap',type='snap'),Client({'body':[{'_source':item}],'aggs':{'type':['Intern']}}))
        self.assertEqual(rows[0]['description_url'],'https://careers.snap.com/job?id=R123')
        with self.assertRaises(SourceError):collect(dict(id='snap',type='snap'),Client({'body':[]}))

    def test_bloomberg_follows_links_and_records_source_overlap(self):
        def page(ids,next_offset=None):
            text='<div aria-label="3 results"></div>'
            for identity in ids:text+=f'<article class="article article--result"><a href="https://bloomberg.avature.net/careers/JobDetail/Software-Intern/{identity}">Software Intern</a><span class="list-item-location">New York</span></article>'
            if next_offset:text+=f'<a href="https://bloomberg.avature.net/careers/SearchJobs/?jobOffset={next_offset}" aria-label="Go to Next Page">Next</a>'
            return text
        responses=[Mock(text=page([1,2],2)),Mock(text=page([2]))]
        client=Mock();client.get.side_effect=responses
        rows=collect(dict(id='bb',type='bloomberg'),client)
        self.assertEqual(len(rows),2)
        self.assertEqual(rows[0]['evidence']['overlapping_source_rows'],1)
        client.get.side_effect=[Mock(text=page([1,2],2)),Mock(text=page([1,2],2))]
        with self.assertRaises(SourceError):collect(dict(id='bb',type='bloomberg'),client)


class EmployerValidationTests(unittest.TestCase):
    def test_verified_employer_name_aliases_do_not_invalidate_each_other(self):
        for name,alias in [('Anduril Industries','Anduril'),('together','Together AI'),('scale','Scale AI'),
                           ('Akuna Capital','Akuna Capital University'),('Voleon Group','The Voleon Group'),
                           ('Five Rings','Five Rings Capital'),('Schonfeld Strategic Advisors','Schonfeld'),
                           ('Voloridge Investment Management','Voloridge'),('Cboe Global Markets','Cboe'),
                           ('RBC Capital Markets','Royal Bank of Canada')]:
            with self.subTest(name=name),tempfile.TemporaryDirectory() as directory,closing(Store(Path(directory)/'jobs.db')) as store:
                feed=job('feed');feed.update(employer=alias,description_url='https://job-boards.greenhouse.io/test/jobs/123',evidence={'provider':'simplify'})
                feed['application_url']=feed['description_url']
                direct=copy.deepcopy(feed);direct.update(source_id='gh-test-123',employer=name,evidence={'provider':'greenhouse','provider_job_id':'123'})
                with store.transaction():
                    jid,_=store.upsert_job('feed',feed,{'decision':'include'},None,baseline=True)
                    self.assertEqual(store.upsert_job('direct',direct,{'decision':'include'},None)[0],jid)
                    store.record_check(jid,dict(status='open',posting_status='open',application_status='open',checked_at='2026-09-19T00:00:00+00:00'),'2099-01-01T00:00:00+00:00')
                for _ in range(2):
                    for source,row in [('feed',feed),('direct',direct)]:
                        with store.transaction():store.upsert_job(source,row,{'decision':'include'},None)
                        self.assertEqual(store.rows('SELECT last_checked FROM jobs')[0]['last_checked'],'2026-09-19T00:00:00+00:00')
                direct['employer']='Unrelated Employer'
                with store.transaction():store.upsert_job('direct',direct,{'decision':'include'},None)
                self.assertIsNone(store.rows('SELECT last_checked FROM jobs')[0]['last_checked'])

    def test_feed_alias_does_not_reset_fresh_direct_validation_each_poll(self):
        with tempfile.TemporaryDirectory() as directory:
            with closing(Store(Path(directory)/'jobs.db')) as store:
                feed=job('feed-1');feed.update(employer='NVIDIA',description_url='https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite/job/US/Intern_JR123',evidence={'provider':'simplify'})
                feed['application_url']=feed['description_url']
                direct=copy.deepcopy(feed);direct.update(source_id='ef-123',description_url='https://jobs.nvidia.com/careers/job/456',description='This internship requires a PhD. Develop software and AI models.',evidence={'provider':'eightfold','domain':'nvidia.com','provider_job_id':'456','ats_job_id':'JR123'})
                direct['application_url']=direct['description_url']
                with store.transaction():
                    jid,_=store.upsert_job('feed',feed,{'decision':'include'},None,baseline=True)
                    other,_=store.upsert_job('direct',direct,{'decision':'include'},None)
                    self.assertEqual(other,jid)
                    store.record_check(jid,dict(status='unverified',posting_status='open',application_status='unverified',checked_at='2026-09-19T00:00:00+00:00',final_description_url=direct['description_url']),'2099-01-01T00:00:00+00:00')
                before=store.rows('SELECT original_url,last_checked,next_check,posting_status,description,baseline FROM jobs')[0]
                for _ in range(2):
                    with store.transaction():
                        store.upsert_job('feed',feed,{'decision':'include'},None)
                        self.assertEqual(store.rows('SELECT original_url,last_checked,next_check,posting_status,description,baseline FROM jobs')[0],before)
                        store.upsert_job('direct',direct,{'decision':'include'},None)
                        self.assertEqual(store.rows('SELECT original_url,last_checked,next_check,posting_status,description,baseline FROM jobs')[0],before)
                self.assertEqual(json.loads(store.rows("SELECT payload FROM source_records WHERE source='feed'")[0]['payload'])['description_url'],feed['description_url'])
                changed=copy.deepcopy(feed);changed['title']='Unrelated Accountant'
                with store.transaction():store.upsert_job('feed',changed,{'decision':'exclude'},None)
                self.assertIsNone(store.rows('SELECT last_checked FROM jobs')[0]['last_checked'])

    def test_snap_typographic_duties_heading_is_meaningful(self):
        from internship_watch.links import meaningful_description
        description = ('Snap builds tools for people to communicate. What you’ll do: '
                       'Build and optimize backend services, investigate performance problems, '
                       'write automated tests, collaborate with other engineers, review designs, '
                       'and document your findings for the team.')
        self.assertTrue(meaningful_description(description))

    @patch('internship_watch.runner.heartbeat')
    def test_every_requested_company_can_queue_a_new_qualifying_record_once(self,_):
        config=json.loads((Path(__file__).resolve().parents[1]/'config.example.json').read_text(encoding='utf8'))
        self.assertEqual(len(config['company_watchlist']),212)
        self.assertEqual(sum(bool(c['direct_sources']) for c in config['company_watchlist']),188)
        configured={s['id'] for s in config['sources'] if s.get('enabled',True)}
        for company in config['company_watchlist']:
            self.assertTrue(set(company['direct_sources']+company['feed_sources']) <= configured)
        with tempfile.TemporaryDirectory() as directory:
            cfg=dict(database=str(Path(directory)/'jobs.db'),sources=[{'id':'contract'}],filters=config['filters'],validation_budget=300,delivery_budget=300)
            sender=Mock();client=Mock()
            run_once(cfg,collector=lambda *_:[],client=client,validator=verified,sender=sender)
            fixtures=[]
            for index,company in enumerate(config['company_watchlist']):
                row=job(str(100000+index));row['employer']=company['company'];fixtures.append(row)
            run_once(cfg,collector=lambda *_:fixtures,client=client,validator=verified,sender=sender)
            self.assertEqual(sender.send.call_count,212)
            run_once(cfg,collector=lambda *_:fixtures,client=client,validator=verified,sender=sender)
            self.assertEqual(sender.send.call_count,212)

    def test_fresh_eightfold_detail_proves_posting_only(self):
        url='https://jobs.nvidia.com/careers/job/123'
        detail=dict(ef(123),publicUrl=url,jobDescription='This software engineering internship is available to current bachelor students. You will design APIs, develop backend services, review technical requirements, write automated tests, investigate distributed system failures, collaborate with product teams, document research findings, optimize database queries, and present a final project to mentors. Candidates should have experience with Python, SQL, version control, algorithms, networking, and Linux. The team supports flexible schedules and provides regular feedback throughout the summer program.')
        response=Response(dict(status=200,data=detail),spec_for(url)['api']);response.status_code=200
        client=Mock();client.get.return_value=response
        result=check_posting(dict(employer='NVIDIA',title=detail['name']),spec_for(url),client)
        self.assertEqual(result['status'],'open')
        self.assertNotIn('application_url',result)
        for bad in [dict(detail,id=456),dict(detail,name='Unrelated accounting position'),dict(detail,publicUrl='https://jobs.nvidia.com/careers/job/456')]:
            response.data=dict(status=200,data=bad)
            self.assertEqual(check_posting(dict(employer='NVIDIA',title=detail['name']),spec_for(url),client)['status'],'unverified')

    def test_cross_source_url_aliases_and_distinct_ids(self):
        pairs=[('https://amazon.jobs/en/jobs/123/title?source=simplify','https://www.amazon.jobs/en/jobs/123/other'),('https://jobs.bytedance.com/en/position/123/detail','https://joinbytedance.com/search/123'),('https://jobs.smartrecruiters.com/LinkedIn3/123-title?oga=true','https://jobs.smartrecruiters.com/LinkedIn3/123')]
        for left,right in pairs:self.assertEqual(url_identity(left),url_identity(right))
        self.assertNotEqual(url_identity(pairs[0][0]),url_identity('https://amazon.jobs/en/jobs/124/title'))

    def test_alias_migration_preserves_history(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'jobs.db';store=Store(path)
            row=job();row['description_url']='https://amazon.jobs/en/jobs/123/title';row['application_url']=row['description_url']
            with store.transaction():
                jid,_=store.upsert_job('old',row,{'decision':'include'},None,baseline=True)
                first=store.rows('SELECT first_seen FROM jobs')[0]['first_seen']
                store.db.execute("DELETE FROM meta WHERE key='company_url_aliases_v1'")
                store.db.execute("DELETE FROM identities WHERE identity LIKE 'url:amazon:%'")
            store.close();store=Store(path)
            row=dict(row,source_id='new',description_url='https://www.amazon.jobs/en/jobs/123/new-title')
            with store.transaction():new,_=store.upsert_job('new',row,{'decision':'include'},None)
            self.assertEqual(jid,new)
            self.assertEqual(store.rows('SELECT first_seen,baseline FROM jobs'),[dict(first_seen=first,baseline=1)])
            store.close()

    @patch('internship_watch.runner.heartbeat')
    def test_parallel_collection_new_job_delivery_and_restart(self,_):
        with tempfile.TemporaryDirectory() as directory:
            cfg=dict(database=str(Path(directory)/'jobs.db'),sources=[{'id':'one'},{'id':'two'}],collection_workers=2)
            client=HttpClient(resolve_dns=False);sender=Mock()
            barrier=threading.Barrier(2)
            def collector(source,_):barrier.wait(timeout=5);return [job(source['id']+'123')]
            run_once(cfg,collector=collector,client=client,validator=verified,sender=sender)
            sender.send.assert_not_called()
            def changed(source,_):return [job(source['id']+'123')]+([job('new456')] if source['id']=='one' else [])
            run_once(cfg,collector=changed,client=client,validator=verified,sender=sender)
            self.assertEqual(sender.send.call_count,1)
            run_once(cfg,collector=changed,client=client,validator=verified,sender=sender)
            self.assertEqual(sender.send.call_count,1)
            client.close()

    def test_worker_sessions_share_rate_limits_not_connections(self):
        parent=HttpClient(resolve_dns=False);child=parent.fork()
        self.assertIsNot(parent.session,child.session)
        self.assertIs(parent._last_request,child._last_request)
        self.assertIs(parent.host_cooldowns,child.host_cooldowns)
        self.assertIs(parent._lock,child._lock)
        child.close();parent.close()


if __name__=='__main__':unittest.main()

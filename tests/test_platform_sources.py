import copy
import json
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import Mock

from internship_watch.sources import collect, SourceError
from internship_watch.platform_sources import workday_spec
from internship_watch.employer_validation import spec_for, check_posting
from internship_watch.storage import Store, url_identity
from internship_watch.classify import classify
from tests.test_employer_sources import BothClient
from tests.test_sources import Client
from tests.test_pipeline import job

BOARD='https://example.wd1.myworkdayjobs.com/External'


def wd_row(identity, title='Software Engineering Intern'):
    return dict(title=title,externalPath='/job/New-York/Software-Intern_'+identity,
                locationsText='New York, NY',postedOn='Posted Yesterday')


def wd_detail(identity='R123',posted=True):
    return dict(jobPostingInfo=dict(id='uuid-'+identity,title='Software Engineering Intern',
        jobDescription='As an intern you will build software and test scalable backend services. '*10,
        jobReqId=identity.split('-')[0],jobPostingSiteId='External',posted=posted,canApply=True,
        externalUrl=BOARD+wd_row(identity)['externalPath'],location='New York, NY',
        country={'descriptor':'United States of America'},timeType='Full time',startDate='2027-06-01'),
        hiringOrganization={'name':'Example, Inc.'})


class PlatformSourceTests(unittest.TestCase):
    def test_workday_zero_total_sentinel_and_full_pagination(self):
        source=dict(id='wd',type='workday',url=BOARD,employer='Example',queries=['intern'])
        client=BothClient(dict(total=2,jobPostings=[wd_row('R1')]),
            dict(total=0,jobPostings=[wd_row('R2')]),wd_detail('R1'),wd_detail('R2'))
        rows=collect(source,client)
        self.assertEqual(len(rows),2)
        self.assertEqual(client.calls[1][1]['json']['offset'],1)
        self.assertTrue(all(call[1]['respect_robots'] for call in client.calls))
        self.assertIsNone(rows[0]['posting_date'])
        self.assertEqual(rows[0]['evidence']['employer_start_date'],'2027-06-01')
        for bad in [dict(total=0,jobPostings=[]),dict(total=3,jobPostings=[wd_row('R2')]),dict(total=0,jobPostings=[wd_row('R1')])]:
            with self.assertRaises(SourceError):collect(source,BothClient(dict(total=2,jobPostings=[wd_row('R1')]),bad))

    def test_workday_live_facets_do_not_match_international(self):
        source=dict(id='wd',type='workday',url=BOARD,employer='Example',queries=['intern'],opportunity_facets=True)
        facets=[dict(facetParameter='workerSubType',values=[
            dict(id='international',descriptor='International Fixed Term'),dict(id='intern',descriptor='Intern (Fixed Term)')])]
        client=BothClient(dict(total=50,jobPostings=[],facets=facets),dict(total=1,jobPostings=[wd_row('R123')]),wd_detail())
        rows=collect(source,client)
        self.assertEqual(client.calls[1][1]['json']['appliedFacets'],{'workerSubType':['intern']})
        self.assertEqual(rows[0]['employment_type'],'Internship')
        self.assertEqual(rows[0]['evidence']['structured_opportunity_scope'],'internship_worker_type')

    def test_workday_empty_facets_fall_back_and_cap_never_succeeds(self):
        source=dict(id='wd',type='workday',url=BOARD,queries=['intern'],opportunity_facets=True,max_pages=1)
        client=BothClient(dict(total=3,jobPostings=[],facets=[]),dict(total=3,jobPostings=[wd_row('R1')]))
        with self.assertRaises(SourceError):collect(source,client)
        self.assertEqual(client.calls[1][1]['json']['searchText'],'intern')

    def test_workday_apply_board_and_posting_instances_are_distinct(self):
        self.assertEqual(workday_spec('https://ebay.wd5.myworkdayjobs.com/apply')['site'],'apply')
        a=BOARD+wd_row('R123')['externalPath'];b=BOARD+wd_row('R123-1')['externalPath']
        self.assertEqual(workday_spec(a+'/apply')['id'],'R123')
        self.assertEqual(url_identity(a),url_identity(a.replace('/External/','/en-US/External/')+'/apply'))
        self.assertNotEqual(url_identity(a),url_identity(b))
        self.assertNotEqual(url_identity(a),url_identity(a.replace('/External/','/Internal/')))
        self.assertNotEqual(url_identity(a),url_identity(a.replace('example.wd1','other.wd1')))

    def test_workday_posting_validity_does_not_assert_application_access(self):
        url=BOARD+wd_row('R123')['externalPath'];record=job();record.update(description_url=url)
        spec=spec_for(url)
        for posted,status in [(True,'open'),(False,'closed')]:
            result=check_posting(record,spec,Client(wd_detail(posted=posted)))
            self.assertEqual(result['status'],status)
            self.assertNotIn('application_status',result)
        bad=wd_detail();bad['jobPostingInfo']['jobReqId']='R999'
        self.assertEqual(check_posting(record,spec,Client(bad))['status'],'unverified')
        denied=Mock();denied.get.side_effect=TimeoutError('test timeout')
        self.assertEqual(check_posting(record,spec,denied)['status'],'unverified')

    def test_jibe_pagination_dedupes_searches_and_rejects_incomplete(self):
        source=dict(id='jibe',type='jibe',url='https://careers.amd.com',queries=['intern','co-op'])
        one={'data':dict(slug='123',req_id='123',title='Software Intern',description='Intern building software',
            searchable=True,internal=False,country_code='US',posted_date='2026-09-19')}
        two=copy.deepcopy(one);two['data'].update(slug='124',req_id='124')
        rows=collect(source,Client(dict(totalCount=2,jobs=[one]),dict(totalCount=2,jobs=[two]),dict(totalCount=1,jobs=[one])))
        self.assertEqual(len(rows),2)
        self.assertEqual(rows[0]['posting_date'],'2026-09-19')
        with self.assertRaises(SourceError):collect(source,Client(dict(totalCount=2,jobs=[one]),dict(totalCount=2,jobs=[])))
        self.assertEqual(url_identity('https://careers.amd.com/jobs/123?icims=1'),url_identity('https://campus-amd.icims.com/jobs/123/login'))
        self.assertNotEqual(url_identity('https://careers.amd.com/jobs/123'),url_identity('https://www.github.careers/jobs/123'))

    def test_atlassian_exact_duplicates_only_and_portal_identity(self):
        one=dict(id=123,title='Product Manager Intern',locations=['New York, NY'],category='Interns',
            overview='Internship in software product management',portalJobPost=dict(id=123,portalUrl='https://careers-americas.icims.com/jobs/123/product-manager-intern/job'))
        rows=collect(dict(id='atl',type='atlassian'),Client([one,copy.deepcopy(one)]))
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['employment_type'],'Internship')
        self.assertEqual(url_identity(rows[0]['description_url']),url_identity(rows[0]['application_url']))
        with self.assertRaises(SourceError):collect(dict(id='atl',type='atlassian'),Client([one,dict(one,title='Different Position')]))
        other=copy.deepcopy(one);other['portalJobPost']['portalUrl']='https://other.icims.com/jobs/123/foo/job'
        with self.assertRaises(SourceError):collect(dict(id='atl',type='atlassian'),Client([other]))

    def test_oracle_pages_and_exact_details(self):
        def page(offset,identity,total=2):
            return {'items':[dict(SiteNumber='CX_45001',Offset=offset,TotalJobsCount=total,
                requisitionList=[dict(Id=identity,Title='Software Intern',PrimaryLocation='New York, NY')])]}
        def detail(identity):return {'items':[dict(Id=identity,Title='Software Intern',PrimaryLocation='New York, NY',
            ExternalDescriptionStr='Software internship for university students',PrimaryLocationCountry='US',
            ExternalPostedStartDate='2026-09-19')]}
        c=Client(page(0,'123'),detail('123'),page(1,'124'),detail('124'))
        rows=collect(dict(id='oracle',type='oracle',employer='Oracle'),c)
        self.assertEqual(len(rows),2)
        self.assertIn('offset=1',c.calls[2][1]['params']['finder'])
        self.assertIn('Student/Intern',c.calls[0][1]['params']['finder'])
        self.assertEqual(url_identity(rows[0]['description_url']),url_identity(rows[0]['description_url'].replace('CX_45001','jobsearch')))
        with self.assertRaises(SourceError):collect(dict(id='oracle',type='oracle'),Client(page(0,'123'),detail('999')))

    def test_shared_bytedance_tiktok_ids_not_titles_are_deduplicated(self):
        self.assertEqual(url_identity('https://lifeattiktok.com/search/123'),url_identity('https://joinbytedance.com/search/123'))
        self.assertNotEqual(url_identity('https://lifeattiktok.com/search/123'),url_identity('https://joinbytedance.com/search/124'))
        with tempfile.TemporaryDirectory() as folder,closing(Store(Path(folder)/'jobs.db')) as store:
            one=job('123');one.update(employer='ByteDance',description_url='https://joinbytedance.com/search/123',application_url='https://joinbytedance.com/search/123')
            two=dict(one,source_id='tiktok-123',employer='TikTok',description_url='https://lifeattiktok.com/search/123',application_url='https://lifeattiktok.com/search/123')
            with store.transaction():
                first=store.upsert_job('byte',one,{'decision':'include'},None)[0]
                self.assertEqual(store.upsert_job('tik',two,{'decision':'include'},None)[0],first)
            self.assertEqual(len(store.rows('SELECT * FROM jobs')),1)


class ClassificationCacheTests(unittest.TestCase):
    def test_oracle_veteran_program_audience_requires_review(self):
        record=job(title='Software Engineer Intern - OVIP')
        record['description']='Oracle Veteran Internship Program. Military veterans and spouses are the program audience. '+record['description']
        result=classify(record,{'countries':['US']})
        self.assertEqual(result['decision'],'ambiguous')
        self.assertIn('program_audience',result['eligibility'])
        self.assertEqual(classify(record,{'countries':['US'],'confirmed_program_eligibility':['oracle_ovip']})['decision'],'include')
        record['title']='Software Engineering Intern';record['description']='We welcome veterans and military spouses. '+job()['description']
        self.assertEqual(classify(record,{'countries':['US']})['decision'],'include')

    def test_restart_reuses_only_identical_job_filters_and_classifier_revision(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'jobs.db';one=job();filt={'countries':['US']}
            classifier=Mock(return_value={'decision':'include','positive_opportunity_evidence':True})
            with closing(Store(path)) as store,store.transaction():store.classify_cached('test',one,filt,classifier)
            with closing(Store(path)) as store,store.transaction():
                self.assertEqual(store.classify_cached('test',one,filt,classifier)['decision'],'include')
                self.assertEqual(classifier.call_count,1)
                store.classify_cached('test',dict(one,description='Permanent full-time position'),filt,classifier)
                store.classify_cached('test',one,{'countries':['CA']},classifier)
                store.classifier_revision='new-rules'
                store.classify_cached('test',one,{'countries':['CA']},classifier)
                self.assertEqual(classifier.call_count,4)

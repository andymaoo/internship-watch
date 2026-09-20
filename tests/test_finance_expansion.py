import copy
import unittest
from internship_watch.classify import classify
from internship_watch.sources import collect, SourceError
from internship_watch.links import provider_spec
from internship_watch.storage import url_identity, custom_greenhouse_identity
from tests.test_employer_sources import BothClient
from tests.test_platform_sources import wd_row, wd_detail, BOARD

class FinanceRegressionTests(unittest.TestCase):
    def test_unchanged_resolved_payload_reuses_current_classification(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        from internship_watch.storage import Store
        job={'source_id':'1','employer':'Example','title':'Software Engineer Intern','location':'New York, NY','description':'As an intern, build backend software.','description_url':'https://example.com/jobs/1','application_url':'https://example.com/jobs/1'}
        with tempfile.TemporaryDirectory() as directory:
            store=Store(Path(directory)/'jobs.db');filters={'countries':['US']}
            decision=classify(job,filters)
            with patch('internship_watch.storage.classify',wraps=classify) as compute:
                for _ in range(2):store.upsert_job('direct',job,decision,None,filters=filters,classification_is_current=True)
                self.assertEqual(compute.call_count,0)
            store.close()

    def test_employer_requisition_conflict_keeps_application_unverified(self):
        from unittest.mock import patch
        from internship_watch.links import validate_job
        job={'title':'Data Analyst Intern','description_url':'https://example.com/jobs/43','application_url':'https://example.com/apply/44','evidence':{'application_identity_conflict':{'posting_requisition':'43','application_requisition':'44'}}}
        def check(job,url,kind,client,cache):return {'kind':kind,'status':'open','evidence':['expected_job_identity_verified'],'final_url':url}
        with patch('internship_watch.links._check',side_effect=check):result=validate_job(job,object())
        self.assertEqual(result['posting_status'],'open')
        self.assertEqual(result['application_status'],'unverified')
        self.assertIn('employer_posting_and_application_requisition_conflict',result['checks'][-1]['evidence'])

    def test_degree_alternatives_without_apostrophes(self):
        job=dict(title='Software Engineer Intern',description='Pursuing a bachelors, masters, or PhD degree in computer science.',location='Chicago, IL')
        self.assertEqual(classify(job,{'degrees':['bachelor']})['decision'],'include')
        job['description']='A PhD is required. Proficient in MS Office.'
        result=classify(job,{'degrees':['bachelor']})
        self.assertEqual(result['decision'],'exclude')
        self.assertNotIn('master',result['eligibility']['degrees'])

    def test_summer_analyst_requires_linked_internship_evidence(self):
        job=dict(title='2027 Research Summer Analyst',description='The Internship Program Our 10-week summer program gives you real work. Your Role Perform quantitative research and develop trading strategies.',location='Greenwich, CT')
        self.assertEqual(classify(job,{})['decision'],'include')
        job['description']='Perform quantitative research. Our company also offers an internship program.'
        self.assertEqual(classify(job,{})['decision'],'ambiguous')
        job['title']='2027 Business Development Summer Analyst'
        self.assertNotEqual(classify(job,{})['decision'],'include')

    def test_eu_greenhouse_uses_global_api_and_preserves_destination(self):
        url='https://job-boards.eu.greenhouse.io/imc/jobs/123'
        spec=provider_spec(url)
        self.assertEqual(spec['canonical'],url)
        self.assertEqual(spec['api'],'https://boards-api.greenhouse.io/v1/boards/imc/jobs/123')
        self.assertEqual(url_identity(url),url_identity('https://boards.greenhouse.io/imc/jobs/123'))
        self.assertNotEqual(url_identity(url),url_identity('https://job-boards.eu.greenhouse.io/other/jobs/123'))

    def test_repeated_identical_greenhouse_parameter_is_same_identity(self):
        job=dict(source_id='gh-aqr-123',description_url='https://careers.aqr.com/jobs?gh_jid=123&gh_jid=123',evidence={'provider':'greenhouse','provider_job_id':'123'})
        self.assertEqual(custom_greenhouse_identity(job),('aqr','123'))
        job['description_url']+='&gh_jid=456'
        self.assertIsNone(custom_greenhouse_identity(job))

    def test_workday_country_facets_and_authoritative_title_update(self):
        source=dict(id='wd',type='workday',url=BOARD,employer='Example',queries=['intern'],country_scope=['US'],opportunity_facets=True)
        discovery=dict(total=50,jobPostings=[],facets=[dict(facetParameter='locationCountry',values=[dict(id='usa',descriptor='United States of America'),dict(id='uk',descriptor='United Kingdom')]),dict(facetParameter='workerSubType',values=[dict(id='intern',descriptor='Intern')])])
        detail=wd_detail();detail['jobPostingInfo']['title']='Software Engineering Intern - Summer 2027'
        client=BothClient(discovery,dict(total=1,jobPostings=[wd_row('R123')]),detail)
        jobs=collect(source,client)
        self.assertEqual(client.calls[1][1]['json']['appliedFacets'],{'locationCountry':['usa'],'workerSubType':['intern']})
        self.assertEqual(jobs[0]['title'],detail['jobPostingInfo']['title'])
        self.assertEqual(jobs[0]['evidence']['search_title'],'Software Engineering Intern')
        bad=copy.deepcopy(detail);bad['jobPostingInfo']['jobReqId']='OTHER'
        with self.assertRaises(SourceError):collect(source,BothClient(discovery,dict(total=1,jobPostings=[wd_row('R123')]),bad))

class FinanceAdapterTests(unittest.TestCase):
    def html_client(self,*pages):
        from unittest.mock import Mock
        client=Mock();responses=[]
        for page in pages:
            r=Mock();r.text=page;r.status_code=200;r.url='https://bankcampuscareers.tal.net/vx/candidate/jobboard/vacancy/1/adv/';r.raise_for_status.return_value=None;responses.append(r)
        client.get.side_effect=responses
        return client

    def test_moodys_nested_lists_pagination_and_conflicting_application(self):
        import json
        def page(number,identity,next_page=False):
            return f'''<section id="search-results" data-current-page="{number}" data-total-results="2" data-total-pages="2"></section><ul id="search-results-jobs"><li><a href="/en/job/new-york/data-intern/49841/{identity}">Data Analyst Intern</a><ul><li>US</li></ul></li></ul><nav id="pagination-bottom">'''+('<a class="next" href="/en/category/students-and-early-careers-jobs/49841/9383648/1/2">Next</a>' if next_page else '')
        def detail(identity,req,app):
            item={'@type':'JobPosting','url':f'https://careers.moodys.com/en/job/new-york/data-intern/49841/{identity}','title':'Data Analyst Intern','description':'Interns analyze data.','identifier':req,'jobLocation':[{'address':{'addressCountry':'United States','addressLocality':'New York'}}],'datePosted':'2026-09-01','employmentType':'Full Time'}
            return '<script type="application/ld+json">'+json.dumps(item)+'</script>'+f'<a href="https://career8.successfactors.com/sfcareer/jobreqcareer?jobId={app}&company=MoodysProd">Apply now</a>'
        source={'id':'moodys','type':'moodys','employer':"Moody's"}
        rows=collect(source,self.html_client(page(1,'100',True),page(2,'101'),detail('100','42','42'),detail('101','43','44')))
        self.assertEqual(len(rows),2)
        self.assertEqual(rows[1]['evidence']['application_identity_conflict'],{'posting_requisition':'43','application_requisition':'44'})
        self.assertNotIn('application_identity_conflict',rows[0]['evidence'])
        with self.assertRaises(SourceError):collect(source,self.html_client(page(1,'100',True),page(1,'100')))

    def test_twosigma_complete_pagination_and_not_campus_fulltime(self):
        def page(identity,next_page=False):
            return f'''<article class="article article--result"><a href="https://careers.twosigma.com/careers/JobDetail/Role/{identity}">Software Engineer - Campus Full-Time</a><span class="paragraph_inner-span">United States - NY New York</span><span class="paragraph_inner-span">Engineering</span><span class="paragraph_inner-span">Early Careers</span></article>'''+('<a class="paginationNextLink" href="https://careers.twosigma.com/careers/OpenRoles/?jobOffset=10">Next</a>' if next_page else '')
        source={'id':'twosigma','type':'finance_avature','board':'twosigma','employer':'Two Sigma'}
        rows=collect(source,self.html_client(page('1',True),page('2')))
        self.assertEqual(len(rows),2)
        self.assertNotEqual(classify(rows[0],{})['decision'],'include')
        with self.assertRaises(SourceError):collect(source,self.html_client(page('1',True),page('1')))

    def test_renaissance_specific_positions_no_internship_invented(self):
        source={'id':'rentec','type':'renaissance','employer':'Renaissance Technologies'}
        index='<h1>Jobs</h1><a href="/Careers.action?jobs=true&selectedPosition=researchScientist">Research Scientist</a>'
        detail='<h1 class="h1-mktg">Research Scientist</h1><div class="h4-mktg mt-4">New York, NY</div><p>Responsibilities Develop statistical trading models.</p><p>Apply Now </p><form>Internship question from an unrelated form</form>'
        rows=collect(source,self.html_client(index,detail))
        self.assertEqual(rows[0]['location'],'New York, NY')
        self.assertNotIn('unrelated',rows[0]['description'])
        self.assertNotEqual(classify(rows[0],{})['decision'],'include')

    def test_deshaw_excludes_internal_records_and_rejects_fetch_error(self):
        import json
        from pathlib import Path
        data=json.loads((Path(__file__).parent/'fixtures/finance/deshaw.json').read_text())
        page=lambda x:'<script id="__NEXT_DATA__" type="application/json">'+json.dumps(x)+'</script>'
        rows=collect({'id':'deshaw','type':'deshaw','employer':'D. E. Shaw'},self.html_client(page(data)))
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['employment_type'],'Intern')
        self.assertIsNone(rows[0]['posting_date'])
        data['props']['pageProps']['jobsFetchingError']=True
        with self.assertRaises(SourceError):collect({'id':'deshaw','type':'deshaw'},self.html_client(page(data)))

    def test_trexquant_private_rows_and_detail_identity(self):
        import json
        from pathlib import Path
        from tests.test_sources import Client
        data=json.loads((Path(__file__).parent/'fixtures/finance/trexquant.json').read_text())
        item=data['jobs'][0];private=dict(item,shortcode='PRIVATE',confidential=True)
        detail=dict(item,full_description='As an intern, develop quantitative trading models.')
        rows=collect({'id':'trex','type':'trexquant','employer':'Trexquant Investment'},Client({'jobs':[item,private]},detail))
        self.assertEqual(len(rows),1)
        self.assertIsNone(rows[0]['posting_date'])
        with self.assertRaises(SourceError):collect({'id':'trex','type':'trexquant'},Client(data,dict(detail,shortcode='OTHER')))

    def test_bankofamerica_pagination_proves_declared_total(self):
        def page(identity,total=2,next_page=False):
            return f'''<p>{total} results match!</p><table><tr data-oppid="{identity}"><td>{identity}</td><td><a href="https://bankcampuscareers.tal.net/vx/lang-en-GB/xf-example/candidate/so/pm/1/pl/1/opp/{identity}-Finance/en-GB">Finance Analyst</a></td><td>New York, NY</td></tr></table>'''+('<a href="?start=1">Next page</a>' if next_page else '')
        source={'id':'bofa','type':'bankofamerica','employer':'Bank of America'}
        rows=collect(source,self.html_client(page('1',next_page=True),page('2')))
        self.assertEqual(len(rows),2)
        self.assertNotIn('/xf-',rows[0]['description_url'])
        with self.assertRaises(SourceError):collect(source,self.html_client(page('1')))
        with self.assertRaises(SourceError):collect(source,self.html_client(page('1',next_page=True),page('1')))
        a=rows[0]['description_url'];b=a.replace('/candidate/','/xf-other/candidate/')
        self.assertEqual(url_identity(a),url_identity(b))
        self.assertNotEqual(url_identity(a),url_identity(rows[1]['description_url']))

    def test_icims_complete_pages_and_no_false_intern_evidence(self):
        def page(n,identity):return f'<p>Page {n} of 2</p><a href="https://careers-gtsx.icims.com/jobs/{identity}/software-developer/job">Job Title Software Developer</a>'
        source=dict(id='gts',type='icims_board',host='careers-gtsx.icims.com')
        rows=collect(source,self.html_client(page(1,123),page(2,124)))
        self.assertEqual(len(rows),2)
        self.assertNotEqual(classify(rows[0],{})['decision'],'include')
        with self.assertRaises(SourceError):collect(source,self.html_client(page(1,123),page(2,123)))

    def test_workday_hostname_is_not_always_tenant(self):
        from internship_watch.platform_sources import workday_spec
        spec=workday_spec('https://osv-cci.wd1.myworkdayjobs.com/CCICareers')
        self.assertEqual(spec['tenant'],'osv_cci')
        self.assertEqual(spec['api'],'https://osv-cci.wd1.myworkdayjobs.com/wday/cxs/osv_cci/CCICareers')

    def test_bankofamerica_us_states_are_not_part_of_country(self):
        index='<p>1 results match!</p><table><tr data-oppid="12"><td>12</td><td><a href="https://bankcampuscareers.tal.net/vx/candidate/so/pm/1/pl/1/opp/12-software/en-GB">Software Engineer Summer Analyst</a></td><td>Charlotte, NC</td></tr></table>'
        detail='<h1>Software Engineer Summer Analyst</h1><p>Program ID 12 Region Americas Location United States of America States North Carolina, Texas City Charlotte, NC Program Global Technology Program type Summer internship Entry level Undergraduate Program description Build software. Pursuing a bachelor degree.</p>'
        rows=collect({'id':'bofa','type':'bankofamerica'},self.html_client(index,detail))
        self.assertEqual(rows[0]['country'],'United States of America')
        self.assertEqual(classify(rows[0],{'countries':['US'],'degrees':['bachelor']})['decision'],'include')

    def test_posting_cache_discards_expired_and_bounds_response_memory(self):
        import time
        from unittest.mock import Mock
        from internship_watch.links import _prune_posting_cache
        bodies=[Mock() for _ in range(70)]
        cache={str(i):(time.monotonic()-(301 if i==0 else 0),bodies[i],'stamp') for i in range(70)}
        _prune_posting_cache(cache)
        self.assertEqual(len(cache),64)
        self.assertNotIn('0',cache)
        self.assertIn('69',cache)
        for body in bodies[:6]:body.close.assert_called_once()
        for body in bodies[6:]:body.close.assert_not_called()

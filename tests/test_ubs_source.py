import copy
import unittest
from unittest.mock import Mock

from internship_watch.ubs_source import PublicSearch, canonical, identity, API
from internship_watch.sources import collect, SourceError
from internship_watch.employer_validation import spec_for, check_posting
from internship_watch.storage import url_identity

TITLE = 'Software & AI Internship'
DESCRIPTION = 'Your internship responsibilities include developing production software and machine learning models. You will build and test APIs, analyze datasets, and collaborate with engineers throughout this ten-week paid internship.'
LANDING = ''.join(f'<input id="{k}" value="{v}">' for k,v in
    dict(partnerId='25008',siteId='5131',CookieValue='test-anonymous',__RequestVerificationToken='test-csrf').items())


def row(job='1', site='5131', restricted=False):
    return dict(Link=canonical(site,job), isSocialReferralJobRestricted=restricted,
        Questions=[dict(QuestionName=k,Value=v) for k,v in
            dict(reqid=job,siteid=site,jobtitle=TITLE,jobdescription=DESCRIPTION,formtext23='United States - New York',lastupdated='18-Sep-2026').items()])


def page(rows, total=2):
    return dict(JobsCount=total,Jobs={'Job':rows},SortFields=[{'Name':'LastUpdated'}, {'Name':'JobTitle'}])


def detail(job='1', site='5131', active=True):
    return {'ServiceResponse':{'Jobdetails':dict(Link=canonical(site,job),Title=TITLE,
        isActive=active,isSocialReferralJobRestricted=False,
        JobDetailQuestions=[dict(VerityZone=k,AnswerValue=v) for k,v in
            dict(reqid=job,siteid=site,jobtitle='Software &amp; AI Internship',jobdescription=DESCRIPTION,
                 formtext23='United States - New York',formtext59='Pursuing a bachelor degree.',
                 formtext60='Unrelated company boilerplate',lastupdated='18-Sep-2026').items()])}}


def client(*payloads):
    c=Mock(); landing=Mock();landing.text=LANDING;landing.raise_for_status.return_value=None
    c.get.return_value=landing;responses=[]
    for payload in payloads:
        response=Mock();response.json.return_value=payload;response.url=API+'test'
        response.raise_for_status.return_value=None;responses.append(response)
    c.post.side_effect=responses
    return c


class UBSTests(unittest.TestCase):
    def test_alphabetical_public_order_avoids_repeated_date_boundaries(self):
        c=client()
        def respond(url, **kwargs):
            payload=kwargs['json']
            if url.endswith('MatchedJobs'):
                data=page([row()])
            elif payload['SortType']=='JobTitle':
                data=page([row(str(payload['pageNumber']))])
            else:
                # Live LastUpdated pages repeated exact IDs at a tied-date boundary.
                data=page([row()])
            response=Mock(); response.json.return_value=data; response.url=url
            response.raise_for_status.return_value=None
            return response
        c.post.side_effect=respond
        rows=PublicSearch(c).rows()
        self.assertEqual([f['reqid'] for _,f in rows],['1','2'])
        self.assertEqual([x.kwargs['json']['SortType'] for x in c.post.call_args_list[1:]],
                         ['JobTitle','JobTitle'])

    def test_missing_reviewed_sort_fails_before_pagination(self):
        data=page([row()]);data['SortFields']=[{'Name':'LastUpdated'}]
        c=client(data)
        with self.assertRaisesRegex(SourceError,'count/order'):
            PublicSearch(c).rows()
        self.assertEqual(c.post.call_count,1)

    def test_mixed_technology_placement_is_reviewable_not_guaranteed(self):
        from internship_watch.classify import classify
        job=dict(title='2027 Summer Internship - Technology',location='Raleigh, NC',
            description='Based on your experience, you could be placed as a Technology Engineer Intern, Data Engineer Intern, or Technology Support Analyst Intern.')
        result=classify(job,{})
        self.assertEqual(result['decision'],'ambiguous')
        self.assertEqual(result['category'],'data_engineering')
        job['title']='2027 Human Resources Internship'
        self.assertEqual(classify(job,{})['decision'],'exclude')

    def test_complete_explicit_sorted_pagination_and_private_exclusion(self):
        c=client(page([row('99')]),page([row()]),page([row('2',restricted=True)]),detail())
        jobs=collect(dict(id='ubs',type='ubs',employer='UBS',country_scope=['US']),c)
        self.assertEqual(len(jobs),1)
        self.assertEqual(jobs[0]['title'],TITLE)
        self.assertIsNone(jobs[0]['posting_date'])
        self.assertEqual(jobs[0]['evidence']['source_updated_at'],'18-Sep-2026')
        self.assertNotIn('boilerplate',jobs[0]['description'])
        self.assertNotIn('test-anonymous',str(jobs))
        self.assertEqual([x.kwargs['json'].get('pageNumber') for x in c.post.call_args_list][1:3],[1,2])
        self.assertTrue(all(x.kwargs['respect_robots'] for x in c.post.call_args_list))

    def test_repeated_truncated_and_changing_pages_fail(self):
        for second in (page([row()]),page([]),page([row('2')],3)):
            with self.assertRaises(SourceError):PublicSearch(client(page([row()]),page([row()]),second)).rows()

    def test_foreign_board_uses_exact_row_site(self):
        c=client(page([row(site='5132')],1),page([row(site='5132')],1),detail(site='5132'))
        jobs=collect(dict(id='ubs',type='ubs',employer='UBS'),c)
        self.assertEqual(jobs[0]['evidence']['board'],'5132')
        self.assertEqual(c.post.call_args_list[-1].kwargs['json']['jobSiteId'],'5132')

    def test_wrong_job_or_restricted_detail_is_unverified(self):
        for bad in (detail('2'),detail(site='5132'),detail()):
            if bad==detail():bad['ServiceResponse']['Jobdetails']['isSocialReferralJobRestricted']=True
            check=check_posting(dict(employer='UBS',title=TITLE),spec_for(canonical('5131','1')),client(bad))
            self.assertEqual(check['status'],'unverified')

    def test_fresh_exact_employer_posting_open_closed_missing(self):
        for state in (True,False):
            check=check_posting(dict(employer='UBS',title=TITLE),spec_for(canonical('5131','1')),client(detail(active=state)))
            self.assertEqual(check['status'],'open' if state else 'closed')
            self.assertNotIn('application_url',check)
        check=check_posting(dict(employer='UBS',title=TITLE),spec_for(canonical('5131','1')),client({'ServiceResponse':{'Jobdetails':None}}))
        self.assertEqual(check['status'],'unverified')

    def test_identity_ignores_navigation_but_preserves_board_and_job(self):
        url=canonical('5131','1')
        self.assertEqual(url_identity(url),url_identity(url+'&frmSiteId=5132'))
        self.assertNotEqual(url_identity(url),url_identity(canonical('5132','1')))
        self.assertNotEqual(url_identity(url),url_identity(canonical('5131','2')))
        self.assertIsNone(identity(url+'&jobid=2'))
        self.assertIsNone(identity(url.replace('25008','12345')))
        self.assertIsNone(identity(url.replace('jobs.ubs.com','evil.example')))

    def test_wrong_employer_cannot_verify(self):
        check=check_posting(dict(employer='Other',title=TITLE),spec_for(canonical('5131','1')),client(detail()))
        self.assertEqual(check['status'],'unverified')


if __name__=='__main__':unittest.main()

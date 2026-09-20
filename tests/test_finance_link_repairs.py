import json
import unittest
from unittest.mock import patch

from internship_watch.classify import classify
from internship_watch.links import employer_compatible, meaningful_description, validate_job
from tests.test_links import Client, response, DESCRIPTION


class FinanceLinkRepairs(unittest.TestCase):
    def test_current_sophomore_program_is_excluded_for_junior(self):
        job=dict(title='Software Development Internship',location='New York, NY',
            description='This program will focus on current sophomores (those in their second year of university). Current sophomores are invited to apply.')
        result=classify(job,{'student_years':['junior']})
        self.assertEqual(result['decision'],'exclude')
        self.assertEqual(result['eligibility']['student_years'],['sophomore'])

    def test_observed_legal_employers_require_their_exact_tenant(self):
        pairs=[('CME Group','CME Chicago Mercantile Exchange Inc.','cmegroup.wd1.myworkdayjobs.com'),
               ('S&P Global','1115 KENSHO TECHNOLOGIES LLC','spgi.wd5.myworkdayjobs.com'),
               ('PIMCO','0200 Pacific Investment Mgt Co. LLC','pimco.wd1.myworkdayjobs.com'),
               ('BMO Capital Markets','Bank of Montreal','bmo.wd3.myworkdayjobs.com')]
        for display,legal,host in pairs:
            self.assertTrue(employer_compatible(display,legal,'https://'+host+'/jobs/12345'))
            self.assertFalse(employer_compatible(display,legal,'https://other.wd1.myworkdayjobs.com/jobs/12345'))
            self.assertFalse(employer_compatible(display,'Other employer','https://'+host+'/jobs/12345'))

    def test_real_intern_responsibilities_without_magic_heading(self):
        for prefix in ['Interns interact with trading groups.', 'Summer interns will be mentored by experienced software developers.',
                       'Join the firm as software developer interns.']:
            self.assertTrue(meaningful_description(prefix+' Design and deploy scalable applications for automated trading activities. Work closely with engineers to build analysis tools and develop efficient, thoroughly tested computer code.'))
        self.assertFalse(meaningful_description('About our company. We run summer internship programs and offer generous employee benefits. '+('Welcome to our careers website. '*6)))

    def test_talnet_form_wrapped_description_has_separate_application_status(self):
        url='https://bankcampuscareers.tal.net/vx/candidate/so/pm/1/pl/1/opp/12345-Software/en-GB'
        job=dict(employer='Bank of America',title='Software Engineer Intern',description_url=url)
        html='<h1>Software Engineer Intern</h1><form>Program ID 12345 Program description '+DESCRIPTION+' View Cookie / Data Protection Notice</form>'
        result=validate_job(job,Client({url:response(html)}))
        self.assertEqual(result['posting_status'],'open')
        self.assertEqual(result['application_status'],'unverified')
        result=validate_job(job,Client({url:response(html.replace('Program ID 12345','Program ID 54321'))}))
        self.assertEqual(result['posting_status'],'unverified')

    def test_404_page_does_not_hide_fresh_active_employer_api(self):
        url='https://job-boards.greenhouse.io/example/jobs/123456'
        api='https://boards-api.greenhouse.io/v1/boards/example/jobs/123456'
        job=dict(employer='Example',title='Software Engineer Intern',description_url=url)
        data=dict(id=123456,title=job['title'],company_name='Example',absolute_url=url,content=DESCRIPTION)
        result=validate_job(job,Client({url:response('Not Found',404),api:response(json.dumps(data))}))
        self.assertEqual(result['posting_status'],'open')
        self.assertEqual(result['application_status'],'closed')
        self.assertIn('employer_api_active_but_posting_page_unavailable',result['checks'][1]['evidence'])

    def test_accented_employer_schema_retains_raw_name_for_comparison(self):
        url='https://careers.societegenerale.com/en/job-offers/intern-26000AAA-en'
        job=dict(employer='Société Générale',title='Data Analyst Intern',description_url=url)
        item={'@type':'JobPosting','title':job['title'],'hiringOrganization':{'name':'Societe Generale'},'description':DESCRIPTION}
        html='<script type="application/ld+json">'+json.dumps(item)+'</script>'
        self.assertEqual(validate_job(job,Client({url:response(html)}))['posting_status'],'open')


if __name__=='__main__':unittest.main()

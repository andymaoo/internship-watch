import json
import unittest

import requests

from internship_watch.links import VALIDATOR_VERSION, provider_spec, validate_job


DESCRIPTION = "Responsibilities: As a Software Engineer Intern, you will develop backend software services, write and maintain automated tests, review code with the engineering team, and document your implementation. Qualifications: currently enrolled in a bachelor's degree in computer science."
FORM = '<form>Upload resume <input type="file" name="resume"> Submit application</form>'
JOB = {"employer":"Example", "title":"Software Engineer Intern", "description_url":"https://jobs.example.com/jobs/123456", "application_url":"https://jobs.example.com/jobs/123456/apply"}


def response(text, status=200, url=None):
    result = requests.Response()
    result.status_code = status
    result._content = text.encode()
    result.url = url
    return result


def page(description=DESCRIPTION, title=JOB["title"]):
    return f"<title>{title}</title><h1>{title}</h1><p>Example</p><article>{description}</article>"


class Client:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        value = self.responses[url]
        if isinstance(value, Exception):
            raise value
        if not value.url:
            value.url = url
        return value


class LinkTests(unittest.TestCase):
    def test_documented_board_namespace_allows_dots_without_path_traversal(self):
        suffix='/8f06f221-8777-4a4d-b035-40882db5f4a0'
        self.assertEqual(provider_spec('https://jobs.ashbyhq.com/mistral.ai'+suffix)['board'],'mistral.ai')
        self.assertIsNone(provider_spec('https://jobs.ashbyhq.com/..'+suffix))

    def client(self, description=None, application=None):
        return Client({JOB["description_url"]:description if description is not None else response(page()), JOB["application_url"]:application if application is not None else response(page()+FORM)})

    def test_both_destinations_and_meaningful_identity(self):
        client = self.client()
        result = validate_job(JOB, client)
        self.assertEqual(result["status"], "open")
        self.assertEqual(result["posting_status"],"open")
        self.assertEqual(result["application_status"],"open")
        self.assertEqual(len(client.calls), 2)
        self.assertTrue(all(c[1]["respect_robots"] for c in client.calls))

    def test_expired_description(self):
        result = validate_job(JOB, self.client(description=response(page("This job is no longer available."))))
        self.assertEqual(result["status"], "closed")

    def test_generic_careers_redirect(self):
        result = validate_job(JOB, self.client(application=response("<h1>Careers at Example</h1>", url="https://jobs.example.com/careers")))
        self.assertEqual(result["status"], "closed")

    def test_http_200_is_insufficient(self):
        result = validate_job(JOB, self.client(description=response("Welcome to our great company")))
        self.assertEqual(result["status"], "unverified")

    def test_other_job_not_accepted(self):
        result = validate_job(JOB, self.client(description=response(page(title="Accountant Intern"), url="https://jobs.example.com/jobs/999999")))
        self.assertEqual(result["status"], "unverified")

    def test_same_title_different_requisition_not_accepted(self):
        payload = {"@type":"JobPosting", "title":JOB["title"], "hiringOrganization":{"name":"Example"}, "description":DESCRIPTION}
        body = '<script type="application/ld+json">'+json.dumps(payload)+"</script>"
        result = validate_job(JOB,self.client(description=response(body,url="https://jobs.example.com/jobs/999999")))
        self.assertEqual(result["status"],"unverified")

    def test_missing_description(self):
        result = validate_job(JOB, self.client(description=response(page("Apply now"))))
        self.assertEqual(result["status"], "unverified")

    def test_navigation_and_job_title_are_not_a_description(self):
        body = '<title>Software Engineer Intern</title><h1>Software Engineer Intern</h1><p>Example</p><nav>' + ('Internship careers research experience company jobs news products and services. '*20) + '</nav><footer>Our internship opportunities are available worldwide.</footer>'
        self.assertEqual(validate_job(JOB,self.client(description=response(body)))["status"],"unverified")

    def test_explicit_description_div(self):
        body = '<title>Software Engineer Intern</title><h1>Software Engineer Intern</h1><p>Example</p><div class="job-description">'+DESCRIPTION+'</div>'
        self.assertEqual(validate_job(JOB,self.client(description=response(body)))["status"],"open")

    def test_timeouts_rate_limits_and_blocking_never_close(self):
        for blocked in [requests.Timeout("timeout"), requests.ConnectionError("down"), response("limit",429), response("forbidden",403), response("down",503), response("Verify you are human"), response("Sign in to apply")]:
            with self.subTest(blocked=str(blocked)):
                self.assertEqual(validate_job(JOB, self.client(application=blocked))["status"], "unverified")

    def test_404_and_410_close(self):
        for code in [404,410]:
            self.assertEqual(validate_job(JOB, self.client(application=response("Gone",code)))["status"], "closed")

    def test_challenge_body_with_404_is_unverified(self):
        for code in [404,410]:
            for body in ["Access denied", "Verify you are human"]:
                self.assertEqual(validate_job(JOB,self.client(application=response(body,code)))["status"],"unverified")

    def test_malformed_and_private_urls_not_requested(self):
        for url in ["no url", "javascript:alert(1)", "https://user:pass@example.com/123456", "http://127.0.0.1/123456", "http://localhost/123456"]:
            client = Client({})
            result = validate_job(dict(JOB, description_url=url, application_url=url),client)
            self.assertEqual(result["status"], "unverified")
            self.assertEqual(client.calls, [])

    def test_same_destination_only_fetched_once(self):
        client = self.client(description=response(page()+FORM))
        result = validate_job(dict(JOB, application_url=JOB["description_url"]),client)
        self.assertEqual(result["status"], "open")
        self.assertEqual(len(client.calls), 1)
        self.assertEqual(len(result["checks"]), 2)

    def test_same_failed_destination_not_retried_twice(self):
        client = self.client(description=requests.Timeout("down"))
        result = validate_job(dict(JOB,application_url=JOB["description_url"]),client)
        self.assertEqual(result["status"],"unverified")
        self.assertEqual(len(client.calls),1)

    def test_jsonld_expiry(self):
        payload = {"@type":"JobPosting", "title":JOB["title"], "hiringOrganization":{"name":"Example"}, "description":DESCRIPTION, "validThrough":"2000-01-01T00:00:00Z"}
        body = '<script type="application/ld+json">'+json.dumps(payload)+"</script>"
        self.assertEqual(validate_job(JOB, self.client(description=response(body)))["status"], "closed")

    def test_application_form_can_omit_description(self):
        form = page("<form>Upload resume <input name='cv'> Submit application</form>")
        self.assertEqual(validate_job(JOB, self.client(application=response(form)))["status"], "open")

    def test_foreign_employer_schema_rejected(self):
        payload = {"@type":"JobPosting", "title":JOB["title"], "hiringOrganization":{"name":"Different"}, "description":DESCRIPTION}
        body = '<script type="application/ld+json">'+json.dumps(payload)+"</script>"
        self.assertEqual(validate_job(JOB, self.client(description=response(body)))["status"], "unverified")

    def test_description_only_is_not_an_application(self):
        client = self.client()
        result = validate_job(dict(JOB,application_url=JOB["description_url"]),client)
        self.assertEqual(result["status"],"unverified")
        self.assertEqual(result["posting_status"],"open")
        self.assertEqual(result["application_status"],"unverified")
        self.assertIn("application_destination_not_verified",result["checks"][-1]["evidence"])
        self.assertEqual(validate_job(JOB,self.client(application=response(page())))["status"],"unverified")
        search_form = '<form>Search jobs<input name="query"></form><p>Apply for this job with a resume.</p>'
        self.assertEqual(validate_job(JOB,self.client(application=response(page()+search_form)))["status"],"unverified")

    def test_outbound_apply_destination_discovered_and_checked(self):
        linked = page()+'<a href="/jobs/123456/apply">Apply now</a>'
        client = self.client(description=response(linked))
        result = validate_job(dict(JOB,application_url=JOB["description_url"]),client)
        self.assertEqual(result["status"],"open")
        self.assertEqual(result["final_application_url"],JOB["application_url"])
        self.assertEqual(len(client.calls),2)
        self.assertEqual(result["validator_version"],VALIDATOR_VERSION)

    def test_generic_apply_link_not_verified(self):
        linked = page()+'<a href="/careers">Apply now</a>'
        client = self.client(description=response(linked))
        client.responses['https://jobs.example.com/careers'] = response('<h1>Careers</h1>Find a position at Example')
        result = validate_job(dict(JOB,application_url=JOB["description_url"]),client)
        self.assertEqual(result["status"],"unverified")

    def test_javascript_apply_link_not_followed(self):
        linked = page()+'<a href="javascript:apply()">Apply now</a>'
        client = self.client(description=response(linked))
        result = validate_job(dict(JOB,application_url=JOB["description_url"]),client)
        self.assertEqual(result["status"],"unverified")
        self.assertEqual(len(client.calls),1)

    def test_application_form_boilerplate_is_not_job_description(self):
        body = '<title>Software Engineer Intern</title><h1>Software Engineer Intern</h1><p>Example</p><main><form>Upload resume<input type="file" name="resume"> Level of Education What degree are you currently enrolled in? PhD Master\'s Bachelor\'s Other. Work Eligibility: Are you authorized to work for this position? Requirements: all applicants must agree to our privacy policy. This internship requires an application. Submit application</form></main>'
        client = self.client(description=response(body))
        result = validate_job(dict(JOB,application_url=JOB["description_url"]),client)
        self.assertEqual(result["status"],"unverified")
        self.assertEqual(result["posting_status"],"unverified")
        self.assertEqual(result["application_status"],"open")
        self.assertEqual(result["checks"][0]["status"],"unverified")
        self.assertEqual(result["checks"][-1]["status"],"open")
        self.assertNotIn("description",result)

    def test_same_identifier_allows_minor_title_words_but_not_other_role(self):
        for title in ['Software Engineering Internship', 'Software Backend Engineer Intern - Summer 2027']:
            result=validate_job(JOB,self.client(description=response(page(DESCRIPTION.replace(JOB['title'],title),title=title))))
            self.assertEqual(result['posting_status'],'open')
        other=page(DESCRIPTION.replace(JOB['title'],'Hardware Engineer Intern'),title='Hardware Engineer Intern')
        self.assertEqual(validate_job(JOB,self.client(description=response(other)))['posting_status'],'unverified')

    def test_workday_legal_entity_requires_matching_brand_and_tenant(self):
        url='https://nxp.wd3.myworkdayjobs.com/careers/job/Data-Intern_R-10065538'
        job=dict(JOB,employer='NXP Semiconductors',description_url=url,application_url=url)
        schema={'@type':'JobPosting','title':JOB['title'],'hiringOrganization':{'name':'US63 NXP USA Inc.'},'description':DESCRIPTION}
        body='<script type="application/ld+json">'+json.dumps(schema)+'</script>'
        self.assertEqual(validate_job(job,Client({url:response(body)}))['posting_status'],'open')
        foreign='https://foreign.wd3.myworkdayjobs.com/careers/job/Data-Intern_R-10065538'
        self.assertEqual(validate_job(dict(job,description_url=foreign,application_url=foreign),Client({foreign:response(body)}))['posting_status'],'unverified')

    def test_meaningful_role_details_without_legacy_keyword(self):
        description='Role Details: Interns will contribute to real data innovation projects involving data analysis and machine learning pipelines, AI evaluation frameworks, enterprise integration, applied research, and automation for large organizational datasets.'
        self.assertEqual(validate_job(JOB,self.client(description=response(page(description))))['posting_status'],'open')

    def test_lever_apply_is_not_used_as_description(self):
        canonical='https://jobs.lever.co/example/8f06f221-8777-4a4d-b035-40882db5f4a0'
        apply=canonical+'/apply'
        job=dict(JOB,description_url=apply,application_url=apply)
        client=Client({canonical:response(page()),apply:response(page('')+FORM)})
        result=validate_job(job,client)
        self.assertEqual(result['status'],'open')
        self.assertEqual(result['description_url'],apply)
        self.assertEqual(result['final_description_url'],canonical)

    def test_fresh_greenhouse_api_can_verify_posting_not_application_access(self):
        url='https://job-boards.greenhouse.io/example/jobs/123456'
        api='https://boards-api.greenhouse.io/v1/boards/example/jobs/123456'
        item={'id':123456,'title':JOB['title'],'company_name':'Example','absolute_url':url,'content':DESCRIPTION}
        client=Client({url:response('Access denied',403),api:response(json.dumps(item))})
        result=validate_job(dict(JOB,description_url=url,application_url=url),client)
        self.assertEqual(result['posting_status'],'open')
        self.assertEqual(result['application_status'],'unverified')
        self.assertEqual(result['status'],'unverified')
        self.assertTrue(any(c['kind']=='posting_api' and c['status']=='open' for c in result['checks']))

    def test_api_does_not_accept_mismatched_identifier_title_or_tiny_content(self):
        url='https://job-boards.greenhouse.io/example/jobs/123456'
        api='https://boards-api.greenhouse.io/v1/boards/example/jobs/123456'
        valid={'id':123456,'title':JOB['title'],'company_name':'Example','absolute_url':url,'content':DESCRIPTION}
        for change in [{'id':999999},{'title':'Accountant Intern'},{'content':'Apply now'}, {'company_name':'Foreign'}, {'absolute_url':'https://job-boards.greenhouse.io/foreign/jobs/123456'}]:
            with self.subTest(change=change):
                client=Client({url:response('JavaScript required'),api:response(json.dumps(dict(valid,**change)))})
                self.assertEqual(validate_job(dict(JOB,description_url=url,application_url=url),client)['posting_status'],'unverified')

    def test_api_failure_does_not_close_and_feed_description_does_not_verify(self):
        url='https://job-boards.greenhouse.io/example/jobs/123456'
        api='https://boards-api.greenhouse.io/v1/boards/example/jobs/123456'
        for response_value in [response('{}',404),response('Rate limited',429),requests.Timeout('temporary')]:
            client=Client({url:response('JavaScript required'),api:response_value})
            result=validate_job(dict(JOB,description_url=url,application_url=url,description=DESCRIPTION),client)
            self.assertEqual(result['posting_status'],'unverified')

    def test_login_url_gets_explicit_evidence(self):
        url=JOB['application_url']+'/login'
        client=self.client(application=response('<h1>Login</h1><form>Email<input name="email"></form>',url=url))
        result=validate_job(JOB,client)
        self.assertEqual(result['application_status'],'unverified')
        self.assertIn('login_required',result['checks'][-1]['evidence'])

    def test_fresh_ashby_board_api_binds_exact_url_and_caches_five_minutes(self):
        url='https://jobs.ashbyhq.com/example/8f06f221-8777-4a4d-b035-40882db5f4a0'
        api='https://api.ashbyhq.com/posting-api/job-board/example'
        item={'title':JOB['title'],'jobUrl':url,'applyUrl':url+'/application','descriptionPlain':DESCRIPTION}
        client=Client({url:response('<script>render()</script>'),url+'/application':response('<script>render()</script>'),api:response(json.dumps({'jobs':[item]}))})
        job=dict(JOB,description_url=url,application_url=url+'/application')
        for _ in range(2):
            result=validate_job(job,client)
            self.assertEqual(result['posting_status'],'open')
            self.assertEqual(result['application_status'],'unverified')
        self.assertEqual(sum(c[0]==api for c in client.calls),1)
        self.assertFalse(next(c[1] for c in client.calls if c[0]==api)['respect_robots'])
        timestamp,body,fetched_at=client._posting_api_cache[api]
        client._posting_api_cache[api]=(timestamp-301,body,fetched_at)
        validate_job(job,client)
        self.assertEqual(sum(c[0]==api for c in client.calls),2)

    def test_fresh_lever_api_binds_exact_posting(self):
        url='https://jobs.lever.co/example/8f06f221-8777-4a4d-b035-40882db5f4a0'
        api='https://api.lever.co/v0/postings/example/8f06f221-8777-4a4d-b035-40882db5f4a0'
        item={'id':url.rsplit('/',1)[-1],'text':JOB['title'],'hostedUrl':url,'applyUrl':url+'/apply','descriptionPlain':DESCRIPTION}
        client=Client({url:response('Access denied',403),url+'/apply':response('Access denied',403),api:response(json.dumps(item))})
        result=validate_job(dict(JOB,description_url=url,application_url=url+'/apply'),client)
        self.assertEqual(result['posting_status'],'open')
        self.assertEqual(result['application_status'],'unverified')

    def test_closed_web_posting_is_not_overridden_by_api(self):
        url='https://job-boards.greenhouse.io/example/jobs/123456'
        client=Client({url:response('This position has been closed.')})
        result=validate_job(dict(JOB,description_url=url,application_url=url),client)
        self.assertEqual(result['posting_status'],'closed')
        self.assertEqual(len(client.calls),1)

    def test_ashby_other_board_with_same_id_is_not_accepted(self):
        url='https://jobs.ashbyhq.com/example/8f06f221-8777-4a4d-b035-40882db5f4a0'
        api='https://api.ashbyhq.com/posting-api/job-board/example'
        item={'title':JOB['title'],'jobUrl':url.replace('/example/','/foreign/'),'descriptionPlain':DESCRIPTION}
        client=Client({url:response('<script>render()</script>'),api:response(json.dumps({'jobs':[item]}))})
        self.assertEqual(validate_job(dict(JOB,description_url=url,application_url=url),client)['posting_status'],'unverified')

    def test_incomplete_embed_url_does_not_guess_employer_api_board(self):
        url='https://boards.greenhouse.io/embed/job_app?token=123456'
        client=Client({url:response('Access denied',403)})
        self.assertEqual(validate_job(dict(JOB,description_url=url,application_url=url),client)['posting_status'],'unverified')
        self.assertEqual(len(client.calls),1)

    def test_api_title_may_omit_intern_only_with_fresh_structured_internship(self):
        url='https://job-boards.greenhouse.io/example/jobs/123456'
        api='https://boards-api.greenhouse.io/v1/boards/example/jobs/123456'
        item={'id':123456,'title':'Software Engineer','company_name':'Example','absolute_url':url,'content':DESCRIPTION}
        for employment,expected in [('Summer Internship','open'),('Full Time','unverified')]:
            value=dict(item,metadata=[{'name':'Employment Type','value':employment}])
            client=Client({url:response('JavaScript required'),api:response(json.dumps(value))})
            result=validate_job(dict(JOB,description_url=url,application_url=url),client)
            self.assertEqual(result['posting_status'],expected)

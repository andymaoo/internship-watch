import json
import unittest

import requests

from internship_watch.links import VALIDATOR_VERSION, validate_job


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
    def client(self, description=None, application=None):
        return Client({JOB["description_url"]:description if description is not None else response(page()), JOB["application_url"]:application if application is not None else response(page()+FORM)})

    def test_both_destinations_and_meaningful_identity(self):
        client = self.client()
        result = validate_job(JOB, client)
        self.assertEqual(result["status"], "open")
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
        self.assertEqual(result["checks"][0]["status"],"unverified")
        self.assertEqual(result["checks"][-1]["status"],"open")
        self.assertNotIn("description",result)

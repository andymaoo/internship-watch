"""Robots regressions from live source failures; no network requests."""
import unittest
from unittest.mock import Mock

import requests

from internship_watch.http import AccessRestricted, HttpClient
from internship_watch.links import validate_job


class RobotsTests(unittest.TestCase):
    def client(self, policy, user_agent="InternshipWatch/1.0 (+personal internship discovery)", **kwargs):
        response = requests.Response()
        response.status_code = 200
        response._content = policy.encode("utf-8")
        response._content_consumed = True
        response.url = "https://example.org/robots.txt"
        session = Mock()
        session.request.return_value = response
        return HttpClient(session=session, user_agent=user_agent, resolve_dns=False,
                          min_interval=0, retries=0, **kwargs)

    def test_literal_query_rule_is_not_a_blanket_path_ban(self):
        client = self.client("User-agent: *\nDisallow: /?\n")
        self.assertTrue(client.robots_allowed("https://example.org/about/careers"))
        self.assertTrue(client.robots_allowed("https://example.org/about/careers?q=intern"))
        self.assertFalse(client.robots_allowed("https://example.org/?q=intern"))
        self.assertEqual(client.session.request.call_count, 1)

    def test_google_careers_queries_obey_actual_pagination_restrictions(self):
        # Exact relevant rules captured from Google's public robots.txt.
        policy = """User-agent: *
Disallow: /?
Disallow: /about/careers/applications/jobs/results?page=
Disallow: /about/careers/applications/jobs/results/?page=
Disallow: /about/careers/applications/jobs/results?*&page=
Disallow: /about/careers/applications/jobs/results/?*&page=
User-agent: Yandex
Disallow: /about/careers/applications/jobs/results
"""
        client = self.client(policy)
        base = "https://example.org/about/careers/applications/jobs/results"
        for suffix in ("/", "/?employment_type=INTERN&location=United%20States", "/123-role"):
            with self.subTest(allowed=suffix):
                self.assertTrue(client.robots_allowed(base + suffix))
        for suffix in ("?page=2", "/?page=2", "?employment_type=INTERN&page=2", "/?employment_type=INTERN&page=2"):
            with self.subTest(disallowed=suffix):
                self.assertFalse(client.robots_allowed(base + suffix))
        self.assertFalse(self.client(policy, "Yandex").robots_allowed(base + "/"))

    def test_params_are_included_before_request_policy_check(self):
        client = self.client("User-agent: *\nDisallow: /jobs?*&page=\n")
        with self.assertRaises(AccessRestricted):
            client.get("https://example.org/jobs?type=intern", params={"page": 2}, respect_robots=True)
        self.assertEqual(client.session.request.call_count, 1)
        self.assertEqual(client.session.request.call_args.args[1], "https://example.org/robots.txt")

    def test_wildcard_and_end_anchor_preserve_specific_allow(self):
        client = self.client("User-agent: *\nDisallow: /*.pdf$\nAllow: /public/*.pdf$\n")
        self.assertFalse(client.robots_allowed("https://example.org/reports/a.pdf"))
        self.assertTrue(client.robots_allowed("https://example.org/reports/a.pdf?download=1"))
        self.assertTrue(client.robots_allowed("https://example.org/public/a.pdf"))
        self.assertTrue(client.robots_allowed("https://example.org/reports/a.PDF"))

    def test_longest_rule_wins_and_allow_breaks_ties(self):
        client = self.client("User-agent: *\nDisallow: /\nDisallow: /jobs/open\nAllow: /jobs\nAllow: /jobs/open\n")
        self.assertFalse(client.robots_allowed("https://example.org/private"))
        self.assertTrue(client.robots_allowed("https://example.org/jobs/open/123"))
        self.assertTrue(client.robots_allowed("https://example.org/jobs/123"))

    def test_case_insensitive_user_agent_groups_are_merged(self):
        client = self.client("User-agent: InternshipWatch\nDisallow: /one\nUser-agent: internshipwatch\nDisallow: /two\nUser-agent: *\nDisallow: /\n")
        self.assertFalse(client.robots_allowed("https://example.org/one"))
        self.assertFalse(client.robots_allowed("https://example.org/two"))
        self.assertTrue(client.robots_allowed("https://example.org/jobs"))

    def test_unmatched_agent_uses_wildcard_not_another_agents_group(self):
        client = self.client("User-agent: SomeOtherBot\nDisallow: /\nUser-agent: *\nDisallow: /private\n")
        self.assertTrue(client.robots_allowed("https://example.org/jobs"))
        self.assertFalse(client.robots_allowed("https://example.org/private"))

    def test_percent_encoding_preserves_reserved_characters(self):
        client = self.client("User-agent: *\nDisallow: /caf\u00e9\nDisallow: /jobs/~draft\nDisallow: /a%2Fb\n")
        for path in ("/caf\u00e9", "/caf%C3%A9", "/jobs/%7Edraft", "/a%2fb"):
            with self.subTest(path=path):
                self.assertFalse(client.robots_allowed("https://example.org" + path))
        self.assertTrue(client.robots_allowed("https://example.org/a/b"))

    def test_crawl_delay_and_request_rate_keep_stricter_pacing(self):
        client = self.client("User-agent: *\nCrawl-delay: 1.5\nRequest-rate: 2/10\nDisallow: /private\n")
        self.assertTrue(client.robots_allowed("https://example.org/jobs"))
        self.assertEqual(client._host_intervals["example.org"], 5)

    def test_specific_agent_pacing_is_preserved(self):
        client = self.client("User-agent: *\nCrawl-delay: 1\nUser-agent: InternshipWatch\nCrawl-delay: 2.5\nRequest-rate: 10/1m\n")
        self.assertTrue(client.robots_allowed("https://example.org/jobs"))
        self.assertEqual(client._host_intervals["example.org"], 6)

    def test_configured_source_policy_denies_all_requests_before_network(self):
        client = self.client("User-agent: *\nAllow: /\n", blocked_hosts={"www.metacareers.com": "Written collection permission required"})
        for url in ("https://www.metacareers.com/jobsearch/", "https://www.metacareers.com/robots.txt", "https://www.metacareers.com/graphql"):
            with self.subTest(url=url), self.assertRaises(AccessRestricted):
                client.get(url)
        with self.assertRaises(AccessRestricted):
            client.robots_allowed("https://www.metacareers.com/jobs/123")
        client.session.request.assert_not_called()

    def test_configured_source_policy_is_exact_host_and_normalized(self):
        client = self.client("User-agent: *\nAllow: /\n", blocked_hosts={"WWW.MetaCareers.com.": "Written collection permission required"})
        with self.assertRaises(AccessRestricted):
            client.get("https://www.metacareers.com/jobsearch/")
        self.assertTrue(client.robots_allowed("https://example.org/jobs"))
        client.get("https://other.metacareers.com/jobs")
        self.assertEqual(client.session.request.call_count, 2)

    def test_redirect_to_configured_blocked_host_stops_before_destination_network(self):
        client = self.client("", blocked_hosts={"www.metacareers.com": "Written collection permission required"})
        response = requests.Response()
        response.status_code = 302
        response._content = b""
        response._content_consumed = True
        response.url = "https://example.org/jobs/123"
        response.headers["Location"] = "https://www.metacareers.com/jobs/123"
        client.session.request.return_value = response
        with self.assertRaises(AccessRestricted):
            client.get("https://example.org/jobs/123")
        self.assertEqual(client.session.request.call_count, 1)

    def test_policy_denied_job_records_unverified_not_closed_with_reason(self):
        client = self.client("", blocked_hosts={"www.metacareers.com": "Written collection permission required"})
        job = {"employer": "Meta", "title": "Software Engineer Intern",
               "description_url": "https://www.metacareers.com/jobs/123456",
               "application_url": "https://www.metacareers.com/jobs/123456/apply"}
        result = validate_job(job, client)
        self.assertEqual(result["status"], "unverified")
        self.assertEqual(result["posting_status"], "unverified")
        self.assertEqual(result["application_status"], "unverified")
        for check in result["checks"]:
            self.assertIn("access_failure:AccessRestricted", check["evidence"])
            self.assertIn("configured_source_policy_restriction", check["evidence"])
            self.assertIn("Written collection permission required", check["failure_detail"])
        client.session.request.assert_not_called()

    def test_invalid_source_policy_configuration_is_rejected(self):
        for mapping in (["example.org"], {"https://example.org": "reason"}, {"example.org": ""}, {"": "reason"}, {"example.org/path": "reason"}):
            with self.subTest(mapping=mapping), self.assertRaises(ValueError):
                self.client("", blocked_hosts=mapping)


if __name__ == "__main__":
    unittest.main()

"""Regression tests for information loss, schema drift and silent truncation."""
import unittest
from unittest.mock import patch
from unittest.mock import Mock
import requests
import time

from internship_watch.sources import SourceError, collect
from internship_watch.http import AccessRestricted, HttpClient, allow_url
import google_scraper
import apple_scraper


class Response:
    def __init__(self, data, url="https://example.org/feed"):
        self.data, self.url = data, url
        self.status_code = 200

    def json(self):
        return self.data

    def raise_for_status(self):
        return None


class Client:
    def __init__(self, *pages):
        self.pages = iter(pages)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return Response(next(self.pages), url)


def lever_job(identity):
    return {"id": identity, "text": "Product Manager Intern", "hostedUrl": f"https://jobs.lever.co/test/{identity}", "applyUrl": f"https://jobs.lever.co/test/{identity}/apply", "descriptionPlain": "An internship building software.", "categories": {"commitment": "Intern", "location": "New York"}}


class SourceTests(unittest.TestCase):
    def test_greenhouse_keeps_description_and_does_not_invent_posting_date(self):
        client = Client({"jobs": [{"id": 12, "title": "AI Research Intern", "absolute_url": "https://boards.greenhouse.io/test/jobs/12", "content": "&lt;p&gt;Internship description&lt;/p&gt;", "location": {"name": "London"}, "updated_at": "2026-09-01"}], "meta": {"total": 1}})
        job = collect({"id": "test", "type": "greenhouse", "slug": "test", "employer": "Test"}, client)[0]
        self.assertEqual(client.calls[0][1]["params"], {"content": "true"})
        self.assertIn("Internship description", job["description"])
        self.assertEqual(job["location"], "London")
        self.assertIsNone(job["posting_date"])
        self.assertEqual(job["evidence"]["source_updated_at"], "2026-09-01")

    def test_schema_failure_is_not_successful_empty_feed(self):
        for kind, bad in (("greenhouse", {}), ("ashby", {"error": "down"}), ("lever", {}), ("simplify", {})):
            with self.subTest(kind=kind), self.assertRaises(SourceError):
                collect({"id": "test", "type": kind, "slug": "test", "url": "https://example.org/jobs"}, Client(bad))

    def test_greenhouse_total_mismatch_is_failure(self):
        with self.assertRaises(SourceError):
            collect({"id": "test", "type": "greenhouse", "slug": "test"}, Client({"jobs": [], "meta": {"total": 5}}))

    def test_lever_reads_every_page_and_preserves_application_url(self):
        client = Client([lever_job("a"), lever_job("b")], [lever_job("c")], [])
        jobs = collect({"id": "test", "type": "lever", "slug": "test", "page_size": 2}, client)
        self.assertEqual(len(jobs), 3)
        self.assertEqual([call[1]["params"]["skip"] for call in client.calls], [0, 2, 3])
        self.assertEqual(jobs[0]["employment_type"], "Intern")
        self.assertTrue(jobs[0]["application_url"].endswith("/apply"))

    def test_repeated_pagination_and_page_cap_fail_loudly(self):
        source = {"id": "test", "type": "lever", "slug": "test", "page_size": 1, "max_pages": 2}
        with self.assertRaises(SourceError):
            collect(source, Client([lever_job("a")], [lever_job("a")]))
        with self.assertRaises(SourceError):
            collect(source, Client([lever_job("a")], [lever_job("b")]))

    def test_ashby_retains_structured_fields_and_unlisted_privacy(self):
        item = {"id": "123", "title": "Software Engineer Intern", "jobUrl": "https://jobs.ashbyhq.com/test/123", "applyUrl": "https://jobs.ashbyhq.com/test/123/application", "employmentType": "Intern", "descriptionPlain": "Summer internship", "publishedAt": "2026-09-01T00:00:00Z", "location": "London", "secondaryLocations": [{"location": "New York"}], "isListed": True}
        jobs = collect({"id": "test", "type": "ashby", "slug": "test"}, Client({"jobs": [item, dict(item, id="456", isListed=False)]}))
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["locations"], ["London", "New York"])
        self.assertEqual(jobs[0]["posting_date"], item["publishedAt"])

    def test_simplify_is_unrestricted_and_feed_date_is_not_employer_date(self):
        item = {"id": "uuid", "company_name": "Unlisted Company", "title": "Product Manager Intern", "url": "https://example.org/job/123", "locations": ["US"], "active": True, "is_visible": True, "terms": ["Fall 2026", "Summer 2027"], "date_posted": 1700000000, "sponsorship": "Unknown", "category": "Product"}
        jobs = collect({"id": "community", "type": "simplify", "url": "https://example.org/feed"}, Client([item, dict(item, id="closed", active=False)]))
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["employer"], "Unlisted Company")
        self.assertIsNone(jobs[0]["posting_date"])
        self.assertEqual(jobs[0]["evidence"]["source_added_at"], 1700000000)
        self.assertEqual(jobs[0]["season"], item["terms"])

    def test_no_title_prefilter_loses_product_or_qualifying_research(self):
        jobs = collect({"id": "test", "type": "lever", "slug": "test"}, Client([lever_job("a"), dict(lever_job("b"), text="Student Researcher")], []))
        self.assertEqual(len(jobs), 2)

    def test_lever_server_capped_short_page_still_continues(self):
        client = Client([lever_job("a")], [lever_job("b")], [])
        jobs = collect({"id": "test", "type": "lever", "slug": "test", "page_size": 100}, client)
        self.assertEqual(len(jobs), 2)
        self.assertEqual([call[1]["params"]["skip"] for call in client.calls], [0, 1, 2])

    def test_legacy_google_schema_drift_is_failure_not_empty_success(self):
        with self.assertRaises(RuntimeError):
            google_scraper.extract_jobs({"error": "schema changed"})

    def test_legacy_google_retains_description(self):
        entry = ["123", "Student Researcher", "https://example.org/job/123", [None, "<p>ML internship</p>"], [None, "Enrolled PhD"], None, None, None, None, [["London"]]]
        job = google_scraper.extract_jobs([[entry]])[0]
        self.assertIn("ML internship", job["description"])
        self.assertIn("Enrolled PhD", job["description"])

    def test_legacy_google_cap_is_failure(self):
        with patch.object(google_scraper, "search_jobs", return_value=[]), patch.object(google_scraper, "extract_jobs", side_effect=lambda payload: [{"id": str(i)} for i in range(20)]):
            with self.assertRaises(RuntimeError):
                google_scraper.fetch_google_internships()

    def test_legacy_apple_search_schema_failure_is_not_empty(self):
        client = Client()
        client.post = lambda *args, **kwargs: Response({"error": "changed"})
        with self.assertRaises(RuntimeError):
            apple_scraper._search_page(client, "token", 1)

    def test_legacy_apple_cap_is_failure(self):
        page = {"searchResults": [{"id": str(i), "positionId": str(i), "postingTitle": "Software Intern", "transformedPostingTitle": "software-intern"} for i in range(20)]}
        with patch.object(apple_scraper, "_prime_session"), patch.object(apple_scraper, "_get_csrf_token", return_value="token"), patch.object(apple_scraper, "_search_page", return_value=page):
            with self.assertRaises(RuntimeError):
                apple_scraper.fetch_apple_internships()

    def test_apple_retains_available_summary_location_and_employer_date(self):
        item = {"id": "200-3810", "title": "Software Intern", "url": "https://jobs.apple.com/en-us/details/200/software-intern", "source_record": {"jobSummary": "Work on a software internship.", "postDateInGMT": "2026-09-01T00:00:00Z", "locations": [{"city": "Cupertino", "stateProvince": "California", "countryName": "United States of America"}]}}
        with patch.object(apple_scraper, "fetch_apple_internships", return_value=[item]):
            job = collect({"id": "apple", "type": "apple", "location_filters": ["postLocation-USA"]}, Client())[0]
        self.assertIn("Cupertino", job["location"])
        self.assertEqual(job["country"], "USA")
        self.assertEqual(job["posting_date"], "2026-09-01T00:00:00Z")
        self.assertEqual(job["evidence"]["description_kind"], "employer_search_summary")


class HttpTests(unittest.TestCase):
    def response(self, status, text="", **headers):
        response = requests.Response()
        response.status_code = status
        response._content = text.encode()
        response._content_consumed = True
        response.url = "https://example.org/jobs/123"
        response.headers.update(headers)
        return response

    def client(self, *responses, retries=2):
        session = Mock()
        session.request.side_effect = responses
        return HttpClient(session=session, resolve_dns=False, min_interval=0, retries=retries, backoff=0)

    def test_timeouts_retry_bounded(self):
        client = self.client(requests.Timeout(), requests.Timeout(), requests.Timeout())
        with self.assertRaises(requests.Timeout):
            client.get("https://example.org/jobs")
        self.assertEqual(client.session.request.call_count, 3)
        self.assertEqual(client.session.request.call_args.kwargs["timeout"], (10, 20))

    def test_long_retry_after_defers_without_hammering(self):
        client = self.client(self.response(429, **{"Retry-After": "300"}))
        with self.assertRaises(requests.HTTPError):
            client.get("https://example.org/jobs")
        self.assertEqual(client.session.request.call_count, 1)

    def test_private_redirect_and_malformed_url_rejected(self):
        client = self.client(self.response(302, Location="http://127.0.0.1/secret"))
        with self.assertRaises(ValueError):
            client.get("https://example.org/jobs")
        self.assertEqual(client.session.request.call_count, 1)
        for url in ("file:///tmp/test", "https://user:pass@example.org", "http://127.0.0.1", "http://[::1]", "https://example.org/bad path"):
            with self.assertRaises(ValueError):
                allow_url(url, resolve_dns=False)

    def test_robots_disallow_and_unavailable_are_unverified(self):
        for response in (self.response(200, "User-agent: *\nDisallow: /jobs"), self.response(503)):
            client = self.client(response, retries=0)
            with self.assertRaises(AccessRestricted):
                client.get("https://example.org/jobs/123", respect_robots=True)
            self.assertEqual(client.session.request.call_count, 1)

    def test_notification_post_is_not_implicitly_retried(self):
        client = self.client(requests.Timeout())
        with self.assertRaises(requests.Timeout):
            client.post("https://example.org/webhook", json={"content": "hello"})
        self.assertEqual(client.session.request.call_count, 1)

    def test_redirect_checks_robots_at_new_destination(self):
        client = self.client(self.response(404), self.response(302, Location="https://other.example.org/jobs/123"), self.response(200, "User-agent: *\nDisallow: /"), retries=0)
        with self.assertRaises(AccessRestricted):
            client.get("https://example.org/jobs/123", respect_robots=True)
        self.assertEqual(client.session.request.call_count, 3)

    def test_deadline_clamps_request_timeouts(self):
        client = self.client(self.response(200))
        client.deadline = time.monotonic() + 1
        client.get("https://example.org/jobs/123")
        self.assertTrue(all(0 < timeout <= .5 for timeout in client.session.request.call_args.kwargs["timeout"]))

    def test_deadline_does_not_start_overlong_pacing_or_retry_sleep(self):
        client = self.client(self.response(200))
        client.deadline = time.monotonic() + 1
        client._last_request["example.org"] = time.monotonic()
        client.min_interval = 2
        with patch("internship_watch.http.time.sleep") as sleep, self.assertRaises(requests.Timeout):
            client.get("https://example.org/jobs/123")
        sleep.assert_not_called()
        client.session.request.assert_not_called()
        client = self.client(self.response(503, **{"Retry-After": "2"}))
        client.deadline = time.monotonic() + 1
        with patch("internship_watch.http.time.sleep") as sleep, self.assertRaises(requests.Timeout):
            client.get("https://example.org/jobs/123")
        sleep.assert_not_called()
        self.assertEqual(client.session.request.call_count, 1)

    def test_expired_deadline_starts_no_request(self):
        client = self.client(self.response(200))
        client.deadline = time.monotonic() - 1
        with self.assertRaises(requests.Timeout):
            client.get("https://example.org/jobs/123")
        client.session.request.assert_not_called()

    def test_429_cools_all_paths_and_robots_without_sleep_or_retry(self):
        client = self.client(self.response(429, **{"Retry-After": "300"}))
        with patch("internship_watch.http.time.time", return_value=1000), patch("internship_watch.http.time.sleep") as sleep:
            response = client.get("https://example.org/jobs/1", raise_for_status=False)
            self.assertEqual(response.status_code, 429)
            self.assertEqual(client.host_cooldowns["example.org"], 1300)
            for url in ("https://example.org/jobs/2", "https://example.org/robots.txt", "http://example.org:80/other"):
                with self.assertRaises(AccessRestricted):
                    client.get(url)
            with self.assertRaises(AccessRestricted):
                client.robots_allowed("https://example.org/jobs/3")
        sleep.assert_not_called()
        self.assertEqual(client.session.request.call_count, 1)

    def test_429_default_and_http_date_delays_are_preserved(self):
        for headers, until in (({}, 1060), ({"Retry-After": "Thu, 01 Jan 1970 00:21:40 GMT"}, 1300), ({"Retry-After": "NaN"}, 1060)):
            client = self.client(self.response(429, **headers))
            with patch("internship_watch.http.time.time", return_value=1000):
                client.get("https://example.org/jobs", raise_for_status=False)
                self.assertEqual(client.host_cooldowns["example.org"], until)

    def test_cooldown_persists_restart_and_does_not_block_other_host(self):
        client = self.client(self.response(429, **{"Retry-After": "300"}))
        with patch("internship_watch.http.time.time", return_value=1000):
            client.get("https://example.org/jobs", raise_for_status=False)
            snapshot = client.rate_limits()
            restarted = self.client(self.response(200))
            restarted.load_rate_limits(snapshot)
            with self.assertRaises(AccessRestricted):
                restarted.get("https://example.org/new-job")
            restarted.get("https://other.example.org/jobs")
            self.assertEqual(restarted.session.request.call_count, 1)
        with patch("internship_watch.http.time.time", return_value=1301):
            restarted.session.request.side_effect = [self.response(200)]
            restarted.get("https://example.org/new-job")
            self.assertNotIn("example.org", restarted.host_cooldowns)

    def test_shared_worker_maps_defer_other_client(self):
        first = self.client(self.response(429))
        second = self.client(self.response(200))
        second.host_cooldowns = first.host_cooldowns
        second.host_failure_counts = first.host_failure_counts
        second._lock = first._lock
        first.get("https://example.org/job/1", raise_for_status=False)
        with self.assertRaises(AccessRestricted):
            second.get("https://example.org/job/2")
        second.session.request.assert_not_called()

    def test_three_consecutive_403_open_circuit(self):
        client = self.client(*(self.response(403) for _ in range(3)))
        with patch("internship_watch.http.time.time", return_value=1000):
            for number in range(3):
                client.get(f"https://example.org/job/{number}", raise_for_status=False)
            self.assertEqual(client.host_cooldowns["example.org"], 1300)
            with self.assertRaises(AccessRestricted):
                client.get("https://example.org/job/next")
        self.assertEqual(client.session.request.call_count, 3)

    def test_success_and_404_reset_forbidden_counter(self):
        for interruption in (200, 404):
            client = self.client(*(self.response(status) for status in (403, 403, interruption, 403, 403)))
            for number in range(5):
                client.get(f"https://example.org/job/{number}", raise_for_status=False)
            self.assertEqual(client.host_failure_counts["example.org"], 2)
            self.assertNotIn("example.org", client.host_cooldowns)

    def test_forbidden_breaker_can_be_disabled(self):
        client = self.client(*(self.response(403) for _ in range(4)))
        client.forbidden_threshold = 0
        for number in range(4):
            client.get(f"https://example.org/job/{number}", raise_for_status=False)
        self.assertNotIn("example.org", client.host_cooldowns)


if __name__ == "__main__":
    unittest.main()

import json
import unittest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.parse import urlencode

import requests

from internship_watch.classify import classify
from internship_watch.google_source import GoogleDetailError, apply_google_eligibility, google_job_id, parse_google_detail
from internship_watch.http import AccessRestricted
from internship_watch.links import validate_job
from internship_watch.runner import run_once
from internship_watch.storage import Store


IDENTITY = "100648618540573382"
URL = "https://www.google.com/about/careers/applications/jobs/results/" + IDENTITY
TITLE = "Software Engineering Intern, BS, Summer 2027"
JOB = {"employer": "Google", "title": "Software Engineer Intern - Multiple Teams",
       "description_url": URL, "application_url": URL, "location": "California, USA"}


def record(title=TITLE, degree="Bachelor's"):
    row = [None] * 21
    row[0], row[1], row[7] = IDENTITY, title, "Google"
    row[2] = "https://www.google.com/about/careers/applications/signin?" + urlencode({"jobId": "public-job-reference", "title": "Software Engineering Intern"})
    row[3] = [None, "<p>Develop software services, test backend features, and work with engineering mentors on a summer internship project.</p>"]
    row[4] = [None, f"<h3>Minimum qualifications:</h3><p>Currently pursuing a {degree} degree in Computer Science.</p>"]
    row[9] = [["Mountain View, CA, USA", ["California"], "Mountain View", "94043", "CA", "US"]]
    row[10] = [None, "<p>This internship offers supervised software engineering work. As an intern you will design, test and document distributed software systems with your team.</p>"]
    row[15] = [None, "<p>Participants must be located in the United States for this internship.</p>"]
    row[18] = [None, "<p>Work location: Mountain View, California.</p>"]
    row[19] = [None, f"<p>Currently pursuing a {degree} degree in Computer Science.</p>"]
    return row


def markup(row=None, title=TITLE, key="ds:0"):
    return (f"<title>{title} — Google Careers</title><main><h1>{title}</h1>Google"
            "<p>Unrelated search result: Accountant Intern. Responsibilities: audit spreadsheets.</p></main>"
            "<script>AF_initDataCallback({key: '" + key + "', hash: '1', data:" + json.dumps([row or record()]) + ", sideChannel: {}});</script>")


def response(text, status=200, url=None):
    r = requests.Response(); r.status_code = status; r._content = text.encode(); r.url = url
    return r


class Client:
    def __init__(self, page, application=None):
        self.page, self.application, self.calls = page, application, []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        r = self.page if url == URL else self.application
        if isinstance(r, Exception):
            raise r
        if r is None:
            raise AssertionError("Unexpected HTTP request")
        if r.url is None:
            r.url = url
        return r


class GoogleDetailTests(unittest.TestCase):
    def test_exact_detail_url_only(self):
        self.assertEqual(google_job_id(URL + "-software-engineering-intern?hl=en"), IDENTITY)
        for url in [URL.replace("www.google.com", "evil.example"), URL.replace("https:", "http:"),
                    URL.replace("www.google.com", "www.google.com.evil.example"),
                    "https://www.google.com/about/careers/applications/jobs/results/?q=intern",
                    URL + "/another"]:
            self.assertIsNone(google_job_id(url))

    def test_detail_retains_all_eligibility_sections(self):
        detail = parse_google_detail(markup(), URL)
        self.assertEqual(detail["id"], IDENTITY)
        self.assertIn("Bachelor's degree", detail["description"])
        self.assertIn("must be located in the United States", detail["description"])
        self.assertEqual(detail["locations"][0]["country"], "US")

    def test_posting_verified_but_actual_login_application_unverified(self):
        client = Client(response(markup()), response("<title>Sign in</title><p>Sign in to continue</p>"))
        result = validate_job(JOB, client)
        self.assertEqual(result["posting_status"], "open")
        self.assertEqual(result["application_status"], "unverified")
        self.assertIn("login_required", result["checks"][-1]["evidence"])
        self.assertIn("Bachelor's degree", result["description"])
        self.assertEqual(len(client.calls), 2)
        self.assertTrue(all(kwargs["respect_robots"] for _, kwargs in client.calls))

    def test_unrelated_search_results_never_substitute_for_detail(self):
        for body in [markup(key="ds:1"), markup() + markup(), markup().replace(IDENTITY, "99999999999999999")]:
            result = validate_job(JOB, Client(response(body)))
            self.assertEqual(result["posting_status"], "unverified")

    def test_wrong_expected_role_or_employer_rejected(self):
        for changes in [{"title": "Accountant Intern"}, {"employer": "Meta"}, {"title": "Research Scientist Intern"}]:
            result = validate_job(dict(JOB, **changes), Client(response(markup())))
            self.assertEqual(result["posting_status"], "unverified")

    def test_wrong_embedded_employer_and_application_rejected(self):
        for index, value in [(7, "Foreign Company"), (2, "https://evil.example/signin?jobId=bad"),
                             (2, "https://www.google.com/about/careers/applications/signin?jobId=123&title=Accountant+Intern")]:
            row = record(); row[index] = value
            with self.assertRaises(GoogleDetailError):
                parse_google_detail(markup(row), URL)

    def test_changed_schema_missing_description_and_location_fail_closed_to_unverified(self):
        for index, value in [(4, None), (10, [None, ""]), (19, [None, ""]), (9, []), (3, "changed")]:
            row = record(); row[index] = value
            result = validate_job(JOB, Client(response(markup(row))))
            self.assertEqual(result["posting_status"], "unverified")

    def test_heading_disagrees_with_record(self):
        result = validate_job(JOB, Client(response(markup(title="Accountant Intern"))))
        self.assertEqual(result["posting_status"], "unverified")

    def test_intern_word_not_removed_for_permanent_posting(self):
        row = record(title="Software Engineering, BS, Summer 2027")
        row[2] = "https://www.google.com/about/careers/applications/signin?jobId=123&title=Software+Engineering+BS"
        result = validate_job(JOB, Client(response(markup(row, title=row[1]))))
        self.assertEqual(result["posting_status"], "unverified")

    def test_explicit_expiry_not_overridden_by_embedded_data(self):
        result = validate_job(JOB, Client(response(markup() + "<p>Job not found. This job may have been taken down.</p>")))
        self.assertEqual(result["posting_status"], "closed")

    def test_restrictions_timeout_and_rate_limit_remain_unverified(self):
        for value in [AccessRestricted("Denied by robots"), requests.Timeout(), response("Rate limited", 429), response("Denied", 403)]:
            result = validate_job(JOB, Client(value))
            self.assertEqual(result["posting_status"], "unverified")

    def test_different_detail_redirect_rejected(self):
        result = validate_job(JOB, Client(response(markup(), url=URL.replace(IDENTITY, "99999999999999999"))))
        self.assertEqual(result["posting_status"], "unverified")

    def test_master_only_description_preserved_for_existing_classifier(self):
        row = record(title="Software Engineering Intern, MS, Summer 2027", degree="Master's")
        client = Client(response(markup(row, title=row[1])), response("Sign in to continue"))
        result = validate_job(JOB, client)
        self.assertEqual(result["posting_status"], "open")
        self.assertIn("Master's degree", result["description"])
        # Enrichment flows through runner's existing reclassification path.
        decision = classify(dict(JOB, description=result["description"]), {"degrees": ["bachelor"]})
        self.assertEqual(decision["decision"], "exclude")

    def test_employer_degree_overrides_conflicting_community_tags_and_survives_restart(self):
        row = record(title="Software Engineering Intern, MS, Summer 2027", degree="Master's")
        feed_job = dict(JOB, source_id="google-ms", description="", evidence={
            "provider":"simplify", "degrees":["Bachelor's", "Master's"], "feed_internship_context":True})
        official = validate_job(feed_job, Client(response(markup(row, title=row[1])), response("Sign in to continue")))
        filters = {"degrees":["bachelor"], "allow_unstated_eligibility":True}
        self.assertEqual(classify(feed_job, filters)["decision"], "include")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "jobs.sqlite3"
            config = {"database":str(path), "sources":[{"id":"feed"}], "filters":filters, "initial_run":"silent"}
            sender = Mock()
            with patch("internship_watch.runner.heartbeat"):
                for jobs in ([], [feed_job], [feed_job], [feed_job]):
                    run_once(config, collector=lambda s,c,jobs=jobs:jobs, client=Mock(),
                             validator=lambda j,c:official, sender=sender)
            store = Store(path)
            try:
                saved = store.rows("SELECT * FROM jobs")[0]
                self.assertEqual(saved["classification"], "exclude")
                payload = json.loads(saved["payload"])
                self.assertEqual(payload["evidence"]["degrees"], ["master"])
                self.assertEqual(payload["evidence"]["validated_google_eligibility"]["job_id"], IDENTITY)
                raw = json.loads(store.rows("SELECT payload FROM source_records")[0]["payload"])
                self.assertEqual(raw["evidence"]["degrees"], ["Bachelor's", "Master's"])
                self.assertEqual(store.rows("SELECT COUNT(*) n FROM outbox")[0]["n"], 0)
                sender.send.assert_not_called()
            finally:
                store.close()

    def test_degree_proof_cannot_cross_job_employer_or_provider(self):
        proof = {"kind":"google_public_detail", "job_id":IDENTITY, "title":TITLE,
                 "degrees":["bachelor"], "minimum_qualifications":"Pursuing a Bachelor's degree."}
        job = dict(JOB, evidence={"provider":"simplify", "degrees":["master"]})
        for change in [{"description_url":URL.replace(IDENTITY,"99999999999999999")},
                       {"employer":"Meta"}, {"title":"Accountant Intern"},
                       {"evidence":{"provider":"greenhouse","degrees":["master"]}}]:
            modified = dict(job, **change)
            self.assertFalse(apply_google_eligibility(modified, proof))
            self.assertNotIn("validated_google_eligibility", modified["evidence"])

    def test_nonempty_community_descriptions_cannot_erase_employer_requirement(self):
        summary = "Join our software engineering internship and build useful products."
        filters = {"degrees":["bachelor"], "allow_unstated_eligibility":True}
        row = record(title="Software Engineering Intern, MS, Summer 2027", degree="Master's")
        feed = dict(JOB, source_id="google-ms", evidence={"provider":"simplify",
                    "degrees":["Bachelor's", "Master's"], "feed_internship_context":True})
        official = validate_job(feed, Client(response(markup(row, title=row[1])), response("Sign in to continue")))
        for initial, later in [("", summary), (summary, summary), (summary, "")]:
            with self.subTest(initial=bool(initial), later=bool(later)), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "jobs.sqlite3"
                config = {"database":str(path), "sources":[{"id":"feed"}], "filters":filters, "initial_run":"silent"}
                sender, validator = Mock(), Mock(return_value=official)
                with patch("internship_watch.runner.heartbeat"):
                    for jobs in ([], [dict(feed, description=initial)], [dict(feed, description=later)], [dict(feed, description=later)]):
                        run_once(config, collector=lambda s,c,jobs=jobs:jobs, client=Mock(), validator=validator, sender=sender)
                        if not jobs:
                            continue
                        # Each cycle reopens SQLite: preservation cannot rely on process memory.
                        store = Store(path)
                        try:
                            saved = store.rows("SELECT * FROM jobs")[0]
                            payload = json.loads(saved["payload"])
                            self.assertEqual(saved["classification"], "exclude")
                            self.assertIn("Master's degree", saved["description"])
                            self.assertEqual(payload["evidence"]["degrees"], ["master"])
                            self.assertEqual(store.rows("SELECT COUNT(*) n FROM outbox")[0]["n"], 0)
                        finally:
                            store.close()
                validator.assert_called_once()
                sender.send.assert_not_called()

    def test_persisted_proof_not_reused_after_feed_changes_id_or_title(self):
        filters = {"degrees":["bachelor"], "allow_unstated_eligibility":True}
        feed = dict(JOB, source_id="google-ms", description="", evidence={"provider":"simplify",
                    "degrees":["Bachelor's", "Master's"], "feed_internship_context":True})
        row = record(title="Software Engineering Intern, MS, Summer 2027", degree="Master's")
        official = validate_job(feed, Client(response(markup(row, title=row[1])), response("Sign in to continue")))
        for changed in [{"title":"Accountant Intern"}, {"description_url":URL.replace(IDENTITY,"99999999999999999"),
                                                       "application_url":URL.replace(IDENTITY,"99999999999999999")}]:
            with self.subTest(changed=changed), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "jobs.sqlite3"
                config = {"database":str(path), "sources":[{"id":"feed"}], "filters":filters, "initial_run":"silent"}
                with patch("internship_watch.runner.heartbeat"):
                    run_once(config, collector=lambda s,c:[feed], client=Mock(), validator=lambda j,c:official, sender=Mock())
                store = Store(path)
                try:
                    with store.transaction():
                        store.upsert_job("feed", dict(feed, description="A different job summary.", **changed), {}, 2, filters=filters)
                    saved = store.rows("SELECT * FROM jobs")[0]
                    self.assertNotIn("validated_google_eligibility", json.loads(saved["payload"])["evidence"])
                    self.assertEqual(saved["posting_status"], "unverified")
                finally:
                    store.close()


if __name__ == "__main__":
    unittest.main()

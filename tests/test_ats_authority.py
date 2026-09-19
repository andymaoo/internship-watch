"""Custom employer URLs must retain directly observed ATS identity after merges."""
import json
import tempfile
import unittest
from pathlib import Path

from internship_watch.classify import classify
from internship_watch.links import provider_spec, validate_job
from internship_watch.storage import Store
from tests.test_links import Client, response


URL = "https://www.hudsonrivertrading.com/careers/job/?gh_jid=7964062"
TITLE = "Algorithm Development (Quant Research & Trading) Internship – Summer 2027"
DESCRIPTION = "Responsibilities: As an intern, develop trading algorithms and perform quantitative research. Qualifications: Currently pursuing a Bachelor's degree in mathematics or computer science. Work with a research mentor and test models on financial data."
DIRECT = {"source_id":"gh-wehrtyou-7964062", "employer":"Hudson River Trading", "title":TITLE,
          "description":DESCRIPTION, "employment_type":"Internship", "location":"New York, NY, USA",
          "description_url":URL, "application_url":URL,
          "evidence":{"provider":"greenhouse","provider_job_id":"7964062"}}
FEED = dict(DIRECT, source_id="community-id", title="Algorithm Development Intern - Quant Research",
            description="Join our algorithm development internship.", employment_type=None,
            evidence={"provider":"simplify","degrees":["Bachelor's", "Master's"], "feed_internship_context":True})
FILTERS = {"degrees":["bachelor"], "allow_unstated_eligibility":True}


def validate(payload, *, title=TITLE, identity=7964062):
    api = "https://boards-api.greenhouse.io/v1/boards/wehrtyou/jobs/7964062"
    body = {"id":identity, "title":title, "company_name":"Hudson River Trading",
            "absolute_url":URL, "content":DESCRIPTION, "metadata":[{"name":"Employment Type","value":"Intern"}]}
    client = Client({URL:response("<script>Render employer job here</script>"), api:response(json.dumps(body))})
    return validate_job(payload, client), client


class AtsAuthorityTests(unittest.TestCase):
    def test_direct_then_feed_and_feed_then_direct_preserve_identity_after_restart(self):
        for first, second in [(DIRECT, FEED), (FEED, DIRECT)]:
            with self.subTest(first=first["evidence"]["provider"]), tempfile.TemporaryDirectory() as directory:
                path = Path(directory)/"jobs.sqlite3"
                store = Store(path)
                original_id = None
                try:
                    for run, job in enumerate([first, second], 1):
                        source = job["evidence"]["provider"]
                        with store.transaction():
                            jid, _ = store.upsert_job(source, job, {}, run, baseline=True, filters=FILTERS)
                        original_id = original_id or jid
                        self.assertEqual(jid, original_id)
                finally:
                    store.close()
                store = Store(path)
                try:
                    for run in range(3, 6):
                        with store.transaction():
                            store.upsert_job("simplify", FEED, {}, run, filters=FILTERS)
                    row = store.rows("SELECT * FROM jobs")[0]
                    payload = json.loads(row["payload"])
                    self.assertEqual(payload["source_id"], DIRECT["source_id"])
                    self.assertEqual(row["title"], TITLE)
                    self.assertEqual(row["description"], DESCRIPTION)
                    self.assertEqual(payload["employment_type"], "Internship")
                    self.assertEqual(row["id"], original_id)
                    self.assertEqual(row["baseline"], 1)
                    self.assertEqual(provider_spec(URL, payload)["board"], "wehrtyou")
                    result, client = validate(payload)
                    self.assertEqual(result["posting_status"], "open")
                    self.assertEqual(result["application_status"], "unverified")
                    self.assertTrue(any("boards-api.greenhouse.io" in url for url,_ in client.calls))
                    raw = {r["source"]:json.loads(r["payload"]) for r in store.rows("SELECT * FROM source_records")}
                    self.assertEqual(raw["simplify"], FEED)
                    self.assertEqual(raw["greenhouse"], DIRECT)
                finally:
                    store.close()

    def test_direct_degree_and_full_time_updates_win_over_nonempty_feed(self):
        for changes in [{"description":"Responsibilities: Develop trading algorithms. Qualifications: This internship requires a PhD degree.","title":TITLE.replace("Internship", "PhD Internship")},
                        {"title":"Algorithm Development – Full-Time Graduate", "employment_type":"Full-Time: New Grad"}]:
            with self.subTest(changes=changes), tempfile.TemporaryDirectory() as directory:
                store = Store(Path(directory)/"jobs.sqlite3")
                try:
                    with store.transaction():
                        store.upsert_job("simplify", FEED, {}, 1, filters=FILTERS)
                        store.upsert_job("greenhouse", DIRECT, {}, 2, filters=FILTERS)
                        store.upsert_job("greenhouse", dict(DIRECT, **changes), {}, 3, filters=FILTERS)
                        store.upsert_job("simplify", FEED, {}, 4, filters=FILTERS)
                    row = store.rows("SELECT * FROM jobs")[0]
                    self.assertEqual(row["classification"], "exclude")
                    self.assertEqual(row["title"], changes["title"])
                finally:
                    store.close()

    def test_feed_identity_changes_do_not_reuse_direct_provenance_or_open_check(self):
        for changes in [{"title":"Accountant Intern"}, {"employer":"Foreign Employer"},
                        {"description_url":URL.replace("7964062", "9999999"), "application_url":URL.replace("7964062", "9999999")},
                        {"description_url":URL.replace("www.hudsonrivertrading.com", "different.example")}]:
            with self.subTest(changes=changes), tempfile.TemporaryDirectory() as directory:
                store = Store(Path(directory)/"jobs.sqlite3")
                try:
                    with store.transaction():
                        jid,_ = store.upsert_job("simplify", FEED, {}, 1, filters=FILTERS)
                        store.upsert_job("greenhouse", DIRECT, {}, 2, filters=FILTERS)
                        store.record_check(jid, {"status":"open","posting_status":"open","application_status":"open"}, "2099-01-01")
                        store.upsert_job("simplify", dict(FEED, **changes), {}, 3, filters=FILTERS)
                    row = store.rows("SELECT * FROM jobs")[0]
                    payload = json.loads(row["payload"])
                    self.assertEqual(payload["evidence"]["provider"], "simplify")
                    self.assertEqual(payload["description"], FEED["description"])
                    self.assertIsNone(provider_spec(payload["description_url"], payload))
                    self.assertEqual(row["posting_status"], "unverified")
                finally:
                    store.close()

    def test_distinct_observed_boards_with_same_numeric_id_remain_separate(self):
        second = dict(DIRECT, source_id="gh-anotherboard-7964062")
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory)/"jobs.sqlite3")
            try:
                with store.transaction():
                    first_id,_ = store.upsert_job("first", DIRECT, {}, 1, filters=FILTERS)
                    store.record_check(first_id, {"status":"open"}, "2099-01-01")
                    second_id,_ = store.upsert_job("second", second, {}, 2, filters=FILTERS)
                    store.upsert_job("second", second, {}, 3, filters=FILTERS)
                self.assertNotEqual(first_id, second_id)
                rows = store.rows("SELECT * FROM jobs")
                self.assertEqual(len(rows), 2)
                row = next(row for row in rows if row["id"] == second_id)
                self.assertEqual(row["posting_status"], "unverified")
                self.assertEqual(provider_spec(URL, json.loads(row["payload"]))["board"], "anotherboard")
            finally:
                store.close()

    def test_official_title_change_invalidates_old_check_and_wrong_live_api_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory)/"jobs.sqlite3")
            try:
                with store.transaction():
                    jid,_ = store.upsert_job("greenhouse", DIRECT, {}, 1, filters=FILTERS)
                    store.record_check(jid, {"status":"open"}, "2099-01-01")
                    changed = dict(DIRECT, title="Accountant Internship")
                    store.upsert_job("greenhouse", changed, {}, 2, filters=FILTERS)
                row = store.rows("SELECT * FROM jobs")[0]
                self.assertEqual(row["posting_status"], "unverified")
                result,_ = validate(json.loads(row["payload"]))
                self.assertEqual(result["posting_status"], "unverified")
                result,_ = validate(DIRECT, identity=9999999)
                self.assertEqual(result["posting_status"], "unverified")
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()

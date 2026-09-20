"""Protect distinct requisitions while recognizing cross-source ATS aliases."""
import tempfile
import unittest
from pathlib import Path

from internship_watch.storage import Store, url_identity


class IdentityTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.directory.name) / "jobs.db")

    def tearDown(self):
        self.store.close()
        self.directory.cleanup()

    def insert(self, source, source_id, description, application=None):
        job = {"source_id": source_id, "employer": "Example", "title": "Software Engineer Intern",
               "description_url": description, "application_url": application or description}
        return self.store.upsert_job(source, job, {"decision": "include", "category": "software"}, None)[0]

    def test_generic_localized_destinations_do_not_identify_jobs(self):
        for path in ("/en-us/careers", "/en/jobs", "/career/search", "/careers/apply", "/de/positions"):
            with self.subTest(path=path):
                self.assertIsNone(url_identity("https://example.com" + path))
        for host in ("boards.greenhouse.io", "jobs.lever.co", "jobs.ashbyhq.com"):
            self.assertIsNone(url_identity(f"https://{host}/example"))

    def test_shared_generic_application_does_not_merge_distinct_positions(self):
        first = self.insert("direct", "1", "https://example.com/jobs/1", "https://example.com/en-us/careers")
        second = self.insert("direct", "2", "https://example.com/jobs/2", "https://example.com/en-us/careers")
        self.assertNotEqual(first, second)
        self.assertEqual(len(self.store.rows("SELECT id FROM jobs")), 2)

    def test_shared_unknown_form_is_not_an_application_alias(self):
        first = self.insert("direct", "1", "https://example.com/jobs/1", "https://forms.example.com/f/application-form")
        second = self.insert("direct", "2", "https://example.com/jobs/2", "https://forms.example.com/f/application-form")
        self.assertNotEqual(first, second)

    def test_cross_source_greenhouse_host_and_embed_aliases_merge(self):
        direct = self.insert("direct", "gh-123", "https://boards.greenhouse.io/example/jobs/123")
        feed = self.insert("simplify", "uuid-1", "https://job-boards.greenhouse.io/example/jobs/123?utm_source=Simplify")
        embed = self.insert("other", "uuid-2", "https://boards.greenhouse.io/embed/job_app?for=example&token=123")
        self.assertEqual(direct, feed)
        self.assertEqual(direct, embed)
        self.assertEqual(len(self.store.rows("SELECT * FROM source_records")), 3)

    def test_known_application_alias_can_connect_custom_employer_page(self):
        direct = self.insert("direct", "gh-123", "https://boards.greenhouse.io/example/jobs/123")
        employer = self.insert("employer", "req-123", "https://example.com/role/software-intern",
                               "https://job-boards.greenhouse.io/example/jobs/123")
        self.assertEqual(direct, employer)

    def test_conflicting_ats_application_requisition_does_not_merge(self):
        first = self.insert("direct", "123", "https://boards.greenhouse.io/example/jobs/123")
        second = self.insert("direct", "456", "https://boards.greenhouse.io/example/jobs/456",
                             "https://boards.greenhouse.io/example/jobs/123")
        self.assertNotEqual(first, second)

    def test_distinct_requisitions_and_boards_are_distinct(self):
        ids = {self.insert("feed", str(n), url) for n, url in enumerate([
            "https://boards.greenhouse.io/a/jobs/123", "https://boards.greenhouse.io/a/jobs/456",
            "https://boards.greenhouse.io/b/jobs/123", "https://example.com/careers?jobId=123",
            "https://example.com/careers?jobId=456"])}
        self.assertEqual(len(ids), 5)

    def test_unknown_provider_references_and_spa_fragments_stay_distinct(self):
        for first, second in (("https://example.com/role?ref=123", "https://example.com/role?ref=456"),
                              ("https://example.com/recruitment#/job/123", "https://example.com/recruitment#/job/456")):
            with self.subTest(first=first):
                self.assertNotEqual(url_identity(first), url_identity(second))

    def test_lever_and_ashby_description_application_aliases(self):
        identity = "d1c2a643-0578-48bc-9517-f6c6acb95124"
        for host, suffix in (("jobs.lever.co", "apply"), ("jobs.eu.lever.co", "apply"),
                             ("jobs.ashbyhq.com", "application")):
            with self.subTest(host=host):
                description = f"https://{host}/example/{identity}"
                self.assertEqual(url_identity(description), url_identity(description + "/" + suffix))

    def test_finance_migration_preserves_history_and_exact_aliases(self):
        pairs=[('https://job-boards.eu.greenhouse.io/imc/jobs/123','https://boards.greenhouse.io/imc/jobs/123'),
               ('https://bankcampuscareers.tal.net/vx/xf-old/candidate/so/pm/1/pl/1/opp/42-Intern/en-GB','https://bankcampuscareers.tal.net/vx/candidate/so/pm/1/pl/1/opp/42-Changed-title/en-GB'),
               ('https://www.deshaw.com/careers/software-intern-42','https://www.deshaw.com/careers/renamed-intern-42')]
        ids=[]
        for i,(old,new) in enumerate(pairs):
            ids.append(self.insert('feed',str(i),old))
        history=self.store.rows('SELECT id,first_seen,baseline FROM jobs ORDER BY id')
        self.store.db.execute("DELETE FROM identities WHERE identity LIKE 'url:%'")
        self.store.db.execute("DELETE FROM meta WHERE key='finance_url_aliases_v1'");self.store.db.commit();self.store.close()
        self.store=Store(Path(self.directory.name)/'jobs.db')
        for i,(old,new) in enumerate(pairs):self.assertEqual(self.insert('direct',str(i),new),ids[i])
        self.assertEqual(self.store.rows('SELECT id,first_seen,baseline FROM jobs ORDER BY id'),history)

    def test_conflicting_employer_application_is_never_a_merge_alias(self):
        application='https://career8.successfactors.com/sfcareer/jobreqcareer?jobId=44&company=MoodysProd'
        original=self.insert('feed','44',application)
        job={'source_id':'100','employer':"Moody's",'title':'Data Analyst Intern','description_url':'https://careers.moodys.com/en/job/new-york/data-intern/49841/100','application_url':application,'evidence':{'application_identity_conflict':{'posting_requisition':'43','application_requisition':'44'}}}
        other=self.store.upsert_job('moodys',job,{'decision':'include','category':'data_analysis'},None)[0]
        self.assertNotEqual(original,other)


if __name__ == "__main__":
    unittest.main()

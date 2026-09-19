"""HRT's real multi-select schema must survive the collection/storage boundary."""
import tempfile
import unittest
from pathlib import Path

from internship_watch.classify import classify
from internship_watch.sources import SourceError, collect
from internship_watch.storage import Store
from tests.test_sources import Client


class EmploymentStorageTests(unittest.TestCase):
    def job(self, value):
        return {"id": 7964062, "title": "Quant Research Internship - Summer 2027",
                "absolute_url": "https://www.hudsonrivertrading.com/careers/job/?gh_jid=7964062",
                "content": "As an intern, develop algorithmic trading strategies. Open to undergraduate students.",
                "location": {"name": "New York, NY, United States"},
                "metadata": [{"name": "Job Type", "type": "multi_select", "value": value}]}

    def collect(self, value):
        source = {"id": "hrt", "type": "greenhouse", "slug": "wehrtyou", "employer": "Hudson River Trading"}
        return collect(source, Client({"jobs": [self.job(value)], "meta": {"total": 1}}))[0]

    def test_multiselect_reaches_sqlite_without_losing_internship_evidence(self):
        row = self.collect(["Internship"])
        self.assertEqual(row["employment_type"], "Internship")
        self.assertEqual(row["evidence"]["metadata"][0]["value"], ["Internship"])
        decision = classify(row, {"countries": ["US"]})
        self.assertEqual(decision["decision"], "include")
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp) / "test.sqlite3")
            try:
                with store.transaction():
                    store.upsert_job("hrt", row, decision, None, baseline=True)
                saved = store.rows("SELECT employment_type,classification FROM jobs")[0]
                self.assertEqual(saved, {"employment_type": "Internship", "classification": "include"})
            finally:
                store.close()

    def test_multiple_values_preserved_and_empty_value_is_unknown(self):
        self.assertEqual(self.collect(["Internship", "Co-op", "Internship"])["employment_type"], "Internship; Co-op")
        self.assertIsNone(self.collect([])["employment_type"])

    def test_changed_structured_schema_fails_as_source_error(self):
        for value in ([{"label": "Internship"}], {"name": "Internship"}):
            with self.subTest(value=value), self.assertRaises(SourceError):
                self.collect(value)


if __name__ == "__main__":
    unittest.main()

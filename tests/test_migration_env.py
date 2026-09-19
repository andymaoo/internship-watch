import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from internship_watch.cli import load_env
from internship_watch.storage import Store, split_statuses


class MigrationTests(unittest.TestCase):
    def test_application_closed_does_not_close_posting(self):
        result = {"validator_version": 4, "status": "closed", "checks": [
            {"kind": "description", "status": "open"}, {"kind": "application", "status": "closed"}]}
        self.assertEqual(split_statuses(result, historical=True), ("open", "closed"))
        self.assertEqual(split_statuses(dict(result, validator_version=3), historical=True), ("unverified", "unverified"))

    def test_v1_migration_preserves_history_and_delivery(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "db"
            # Build an actual v1 schema from the reviewed commit's column layout.
            db = sqlite3.connect(path)
            db.executescript("""CREATE TABLE jobs(id TEXT PRIMARY KEY,employer TEXT,title TEXT,classification TEXT,
                status TEXT,first_seen TEXT,next_check TEXT,last_checked TEXT);
                CREATE TABLE link_checks(id INTEGER PRIMARY KEY,job_id TEXT,checked_at TEXT,result TEXT);
                CREATE TABLE outbox(id INTEGER PRIMARY KEY,dedupe_key TEXT UNIQUE,kind TEXT,payload TEXT,
                created_at TEXT,status TEXT,attempts INTEGER,next_attempt TEXT,last_error TEXT,delivered_at TEXT);
                PRAGMA user_version=1;""")
            result = {"validator_version": 4, "status": "unverified", "checks": [
                {"kind": "description", "status": "open"}, {"kind": "application", "status": "unverified"}]}
            db.execute("INSERT INTO jobs VALUES('a','Example','Intern','include','unverified','2026-01-01',NULL,'2026-01-02')")
            db.execute("INSERT INTO jobs VALUES('b','Changed','Different Intern','include','unverified','2026-01-01',NULL,NULL)")
            db.execute("INSERT INTO link_checks VALUES(1,'a','2026-01-02',?)", (json.dumps(result),))
            db.execute("INSERT INTO link_checks VALUES(2,'b','2026-01-02',?)", (json.dumps(result),))
            db.execute("INSERT INTO outbox VALUES(1,'initial:digest','digest','{}','2026-01-02','delivered',1,'2026-01-02',NULL,'2026-01-02')")
            db.commit(); db.close()
            store = Store(path)
            row = store.rows("SELECT * FROM jobs")[0]
            self.assertEqual((row['posting_status'], row['application_status']), ('open', 'unverified'))
            self.assertEqual(row['first_seen'], '2026-01-01')
            self.assertIsNone(row['notification_decided_at'])
            self.assertEqual(store.rows('SELECT * FROM outbox')[0]['status'], 'delivered')
            self.assertEqual(store.rows("SELECT posting_status FROM jobs WHERE id='b'")[0]['posting_status'], 'unverified')
            self.assertEqual(len(store.rows('SELECT * FROM link_checks')), 2)
            store.close()
            store = Store(path)
            self.assertEqual(store.db.execute('PRAGMA user_version').fetchone()[0], 2)
            store.close()

    def test_migration_makes_older_validator_evidence_due_without_erasing_history(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "db"
            db = sqlite3.connect(path)
            db.executescript("""CREATE TABLE jobs(id TEXT PRIMARY KEY,employer TEXT,title TEXT,classification TEXT,
                status TEXT,first_seen TEXT,next_check TEXT,last_checked TEXT);
                CREATE TABLE link_checks(id INTEGER PRIMARY KEY,job_id TEXT,checked_at TEXT,result TEXT);
                PRAGMA user_version=1;""")
            for index, version in enumerate((None, 3, 4), 1):
                result = {"status": "closed", "checks": [
                    {"kind": "description", "status": "closed"}, {"kind": "application", "status": "closed"}]}
                if version is not None:
                    result["validator_version"] = version
                db.execute("INSERT INTO jobs VALUES(?, 'Example','Intern','include','closed','2026-01-01','2099-01-01','2026-01-02')", (str(index),))
                db.execute("INSERT INTO link_checks VALUES(?,?,'2026-01-02',?)", (index, str(index), json.dumps(result)))
            db.commit(); db.close()
            store = Store(path)
            try:
                rows = store.rows("SELECT status,posting_status,application_status,next_check FROM jobs ORDER BY id")
                for row in rows[:2]:
                    self.assertEqual(row, {"status": "unverified", "posting_status": "unverified", "application_status": "unverified", "next_check": None})
                self.assertEqual(rows[2], {"status": "closed", "posting_status": "closed", "application_status": "closed", "next_check": "2099-01-01"})
                self.assertEqual(len(store.rows("SELECT * FROM link_checks")), 3)
            finally:
                store.close()

    def test_private_file_literal_values_and_rejected_unknown_keys(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {}, clear=True):
            path = Path(temp) / '.env'
            path.write_text('# private\nDISCORD_WEBHOOK_URL="literal$(not-a-shell)"\nHEALTHCHECKS_PING_URL=\n')
            load_env(path)
            self.assertEqual(os.environ['DISCORD_WEBHOOK_URL'], 'literal$(not-a-shell)')
            self.assertEqual(os.environ['HEALTHCHECKS_PING_URL'], '')
            path.write_text('PATH=secret-sentinel')
            with self.assertRaisesRegex(ValueError, 'line 1') as error:
                load_env(path)
            self.assertNotIn('secret-sentinel', str(error.exception))


if __name__ == '__main__':
    unittest.main()

"""Backup regression fixtures; no provider access or real secret values."""
import argparse
import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import backup


class BackupTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.root = Path(self.folder.name)
        self.source = self.root / "jobs.sqlite3"
        with contextlib.closing(sqlite3.connect(self.source)) as connection:
            connection.executescript("CREATE TABLE jobs(id TEXT PRIMARY KEY,first_seen TEXT);"
                                     "CREATE TABLE outbox(id INTEGER PRIMARY KEY,status TEXT);"
                                     "INSERT INTO jobs VALUES('one','2026-01-01');"
                                     "INSERT INTO outbox VALUES(1,'pending');")
            connection.commit()
        self.config = self.root / "config.json"
        self.config.write_text(json.dumps({"database": "jobs.sqlite3"}), encoding="utf-8")
        self.state = self.root / "backups"
        self.state.mkdir()

    def tearDown(self):
        self.folder.cleanup()

    def test_online_backup_and_restored_manifest_keep_pending_delivery(self):
        target = self.state / "copy.sqlite3"
        expected = backup.sqlite_snapshot(self.source, target)
        restored = self.state / "restored.sqlite3"
        shutil.copyfile(target, restored)
        self.assertEqual(backup.inspect_database(restored, expected), expected)
        self.assertEqual(expected["tables"]["outbox"]["rows"], 1)

    def test_changed_restored_row_is_detected(self):
        target = self.state / "copy.sqlite3"
        expected = backup.sqlite_snapshot(self.source, target)
        with contextlib.closing(sqlite3.connect(target)) as connection:
            connection.execute("UPDATE outbox SET status='delivered'")
            connection.commit()
        with self.assertRaisesRegex(RuntimeError, "does not match"):
            backup.inspect_database(target, expected)

    def test_source_cannot_be_replaced_and_partial_is_preserved(self):
        with self.assertRaises(ValueError):
            backup.sqlite_snapshot(self.source, self.source)
        target = self.state / "copy.sqlite3"
        partial = target.with_name(target.name + ".partial")
        partial.write_text("preserve failed attempt", encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "partial"):
            backup.sqlite_snapshot(self.source, target)
        self.assertEqual(partial.read_text(), "preserve failed attempt")

    def test_local_only_restores_without_any_monitor_or_provider_call(self):
        args = argparse.Namespace(config=str(self.config), local_only=True, compose_dir=None)
        with patch.object(backup, "ping") as ping, patch.object(backup, "command") as command, contextlib.redirect_stdout(io.StringIO()):
            backup.perform(args, self.state)
        ping.assert_not_called()
        command.assert_not_called()
        evidence = json.loads((self.state / "last-success.json").read_text())
        self.assertTrue(evidence["local_only"])
        self.assertTrue(evidence["restored_database_verified"])

    def test_remote_success_requires_restore_before_success_heartbeat(self):
        args = argparse.Namespace(config=str(self.config), local_only=False, compose_dir=None)
        calls = []
        def run(command, cwd=None):
            calls.append(command[1])
            if command[1] == "backup":
                return json.dumps({"message_type": "summary", "snapshot_id": "a" * 64})
            if command[1] == "restore":
                target = Path(command[command.index("--target") + 1])
                shutil.copyfile(self.state / "latest.sqlite3", target / "latest.sqlite3")
            return ""
        values = {"RESTIC_REPOSITORY": "test", "RESTIC_PASSWORD_FILE": "private-file",
                  "BACKUP_HEALTHCHECKS_PING_URL": "https://example.invalid/check"}
        with patch.dict(os.environ, values), patch.object(backup, "command", side_effect=run), patch.object(backup, "ping") as ping, contextlib.redirect_stdout(io.StringIO()):
            backup.perform(args, self.state)
        self.assertEqual(calls, ["backup", "restore", "check", "forget"])
        self.assertEqual([call.args for call in ping.call_args_list], [("/start",), ()])
        self.assertFalse(json.loads((self.state / "last-success.json").read_text())["local_only"])

    def test_remote_failure_never_signals_success(self):
        args = argparse.Namespace(config=str(self.config), local_only=False, compose_dir=None)
        values = {"RESTIC_REPOSITORY": "test", "RESTIC_PASSWORD_FILE": "private-file",
                  "BACKUP_HEALTHCHECKS_PING_URL": "https://example.invalid/check"}
        with patch.dict(os.environ, values), patch.object(backup, "command", side_effect=RuntimeError("upload failed")), patch.object(backup, "ping") as ping:
            with self.assertRaisesRegex(RuntimeError, "upload failed"):
                backup.perform(args, self.state)
        self.assertEqual([call.args for call in ping.call_args_list], [("/start",), ("/fail",)])
        self.assertFalse((self.state / "last-success.json").exists())


if __name__ == "__main__":
    unittest.main()

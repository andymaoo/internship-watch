"""Consistent SQLite backup, encrypted restic upload, and restored-data verification.

No provider credentials are accepted as arguments or printed. Off-host mode
requires an initialized restic repository and a separate backup heartbeat.
"""
import argparse
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from internship_watch.locking import run_lock

def stamp():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect_readonly(path):
    return sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True, timeout=30)


def manifest(connection):
    tables = {}
    for name, sql in connection.execute("SELECT name,sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"):
        quoted = '"' + name.replace('"', '""') + '"'
        columns = [row[1] for row in connection.execute("PRAGMA table_info(" + quoted + ")")]
        order = ",".join('"' + column.replace('"', '""') + '"' for column in columns)
        digest = hashlib.sha256()
        count = 0
        for row in connection.execute("SELECT * FROM " + quoted + " ORDER BY " + order):
            # Application tables use SQLite strings/numbers/null; bytes remain
            # deterministic if a future schema introduces blobs.
            values = [{"bytes_hex": value.hex()} if isinstance(value, bytes) else value for value in row]
            digest.update(json.dumps(values, ensure_ascii=False, separators=(",", ":")).encode("utf-8") + b"\n")
            count += 1
        tables[name] = {"rows": count, "sha256": digest.hexdigest(), "schema": sql}
    return {"user_version": connection.execute("PRAGMA user_version").fetchone()[0], "tables": tables}


def inspect_database(path, expected=None):
    with closing(connect_readonly(path)) as connection:
        if connection.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
            raise RuntimeError("SQLite integrity check failed")
        result = manifest(connection)
    if expected is not None and result != expected:
        raise RuntimeError("Restored database does not match the saved manifest")
    return result


def sqlite_snapshot(source, destination):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if source == destination or (destination.exists() and os.path.samefile(source, destination)):
        raise ValueError("Backup destination must differ from the source database")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".partial")
    if temporary.exists():
        raise RuntimeError("Previous partial backup exists; inspect it before retrying")
    with closing(connect_readonly(source)) as connection:
        connection.execute("BEGIN")
        expected = manifest(connection)
        target = sqlite3.connect(temporary)
        try:
            connection.backup(target, pages=256, sleep=0.05)
        finally:
            target.close()
    inspect_database(temporary, expected)
    os.replace(temporary, destination)
    return expected


def ping(suffix=""):
    secret = os.environ.get("BACKUP_HEALTHCHECKS_PING_URL", "")
    if not secret or urlsplit(secret).scheme != "https":
        raise RuntimeError("Set BACKUP_HEALTHCHECKS_PING_URL to the separate HTTPS backup check")
    for attempt in range(3):
        try:
            with urlopen(Request(secret.rstrip("/") + suffix, data=b""), timeout=10) as response:
                if not 200 <= response.status < 300:
                    raise RuntimeError("Backup monitor did not acknowledge the ping")
            return
        except Exception:
            if attempt == 2:
                raise RuntimeError("Backup heartbeat request failed; secret URL omitted") from None
            time.sleep(attempt + 1)


def command(arguments, cwd=None):
    try:
        result = subprocess.run(arguments, cwd=cwd, capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=1800, check=False)
    except subprocess.TimeoutExpired:
        raise RuntimeError("Backup subprocess timed out") from None
    if result.returncode:
        # Provider output can contain repository URLs; do not expose it here.
        raise RuntimeError(f"Backup subprocess {Path(arguments[0]).name} failed with exit {result.returncode}; inspect provider configuration privately")
    return result.stdout


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config")
    parser.add_argument("--state-dir")
    parser.add_argument("--local-only", action="store_true")
    parser.add_argument("--compose-dir", help="Use the running watcher container's SQLite backup CLI")
    parser.add_argument("--verify", help="Read-only verification of a restored SQLite file")
    parser.add_argument("--manifest", help="Expected manifest JSON for --verify")
    args = parser.parse_args(argv)
    if args.verify:
        if not args.manifest:
            parser.error("--verify requires --manifest")
        expected = json.loads(Path(args.manifest).read_text(encoding="utf-8"))["database"]
        result = inspect_database(args.verify, expected)
        print(json.dumps({"verified": True, "tables": {name: row["rows"] for name, row in result["tables"].items()}}))
        return
    if not args.config or not args.state_dir:
        parser.error("--config and --state-dir are required")
    state = Path(args.state_dir).resolve()
    state.mkdir(parents=True, exist_ok=True)
    with run_lock(str(state / "backup.lock")):
        return perform(args, state)


def perform(args, state):
    if not args.local_only:
        for variable in ("RESTIC_REPOSITORY", "RESTIC_PASSWORD_FILE", "BACKUP_HEALTHCHECKS_PING_URL"):
            if not os.environ.get(variable):
                raise RuntimeError(f"Missing required environment variable: {variable}")
        ping("/start")
    try:
        config_path = Path(args.config).resolve()
        config = json.loads(config_path.read_text(encoding="utf-8-sig"))
        snapshot = state / "latest.sqlite3"
        if args.compose_dir:
            compose_dir = Path(args.compose_dir).resolve()
            docker = ["docker", "compose", "--project-directory", str(compose_dir), "-f", str(compose_dir / "compose.yaml")]
            command(docker + ["exec", "-T", "watcher", "python", "-m", "internship_watch", "--config", "/app/config.json",
                             "backup", "/app/data/backup-staging.sqlite3"])
            partial = state / "latest.sqlite3.partial"
            if partial.exists():
                raise RuntimeError("Previous partial backup exists; inspect it before retrying")
            command(docker + ["cp", "watcher:/app/data/backup-staging.sqlite3", str(partial)])
            database_manifest = inspect_database(partial)
            os.replace(partial, snapshot)
            method = "SQLite online backup inside watcher container, then copied and verified"
        else:
            source = (config_path.parent / config.get("database", "data/jobs.sqlite3")).resolve()
            database_manifest = sqlite_snapshot(source, snapshot)
            method = "SQLite online backup and all-table hash comparison from one read transaction"
        record = {"created_at": stamp(), "method": method, "database": database_manifest}
        (state / "latest.manifest.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        # This project keeps credentials in environment files, not JSON config.
        shutil.copyfile(config_path, state / "config.json")
        with tempfile.TemporaryDirectory(prefix="restore-check-", dir=state) as folder:
            restored_root = Path(folder).resolve()
            if not restored_root.is_relative_to(state):
                raise RuntimeError("Restore verification path escaped backup directory")
            if args.local_only:
                restored = restored_root / "latest.sqlite3"
                shutil.copyfile(snapshot, restored)
                snapshot_id = None
            else:
                text = command(["restic", "backup", "--json", "--tag", "internship-watch",
                                "latest.sqlite3", "latest.manifest.json", "config.json"], cwd=state)
                summaries = [json.loads(line) for line in text.splitlines() if line.strip().startswith("{")]
                snapshot_id = next((row.get("snapshot_id") for row in reversed(summaries) if row.get("message_type") == "summary"), None)
                if not snapshot_id or not re.fullmatch(r"[0-9a-f]{8,64}", snapshot_id):
                    raise RuntimeError("Restic did not return an acknowledged snapshot ID")
                command(["restic", "restore", snapshot_id, "--target", str(restored_root), "--verify"])
                files = list(restored_root.rglob("latest.sqlite3"))
                if len(files) != 1:
                    raise RuntimeError("Restored snapshot did not contain exactly one expected database")
                restored = files[0]
            inspect_database(restored, database_manifest)
        if not args.local_only:
            command(["restic", "check"])
            command(["restic", "forget", "--tag", "internship-watch", "--group-by", "host,paths",
                     "--keep-daily", "7", "--keep-weekly", "4", "--keep-monthly", "6", "--prune"])
            ping()
        outcome = {"at": stamp(), "local_only": args.local_only, "snapshot_id": snapshot_id,
                   "restored_database_verified": True,
                   "tables": {name: row["rows"] for name, row in database_manifest["tables"].items()},
                   "database_bytes": snapshot.stat().st_size}
        (state / "last-success.json").write_text(json.dumps(outcome, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(outcome))
    except Exception:
        if not args.local_only:
            try:
                ping("/fail")
            except Exception:
                pass  # Missing-success deadline is the independent fallback.
        raise


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Backup failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)

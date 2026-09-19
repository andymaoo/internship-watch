"""Audit every configured source without writing to the job DB or sending alerts.

Run from any directory: python /path/to/repo/scripts/check_sources.py
    --config /path/to/config.json --output /path/to/audit-output
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from internship_watch.http import HttpClient
from internship_watch.sources import collect


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, value):
    """Replace a complete UTF-8 JSON document, never a partly written report."""
    data = json.dumps(value, ensure_ascii=True, allow_nan=False, indent=2) + "\n"
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix="." + path.name + ".", suffix=".tmp", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def check_sources(config: dict, output: Path, client) -> dict:
    report, jobs = [], []
    summary = {"started_at": timestamp(), "completed_at": None, "completed": False,
               "configured_sources": len(config["sources"]),
               "enabled_sources": sum(source.get("enabled", True) for source in config["sources"]),
               "disabled_sources": sum(not source.get("enabled", True) for source in config["sources"]),
               "checked_sources": 0, "failed_sources": 0, "collected_records": 0}
    output.mkdir(parents=True, exist_ok=True)

    def checkpoint():
        # summary is written last: completed=true means both data files finished.
        write_json(output / "source-live.json", report)
        write_json(output / "source-jobs.json", jobs)
        write_json(output / "summary.json", summary)

    checkpoint()
    try:
        for source in config["sources"]:
            enabled = source.get("enabled", True)
            if not enabled:
                report.append({"source": source["id"], "type": source["type"], "enabled": False,
                               "status": "disabled", "reason": source.get("disabled_reason", "Disabled by configuration")})
                checkpoint()
                continue
            started = time.monotonic()
            entry = {"source": source["id"], "type": source["type"], "enabled": True, "checked_at": timestamp()}
            try:
                records = collect(source, client)
                entry.update(status="unexpected_empty" if source.get("expect_nonempty") and not records else "ok",
                             collected=len(records), missing_descriptions=sum(not job.get("description") for job in records),
                             missing_full_descriptions=sum(not job.get("description") or job.get("evidence", {}).get("description_kind") == "employer_search_summary" for job in records),
                             sample=[{"id": job["source_id"], "title": job["title"], "url": job["description_url"]} for job in records[:3]])
                jobs.extend(dict(job, source=source["id"]) for job in records)
            except Exception as exc:
                entry.update(status="unverified", error=f"{type(exc).__name__}: {exc}")
            entry["seconds"] = round(time.monotonic() - started, 2)
            report.append(entry)
            summary["checked_sources"] += 1
            summary["failed_sources"] += entry["status"] != "ok"
            summary["collected_records"] = len(jobs)
            checkpoint()
            # ASCII JSON remains readable on Windows consoles with legacy codecs.
            print(json.dumps({"source": source["id"], "status": entry["status"],
                              "collected": entry.get("collected"), "error": entry.get("error")}, ensure_ascii=True), flush=True)
    except BaseException:
        summary["interrupted_at"] = timestamp()
        checkpoint()
        raise
    summary.update(completed=True, completed_at=timestamp())
    checkpoint()
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "config.example.json", help="Configuration JSON; defaults to the checked-in example")
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "source-audit", help="Report directory; existing report files are replaced atomically")
    args = parser.parse_args(argv)
    config = json.loads(args.config.read_text(encoding="utf-8-sig"))
    sources = config.get("sources")
    if not isinstance(sources, list):
        parser.error("Configuration must contain a sources array")
    ids = [source["id"] for source in sources]
    if len(ids) != len(set(ids)):
        parser.error("Source IDs must be unique")
    client = HttpClient(**config.get("http", {}))
    try:
        summary = check_sources(config, args.output.resolve(), client)
    finally:
        client.close()
    print(json.dumps(summary, ensure_ascii=True), flush=True)
    return 1 if summary["failed_sources"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Load a private .env without printing it, then run a supervised local command."""
import argparse
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import re
import subprocess
import sys

ALLOWED = {"DISCORD_WEBHOOK_URL", "OPS_DISCORD_WEBHOOK_URL", "HEALTHCHECKS_PING_URL",
           "NTFY_URL", "NTFY_TOKEN", "OPS_NTFY_URL", "OPS_NTFY_TOKEN",
           "RESTIC_REPOSITORY", "RESTIC_PASSWORD_FILE", "RESTIC_CACHE_DIR",
           "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_DEFAULT_REGION",
           "BACKUP_HEALTHCHECKS_PING_URL"}


def load_env(path):
    for number, line in enumerate(Path(path).read_text(encoding="utf-8-sig").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.fullmatch(r"([A-Z][A-Z0-9_]*)=(.*)", line)
        if not match or match[1] not in ALLOWED:
            raise ValueError(f"Invalid or unsupported environment setting at line {number}; contents omitted")
        value = match[2].strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ[match[1]] = value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--env-file", required=True)
    parser.add_argument("--mode", choices=("daemon", "backup"), default="daemon")
    parser.add_argument("--state-dir", required=True)
    args = parser.parse_args()
    load_env(args.env_file)
    repository = Path(__file__).resolve().parents[1]
    state = Path(args.state_dir).resolve()
    state.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("internship-watch-service")
    logger.setLevel(logging.INFO)
    handler = RotatingFileHandler(state / (args.mode + ".log"), maxBytes=10 * 1024 * 1024,
                                  backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
    logger.addHandler(handler)
    if args.mode == "daemon":
        command = [sys.executable, "-m", "internship_watch", "--config", str(Path(args.config).resolve()), "daemon"]
    else:
        command = [sys.executable, str(repository / "deploy" / "backup.py"), "--config",
                   str(Path(args.config).resolve()), "--state-dir", str(state / "backups")]
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    process = subprocess.Popen(command, cwd=repository, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               text=True, encoding="utf-8", errors="replace", bufsize=1, creationflags=flags)
    try:
        for line in process.stdout:
            logger.info(line.rstrip())
        return process.wait()
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
        handler.close()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"Windows launcher failed: {type(exc).__name__}; inspect paths, permissions, and configuration privately", file=sys.stderr)
        sys.exit(1)

# Deployment preparation

This repository contains deployment preparation, not proof of a permanent running deployment. Real sources and Discord have been exercised locally; no paid server, reboot startup, external heartbeat or off-host backup is active. Complete the acceptance procedure below on the chosen host before calling the system deployed. [Current evidence](CONTINUATION.md)

Use [HOSTING.md](HOSTING.md) for the current price comparison and measurement-based sizing, and [CONNECTIONS.md](CONNECTIONS.md) for private monitor/bucket setup, encrypted off-host backup scheduling, and the Windows Task Scheduler option. Those prepared files do not create accounts or authorize spending.

## Choose one runtime

Prefer the supplied Linux systemd daemon on an already-owned, always-on host. It polls according to `poll_seconds` (the requested production setting is `300`), uses one writer and a kernel-owned lock, and keeps SQLite outside the release directory. The Docker alternative runs the same daemon as UID/GID 10001 with a persistent named volume. Do not enable both runtimes against the same deployment.

An existing host can have $0 incremental hosting cost, plus electricity. Student cloud benefits should be evaluated first; current eligibility and complete compute/network/disk/backup costs are in [HOSTING.md](HOSTING.md). The paid fallback is a 1 GiB DigitalOcean instance at $6/month plus tax and backup overage; optional weekly provider images add $1.20. Healthchecks.io's free plan is sufficient for the external check. Account selection and any spending require the user's approval; preparation does not authorize a purchase.

GitHub Actions is retained for tests only. Its delayed/dropped schedule behavior and ephemeral workers do not provide the desired runtime/storage guarantees. The old production scrape schedule and automatic `seen.json` commits have been removed. Keep `seen.json` as an explicitly imported migration artifact.

## Configure secrets privately

Create a Discord incoming webhook in the desired job notification channel and another in the operational alert channel, using the connected account or the provider's own settings. The operational webhook can fall back to the primary webhook, but a separately configured Healthchecks email recipient should remain independent of Discord.

Create a Healthchecks.io check in its own hosted service, configure its notification destination, and obtain its ping URL. Enter these values directly into host-side secret configuration or a protected file; **do not paste webhook tokens, passwords, or ping URLs into chat**. The variable names are in `.env.example`:

- `DISCORD_WEBHOOK_URL` and optional `OPS_DISCORD_WEBHOOK_URL`.
- `HEALTHCHECKS_PING_URL` for the external monitor.
- If retaining ntfy, choose `notifications.channel: "ntfy"` and configure `NTFY_URL`/`NTFY_TOKEN`, with optional `OPS_NTFY_URL`/`OPS_NTFY_TOKEN`. `NTFY_URL` is the complete HTTPS topic URL. Old `NTFY_TOPIC` is not a runtime setting in the new worker.

Restrict the secret file to its owner (`chmod 600`). Never commit it or include it in build context, support logs, screenshots, or exported reports. Changing a webhook requires updating the secret file and restarting/recreating the worker.

## Preferred: systemd on Linux

Prerequisites: a supported Linux host with systemd and Python 3.12 plus `venv`; SSH or a supported host connection; this prepared checkout copied to `/opt/internship-watch`. Use the dedicated directory and user below so existing applications remain separate.

`requirements.txt` pins the tested Requests 2.34.2 dependency set, including its transitive dependencies. Install from that file rather than installing an unpinned `requests`. Regression tests include the reviewed source fixture under `tests/fixtures`, so a source-only package can run them without Git history.

Run these commands on the selected host after access is available:

```sh
sudo useradd --system --user-group --home-dir /var/lib/internship-watch --shell /usr/sbin/nologin internship-watch
sudo install -d -o internship-watch -g internship-watch -m 0750 /var/lib/internship-watch
cd /opt/internship-watch
sudo python3.12 -m venv .venv
sudo .venv/bin/python -m pip install -r requirements.txt
sudo .venv/bin/python -m unittest discover -s tests -v
sudo install -o root -g root -m 0644 config.example.json /etc/internship-watch.json
sudo python3.12 -c 'import json; p="/etc/internship-watch.json"; c=json.load(open(p)); c["database"]="/var/lib/internship-watch/jobs.sqlite3"; c["export_directory"]="/var/lib/internship-watch/export"; c["poll_seconds"]=300; json.dump(c,open(p,"w"),indent=2)'
sudo install -o root -g root -m 0600 .env.example /etc/internship-watch.env
sudoedit /etc/internship-watch.env
sudo install -o root -g root -m 0644 deploy/internship-watch.service /etc/systemd/system/internship-watch.service
sudo systemctl daemon-reload
```

For an existing installation, reuse its service user and secret file rather than repeating `useradd` or replacing credentials with the example. Review geography, seasons, eligibility, companies, notification channel, and initial behavior in `/etc/internship-watch.json`. Database paths resolve relative to the config file unless absolute; the systemd setup deliberately uses the absolute persistent path above.

**Preserve the existing database before first collection.** The delivered `outputs/continuation/internships.sqlite3` is a consistent snapshot including source history, baseline membership and Discord receipts. Transfer it privately with SCP/SFTP to the chosen host, then install it while the service is stopped. Replace `/path/to/uploaded/internships.sqlite3` below with that actual upload path; never overwrite an existing newer production database. Starting with an empty database would discard the delivery ledger and could resend the initial report.

```sh
sudo install -o internship-watch -g internship-watch -m 0600 /path/to/uploaded/internships.sqlite3 /var/lib/internship-watch/jobs.sqlite3
cd /opt/internship-watch
sudo -u internship-watch .venv/bin/python -c 'import sqlite3; c=sqlite3.connect("/var/lib/internship-watch/jobs.sqlite3"); print(c.execute("PRAGMA integrity_check").fetchone()[0]); print("jobs", c.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]); print("deliveries", c.execute("SELECT status,COUNT(*) FROM outbox GROUP BY status").fetchall())'
sudo -u internship-watch .venv/bin/python -m internship_watch --config /etc/internship-watch.json status
```

`seen.json` contains historical IDs, not delivery receipts. The supplied database already preserves the current initial-run state; an optional `import-seen seen.json` is a separate suppression choice, not a replacement for database migration. Once configuration, state and private secrets are installed:

```sh
cd /opt/internship-watch
sudo systemctl enable --now internship-watch
sudo systemctl status internship-watch --no-pager
sudo journalctl -u internship-watch -n 100 --no-pager
```

The daemon catches cycle failures, records them, and retries later. Systemd restarts a crashed process and starts it after a host reboot. This provides persistence and process supervision, not a service-level guarantee. A run taking longer than five minutes delays the next cycle; overlapping runs are skipped. See [OPERATIONS.md](OPERATIONS.md) for measuring backlog and alerts.

## Alternative: Docker Compose

Prerequisites: Docker Engine/Compose with a running Linux-container daemon. The image pins `python:3.12.14-slim-bookworm`, observed in the [official image manifest](https://raw.githubusercontent.com/docker-library/official-images/master/library/python). Periodically review updates; this tag pin is not an immutable digest or a promise of permanent security support.

```sh
cp config.example.json config.json
cp .env.example .env
chmod 600 .env
```

For a new checkout only, use the copies above; preserve existing files on update. Set `database` to `data/jobs.sqlite3` and `export_directory` to `data/export` in `config.json` (therefore under persistent `/app/data` in the container), set `poll_seconds` to `300`, choose the notification channel, and enter secrets directly into `.env` using the host editor. Build first:

```sh
docker compose config --quiet
docker compose build --pull
```

Create the volume/container with `docker compose create`, then copy the consistent existing SQLite snapshot to `/app/data/jobs.sqlite3` using `docker compose cp /path/to/uploaded/internships.sqlite3 watcher:/app/data/jobs.sqlite3`. Before starting, set the copied file to UID/GID 10001:10001 and mode 0600 using a one-off container restricted to this volume. Inspect its integrity and saved delivery counts as above. Do not use a fresh volume as a substitute for migrating the current state. After that, run `docker compose up -d` and `docker compose logs --tail=100 watcher`.

The named volume `internship-watch-data` persists independently of the checkout directory and image. A newly created Docker volume inherits `/app/data` ownership (10001:10001) from the image. If reusing a volume created under another UID, stop the worker and deliberately repair only that volume's ownership before starting; do not run the worker as root to mask a permissions problem. A host bind mount alternative must be prepared with UID/GID 10001 ownership.

Do **not** use `docker compose down --volumes`, delete `internship-watch-data`, or place SQLite only inside the container image. Deploy code updates with `docker compose up -d --build` and retain the named volume/config/secret file. No public port is exposed. Export reports from the volume with the operations commands below.

## Access the private updated report

Every completed cycle replaces `/var/lib/internship-watch/export/jobs.html`, `jobs.csv`, `jobs.json`, and the source/link evidence files. The simplest access is SFTP download of that **export directory only** using the chosen host's SSH account. The service directory has restricted permissions; grant the chosen SSH account read access to exports or copy exports to its private download directory, rather than loosening permissions on the database or secret files.

For a live view, start a loopback-only file server on the host in a dedicated SSH session:

```sh
sudo -u internship-watch /opt/internship-watch/.venv/bin/python -m http.server 8765 --bind 127.0.0.1 --directory /var/lib/internship-watch/export
```

On the PC, run `ssh -N -L 8765:127.0.0.1:8765 USER@HOST`, substituting the actual SSH user and host. Open `http://127.0.0.1:8765/jobs.html` or `http://127.0.0.1:8765/jobs.csv`; refresh to see subsequent exports. No inbound HTTP port, domain or public dashboard is needed. Close the tunnel and stop the temporary file server with Ctrl+C when done. Only report files are served, not the SQLite database or private environment files. On Windows hosting, open `data/export/jobs.html` directly and refresh after cycles.

## Acceptance evidence required

Save a dated deployment evidence report containing:

1. The exact deployed commit or package hash, host/runtime, config (without secrets), and enabled source list.
2. At least two naturally scheduled cycles with start/end times, source counts/errors, validation counts, and durable notification attempts. A manual run alone is not a scheduled-run test.
3. A pre-restart and post-restart comparison of job counts, stable IDs/first-seen times, source state, run history, and pending deliveries. Restart must use the same persistent database.
4. The receipt from `test-notification` and confirmation that it appeared in the subscribed destination. Provider HTTP acceptance alone does not prove the user saw it.
5. A labeled `test-failure-alert`, a controlled persistent source failure (three failing cycles by default), one incident notification, and recovery. Use a temporary copy of the source configuration pointing to a deliberately unavailable endpoint, then restore it.
6. Stop the scraper, allow the external heartbeat deadline/grace to expire, and confirm the independent monitor's alert. Restart the worker and confirm recovery. This is separate from explicitly sending `/fail`.
7. A database backup and successful restore into a separate test path. Verify restored records and notification history before considering the backup usable.

The local environment available during preparation did not have an accessible running Docker engine or Linux systemd; image build, unit startup, persistent-volume behavior, final full-source scheduled operation, and external alert delivery must therefore be validated on the target host. Three later local full-source cycles and real Discord tests are documented in [CONTINUATION.md](CONTINUATION.md); the earlier one-source smoke remains in [VALIDATION.md](VALIDATION.md). A CLI help check or YAML parse does not replace deployment acceptance.

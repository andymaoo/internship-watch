# Operating Internship Watch

Use [DEPLOYMENT.md](DEPLOYMENT.md) to provision the selected runtime. This guide distinguishes stored evidence from live guarantees. An `open` job has passed the current description/application validator at `last_checked`; an `unverified` job needs another check or manual review. A blocked page, timeout, or rate limit is not proof of closure. Inspect `link-validation.json` for the reason and each destination.

## Configuration and first run

Edit `config.json` (Docker) or `/etc/internship-watch.json` (systemd). Use `poll_seconds: 300` for the five-minute target, `initial_run: "silent"` to import without job alerts, or `initial_run: "digest"` for the implemented initial digest. Each newly enabled source establishes its own baseline. Configure categories, countries, remote-work rules, seasons, co-op inclusion, degrees, graduation years, and optional company restrictions in `filters`; do not infer a candidate's work authorization from the word remote.

Keep ambiguous listings visible in exports for review. The same JSON feed may include old seasons or missing degree/sponsorship evidence. Follow source and employer requirements rather than assuming every feed row is eligible. Descriptions and provider metadata are retained when available; source import timestamps are distinct from employer publication dates.

The old `seen.json` is not the database. `import-seen` copies its IDs into legacy suppression state without pretending successful historic delivery. It is safe to rerun the import, but do not automatically re-import on every deployment. Back up the new database; deleting it starts a fresh discovery history and may cause duplicate alerts.

## Command reference

From the checkout, with the configured environment already loaded by your runtime:

```sh
python -m internship_watch --config config.json run
python -m internship_watch --config config.json daemon
python -m internship_watch --config config.json status
python -m internship_watch --config config.json export --output data/export
python -m internship_watch --config config.json import-seen seen.json
python -m internship_watch --config config.json backup data/backup.sqlite3
python -m internship_watch --config config.json drain
python -m internship_watch --config config.json test-notification
python -m internship_watch --config config.json test-notification --operational
python -m internship_watch --config config.json test-failure-alert
```

`test-failure-alert` sends an explicitly labeled operational message and signals the external heartbeat check as failed. It does not substitute for testing a stopped worker. `drain` retries due outbox messages without collecting sources. Failed delivery remains pending; a server acknowledgment marks delivered. There is an unavoidable at-least-once window if a provider accepts a message but the network/process fails before its receipt is committed; normal job/incident deduplication suppresses repeated completed deliveries, not every possible transport ambiguity.

For systemd inspection commands, run from `/opt/internship-watch` as the service user:

```sh
sudo -u internship-watch .venv/bin/python -m internship_watch --config /etc/internship-watch.json status
sudo -u internship-watch .venv/bin/python -m internship_watch --config /etc/internship-watch.json export --output /var/lib/internship-watch/export
sudo -u internship-watch .venv/bin/python -m internship_watch --config /etc/internship-watch.json backup /var/lib/internship-watch/backup.sqlite3
```

Inspection/export/backup do not need notification secrets. For a one-off notification test that loads the root-protected environment file, use a transient systemd unit:

```sh
sudo systemd-run --wait --pipe --collect --uid=internship-watch --property=WorkingDirectory=/opt/internship-watch --property=EnvironmentFile=/etc/internship-watch.env /opt/internship-watch/.venv/bin/python -m internship_watch --config /etc/internship-watch.json test-notification
```

Replace the final command with `test-failure-alert`, `test-notification --operational`, or `drain` as needed. Do not print the environment file to load it.

For Docker, commands run inside the configured container:

```sh
docker compose exec watcher python -m internship_watch --config /app/config.json status
docker compose exec watcher python -m internship_watch --config /app/config.json export --output /app/data/export
docker compose exec watcher python -m internship_watch --config /app/config.json backup /app/data/backup.sqlite3
docker compose exec watcher python -m internship_watch --config /app/config.json test-notification
docker compose exec watcher python -m internship_watch --config /app/config.json test-failure-alert
docker compose cp watcher:/app/data/export ./export
docker compose cp watcher:/app/data/backup.sqlite3 ./backup.sqlite3
```

Open `export/jobs.html` in a local browser for searchable jobs and status filters. CSV and JSON exports are beside it, with source-health and link-validation evidence. Reports are snapshots; regenerate them after collection. Keep the database private. For a remote host, copy exports over SSH or use an SSH tunnel; no public dashboard needs to be hosted initially.

## Monitoring and reliability

Healthchecks must run independently of the scraper host. Configure a five-minute expected period and a grace window longer than a measured successful cycle (start provisionally at 15 minutes while measuring). A `/start` signal also makes the grace interval the maximum allowed run duration. Increase it only when measurements justify the longer detection delay; otherwise diagnose long-running sources or validation backlog. Attach an email alert independently of the job webhook and test it. [Healthchecks schedule behavior](https://healthchecks.io/docs/configuring_checks/)

The worker attempts the configured polling interval. Direct-source discovery adds up to one polling interval after that provider exposes the job, plus collection/check/retry time. It does not promise jobs appear within five minutes of the employer's original publication. The Simplify feed's curation and daily export can add a day or more; blocked sources have no bounded discovery time. The validation budget can delay first notification of newly discovered candidates. Monitor pending candidates and increase the budget only within source access/rate constraints.

Review `status` and logs for:

- Source failures and unexpected consecutive empty collections. The default threshold is three; one incident remains active until recovery, with a new generation for a later recurrence.
- Pending delivery attempts and `next_attempt`. Repair the webhook/account or wait for a rate limit, then `drain`; do not delete the outbox or mark a failed message delivered.
- Unverified links, unavailable descriptions, expired jobs, and source schema/pagination errors. Fix the source only after reproducing the failure; do not weaken verification to force green results.
- Disk space, database growth, backup freshness, and time between completed cycles. SQLite needs space for the DB, WAL, and backups. Discovery observations store changes rather than repeating every unchanged description each poll, but history still grows.

If storage is unusable, the worker may be unable to persist an incident or delivery retry. Its failure signal and missing successful heartbeat are the independent fallback. The worker leaves alert transitions to the external monitor instead of sending an undeduplicated direct message each failed cycle. Fix disk/permissions and confirm the next committed run recovers the check. A completely unavailable host cannot send its own alert.

## Backup, restart, upgrade, and recovery

Use the `backup` command, which uses SQLite's online backup API. Copy the resulting file off the scraper host; provider snapshots alone are not a substitute for testing a usable database copy. Never copy only a running `.sqlite3` file while ignoring its WAL. Retain several dated backups and monitor backup freshness. No automated off-host backup destination is configured until a host/account is chosen.

To test restore, copy a backup to a separate directory, create a config copy pointing to that restored database, disable production notification settings, and run `status`/`export`. Compare identities, first-seen timestamps, history, and outbox with the original. Do not attach a restored test worker to production secrets or run it against the same notification destination.

For an upgrade: create and copy a consistent backup, stop the worker, deploy the tested code/dependencies, retain the configuration/secrets/database, restart, and inspect scheduled cycles. Docker's `up -d --build` retains the named data volume; a systemd checkout update retains `/var/lib/internship-watch`. Roll back code only when its database schema is compatible; otherwise restore a tested pre-upgrade backup deliberately, acknowledging possible replay of notifications after that backup.

Stop/start commands:

```sh
sudo systemctl stop internship-watch
sudo systemctl start internship-watch
sudo systemctl restart internship-watch
docker compose stop watcher
docker compose start watcher
docker compose restart watcher
```

Use only the commands for your selected runtime. After an unclean stop, the kernel releases the run lock; the next run records the previous running cycle as interrupted and retries pending work. Do not delete a lock file to force overlap. For the external deadman test, stop the worker long enough to receive the alert, then start it and verify the next successful heartbeat recovers the check.

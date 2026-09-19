# Connections, private secrets, and final acceptance

No passwords, API keys, webhook tokens, encryption passwords or heartbeat URLs should be pasted into chat. Enter them in the provider's own settings and the host-side protected files below. This guide prepares a concrete deployment; it does not claim an account, resource, delivery, scheduled task, or cloud upload already exists.

## Remaining setup choices and access

1. Select the existing always-on PC or a measured suitable Linux plan/region from [HOSTING.md](HOSTING.md). For a paid option, approve its monthly total before provisioning. Supply access through an existing supported SSH/hosting connection or configure an SSH public key; no login password is needed in chat.
2. Configure the chosen job and operational Discord webhooks privately. An already working webhook does not need to be recreated. Local Windows uses the repository's private `.env`; Linux uses `/etc/internship-watch.env`. The worker's secret names remain those in `.env.example`.
3. In a Healthchecks.io account, create separate **scraper** and **backup** checks. Attach the desired email destination to both and verify its address. Discord may be an additional integration; email should remain independent of the scraper's Discord transport.
4. Create a private, dedicated B2 bucket and bucket-scoped S3 access key, plus a strong restic repository password saved outside this host. These are needed only when off-host backups are selected. Use cost caps and the dedicated bucket lifecycle described in [HOSTING.md](HOSTING.md).

No additional Google/Meta/HRT credentials are requested. Their direct integrations remain disabled for the documented access/completeness reasons. Their official career pages can be checked manually, and Simplify's public feed supplies partial indirect discovery. Do not bypass robots/access restrictions or treat that indirect coverage as the employer's complete feed. [Current source gaps](SOURCE_AUDIT.md)

Permitted supplemental channels are user-controlled: [Google Careers](https://www.google.com/about/careers/applications/jobs/results/) exposes a Job alerts link and job-type/location filters; configure its native alerts in the user's own account. [HRT Careers](https://www.hudsonrivertrading.com/careers/) links Student Opportunities and a Talent Community. Check these directly or enroll through their own interface if desired; a Talent Community is not a documented complete job feed or freshness guarantee. [Meta's careers site](https://www.metacareers.com/jobs/) remains available for user-led checking, but this review could not verify a native alert feature or documented public API, so neither is claimed. These supplemental channels are not yet imported into this database or deduplicated with scraper notifications.

## External monitor settings

For the scraper check, set a five-minute expected interval and initially a 15-minute grace window, then calibrate grace using measured complete cycles. `/start` also times execution, so the run must complete within the grace window. Put its ping URL only in `HEALTHCHECKS_PING_URL`. For the daily backup check, use a 24-hour interval and two-hour grace; put its distinct URL in `BACKUP_HEALTHCHECKS_PING_URL`. [Check timing](https://healthchecks.io/docs/configuring_checks/)

With these provisional settings, a worker that stops after its last success is overdue after about **20 minutes** (five-minute period plus 15-minute grace), while a missed backup is overdue after about **26 hours**. An in-progress run that never finishes instead reaches its grace timeout from `/start`. Monitor processing and email delivery can add delay; the failure test must record actual observed alert timing.

In each check's integrations settings, enable and test an email integration using the user's chosen address. Confirm the email arrives; merely saving an address is insufficient. The scraper and backup send `/fail` on detected failures, and Healthchecks can alert independently when a host never sends the next ping. Repeated failed pings stay one incident until recovery according to the monitor's configured behavior. [Failure signaling](https://healthchecks.io/docs/signaling_failures/)

Acceptance needs two distinct tests: an explicit labeled failure signal, and actually stopping the worker long enough for its deadline to expire. Confirm both email delivery and recovery after restarting. Separately stop or disable the backup schedule through one expected backup deadline and verify its alert. Do not claim the stopped-worker test passed merely because `/fail` worked.

## Linux systemd backup setup

The scraper service is configured in [DEPLOYMENT.md](DEPLOYMENT.md). Install a supported restic binary from the [official installation instructions](https://restic.readthedocs.io/en/stable/020_installation.html). Restic 0.19.1 was downloaded from its official release, checksum-verified and executed successfully against an encrypted local test repository on Windows; no remote repository was configured. Verify the downloaded release checksums through the official release assets on the selected host, and record `restic version` there.

Copy `deploy/backup.env.example` to `/etc/internship-watch-backup.env` with owner root and mode `0600`. Edit it privately to set the actual S3 repository, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, and backup heartbeat. The service manager reads this protected environment file for the service. Create `/etc/internship-watch-restic-password` with root ownership, group `internship-watch`, mode `0640`; enter only the encryption password. Preserve a separate password-manager copy. Do not store the password inside the backup repository it unlocks.

Initialize the dedicated remote repository once, after bucket selection/spending authorization:

```sh
sudo systemd-run --wait --pipe --collect --uid=internship-watch --property=EnvironmentFile=/etc/internship-watch-backup.env /usr/local/bin/restic init
```

Use the actual installed absolute restic path if different. Never rerun `init` to address an inaccessible existing repository; inspect credentials/endpoint instead. The following installs the prepared backup schedule:

```sh
cd /opt/internship-watch
sudo install -o root -g root -m 0644 deploy/internship-watch-backup.service /etc/systemd/system/internship-watch-backup.service
sudo install -o root -g root -m 0644 deploy/internship-watch-backup.timer /etc/systemd/system/internship-watch-backup.timer
sudo systemctl daemon-reload
sudo systemctl start internship-watch-backup.service
sudo journalctl -u internship-watch-backup.service -n 40 --no-pager
sudo systemctl enable --now internship-watch-backup.timer
sudo systemctl list-timers internship-watch-backup.timer
```

The timer runs daily at 03:15 in the host timezone with up to 15 minutes of random delay and catches a missed run when the machine returns. The service is bounded to 45 minutes; adjust only after measuring larger backups. A successful manual first run must precede scheduled acceptance. Inspect `/var/lib/internship-watch/backups/last-success.json` and the external check.

For a local-only rehearsal with no network/provider secrets:

```sh
sudo -u internship-watch .venv/bin/python deploy/backup.py --config /etc/internship-watch.json --state-dir /var/lib/internship-watch/backups --local-only
```

This creates a consistent local snapshot and verifies a separate restored copy. It intentionally does not signal remote-backup success and is not an off-host backup.

## Docker deployment backup

Keep restic and the backup helper on the Linux host. Add `--compose-dir /opt/internship-watch` to the backup helper command and point `--config` at that checkout's `config.json`. It invokes the running container's existing SQLite backup command, copies only the completed snapshot, then performs host-side encryption/upload/restore checks. It does not read the live database file out of a Docker volume.

The host account invoking Docker needs Docker permission; membership in the Docker group is effectively host-root authority. For this variant, use a dedicated root-owned backup unit and protected files deliberately, or a rootless Docker context that the service account already owns. Do not grant a random interactive user Docker access simply to bypass an error. The default supplied backup unit is for the direct Linux worker and must be deliberately adapted for Docker access/paths. Docker backup execution remains a target-host acceptance item.

## Windows: no stored account password

Copy `.env.example` to the repository's private `.env` only if it does not exist. Add the backup variables from `deploy/backup.env.example` if off-host backup is enabled, using Windows absolute paths for `RESTIC_PASSWORD_FILE` and `RESTIC_CACHE_DIR`. Restrict `.env` and the password file to the chosen task identity, the owner and administrators/SYSTEM. The launcher supports literal `NAME=value` lines and optional matching quotes; it does not execute shell expansions or print values.

In PowerShell, after creating the virtual environment and completing private configuration:

```powershell
$taskRepo = (Get-Location).Path
.\deploy\register-windows-task.ps1 -RepoPath $taskRepo -ConfigPath "$taskRepo\config.json" -EnvFile "$taskRepo\.env" -Preview
# Review the preview; registration does not start collection immediately.
.\deploy\register-windows-task.ps1 -RepoPath $taskRepo -ConfigPath "$taskRepo\config.json" -EnvFile "$taskRepo\.env"
Start-ScheduledTask -TaskName 'Internship Watch'
Get-ScheduledTaskInfo -TaskName 'Internship Watch'
```

This default needs the user logged on. For startup without login, first install Python for all users, rebuild the repository virtual environment from that installation, and prepare access for Local Service. In an elevated PowerShell, grant that account read/execute on the **specific repository** and modify only on its **data directory**, plus read access to the specific environment/password files. Resolve and inspect those paths before applying ACLs; never grant access to an entire user profile. Use `-AtStartup` with the registration command only after that setup. The script refuses to overwrite an existing named task. [Microsoft ScheduledTasks principals](https://learn.microsoft.com/en-us/powershell/module/scheduledtasks/new-scheduledtaskprincipal?view=windowsserver2025-ps)

For backup scheduling, use the same registration command with `-Backup`, and the same principal choice (`-AtStartup` selects Local Service for the daily backup task). Install restic into that principal's machine-wide PATH and initialize the configured repository through the provider's supported private setup. Start the backup task explicitly, inspect its result and `data/service/backups/last-success.json`, then confirm a natural daily run. A stopped or sleeping PC cannot collect jobs; startup tasks do not change its power settings.

After the bucket/password files are configured and remote initialization is authorized, this one-time command loads the private variables without echoing them:

```powershell
.venv\Scripts\python.exe -c "import sys,subprocess; sys.path.insert(0,'deploy'); from windows_runner import load_env; load_env('.env'); subprocess.run(['restic','init'], check=True)"
```

For startup mode, an administrator can grant Local Service access to the explicitly inspected checkout and state directory without storing a password:

```powershell
$taskRepo = (Resolve-Path -LiteralPath '.').Path
$taskData = Join-Path $taskRepo 'data'
New-Item -ItemType Directory -Path $taskData -Force | Out-Null
icacls $taskRepo /grant '*S-1-5-19:(OI)(CI)RX'
icacls $taskData /grant '*S-1-5-19:(OI)(CI)M'
# If the password file is outside this checkout, separately grant Local Service
# read access to that exact file. Keep its remaining ACL restricted.
```

These grants are for the dedicated checkout only; do not replace `$taskRepo` with a user profile or drive root. Inspect existing ACLs on `.env` and the password file and remove broad inherited access through Windows file security settings. The daily task must then pass under Local Service itself, since a successful owner-run command does not prove the service identity can read the files.

Logs rotate under `data/service`; the database remains at the configured persistent path. Stop a task deliberately with `Stop-ScheduledTask`. Test the chosen identity's access after reboot, not only from an interactive administrator terminal.

## Restore and acceptance evidence

Restic's automatic verification restores each uploaded snapshot into isolated staging and checks every SQLite table against the manifest. For an independent recovery exercise, restore a selected snapshot on another machine or new directory, with production notification credentials absent. [Restic restore](https://restic.readthedocs.io/en/stable/050_restore.html)

```sh
restic snapshots --tag internship-watch
restic restore SNAPSHOT_ID --target /var/lib/internship-watch/restore-drill --verify
python deploy/backup.py --verify /var/lib/internship-watch/restore-drill/latest.sqlite3 --manifest /var/lib/internship-watch/restore-drill/latest.manifest.json
```

Use an empty restore directory and the actual restored paths printed by restic. Keep the production database intact. Create a separate config pointing to the restored database, run `status` and `export`, and compare IDs, first-seen, source state, history and outbox. The database, configuration, application revision/package, remote access key and encryption password are all needed for recovery; only the first two are in this backup snapshot.

Before marking the chosen host deployed, retain evidence of its exact revision, full-source scheduled cycles and resource peaks, restart persistence, one received job-channel test, one operational test, a persistent source-failure incident/recovery, stopped-worker email alert/recovery, a completed off-host backup and independently restored database, and failed/missed-backup email alert/recovery. Preserve the receipt IDs and timestamps without saving secret URLs. Items demonstrated only locally or with mocks must remain labeled that way.

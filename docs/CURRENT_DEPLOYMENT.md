# Current deployment and canonical repository

Last actual-host verification: **2026-10-22 at 21:36 UTC (2:36 PM Pacific)**.
This is a dated observation, not a guarantee of future service or source health.

## One canonical project

Keep `andymaoo/internship-watch` (private), default branch
`codex/reliable-internship-discovery`. This contains the Python package, source
registry, SQLite storage, eligibility classifier, link validation, durable
Discord delivery, maintenance supervisor, backup tooling and regression tests
used by the Azure installation. GitHub Actions runs tests here; collection runs
on the VM. A Git push does not deploy the VM.

The older public `andymaoo/internship-job-monitor` is a separate history with
the initial `scrape.py`, title keywords, `seen.json` and a GitHub Actions
collection workflow. It lacks the durable backend described by the README that
had been pasted into it. The latest observed Actions run (`39838534318`) had an
empty notification topic and logged dry-run messages. It was not the source of
the Azure Discord notifications. The old schedule was disabled on October 22;
the API confirmed `disabled_manually`. Deletion subsequently completed in the
signed-in browser session. The repository API returns 404 and the owner's
authenticated repository list contains only `internship-watch` for this project.

Before deletion, the full old Git history was mirrored and exported to a
verified Git bundle outside the active project. The final archived old commit is
`9949aa59ec762e8bfa3601a6a3454a91c84ad447`. The old repository had no issues/PRs,
releases, forks, webhooks or Actions secrets at inspection. Its workflow history
is not part of a Git bundle. Local recovery instructions are below.

## What is running on Azure

| Item | Observed value |
| --- | --- |
| Release directory | `/opt/internship-watch-releases/c1456189b7bc` |
| Git commit | `c1456189b7bccefca7e5a0fc2fe45a4857be6184` |
| Entry point | `python -m internship_watch --config /etc/internship-watch.json daemon` |
| Worker service | `internship-watch.service`: active |
| Supervisor schedule | `internship-watch-maintenance.timer`: active |
| Local backup schedule | `internship-watch-local-backup.timer`: active |
| Configured / enabled sources | 216 / 213 |
| Company watchlist entries | 212 |
| Delivered worker outbox messages | 1,776; no pending messages at acceptance |
| Deployment test delivery | Delivered once at 21:25:00 UTC, receipt `1562939858689990727` |
| Latest accepted full-source runs | 9211 and 9212; 212 passed, only known Old Mission 404 failed |
| Latest supervisor completion | 21:36:26 UTC, successful, 1.919 seconds |

All 22 direct Python files in `internship_watch/` matched the Git commit after
normalizing CRLF to LF. The aggregate SHA-256 was
`65ff174409fbf9d799012d4001450b08de90c437f05241d9f8e3ef57e6db41c8`.
The digest concatenates sorted path, NUL, normalized contents and NUL for each
file. This checks the deployed source content, independently of its directory
name. Private credentials were not displayed or copied.

The initial read-only inspection used Azure Run Command. Owner SSH access was
then restored by rotating the existing rule to the current single-client /32,
retaining TCP 22 and the existing key. It was rotated again when the client's
public IP changed during acceptance. The final cutover completed even though
that change interrupted the SSH response; its saved host result and subsequent
observations independently confirmed success. Configuration and both databases
were preserved. The current code and systemd timeout were deployed through SSH.

## Current health limit

Old Mission's direct board still returns HTTP 404 and is left unchanged per the
owner's instruction. Runs remain labeled degraded because this real source
failure is retained. No other source failed in the staged check or the two
accepted consecutive production runs. Existing count/schema contract warnings,
intermittent-access history, coverage gaps and validation backlog warnings remain
visible; they were not silenced by accepting new baselines or changing job status.

The supervisor's storage-error and stale-agent-review incidents recovered. Its
daily integrity marker is current at 21:19:18 UTC. The local-backup restore proof
from 05:10:25 UTC remains valid and recent, and this update independently created
and restored both databases off the VM before cutover. Automatic encrypted
off-host bucket storage remains unconfigured; manual recovery copies do not
resolve that separate warning. Independent worker and supervisor heartbeat
configuration remains present, and the latest supervisor reported no heartbeat
or delivery failures. A new missed-heartbeat outage test was not repeated for
this code-only update.

## Code and deployment history

The latest backend code, including the Moody's repair and the maintenance
canary-lock fix, is deployed. HubSpot's original Greenhouse board recovered with
62 records at 21:08:26 UTC, so its earlier retirement proposal was reversed before
deployment. All live configuration values, including source settings and user
filters, remain unchanged. The configuration retains 213 enabled sources, 212
company entries, 188 direct routes and 24 incomplete public-feed-only routes.
These are routes and watchlist entries, not guaranteed market coverage.

The release tag `azure-production-2026-10-22-updated` identifies the current
Discord worker code. The earlier `azure-production-2026-10-22` tag records the
pre-update `b3d88cd` release and is retained as historical evidence. Tags are
code snapshots, not separate running services. The default branch contains the
same backend plus current documentation; documentation-only commits do not
require another restart. See `DEPLOYMENT_2026-10-22.md` for acceptance evidence.

Deploy pending code only after current live checks, staged tests, a verified
off-host predeployment snapshot and a reversible cutover preserving both
databases. See `MAINTENANCE.md`. There is no automatic deployment workflow.

## Recovering the retired repository's code

The local archive is outside the maintained checkout:
`C:/Users/o3ti3/Documents/Codex/2026-09-18/c/work/repository-archives/2026-10-22/`.
It contains `internship-job-monitor.git`, `internship-job-monitor.bundle` and
the former public README. The bundle's SHA-256 is
`1b1787a5d18de494b3bcd6ae4bbade423f3f237eb489b3d624897698a79a6bae`.
`git fsck --full` and `git bundle verify` passed before deletion.

To recover code into a new local directory, clone the bundle with `git clone
<absolute-bundle-path> <new-directory>`. This restores Git history and files;
it does not restore deleted GitHub workflow runs or other service metadata.

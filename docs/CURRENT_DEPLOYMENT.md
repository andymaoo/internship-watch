# Current deployment and canonical repository

Last actual-host verification: **2026-11-01 at 23:03 UTC (3:03 PM Pacific)**.
This is a dated observation, not a guarantee of future service or source health.

## One canonical project

Keep `andymaoo/internship-watch`, default branch
`codex/reliable-internship-discovery`. This contains the Python package, source
registry, SQLite storage, eligibility classifier, link validation, durable
Discord delivery, maintenance supervisor, backup tooling and regression tests
used by the Azure installation. GitHub Actions runs tests here; collection runs
on the VM. A Git push does not deploy the VM.

GitHub currently reports this repository as **public** (November 1 API check).
Earlier private-repository descriptions are not reliable evidence of its current
visibility. Visibility was left unchanged pending owner intent. Reports, live
configuration, credentials and SQLite files remain outside tracked Git files.
A current-tree heuristic check found no tracked private credential files or
Discord-webhook/Healthchecks-ping/private-key patterns; this is not a full-history
secret audit.

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
| Release directory | `/opt/internship-watch-releases/31d418e3d958` |
| Backend Git commit | `31d418e3d958423eaf838bc9e7bcbf9d1abe44be` |
| Entry point | `python -m internship_watch --config /etc/internship-watch.json daemon` |
| Worker | Active, enabled after reboot, zero automatic restarts |
| Supervisor / daily local backup | Existing independent timers retained |
| Configured / enabled sources | 216 / 213 |
| Company watchlist entries | 212 |
| Deployment test | Delivered once at 22:57:39 UTC, receipt `1566587055507636375` |
| Normal recovered job alert | Macquarie technology internship delivered 22:57:40 UTC |
| Consecutive full-source polls | 11920 / 11921; 212/213 passed; 356.475 / 302.403 seconds |
| Worker outbox | 2,565 delivered, none pending |
| Supervisor completion | 23:03:35 UTC, successful, 1.712 seconds |

All 23 runtime source files match the deployed Git commit after normalizing
CRLF to LF: 22 package modules plus root `apple_scraper.py`. The sorted path/NUL/
contents/NUL SHA-256 is
`432dbf403c11196143581461cbdcf375fac8740f3dfcdae712c622ecdb486345`.
The package-only digest is
`ca6c4661b4beee89094a92c4259c13e7e0511cf446c8b339761a11484f56aef7`.
Private credentials were not displayed or committed.

The owner-only SSH rule was rotated to the current single-client /32, retaining
TCP 22 and the existing key. Actual-key SSH verified recovery before staging.
A fresh consistent snapshot of both databases was downloaded, restored and
verified off the VM before the atomic release switch. The restart preserved all
5,375 old job identities/first-seen values/baseline flags, 12,628 identity mappings,
6,069 source mappings/first-seen values, and 2,561 worker plus 1,399 maintenance
delivered receipts. New observations and notifications continue in the same DBs.

## Current health limits

The repaired Macquarie counter parser and duty-based technology-program
classification now work on actual source data. Apple's exact-overlap handling
retains conflict/no-progress and raw-count validation. All 353 application and
seven backup tests passed locally, on Azure and in CI. See
[November 1 acceptance](DEPLOYMENT_2026-11-01.md) for actual scheduled results,
latency, receipt, preservation and independent monitoring evidence.

Old Mission's direct board still returns HTTP 404 and remains unchanged per the
owner's instruction. Existing count/schema contracts, intermittent-access history,
incomplete coverage, validation lag/backlog and automatic off-host storage remain
visible. They were not silenced by accepting baselines or changing job statuses.
The worker's configured five-minute interval is a target; slow collections and
validation postpone the next cycle without overlap. Upstream feed delays are
separate and unmeasured.

Daily local restore proof is valid/recent. Manual off-VM recovery copies were
verified on November 1; automatic encrypted bucket backup remains unconfigured.
Both independent worker/supervisor Healthchecks checks were observed UP after
the two accepted production polls. Disruptive outage tests were not repeated
for this adapter/classifier update; previous live evidence and current regression
coverage remain available. This is not a claim of perfect future health.

## Code and deployment history

The tag `azure-production-2026-11-01` identifies the running backend. Older
production tags are retained as historical code snapshots, not separate services.
The default branch contains the same backend plus later documentation-only
commits. A documentation commit does not require restarting the worker.
All production settings, including 213 enabled sources, 212 watchlist entries,
188 direct routes and 24 incomplete public-feed-only entries, remain unchanged.
These route counts do not establish complete employer or market coverage.

Future runtime changes still require staged tests, permitted live checks, a
verified fresh off-VM snapshot and reversible code-only deployment. See
MAINTENANCE.md. There is no automatic Git-push deployment workflow.

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

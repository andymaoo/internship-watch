# Current deployment and canonical repository

Last actual-host verification: **2026-10-22 at 20:56 UTC (1:56 PM Pacific)**.
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
| Release directory | `/opt/internship-watch-releases/b3d88cd` |
| Git commit | `b3d88cd7674eb84853be889db6c8ff24bda317d6` |
| Entry point | `python -m internship_watch --config /etc/internship-watch.json daemon` |
| Worker service | `internship-watch.service`: active |
| Supervisor schedule | `internship-watch-maintenance.timer`: active |
| Local backup schedule | `internship-watch-local-backup.timer`: active |
| Configured / enabled sources | 216 / 213 |
| Company watchlist entries | 212 |
| Delivered worker outbox messages | 1,774; no pending messages at first observation |
| Delivery kinds | 761 jobs, 150 digests, 863 incidents |
| Latest delivered job | October 22 at 19:25:10 UTC (12:25 PM Pacific) |

All 22 direct Python files in `internship_watch/` matched the Git commit after
normalizing CRLF to LF. The aggregate SHA-256 was
`f19d9ca975393384759ae2ffa6594b221359fa7810a63ea3334dd8c2c5f44f52`.
The digest concatenates sorted path, NUL, normalized contents and NUL for each
file. This checks the deployed source content, independently of its directory
name. Private credentials were not displayed or copied.

Azure Run Command provided these read-only checks through the owner's existing
authenticated portal session. SSH remains unavailable from the current client
network. No firewall, runtime, private configuration or database was changed
as part of this repository consolidation.

## Current health limit

Completed runs 9205 and 9206 were degraded; run 9207 was in progress. The current
source failure was `greenhouse-oldmissioncapital`: 335 consecutive failed
attempts, last success October 21 at 13:48:48 UTC, HTTP 404 from its Greenhouse
board. Retain this as source-ticket evidence for the next maintenance repair;
this consolidation does not establish a permitted replacement or repair it.
The notification queue is delivering, but source coverage is incomplete.
Active backup scheduling alone does not verify a recent restore; this session
did not rerun the restore test or independently inspect Healthchecks receipt.
Automatic encrypted off-host backup storage remains unconfigured.

## GitHub code awaiting deployment

The default branch contains the tested October 7 repair commit `efeefe4` and
later documentation. Its Moody's structured-location fallback and HubSpot
direct-board retirement are **not present on the running VM**. The prepared
configuration has 212 enabled sources, 212 company entries, 187 direct routes
and 25 incomplete public-feed-only routes. The live configuration still has
213 enabled sources. These are source routes and watchlist entries, not counts
of distinct employers successfully returning qualifying internships.

The release tag `azure-production-2026-10-22` identifies the verified deployed
code. It is a snapshot of deployment evidence, not a separate running service.
Use that tag to inspect the actual Discord worker code; use the default branch
for tested changes and current documentation. Do not replace the default branch
with older deployed code or discard pending fixes just to make revisions equal.

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

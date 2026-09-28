# Maintenance safeguards: actual-host acceptance

Runtime release: `1d36c8261773ca31d59dcbaf656a9b2b2f339bc2`, on the existing Azure
VM through `/opt/internship-watch`. The user's US/junior/role/eligibility filters,
all 213 enabled sources, five-minute polling target, persistent SQLite, private
HTML/CSV and Discord settings were preserved. No new paid service was added.

The final code passed **326 application tests and seven backup tests** locally,
on Azure, and in [GitHub CI](https://github.com/andymaoo/internship-watch/actions/runs/35490364244).
Tests include persistent failure/recovery, duplicate suppression, three-poll
anomalies, missing/corrupt-storage reporting, daily-review expiry, intermittent
failure retention, worker-wide alert grouping, feed migration/staleness and
restored maintenance data. Unit and timer definitions also passed systemd's
configuration verifier.

## Live sources and storage

All 213 sources ran through collection and the new normalized contracts on
Azure. The first pass took 233.214 seconds: 212 passed, and Group One failed an
access/robots-policy check. An unchanged, permitted retry returned six records
in 16.460 seconds and passed. No access restrictions were disabled. Final
maintenance-only changes reused this source evidence because the adapters,
contracts and production source configuration were byte-identical, then the
scheduled worker continued checking every enabled source.

Initial activation preserved all 2,967 job identities, first-seen times and
baseline flags, plus all nine existing outbox entries/receipts. The final
activation preserved the same jobs and all ten outbox entries, including the
new weekly canary. These values were compared before and after restart.

Both job and maintenance databases were copied using SQLite's consistent backup
API, integrity checked, transferred off-host over verified SSH, and hash checked
before the final deployment. The compressed two-database snapshot was 43,157,626
bytes; its SHA-256 was
`e989c816b43e0efb04867c4f10319cf4ea5f4e8b962d5db892929c488fafceb5`.
These are manual deployment snapshots, not evidence of automatic off-host backup.

## Notifications and independent monitoring

- Controlled maintenance failure: an injected pre-transport exception left one
  pending record. After reopening the SQLite store and making the test item due,
  real Discord delivery returned receipt `1551092130578169877` at 04:46:21 UTC.
  A second drain delivered zero duplicates. Recovery returned receipt
  `1551092131496460430` at 04:46:22; another drain again delivered zero duplicates.
  This used an isolated test DB and did not change the production webhook or job
  records. Normal backoff and rate-limit behavior also have regression coverage.
- The weekly canary went through the actual production worker outbox. Created
  04:52:00 UTC, it was acknowledged at 04:56:03 with receipt
  `1551094571608313898`, on its first delivery attempt. Its stable weekly key
  remained delivered across supervisor executions and the final worker restart.
- A separate Healthchecks maintenance monitor received an Azure ping at
  04:45:28. With further pings withheld and a temporary 1-minute period plus
  1-minute grace, it transitioned DOWN and recorded an email send at 04:47.
  The Azure recovery ping at 04:49:40 restored UP. Production settings were
  restored and verified: **15-minute period, 20-minute grace**, existing Berkeley
  email destination enabled. Actual supervisor start/success pings subsequently
  appeared in Healthchecks. The user confirmed receiving both Discord and email.
  The existing scraper monitor was left operational during this test.

## Scheduled operation and resource measurements

The new `internship-watch-maintenance.timer` and
`internship-watch-local-backup.timer` are enabled for startup after reboot.
The existing worker service remains active/enabled. Maintenance runs every
15 minutes with at most 30 seconds of jitter; daily local backup runs at
04:45 UTC with at most 15 minutes of jitter. Kernel locks and systemd single-unit
execution prevent duplicate maintenance/backup instances.

The initial supervisor run took 6.356 seconds including the real public-feed
metadata audit. The first timer-triggered run started **05:00:19 UTC** and took
**0.732 seconds**, read telemetry for all 213 sources, confirmed the production
canary receipt, and sent no duplicate alerts. A measured final-code invocation
took **1.368 seconds** with peak RSS **37,300 KiB** (about 36.4 MiB). The supervisor
unit is capped at 180 MiB and a four-minute lifetime.

The daily feed audit verified `SimplifyJobs/Summer2027-Internships`, branch `dev`,
path `.github/scripts/listings.json`, and a feed-path commit at 04:31:34 UTC.
This audit does not establish Simplify website publication time or whole-site
coverage. The regular scraper still polls its configured feed every cycle.

The initial local backup completed at 04:51:58 UTC. A second actual service run
completed at **05:09:58 UTC**, restoring and verifying the 246,218,752-byte main
database and the populated maintenance database against saved table hashes.
It retained 2,967 jobs, ten worker outbox records and telemetry for 213 sources.
All 213 source baselines were established from at least three successful polls.
Local verification does not satisfy the off-host-backup check.

Completed scheduled worker cycles, all on 2026-09-20 UTC:

| Run | Runtime | Start | Finish | Seconds | Sources passed | Checks due afterward |
| --- | --- | --- | --- | ---: | ---: | ---: |
| 243 | First maintenance release | 04:50:58 | 04:56:12 | 314.311 | 213/213 | 269 |
| 244 | First maintenance release | 04:56:14 | 05:01:30 | 315.916 | 213/213 | 271 |
| 245 | Final `1d36c8261773` | 05:01:43 | 05:06:38 | 294.835 | 213/213 | 265 |
| 246 | Final `1d36c8261773` | 05:06:43 | 05:11:47 | 303.794 | 213/213 | 277 |

All four completed successfully with no source failures and no pending
notifications. The due-check backlog fluctuated rather than growing steadily;
the preceding run 242 ended with 289 due. This short acceptance window does not
establish long-term queue stability. Overdue checks include recurring access
problems, and 766 qualifying postings remained unverified; these were not
silently promoted to open or classified as closed. Slow cycles postponed the
next poll without overlap. After both final-release cycles, all 2,967 prior job
IDs/first-seen/baseline values and all ten outbox status/receipt values still
matched the pre-restart snapshot.

The database's four historical non-baseline notification decisions still showed
a 64-second median and 66-second maximum from first discovery to decision.
There were no new decision samples in this acceptance window, so this is not a
new measurement of discovery speed or employer publication delay. The weekly
canary measured queue delivery separately, taking 243 seconds in its observed
cycle. Source/export delays precede local discovery and remain outside those
metrics.

The final supervisor check at **05:12:45 UTC** took 0.458 seconds, found zero
currently due qualifying checks, retained all 213 baselines, and sent zero
duplicate alerts. The worker and both added timers were active and enabled.
Only the known off-host-backup warning and informational company-coverage item
remained open. An actual completed review was recorded for the daily agent's
missed-review monitor.

## Remaining limits and owner setup

Automatic encrypted off-host backups still need the private storage connection
in `/etc/internship-watch-backup.env`: `RESTIC_REPOSITORY`,
`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`. The prepared password-file and
backup-heartbeat settings remain separate. Until a real upload and restore
passes, this stays one open warning with a weekly reminder. No secret should be
sent in chat or committed to the repository.

Known company coverage gaps stay visible. Source health is not market
completeness, and valid-looking partial data can escape heuristics. A legitimate
seasonal change can require accepting a reviewed new baseline. No new qualifying
job is needed for the weekly delivery canary; that test does not measure employer
publication-to-notification delay.

The daily 09:00 local Codex follow-up can investigate and repair reproducible code
defects under the documented test/deployment policy. It requires the Windows PC
and app to be available with working access and sufficient usage. Azure checks,
alerts and local backups continue independently. No completed agent review for
72 hours produces a separate warning. Unknown permission/access/budget decisions
remain for the owner. There is no guarantee that every future integration change
can be repaired automatically.

See [operating, updating and stopping instructions](MAINTENANCE.md) and
[the review queue](MAINTENANCE_REVIEW.md). The existing private live report now
links to `maintenance.html`; a downloaded report remains a static snapshot.

## September 28 repair deployment

Release `ce0d1ccc882bd5fe108d9e8081922f3a6b53e8a5` was deployed at
20:59:10 UTC after the owner approved replacing the stale SSH /32 with the
current single-client /32. Before cutover, consistent copies of both production
databases were downloaded off the VM and independently verified by SHA-256,
SQLite integrity check and complete per-table manifests. These are manual
predeployment recovery copies; the automatic encrypted off-host backup remains
unconfigured and its warning remains valid.

The combined release passed 339 application tests and seven backup tests
locally and on Azure, passed GitHub CI, and collected all 213 enabled sources in
250.912 seconds with no failures during staging. The actual-host cutover
preserved 3,410 existing job identities, first-seen/baseline values, 437 worker
delivery receipts, 146 supervisor receipts, every source/filter setting and the
five-minute polling interval. It changed only `validation_workers` from the
implicit default of one to two and requeued 13 affected unverified records for
real checks without assigning open or closed status. The prior release remains
available for a code-only rollback without replacing newer SQLite data.

Post-cutover runs 2630, 2632 and 2633 completed with all 213 sources; runs 2632
and 2633 were consecutive clean polls. Run 2631 had one transient Veeva
pagination inconsistency and the following run recovered. The
previously persistent Fidelity failure recovered, and Fidelity, State Street,
Broadcom, Atlassian, AMD and Société Générale each had a successful production
collection with zero current failures. Validation throughput rose from 25–28
checks in the first cycles to 55 in run 2632 and 64 in run 2633; the due count
fell from 1,244 to 1,162. This is early capacity evidence, not proof the historical backlog is
fully drained. The worker remained active with zero service restarts and no
pending notification deliveries.

State Street's corrected US-scoped result was stable at 252 records across the
staged check and three production polls. Its reviewed baseline was accepted with
an audit reason because the prior 744-record baseline represented the global
board. S&P Global's separate count-drop warning remains open pending review; no
unexplained decline was accepted. Healthchecks showed recent worker and
maintenance pings with email enabled. A September 28 review marker records the
actual host, source, CI, delivery and restore checks.

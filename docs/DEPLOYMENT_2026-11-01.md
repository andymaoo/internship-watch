# November 1 deployment acceptance

Backend commit: `31d418e3d958423eaf838bc9e7bcbf9d1abe44be` in the personal
`andymaoo/internship-watch` repository. Activated at **22:51:55 UTC** through
`/opt/internship-watch` on the existing Azure VM. Previous release
`/opt/internship-watch-releases/c1456189b7bc` remains available for code-only
rollback. Configuration, secrets, source restrictions and SQLite histories were
preserved. A Git push alone does not deploy this service.

## Repairs and staging

- Macquarie's dedicated result counter changed from a range to a single-page
  total. Accept the observed dedicated counter, while retaining strict total,
  pagination, identity, host and challenge checks.
- A generic Technology Summer Internship Program was incorrectly excluded
  despite explicit engineering-team/software duties in its responsibilities.
  The narrow classifier fallback requires those duties, not qualifications or
  a technology keyword alone. Ambiguous placements and hardware remain explicit.
- Apple's populated last page repeated an identical requisition. Deduplicate
  exact same-ID payloads while rejecting conflicting records, non-progressing
  pages and incomplete/changing declared totals. The observed terminal zero
  counter is accepted only after the previous raw-row total was satisfied.

See [reproduction and regressions](REPAIR_2026-10-30.md). All **353 application
and seven backup tests** passed locally and on the actual Azure staging release.
The host application suite took 32.877 seconds; backup tests took 0.603 seconds.
[GitHub CI for the deployed commit](https://github.com/andymaoo/internship-watch/actions/runs/41358943582)
also passed. Dependencies and all production source/filter settings are unchanged.

Fresh full staging exercised all 213 enabled sources and classified 37,315
records in 335.645 seconds while backup activity shared the VM. For the final
Apple-only change, the 212 unchanged-source results were reused only after
checking package/configuration identity and evidence age below two hours;
Apple was collected again on Azure and returned 63 unique records in 8.153
seconds. One bounded permitted PIMCO retry recovered its transient count error.
The remaining failure was the owner-ignored Old Mission 404. No access policy,
validator or anomaly baseline was disabled to make these results pass.

## Consistent off-VM recovery copies

Before activation, both live databases were copied with SQLite's backup API
from an explicit read transaction, integrity checked, compressed, transferred
with strict SSH host-key checking, decompressed and independently checked on the
Windows computer. Compressed and raw SHA-256, full integrity checks and every
table count matched. Neither database was restored over production.

| Database | Raw bytes | Compressed bytes | Raw SHA-256 |
| --- | ---: | ---: | --- |
| jobs.sqlite3 | 3,911,499,776 | 632,077,043 | `366598ff49badce9341870e78867e93b1b0fba0f8d22b3c9cf1a9293e472b2f6` |
| maintenance.sqlite3 | 7,909,376 | 898,534 | `864479f7a030faf2bb68b2771ca76ee33f9d8e93d0b7239e5ee8b0507787ac2f` |

The private local recovery directory is
`C:/Users/o3ti3/Documents/Codex/2026-09-18/c/work/job-scraper/work/private/oct30-a93517e1a659/`.
Its historical prefix does not indicate snapshot age: these copies were created
and verified on November 1. These manual off-VM copies do not resolve the known
missing automatic encrypted off-host bucket connection. The independent daily
local-backup proof from 05:07:40 UTC remains valid and recent.

The restart preserved all **5,375 existing job IDs, first-seen timestamps and
baseline flags; 12,628 identities; 6,069 source-record identities/first-seen
values; 2,561 delivered worker receipts; and 1,399 delivered maintenance
receipts**. Acceptance assertions compare each existing record, not just counts.
All user filters, the 300-second target and 213 enabled sources were preserved.

## Production acceptance

The first scheduled run, 11920, completed at 22:57:52 UTC in 356.475 seconds,
with 212/213 successful sources. Only the known Old Mission 404 remained.
Apple returned 64 unique jobs; Macquarie returned eight. Both failure counters
reset to zero from actual collection success. The next scheduled run started
at 22:57:54, after completion; no overlapping worker was launched.

Two consecutive scheduled polls are accepted:

| Run | Start UTC | Finish UTC | Total seconds | Successful sources | Due link checks |
| --- | --- | --- | ---: | ---: | ---: |
| 11920 | 22:51:55 | 22:57:52 | 356.475 | 212/213 | 1,950 |
| 11921 | 22:57:54 | 23:02:55 | 302.403 | 212/213 | 1,947 |

Both retain degraded status solely for Old Mission's real 404. The next poll
started at 23:02:58 after the prior completion. The small queue decrease does
not establish long-term stability: 379 qualifying rechecks were due at 23:03,
oldest 21:31:50, while zero included jobs lacked their first check. Existing lag
and backlog-growth incidents remain open with sustained-recovery requirements.
The all-status oldest-due metric includes old unresolved records; it must not
be represented as the age of every new qualifying job.

The supervisor completed at 23:03:35 UTC in 1.712 seconds, with no storage or
delivery failure and no pending supervisor deliveries. The agent-review marker
records the actual acceptance at 23:03:33. It retains 26 open warning/information
tickets (contracts, intermittent history, coverage, queue and off-host setup),
rather than declaring the installation issue-free. Worker and maintenance
Healthchecks were independently observed UP after the second completion, with
recent real pings; the off-host backup check still has never received a ping.
Worker, supervisor timer and local-backup timer remain active/enabled; the
worker had zero automatic restarts. No reboot was induced for this code-only
update. Earlier reboot/startup acceptance and current enabled-state evidence
remain distinct.

The ordinary pipeline discovered Macquarie requisition 24477 at 22:53:13,
classified it as software engineering, and verified its employer posting at
22:56:38. Application access remains unverified. Its notification decision was
saved at 22:57:35, **262 seconds after discovery**, and Discord acknowledged its
single normal job alert at 22:57:40, receipt `1566587057604657413`.
Its employer posting date is September 29, not the November 1 discovery time.
This example establishes a real source-to-classification-to-validation-to-job-
notification path; it does not establish a worst-case notification delay.

Discord also acknowledged one labeled deployment check at 22:57:39, on its first
attempt, receipt `1566587055507636375`, and ordinary Apple/Macquarie recovery
messages. The worker queue was empty afterward. Existing outbox/deduplication
keys and prior receipts survived restart. Disruptive failed-delivery and stopped-
worker tests were not repeated for these adapter/classifier-only changes;
their historical actual-host evidence remains in MAINTENANCE_ACCEPTANCE.md,
and the current full regression suite covers persistent retries and recovery.

All 23 deployed runtime source files match Git independently of release name:
22 package modules plus root `apple_scraper.py`. LF-normalized, sorted path/NUL/
contents/NUL aggregate SHA-256 is
`432dbf403c11196143581461cbdcf375fac8740f3dfcdae712c622ecdb486345`.
The package-only aggregate is
`ca6c4661b4beee89094a92c4259c13e7e0511cf446c8b339761a11484f56aef7`.
Root Apple's file SHA-256 is
`5d1792a7627fa08e3d7d1f1b3b72d67d9806afe8ce5aab61c09bbbc3bf6bf863`.

## Operating limits and controls

This is a five-minute target, not a publication-to-notification guarantee.
Slow collections and queued link checks postpone the next cycle without overlap.
The initial deployment poll took about six minutes; the next took 302 seconds. Employer-to-Simplify feed
curation/export delay is separate and unmeasured. The daily public-feed audit
still verifies Summer2027-Internships, dev, .github/scripts/listings.json; at
22:30:30 it observed commit `319a6b5750ad3e73c1593034b7091759a69bc166`
with feed-path commit time 21:32:29 UTC. This is not whole-site Simplify coverage.

Existing count/schema anomalies, incomplete company coverage, validation lag
and automatic off-host backup setup remain separate repair tickets. Historical
intermittent Apple/Macquarie evidence is retained after source recovery. No
claim of perfect health, complete coverage or stable validation capacity is made.
The partial weekly official-route review and next cursor are recorded in
MAINTENANCE_REVIEW.md; dependency update PRs remain unmerged.

Private reports remain under `/var/lib/internship-watch/export/`: jobs.html,
jobs.csv, jobs.json, link-validation.json, sources.json, maintenance.html and
coverage.html. Copy the export directory through the existing SSH connection or
use the existing private tunnel; an old downloaded file does not refresh from
Azure. Nothing was made public.

Update by staging/tests/live checks, a verified fresh off-VM snapshot, then an
atomic release-symlink switch between polls. Keep the previous release and both
current databases. Roll back code only; do not overwrite newer data from a
snapshot during routine rollback. To stop collection immediately use
`sudo systemctl stop internship-watch`; to keep it stopped across reboot use
`sudo systemctl disable --now internship-watch`. Supervisor/local-backup timers
are independent. Pause the corresponding Healthchecks check for intentional
stops. Full commands and secret locations are in MAINTENANCE.md and OPERATIONS.md.

## Repository visibility review

The authenticated GitHub API currently reports `andymaoo/internship-watch` as
public. Its owner/default branch are correct; this is a visibility discrepancy
with earlier documentation, not evidence that another backend is running.
Visibility was not changed because the owner's current publication intent is
uncertain. Current tracked files contain no private credential files and no
matches for the checked Discord-webhook, Healthchecks-ping or private-key
patterns. That heuristic current-tree scan is not a full-history secret audit
or proof that no secret was ever exposed. Review ticket: `repository-visibility`;
owner decision required before changing visibility. Private report snapshots
and backup copies remain outside tracked Git files.

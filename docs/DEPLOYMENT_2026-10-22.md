# October 22 Azure update acceptance

Backend `c1456189b7bccefca7e5a0fc2fe45a4857be6184` is deployed at
`/opt/internship-watch-releases/c1456189b7bc`. Acceptance completed at 21:36 UTC
(2:36 PM Pacific). Later documentation-only commits do not change the backend.

## Changes and verification

- Deployed the tested Moody's location fallback, retaining exact identity and
  explicit employer-location evidence requirements.
- Preserved HubSpot's recovered Greenhouse board: actual Azure collection
  returned 62 records. Its earlier retirement proposal was never deployed.
- Fixed recurring canary observation unnecessarily issuing `INSERT OR IGNORE`
  even when the weekly test message already existed. A real concurrent SQLite
  regression reproduced `database is locked`. The repaired path reads the
  existing receipt first; new canaries retain durable deduplicated insertion.
- Extended the supervisor timeout from four to ten minutes within its unchanged
  fifteen-minute schedule. Prior service attempts timed out while the daily
  integrity marker remained overdue on the approximately 3 GB jobs database.
  The daily check subsequently completed at 21:19:18 UTC.

No production source/filter configuration changed. No baseline was accepted to
hide warnings and no unverified job was declared open or closed. Old Mission's
known 404 was retained at the owner's request.

The final revision passed 349 application regressions and seven backup tests
locally and on Azure; actual-host runtimes were 35.335 and 0.635 seconds.
Compilation and systemd unit verification passed.
[CI for the deployed code](https://github.com/andymaoo/internship-watch/actions/runs/39856029512)
passed before cutover.

The actual-host staged collection checked all 213 sources in 209.661 seconds.
Only Old Mission failed; 212 passed. This result was reused for the final
supervisor-only repair after verifying unchanged adapters and source settings.
Staging held the production collection lock, preventing overlapping scrapes.

## Verified off-VM recovery copies

Before cutover, online backups of both databases were checked, compressed,
downloaded and restored on this computer. Complete original/restored file
SHA-256 values, SQLite integrity and every table's row count matched.

| Database | Original bytes | Compressed bytes |
| --- | ---: | ---: |
| Jobs | 3,017,859,072 | 492,141,107 |
| Maintenance | 6,758,400 | 735,665 |

The jobs snapshot contained 4,720 jobs, 11,243 identities, 5,355 source records,
422,678 link checks and 1,774 outbox records. Private manifests/restores remain
under ignored `work/private/` and `work/maintenance/oct22-deployment/` paths.
These are manual off-VM copies, not configured automatic bucket backups.

## Cutover and persistence

The first update switched `b3d88cd` to `1bef385`. Acceptance then reproduced
the canary write conflict; the final reviewed repair switched to `c145618`
between runs, after run 9210. Existing dependencies were retained. Both older
releases remain available for a code-only rollback.

A client public-IP change interrupted the final SSH response. Its saved host
cutover result and later source fingerprint, service, database and completed-run
observations independently confirmed success. The existing owner SSH rule was
rotated to the current single-client /32, retaining TCP 22 and the existing key.

After restart, assertions verified preservation of all existing:

- 4,720 job IDs, first-seen timestamps and baseline flags;
- 11,243 identity-to-job mappings;
- 5,355 source-record identities, job mappings and first-seen values;
- 1,775 delivered worker receipts and 1,048 supervisor receipts;
- user filters, source settings and the 300-second polling target.

The extra worker receipt relative to the original backup is the labeled first
deployment test. No receipt was reset. All 22 deployed package files matched the
Git revision after normalizing line endings, aggregate SHA-256
`65ff174409fbf9d799012d4001450b08de90c437f05241d9f8e3ef57e6db41c8`.

## Actual scheduled-run and delivery evidence

| Run | Start UTC | Finish UTC | Seconds | Source result |
| --- | --- | --- | ---: | --- |
| 9211 | 21:20:08 | 21:25:11 | 303.347 | 212 passed; known Old Mission 404 |
| 9212 | 21:25:14 | 21:30:32 | 318.693 | 212 passed; known Old Mission 404 |

Both consecutive polls remain labeled degraded because the real Old Mission
failure was retained. They had no pending worker deliveries. Due link checks
fell from 1,322 to 1,312 across this short window; this does not establish
long-term queue stability. Many jobs remain unverified. A later backlog-growth
warning remains visible rather than being suppressed.

The final deployment message traversed the persistent outbox. Discord accepted
it on its first attempt at 21:25:00 UTC, receipt `1562939858689990727`.
This establishes provider delivery; user receipt was not separately requested.
Unchanged failed-delivery and stopped-worker alert paths retain prior live-test
evidence and passed regressions; those outage tests were not repeated here.

The worker is active, enabled after reboot and has zero automatic restarts in
the observed window. The supervisor completed at 21:30:34 UTC in 1.272 seconds,
and again at 21:36:26 UTC in 1.919 seconds. Its storage-error and stale-review
incidents resolved. The latest report had no storage error or failed delivery;
the daily integrity marker is current. A completed agent review was recorded.
Both independent heartbeat configurations remain present; monitoring was not
paused. No new stopped-worker Healthchecks outage test was performed.

## Remaining limits and operation

Existing count/schema contract warnings, intermittent-access history, coverage
gaps and backlog warnings remain unresolved. Passing collection contracts does
not prove complete employer coverage. Automatic encrypted off-host bucket
storage remains unconfigured. Old Mission is the owner's accepted direct-source
exception.

The target interval remains 300 seconds; observed cycles took 303–319 seconds,
so slow cycles postpone the next poll without overlap. Feed publication/curation
delays happen before local discovery and remain outside that interval.

Reports still update under `/var/lib/internship-watch/export/`, using the existing
private tunnel/report access. Downloaded Windows HTML files remain snapshots.

Use `MAINTENANCE.md` for future staged updates and coordinated code-only rollback.
Rollback must preserve newer SQLite data. Stop collection with
`sudo systemctl stop internship-watch`; keep it stopped after reboot with
`sudo systemctl disable --now internship-watch`. Maintenance and backup timers
are separate. Reflect intentional stops in independent monitoring to avoid
expected missing-worker alerts.

# Maintenance reviews

The daily Codex follow-up is active in the original task at 09:00 local time.
It should investigate stored incidents and apply tested reversible repairs under
the policy in `MAINTENANCE.md`. Azure monitoring is independent of that follow-up.

## Daily follow-up — 2026-09-23, 22:23–22:25 UTC observation

Read-only production review used the existing authenticated Azure Run Command
interface because normal SSH remained unavailable. The pending single-IP
allowlist change was not performed. Runtime is still `1d36c8261773`; prepared
repair `2430be8` has not been deployed. No filters, records, notification history,
source configuration, access rules or production code were changed.

- Worker was active with zero automatic restarts and about 527 MiB current
  service memory. Runs 1274–1276 completed in 334.276, 308.893 and 319.341 seconds,
  all degraded, with 211, 212 and 210 of 213 sources succeeding respectively.
  Fidelity had 760 consecutive failures with the already-reproduced
  posting/site alias defect. The prepared repair remains the appropriate next
  step after approved maintenance access, fresh verified off-host snapshots and
  actual-host staging. State Street had one missing/repeated identity failure
  after a successful collection at 22:14:48; this single observation does not
  establish a new code defect or authorize weakening identity validation.
- The worker outbox contained 190 delivered messages and zero pending, with a
  receipt at 22:22:17. The supervisor outbox contained 42 delivered and zero
  pending, with its latest receipt at 21:15:30. The weekly worker canary was
  acknowledged on September 21 at 00:02:29, on its first attempt. These are
  provider acknowledgements, not a new inbox-receipt test with the owner.
- The live Simplify source already uses `SimplifyJobs/Summer2027-Internships`,
  branch `dev`, path `.github/scripts/listings.json`. Its successful 22:22:40
  poll returned 4,513 source records with zero source failures. The daily metadata
  audit at 05:31:05 confirmed the canonical repository and feed commit
  `e4819a76003d9abeb8cb5782ae9fed09de669ab6`, dated 05:01:33 UTC. No duplicate source
  was added. This is public-repository coverage, not Simplify website coverage
  or a guarantee of five-minute upstream publication.
- Due validation candidates rose from 1,080 to 1,087 to 1,102 over the observed
  three cycles. The oldest candidate was about four days overdue, including
  lower-priority records; this must not be presented as the age of a newly
  qualifying job. The history contained 175 notification decisions with a
  296-second median and 48,508-second maximum from discovery. These historical
  values do not establish current worst-case latency or include upstream delays.
  A separate 22:25:05 query found 262 qualifying rechecks due, oldest at 20:31:10
  (about 114 minutes overdue), and zero newly included, unverified jobs without
  any prior link check. Production still uses one validation worker; the prepared
  two-worker capacity change is not live.
- The supervisor report was fresh at 22:15:40. Its active warnings were Fidelity,
  the known missing off-host backup connection, and a stale agent review.
  Local backup restore proof was current at 04:52:15 on September 23, including
  the 426,864,640-byte jobs database and `maintenance.sqlite3`; saved row counts
  included 3,184 jobs, 164 worker outbox rows and 213 source states. Automatic
  off-host restore evidence remained absent; no repeated credential request was
  issued.
- GitHub's latest Tests workflow on `2430be8`, run `35645525695` from September 21
  at 19:33:12 UTC, completed successfully. The two Actions major-upgrade proposals
  remain open and unmerged. No code changed, so the existing full regression
  result was not needlessly repeated.

After these checks, the actual daily review marker was recorded at 22:26:14 UTC
as the `internship-watch` service account. The saved reason explicitly retains
the undeployed repair, access requirement, backlog and off-host setup limitations.
The next regular supervisor execution can evaluate that refreshed marker; this
review did not force or claim a delivered recovery alert.

The weekly cursor remains the 24 coverage gaps and permitted official routes,
season continuity beyond the configured feed, and the two dependency proposals.
This was a daily production review, not a fresh audit of every employer. The
deferred deployment and off-host backup connection remain separate outstanding
items; none of these read-only observations proves the pending repair is live.

## Incident repair preparation — 2026-09-21 UTC

The owner requested repair of the reproduced Fidelity and State Street failures
and validation issues. See `REPAIR_2026-09-21.md` for the precise changes, live
source/link evidence and 335 passing local application regressions plus seven
backup tests. Oracle passed unchanged. Repairs also address repeated structural
validation retries, bounded validation concurrency and queue-alert flapping.
The user's citizenship, sponsorship, geography and role filters are preserved.

At preparation time SSH was again blocked by a changed client IP. The existing
Azure browser session provided read-only production inspection; the single-IP
allowlist replacement was requested and remains pending confirmation. No server
access rule or production release was changed. Deployment, fresh verified
off-host snapshots and consecutive actual-host acceptance runs remain required.
The previous weekly coverage/dependency review cursor below remains unchanged.

## Daily follow-up — 2026-09-20, 19:36 UTC observation

Runtime remains `1d36c8261773`; no reproducible application defect was found and
no runtime code, filters, source restrictions, job statuses or delivery records
were changed.

- Normal SSH failed twice before authentication. Azure showed the same public
  VM address and a running VM. Its `default-allow-ssh` rule still permits TCP 22
  from one `/32` address; the current client address no longer matches it.
  Fresh scraper and supervisor heartbeats were visible in the signed-in
  Healthchecks account. Read-only health queries therefore used the existing
  authenticated Azure Run Command interface. Initial diagnostics left the
  firewall unchanged.
- Grouped a new `management:ssh-client-ip` maintenance ticket separately from
  worker incidents. The user approved replacing the single-IP entry with the
  current client IP. The existing rule was updated, retaining one `/32`, TCP 22,
  priority 800 and key authentication. Existing-key SSH with strict host-key
  verification succeeded at 19:45:44 UTC. The access ticket was resolved at
  19:46:33 UTC; no new credential or broader network range was introduced.
  Future client-IP changes may require a separately approved replacement. The
  Azure management fallback remains available while its account session is valid.
- Since run 247, the observed window contained 161 successful, eight degraded,
  two interrupted and one running cycle. Latest completed runs 416 and 417
  passed all 213 sources in 301.967 and 307.430 seconds. No source was currently
  failing, and the worker outbox held ten delivered messages and zero pending.
  The weekly canary receipt remained intact; no additional test was sent.
- Recovered source issues included changing pagination totals at AMD (twice)
  and Nvidia, one unverifiable Barclays robots-policy response, one S&P Global
  response missing title/path, and earlier Wellington/Unity failures. Later
  normal scheduled collections succeeded. These observations do not reproduce
  a code defect; strict completeness/access checks remain enabled.
- The due-validation count rose from 277 at run 246 to 687 at run 417, with
  696 at run 416. It is a real accumulated recheck queue, not proof of a new-job
  notification delay. The separate due-row inspection was largely ambiguous
  or excluded records. The oldest due included record was scheduled for
  18:38:55 UTC, within the configured two-hour alert window when inspected.
  Continue tracking lower-priority queue age and qualifying lag; this review
  does not establish long-term capacity or claim all checks are resolved.
- Runs 263 and 264 were interrupted around 06:37 UTC. The journal records
  explicit systemd stop/start events; the same host boot continued, automatic
  crash restart count was zero, and no kernel OOM events were found. The stop
  initiator was not determined. Collection recovered and remained current.
  Observed service memory was about 502 MiB, peak 627 MiB; compare subsequent
  observations before diagnosing a leak or proposing a larger paid host.
- The local backup still had verified restores of both databases at 05:09:58
  UTC, within its 36-hour freshness threshold. Off-host credentials remain the
  known outstanding setup item. The deployed-code and latest committed-docs CI
  passed; the later pip dependency scan also succeeded. The two Actions major
  upgrade proposals remain unmerged pending their separate review.

The initial review marker and management-access ticket were saved on Azure at
19:42:22 UTC. After the approved access repair, the review marker and supervisor
were refreshed at 19:46:33 UTC with no failed or duplicate deliveries. Runs 418
and 419 completed at 19:40:18 and 19:45:28 UTC, both with 213/213 sources passing
and no pending notifications. Runtime stayed `1d36c8261773` throughout; there
was no worker restart or application deployment for this network-rule repair.

This daily review did not perform a new careers-site/season audit or rerun a
full regression suite: there was no code change. The next weekly
cursor remains the 24 coverage gaps, official permitted routes, Simplify season
continuity and the two Actions upgrade proposals. On the next daily review,
check management connectivity, lower-priority recheck age, memory trend
and any recurrence of the recovered source errors.

## Initial deployment review — 2026-09-20, 04:45–05:13 UTC

Reviewed during deployment:

- All 213 enabled sources through actual Azure collection and the new normalized
  contracts. First pass: 212 successes and one Group One robots-policy/access
  failure; its unchanged permitted retry returned six records and passed.
- 326 application regressions and seven backup tests locally and on Azure.
- Failure persistence, restart retry and duplicate suppression with real Discord
  failure/recovery receipts; a weekly canary traversed the production outbox.
- A separate maintenance Healthchecks check: missing heartbeat caused DOWN and
  an email send; successful pings restored UP. Normal schedule is 15 minutes with
  20 minutes of grace. The user confirmed receiving both the Discord messages
  and the Healthchecks email for this test.
- Simplify's canonical public repository, configured `dev` branch and listings
  path through the daily metadata audit. At 04:52 UTC its latest feed-path commit
  was `37b15024d22f281110e57a85fde9541c67222263`, dated 04:31:34 UTC. This does not
  establish when the jobs first appeared on Simplify's full website.
- Existing source configuration, eligibility filters, private reporting and
  notification records remain preserved. See `MAINTENANCE_ACCEPTANCE.md` for
  completed scheduled-run evidence and deployed revision.
- Final runtime `1d36c8261773` passed runs 245 and 246, each with 213/213 sources.
  All 2,967 prior job identities/first-seen/baseline values and ten notification
  status/receipt values matched after restart. The populated jobs and maintenance
  databases passed the second actual-host restore test at 05:09:58 UTC.

Outstanding owner setup: off-host restic bucket/scoped credentials. This is a
known single maintenance warning, not a reason to repeatedly request credentials
in chat. Daily verified local snapshots are active; independently verified
manual off-host predeployment snapshots exist on the Windows computer.

Review queue / next weekly coverage review:

1. Inspect persisted intermittent source evidence, including any recurrence of
   Atlassian's pre-upgrade conflicting duplicate requisition response. Runs 240
   and 241 failed that existing safeguard; run 242 recovered. Do not weaken
   identity validation or call the intermittent failure a verified code defect
   without reproducing it.
2. Revisit the 24 known public-feed-only company gaps in the coverage report,
   prioritizing newly available permitted structured routes. Google's direct
   gap and Meta's explicit public-feed-only policy remain unchanged. This session
   did not manually re-audit every company's official careers landing page.
3. Confirm season/repository continuity as recruiting seasons change. Current
   automated metadata monitoring checks the configured feed; it does not prove
   that a newly created sibling season repository is also being collected.
4. Review dependency proposals against official release information and run the
   tests/live checks before merging or deploying. Dependency automation is not
   an auto-merge mechanism.
5. Verify off-host restore evidence after credentials are configured. Confirm
   maintenance/worker state is retained by any restoration, and record an actual
   completed agent review on the host so a missed-review alert is meaningful.

Known limitations: plausible partial data can evade anomaly thresholds; a
legitimate seasonal decline can require a reviewed new baseline; blocked sources
remain incomplete; external delivery acknowledgement failures can cause a rare
duplicate if the provider accepted a message but its response was lost. Neither
CI nor a heartbeat proves complete market coverage.

## Repair and weekly review — 2026-09-28

The owner-reported incidents were compared with current production state and
permitted live endpoints. Société Générale requisition `26000K4P` reproducibly
returned HTTP 410 and previously aborted its entire source. AMD's changing iCIMS
pagination totals and Atlassian's conflicting duplicate snapshots were retained
as intermittent evidence. Broadcom's malformed Workday row did not reproduce.
The new bounded snapshot retry discards an inconsistent attempt and repeats the
whole request set once; persistent inconsistencies and every existing identity,
count, schema, destination, robots and access check still fail visibly. See
`REPAIR_2026-09-28.md` for regression and source evidence.

Azure remained on `1d36c8261773` until a fresh host review showed Fidelity's
known alias defect at 2,110 consecutive failures. The worker, supervisor and
local backup timer were active, outboxes had no pending deliveries, and the
September 28 local restore proof covered both databases. The owner approved the
narrow SSH allowlist update, enabling a verified two-database off-host snapshot,
Azure staging and cutover to `ce0d1ccc882b`. All 213 staged source contracts,
339 application tests, seven backup tests and GitHub CI passed. Consecutive
production evidence and preservation results are recorded in
`MAINTENANCE_ACCEPTANCE.md`.

The configured Simplify source still points to the canonical, unarchived
`SimplifyJobs/Summer2027-Internships` repository, `dev` branch and
`.github/scripts/listings.json`; its latest reviewed feed-path commit was
`0b529f6c00e169a96016b8e856fa6b2b58bc309a` at 20:31:27 UTC. This confirms the
public repository feed, not Simplify's full website or its upstream publication
latency. Three dependency proposals remain unmerged pending review: Protego
0.6.2→0.7.0, actions/checkout 4→7 and actions/setup-python 5→7.

This weekly coverage review was partial. The 24 known permitted-route gaps,
including Google's direct gap and Meta's public-feed-only limitation, remain the
next company-review cursor. Automatic off-host storage is still unconfigured.
The S&P Global count-drop contract is open for evidence-based review, and the
validation backlog must be observed until sustained recovery clears its warning.

## Source repair review — 2026-09-29

Production and permitted live evidence confirmed three current adapter issues.
Atlassian introduced one additional public iCIMS portal; Capital Group retained
an expired Workday search row whose exact detail returned 404; and Fidelity
returned eight stable search-only shells alongside 331 usable records. The
prepared repair preserves strict identity, redirect and access checks and reports
Fidelity's incomplete upstream rows through a dedicated maintenance ticket. See
`REPAIR_2026-09-29.md` for evidence and acceptance gates.

The local suite passes with 346 tests and 126 subtests. Live checks passed for
Atlassian, Capital Group and Fidelity. Deployment remains pending because the
maintenance computer's public address changed after the approved single-IP SSH
rule update. The existing off-host-backup setup gap and weekly coverage-review
cursor are unchanged.

The later complete-source staging pass reproduced an additional Atlassian
mirror: requisition 25264 appeared on two reviewed regional iCIMS portals with
identical core content. A focused regression now permits only this structurally
identical portal mirror and preserves failures for any core-content conflict or
unreviewed host. The expanded local suite passes with 347 tests and 126 subtests.

## Weekly source and dependency review — 2026-10-07

The review began from deployed revision
`b3d88cd7674eb84853be889db6c8ff24bda317d6`. A complete permitted local live
collection checked 213 enabled sources and collected 36,367 records. Moody's
had one reproducible structured-location omission and HubSpot's former
Greenhouse board had been retired. Three access failures passed immediate
isolated retries. The prepared strict Moody's fallback and explicit HubSpot
public-feed-only downgrade are documented in `REPAIR_2026-10-07.md`; production
remains unchanged pending the actual-host acceptance gates.

The configured Simplify source remains the canonical, unarchived
`SimplifyJobs/Summer2027-Internships` repository, `dev` branch and
`.github/scripts/listings.json` path. Its latest reviewed path commit was
`1c7e4c0c59a24d57949cb006f8ae7eb160ba9b58` at 20:31:56 UTC. This confirms
only the public repository feed. It cannot prove full-site coverage or upstream
employer-to-feed delay.

The official careers routes for Balyasny, BNP Paribas, Campbell & Company and
Citadel were manually revisited as the next four items in the gap cursor. The
landing pages or internship/opening directories remain current, but this review
did not establish a complete permitted structured collector for any of them.
Citadel's current openings remain inaccessible from the Azure collector and no
documented stable API was found. They therefore remain explicit public-feed-only
gaps; no page restrictions were bypassed.

GitHub CI for the deployed commit passed again on October 5. Dependabot PR #4
updates Protego from 0.6.2 to 0.7.0 and changes robots matching behavior; it is
not eligible for automatic merge and needs source replay plus Azure staging.
The actions/checkout and actions/setup-python major-version proposals also
remain unmerged pending review. Dependabot security-alert details were
unavailable because the repository setting/API denied that read; this is not
evidence of zero vulnerabilities.

The next weekly cursor begins after Citadel and continues through the remaining
official-route gaps, then dependency replay and actual off-host restore evidence.
The known missing automatic off-host bucket connection remains unchanged and is
not being re-requested. Live Azure maintenance state, production source health,
recent runs, notification receipts and current backup restore proof remain
pending until the authenticated single-IP maintenance path is restored.

## Deployment preparation — 2026-10-22

SSH access was restored by rotating the existing owner management rule from the
stale network range to the current single-client /32, retaining TCP 22 and the
existing SSH key. Read-only Azure checks confirmed runtime `b3d88cd` and current
Discord delivery. HubSpot's original Greenhouse board had recovered: production
source state showed 62 rows, zero failures and success at 21:08:26 UTC. Its
October 7 retirement proposal was therefore reversed before deployment. All
other source settings and the owner's filters are retained. Old Mission's 404
is left as a known exception per the owner's instruction. Pending cutover still
requires the off-host snapshot, staged live check and production acceptance.

The maintenance timer was active but its service repeatedly reached the old
four-minute timeout. Its last completed report was 12:30 UTC, and the due daily
integrity marker remained at October 21, 12:34 UTC. The jobs database is now
approximately 3 GB; a fresh full integrity check and compressed backup took about
six minutes on this host. The prepared unit extends the bound to ten minutes
within the existing fifteen-minute schedule. Actual post-update supervisor
completion must still be verified; checks are retained rather than disabled.

Acceptance also reproduced an independent supervisor defect at
`maintenance.py:339`: observing an already queued/delivered weekly canary still
issued `INSERT OR IGNORE`, unnecessarily requesting the worker database's write
lock. Production had retained 27 storage-error occurrences at this line. A real
SQLite regression held an independent write transaction while reading the
existing receipt; the old code failed with `database is locked`. The repair reads
and returns that receipt before attempting an insert. New weekly canaries still
use the durable, deduplicated insertion path. This preserves real storage alerts
and avoids the unnecessary recurring write conflict.

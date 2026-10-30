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

The final repair `c145618` was deployed and accepted at 21:36 UTC. Runs 9211 and
9212 collected all 213 configured sources, with only the owner-ignored Old Mission
404 failing; the other 212 passed. The Discord deployment check was delivered
once and no worker messages remained pending. All prior job, identity,
source-record and delivered-receipt assertions passed after restart. Both
off-VM restored database copies were verified before cutover. The integrity
marker advanced to 21:19:18 UTC and supervisor executions at 21:30 and 21:36
completed in 1.272 and 1.919 seconds, resolving storage/stale-review incidents.
See `DEPLOYMENT_2026-10-22.md` for measured evidence. Existing contract warnings,
backlog/coverage gaps and the automatic off-host bucket setup remain open. No
baseline or job status was changed to silence them. This deployment did not
complete a new review of every official careers route or dependency proposal;
the prior weekly review cursor remains outstanding.

## Daily and partial weekly review — 2026-10-23, 23:15–23:20 UTC

Azure Run Command provided actual-host inspection after SSH timed out. The
existing Azure session refreshed successfully; no network rule, credential,
runtime code, source configuration, filter, job status or delivery history was
changed. The running release remains `c1456189b7bc`.

- Worker and both maintenance/local-backup timers were active and enabled, with
  zero worker automatic restarts. Completed runs 9499–9501 each passed 212 of
  213 configured sources, taking 322.918, 322.219 and 322.893 seconds. Only the
  owner-ignored Old Mission Greenhouse 404 was failing. These observations do
  not demonstrate permanent freedom from intermittent upstream failures.
- Nvidia returned 215 records at 23:12:01, Palo Alto returned 29 at 23:12:19,
  and Simplify returned 5,040 at 23:16:14, all with zero current failures.
  Palo Alto's two-shell partial-source ticket had resolved on October 22 at
  06:45:31, before the latest deployment; it was not repaired by that update.
  Its retained October 23 robots/access-verification failure is informational
  history, followed by successful normal collections. No access bypass or
  reproducible new pagination/parser defect was established.
- At 23:15 the worker outbox contained 1,901 delivered messages and no pending
  records; its latest acknowledgement was at 23:10:20, receipt
  `1563328753780658198`. Maintenance had 1,086 delivered, 14 cancelled and none
  pending. Its latest acknowledgement was at 22:00:06. No extra test message
  was sent; these are provider receipts, not a new owner inbox confirmation.
- The latest sampled maintenance report was 23:00:31, completed in 1.680
  seconds without failed delivery. Storage remained resolved; the daily
  integrity marker advanced to 21:34:26. Local backup restore evidence at
  05:09:12 verified the 3,049,222,144-byte jobs database and the additional
  maintenance database, including saved table counts. Free storage was
  35.68 GiB. Automatic off-host restore proof remains absent; the already-known
  bucket setup requirement is unchanged and was not requested again.
- Healthchecks independently showed both scraper and maintenance indicators
  UP, with recent pings and the email integration attached. Their schedules
  remain five minutes plus fifteen-minute grace, and fifteen minutes plus
  twenty-minute grace, respectively. The off-host backup check still has never
  received a ping, consistent with the known setup gap. No missed-ping outage
  test was repeated during this review.
- Overall validation candidates rose 1,395 → 1,408 → 1,415 in the three sampled
  cycles. This short rising window does not establish stability. There were
  114 qualifying rechecks due, oldest at 22:11:08 (about one hour overdue), and
  zero included jobs awaiting their first link check. The five latest saved
  notification decisions each occurred 283 seconds after discovery; this is a
  small recent sample, not a worst-case guarantee or upstream publication delay.
  The existing backlog-growth ticket had recovered at 18:15:26 after the
  sustained recovery window; it may reopen on renewed sustained growth.
  Validation-lag also remained resolved. No thresholds or statuses were relaxed.
- GitHub Tests for deployed backend `c145618` and default-branch `4291ae7`
  were successful, including runs `39856029512` and `39859062092`. Three
  dependency proposals remain unmerged: Protego 0.7.0 plus charset-normalizer
  3.5.2 in PR #4, checkout 7 in #2, and setup-python 7 in #1. Protego changes
  robots matching, so passing PR CI alone does not replace source replay and
  staged acceptance. The Dependabot alerts endpoint returned 403 and reported
  alerts disabled; vulnerability-alert state therefore remains unavailable,
  rather than being reported as zero vulnerabilities.

The supervisor's daily feed audit at 21:15:24 confirmed the canonical,
unarchived `SimplifyJobs/Summer2027-Internships`, branch `dev`, path
`.github/scripts/listings.json`, commit
`1ca4a34cfb953007fb0888892de37c8bb5723417`, dated 21:01:49 UTC. This is public
repository coverage; neither additional seasons nor Simplify's complete website
or upstream latency were established.

The weekly official-route cursor advanced through four more known gaps:

- [Citadel Securities internships](https://www.citadelsecurities.com/careers/internships/)
  still links to an internship-filtered open-opportunities directory. The
  observed directory contained filter controls without enumerated requisitions;
  this manual review did not establish a complete permitted collector.
- [Deutsche Bank's application calendar](https://careers.db.com/students-graduates/your-application/?language_id=1)
  distinguishes US summer internships, graduate programs and their eligibility.
  Its [Search Programmes page](https://careers.db.com/students-graduates/Search-Programmes/)
  did not expose a complete requisition collection in the observed text.
- [Goldman Sachs's student directory](https://www.goldmansachs.com/careers/students/programs-and-internships)
  still points to [higher.gs.com](https://higher.gs.com/results). The observed
  directory had filter headings, while the role destination exposed no usable
  text to this review. No complete permitted API was verified.
- The previously published [HAP Capital domain](https://www.hap-capital.com/)
  again returned 404 to this review. This does not prove that the firm is closed;
  similarly named unrelated employers were not substituted.

All four remain explicitly incomplete public-feed coverage. Google/Meta and
other previously recorded gaps remain unchanged. The next weekly cursor starts
with Intercontinental Exchange, JPMorgan Chase, Millennium and Nomura, then the
remaining gaps, dependency replay, additional season continuity and automatic
off-host restore evidence. This was a partial review, not a re-audit of every
employer. No verified new code defect justified a repair or deployment, so full
runtime tests and disruptive restart/failure tests were not repeated.

The completed review marker was saved as the service account at 23:18:47 UTC.
A final host query confirmed consecutive completed runs 9501 and 9502, both
with 212 sources passing and only the known Old Mission exception. This marker
records the review performed; it does not resolve coverage or backup warnings.

## Daily review — 2026-10-26, 06:08 UTC (October 25 Pacific)

Read `MAINTENANCE.md`, acceptance notes and the preceding review before checking
production. SSH timed out again; the authenticated Azure Run Command fallback
worked without changing the single-IP firewall rule. The release remained
`c1456189b7bc`; the worker, supervisor timer and local-backup timer were active
and enabled, with zero worker automatic restarts.

Completed runs 10123–10125 passed **211/213** sources in 298.698, 311.264 and
300.117 seconds. Old Mission's owner-ignored 404 remains unchanged. The other
current failure was Bank of America's campus source: seven consecutive
`US facet missing; scope cannot be verified` failures at inspection. Its existing
ticket is `source:bankofamerica-campus`, first seen at 00:00:27 UTC; the source
last succeeded at 05:28:44, so the observed problem has been intermittent as well
as currently persistent. This is distinct from its older count-drop contract.

A permitted local diagnostic using the existing `HttpClient`, robots checks and
request pacing returned HTTP 200 with **"Quick Check Needed"** and a request to
confirm a real person, instead of the country filters/job board. The missing
facet is therefore reproducible on an access-challenge response; this is not
proof of a changed facet schema or permission to bypass the challenge. Prior
records remain intact, and no unverified job was declared open/closed or merged.
Public Simplify discovery remains available as incomplete fallback coverage.

The new `contract:ashby-replit` observation, first seen October 24, showed three
consistent 37-record responses against its 76-record baseline. All observed
description/location/URL fractions were 1.0, the host was unchanged and partial
records were zero. This is a count-drop hypothesis, not a reproduced parser
defect; its baseline and warning were retained pending independent completeness
evidence. Other existing source-contract/coverage incidents were not reset.

- The supervisor report at 06:00:24 completed in 2.730 seconds with no failed
  notification delivery. Worker outbox: 2,007 delivered, none pending; latest
  acknowledgement 05:47:07, receipt `1564153383055532144`. Maintenance outbox:
  1,124 delivered, 14 cancelled, none pending. The newly scheduled weekly worker
  canary was delivered on its first attempt at 00:03:06, receipt
  `1564066810775601183`. These are provider acknowledgements; no extra test
  notification or inbox confirmation was requested.
- Independent Healthchecks scraper and maintenance indicators were both UP,
  with recent pings and email destinations still attached. The unconfigured
  off-host backup check still showed Never; its known setup requirement was
  not requested again.
- The 05:02:01 local restore proof verified the 3,303,460,864-byte job database,
  saved table counts (4,903 jobs and 11,640 identities), and the maintenance
  database. The daily integrity marker was October 25 at 22:05:00, and disk
  space was 35.26 GiB free. This local proof does not establish automatic
  off-host recovery; the earlier verified manual deployment copies are separate.
- Due validation candidates decreased 1,608 → 1,585 → 1,546 over the sampled
  completed cycles. There were 173 qualifying rechecks due, oldest 04:42:43
  (about 85 minutes overdue), and zero included jobs without a first link check.
  The existing backlog-growth ticket remained open under its sustained recovery
  rule. A short decrease does not establish long-term capacity or justify
  changing the alert threshold.
- The daily Simplify audit at October 25, 21:30:35 confirmed the canonical,
  unarchived `SimplifyJobs/Summer2027-Internships`, branch `dev`, path
  `.github/scripts/listings.json`, commit
  `b4fd6c2cc8ba61c3925012262240a6b5255df363` (16:02:40 UTC). Upstream website
  publication latency and additional seasons remain unknown.
- Default-branch CI for `b8dcacb` passed (run `40226522522`). Dependabot replaced
  PR #4 with unmerged PR #5, adding certifi 2026.10.19 to the existing proposed
  Protego 0.7.0/charset-normalizer 3.5.2 changes. PR #5 CI passed, but no
  dependency was merged or deployed without the required behavioral/source
  review. Actions proposals #1 and #2 remain open.

No new code defect was established, so no runtime deployment, restart, data
rollback or redundant full test run was performed. The October 23 partial
weekly review remains the latest official-route review; its cursor starts with
Intercontinental Exchange, JPMorgan Chase, Millennium and Nomura. This daily
check did not re-audit those companies or claim to close the 24 coverage gaps.

An Azure diagnostic at 06:12:49 independently reproduced the same HTTP 200
human-verification page, with `human_verification: true`. Its bounded evidence
was saved as the service account in
`/var/lib/internship-watch/agent-evidence/2026-10-26-bofa.json` and appended as an
`agent_review` event under the existing Bank of America source ticket. No ticket
status, source baseline, job or outbox row was changed. The completed review
marker was recorded at 06:13:00 UTC. Direct coverage remains blocked pending
permitted access or an independently verified permitted alternative; the human
check was not solved or bypassed.

## Daily review — 2026-10-28, 20:49 UTC actual observation

The queued heartbeat's trigger time was earlier; the observations below use the
actual Azure query timestamps. Read the maintenance policy, acceptance notes
and preceding reviews first. SSH still timed out, but the existing Azure session
refreshed and Run Command worked. No firewall or credential change was needed.

- Backend remained `c1456189b7bc`, with the worker and both supervisor/local
  backup timers active and enabled, and zero worker automatic restarts.
  Runs 10815 and 10816 passed 212/213 sources in 342.908 and 322.411 seconds.
  Run 10817 passed 211/213 in 335.041 seconds: the known owner-ignored Old Mission
  404 and a PIMCO Workday response with more rows than its declared total.
  PIMCO had already returned to zero failures in current source state. One
  inconsistent upstream snapshot followed by recovery does not reproduce a
  parser defect; the strict completeness check remains enabled.
- **Bank of America direct discovery recovered through normal scheduled polls.**
  Its existing source incident resolved at 16:15:38. Six consecutive samples
  from runs 10813–10818 (20:18:27–20:46:10) each successfully returned nine
  source records, with zero current failures. No human check was solved,
  cookie/session imported, restriction bypassed or adapter modified. This is
  observed recovery, not a permanent access fix. The older 27-to-9 count-drop
  contract remains a separate unresolved coverage/completeness question.
- Fidelity and State Street each still reported one upstream partial search
  shell in run 10817, grouped under their existing `partial-source` tickets.
  Usable records continue collecting, while incomplete rows stay unresolved.
  No new identity, description or job status was invented to clear the warning.
- Worker outbox: 2,220 delivered, none pending; latest receipt
  `1565081574796566668` at 19:15:25. Supervisor: 1,245 delivered, 14 cancelled,
  none pending; latest receipt `1565100477253685459` at 20:30:32. The October 26
  weekly canary receipt remained delivered on its first attempt. These are
  provider receipts, not new owner inbox confirmations; no extra test was sent.
- The 20:45:25 supervisor report completed in 1.874 seconds without delivery
  failures. Independent Healthchecks scraper and supervisor indicators were
  both UP with recent pings and email integrations. The off-host check still
  showed Never, consistent with its known unconfigured bucket connection.
- Local restore proof at 05:14:08 verified the 3,495,862,272-byte jobs database
  and maintenance database, with saved counts including 5,078 jobs and 12,002
  identities. Daily integrity evidence was current at October 27, 22:35:21;
  34.72 GiB remained free. No automatic off-host proof was claimed, and the
  existing missing-credentials/setup request was not repeated.
- Overall validation candidates were 1,735 → 1,728 → 1,727 across the sampled
  completed runs. There were 253 qualifying rechecks due, oldest 19:20:20,
  about 89 minutes before the query, and zero included jobs without a first
  link check. Backlog-growth had recovered at 19:00:43. Validation-lag remained
  open under its lower-lag/sustained-recovery rule; the ticket's older evidence
  is not the current oldest due time. The five latest saved decisions took
  222, 91, 191, 224 and 292 seconds from discovery. This small recent sample
  does not establish worst-case delay, upstream freshness or stable capacity.
- The daily Simplify audit at October 27, 22:00:35 still verified the canonical,
  unarchived Summer2027 repository, `dev` branch and listings JSON path, commit
  `e8fb6e97fb71c8d8c77b28ed08b3931c23f6abbe` (21:02:24 UTC). Default-branch
  `a3f4490` CI passed, including run `40391613904`. Dependency PRs #1, #2 and #5
  remained unmerged. No runtime dependency or source configuration changed.

No new reproducible code defect required a repair, restart or deployment, so
full runtime tests and disruptive failure tests were not repeated. The October
23 partial weekly review remains current; the next official-route cursor is
Intercontinental Exchange, JPMorgan Chase, Millennium and Nomura, followed by
the other documented gaps, dependency replay, season continuity and off-host
restore evidence. This daily review did not re-audit every employer.

The completed review marker was saved as the service account at 20:51:41 UTC.
Run 10818 subsequently confirmed 212/213 successful sources, with only the
known Old Mission 404. PIMCO's successful 20:48:04 collection independently
confirmed its recovery. No worker restart or new notification test was needed.

## Daily repair preparation and partial weekly review — 2026-10-30

The 22:31:16 Azure query confirmed deployed `c145618`, active/enabled worker and
supervisor/local-backup timers, zero automatic restarts, a fresh successful
22:30:25 supervisor report and UP independent scraper/supervisor monitors.
Runs 11361–11363 passed 208, 209 and 210 of 213 sources in 325.475, 319.461 and
313.546 seconds. Current source state had the owner-ignored Old Mission 404 and
72 Macquarie failures; transient other failures require source-specific evidence
rather than weakening collection checks. Worker outbox had 2,353 delivered and
one pending record during an active poll; this alone does not establish failed
delivery. The latest receipt was at 22:29:17, and the supervisor had no pending
messages or delivery failures. The existing weekly canary remained acknowledged.

Macquarie's count-format defect and a generic-title classification false
exclusion were reproduced and repaired locally with failing-before/passing-after
regressions. See `REPAIR_2026-10-30.md`. All 351 application and seven backup
tests passed. Actual-host staging, off-VM backup verification, deployment and
consecutive production acceptance remain pending at this preparation point.

There were 232 qualifying rechecks due, oldest 21:08:14, and zero included jobs
without their first check. Total due counts were 1,750 → 1,750 → 1,741. Existing
validation-lag/coverage/contracts remain open. Local restore proof at 05:08:46
was valid/recent, integrity evidence was October 29 at 23:05:23, and 34.63 GiB
remained free. Automatic off-host storage remains unconfigured; no repeated
credential request was issued. Default-branch CI for `af4f9e8` passed. Dependency
PRs #1, #2 and #5 remain unmerged; no automatic dependency deployment occurred.

The daily feed audit at 22:30:26 confirmed the canonical, unarchived
`SimplifyJobs/Summer2027-Internships`, `dev`, `.github/scripts/listings.json`,
commit `f6ef829ffeb246f72e0b0506b2d71b2974540ee1` at 22:02:20. This verifies
the configured public feed, not whole-site coverage or employer-to-feed latency.

The weekly official-route review advanced through these four known gaps:

- [ICE's current careers host](https://careers.ice.com/jobs/14113?lang=en-us)
  exposed a current internship in search indexing, but direct opening returned
  HTTP 403. No access bypass or complete permitted collector was established.
- [JPMorganChase students](https://www.jpmorganchase.com/careers/explore-opportunities/students-and-graduates)
  still links to the official Oracle CX_1001 candidate site. The observed
  destination rendered no usable requisition text. No complete permitted API
  was verified by this review; its earlier access restriction was not bypassed.
- [Millennium students](https://www.mlp.com/careers/students/) currently links
  2027 applications to `campusjobs.mlp.com`, domain `mlp.com`, campus microsite.
  The observed destination exposed navigation/configuration rather than a
  complete job enumeration. This is a useful route-review candidate, not an
  enabled integration or proof of complete coverage.
- [Nomura's program overview](https://www.nomura.com/careers/early-careers/program-overviews/)
  still links to its official Tal.net campus board. The manual web view now
  exposed student opportunities rather than the earlier challenge. Actual-host
  robots/access policy, complete pagination and identity/detail validation must
  be established before claiming a working direct collector.

All four remain incomplete public-feed coverage. The next gap-review cursor is
Quantlab, Seven Eight Capital, SIG and TGS, followed by Wells Fargo/Wolverine and
the remaining earlier gaps. Dependency behavioral replay, extra season
continuity and automatic off-host restore evidence remain outstanding. This
partial review did not re-audit all companies or infer that old access failures
are permanent.

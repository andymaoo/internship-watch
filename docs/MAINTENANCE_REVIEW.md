# Maintenance reviews

The daily Codex follow-up is active in the original task at 09:00 local time.
It should investigate stored incidents and apply tested reversible repairs under
the policy in `MAINTENANCE.md`. Azure monitoring is independent of that follow-up.

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

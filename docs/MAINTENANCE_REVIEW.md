# Maintenance review — 2026-09-20 UTC

The daily Codex follow-up is active in the original task at 09:00 local time.
It should investigate stored incidents and apply tested reversible repairs under
the policy in `MAINTENANCE.md`. Azure monitoring is independent of that follow-up.

Reviewed in this session:

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

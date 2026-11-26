# New-grad discovery repair — November 25, 2026 Pacific

## Confirmed causes from Azure

- The 213-source personal worker remains internship-only. Its category routing does not enable new-grad collection.
- The dedicated member worker is running, but its configured input is only eight boards. Runs 759–761 completed, with run 761 finishing November 25 at 10:37 PM Pacific (November 26 06:37 UTC).
- The member database contains three new-grad records, all imported with baseline=1 on November 10. Silent initial import intentionally excludes them from individual new-job alerts.
- Two Databricks jobs remain unverified: their specific URLs redirect to the generic careers directory and exact Greenhouse detail requests return 404. They must not be promoted to verified openings to produce alerts.
- The Notion new-grad posting is verified; application access remains unverified. Its baseline flag, rather than a delivery failure, suppresses an individual alert.
- Capital One has 496 consecutive member collection failures with HTTP 429; Morgan Stanley has 480 and Truist 54 access-restriction failures. These are coverage failures, not evidence of zero openings. Access and retry restrictions remain enforced.
- Two real member job receipts exist, both Zoox internships. The latest was acknowledged November 25 at 21:06:11 UTC. No pending member job delivery was shown by the diagnostic query.
- Member classifier changes did not invalidate persistent classification-cache entries, because the revision fingerprint covered only classify.py. A focused restart test reproduced the stale exclusion; the fix includes member_evidence.py and member_routes.py in the rules fingerprint.

## Repair and acceptance sequence

1. Preserve existing member identities, original baseline and first-seen timestamps, and all delivered receipts.
2. Extend the member rules for explicit University Grad, New College Graduate, specific graduate engineering/quant titles and role-specific recent-graduate descriptions. Generic junior wording remains insufficient.
3. Add six reviewed structured boards: Stripe, Figma, Ramp, Datadog, IMC and Optiver US. Preserve existing eight sources and their failure evidence; do not bypass blocked sources.
4. Stage the member-only release and run the full tests. Verify an off-VM SQLite snapshot by SHA-256, integrity and all-table counts before activation.
5. Collect and validate with the staged code and permitted HTTP policies, a disposable database, no Discord transport, and the same shared collection lock.
6. Switch only the member symlink/config between executions. Preserve the personal worker and its notification history. Keep rollback code/config; never restore the snapshot over newer production state as routine rollback.
7. Verify consecutive production member executions, actual category routing with a labeled canary and acknowledged receipt, retry/dedup regression tests and source-specific unresolved checks. Existing baseline imports stay silent; provide a grouped catch-up report rather than presenting old jobs as newly posted.

## Local/staged evidence so far

416 tests and 136 subtests pass locally and on Azure. The regression test failed before the cache fix and passes afterward. The staged release is `/opt/internship-watch-releases/newgrad-2b72a03a46dd`; it is not active until acceptance/cutover is recorded below. The member snapshot is verified outside Azure at `work/private/newgrad-2b72a03a46dd/member.sqlite3` (SHA-256 8a0750cb1017364f5bb0579816961e49cab4e5d54e4a2e845a94d1bb1f8c7421).

The fresh local bounded collection returned Stripe 772, Figma 141, Ramp 183, Datadog 391, IMC 151 and Optiver US 146 records. Explicit US new-grad matches: two Stripe, two IMC and two Optiver; other raw records are not automatically graduate opportunities. Live Azure staging and cutover evidence remains to be appended.

## Activated and verified on Azure

The member symlink now selects `newgrad-2b72a03a46dd`, with 14 configured sources.
The personal release remains `category-personal-8664d236bdef`. Only the member
source list and member release changed; existing filters, keys, baseline flags,
first-seen values and acknowledged receipts were preserved. Rollback config is
`/root/newgrad-2b72a03a46dd/member-config.json`; the prior member release remains
available. Roll back the symlink/config only, preserving current SQLite data.

Production runs 762 and 763 completed at 22:56:59 and 22:58:26 Pacific on
November 25. Both passed 11/14 sources, including all six additions. The three
previously described Workday restrictions remained, so both runs correctly
reported degraded rather than full health. Runs took 104.015 and 31.807 seconds.
The first checked 30 links; the second had no further due links. Seven new-grad
postings are now verified: one Notion, two Stripe, two IMC and two Optiver.
Two historical Databricks records remain unverified. IMC and Stripe application
access was verified; Notion and Optiver application access remains unverified.
No pending member outbox messages remained at inspection. No naturally new
qualifying discovery occurred during these acceptance runs; existing baseline
jobs were not replayed as new-job alerts.

A real labeled new-grad SWE canary was acknowledged by Discord after a
controlled pre-transport failure. The persistent test outbox retained the failed
attempt, then saved the successful retry receipt, and a third drain sent nothing.
Receipt 1575404681348259992 was fetched and confirmed to belong to the exact
new-grad-swe channel. This tests retry handling and real transport; the injected
first failure was not an actual Discord outage. The separate catch-up digest
receipt 1575405680293191770 was fetched and confirmed in the private digest
channel. Both use a separate durable test/report outbox; production job receipt
keys and baseline flags were not consumed or changed.

The existing member timer remains enabled at :05/:35 UTC (30 minutes); the
personal worker retains its five-minute target. This expansion does not establish
five-minute new-grad delivery or complete market coverage. Shared source locking
prevents overlapping network polls and can delay execution behind the other
worker. Public source release delays and blocked access remain independent limits.

The updated member HTML/CSV export was downloaded to
`C:/Users/o3ti3/Documents/Codex/2026-09-18/c/outputs/newgrad-repair/report/`.
These downloaded files are snapshots, not a live connection to Azure.

## CI correction

The first GitHub run after publishing the previously unpushed member work failed
because CI installed only runtime requirements and used unittest discovery.
The newer member tests require pytest, and unittest discovery also omits their
function-based test cases. CI now installs pinned test-only requirements and
runs pytest over the complete tests directory, retaining the separate deployment
backup tests and compile check. Production runtime requirements are unchanged.

The corrected GitHub CI run 45772688255 passed for daa9eb4. A fresh isolated
local environment using only requirements-test.txt also passed all 416 tests,
136 subtests, seven deployment backup tests, and compilation. README scope and
polling details were corrected to distinguish the personal and member workers.

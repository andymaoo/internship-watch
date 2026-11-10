# US early-career Discord rollout

## Decisions

One catalog, two member tracks (internship and explicit new grad), and category
feeds for PM, IB, Quant, SWE, ML/AI and Data. Keep the three existing data
categories in storage; group them in Discord. Research and co-ops route only
when the listing establishes an internship or new-grad track; leave other
programs for review until there is demand for a separate feed. Do not infer
new-grad status from full-time, junior or low experience alone.

Filter in this order: normalize and deduplicate; accept confirmed US locations and remote roles unless the
listing explicitly excludes US-based work; establish opportunity type; classify role by
responsibilities; prioritize posting verification; then route and deduplicate
delivery. Unknown geography for non-remote jobs, or unknown type/category, goes to review.
Remote does not include hybrid or on-site roles. For the geography adapter,
test US-remote, unspecified remote, worldwide remote, remote outside the US
only, non-US hybrid, and ambiguous on-site locations. Label unspecified remote
as such in alerts; inclusion does not establish work authorization.
No member sponsorship, clearance, degree or citizenship filters; preserve any
employer-stated restrictions as facts in the listing. Never imply eligibility.
Leave existing private preferences and delivery history untouched.

## Discord and Whop

Use two categories, Internships and New Grad, with read-only channels such as
#intern-quant and #new-grad-swe. Whop owns Paid Member; Staff alone sees operations.
Deny everyone View Channel on paid categories; grant Paid Member view only.
Topic roles are notification preferences and must never grant channel access:
Discord combines role permissions, so granting View Channel to a topic role
can undermine the paywall. Start with channel follows via member notification
settings or a paid-only preference picker; no role mentions by default.
Test an unpaid member, a paid member, a canceled member with stale topic
preferences, and staff. Test that no paid jobs or webhook URLs leak.

Discord Community Onboarding can personalize channels and roles, but its seven
default channels and five everyone-readable/writable channel requirement make
it unnecessary for this gated pilot. Use a welcome guide and channel list first.
If adding exact opt-in pings later, use a bot with restricted permissions and
pair preferences such as internship + quant; separate stage and topic mentions
would ping people matching either. Webhooks suffice for initial channel posts.

- [Discord permission setup](https://support.discord.com/hc/en-us/articles/206029707-Setting-Up-Permissions-FAQ)
- [Discord Community Onboarding](https://support.discord.com/hc/hi-in/articles/11074987197975-Community-Onboarding-FAQ)
- [Whop Discord access setup](https://whop.com/blog/link-whop-to-discord/)

## Build and release order

1. Implement and test the standalone routing contract. In staging, add evidence
   adapters for geography, explicit internship/new-grad and IB. Keep uncertain
   listings in review. Audit upstream student-only searches and add separately
   tested US new-grad queries and IB boards; the router cannot recover jobs
   that sources never return. Start with existing public feeds and permitted
   employer ATS endpoints; verify commercial redistribution terms.
2. Quiet the feed: the Nov 3–10 Azure sample had 178 job alerts, 33 worker
   digests, one maintenance digest and 403 incident messages. Group incident
   history by key and warning/recovery before tuning. Keep outages, storage
   and delivery failures immediate to staff, with independent email monitoring.
   Require sustained recovery for flapping warnings; retain evidence in the
   maintenance report. Offer a separate opt-in daily unverified digest; remove
   jobs verified before send, and keep verified alerts immediate.
3. Wire the router into a separate staging delivery path with per-job,
   per-destination dedupe and retry. Seed history silently; test restart,
   permissions and membership revocation before using live Whop or Discord.
4. Benchmark direct versus feed discovery: Simplify first surfaced 324 of 372
   new jobs in the sample. Compare matched requisitions against Jobright and
   a speed competitor for two weeks; report first-observed-live to actual
   delivery p50/p90, wins, misses and coverage. Do not sell the five-minute
   polling target as an employer-to-alert guarantee.
5. Release only after staging evidence, recoverable backup, rollback plan and
   confirmed production access. Preserve the private worker during pilot.

## Testing gates

Before advancing each stage, run focused regression tests and the full local
suite. Validate geography and classification on representative employer fixtures
before integrating delivery. Require staging evidence for source completeness,
discord routing, daily digest suppression, incident recovery, failed-send retry,
restart deduplication and subscription revocation before production cutover.

## Local implementation checkpoint

The member route and normalized listing preview are implemented separately from
the production worker. The preview consumes existing title, employment type,
description, country, location, workplace and validation fields. Tests cover
remote with unspecified geography, foreign-only remote, structured country
evidence, hybrid, explicit graduate titles, generic junior titles, contradictory
internship evidence, IB, hardware and posting/application status.

The maintained local suite passed: 388 tests and 136 subtests. These are
synthetic normalized-record tests, not evidence of employer coverage. Before
connecting the preview to an outbox, replay actual source fixtures, audit
student-only queries and verify which IB and new-grad titles need description
evidence. No Discord mapping or live delivery is enabled by this checkpoint.

## Notification split: local staging and cutover

Configure the existing job webhook, a staff-only webhook, and a webhook in a
separate opt-in digest channel. Set their URLs only in the private service
environment as DISCORD_WEBHOOK_URL, OPS_DISCORD_WEBHOOK_URL and
DIGEST_DISCORD_WEBHOOK_URL. Never paste them into chat or Run Command history.
In the private worker and supervisor configuration, enable
notifications.split_channels, set awaiting_digest_enabled explicitly, and set
awaiting_digest_seconds to 86400. Split mode enforces a 24-hour minimum.
Existing pending messages retain their history and follow the new routing when
retried. An already-due digest may send at cutover, then the daily interval
applies. A missing destination keeps the message queued without fallback.

Before restarting production, verify a fresh off-VM recovery copy and stage
labeled canaries against each configured webhook; confirm the actual Discord
channel and message receipts. Verify staff permissions as a non-staff member.
After cutover, observe consecutive worker runs and a supervisor run. Restore
the previous release and private config if routing fails; keep the live SQLite
history. Member category feeds and incident recovery tuning remain separate
stages.

Local notification destination, no-fallback and daily batching tests passed.
The maintained suite passed 396 tests and 136 subtests. Azure Run Command
confirmed the existing worker is active; SSH timed out. No channels, webhook
secrets, production settings, or runtime files were changed.

The approved single-IP SSH rule replacement restored strict-key access.
Release split-0d0b041cdede was staged on Azure alongside 31d418e3d958 and
passed 396 tests and 136 subtests on the host. The live symlink remains on
31d418e3d958. A fresh manual recovery copy was started; the permanent backup
bucket is unchanged. Redacted host inspection confirmed that only the jobs
webhook is present. The ignored cutover helper checks distinct channel IDs,
supports labeled canaries, and preserves the original config for rollback.

## Azure cutover — 2026-11-10

The active release was switched to split-0d0b041cdede after the staged suite
passed (396 tests, 136 subtests). Strict-key SSH worked after replacing the
single-IP rule. The local off-VM copies of both SQLite databases matched the
compressed and restored hashes, integrity checks, and table counts. A
post-cutover read confirmed all 2,987 worker and 1,722 supervisor delivered
receipts in the snapshots were preserved. The scheduled backup bucket was
not configured by this work.

Verified destinations: existing #internships, private #watch-ops, and private
#watch-digest. No Discord roles were added to the two private channels. The
digest is currently administrator-only; grant access to consenting members
only after the server's membership rules are set up. The three test receipts
were 1569668178156453915 (jobs), 1569668180417318933 (staff), and
1569668182459940867 (digest). Secrets are in /etc/internship-watch.env.
The worker and supervisor use /etc/internship-watch.json; the only live
config changes were split routing, enabling awaiting digests, and setting the
digest interval to 86,400 seconds. Filters, sources, and polling were preserved.

Rollback uses the previous release at
/opt/internship-watch-releases/31d418e3d958 and the saved pre-split JSON in
the staged release. Restore the pre-split environment as well if reverting
destination routing. Stop the timer and services for a cutover, preserve the
live databases, switch the release and configuration, then restart worker
and timer. To intentionally stop scheduled processing, stop the worker and
maintenance timer; independent Healthchecks may alert as designed.

Post-cutover acceptance: worker runs 14183 and 14184 completed consecutively
at 11:09:08 and 11:14:29 UTC. They checked 213 sources each, with 208 and 209
successful respectively. Atlassian, Old Mission, MSCI and Trexquant had already
been failing before cutover; BlackRock's changing Workday pagination total
affected the first cycle and recovered on the second. No notification failed
or remained queued. Run 14184 delivered a real job message with Discord
receipt 1569671498715897942 at 11:14:08 UTC. The scheduled supervisor run
completed successfully at 11:15:27 UTC, with no delivery errors. Worker and
maintenance timer are active and enabled. The first organic daily digest was
not observed in this window; its destination was verified with the labeled
Discord test and its cadence in the automated tests.

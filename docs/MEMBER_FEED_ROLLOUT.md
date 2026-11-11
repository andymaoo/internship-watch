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

## Category-channel pilot

Internships and New Grad each have six locked channels: SWE, ML/AI, Data,
Quant, PM and IB. No member roles were granted. Incoming webhook URLs live
in root-only /etc/internship-watch-member.env; the existing staff webhook
receives operational messages. There is no fallback into #internships.
All twelve webhooks were checked against their exact channel and server IDs,
and each returned a Discord receipt for one labeled routing test.

The pilot is a separate systemd oneshot with its own SQLite database, exports,
release directory, and queue. It never emits the personal worker's heartbeat.
The initial source import is silent; later verified jobs use the canonical
job ID for dedupe and the current classification for the channel lookup.
A missing destination keeps delivery pending. The timer schedules two polls
an hour; shared locking prevents concurrent collection with the personal
worker, which can defer a personal poll while the member pilot runs.

Eight reviewed boards are enabled: Databricks, Notion, Zoox, Point72, Bank of
America campus, Capital One, Morgan Stanley, and Truist Securities campus. Workday member queries add
new-grad and investment-banking summer searches; the private worker's searches
are untouched. The November 10 local live probe collected all seven boards.
Databricks and Notion produced explicit new-grad candidates. No qualifying IB posting appeared in the initial seven-board probe. The
additional Truist campus query returned a verified IB internship in the next
Azure run. This pilot does not mirror all 213 personal sources.

Local and VM staging tests: 400 tests and 136 subtests passed. Tests include
silent seeding, remote location rules, new-grad and IB routing, missing
destination retry, durable deduplication after restart, and refusal to use the
personal database in member mode.

To stop only the category pilot, run:
    sudo systemctl disable --now internship-watch-member.timer
    sudo systemctl stop internship-watch-member.service

The personal worker remains on its separate release and database. To resume
the pilot after checking configuration, enable the member timer again.


### Deployed pilot acceptance — November 10, 2026

Release /opt/internship-watch-releases/member-cbd7761a5233 contains the member
runtime from local commit 3aa65a0. The two initial host runs were triggered
for acceptance; the recurring timer was enabled after they passed.

| Run | Finished (UTC) | Successful boards | Verified listings | Delivered or failed |
| --- | --- | ---: | ---: | --- |
| 1 | 11:39:38 | 7/7 | 20, including 3 new-grad roles | 0 delivered, 0 failed |
| 2 | 11:42:13 | 8/8 | 21, including the Truist IB internship | 0 delivered, 0 failed |

Both runs retained the initial listing backlog silently and had empty outboxes.
Discord acknowledged the 12 labeled route tests, and a transient systemd check
loaded all 12 distinct mappings from the same private environment file used
by the service. No organic post-baseline alert was observed during acceptance.

The collection timer is active and enabled, scheduled at :05 and :35 UTC.
The daily local restore-check timer is active and enabled, and the first
manual snapshot was restored and verified at 11:42:24 UTC. Its downloaded
off-VM copy matched the saved hash, passed SQLite integrity, and matched all
table counts. Automated off-VM backup storage remains unconfigured.

Private server report: /var/lib/internship-watch-member/export/jobs.html,
with jobs.csv and link-validation.json in the same directory. The existing
personal release stayed active and its configuration was not modified.
Stop the member backup timer as well if suspending all member tasks:
    sudo systemctl disable --now internship-watch-member-backup.timer

Member access, paid enrollment, full source expansion, and end-to-end
speed benchmarking remain separate from this private deployment.

## Server-member visibility and primary-worker routing

Both Discord categories and all twelve child feeds were synchronized with
server-member view and read-history allowed, and posting, thread creation,
and webhook management denied to everyone. Operations and digest channels
remain private. This is server-member access, not a change to Whop billing.

The original worker still sends jobs to #internships until the Azure cutover.
The local opt-in notifications.category_channels implementation uses its
stored, verified internship category to select the matching channel. It
preserves the original filters, source registry, SQLite identity, and outbox
keys. Unmapped category jobs remain queued; digests and operational messages
use their existing destinations. No historical job alerts are replayed.

When Azure access is restored:
1. Stage the same tested delivery code in new personal and member releases.
   Verify all existing webhook IDs and file permissions without printing URLs.
2. Verify fresh off-VM snapshots of personal jobs, maintenance, and member jobs.
   Save both active releases, configs, and systemd unit/drop-in versions.
3. Pass /etc/internship-watch-member.env to the primary worker as an additional
   root-owned systemd EnvironmentFile. Enable category_channels for the main
   worker; set category_peer_database in each config to the other's absolute
   SQLite path. Both services need SQLite WAL access to the peer directory
   under their service sandbox, but the receipt query opens the peer read-only.
   Keep the existing shared poll lock and check that drain/retry respects it.
4. Test both deployed paths under the service account with non-posting staging
   fixtures; test receipt suppression, existing digest/ops routing, and missing
   destinations. Cut over between runs, then check consecutive runs, a natural
   job receipt and its channel, zero unexpected legacy sends, and supervisor
   health. Roll back code/config only if routing fails.
5. Only exact shared identities with an acknowledged category receipt suppress
   the second post; a legacy #internships receipt is not a category delivery.
   Suppression records a separate outbox state rather than fabricating delivery.

Local evidence: 406 tests and 136 subtests passed. SSH timed out and the Azure
browser session remained expired, so no production routing or storage was
changed for this cutover.

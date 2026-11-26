# Business funnel implementation and coverage limits

## Scope and selection

The target catalog contains five lists of 50 employer names and 161 unique names
across technology consulting, strategy consulting, technical product management,
product strategy and business analysis. These are curated research/watch targets,
not a defensible universal ranking of the best 50 firms. Vault's published survey
methodology informed consulting selection; technical PM/product/analyst lists are
editorial targets, not a Vault ranking. See BUSINESS_EMPLOYER_TARGETS.md and
config/business-employer-targets.json for every name and overlap.

## Current combined Discord destinations

The November 26 owner-requested grouping supersedes the original eight-destination
business layout. There are four additional webhook destinations (sixteen total
including the existing twelve):

| Stored categories | Internship channel | New-grad channel |
| --- | --- | --- |
| Technology consulting; strategy consulting | intern-consulting | new-grad-consulting |
| Product strategy; business analysis | intern-strategy-and-business-analysis | new-grad-strategy-and-business-analysis |

Only destination grouping changes. Individual job categories, exact identities,
filters, opportunity types and delivery history remain distinct. Technical PM
continues to use the existing PM destinations. The updated private webhook
template has these four keys. Actual delivery to them requires those URLs;
existing twelve mappings are preserved. Local and staged Azure regression suites
passed 456 tests and 136 subtests, including distinct-job delivery to shared
channels and suppression of repeat notifications.

The active combined-route releases are combined-personal-1ec851a28f9b and
combined-member-1ec851a28f9b. All 27 runtime modules on each matched code commit
436d1f0f2202ffce5eb4665b26704d7b613c1b06, published to the canonical main branch;
[GitHub CI passed](https://github.com/andymaoo/internship-watch/actions/runs/45786467284).
This was a reversible code-only deployment: live JSON configuration and secret
files were unchanged. Fresh member/maintenance SQLite copies were verified off
the VM using hashes, integrity and all-table counts; the prior verified full
personal recovery copy was retained. Private rollback metadata is under
/root/combined-business-routes-1ec851a28f9b. No data was restored or reset.
The four new webhook fields remain unset, so real delivery to these destinations
awaits private configuration and labeled routing tests. Existing twelve routes
continue to use their current credentials.

On November 26 Pacific time, scheduled member runs 775 (00:52:04–00:54:15) and
776 (00:57:53–00:58:39) completed OK on this version. The initial run refreshed
the classifier cache after the routing revision; the following run took about
46 seconds. Snapshot-to-production comparison preserved all 6,536 personal and
3,046 member job identities, first-seen timestamps and baseline flags, plus all
3,774 personal and 60 member delivered receipts. The supervisor checked run 776
at 01:01:36 Pacific with zero pending notifications and zero delivery failures.
These checks do not claim delivery to the four new channels while URLs are unset.
Private evidence: work/maintenance/combined-business-routes/{stage.txt,
backup-verified.json,cutover.json,runtime-match.json,history-preserved.json,
scheduled-check.json,maintenance-and-routes.json}.

## Funneling strategies investigated

1. Reuse existing complete employer collections from Greenhouse, Ashby, Lever,
   SmartRecruiters and compatible campus/public feeds. Two independent workers
   must not repeatedly fetch the same board to apply different filters.
2. Inspect official company roots and career links; inspect linked recruiting
   hosts, including public iCIMS and Workday destinations. Respect robots,
   rate limits, authentication boundaries and complete pagination.
3. Inspect actual active public feed job URLs to identify additional ATS routes,
   rather than guessing company slugs. Accenture Federal Services routes are
   subsidiary coverage, not all Accenture openings.
4. Ingest both publicly available Simplify repositories: Summer2027-Internships
   and New-Grad-Positions, dev branch, .github/scripts/listings.json. The latter
   was previously missing and is a major new-grad input gap. Both feeds expose
   active/is_visible booleans; feed dates remain source metadata, not employer
   posting dates. Neither feed is Simplify's full website or every employer job.
5. Official native employer job-alert emails and talent communities can cover
   sites that lack a permitted collector. These require account/subscription
   setup and have their own delivery intervals; they are not enabled by naming
   a company in this catalog. Existing Handshake/LinkedIn native-alert workflows
   remain separate from the Azure pipeline. No account-gated scraping is added.
6. Licensed job-search APIs are a possible additional contract/account route.
   Adzuna documents keyword/location job search and requires registration for an
   API key (https://developer.adzuna.com/). Access rights, redistribution rights,
   quota, cost and actual employer coverage must be checked before activation.
   The former Muse developer URL currently redirects to an About page, so it is
   not treated as a verified working integration. USAJOBS documents a separate
   federal job API (https://developer.usajobs.gov/); it cannot fill private-firm
   consulting coverage by itself. None was purchased or silently activated.
7. Keep per-company unresolved routes and a weekly review cursor. A career-page
   HTTP 200, an empty board or one found posting does not prove future complete
   enumeration. Permissions or an employer-provided feed may be the only sound
   remaining path for some companies. No strategy guarantees all future jobs.

The bounded public audit covered all 161 company targets, with up to an official
root, a career page and an observed job-search destination for unimplemented
companies. Existing registry matches were reused. config/business-route-audit.json
records actual observations, access failures and still-unenumerated pages.
New source candidates were live-tested locally and on Azure; only ten additions
passed Azure verification. Failed pagination, 429s, robots denials and unsupported
schemas remain disabled candidates with reasons in config/business-sources.json.
They are not represented as successful full-company coverage.

## Five-minute operation

Both workers target five minutes after deployment. The main worker publishes
atomic private full-collection snapshots for 139 shared sources; the member
worker reads exact matching definitions, with a maximum age of ten minutes.
Missing, stale, corrupt or incompatible copies are source failures, never empty
successes or job-closure evidence. Source health retains the actual upstream
collection time, distinguishing cache reads from new provider requests. HTTP
pacing and the shared collection lock still apply. Five-minute scheduling does
not guarantee five-minute end-to-end delivery or upstream publication speed.
Slow/restricted Workday and iCIMS boards retain a 30-minute per-source cadence;
public feed and shared-board ingestion targets five minutes. No overlapping runs
or additional cloud resources are introduced.

The member worker accepts explicit new-grad/entry-level evidence, curated
new-grad feed provenance and candidate graduation-cohort requirements. Generic
analyst/consultant titles do not by themselves establish new-grad eligibility.
Senior roles and explicit requirements for at least three years are rejected.
Required masters/PhD/MBA roles are excluded; bachelor-or-master alternatives and
optional/preferred graduate degrees remain eligible. Employer responsibilities
and title evidence distinguish the four new business families; technical PM
uses the existing PM routes. Exact identities and delivery receipts are retained.

The supervisor separately inspects member storage, completed runs, queued
notifications and prolonged quiet new-grad intake. Seven quiet days triggers a
single review warning, not a claim that jobs must exist. A stale member worker
is critical even if the personal scraper is still healthy. Existing independent
Healthchecks email monitoring remains active.

## Initial expansion deployment and acceptance

Local and Azure staged tests: 451 passed and 136 subtests; seven deployment backup tests passed.
Fresh consistent personal, maintenance and member snapshots were verified off
Azure using compressed/raw SHA-256, integrity and table counts before cutover.
The added sources initially import silently. Existing delivery keys and receipts
remain intact. New category destinations remain queued until configured.

The source-cache startup race exposed a daemon defect: an overlap skipped the
producer for an entire five-minute interval. It now retries the same lock after
15 seconds. This neither permits overlapping collection nor increases successful
provider polling frequency. Member policy revisions also reclassify stored jobs,
including jobs omitted by an unavailable source; identity, baseline flags,
posting-check evidence and delivery receipts remain unchanged.

Production collected 149/152 sources successfully across the rollout. Capital
One, Morgan Stanley and Truist Workday routes remain restricted, with their
existing failure history retained. They receive no access-policy bypass. Six
Workday/iCIMS sources have 30-minute per-source cadence; a deferred poll is
identified separately from a successful upstream collection. See the dated
[per-company matrix](BUSINESS_COVERAGE_MATRIX.md): 39 targets have configured
direct routes and 37 are responding; others retain incomplete public-feed routes.

The actual new-grad path delivered IMC Trading's Quant Performance Engineer to
new-grad-quant at 08:18:10 UTC on November 26 (receipt 1575425419845304441).
This proves real qualifying-job delivery, not the employer's original posting
date. A separate labeled test introduced an existing Notion new-grad posting into
a disposable database after empty-source initialization, performed live posting
validation in 2.83 seconds, retained a controlled failed delivery, then delivered
the retry to new-grad-swe (receipt 1575422573569908756). A third drain sent nothing;
Discord message lookups verified both destination channel IDs. Application access
for that Notion test remained unverified. Production records were not reseeded.

Code commit ddb86b70d63ecee3c3354d4cd8732f7bc00e8f5e passed
[GitHub CI](https://github.com/andymaoo/internship-watch/actions/runs/45782593249).
At initial expansion acceptance, all 27 runtime modules on both releases matched
that commit. Those releases were business-personal-0d60489082db and
business-member-0d60489082db, superseded by the combined-route releases above;
the personal service, member timer and maintenance timer are enabled after reboot.
Secrets remain root-owned mode 0600. Rollback configuration is privately saved in
/root/business-20261126-072828-cutover-779b094a; previous release symlinks remain
available. Rollback changes code/configuration only, never restores an older DB.

Final release scheduled acceptance (November 26 UTC):

| Worker/run | Actual collection start | Completion | Result |
| --- | --- | --- | --- |
| Personal 18283 | 08:23:31 | 08:27:08 | Completed/degraded: 165/213 sources succeeded; 48 pre-existing source access/schema failures remain |
| Member 770 | 08:27:11 | 08:27:55 | OK: 146 successful collections, six explicitly deferred sources; 25 link checks |
| Personal 18284 | 08:28:31 | 08:32:28 | Completed/degraded: 165/213 sources succeeded; existing failures remain |
| Member 771 | 08:32:29 | 08:33:15 | OK: 146 successful collections, six deferred sources; 34 link checks |

Member processing took approximately 46 seconds per run; timer service lifetimes
also include waiting for the shared lock. Actual member starts were 318 seconds
apart, so five minutes is a target rather than an exact delivery guarantee.
No completed worker runs overlapped. Member validation due fell from 2,799 to
2,767 across the final two runs; the imported backlog is still large and this
short window does not establish long-term queue stability. New discoveries
retain their separate validation priority. No production notification failures
were pending. The independent supervisor completed at 08:30:36 and successfully
inspected the new member monitor. General existing source/coverage, validation
and off-host-bucket incidents were not declared resolved by this rollout.

At 08:33:41, the member DB contained 3,046 jobs with all 60 delivered production
outbox records retained, including pre-rollout history. The personal DB retained
6,536 jobs and 3,774 delivered records. Twenty-eight graduate-required jobs were
excluded; zero included jobs had graduate_degree_required=true. Ninety qualifying
new-grad employer postings were verified open, 1,040 were unverified and three
were closed. These are stored listing statuses, not employer posting recency.
One grouped backlog message went to private watch-digest at 08:33:46 (receipt
1575429345537691719); Discord lookup confirmed the channel and a duplicate drain
sent nothing. Baseline imports were not replayed individually.

Private evidence is work/maintenance/business-funnel: backup-verified.json,
stage.txt, pipeline-check.json, receipt-verified.json, production-acceptance.json,
final-invariants.json, cutover.json and runtime-match.json. These include private
operational data and are deliberately excluded from Git. Updated local report:
outputs/business-funnel/report/jobs.html, with CSV and coverage/link evidence.
The recurring cloud backup bucket is still unconfigured; today's verified
off-VM deployment copies do not constitute an automated off-host backup service.

## Operating the expansion

The authoritative configuration remains /etc/internship-watch.json and
/etc/internship-watch-member.json. build_funnel in internship_watch/member_funnel.py
constructs candidate configurations from the existing registry, enabled additions
and target catalog. Review/stage those candidates before replacing live files.
Adding a catalog name alone does not implement an employer collector. For each
new direct route, verify the official destination and access rules, exercise
complete pagination, add adapter regression fixtures, run local and actual-host
checks, then observe consecutive scheduled collections and its Discord route.
Record blocked/partial coverage explicitly. Keep new-source initial import silent.

See [Discord setup](DISCORD_BUSINESS_SETUP.md) for the four missing webhook keys.
The private updated member report is /var/lib/internship-watch-member/export/jobs.html,
with jobs.csv, link-validation.json, sources.json and coverage.html beside it.
Copy exports over SSH or bind a temporary report server to 127.0.0.1 and tunnel it
as described in DEPLOYMENT.md, substituting the member export directory. Downloaded
local HTML files are snapshots; refreshing a local file does not fetch Azure.

After a reviewed code/config update, restart internship-watch.service; the next
member timer invocation reads the active member release/configuration. To stop
both collection workers, stop internship-watch-member.timer,
internship-watch-member.service and internship-watch.service. Independent
maintenance/Healthchecks may alert about the intentional stop. Do not delete
SQLite files, clear the outbox or reset initial baselines.

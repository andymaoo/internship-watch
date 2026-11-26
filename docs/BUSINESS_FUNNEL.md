# Business funnel implementation and coverage limits

## Scope and selection

The target catalog contains five lists of 50 employer names and 161 unique names
across technology consulting, strategy consulting, technical product management,
product strategy and business analysis. These are curated research/watch targets,
not a defensible universal ranking of the best 50 firms. Vault's published survey
methodology informed consulting selection; technical PM/product/analyst lists are
editorial targets, not a Vault ranking. See BUSINESS_EMPLOYER_TARGETS.md and
config/business-employer-targets.json for every name and overlap.

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

## Deployment and acceptance

Local tests: 449 passed and 136 subtests; seven deployment backup tests passed.
Fresh consistent personal, maintenance and member snapshots were verified off
Azure using compressed/raw SHA-256, integrity and table counts before cutover.
Actual staging/production timings, coverage counts and receipts follow after
acceptance. Newly imported backlog is grouped rather than replayed as individual
new-job alerts. New category destinations remain queued until configured.

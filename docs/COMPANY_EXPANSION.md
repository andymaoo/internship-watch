# Requested company expansion â€” 2026-09-19

The requested list contains 50 companies. Configuration now explicitly tracks all
50, with 47 enabled direct discovery integrations plus the unrestricted Simplify public
internship feed. Google, Meta and Uber remain **incomplete public-feed discovery**;
these are not represented as successful complete direct integrations.

## Simplify timing and notifications

The existing feed is still `SimplifyJobs/Summer2027-Internships`, branch `dev`,
`.github/scripts/listings.json`. No company allowlist is applied. Five-minute
polling discovers active, visible new records that satisfy the configured US,
role and junior/bachelor eligibility filters. The public repository is a subset
of Simplify's website. Its [maintainer guide](https://github.com/SimplifyJobs/Summer2027-Internships/blob/dev/CONTRIBUTING.md#maintainer-guide)
describes daily database exports plus reviewed community submissions. A website
posting can therefore precede the public feed by much more than five minutes.
Internal Simplify crawling schedules and completeness are unknown.

Verified qualifying new jobs enter the durable immediate Discord outbox after a
cycle's validation. The separate awaiting-verification digest is now eligible
every 300 seconds, previously 900. Duplicate receipts remain separate from
discovery records. Newly enabled boards receive a silent initial baseline, so
adding these companies does not replay every existing job. Their backlog is
browsable in the report. Subsequent new identifiers use the normal alerts.

## New direct integrations

| Companies | Integration | Discovery scope |
|---|---|---|
| Airtable, Affirm, Dropbox, Brex, Waymo, Asana, Chime, Anduril Industries, DoorDash, Datadog | Greenhouse public Job Board API | Complete returned employer board, with declared-total checks |
| Cerebras Systems, Confluent | Ashby public posting API | Complete listed board; their former Greenhouse/Jobvite URLs are obsolete |
| LinkedIn | SmartRecruiters public Posting API | All public employer postings; complete offset pagination |
| NVIDIA | Public Eightfold career-site search | Union of structured internship job type and `intern` keyword; all pages of both searches |
| Microsoft | Public Eightfold career-site search | Structured `employment_type=internship`; all pages. The broad keyword search produced overlapping pages and is not enabled |
| Netflix | Public Eightfold legacy search | `intern`, `fellow`, `residency`; all pages, deduplicated across queries |
| Snap | Public careers JSON | Complete response used by its job-list UI, including structured employment type |
| Uber | Public careers search (disabled on Azure) | 531 jobs collected locally with complete pagination; Azure returns a Cloudflare access challenge. Simplify public-feed discovery remains incomplete |
| Amazon | Public job search JSON | `intern`, `co-op`, `fellowship`, `residency`, `student`; all pages and qualifications |
| Rippling | Public careers Algolia index | All search objects; exact job IDs merge only location variants |
| Bloomberg | Public Avature search pages | Follow every advertised next-page link; check raw row total; deduplicate repeated exact requisition IDs |
| ByteDance | Public supplier search used by its careers UI | `intern` search, complete count-checked pagination; current response fits in one 1,000-record request |

Employer search APIs without formal public documentation are schema-sensitive.
Robots policy, timeouts, bounded retries, host pacing and cooldowns apply. No
accounts, candidate data, private APIs, CAPTCHA bypass or application submission
are used. Rippling's API key is the **public search-only key shipped in its
website JavaScript**, scoped here to its public careers index; it is not an
operator credential or admin key.

Structured internship/keyword scopes can miss an unusually named research
program. Full-board integrations also depend on employers listing opportunities
publicly on that board. No configuration can guarantee every future posting or
permanent compatibility with a third party.

Bloomberg currently repeats some requisitions between advertised pages. The
adapter records both raw rows and unique jobs, rejects conflicting identities,
repeated entire pages and incomplete raw totals. The changing search index is
not an atomic snapshot; repeated five-minute scans reduce, but cannot eliminate,
transient omissions caused by upstream reordering.

The actual-host staging gate caught Uber's HTTP 403 response with
`Cf-Mitigated: challenge`; a locally successful adapter is not treated as a
working deployment. Its adapter is retained but disabled. No alternate IP,
proxy, challenge solving or hidden endpoint bypass is used. Uber's
[official careers search](https://jobs.uber.com/en/jobs/?team=all) offers email
job alerts as a permitted supplement. That separate subscription is not yet
configured. There are **74 enabled integrations** after this host-specific
restriction, including 21 newly enabled integrations.

## Correctness changes

* A verified Anduril Warhead Engineer Co-op false positive came from AI company
  boilerplate. Role-heading scoping and physical-role evidence now exclude that
  position, while retaining software/AI internships at the same employer.
  Regression tests reproduced the failure before the fix. The same checks caught
  an Amazon industrial-layout co-op, engineering roles mentioning PM colleagues,
  a regular ByteDance graduate role with copied internship text, and explicit
  PhD/MBA titles containing a mention of a prior bachelor's degree. These no
  longer pass the configured filters; uncertain mixed-duty roles need review.
* A live Snap detail check exposed typographic apostrophes in duty headings
  being rejected as missing descriptions. Apostrophe normalization fixes this
  while retaining exact job identity and substantive-description requirements.
* Employer posting validity is independent of application access. Exact public
  SmartRecruiters, NVIDIA/Microsoft Eightfold and Snap details can verify a
  posting only after checking employer namespace, job ID, title, canonical URL
  and meaningful description. A blocked application stays unverified.
* Exact URL aliases cover SmartRecruiters title slugs, Amazon hostname variants,
  old/new ByteDance destinations, and Snap's Workday destinations. NVIDIA's
  observed ATS requisition can match its original Workday URL. A one-time alias
  migration preserves existing job IDs, first-seen times, baseline flags and
  delivery receipts; conflicting existing records are not destructively merged.
* Repeated Simplify/employer URL aliases no longer alternate the saved destination
  and erase completed checks each poll. Direct employer evidence remains preferred
  for known exact aliases; raw feed history is retained, and changed role identities
  or unknown destinations still invalidate validation. A regression test reproduces
  the NVIDIA Workday/Eightfold case across repeated source polls. Live repeated
  checks also identified the reviewed display-name pairs Anduril/Anduril Industries,
  Together/Together AI and Scale/Scale AI. These no longer invalidate one another
  at the same exact requisition; unrelated employer changes still do.
* Three bounded collection workers use separate HTTP sessions with shared host
  pacing/cooldowns. At most three boards wait in memory, and SQLite writes remain
  on one thread. Source calls have a 180-second deadline. The existing run lock
  still prevents overlapping whole runs.

## Inspection and operations

The private report now links `coverage.html` and `coverage.json`. These list all
50 companies, actual source last-success times, stored match counts and coverage
limits. Zero qualifying internships is not confused with a broken board.
`sources.json` remains the complete source-health export; `jobs.csv` remains the
CSV export. The deployed configuration retains five-minute polling and all
previous eligibility filters.

Actual-host acceptance evidence is recorded separately in
`COMPANY_EXPANSION_ACCEPTANCE.md` after scheduled runs. Source fixtures and live
checks cannot guarantee that an employer will keep its API unchanged. The
existing operational alerts and independent Healthchecks monitor cover failures.
Automatic off-host backups still require the previously requested backup
account/bucket credentials; this expansion does not claim to have completed that
separate prerequisite.

API references: [Greenhouse](https://developers.greenhouse.io/job-board.html),
[Ashby](https://developers.ashbyhq.com/docs/public-job-posting-api),
[SmartRecruiters](https://developers.smartrecruiters.com/docs/endpoints),
[Algolia public search](https://www.algolia.com/doc/rest-api/search/search-single-index).

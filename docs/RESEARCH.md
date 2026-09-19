# Public-source research and deployment recommendation

Research date: 2026-09-18 America/Los_Angeles (2026-09-19 UTC). Original project reviewed at `2a776814a993fd74e92cc91aa15e90fb0f99424a`. Public pages and feeds change; counts below are observations, not coverage guarantees. This document recommends an approach; deployment and runtime evidence belong in the operating/validation reports.

## Simplify integration: preserve and expand it

The original integration already exists at [`scrape.py:179–201` at the reviewed commit](https://github.com/ALNgu1/job-scraper/blob/2a776814a993fd74e92cc91aa15e90fb0f99424a/scrape.py#L179). Its feed URL is the old repository name, `https://raw.githubusercontent.com/SimplifyJobs/Summer2026-Internships/dev/.github/scripts/listings.json`. Adding a second independently notified integration would increase duplicates. Make the existing adapter configurable and retain provenance.

The [old repository web URL](https://github.com/SimplifyJobs/Summer2026-Internships) currently redirects to [SimplifyJobs/Summer2027-Internships](https://github.com/SimplifyJobs/Summer2027-Internships), whose default branch shown by GitHub is `dev`. The canonical feed path remains `.github/scripts/listings.json`. The old raw-content URL was separately fetched successfully: HTTP 200, **no HTTP redirect**, same final URL, response date `Sat, 19 Sep 2026 05:43:48 GMT`. GitHub's repository-page redirect and raw-content alias behavior are different observations.

Captured feed: `work/simplify-feed.json`; HTTP metadata: `work/simplify-feed-meta.json`. SHA-256 of captured decoded file bytes: `b84be2307484485f2f9823616640bacf3e04755fa57fb2b2e6fceeb0e1a57485`. It contains 17,098 objects and 4,435 active, visible objects representing 1,152 distinct employer strings. Feed acquisition artifacts are reproducibility inputs, not validated employer listings.

These research counts describe the earlier captured feed. The final enabled-source refresh at 2026-09-19 06:01–06:02 UTC returned 4,433 active/visible Simplify rows, within 14,673 rows across all 52 enabled sources. The replay of original allowlist/title behavior below uses the earlier 4,435-row snapshot consistently.

A second direct fetch of the [canonical raw URL](https://raw.githubusercontent.com/SimplifyJobs/Summer2027-Internships/dev/.github/scripts/listings.json) produced JSON records equal to the legacy URL. The observed `dev` head was `a37c7e5324a4f59f545ad43c8a17fb523bfb5de9`, dated `2026-09-19T05:31:49Z` (`work/simplify-head.json`). The head and feed were fetched separately, so this records the observed repository revision rather than asserting an atomic commit-pinned feed acquisition.

Observed schema:

| Field | Observed JSON type | Use/limitation |
| --- | --- | --- |
| `id`, `source`, `company_name`, `company_url`, `title`, `url` | string | Source identity, attribution, employer label, destination |
| `active`, `is_visible` | boolean | Source assertions; not independent destination checks |
| `locations`, `terms`, `degrees` | array | Locations, seasons, and degree labels; may be empty or ambiguous |
| `category`, `sponsorship` | string | Source labels; category has both short and full-name variants |
| `date_posted`, `date_updated` | integer | Feed timestamps; do not manufacture employer posting dates |

The [maintainer documentation](https://raw.githubusercontent.com/SimplifyJobs/Summer2027-Internships/dev/CONTRIBUTING.md) defines `date_posted` as when a listing was added and describes daily imports from Simplify's database plus approved community submissions. It asks contributors for US, Canadian, or remote internships using a formal ATS, with exceptions requiring verification. These are intended contribution rules, not proof every row complies. The feed does not include full descriptions or a separately typed application URL, and importing it does not import the full Simplify website.

The [summer README](https://raw.githubusercontent.com/SimplifyJobs/Summer2027-Internships/dev/README.md) advertises SWE, product management, data/AI/ML, quant, and hardware roles, daily list updates, and hourly monitoring of company career pages. It links both an off-season view and a Summer 2026 archive. The [off-season view](https://raw.githubusercontent.com/SimplifyJobs/Summer2027-Internships/dev/README-Off-Season.md) targets Fall 2026, Winter 2027, and Spring 2027, including co-ops. **One underlying JSON feed serves multiple seasons**; the repository name is not a season filter.

The captured active-visible feed includes 2,073 entries tagged Summer 2027, 554 Fall 2026, 476 Winter 2027, and 272 Spring 2027. Counts overlap because terms are arrays. It also includes 529 Summer 2026 entries, 238 `N/A` terms, and anomalous older years. Retain explicit term evidence and quarantine ambiguous dates instead of assuming current eligibility.

The public [constants](https://raw.githubusercontent.com/SimplifyJobs/Summer2027-Internships/dev/list_updater/constants.py) define category keys `Software`, `Product`, `AI/ML/Data`, `Quant`, and `Hardware`, and a README company block for `https://simplify.jobs/c/Jerry`. The source [listing filters](https://raw.githubusercontent.com/SimplifyJobs/Summer2027-Internships/dev/list_updater/listings.py) apply visibility/season/date restrictions and include a function that marks entries inactive at two months of age. Therefore neither README absence nor an inactive marker proves an employer has closed the job. Preserve source state separately from independently observed link state.

The original scraper imposes its own 30-name allowlist, then title filtering. Replaying those filters on the captured feed reduces 4,435 active-visible objects to 572 after company filtering, then 520 across 21 employer strings. The 520 include 116 source-categorized hardware roles and zero source-categorized quant roles. Microsoft is absent from the allowlist despite the comment describing “MSFT+” coverage. Removing this repository-specific restriction materially expands discovery; it does not remove the feed's upstream curation limits.

## Comparison with publicly observable Simplify

| Dimension | Original repository | Simplify public evidence and unknowns |
| --- | --- | --- |
| Sources | Hard-coded Greenhouse, Ashby, Lever boards; custom Apple/Google/Meta; restricted public Simplify feed | Homepage says 50+ boards and company career pages; public internship list also accepts community submissions. Exact employer universe, API agreements, crawler inventory, and private importer implementation are unknown. |
| Coverage | 50 configured source entries, one disabled; broad engineering keyword matches; quant/data-analysis coverage accidental | Website spans many job families and experience levels. Public internship feed is a curated subset and intentionally includes hardware. Neither system demonstrates complete market coverage. |
| Freshness | Own configured polling can discover direct-board changes, but comment claiming 1–2 hour feed lag is unsupported | Homepage mentions hourly additions and daily indexing; list README mentions hourly employer monitoring while contributor docs describe daily export. These describe different stages and are not end-to-end SLAs. |
| Filtering | Title-only inclusion; unconditional `manager` exclusion drops PM internships; no geography or eligibility controls | Public search exposes location, job type, experience, and category. Help describes remote preferences, salary/company refinement, saved searches, recency sorting, and applied-job hiding. Exact classifier/ranker internals are unknown. |
| Deduplication | Source-prefixed IDs; company exclusions try to avoid overlap; no cross-source identity model | Public updater checks duplicate URLs/IDs. Captured JSON has zero exact duplicate URLs or IDs. Website semantic deduplication and cross-board identity logic are unknown. |
| Link quality | Saves source URL without fetching description/application destination | Public rows expose employer application links and sometimes separate Simplify details. Active flags and curation help, but do not prove current destination, job identity, or absence of redirects. Website revalidation policy/error rates are unknown. |

Sources for website-specific observations: [Simplify homepage](https://simplify.jobs/), [public search controls](https://simplify.jobs/jobs), [search/filter help](https://help.simplify.jobs/articles/8339467-searching-and-filtering-jobs-on-simplify), and [public duplicate validation implementation](https://raw.githubusercontent.com/SimplifyJobs/Summer2027-Internships/dev/list_updater/analytics.py). Marketing descriptions are attributed claims, not independently measured service levels. No private API, authenticated account, or undisclosed infrastructure was inspected.

## Architecture and operating recommendation

Extend the working Python adapters. Their public ATS interfaces are useful; replacing the whole collector with browser automation would add failure modes and maintenance. Move orchestration/state to a small package with configuration, normalized records, conservative classification, a persistent SQLite database, link evidence, and a separate notification outbox. Keep brittle employer adapters isolated and report their health independently. Feed objects lacking descriptions need employer-page enrichment and explicit unverified outcomes.

Use one always-on Linux instance with a systemd service/timer (or one container with a persistent disk), one database writer, and process/run locking. Persist the database outside the checkout/image. Take SQLite-consistent backups to another location and test restoring them. A rebuild must not replace the persistent data directory. A local HTML/CSV export is sufficient to inspect jobs initially; SSH forwarding can expose a private read-only viewer without adding public authentication infrastructure.

Do not rely on committing `seen.json` back into Git for production storage. Git history cannot atomically commit discovery plus a delivery outbox, and source outages must not erase state. Import its known IDs as legacy discovery/suppression evidence; their presence cannot prove successful notification because the original sender does not check response status.

Start with one documented ATS board through collection, classification, storage, link checking, and retryable delivery. Then add the existing ATS registry and unrestricted Simplify feed; expand direct employers where observed coverage gaps justify upkeep. Test custom APIs before enabling them. Do not treat a disabled or failing source as covered.

## Hosting cost and heartbeat

Recommended planning budget: **about US$6–10/month**, subject to the user's host and paid notification preferences. DigitalOcean lists a 1 GiB/1-vCPU instance with 25 GiB SSD at $6/month; weekly provider backups at 20% bring that example to $7.20/month before taxes and extra services. A $4/512 MiB option exists, but 1 GiB leaves more margin for parsing, operating-system updates, and SQLite. These are current posted prices, not a purchase authorization or a benchmark of this workload. [DigitalOcean pricing](https://www.digitalocean.com/pricing/droplets)

An already-owned always-on server can avoid incremental compute cost if it has enough resources. A managed worker plus persistent disk is another option; verify the current combined bill before choosing it. Render's disk documentation confirms ephemeral default storage and requires placing persistent files on an attached disk. [Render persistent disks](https://render.com/docs/disks)

GitHub Actions remains useful for CI, but its scheduler is a poor primary reliability foundation here: schedules can be delayed or dropped under load, only run on the default branch, and public-repository schedules can disable after 60 days without activity. [GitHub schedule documentation](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)

Use **Healthchecks.io outside the scraper host** as the independent deadman monitor. A successful cycle should ping only after its database commit and health evaluation; signal failures separately, and never run the independent monitor on the same instance. Healthchecks supports start/success/failure signals, period/grace configuration, and external notification integrations. Keep ping URLs secret. [Healthchecks documentation](https://healthchecks.io/docs/)

Its Hobbyist plan currently costs $0/month for 20 checks and retains 100 log entries per check, enough for the checks needed here but only a short history at frequent polling. Persist detailed history locally. [Healthchecks pricing](https://healthchecks.io/pricing/)

The prepared deployment targets a configurable five-minute interval, with a heartbeat grace period selected from measured worst-case run duration. A five-minute poll means 0–5 minutes of additional detection delay after a source actually exposes a job, plus run time, validation backlog, source cache lag, retries, and notification delay. Feed curation/export can add a day or more; source outages and blocks have no finite discovery bound. Record actual start/end times, missed schedules, source checks, and notification attempts before claiming an operating reliability level.

To validate deployment, collect evidence from multiple scheduled cycles; restart the service and prove the same DB/history survive; deliver a subscribed test notification; cause a controlled source failure and confirm one incident alert; stop heartbeat pings and confirm the external monitor alerts. Restore normal operation and verify recovery. Until these checks and target-host provisioning are complete, the honest status is prepared/tested, not deployed.

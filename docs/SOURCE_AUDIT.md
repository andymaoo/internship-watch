# Source audit and maintenance

Reviewed original commit: `2a776814a993fd74e92cc91aa15e90fb0f99424a`. Live checks occurred on 2026-09-19 UTC (September 18 Pacific). Original source references below refer to that commit, not an invented upstream revision.

## Confirmed original defects and limitations

| Location at reviewed commit | Evidence and impact | Resolution |
| --- | --- | --- |
| `scrape.py:131â€“177` | Greenhouse requests omit `content=true`; all three structured adapters discard descriptions, locations, employment metadata and dates. Classification cannot inspect responsibilities or eligibility. | Structured fields retained by `internship_watch/sources.py`; Greenhouse requests full content. |
| `scrape.py:137`, `scrape.py:169` | Missing `jobs` keys become an empty successful collection through `.get("jobs", [])`. An upstream schema error is indistinguishable from zero jobs. | Strict expected schema and required-field checks raise `SourceError`; Greenhouse reported totals and unexpected pagination are checked. |
| `scrape.py:147â€“160` | Lever has no explicit pagination loop. Its documented API exposes skip/limit; a complete board is not established by this implementation. Actual truncation at every employer was not proven. | Bounded skip/limit pagination, duplicate-page detection, and explicit failure if the end cannot be established. |
| `scrape.py:101â€“103` | Coinbase disabled based on a historical 404. Current public Greenhouse API succeeds. | Restored after live check. |
| `scrape.py:182â€“200` | Simplify is restricted to 30 companies. An empty allowlist excludes every company. It excludes Meta/Google/Apple to avoid duplicates rather than performing cross-source deduplication. | One unrestricted public-feed adapter; optional explicit company filter only. Deduplication belongs in persistent storage. |
| `scrape.py:179`; `CHANGELOG.md` | Hardcoded Summer2026 alias; unsupported 1â€“2-hour freshness claim. | Canonical Summer2027 repository, dev branch and existing feed path verified. Shared raw feed includes different seasons. Public sync code says daily import; no guarantee of upstream discovery delay. |
| `google_scraper.py:220â€“225`, `:228â€“243` | Malformed RPC schema returns `[]`; known description fields are discarded. | Regression reproduced and fixed: error on schema drift; retain description and qualification text. |
| `google_scraper.py:248â€“264`; `apple_scraper.py:114â€“140` | Fixed 10-page cap silently returns partial data. Fixed assumed page size may prematurely terminate. | Regression reproduced and fixed: paginate to empty, reject repeated identities, and raise if configurable safety bound exhausted. |
| `apple_scraper.py:103â€“105` | Missing `res` silently returns `{}` and therefore zero jobs. Priming response not checked. | Regression reproduced and fixed: strict `res.searchResults`, priming HTTP status check. |
| `apple_scraper.py:79â€“81` | United States geography is hardcoded inside the request. | Optional location filters; deployment config explicitly uses USA to match the selected preference. |
| `meta_scraper.py:18â€“20`, `:88â€“90`, `:121â€“147` | Undocumented rotating doc_id and opaque `all_jobs`; no complete-pagination contract. A successful response alone does not establish complete coverage. | Transparent live call succeeded with one record, but direct Meta remains quarantined pending completeness verification. Public feed retains Meta coverage. |

The legacy collector and its title-only predicates remain a historical reference; unattended deployment uses `internship_watch`. Five focused legacy tests failed before the fixes above, then passed. Source/HTTP tests additionally cover pagination, source outages/schema errors, field retention, robots denial, unsafe redirects, bounded retries and not blindly retrying notification POSTs.

## Current source decisions

The repaired configuration enables **53 sources** (the previous measured release had 52). Google and Meta direct discovery remain disabled for the explicit reasons below. [Current repair evidence and deployment boundary](SOURCE_REPAIR.md) supersedes earlier blanket coverage statements; historical collection counts remain dated measurements.

Greenhouse, Lever and Ashby remain the primary foundation. Their documented public feeds avoid browser-session tokens and expose useful description and employment fields. This extends the working design without introducing a browser farm. All original working standard integrations are retained; Vercel and Mistral required verified ATS migrations.

- **Vercel:** old Ashby feed returned zero while the employer careers page listed jobs, including Summer/Winter 2027 internships. Greenhouse `vercel` returned 84 records. This is a verified silent coverage defect, repaired in config.
- **Mistral AI:** old Lever `mistral` returned zero. Its official careers page now links `jobs.ashbyhq.com/mistral.ai`; that documented Ashby feed returned 199 records. Config migrated accordingly.
- **Quant expansion:** Jane Street `janestreet`, DV Trading `dvtrading`, Virtu `virtu`, and DRW `drweng` public Greenhouse boards verified. This adds trading, quant research and quant/software-development coverage; classification still rejects hardware and permanent positions.
- **Apple:** retained and repaired. Transparent requests respecting robots retrieved 57 entries and reached an empty page. The adapter shares the central HTTP client and configurable USA filter, stores public search records as evidence, and relies on destination verification for descriptions absent from search results. Its API remains undocumented and monitored.
- **Google (rechecked September 19):** the original blanket denial was partly a confirmed robots-parser defect, now repaired with RFC-aware matching. Permitted individual job pages can be verified and enriched from their exact public detail records. Complete direct discovery remains disabled: 31 US internship results exceed the first page of 20, and published policy disallows pagination. No restricted RPC or pagination workaround is used. See [SOURCE_REPAIR.md](SOURCE_REPAIR.md).
- **Meta (rechecked September 19):** direct collection remains disabled because the current policy requires express written permission. Public search is a JavaScript shell and the old GraphQL probe never established completeness. Both Meta Careers hostnames are explicitly restricted for automated requests, including future feed-driven link checks. The Simplify recheck contained 45 inactive Meta records and zero active ones; there is no current active Meta coverage to claim.
- **Hudson River Trading (repaired September 19):** the official careers frontend explicitly embeds Greenhouse board `wehrtyou`. Its documented public API returned all 83 reported jobs, with three passing the configured internship/US filters. All three employer postings validated; their JavaScript application access remains unverified. Multi-select employment metadata is normalized before SQLite insertion while original evidence is preserved. Existing feed identities merge without duplicate jobs. The old source ID is retained and its board slug corrected.

The initial complete live check succeeded for **52 of 52 enabled sources**, yielding **14,674 raw source rows** before classification and cross-source deduplication. The final fresh collection with pinned dependencies, at **2026-09-19 06:01â€“06:02 UTC**, again succeeded for **52 of 52**, yielding **14,673 rows** as upstream records changed. Three direct sources remain disabled with their reasons. Palantir's Lever pagination was rechecked through an explicit empty terminal page after the final adapter revision. Apple source records preserve its available search summary, location and employer `postDateInGMT`; the summary is labeled and is not treated as a verified full destination description.

Every enabled source has an `expect_nonempty` configuration flag based on a nonempty successful board check. This means zero **raw board jobs**, not zero internships after eligibility filters. A company may legitimately have no in-scope internships. Persistent source failure and unexpected board emptiness must be reported separately by the runner.

## Feed and field semantics

The existing Simplify integration was updated, not duplicated. Canonical feed:

`https://raw.githubusercontent.com/SimplifyJobs/Summer2027-Internships/dev/.github/scripts/listings.json`

The old repository's browser URL redirects to the new season. Its old raw-content URL still returned HTTP 200 without an HTTP redirect in this check. The raw feed is shared by summer, off-season and archival views. Filtering only the README's season would miss entries in the other views. The adapter preserves each record's `terms`, category, sponsorship, degree metadata, visible/active markers and upstream source.

Simplify `date_posted` means **added to the feed**, not an employer posting date. It is stored as `evidence.source_added_at`; `posting_date` stays empty. Likewise Greenhouse `updated_at` and Lever `createdAt` are retained as source metadata without asserting employer publication. Ashby `publishedAt` is documented as last publication and is labeled `posting_date_kind=last_published`.

The feed's `active=false` can result from age-based staleness rules and does not independently prove employer closure. The adapter collects active, visible entries, and the runner must not mark jobs closed merely because they disappear from this source. Employer destinations provide separate closure evidence.

The first full feed snapshot contained 17,098 records, 4,435 active/visible records from 1,152 employers. The final source refresh returned 4,433 active/visible Simplify records. Every active record lacked a full description in this feed. These numbers are dated snapshots, not market coverage. Direct ATS descriptions and link checks add evidence but blocked destinations remain unverified. See `RESEARCH.md` for fuller public-product comparison and unknown internals.

## HTTP and operational behavior

`HttpClient` centrally configures connect/read timeout, bounded GET retries, per-host pacing, redirect limits and a transparent user agent. An HTTP 429 immediately defers the host for the full Retry-After delay, including values above the per-request retry budget; absent or malformed delays default to 60 seconds. Later jobs, sources and robots checks on that host are held as unverified, while other hosts can proceed. The client exposes a JSON-safe cooldown snapshot for the runner to persist across restarts. Separate audit-worker sessions share these host maps and their lock. Three consecutive HTTP 403 responses open a configurable 300-second host circuit breaker; successful responses and individual-job 404s reset the counter. Set `http.forbidden_threshold` to zero to disable only this optional 403 circuit.

Webpage checks enforce robots policy, including crawl delay/request rate, at each redirect destination. A robots access failure is unverified, not a closed job. API collection uses documented public endpoints. The repaired Apple search is a read-only POST explicitly eligible for retry; delivery POSTs are not implicitly retried by the HTTP transport.

The runner can set an absolute monotonic `HttpClient.deadline` during a validation batch. Requests and retry/pacing waits check it, and connection/read timeout settings shrink to the remaining budget. This is a cooperative bound, not process cancellation: DNS resolution and pathological slowly streamed responses can still overrun a target interval. Normal five-minute scheduling is achievable only while collection and bounded validation finish in that interval; outages and source publication lag prevent a strict discovery-time guarantee.

Unsafe schemes, credentials embedded in URLs, private/local IP destinations, nonstandard ports and HTTPS-to-HTTP redirect downgrades are rejected. These checks are defense in depth for public feed URLs, not a promise against every DNS rebinding attack; deployment should retain outbound network restrictions where practical.

To add a company, add a source object in `config.example.json` with a unique id, a supported adapter type, employer label and verified ATS slug. Use `region: "eu"` for European Lever hosting when the employer's own board uses it. To add another Simplify seasonal feed, first verify whether it is already the same shared raw feed; do not create duplicate collectors. Keep an inaccessible source disabled with its reason and a documented fallback. Do not treat a 200 response or zero-row JSON as proof of a correct employer slug.

## Evidence and limits

Reproduce the complete source audit using the checked-in script (from the repository root):

```sh
python scripts/check_sources.py --config config.json --output data/source-audit
```

The command checks every enabled source with the configured HTTP policies, records every disabled source and its reason, and sends no notifications. It writes `source-live.json` (source counts, errors and timestamps), `source-jobs.json` (raw normalized records for the separate link audit), and `summary.json` (run completion and totals). Each report is replaced atomically and checkpointed between sources. Exit code 1 indicates a failed check or unexpectedly empty board. An interrupted audit has `completed: false`; a successful script exit does not assert link quality or market completeness. Output paths can be absolute, so the command can also run from another working directory.

Then reproduce destination checks and rebuild the report from its resumable checkpoint:

```sh
python scripts/check_links.py --config config.json --input data/source-audit/source-jobs.json --output data/link-audit/checks.jsonl --report data/link-audit/report.json --workers 6 --refresh-open
python scripts/check_links.py --config config.json --input data/source-audit/source-jobs.json --output data/link-audit/checks.jsonl --report data/link-audit/report.json --summary-only
```

The second command performs no network checks. The first checks new candidates and refreshes previously open results recorded before validator version 3; current-version checkpoint results are retained. Use a new output filename for a completely fresh live audit. Worker count must be 1â€“12. All classification and HTTP settings come from the supplied config. Separate worker sessions share per-host pacing, robots policies, cooldowns and consecutive-forbidden counters. Rate-limit state is saved beside the checkpoint as `checks.rate-limits.json` and restored on resume.

Link classifications and their summary are written beside the checkpoint; the final report and `report.summary.json` use the requested report location. Grouping follows the storage identity rules: exact description destinations and known ATS requisitions can match, shared unknown application pages cannot, and conflicting known requisitions remain separate. An old open result without validator version 3 is reported as requiring current verification, not as open. Checkpoint source records that are no longer candidates remain identifiable in the report. These audit scripts do not send alerts, mutate the production database or establish deployment acceptance.

The selected configuration covers US jobs, including remote jobs explicitly eligible in the US; all seasons; co-ops; bachelor's-level junior students; and relevant research programs. It has no company allowlist. Unstated eligibility is recorded and allowed by configuration, while explicit incompatible degree/student-year requirements are filtered. Empty graduation-year and season lists mean no restriction on those fields, not a guessed graduation date. Anthropic's direct Greenhouse board is included; actual research-program eligibility still depends on each listing's evidence.

The original audit's temporary snapshots are under `work/` and excluded from version control; normal reproducible output defaults to `data/source-audit/`, also excluded. The delivered report includes per-source counts, check timestamps, disabled reasons and unresolved destination checks. Live checks establish behavior from this environment at this time; they do not guarantee future uptime, authentication behavior, source completeness, or employer posting-to-feed latency.

Primary documentation and employer evidence:

- [Greenhouse Job Board API](https://docs.greenhouse.io/job-board.html)
- [Lever official postings API](https://github.com/lever/postings-api)
- [Ashby public job-posting API](https://developers.ashbyhq.com/docs/public-job-posting-api)
- [Vercel careers](https://vercel.com/careers)
- [Mistral careers](https://mistral.ai/careers/)
- [DV Trading public board](https://job-boards.greenhouse.io/dvtrading)
- [Virtu public board](https://job-boards.greenhouse.io/virtu)
- [DRW public board](https://job-boards.greenhouse.io/drweng)
- [HRT careers](https://www.hudsonrivertrading.com/careers/)
- [Simplify internship repository](https://github.com/SimplifyJobs/Summer2027-Internships)

No inference about Simplify's private discovery, crawler refresh, deduplication or verification implementation is made from its public list alone.

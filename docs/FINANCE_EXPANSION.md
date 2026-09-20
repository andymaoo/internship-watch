# Finance and quant expansion

Reviewed from deployment `690b0209075ac35cafa2067bcf18329eb56bf467`. This request adds 108 named finance/quant employers to the coverage audit. Six already had working direct sources and are retained; DRW also gets its separate university board. The resulting configuration has **212 enabled sources and 212 company labels**, including **89 of these 108 employers with a live-tested direct route** and **19 with incomplete public-feed-only discovery**. Company labels are not source counts. A live directory response does not imply there is a qualifying opening today or guarantee every future opening.

The 210-source release was activated on Azure with its original records and receipts preserved. The additional UBS and Société Générale routes are locally tested; final 212-source scheduled production acceptance is recorded separately below after cutover. No extra server, paid service, account or subscription is created.

## What is collected

Greenhouse, Lever and Ashby public APIs remain the preferred routes. New Workday boards use observed tenant/site names, complete declared-result pagination, current internship/student/co-op facets when available, and US country facets when available. Supplementary keyword searches are explicitly configured; unusually categorized programs may be missed. BMO's worker-type facet is named `company`, CCI declares the tenant `osv_cci` on the host `osv-cci`, and Workday site-name capitalization matters.

Direct custom sources cover D. E. Shaw's public job arrays, Bank of America's US campus Tal.net board, Trexquant's public job API, Group One's employer-linked ApplicantPro listings, GTS/MSCI public iCIMS directories, PanAgora's public listings, Two Sigma's complete current Avature directory, Macquarie's campus directory, Moody's Students & Early Careers category Renaissance's public directory, and UBS's complete public student/graduate BrassRing directory (US-filtered after pagination), and Société Générale's public Quantum search with full US pagination and exact employer JobPosting details. Internal, confidential, targeted/private and invitation-only boards are excluded. New full-time rows never become internships merely because they occur on a campus page.

Optiver's current public application embeds identify `optiverus`; that board returned 161 global postings. The old `optiver` board was empty and is not enabled. IMC and Man Group use European Greenhouse posting hosts served by the global public Greenhouse API. Point72 includes Cubist. DV's existing board includes DV Equities and DV Commodities. Walleye's official student board and campus FAQ include Quantic. These parent/affiliate scopes do not guarantee every subsidiary vacancy.

The existing public Simplify source remains unrestricted by company: `SimplifyJobs/Summer2027-Internships`, `dev`, `.github/scripts/listings.json`. Matching new records are checked on each poll and pass through the same persistent notification queue. This is the public repository feed, not Simplify's complete website. Five-minute polling cannot eliminate upstream export or maintainer delays, and initial imported records are not newly posted jobs.

## Verified repairs and safeguards

- `internship_watch/http.py`: per-host pacing now sleeps under a per-host lock, preserving same-host limits without blocking independent hosts. A deterministic regression test reproduces the previous global-lock stall.
- `internship_watch/classify.py`: accepts Bachelors/Masters spellings and does not interpret MS Office as a master's degree. Akuna's mixed undergraduate/graduate eligibility was otherwise misclassified. AQR summer-analyst roles require specifically linked internship-program evidence; an unrelated footer is insufficient.
- `internship_watch/platform_sources.py`: current Workday detail titles are authoritative only after exact tenant/site/posting-instance/requisition verification. This handles stale search titles, including observed PIMCO rows, without accepting another position.
- `internship_watch/links.py`: European Greenhouse links use the verified public API; posting-response cache is bounded to 64 entries and five minutes instead of retaining every response for the life of the daemon. Memory is measured again on the host.
- `internship_watch/storage.py`: exact finance/Tal.net/Workable/Avature/ApplicantPro identifiers and European Greenhouse aliases migrate conservatively. Random Tal.net navigation tokens and repeated identical AQR `gh_jid` parameters do not create new jobs. Different board IDs, posting instances and CTC campus requisitions remain distinct, even with identical titles.
- `internship_watch/finance_sources.py`: Moody's live posting `100482312640` declared requisition **14701**, but its Apply link pointed at **14737**. The observed destination is retained with conflict evidence, cannot become an identity alias, and remains application-unverified. Employer posting validity remains independent. Moody's schema posting date and displayed date can also differ; both pieces of evidence are retained rather than inventing recency.
- `internship_watch/employer_sources.py`: NVIDIA relevance-ranked pages repeated an ID at a page boundary. Explicit `timestamp` ordering returned all 113 distinct declared results, with descending posted timestamps. The adapter verifies that the server honored the configured sort and still fails on duplicate/truncated pages; it never silently accepts 112 of 113.

UBS uses the public search interface with an anonymous session and CSRF token kept only in memory. It checks every declared page with explicit ordering, detects repeated/missing results, excludes restricted postings, and verifies fresh public details using the exact partner/board/job identity. Employer active status and application accessibility stay separate. Its last-updated timestamp is not represented as an employer posting date.

Source-level deadlines, bounded retries, rate limiting, SQLite locking, notification retry/deduplication, source incident suppression, Healthchecks and report exports remain enabled. Existing source baselines and notification receipts are retained. The first collection of each added board is a baseline import, so it does not generate one alert per historical job. Newly arriving verified matches produce immediate notifications after the run's collection/validation decision; qualifying unverified discoveries appear in a separate digest.

## Incomplete direct routes

These entries remain visible in the company-coverage report. Full access to the user's accounts does not make an employer's blocked or incomplete feed a reliable collection source. Employer job alerts and manual official searches are permitted alternatives; none have been subscribed to or messaged on the user's behalf in this expansion.

| Employer | Observed limitation |
|---|---|
| Balyasny Asset Management | Public Salesforce guest careers page is a JavaScript shell; a complete guest feed has not been verified. |
| BNP Paribas | The official job-search route could not be collected under its robots policy. No access bypass is used. |
| Campbell & Company | Official careers link opens an ADP JavaScript recruitment portal; its complete public collection interface has not been verified. This is the investment firm, not Campbell Soup. |
| Citadel | Official open-opportunities request returned HTTP 403. No challenge bypass is used. |
| Citadel Securities | The official opportunities route could not be collected under its robots policy. |
| Deutsche Bank | Official student information is accessible, but a complete current campus requisition feed has not been verified. |
| Goldman Sachs | The higher.gs.com role directory could not be collected under its robots policy. |
| HAP Capital | The published hap-capital.com home and careers routes returned 404; no current direct job board was verified. This is not evidence that the firm is closed. |
| HSBC | The public careers search API returned HTTP 403; the separate emerging-talent board has not been integrated. |
| Intercontinental Exchange | The reviewed ICE iCIMS directory could not be collected under its robots policy. |
| JPMorgan Chase | The reviewed Oracle candidate-search API could not be collected under its robots policy. |
| Millennium Management | Official careers links to Eightfold; its public search endpoint returned HTTP 403. |
| Nomura | The official campus Tal.net directory returned a human-verification challenge. It is not bypassed. |
| Quantlab | Official careers routes could not be collected under their robots/access policy; no current public ATS feed verified. |
| Seven Eight Capital | The published home and careers routes returned tiny pages with no verifiable job directory; the guessed ATS board did not exist. |
| Susquehanna International Group | The reviewed SIG iCIMS directory could not be collected under its robots policy. |
| TGS Management | The official site could not be collected under its robots/access policy; no current direct ATS route verified. |
| Wells Fargo | Official HTML is accessible, but observed keyword/worker-type query parameters returned unfiltered results; completeness for a bounded internship poll has not been established. The reviewed Workday route could not be collected under its robots policy. |
| Wolverine Trading | Official open-positions page uses a separate JavaScript widget whose asset robots policy could not be verified. Old Lever route returned 404; no current public feed verified. |

Google, Meta, Uber, IBM, Intuit and Tesla retain the separately documented gaps in [the earlier expansion](EXPANSION_100.md). HRT's direct Greenhouse source is working and retained.

## Every requested employer

Counts below are public source rows from individual live probes, before the user's role/location/eligibility filters and before link validation. “Existing” refers to retained source configuration; all enabled sources are rechecked during actual-host acceptance. Zero qualifying internships is not a broken source. A feed-only row is explicitly incomplete and does not claim future employer-direct detection.

| Employer | Direct source IDs / current raw counts | Scope note |
|---|---|---|
| Acadian Asset Management | `greenhouse-acadianassetmanagementllc` (12) |  |
| Akuna Capital | `greenhouse-akunacapital` (40) |  |
| AllianceBernstein | `workday-alliancebernstein-abcampuscareers` (22) | Workday US country facet is used when present, with internship/student/co-op worker types and configured supplementary queries. Unusually categorized programs may be missed. |
| AQR Capital Management | `greenhouse-aqr` (51) |  |
| Aquatic Capital Management | `greenhouse-aquaticcapitalmanagement` (8) |  |
| Arrowstreet Capital | `workday-arrowstreet-capital-campus_careers` (2) | Workday US country facet is used when present, with internship/student/co-op worker types and configured supplementary queries. Unusually categorized programs may be missed. |
| Balyasny Asset Management | **Incomplete: public feed only** | See limitation above. |
| Bank of America | `bankofamerica-campus` (27) | Official campus board, restricted using its current US country facet; technical/research/trading program descriptions are enriched. This is not the full lateral-careers board. |
| Barclays | `workday-barclays-external_career_site_barclays` (92) | Workday US country facet is used when present, with internship/student/co-op worker types and configured supplementary queries. Unusually categorized programs may be missed. |
| Belvedere Trading | `lever-belvederetrading` (17) |  |
| BlackEdge Capital | `greenhouse-blackedgecapital` (6) |  |
| BlackRock | `workday-blackrock-blackrock_early_careers_program` (4)<br>`workday-blackrock-blackrock_professional` (206) | Workday US country facet is used when present, with internship/student/co-op worker types and configured supplementary queries. Unusually categorized programs may be missed. |
| Blackstone | `workday-blackstone-blackstone_campus_careers` (29)<br>`workday-blackstone-bx_external_site` (60) | Workday US country facet is used when present, with internship/student/co-op worker types and configured supplementary queries. Unusually categorized programs may be missed. |
| BMO Capital Markets | `workday-bmo-capital-markets` (23) | Workday US country facet is used when present, with internship/student/co-op worker types and configured supplementary queries. Unusually categorized programs may be missed. |
| BNP Paribas | **Incomplete: public feed only** | See limitation above. |
| Bridgewater Associates | `greenhouse-bridgewater89` (14) |  |
| Campbell & Company | **Incomplete: public feed only** | See limitation above. |
| Capital Group | `workday-capital-group-capitalgroupcareers` (68) | Workday US country facet is used when present, with internship/student/co-op worker types and configured supplementary queries. Unusually categorized programs may be missed. |
| Capital One | `workday-capital-one` (existing) |  |
| Capstone Investment Advisors | `greenhouse-capstoneinvestmentadvisors` (13) |  |
| Castleton Commodities International | `workday-cci` (10) | Workday US country facet is used when present, with internship/student/co-op worker types and configured supplementary queries. Unusually categorized programs may be missed. |
| Cboe Global Markets | `workday-cboe` (4) | Workday US country facet is used when present, with internship/student/co-op worker types and configured supplementary queries. Unusually categorized programs may be missed. |
| Chicago Trading Company | `greenhouse-ctccampusboard` (6)<br>`greenhouse-chicagotradingcampus` (8) | Two public campus boards are checked. Similar titles with different posting IDs remain separate; no title-only merging. |
| Citadel | **Incomplete: public feed only** | See limitation above. |
| Citadel Securities | **Incomplete: public feed only** | See limitation above. |
| Citi | `workday-citi-2` (14) | Workday US country facet is used when present, with internship/student/co-op worker types and configured supplementary queries. Unusually categorized programs may be missed. |
| CME Group | `workday-cme-group-cme_careers` (4) | Workday US country facet is used when present, with internship/student/co-op worker types and configured supplementary queries. Unusually categorized programs may be missed. |
| D. E. Shaw | `deshaw-direct` (82) |  |
| Deutsche Bank | **Incomplete: public feed only** | See limitation above. |
| DRW | `greenhouse-drweng` (existing)<br>`greenhouse-drwuniversityjobs` (1) |  |
| DV Trading | `greenhouse-dvtrading` (existing) | Existing DV Trading board includes DV Equities and DV Commodities. Subsidiary coverage depends on their posting on this board. |
| Fidelity Investments | `workday-fidelity-investments-fidelitycareers` (232) | Workday US country facet is used when present, with internship/student/co-op worker types and configured supplementary queries. Unusually categorized programs may be missed. |
| Five Rings | `greenhouse-fiveringsllc` (16) |  |
| Flow Traders | `greenhouse-flowtraders` (45) |  |
| Franklin Templeton | `workday-franklin-templeton-primary-external-1` (0) | Workday US country facet is used when present, with internship/student/co-op worker types and configured supplementary queries. Unusually categorized programs may be missed. |
| G-Research | `workday-g-research-g-research` (19) | Workday US country facet is used when present, with internship/student/co-op worker types and configured supplementary queries. Unusually categorized programs may be missed. |
| Gelber Group | `greenhouse-gelbergroup` (8) |  |
| Geneva Trading | `greenhouse-genevatrading` (11) |  |
| Goldman Sachs | **Incomplete: public feed only** | See limitation above. |
| Group One Trading | `groupone-direct` (6) |  |
| GSA Capital | `greenhouse-gsacapital` (10) |  |
| GTS | `icims-gts` (15) |  |
| HAP Capital | **Incomplete: public feed only** | See limitation above. |
| Headlands Technologies | `greenhouse-headlandstechnologiesllc` (8) |  |
| HSBC | **Incomplete: public feed only** | See limitation above. |
| Hudson River Trading | `greenhouse-hudsonrivertrading` (existing) |  |
| IMC Trading | `greenhouse-imc` (172) |  |
| Intercontinental Exchange | **Incomplete: public feed only** | See limitation above. |
| Invesco | `workday-invesco-ivzearlycareers` (14)<br>`workday-invesco-ivz` (16) | Workday US country facet is used when present, with internship/student/co-op worker types and configured supplementary queries. Unusually categorized programs may be missed. |
| Jane Street | `greenhouse-janestreet` (existing) |  |
| JPMorgan Chase | **Incomplete: public feed only** | See limitation above. |
| Jump Trading | `greenhouse-jumptrading` (110) |  |
| Macquarie Group | `macquarie-campus` (31) | Official campus recruitment records, with complete pagination; unusually categorized programs outside the campus directory can be missed. |
| Magnetar | `greenhouse-magnetar` (2) |  |
| Mako | `greenhouse-mako` (7) |  |
| Man Group | `greenhouse-mangroup` (56) |  |
| Marshall Wace | `greenhouse-mwinternshipprogram` (7) |  |
| Maven Securities | `greenhouse-mavensecuritiesholdingltd` (46) |  |
| Millennium Management | **Incomplete: public feed only** | See limitation above. |
| Moody's | `moodys-campus` (28) | Official Students & Early Careers category, with complete pagination. Structured posting date and displayed date are recorded separately when they differ; mismatched application requisitions remain unverified. |
| Morgan Stanley | `workday-morgan-stanley` (50) | Workday US country facet is used when present, with internship/student/co-op worker types and configured supplementary queries. Unusually categorized programs may be missed. |
| MSCI | `icims-msci-us` (2) | Direct source is the US iCIMS board. Other regional boards are outside this direct scope. |
| Nasdaq | `workday-nasdaq-global_external_site` (9) | Workday US country facet is used when present, with internship/student/co-op worker types and configured supplementary queries. Unusually categorized programs may be missed. |
| Neuberger Berman | `workday-neuberger-berman-nbcareers` (47) | Workday US country facet is used when present, with internship/student/co-op worker types and configured supplementary queries. Unusually categorized programs may be missed. |
| Nomura | **Incomplete: public feed only** | See limitation above. |
| Old Mission | `greenhouse-oldmissioncapital` (39) |  |
| Optiver | `greenhouse-optiverus` (161) | Current optiverus public board contains global postings. The old optiver board was empty and is not added. |
| PanAgora Asset Management | `panagora-direct` (1) |  |
| PDT Partners | `greenhouse-pdtpartners` (9) |  |
| PEAK6 Capital Management | `workday-peak6-capital-management-capman` (2) | Workday US country facet is used when present, with internship/student/co-op worker types and configured supplementary queries. Unusually categorized programs may be missed. |
| PGIM | `workday-pgim-pgim_careers` (69) | Workday US country facet is used when present, with internship/student/co-op worker types and configured supplementary queries. Unusually categorized programs may be missed. |
| PIMCO | `workday-pimco-pimco-careers` (185) | Workday US country facet is used when present, with internship/student/co-op worker types and configured supplementary queries. Unusually categorized programs may be missed. |
| PNC | `workday-pnc` (34) | Workday US country facet is used when present, with internship/student/co-op worker types and configured supplementary queries. Unusually categorized programs may be missed. |
| Point72 | `greenhouse-point72` (233) | Point72 board includes Cubist roles; exact requisition IDs remain distinct. |
| Quantlab | **Incomplete: public feed only** | See limitation above. |
| Qube Research & Technologies | `greenhouse-quberesearchandtechnologies` (202) |  |
| Radix Trading | `greenhouse-radixuniversity` (8) |  |
| RBC Capital Markets | `workday-rbc-capital-markets` (10) | Workday US country facet is used when present, with internship/student/co-op worker types and configured supplementary queries. Unusually categorized programs may be missed. |
| Renaissance Technologies | `renaissance-direct` (12) | Current public job directory is checked; the live snapshot contained no proven internships. New titles/descriptions must independently prove internship eligibility. |
| S&P Global | `workday-s-p-global-spgi_careers` (298) | Workday US country facet is used when present, with internship/student/co-op worker types and configured supplementary queries. Unusually categorized programs may be missed. |
| Schonfeld Strategic Advisors | `greenhouse-schonfeld` (79) |  |
| Seven Eight Capital | **Incomplete: public feed only** | See limitation above. |
| Seven Research | `greenhouse-sevenresearch` (8) |  |
| Société Générale | `socgen-us` (75) | Official public Quantum careers search: complete declared US result pagination, exact employer job schema, and Taleo application identity. Anonymous website search tokens stay in memory. Internship evidence is required; ordinary investment banking roles remain outside the configured families. |
| Squarepoint Capital | `greenhouse-squarepointcapital` (94) |  |
| State Street | `workday-state-street-global` (745) | Workday US country facet is used when present, with internship/student/co-op worker types and configured supplementary queries. Unusually categorized programs may be missed. |
| Susquehanna International Group | **Incomplete: public feed only** | See limitation above. |
| T. Rowe Price | `workday-t-rowe-price-troweprice` (69) | Workday US country facet is used when present, with internship/student/co-op worker types and configured supplementary queries. Unusually categorized programs may be missed. |
| TGS Management | **Incomplete: public feed only** | See limitation above. |
| Tower Research Capital | `greenhouse-towerresearchcapital` (89) |  |
| TransMarket Group | `greenhouse-transmarketgroup` (19) |  |
| Trexquant Investment | `trexquant-direct` (34) |  |
| Tudor Investment Corporation | `greenhouse-tudorgroup` (4) |  |
| Two Sigma | `twosigma-direct` (55) |  |
| UBS | `ubs-students` (19) | Official student/graduate BrassRing directory, all declared results paginated before the US filter. Candidate internship details are enriched by exact board/job ID. Last-updated dates are retained as updates, not posting dates; experienced-hire boards are outside scope. |
| Valkyrie Trading | `lever-valkyrietrading` (6) |  |
| Vanguard | `workday-vanguard-vanguard_external` (215) | Workday US country facet is used when present, with internship/student/co-op worker types and configured supplementary queries. Unusually categorized programs may be missed. |
| Vatic Investments | `greenhouse-vaticlabs` (8) |  |
| Verition Fund Management | `greenhouse-veritiongroupllc` (30) |  |
| Virtu Financial | `greenhouse-virtu` (existing) |  |
| Voleon Group | `ashby-voleon` (55) |  |
| Voloridge Investment Management | `greenhouse-voloridgeinvestmentmanagement` (8) |  |
| Walleye Capital | `greenhouse-walleyecapital-external-students` (4) | Official student board; campus FAQ identifies Quantic internships. Other subsidiaries and lateral roles are outside this campus source. |
| Wellington Management | `workday-wellington-management-campus` (24)<br>`workday-wellington-management-external` (113) | Workday US country facet is used when present, with internship/student/co-op worker types and configured supplementary queries. Unusually categorized programs may be missed. |
| Wells Fargo | **Incomplete: public feed only** | See limitation above. |
| Wolverine Trading | **Incomplete: public feed only** | See limitation above. |
| WorldQuant | `greenhouse-worldquant` (104) |  |
| XTX Markets | `greenhouse-xtxmarketstechnologies` (10) |  |

## Verification and operation

Local tests cover classification, source completeness, application conflicts, source outages, notification retries, restart recovery and exact cross-source identity. The per-company notification contract uses synthetic jobs and proves queue behavior, not live employer coverage. [Machine-readable probe evidence](finance-source-evidence.json) contains source counts and timings; private raw discovery responses stay outside Git.

The production SQLite path is `/var/lib/internship-watch/jobs.sqlite3`; private exports are `/var/lib/internship-watch/export`. Existing private report access and local download instructions remain in [operations](OPERATIONS.md). No public report hosting is added. After an update, refresh/download the report to see the latest export timestamp; a previously opened local file is a snapshot.

The `internship-watch` systemd unit remains enabled at boot. Stop with `sudo systemctl stop internship-watch`; disable reboot startup with `sudo systemctl disable internship-watch`. A deliberate stop triggers the independent Healthchecks monitor unless its check is paused intentionally. Update using a tested release archive, a consistent off-host SQLite snapshot and guarded symlink cutover; keep `/etc/internship-watch.env` and `/var/lib/internship-watch` intact. Do not replace the database with an empty checkout or delete delivery history.

Automatic off-host backup scheduling remains blocked on the previously requested backup storage account/secret connection. Manual off-host upgrade snapshots are made and verified before this cutover. Existing verified Discord and independent monitoring remain configured; their credentials are not included in this repository or report.

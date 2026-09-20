# Finance expansion: actual-host acceptance

Azure runs `ebfacc718945893f2a15c1a0449401093fad1590` on the existing VM. This release is in [your private repository](https://github.com/andymaoo/internship-watch/tree/codex/reliable-internship-discovery). All **304 application tests and six backup tests** passed locally and on the host. Configuration still targets US opportunities, the user's junior eligibility, all seasons, five-minute polling, persistent SQLite, Discord and independent Healthchecks email monitoring. No extra paid resources were created.

Links to `report/`, `ACTUAL_HOST.md` and `HOST_ACCEPTANCE.md` refer to the accompanying private deployment package; those private files are not committed to GitHub.

## Coverage and remaining gaps

All 108 requested finance/quant employers are accounted for: **90 have live-tested direct routes and 18 retain incomplete public-feed-only discovery**. Combined with prior requests: **213 enabled sources, 212 company labels, 188 labels with direct or parent-board routes, and 24 incomplete labels**. These counts describe configured and observed coverage, not every market opening or a guarantee against future provider changes. [Every requested employer and exact limitations](FINANCE_EXPANSION.md) and the private [coverage report](../report/coverage.html) distinguish healthy sources from missing direct coverage. Existing working sources, including HRT, were retained.

The new-source link audit originally found 98 filter matches. Focused classification repairs removed sophomore-only programs and a mortgage-finance role wrongly matched by the word “Residential.” The final audit contains **95 qualifying distinct postings**: **31 posting/application open, 63 posting open/application unverified, and one posting open/application closed**. All were checked live; no application was submitted. The closed application is a GSA public page returning 404 while its exact Greenhouse posting API remains active. The discrepancy is recorded, and known-closed applications are excluded from immediate notification. Login, JavaScript, robots and unconfirmed forms remain unverified rather than closed. This audit is a dated sample of new-source discoveries, separate from the full persistent report and ongoing worker checks.

Repairs bind observed Workday legal names to exact employer tenants (CME, BMO, S&P/Kensho, PIMCO); accept real intern duties without requiring a particular heading; extract Bank of America's labeled description inside its Tal.net form; preserve accented employer names; and retain independent posting/application evidence. A real Moody's posting/apply requisition conflict remains explicitly unverified. UBS and Société Générale anonymous search tokens stay in memory and are not stored in job records.

The preceding 212-source checkpoint passed four source runs but failed cross-source stability: six exact Akuna requisitions alternated between “Akuna Capital” and “Akuna Capital University,” repeatedly clearing validation. The new regression reproduced the failure before repair. A reviewed display-name alias now retains the direct employer payload and valid check state; it does not merge jobs by employer name. A broader offline replay reproduced 14 further resets across six observed name aliases (Voleon, Five Rings, Schonfeld, Voloridge, Cboe and RBC). The fixed replay retained validation across all 402 canonical jobs and 886 source observations, without network requests or notifications. Direct PhD-only requirements are also retained across abbreviated community records. The final alias test below is required rather than treating the earlier failed checkpoint as accepted.

HSBC's separate [official campus programme finder](https://www.hsbc.com/careers/students-and-graduates/find-a-programme) closes one additional direct-coverage gap. Its public load-more API returned all 67 declared programmes; ordinary page-number URLs repeated the first page and were rejected as a collection method. The three current US entries were graduate programmes, so none qualified. A foreign internship sample verified its employer posting and exact application ID; application access remained unverified under robots policy. The source preserves the employer's stated programme-opening date with that specific provenance. Structured graduate-career programmes are excluded, while conflicting internship/graduate evidence stays ambiguous. General and lateral-careers openings outside this directory remain outside its direct scope.

The following 213-source checkpoint passed its staged collection and first scheduled run, then run 228 correctly rejected UBS pages that repeated five exact posting IDs. A separate live reproduction confirmed the date-order problem. The employer's advertised alphabetical sort returned all 151 distinct postings in two fresh sessions. The final adapter uses that order on every page, with unchanged strict identity, duplicate and total checks. Missing sort support also fails safely. This checkpoint is preserved as incomplete rather than counted as final acceptance.

NVIDIA's timestamp sort alone did not resolve tied-date page boundaries. Overlapping windows now collect every distinct declared ID, with a single bounded restart for unstable pagination. Repeated inconsistent payloads, missing IDs, changed totals and private records still fail safely. The repaired local pass returned all 113 postings; final Azure runs below rechecked it.

## Actual scheduled runs and capacity

The final staged pass collected/classified all **213/213 sources** in **280.022 seconds**, peak RSS **358.0 MiB**. Staging ran alongside the preceding worker, so this is not an isolated capacity benchmark. Production timings below include collection/storage, validation, delivery and exports.

An earlier 213-source staged attempt failed its completeness/health assertion after 276.324 seconds and did not switch production. The helper's truncated error output omitted the source/count responsible, so that attempt's cause remains unresolved. The retry identified a corrupted Société Générale employer name in configuration, caused by default Windows decoding during the local edit. The known Unicode names were restored against the prior deployed configuration and given regression coverage; no validator was weakened. The first attempt's truncated output cannot independently establish its exact failing source set. Full failed-command diagnostics are now retained. The successful staged pass and subsequent ordinary runs below are the acceptance evidence; the failed attempt is preserved separately and is not counted as a pass.

| Run | Status | Start UTC | End UTC | Seconds | Collection/storage | Checks | Due afterward | Qualifying posting unverified | Failed sources |
|---|---|---|---|---:|---:|---:|---:|---:|---|
| 231 | ok | 2026-09-20T03:44:05+00:00 | 2026-09-20T03:49:12+00:00 | 306.808 | 239.932 | 33 | 264 | 771 | None |
| 232 | ok | 2026-09-20T03:49:15+00:00 | 2026-09-20T03:54:32+00:00 | 316.237 | 247.996 | 36 | 244 | 771 | None |
| 233 | degraded | 2026-09-20T03:54:33+00:00 | 2026-09-20T03:59:26+00:00 | 293.206 | 225.532 | 25 | 246 | 771 | workday-wellington-management-campus |
| 234 | ok | 2026-09-20T03:59:33+00:00 | 2026-09-20T04:04:35+00:00 | 301.986 | 234.24 | 31 | 228 | 771 | None |
| 235 | ok | 2026-09-20T04:04:37+00:00 | 2026-09-20T04:09:41+00:00 | 304.128 | 235.923 | 29 | 219 | 770 | None |
| 236 | ok | 2026-09-20T04:09:42+00:00 | 2026-09-20T04:14:55+00:00 | 312.78 | 244.498 | 24 | 206 | 769 | None |

Any degraded rows above are failed observations, retained for review. Run 233 encountered a policy-access failure on Wellington's campus source; it recovered on the following scheduled poll without a policy override. An independent local recheck received a valid HTTP 200 policy file and all 24 campus listings. The exact cause of the earlier failed policy check was not captured, so a temporary access problem is an inference from recovery, not a proved HTTP diagnosis. The last two completed post-restart runs must each have all 213 sources healthy to pass acceptance. The last two post-restart scheduled runs started **305.0 seconds apart**. No observed runs overlapped. Polling remains configured at 300 seconds; a cycle that exceeds that duration postpones the next one. Cold classification caches, source latency, rate limits and maintenance can extend the interval. The existing VM has about 842 MiB usable RAM and its previously configured 2 GiB swap; no resize was performed. Service memory: `MemoryCurrent=308846592; MemoryPeak=626073600`.

Validation due across the recorded runs: **264 → 244 → 246 → 228 → 219 → 206**. This is a short observation window, not a steady-state throughput guarantee. A separate queue inspection at `2026-09-20T04:16:01+00:00` found **207 due items, of which 0 had never been checked**; the rest were rechecks. Due work includes baseline imports and scheduled rechecks; unresolved login/JavaScript/blocked destinations are not necessarily overdue. The recorded final decision-latency metric is `{"count": 4, "max_seconds": 66.0, "p50_seconds": 64.0}`. That metric is cumulative historical evidence. During this release window there were **0 newly discovered non-baseline records**, including **0 qualifying records**; their measured decision delays in seconds were `[]`. An empty sample provides no fresh-discovery latency measurement for the expanded configuration. Employer-publication-to-discovery delay remains unknown where the employer does not provide a posting timestamp. Additional source records are silently baselined; future qualifying discoveries enter the verified alert or clearly labeled awaiting-verification digest queue.

Simplify's unrestricted public internship feed is still checked each cycle. Its full website is not this GitHub export, and upstream publishing/maintainer delays are additional to polling and validation time. Immediate alerts mean delivery after the worker reaches a verified qualifying notification decision, not instant delivery from an employer's publication time.

## Delivery, history and restart

A labeled real Discord test was acknowledged at `2026-09-20T01:48:57.751454+00:00`, receipt `1551047485764403232`. An injected transport failure first left a pending record, reopening SQLite retained it, the retry delivered, and another drain sent no duplicate. That test used the preceding finance release; delivery/outbox code is unchanged in the final source and validator repairs, so an identical test message was not resent.

One grouped **initial finance expansion / imported backlog** report was delivered at `2026-09-20T02:41:02+00:00`, receipt `1551060591479750769`. The outbox contains exactly one record for its dedicated deduplication key. Its dated counts were **95 qualifying records associated with added boards, 74 postings verified open, 20 awaiting posting verification, and 1 with a known-closed posting or application**. These categories can overlap: a posting can be open while its application is closed. Records already known from other sources are included in this grouped snapshot, not announced individually as new discoveries.

The controlled restart at `2026-09-20T03:49:15.730625+00:00` preserved **2967 job identities/first-seen/baseline states, 9 delivery records, 213 source initialization states and 36525 cache rows**. The required consecutive successful runs completed after restart. **293 unchanged cross-source records** retained their validation and next-check state. Reviewed alias cases within that preserved set were `{"Akuna Capital": 6, "Voloridge Investment Management": 2, "Five Rings": 3, "Voleon Group": 1, "Schonfeld Strategic Advisors": 2, "Cboe Global Markets": 1}`. The separate historical-data replay matched 90 new-source observations to prior records and preserved all 2871 original job IDs/first-seen values and existing delivery receipts. Exact ATS/board/requisition identities are used; identical titles alone never merge jobs.

Systemd is active and enabled for boot. Earlier real reboot, controlled incident/recovery, and independent Healthchecks stopped-worker email-alert evidence remains in [HOST_ACCEPTANCE.md](HOST_ACCEPTANCE.md). The user confirmed the initial test email; Healthchecks recorded delivery for the later accelerated missing-heartbeat DOWN/recovery test, but recipient confirmation of those later emails remains pending. The production check uses a five-minute period and 15-minute grace. Those unchanged monitoring paths were not all repeated during this expansion. The recent Discord retry and restart tests above are separate current evidence.

## Reports, backups and operating instructions

The private [HTML](../report/jobs.html), [CSV](../report/jobs.csv), source health and coverage reports were exported at **2026-09-20T04:14:54+00:00**. HTML/CSV/JSON/link-evidence rows were checked against one another. The included consistent SQLite snapshot has **2967 records**, **213 initialized healthy sources**, and passed integrity and off-host SHA-256 verification. Snapshot hash: `753aaaa1803bbda710b59e5406019ca7c339a1ee25939db4aa15b790e6b665de`.

These downloaded files are snapshots. For continuously updated private reports, use the existing SSH tunnel instructions in [ACTUAL_HOST.md](ACTUAL_HOST.md), then refresh after a completed cycle. No public HTTP port was opened.

**Automatic off-host backups remain unfinished:** a private backup bucket and scoped credentials are still needed in `/etc/internship-watch-backup.env` (`RESTIC_REPOSITORY`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`). Keep values out of chat. Manual upgrade/current snapshots were copied off-host and verified; they do not replace scheduled backup upload/restore and backup-monitor acceptance. Full-system acceptance remains incomplete for this reason.

Runtime: `/opt/internship-watch`; state: `/var/lib/internship-watch/jobs.sqlite3`; config: `/etc/internship-watch.json`; secrets: `/etc/internship-watch.env`; exports: `/var/lib/internship-watch/export`. Stop: `sudo systemctl stop internship-watch`. Disable reboot startup: `sudo systemctl disable internship-watch`. Resume: `sudo systemctl enable --now internship-watch`. Pause the independent check during planned downtime. Updates use a tested archive, consistent off-host snapshot, guarded code/config switch and scheduled verification; preserve secrets, database and delivery history.

## All sources in the final staged pass

Raw rows and pre-link filter counts below are that pass's observations; zero matches does not imply a broken source.

| Source | Raw rows | Filter matches | Collection seconds |
|---|---:|---:|---:|
| amazon-direct | 347 | 6 | 8.574 |
| apple-apple | 57 | 2 | 7.21 |
| ashby-applied | 292 | 0 | 0.178 |
| ashby-aurora-operations-inc | 86 | 0 | 0.441 |
| ashby-benchling | 51 | 0 | 0.419 |
| ashby-cerebras | 113 | 0 | 0.206 |
| ashby-characterai | 13 | 0 | 0.157 |
| ashby-cohere | 142 | 2 | 0.145 |
| ashby-confluent | 21 | 0 | 0.052 |
| ashby-cursor | 122 | 0 | 0.159 |
| ashby-decagon | 146 | 1 | 0.101 |
| ashby-elevenlabs | 235 | 0 | 1.007 |
| ashby-harvey | 299 | 0 | 1.086 |
| ashby-kalshi | 42 | 0 | 0.096 |
| ashby-linear | 32 | 0 | 0.17 |
| ashby-mistral.ai | 199 | 0 | 0.136 |
| ashby-modal | 34 | 0 | 0.221 |
| ashby-notion | 128 | 3 | 0.642 |
| ashby-openai | 818 | 0 | 0.899 |
| ashby-perplexity | 118 | 1 | 0.111 |
| ashby-plaid | 114 | 0 | 0.903 |
| ashby-polymarket | 83 | 0 | 0.143 |
| ashby-quora | 5 | 0 | 0.074 |
| ashby-ramp | 148 | 0 | 0.324 |
| ashby-replit | 76 | 0 | 0.386 |
| ashby-runway | 4 | 0 | 0.227 |
| ashby-sierra | 210 | 1 | 0.707 |
| ashby-skydio | 138 | 1 | 0.129 |
| ashby-snowflake | 346 | 0 | 0.72 |
| ashby-voleon | 55 | 1 | 0.066 |
| atlassian-direct | 274 | 2 | 1.568 |
| bankofamerica-campus | 27 | 2 | 90.494 |
| bloomberg-direct | 353 | 0 | 32.612 |
| bytedance-direct | 885 | 58 | 6.275 |
| deshaw-direct | 82 | 3 | 1.616 |
| eightfold-microsoft | 85 | 4 | 9.226 |
| eightfold-netflix | 12 | 0 | 3.274 |
| eightfold-nvidia | 113 | 7 | 40.504 |
| eightfold-paypal | 2 | 0 | 4.528 |
| greenhouse-acadianassetmanagementllc | 12 | 0 | 7.9 |
| greenhouse-affirm | 199 | 0 | 0.236 |
| greenhouse-airbnb | 168 | 0 | 0.36 |
| greenhouse-airtable | 16 | 0 | 0.29 |
| greenhouse-akunacapital | 40 | 7 | 3.408 |
| greenhouse-andurilindustries | 2374 | 3 | 4.582 |
| greenhouse-anthropic | 611 | 3 | 1.725 |
| greenhouse-aqr | 51 | 2 | 3.74 |
| greenhouse-aquaticcapitalmanagement | 8 | 2 | 4.846 |
| greenhouse-asana | 103 | 0 | 0.146 |
| greenhouse-blackedgecapital | 6 | 2 | 4.674 |
| greenhouse-block | 221 | 0 | 0.608 |
| greenhouse-boxinc | 115 | 0 | 1.058 |
| greenhouse-brex | 251 | 0 | 0.206 |
| greenhouse-bridgewater89 | 14 | 0 | 7.837 |
| greenhouse-c3iot | 83 | 1 | 2.705 |
| greenhouse-capstoneinvestmentadvisors | 13 | 0 | 4.749 |
| greenhouse-chicagotradingcampus | 8 | 2 | 6.27 |
| greenhouse-chime | 67 | 0 | 0.16 |
| greenhouse-cloudflare | 379 | 0 | 1.43 |
| greenhouse-coinbase | 217 | 6 | 1.792 |
| greenhouse-coursera | 17 | 0 | 2.659 |
| greenhouse-ctccampusboard | 6 | 2 | 6.062 |
| greenhouse-databricks | 877 | 2 | 1.858 |
| greenhouse-datadog | 453 | 2 | 1.966 |
| greenhouse-discord | 47 | 0 | 0.185 |
| greenhouse-doordashusa | 462 | 1 | 1.201 |
| greenhouse-dropbox | 44 | 1 | 0.113 |
| greenhouse-drweng | 164 | 4 | 0.906 |
| greenhouse-drwuniversityjobs | 1 | 0 | 6.657 |
| greenhouse-duolingounirecruitment | 3 | 2 | 0.116 |
| greenhouse-dvtrading | 71 | 8 | 0.127 |
| greenhouse-figma | 152 | 3 | 0.165 |
| greenhouse-fiveringsllc | 16 | 2 | 7.989 |
| greenhouse-flexport | 198 | 0 | 3.592 |
| greenhouse-flowtraders | 45 | 0 | 5.369 |
| greenhouse-gelbergroup | 8 | 0 | 5.35 |
| greenhouse-genevatrading | 11 | 2 | 6.212 |
| greenhouse-glean | 123 | 0 | 0.249 |
| greenhouse-gsacapital | 10 | 1 | 6.809 |
| greenhouse-headlandstechnologiesllc | 8 | 0 | 7.975 |
| greenhouse-hubspotjobs | 138 | 0 | 4.699 |
| greenhouse-hudsonrivertrading | 83 | 3 | 0.259 |
| greenhouse-imc | 172 | 4 | 6.953 |
| greenhouse-instacart | 108 | 0 | 0.549 |
| greenhouse-janestreet | 229 | 9 | 0.153 |
| greenhouse-jumptrading | 110 | 7 | 7.072 |
| greenhouse-lyft | 178 | 1 | 0.246 |
| greenhouse-magnetar | 2 | 0 | 6.826 |
| greenhouse-mako | 7 | 0 | 6.731 |
| greenhouse-mangroup | 56 | 0 | 8.013 |
| greenhouse-mavensecuritiesholdingltd | 46 | 1 | 7.697 |
| greenhouse-mercury | 64 | 0 | 3.843 |
| greenhouse-mongodb | 401 | 0 | 0.441 |
| greenhouse-mwinternshipprogram | 7 | 0 | 7.058 |
| greenhouse-neuralink | 77 | 7 | 0.168 |
| greenhouse-nextdoor | 21 | 0 | 2.685 |
| greenhouse-nuro | 107 | 1 | 1.278 |
| greenhouse-okta | 324 | 0 | 5.439 |
| greenhouse-oldmissioncapital | 39 | 1 | 6.866 |
| greenhouse-optiverus | 161 | 3 | 8.187 |
| greenhouse-pdtpartners | 9 | 2 | 6.965 |
| greenhouse-pinterest | 161 | 0 | 1.042 |
| greenhouse-point72 | 233 | 3 | 7.221 |
| greenhouse-purestorage | 354 | 0 | 0.826 |
| greenhouse-quberesearchandtechnologies | 202 | 0 | 7.123 |
| greenhouse-radixuniversity | 8 | 0 | 7.52 |
| greenhouse-reddit | 156 | 0 | 0.936 |
| greenhouse-riotgames | 155 | 0 | 2.654 |
| greenhouse-robinhood | 157 | 4 | 0.298 |
| greenhouse-roblox | 244 | 2 | 0.71 |
| greenhouse-roku | 254 | 0 | 1.932 |
| greenhouse-rubrik | 139 | 1 | 0.181 |
| greenhouse-samsara | 273 | 1 | 0.469 |
| greenhouse-samsungresearchamericainternship | 4 | 0 | 1.972 |
| greenhouse-scale | 223 | 1 | 0.702 |
| greenhouse-schonfeld | 79 | 2 | 6.45 |
| greenhouse-sevenresearch | 8 | 1 | 7.957 |
| greenhouse-sofi | 57 | 0 | 3.58 |
| greenhouse-spacex | 2505 | 0 | 2.948 |
| greenhouse-squarepointcapital | 94 | 0 | 7.097 |
| greenhouse-stripe | 665 | 1 | 0.716 |
| greenhouse-stubhubinc | 33 | 0 | 1.333 |
| greenhouse-together | 78 | 9 | 0.176 |
| greenhouse-towerresearchcapital | 89 | 3 | 6.464 |
| greenhouse-transmarketgroup | 19 | 3 | 6.891 |
| greenhouse-tudorgroup | 4 | 0 | 7.805 |
| greenhouse-twilio | 143 | 0 | 2.862 |
| greenhouse-twitch | 48 | 0 | 0.303 |
| greenhouse-vaticlabs | 8 | 0 | 7.97 |
| greenhouse-vercel | 84 | 2 | 0.113 |
| greenhouse-veritiongroupllc | 30 | 0 | 7.986 |
| greenhouse-verkada | 297 | 5 | 1.257 |
| greenhouse-virtu | 51 | 1 | 0.151 |
| greenhouse-voloridgeinvestmentmanagement | 8 | 2 | 7.92 |
| greenhouse-walleyecapital-external-students | 4 | 1 | 7.483 |
| greenhouse-waymo | 339 | 4 | 0.229 |
| greenhouse-worldquant | 104 | 0 | 7.022 |
| greenhouse-xai | 265 | 0 | 0.688 |
| greenhouse-xtxmarketstechnologies | 10 | 0 | 7.918 |
| greenhouse-zscaler | 369 | 0 | 0.607 |
| groupone-direct | 6 | 1 | 16.572 |
| hsbc-campus | 67 | 0 | 4.219 |
| icims-gts | 15 | 0 | 1.396 |
| icims-msci-us | 2 | 0 | 1.183 |
| jibe-amd | 134 | 13 | 25.191 |
| jibe-github | 2 | 0 | 20.187 |
| jobvite-nutanix | 110 | 0 | 1.616 |
| lever-belvederetrading | 17 | 0 | 1.165 |
| lever-palantir | 313 | 21 | 5.179 |
| lever-spotify | 71 | 0 | 1.399 |
| lever-valkyrietrading | 6 | 0 | 1.09 |
| lever-veeva | 918 | 0 | 10.259 |
| lever-zoox | 237 | 0 | 5.011 |
| macquarie-campus | 31 | 0 | 30.497 |
| moodys-campus | 28 | 4 | 30.615 |
| oracle-direct | 20 | 0 | 21.397 |
| panagora-direct | 1 | 0 | 2.434 |
| renaissance-direct | 12 | 0 | 13.17 |
| rippling-direct | 323 | 1 | 6.17 |
| simplify-public-internships | 4405 | 1697 | 0.718 |
| smartrecruiters-aristanetworks | 247 | 0 | 2.399 |
| smartrecruiters-linkedin | 332 | 0 | 3.511 |
| smartrecruiters-servicenow | 646 | 0 | 6.383 |
| snap-direct | 179 | 0 | 1.22 |
| socgen-us | 75 | 0 | 19.23 |
| tiktok-direct | 885 | 58 | 4.726 |
| trexquant-direct | 34 | 0 | 13.694 |
| twosigma-direct | 55 | 3 | 11.169 |
| ubs-students | 19 | 1 | 17.348 |
| workday-adobe | 10 | 2 | 12.464 |
| workday-alliancebernstein-abcampuscareers | 22 | 0 | 26.379 |
| workday-arrowstreet-capital-campus_careers | 2 | 2 | 6.361 |
| workday-barclays-external_career_site_barclays | 92 | 2 | 100.615 |
| workday-blackrock-blackrock_early_careers_program | 4 | 0 | 8.397 |
| workday-blackrock-blackrock_professional | 206 | 0 | 28.367 |
| workday-blackstone-blackstone_campus_careers | 29 | 0 | 15.033 |
| workday-blackstone-bx_external_site | 60 | 0 | 12.965 |
| workday-bmo-capital-markets | 23 | 2 | 24.935 |
| workday-broadcom | 105 | 0 | 9.332 |
| workday-capital-group-capitalgroupcareers | 68 | 0 | 7.593 |
| workday-capital-one | 12 | 0 | 15.314 |
| workday-cboe | 4 | 1 | 8.744 |
| workday-cci | 10 | 0 | 7.308 |
| workday-cisco | 32 | 2 | 35.469 |
| workday-citi-2 | 14 | 0 | 11.849 |
| workday-cme-group-cme_careers | 4 | 2 | 8.448 |
| workday-crowdstrike | 5 | 0 | 6.364 |
| workday-ebay | 3 | 0 | 7.575 |
| workday-fidelity-investments-fidelitycareers | 232 | 0 | 15.673 |
| workday-franklin-templeton-primary-external-1 | 0 | 0 | 4.606 |
| workday-g-research-g-research | 19 | 0 | 8.458 |
| workday-invesco-ivz | 16 | 0 | 31.374 |
| workday-invesco-ivzearlycareers | 14 | 0 | 30.358 |
| workday-morgan-stanley | 50 | 0 | 52.994 |
| workday-nasdaq-global_external_site | 9 | 1 | 7.26 |
| workday-neuberger-berman-nbcareers | 47 | 0 | 8.309 |
| workday-palo-alto-networks | 34 | 9 | 30.701 |
| workday-peak6-capital-management-capman | 2 | 0 | 4.615 |
| workday-pgim-pgim_careers | 69 | 0 | 16.491 |
| workday-pimco-pimco-careers | 185 | 1 | 65.914 |
| workday-pnc | 34 | 0 | 31.003 |
| workday-rbc-capital-markets | 10 | 0 | 22.122 |
| workday-s-p-global-spgi_careers | 298 | 1 | 24.361 |
| workday-salesforce | 22 | 1 | 22.675 |
| workday-samsung | 36 | 0 | 41.899 |
| workday-servicetitan | 55 | 0 | 6.629 |
| workday-state-street-global | 744 | 0 | 44.21 |
| workday-t-rowe-price-troweprice | 69 | 1 | 17.353 |
| workday-unity | 2 | 0 | 6.422 |
| workday-vanguard-vanguard_external | 215 | 4 | 34.832 |
| workday-wellington-management-campus | 24 | 4 | 42.526 |
| workday-wellington-management-external | 113 | 4 | 47.363 |
| workday-zoom | 45 | 0 | 6.67 |

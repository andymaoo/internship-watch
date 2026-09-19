# Link validation triage — 19 September 2026 UTC

The frozen `work/audit.sqlite3` baseline contained **2,065 unverified candidate jobs: 1,585 included and 480 ambiguous**. Another 412 unverified records were classified excluded and are outside this denominator. Unverified does not mean expired. The baseline and every representative result are retained under `work/triage/`; this investigation did not mutate SQLite.

## Exact baseline breakdown

Each job gets one primary reason: inspect the description check unless it passed, then inspect the last application check; choose the first reason in the documented precedence in `baseline_summary.json`. Counts therefore sum to the population. Multi-label evidence and contributing-source counts overlap and must not be summed as distinct jobs.

| Primary reason | All candidates | Included |
|---|---:|---:|
| Expected job identity not verified | 1,331 | 1,027 |
| Access restriction, historic detail unavailable | 367 | 285 |
| Application form/destination not verified | 201 | 161 |
| HTTP 403 restriction | 81 | 62 |
| Missing or insufficient description | 58 | 32 |
| URL access ValueError | 24 | 16 |
| Access challenge | 1 | 1 |
| Timeout | 1 | 0 |
| HTTP server failure | 1 | 1 |
| **Total** | **2,065** | **1,585** |

Included multi-label evidence: identity 1,027; application form/destination 371; unspecified access restriction 285; HTTP 403 62; missing description 32; ValueError 16; challenge 1; server failure 1. A job can contribute to several labels, for example a description identity failure and a separate application failure.

| Primary source, included records | Count |
|---|---:|
| simplify-public-internships | 1,557 |
| greenhouse-janestreet | 13 |
| apple-apple | 4 |
| ashby-notion | 2 |
| greenhouse-databricks | 2 |
| ashby-cohere | 2 |
| greenhouse-roblox | 2 |
| ashby-perplexity | 1 |
| ashby-sierra | 1 |
| greenhouse-rubrik | 1 |

Primary source is the alphabetically first stored contributor, an additive reporting convention rather than attribution of blame. `baseline_summary.json` includes the complete source-membership and source-by-reason matrices. `baseline_jobs.json` retains every contributor and source ID.

Largest blocking-destination host groups among included jobs: lifeattiktok.com 119; jobs.ashbyhq.com 97; job-boards.greenhouse.io 59; www.tesla.com 56; jobs.l3harris.com 49; jobs.smartrecruiters.com 40; egug.fa.us2.oraclecloud.com 26; careers.qorvo.com 23; hdjq.fa.us2.oraclecloud.com 22; jobs.lever.co 22; bah.wd1.myworkdayjobs.com 19; jobs.bytedance.com 19. The JSON report contains **every hostname**, separately for included, ambiguous, and combined populations.

### Historical validation versions matter

The included baseline had 1,214 description/application pairs both unverified, 357 description-open/application-unverified, and 14 description-unverified/application-open. **All 357 historical description passes came from validator v3**, before application-form text was excluded from descriptions. These are a priority recheck pool, not 357 trusted postings or automatic promotions. Migration conservatively keeps pre-v4 evidence unverified. The fresh checks below use the corrected parser.

## Representative live evidence and verified repairs

Sixteen deliberately selected jobs were checked with bounded requests and the existing robots, DNS, redirect, pacing, and cooldown policy. This is a diagnostic sample, not a statistical recovery estimate. `live_before.jsonl` contains the first fresh checks; `live_representatives.jsonl` contains the subsequent checks; complete response bodies are archived in `responses/` with content hashes in filenames. The after run verified **10 postings versus 5 before**, including **2 with verified application forms**. The remaining 8 verified postings still have unverified application access. These are validation results, not final eligibility decisions; enriched descriptions must be classified again.

The subsequent Jane Street check verified its posting through the fresh exact-job API and retained unverified application access because the destination still attempted an insecure redirect. Combining the latest result for each of the same 16 jobs gives **11 verified postings (6 newly recovered), 2 with verified applications, and 9 with unverified application access**. `live_summary.json` records these exact counts and the six recovered IDs. One recovery used API fallback directly; the other five were verified from corrected webpage parsing/canonical URL handling. This does not predict how many of the 192 potential API candidates will recover.

| Job ID and current URL | Observed cause and result |
|---|---|
| `0cfe161fe1f0ce848cbb98c8` [Belvedere](https://jobs.lever.co/belvederetrading/8f06f221-8777-4a4d-b035-40882db5f4a0/apply) | Feed URL was an application-only form. The same-ID canonical posting has the description. Recognized Lever/Ashby application paths now use the canonical description URL; original URLs remain recorded. Both components verified. |
| `0009d26ab1f3428a720336bf` [Terranova](https://jobs.ashbyhq.com/terranova/a8e5a8d2-4af3-4736-b66e-e0804447f7a0) | Source says “Software Engineer Intern”; current schema says “Software Engineering Intern.” Narrow token variants and ordered title additions are accepted only with the same immutable job ID. Posting verified; application unverified. |
| `015e8f2e71520066d818cfe1` [Corning](https://corningjobs.corning.com/job/Charlotte-Digital-&-IT-Intern,-Analyst,-Manufacturing-AIML-Summer-2027-NC-28216/1425708000/?ats=successfactors) | Current title inserts “Analyst” between source title words. Same-ID ordered title matching recovered the posting without fuzzy matching other roles. Application unverified. |
| `00e6da3b0ff4ff3f55803066` [NXP](https://nxp.wd3.myworkdayjobs.com/en-US/careers/job/Austin-Oakhill-Office/Data-Analytics-Engineer-Intern---Summer-2027_R-10065538) | Exact title and substantial JobPosting description were rejected because legal employer is “US63 NXP USA Inc.” Require the NXP brand in both legal name and Workday tenant hostname. Posting verified; application unverified. |
| `afd7a83e585c957c82303a72` [Evolver](https://job-boards.greenhouse.io/evolver/jobs/4254540009) | Substantial description used “Role Details” and “Interns will contribute,” absent from the old content vocabulary. These specific responsibility phrases are now recognized. Both components verified; season uncertainty remains in STALE_SEASON_REVIEW.md. |
| `03e70e07460255f2d740c3f9` [Jane Street](https://job-boards.greenhouse.io/janestreet/jobs/8498547002) | Web redirect attempts HTTPS-to-HTTP downgrade, correctly rejected. Fresh documented Greenhouse API returned exact ID, full description, a HTTPS canonical URL, title “Quantitative Researcher,” and structured employment “Summer Internship.” API-only title matching can omit the internship word when fresh structured employment proves it. A focused final check is saved separately in `live_additional.jsonl`; it is not included in the 16-job before/after counts. |
| `0105bc1201d82d0ee031d879` [Shure](https://careersus-shure.icims.com/jobs/4996/job?mobile=true&needsRedirect=false) | Posting verified; apply link resolves to a job-specific login screen. It now receives explicit login evidence and remains application-unverified. No login attempted. |
| `00dcee9f80d5796bb4437d16` [TikTok](https://lifeattiktok.com/search/7668642761473902901) | Posting renders substantial public content; apply link serves a JavaScript shell. Posting verified, application unverified. |
| `303902cc7e65a47f57c907ed` [Apple](https://jobs.apple.com/en-us/details/200664780/machine-learning-and-artificial-intelligence-undergrad-internships) | HTML contains the expected title and corporate navigation/footer, without a rendered job description. Remains unverified; HTTP 200 was insufficient. |
| `afa4b18b549ce51322b3ebff` [Domino](https://app.careerpuck.com/job-board/domino-data-lab/job/7992560?gh_jid=7992560) | Title-only JavaScript shell. Remains unverified; the validator does not guess a Greenhouse board from the employer name. |
| `02a1c5cd5b94f87b965c2615` [Tesla](https://www.tesla.com/careers/search/job/282248) | Fresh HTTP 403 access-denied response. Remains unverified. |
| `00bd42eadc1b28b7f36494b7` [Jump Trading](https://boards.greenhouse.io/embed/job_app?token=8002998) | Explicit robots denial; URL also omits employer-board parameter. No guessing or bypass. Remains unverified. |
| `0004efffce9c533324618d84` [Ecolab](https://ecolab.wd1.myworkdayjobs.com/ecolab_external/job/USA---Minnesota---Saint-Paul/Digital---AI-Technology-Intern_R00303249) | Robots policy could not be verified; this differs from an explicit rule denying a path. Remains unverified. |

Historic `AccessRestricted` records omit which of robots denial, unavailable robots policy, or host cooldown occurred. Their exact retrospective causes cannot be recovered. New evidence distinguishes these cases when the HTTP client has the relevant policy state. A local sandbox-denied probe was discarded and the live sample was rerun from the network-enabled execution context; local socket restrictions are not counted as employer failures.

## Validator v5 contract and limits

`posting_status` and `application_status` independently use `open`, `closed`, or `unverified`. Legacy `status` remains conservative: closed if either component is closed, open only if both are open. A posting can support a clearly labeled notification while application access is unverified. An application known closed must suppress immediate usable-job notification.

Fresh documented [Greenhouse exact-job data](https://docs.greenhouse.io/job-board.html), [Lever exact-posting data](https://github.com/lever/postings-api), and [Ashby public board data](https://developers.ashbyhq.com/docs/public-job-posting-api) can establish posting validity. The validator requires exact employer-board/job identity, a compatible title, a bound canonical job URL, and a substantial description. API checks have `kind=posting_api`, `fetched_at`, and explicit evidence. Public API GETs use the providers' documented public API contract; webpage GETs continue to respect robots. API results are cached at most five minutes per client. A feed description, HTTP 200, or API absence alone never proves open or closed. APIs do not prove the application interface works; it is fetched separately. Explicit webpage closure is not overridden by API fallback.

Focused regressions cover all confirmed repairs plus wrong jobs, foreign employers/boards, unavailable APIs, cache expiry, small descriptions, missing employer-board IDs, form-only boilerplate, login pages, and dotted board names such as `mistral.ai`. No captcha bypass, authentication, application submission, or unsafe redirect relaxation was added.

## Recheck plan and remaining work

`prioritized_rechecks.json` lists all 1,585 included baseline jobs: 357 older posting passes first; 147 additional exact-API candidates next; 566 remaining Workday jobs for schema/legal-name checks; 515 others. There are 192 recognized API candidates overall (95 Ashby, 76 Greenhouse, 21 Lever), overlapping 45 older posting passes. **These counts measure eligible recheck routes, not successful recoveries.** Run bounded fair batches, retain per-host cooldowns, and classify newly retrieved descriptions before notification.

Blocked sources remain unverified until access policy permits a recheck. Browser-rendered verification could help selected JavaScript application pages, but unattended browser sessions add maintenance and do not resolve source restrictions. Explicit board configuration is preferable for incomplete ATS URLs. Expand public API integrations only where documented or directly authorized. Inspect the generated baseline JSON for complete reason/source/hostname coverage and use the separate fresh result files to measure actual recovery rather than estimating it from historical error labels.

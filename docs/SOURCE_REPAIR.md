# Direct-source repair â€” September 19, 2026

The configuration now includes a verified HRT direct board. Google detail verification is repaired, while complete Google discovery and Meta automation remain blocked by specific source restrictions. The public feed is not a substitute for complete employer coverage. Existing user filters, five-minute polling, SQLite identities and notification history are preserved.

## HRT: working board found and storage bug repaired

The [official careers page](https://www.hudsonrivertrading.com/careers/) loads `wp-content/plugins/hrt-jobs/scripts/frontend-bundle.min.js?ver=5.1.2`. That public frontend explicitly identifies Greenhouse board `wehrtyou`. The [documented public board endpoint](https://boards-api.greenhouse.io/v1/boards/wehrtyou/jobs?content=true) returned **83 jobs**, matching its declared total. No private plugin endpoint or restricted WordPress REST path is used.

Three listings passed the configured filters: Algorithm Development (Quant Research & Trading), Software Engineering (C++ or Python), and Women in Trading and Technology. Employer posting validation succeeded for all three; application access remains unverified because the forms are rendered with JavaScript. Program-specific eligibility still requires review. These are current discovered matches, not a claim of three newly published opportunities.

An actual source-to-storage rehearsal exposed list-valued Greenhouse employment metadata that SQLite could not bind. The source adapter now normalizes string arrays to a scalar employment value while retaining the exact metadata in evidence. Unexpected nested schemas fail as source errors. Regression tests cover collection through classification and SQLite, multiple/empty selections and malformed values. A replay against a private database copy merged the three HRT records into the existing three feed identities, preserving their original discovery timestamps and baseline membership without increasing the job count or sending notifications.

## Google: permitted detail verification repaired; discovery incomplete

Python 3.12's `urllib.robotparser` converted Google's actual `Disallow: /?` into `/`, falsely treating it as a blanket prohibition. A second defect evaluated policy before Requests appended `params=`, which could miss query-specific restrictions. The HTTP client now uses pinned [Protego](https://github.com/scrapy/protego) and checks the actual prepared URL with [RFC 9309](https://www.rfc-editor.org/rfc/rfc9309.html) matching. Wildcards, end anchors, longest-match rules, user-agent groups, percent encoding and pacing have dedicated regressions. The client identity is unchanged.

Google's [published policy](https://www.google.com/robots.txt) permits the inspected first-page search and individual detail paths, but disallows the relevant pagination query parameters. The public US internship search reported **31 jobs and returned 20 on page one**. Restricted pagination was not fetched, and no RPC, token or query-partition workaround is used. Thus no complete direct Google collector is enabled.

Individual permitted Google job pages contain public embedded detail records alongside unrelated search suggestions. The new parser requires the exact URL job ID, Google employer, matching actual title/heading, valid description/qualification/location fields and a consistent employer application link. Suggestions never substitute for the requested job. Schema drift or title ambiguity remains unverified. Only narrow evidenced title variants are accepted. Google's sign-in application destination remains unverified independently of a verified employer posting.

A live seven-record Google cohort now has seven verified employer postings, each with unverified sign-in application access. Reclassification produces two included matches, four degree-incompatible exclusions and one ambiguous apprenticeship. Fresh official minimum qualifications override conflicting community degree hints. In the live cohort, an MS-only internship otherwise inherited an incorrect Bachelor's/Master's hint from Simplify. The repair preserves the raw feed evidence and ensures subsequent sparse feed polls cannot resurrect that listing as eligible for the configured bachelor's-level user. Description enrichment is reclassified before notifications.

## Meta: written permission required, no active indirect records

The [Meta Careers policy](https://www.metacareers.com/robots.txt) explicitly requires written permission for automated collection. Public search returned a JavaScript shell, not a verified complete job list. The older private GraphQL probe's single hardware PhD record did not demonstrate completeness, and that flow has not been enabled or replayed.

The configured Simplify feed recheck contained **45 Meta records, all inactive**, and zero active/visible ones. Earlier wording that Meta "remains covered" was too strong. Zero feed records does not establish zero employer openings. Both `metacareers.com` and `www.metacareers.com` are configured in `http.blocked_hosts` so future feed entries do not cause prohibited automated destination requests. Their links remain unverified with the policy reason; they are not marked closed.

Further Meta progress requires written collection permission or an authorized feed/API with a usable completeness contract. The user can browse [Meta Careers](https://www.metacareers.com/jobsearch/) normally. No native alert capability was verified, so none is claimed. Google native job alerts/manual official checking and the existing public feed remain permitted supplements to the incomplete direct coverage.

## Operation and evidence

The combined local suite passed **196 application tests and six backup tests**, plus compilation. The release must also pass staged tests and consecutive 53-source cycles on Azure before being described as deployed. The operating checkpoint and dated host evidence are delivered under `outputs/continuation`; these versioned implementation notes do not substitute for that evidence. The update preserves `/etc/internship-watch*` and `/var/lib/internship-watch`, with a consistent recovery snapshot copied off-host before activation and the prior code release retained for rollback.

Reproducible regression commands:

```sh
python -m unittest discover -s tests -v
python -m unittest discover -s deploy -p test_backup.py -v
python -m compileall -q internship_watch
```

Use the project virtual environment. The repair does not bypass source restrictions, manufacture posting dates or turn login forms into verified application access. Five-minute polling remains distinct from upstream discovery/export delay. Automatic remote backups still require the separately pending storage connection.

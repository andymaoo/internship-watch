# Simplify, Handshake and LinkedIn

Reviewed 2026-09-23. Native account alerts are separate from the Azure worker,
SQLite records and Discord outbox. No authenticated browser scraper was added.

## Simplify is already an enabled source

`simplify-public-internships` reads
`https://raw.githubusercontent.com/SimplifyJobs/Summer2027-Internships/dev/.github/scripts/listings.json`.
This is the input to the public repository's README generation, so adding a
second README collector would duplicate the same source.

The live public check at approximately 22:21 UTC found the same canonical
repository, the `dev` branch, no feed redirects, valid required fields, 17,210
records and 4,513 active/visible records. The latest feed-path commit was
`754d261ca47a88e28f422e8a47d3028618ab63a6`, dated 22:02:09 UTC. Azure's configured
source was independently confirmed enabled and successful at 22:22:40 UTC,
returning 4,513 records with zero consecutive failures.

The worker targets 300-second polling. Only newly discovered qualifying jobs
trigger normal alerts: verified employer postings use individual notifications;
qualifying unresolved postings use the separate deduplicated digest. Existing
baseline jobs are suppressed. Validation queues and delivery retries can add
delay. An active feed record can belong to an older season; it does not prove
recent employer publication. This public feed is not Simplify's whole website,
and website-to-feed publication delay is unknown.

## Supported alternatives for authenticated platforms

Handshake's terms prohibit third-party bulk automated collection of job
descriptions and marketplace data. Its documented EDU API is institution-scoped,
requires support-provided credentials and approval, and is not established as a
self-service student job-search API. Any future adapter needs an explicitly
authorized job-only feed and verified scope/schema. Do not request or use access
to student, application, or other unrelated institutional records.

LinkedIn's help documentation prohibits third-party tools that scrape or
automate its website. No authorized collection feed is configured. A persistent
cloud login does not grant collection permission and introduces session-expiry,
MFA and account-challenge dependencies. No cookies, passwords or passkeys were
copied to Azure.

The owner approved native daily job alerts. These run on the providers' systems
without keeping this computer or a cloud browser logged in. They are approximate
search matches, not the worker's independently validated/classified matches.
They do not share its cross-source deduplication or Discord delivery history.
Their own daily schedule cannot provide five-minute discovery. Handshake states
that each alert email contains at most 25 postings.

## Account setup evidence

Handshake: the existing `Internships` alert was changed from Weekly to Daily.
After navigating away and reopening notification preferences, its saved modal
showed Daily and Email/in-app/push enabled. Existing search criteria were retained:
internships, part-time, hybrid or remote. This alert is not comprehensive US
coverage and excludes onsite/full-time-schedule internships. The current account's
new search UI exposed no create-alert toggle, even after a keyword search with
internship/co-op/fellowship filters. The Saved tab contained only saved jobs; the
notification page offered editing the existing alert, not creating another.
Consequently no new role-specific Handshake alert is claimed. The location picker
offered city/radius matches rather than a verified US-wide country choice.

Additional Handshake saved searches remain blocked on an available supported UI
or assistance from Handshake/Berkeley. Existing private worker filters were not
changed to accommodate these platform limitations.

LinkedIn: five new searches were saved. Manage job alerts showed each with
United States, Internship, and Daily via email and notification. All four
pre-existing alerts were preserved, including two existing similar Berkeley
software alerts; the account now lists nine total. Exact new keyword queries:

| Group | Keywords |
| --- | --- |
| Software | `("software engineer" OR "software developer" OR "backend" OR "back-end" OR "full stack" OR "full-stack")` |
| Data | `("data analyst" OR "data analysis" OR "data engineer" OR "data scientist" OR "data science")` |
| ML/AI and research | `("machine learning" OR "artificial intelligence" OR "AI engineer" OR "AI research" OR "research scientist" OR "research engineer")` |
| Quant | `("quantitative" OR "quant" OR "algorithmic trading" OR "systematic trading")` |
| Product | `("product manager" OR "product management")` |

No season, company or onsite/remote restriction was added. Internship is the
native employment-type filter in the observed UI. These saved searches do not
independently enforce junior eligibility, citizenship/sponsorship compatibility
or hardware-responsibility exclusions. Fellowships/residencies not tagged as
internships may be absent. The settings were verified in the account; receipt
of a future scheduled native email has not yet been tested. Manage or stop them
in [LinkedIn Job alerts](https://www.linkedin.com/jobs/jam/).

## References and account controls

- [Simplify repository](https://github.com/SimplifyJobs/Summer2027-Internships)
- [README generation workflow](https://github.com/SimplifyJobs/Summer2027-Internships/blob/dev/.github/workflows/update_readmes.yml)
- [Handshake terms](https://joinhandshake.com/legal/tos/)
- [Handshake native alerts](https://support.joinhandshake.com/hc/en-us/articles/218693388-Saving-Job-Searches-and-Receiving-Job-Alerts)
- [Handshake EDU API setup](https://support.joinhandshake.com/hc/en-us/articles/31061076506391-Getting-Started-with-EDU-API)
- [Handshake notification preferences](https://berkeley.joinhandshake.com/notification-preferences)
- [LinkedIn automation policy](https://www.linkedin.com/help/linkedin/answer/a1340567/automated-activity-on-linkedin?lang=en)
- [LinkedIn native job alerts](https://www.linkedin.com/help/linkedin/answer/a511279/job-alerts-on-linkedin?lang=en)

To stop or change Handshake delivery, open Notification preferences, then Edit
beside the named job alert. LinkedIn alerts are managed from Jobs > Job alerts.
No new hosting or paid resources are required for native alerts.

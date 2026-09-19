# Latest requested company expansion

The September 19, 2026 request contains 100 company labels. Combined with the earlier list, the configured watchlist has 105 entries. Existing working integrations are retained. There are 123 enabled sources, 49 more than the prior release. A company is not necessarily a source: multiple companies share parent boards, and the public Simplify feed covers many employers.

## Discovery and remaining gaps

Greenhouse, Ashby, Lever and SmartRecruiters integrations use their public recruiting APIs. Simplify discovery continues every 300 seconds from the public `SimplifyJobs/Summer2027-Internships` repository, `dev` branch, `.github/scripts/listings.json`, without a company allowlist. This detects changes after they reach that feed; it does not subscribe to Simplify's full website. Its maintainer guide describes daily database exports, so upstream delays can exceed the polling interval.

The following requested employers have incomplete, public-feed-only automated discovery:

| Employer | Confirmed limitation | Permitted alternative |
|---|---|---|
| Google | Search pagination is restricted. Known individual postings can be checked. | Public internship feed and employer alerts/manual search. |
| Meta | Direct automated collection requires written permission; user selected public feeds only. | Public feed or a separately authorized Meta feed. |
| Uber | Azure returned HTTP 403 with a Cloudflare challenge. | Public feed and official employer alerts. |
| IBM | The observed public search API's robots policy prevents automated access. | Public feed and IBM job alerts/manual search. |
| Intuit | Public HTML first pages work; the observed pagination request is excluded by robots policy. Reading only page one would be incomplete. | Public feed and Intuit job alerts/manual search. |
| Tesla | Public careers search returned HTTP 403. | Public feed and official employer alerts/manual search. |

No challenge, login restriction or robots exclusion is bypassed. The job filter remains US, junior/bachelor, no sponsorship needed, all seasons, including configured co-ops and research programs. Unknown eligibility is shown as unverified, not invented.

Additional scope limits:

- Slack is covered through Salesforce's public Workday board. Splunk's own careers page links to Cisco's Workday board. Parent-company listings retain their employer names; they are not all relabeled as the subsidiary.
- Samsung coverage includes Samsung Electronics Workday and Samsung Research America internships, not every Samsung affiliate.
- Duolingo uses its university recruiting board.
- Workday uses current Intern/Student/Co-op worker-type facets when available, supplemented by fellowship/residency searches. Without those facets it falls back to the `intern` search. Workday treats broad `intern` and `co-op` text as matches for many ordinary jobs, so explicit structured scopes keep requests bounded. A co-op or research program categorized unusually can be missed by direct discovery; public-feed coverage remains supplementary.
- Oracle uses the public Oracle Cloud Candidate Experience Student/Intern worker-type scope with complete pagination and full posting details. The unrestricted full-board query had inconsistent page counts; it was not enabled. Other Oracle research programs rely on the public feed.
- ByteDance and TikTok's two public supplier hosts returned identical content for all 885 shared global posting IDs. They expose a shared group index; brand-specific website results can differ. Exact shared posting IDs are aliased across those known domains. Records retain the ByteDance parent-company label; the TikTok hostname is discovery provenance, not proof of the hiring subsidiary. The evidence explicitly marks subsidiary identity unverified.
- PayPal's current `/api/pcsx/search` public API works. The older `/api/apply/v2/jobs` route failed and is not used.
- Applied Intuition and Aurora now use Ashby; HubSpot uses `hubspotjobs`, and Unity uses Workday. Obsolete or empty legacy boards are not enabled.

The private `coverage.html` / `coverage.json` report gives each company's source IDs, latest source health, stored qualifying counts and limitations. Zero qualifying jobs does not mean a source is broken, and a working source does not guarantee future availability or complete market coverage.

## Identity and validation

Deduplication uses stable source IDs and exact reviewed ATS URL aliases, never employer/title alone. Workday identities include tenant, site and posting instance; distinct `R123` and `R123-1` postings remain separate. Reviewed AMD/GitHub iCIMS, Atlassian portal, Oracle locale/site aliases and ByteDance/TikTok aliases converge on their existing records. Legacy aliases are added in a non-destructive migration; conflicting already-existing records are not silently merged.

For an exact ByteDance/TikTok mirror with identical job content, the readable ByteDance posting remains the canonical destination. A live comparison verified the parent posting while the TikTok mirror lacked readable description content. A changed mirror description still affects eligibility; both untouched source records remain in history. This preference is restricted to reviewed shared IDs and matching content.

Workday detail validation verifies the exact requisition, posting instance, tenant/site, title, employer and meaningful description. Employer `posted=false` is closed; unavailable or mismatched evidence is unverified. `canApply=true` is not proof an application form is accessible. Employer `startDate` is retained as evidence and is not misrepresented as a posting date.

Atlassian's public feed contains repeated identical records. Only exact repeats of the same requisition are collapsed; conflicting content fails collection. Workday's later pages report `total=0` even while returning jobs: the initial count governs pagination, with repeated pages, truncation and conflicting totals rejected.

The persistent classification cache uses the complete job payload, filters and classifier-code fingerprint. Job edits, filter edits or classifier changes invalidate it. Old cache entries expire after 30 days without observation. Discovery records, validation history and notification receipts remain separate.

The final host audit found a validation-budget defect: when there was too little time left for rate-limit pacing, unrequested jobs could be recorded as timeouts and deferred for an hour. Local budget exhaustion is now separate from a remote network failure. An entirely deferred check retains its previous state and due time; useful partial posting evidence is kept, can notify immediately, and gets another application check next poll. The loop stops at that boundary instead of churning through the remaining due jobs. A deferred robots fetch cannot cache a denied policy. Regression tests cover these paths, real network timeouts and restart preservation.

New source backlogs are baselined to prevent hundreds of individual alerts. Future newly discovered verified qualifying jobs use the existing Discord queue; qualifying unverified jobs use the separately labeled digest. Existing retry and incident suppression policies remain in place.

## Acceptance and operations

Run `python -m unittest discover -s tests` and the backup tests in `deploy/`. New tests cover source pagination/schema changes, posting versus application state, exact duplicates, distinct requisitions, and cache invalidation after restart. Deployment acceptance must additionally contain live Azure results for every enabled source, scheduled timing/backlog measurements, state preservation and current export hashes. Do not treat a local test as deployment evidence.

The existing systemd service, persistent `/var/lib/internship-watch/jobs.sqlite3`, private report tunnel and secret paths are retained. See `OPERATIONS.md`, `CONNECTIONS.md` and `HOST_ACCEPTANCE.md` for transport/monitoring evidence and operating instructions. Automatic encrypted off-host backups still require the user's B2 bucket and scoped credentials; manual consistent snapshots are verified separately. New source integration does not complete that remaining backup setup.

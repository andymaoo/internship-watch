# Internship Watch

US internship and research-program discovery with persistent records, conservative link checks, and retryable Discord or ntfy notifications. **This private repository, `andymaoo/internship-watch`, is the canonical backend for the Azure Discord worker.** It extends the original project reviewed at `2a776814a993fd74e92cc91aa15e90fb0f99424a`.

The default configuration reflects the requested preferences: United States (including remote roles with US eligibility), all seasons, co-ops, current undergraduate junior, no sponsorship required, and relevant research programs. Freshman/sophomore-only, permanent/new-graduate, and hardware-focused roles are excluded. Unclear eligibility stays available for review. Software/AI internships at hardware companies remain eligible.

**Live deployment verified October 22, 2026:** Azure is running release `b3d88cd`, with 213 enabled sources and 212 company entries. The worker, 15-minute maintenance timer and local backup timer are active. The worker database contains 1,774 delivered messages and no queued messages at the recorded observation. Recent collection cycles were degraded; active services do not establish complete source health. See [the current deployment record](docs/CURRENT_DEPLOYMENT.md) for the observed release, evidence and limits.

**Repository code and deployment are separate:** the tested Moody's location repair is pushed here but is **not yet deployed to Azure**. HubSpot's original Greenhouse board recovered and returned 62 records during scheduled Azure collection on October 22, so its earlier retirement proposal was reversed before deployment. The configuration retains 213 enabled sources and 212 company entries: 188 direct or parent-company routes and 24 incomplete public-feed-only routes. Counts describe configured routes, not guaranteed employer or market coverage. Pushing to GitHub runs CI; it does not automatically deploy or send job notifications.

The older public `internship-job-monitor` repository contained a separate legacy scraper and was deleted on October 22 after its collection schedule was disabled and its full Git history was backed up locally. Keep this repository for development and deployment. This backend runs as `python -m internship_watch` on Azure; its `scrape.py` is only a compatibility entry point to the same durable pipeline. `seen.json` is a historical import artifact. Neither is a separate active notification service in this repository.

The Azure installation uses persistent SQLite, Discord webhooks and previously configured independent Healthchecks email. Automatic startup was tested during deployment. Automatic off-host backups still await the storage-account connection; daily local backup scheduling is active. Older acceptance reports contain dated measurements, not a current all-sources-health guarantee. Slow cycles postpone the next poll without overlapping.

Handshake and LinkedIn marketplace discovery use separate native daily account alerts. They do not feed the Azure database or Discord queue. The LinkedIn employer's own SmartRecruiters board is a different configured source. Cloud/platform software roles may qualify under software engineering; there is no separate cloud category. See [additional discovery channels](docs/ADDITIONAL_DISCOVERY_CHANNELS.md).

Maintenance has an independent 15-minute supervisor, live source contracts,
persisted repair evidence, anomaly alerts, daily verified local backups, weekly
delivery checks and a daily Codex repair follow-up. The follow-up requires the
Windows PC/app to be available; Azure monitoring remains independent. See the
[maintenance operating guide](docs/MAINTENANCE.md), [actual test evidence](docs/MAINTENANCE_ACCEPTANCE.md)
and [review queue](docs/MAINTENANCE_REVIEW.md). Automatic off-host backup credentials
remain an explicit outstanding issue. The private HTML report links to the
searchable maintenance backlog.

## Run locally

Requires Python 3.12. Use a virtual environment:

```sh
python -m venv .venv
# Activate .venv for your shell, then:
python -m pip install -r requirements.txt
cp config.example.json config.json
python -m unittest discover -s tests -v
python -m internship_watch --config config.json --env-file .env run
python -m internship_watch --config config.json status
python -m internship_watch --config config.json export --output data/export
```

On PowerShell, use `.venv\Scripts\Activate.ps1` and `Copy-Item config.example.json config.json`. For a **new** checkout, copy `.env.example` to `.env` and privately fill its fields before the command above; do not overwrite an existing configuration, secret file or database. Alternatively omit `--env-file` when the service manager supplies the environment. Open `data/export/jobs.html` for a searchable snapshot; CSV, JSON, source status and link evidence are beside it. The default `initial_run: "digest"` sends one grouped initial report; use `"silent"` to import quietly. Notification credentials belong in private environment configuration, never committed to Git.

Run continuously with `python -m internship_watch --config config.json --env-file .env daemon`. The target polling interval is five minutes; slow sources, retries and queued link verification can delay discovery/notification. A five-minute interval is not a promise of finding employer postings five minutes after publication.

## Design

1. Public Greenhouse, Lever, Ashby, Workday, SmartRecruiters and other reviewed employer integrations plus the existing Simplify community feed collect records. Each source has independent health and bootstrap state.
2. An evidence-based classifier identifies role family, internship/program evidence, location, season and eligibility. Ambiguous listings remain explicit.
3. SQLite records source observations, job identities, historical checks, run health and a separate delivery outbox. Only changed observations add history; `last_seen` advances each successful observation.
4. Employer posting validity and application access are stored separately. Each verified destination must identify the expected position; HTTP 200 alone does not mean open. Robots restrictions, timeouts, missing descriptions and access failures remain unverified.
5. Included jobs with a verified posting generate immediate alerts unless the application is known closed. An inaccessible application is clearly labeled. Newly discovered included jobs awaiting verification get a separate, duplicate-suppressed digest. Failed deliveries stay queued. Source/empty-result incidents are deduplicated until recovery. Once configured, a separately hosted Healthchecks monitor detects missing runs and persistent notification/storage failures.

Deduplication uses job-specific URL/requisition identities, not title similarity. This avoids merging separate positions with identical titles but leaves uncertain cross-source aliases separate. Delivery is at least once across the rare crash-after-provider-acceptance window; the worker does not promise impossible exactly-once delivery.

`seen.json` is a historical artifact containing 5,472 IDs. Import it once with `import-seen seen.json` if those IDs should be suppressed. It never becomes delivery evidence, is never rewritten, and is no longer committed by scheduled GitHub Actions. Do not delete the SQLite database during deployments.

## Configuration and reports

- [Simplify feed verification and separate Handshake/LinkedIn native alerts](docs/ADDITIONAL_DISCOVERY_CHANNELS.md)
- [Current actual-host acceptance, measured polling and remaining backup setup](docs/FINANCE_ACCEPTANCE.md)
- [Finance/quant expansion, all 108 requested employers and explicit gaps](docs/FINANCE_EXPANSION.md)
- [Current company expansion and coverage limits](docs/EXPANSION_100.md)
- [Audit and implementation decisions](docs/AUDIT.md)
- [Current delivery, measurements and remaining access](docs/CONTINUATION.md)
- [Unresolved link triage and representative live checks](docs/LINK_TRIAGE.md)
- [Notification and recheck policy](docs/NOTIFICATIONS.md)
- [Measured hosting comparison](docs/HOSTING.md)
- [Proposed Azure student setup](docs/AZURE_STUDENT.md)
- [Private account and secret setup](docs/CONNECTIONS.md)
- [Sources and verified migrations](docs/SOURCE_AUDIT.md)
- [Simplify comparison and hosting research](docs/RESEARCH.md)
- [Classification and link policy](docs/CLASSIFICATION.md)
- [Validation evidence and remaining acceptance](docs/VALIDATION.md)
- [Deployment and acceptance procedure](docs/DEPLOYMENT.md)
- [Secrets, inspection, backup and recovery](docs/OPERATIONS.md)
- [Example configuration](config.example.json)

Coverage is measured per configured source, not claimed to cover the entire market. The finance report lists 18 additional incomplete direct routes, alongside the earlier Google, Meta, Uber, IBM, Intuit and Tesla gaps; the unrestricted community feed may provide some of their listings. Google individual-posting verification and HRT's public Greenhouse board work. The public Simplify repository is a subset of Simplify's website and has separate curation/export delays. Refresh the canonical seasonal feed configuration when the upstream repository changes.

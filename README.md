# Internship Watch

US internship and research-program discovery with persistent records, conservative link checks, and retryable Discord or ntfy notifications. Extends the original project reviewed at `2a776814a993fd74e92cc91aa15e90fb0f99424a`.

The default configuration reflects the requested preferences: United States (including remote roles with US eligibility), all seasons, co-ops, current undergraduate junior, no sponsorship required, and relevant research programs. Freshman/sophomore-only, permanent/new-graduate, and hardware-focused roles are excluded. Unclear eligibility stays available for review. Software/AI internships at hardware companies remain eligible.

**Deployment status:** prepared and locally tested. All 128 regression tests pass; live checks succeeded for 52 enabled sources. A full manual pipeline cycle completed in 156.3 seconds before the final classifier and link-validator refinements. A local one-source daemon completed two five-minute scheduled runs and preserved its database after restart and backup. Production host, private notification/heartbeat secrets, and target-host acceptance tests are required before this is a deployed service. No real notification or independent heartbeat alert has been delivered to your account. See [validation evidence](docs/VALIDATION.md).

## Run locally

Requires Python 3.12. Use a virtual environment:

```sh
python -m venv .venv
# Activate .venv for your shell, then:
python -m pip install -r requirements.txt
cp config.example.json config.json
python -m unittest discover -s tests -v
python -m internship_watch --config config.json run
python -m internship_watch --config config.json status
python -m internship_watch --config config.json export --output data/export
```

On PowerShell, use `.venv\Scripts\Activate.ps1` and `Copy-Item config.example.json config.json`. Open `data/export/jobs.html` for a searchable snapshot; CSV, JSON, source status and link evidence are beside it. The default first run silently imports records. `initial_run: "digest"` requests an initial import summary. Notification credentials belong in environment variables, never configuration committed to Git.

Run continuously with `python -m internship_watch --config config.json daemon`. The target polling interval is five minutes; slow sources, retries and queued link verification can delay discovery/notification. A five-minute interval is not a promise of finding employer postings five minutes after publication.

## Design

1. Public Greenhouse, Lever, Ashby, repaired Apple and the existing Simplify community feed collect structured records. Each source has independent health and bootstrap state.
2. An evidence-based classifier identifies role family, internship/program evidence, location, season and eligibility. Ambiguous listings remain explicit.
3. SQLite records source observations, job identities, historical checks, run health and a separate delivery outbox. Only changed observations add history; `last_seen` advances each successful observation.
4. Both description and application destinations must identify the expected position. HTTP 200 alone does not mean open. Robots restrictions, timeouts, missing descriptions and access failures remain unverified.
5. Only eligible jobs with verified destinations generate new-job deliveries. Failed deliveries stay queued. Source/empty-result incidents are deduplicated until recovery. Once configured, a separately hosted Healthchecks monitor detects missing runs and persistent notification/storage failures.

Deduplication uses job-specific URL/requisition identities, not title similarity. This avoids merging separate positions with identical titles but leaves uncertain cross-source aliases separate. Delivery is at least once across the rare crash-after-provider-acceptance window; the worker does not promise impossible exactly-once delivery.

`seen.json` is a historical artifact containing 5,472 IDs. Import it once with `import-seen seen.json` if those IDs should be suppressed. It never becomes delivery evidence, is never rewritten, and is no longer committed by scheduled GitHub Actions. Do not delete the SQLite database during deployments.

## Configuration and reports

- [Audit and implementation decisions](docs/AUDIT.md)
- [Sources and verified migrations](docs/SOURCE_AUDIT.md)
- [Simplify comparison and hosting research](docs/RESEARCH.md)
- [Classification and link policy](docs/CLASSIFICATION.md)
- [Validation evidence and remaining acceptance](docs/VALIDATION.md)
- [Deployment and acceptance procedure](docs/DEPLOYMENT.md)
- [Secrets, inspection, backup and recovery](docs/OPERATIONS.md)
- [Example configuration](config.example.json)

Coverage is measured per configured source, not claimed to cover the entire market. Direct Google, Meta and Hudson River Trading are explicitly disabled with reasons; the unrestricted community feed may provide some of their listings. The public Simplify repository is a subset of Simplify's website and has separate curation/export delays. Refresh the canonical seasonal feed configuration when the upstream repository changes.

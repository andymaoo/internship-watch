# Continuation delivery — 19 September 2026 UTC

Continued from `codex/reliable-internship-discovery` at `3fdc9dec9a7aa20e93ec9cd2137e5030a42b6af6`. The earlier upstream audit reviewed `2a776814a993fd74e92cc91aa15e90fb0f99424a`. The existing architecture and every configured filter/source were preserved; polling remains 300 seconds. The implementation is now preserved in the user's **private** [andymaoo/internship-watch repository](https://github.com/andymaoo/internship-watch), on the same branch. No replacement framework was needed: the working adapters, SQLite store, transport policy, and regression suite remain the foundation.

**Status: implemented, locally exercised with real sources and Discord, and prepared for deployment. A permanent host, reboot startup, remote backup account, and independent monitor are not active.** No paid resources were created. Temporary acceptance workers have finished; there is no unattended production worker running after this handoff.

## Validation and notification changes

[LINK_TRIAGE.md](LINK_TRIAGE.md) contains the complete reason/source breakdown for the frozen 2,065 unresolved candidates, including the priority population of 1,585 included jobs. Included primary reasons were 1,027 identity mismatches/unverified identities, 285 historical access restrictions, 161 unverified application destinations, 62 HTTP403s, 32 missing descriptions, 16 URL access errors, one challenge, and one server failure. The additive source attribution places 1,557 of those jobs in the public Simplify feed; full overlapping contributor/source/reason matrices are in the accompanying evidence JSON.

The 357 historical description passes were **all validator v3** and were not automatically promoted. Version 5 excludes application-form boilerplate, records employer posting validity separately from application access, uses known ATS canonical posting URLs, accepts narrowly bound title/legal-employer variants, and can obtain fresh exact-job evidence from documented public ATS APIs. It still rejects unsafe redirects and respects webpage access restrictions.

The same 16-job diagnostic cohort improved from 5 to 11 verified postings: two have verified applications; nine have unverified applications. This is a selected diagnostic sample, not an estimated market-wide recovery percentage. Separate fresh negative controls confirmed three closed postings: two Illinois Tool Works internships and one Muru internship. Their HTTP/closure evidence is saved in `closed_controls.json`. Fresh descriptions were reclassified before updating the report.

The current private report contains **2,308 candidates**: 1,768 included and 540 ambiguous. Included posting states are **179 open, 3 closed, and 1,586 unverified**. Of the 179 open postings, 167 also have verified application access and 12 do not. The legacy combined status counts 2,079 unresolved candidates across both components. It is not directly comparable to the original 2,065: conservative migration downgraded pre-v4 evidence, fresh descriptions changed eligibility, and sources changed. Historical raw check evidence remains intact.

Immediate alerts require included classification and a verified posting, with application accessibility clearly labeled. A known-closed application holds the alert for review. Newly discovered included jobs awaiting verification get a separate labeled digest, at most once per 15-minute digest window; each job's membership is durable. A later verified notification remains independent of its earlier digest. Existing baseline records get one grouped initial report and no individual backlog flood. [Notification policy and delivery limitations](NOTIFICATIONS.md)

SQLite v2 preserves source identities, observations, check history, discovery times, delivery attempts, receipts, and the initial-digest ledger across restart. Migration does not revive checks invalidated by changed job identity or destinations. Reopened incidents cancel stale unsent recovery messages. A new lookup index avoids scanning the full check history for each exported job. HTML/CSV/JSON files are published individually by atomic replacement, with HTML last.

## Measured local evidence

The temporary harness launched a fresh real worker process on this Windows PC every 300 seconds and reused the persistent database. It checked all enabled sources in each run; it was not a Windows startup service or a cloud deployment.

| UTC start | Sources healthy | Wall time | Peak worker RSS | CPU time | Link checks | Due checks remaining |
|---|---:|---:|---:|---:|---:|---:|
| 07:38:04 | 52/52 | 158.562 s | 157.25 MiB | 71.281 s | 25 | 2,242 |
| 07:43:04 | 52/52 | 160.265 s | 96.38 MiB | 66.844 s | 26 | 2,216 |
| 07:48:04 | 52/52 | 144.937 s | 101.19 MiB | 57.062 s | 24 | 2,192 |

All prior job IDs survived each restart; the database grew from 83,443,712 to 83,697,664 bytes between the first and third completed cycles. An overlapping invocation logged `Skipped overlap` while the third worker was running. Export time fell from 7–8 seconds to 0.7 seconds with the history index. These are short local measurements, not a monthly growth forecast or Linux VM benchmark.

The first two runs preceded the last validator/queue refinements; the third included the finalized validator and included-first ordering. After measurements, repeated stable unresolved checks were calibrated from six to **twelve hours**, based on the observed ~300 checks/hour capacity: 2,065 stable failures every six hours would alone require ~344 checks/hour; twelve hours reduces that to ~172/hour. Transient failures remain hourly. This final default is regression-tested; a long steady-state run on the selected host remains required. Diagnostic checks and conservative migration reconciliation were applied after measurement and do not alter the three recorded benchmark summaries.

The due queue decreased by 50 between first and third completions, while included unverified postings decreased only from 1,602 to 1,600 during those runs. Processing a check often records an unresolved restriction rather than resolving it. The oldest due age increased as the initial backlog was worked. This short sample does not establish a permanently stable backlog. Included matches precede ambiguous records within each of the rotating new/imported/recheck groups. Persistent inaccessible postings can take twelve hours plus queue delay to be rechecked; new and changed identities retain priority.

One real new discovery, DatologyAI's Research Intern, went from first seen at 07:39:27 to a decision at 07:40:30 and Discord delivery at 07:40:33: **63 seconds to decision, 66 seconds to delivery**. This is one observed opportunity, not a latency SLA. The initial backlog message and new-job message each have one acknowledged saved receipt; neither repeated in subsequent cycles.

Real Discord tests verified connection, saved-message readback, failed-delivery persistence after an actual HTTP rejection using an intentionally invalid token, and successful retry after reopening SQLite with the correct configuration. A separate four-run source test used three real Greenhouse404 responses to trigger exactly one incident, followed by a successful real board collection and one recovery alert. Those four controlled runs were consecutive immediate test invocations, not a fifteen-minute outage simulation. The production source configuration was unchanged.

The local suite has **163 application tests plus 6 backup tests**, including classification, Product Manager inclusion, hardware responsibilities, pagination, deduplication, migration, persistent outbox retry, outages, expiry, and restart recovery. Linux GitHub Actions also passed for implementation commit `4b27e0c39212c847d60f1f9377a441a4b5adab8b`: [CI evidence](https://github.com/andymaoo/internship-watch/actions/runs/35430285477). Later documentation/default calibration commits have their own CI runs in the repository.

Restic 0.19.1 was downloaded from its official release and checked against the published SHA256SUMS. An **encrypted local** repository passed backup, full restore verification against every SQLite table, wrong-password rejection, repository checks, and real retention pruning (11 test snapshots to 7, with the newest preserved). Worker-independent backup RSS peaked at 101.98 MiB and elapsed time was 6.063 seconds. Its heartbeat was mocked for this test. These results prove neither remote B2 upload nor an external alert. Synthetic backup passwords and repositories are excluded from deliverables.

## Host and total cost decision

The existing PC has **$0 additional hosting** cost if it is already continuously awake and connected, plus electricity and any backup overage. An illustrative extra 20 W at $0.20/kWh costs $2.88/month; actual power cost is not measured. It must stay powered on, awake and online for continuous polling; locking the screen is fine. Existing Python is installed in a user profile, so reliable boot-before-login operation needs administrator setup with a machine-wide runtime and the prepared limited service account. A logon-only task would not satisfy reboot-before-login availability.

Since no student credits have been claimed, **try Azure for Students first**. Direct school verification does not require GitHub Pack approval. If the account receives the advertised new-customer VM/P6 disk allowances, a Linux B2ats_v2 (1 GiB) with one 64 GiB P6 disk uses approximately $43.80/year of the $100 credit for its Standard IPv4. Healthchecks is free; current-size B2 backup/restore overage is approximately $0–$0.03/month outside that credit. Expected first-year cash total is therefore **$0–$0.03/month**, subject to eligibility, region quota, actual free-service meters and backup growth. Annual credit renewal does not establish renewal of the free VM/disk allowances; the unchanged configuration would be about $20.72/month before renewed credit after they expire. [Exact proposed setup and private fields](AZURE_STUDENT.md)

The paid fallback is **DigitalOcean Basic 1 GiB: $6/month**, with IPv4, 25 GiB disk and transfer allowance included, for about **$6–$6.03/month plus tax** at current backup size. Its former $200 GitHub student offer ended in August 2026; it is not an available discount. Optional provider image backups add $1.20/month. The $4/512 MiB plan has insufficient proven margin: measured worker plus separately measured backup peaks sum to 259 MiB before the OS, caches and updates. [Full comparison, current primary sources and backup costs](HOSTING.md)

## Exact private configuration and remaining access

On this computer the actual private file is:

`C:\Users\o3ti3\Documents\Codex\2026-09-18\c\work\job-scraper\.env`

It is Git-ignored and its ACL is restricted to the user and SYSTEM. `DISCORD_WEBHOOK_URL` is already filled and tested. `OPS_DISCORD_WEBHOOK_URL` is blank, so operational messages use the same webhook. Do not replace the existing file wholesale.

- Put the scraper check's full secret ping URL in `HEALTHCHECKS_PING_URL=`.
- Put a separate daily-backup check's URL in `BACKUP_HEALTHCHECKS_PING_URL=`.
- Configure and verify the backup email destination in **Healthchecks itself**, attached to both checks. There is no invented application email setting or SMTP secret to fill.
- For B2 encrypted backups, privately fill `RESTIC_REPOSITORY`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, and `RESTIC_PASSWORD_FILE`. The last value is an absolute path to a separate private password file; preserve another password-manager copy outside the host.

On Linux the worker uses `/etc/internship-watch.env`; backups use `/etc/internship-watch-backup.env` and `/etc/internship-watch-restic-password`. The complete account, bucket, monitor, permission, and startup commands are in [CONNECTIONS.md](CONNECTIONS.md). Worker check:5-minute period, initially15-minute grace. Backup check:24-hour period,2-hour grace. Alert email delivery and actual stopped-worker expiry must be observed before claiming deployment.

Still needed from the user: choose Azure student hosting versus the PC or paid fallback; complete student sign-in/verification if using Azure; connect/sign in to Healthchecks and verify the chosen alert email; create/connect a dedicated B2 bucket or identify another off-host destination; provide host access through supported login/SSH and private secret configuration. GitHub ownership and Discord are already connected. Account sign-in, academic verification and email-link verification require user-controlled access; no account was created or offer redeemed. No passwords are requested in chat.

## Browse, update, stop, and remaining limits

The active local export is `work/job-scraper/data/export/jobs.html`, with CSV/JSON beside it. Each completed worker cycle refreshes it. The delivered report under `outputs/continuation/report/` is a frozen handoff snapshot; it does not update itself. Open the HTML locally. On a server, download the private export directory over SFTP or use an SSH tunnel to a loopback-only file server; do not expose an unauthenticated public dashboard. [Exact private access instructions](DEPLOYMENT.md)

For a configured Linux deployment, update by stopping `internship-watch`, making a consistent backup, pulling the reviewed branch with `git pull --ff-only`, installing pinned requirements into the existing virtual environment, running tests, then starting the service and checking status/Healthchecks. Keep `/var/lib/internship-watch/jobs.sqlite3` and private environment files. Stop collection with `sudo systemctl stop internship-watch`; disable automatic startup with `sudo systemctl disable internship-watch`. Stop the backup timer separately with `sudo systemctl disable --now internship-watch-backup.timer`. Pause the corresponding Healthchecks check during intended maintenance, then re-enable it when restarting. No such services are installed here yet.

For a chosen Windows deployment, the supplied registration script supports a preview and separate worker/backup tasks. Stop a configured worker with `Stop-ScheduledTask -TaskName 'Internship Watch'` and disable it with `Disable-ScheduledTask -TaskName 'Internship Watch'`; operate the `Internship Watch Backup` task separately. Current temporary test workers already exited. [Windows prerequisites and commands](CONNECTIONS.md)

Google direct access remains disabled by robots policy; Meta's undocumented GraphQL source lacks a proven completeness/pagination contract; HRT's old Greenhouse board is404 and the current custom site has no verified structured adapter. Simplify may provide partial indirect coverage for all three. Permitted supplements are Google's native job alerts, HRT's student/talent-community channels, and manual official Meta Careers checks. They are not connected feeds or deduplicated inputs here. [Coverage evidence and alternatives](SOURCE_AUDIT.md), [connection details](CONNECTIONS.md).

Five-minute polling only bounds the added wait after a source exposes a listing, while the worker is healthy and its cycle finishes in time. Employer publication caches, Simplify discovery/curation/daily export, validation queues, blocked destinations, and transport retries add delay. Simplify's public repository is not its full website, and its private discovery implementation remains unknown. [Public capability comparison and freshness evidence](RESEARCH.md)

Outstanding deployment acceptance: permanent-host consecutive scheduled runs after final setup, restart and reboot persistence, actual off-host upload/restore, real Healthchecks email delivery, and an independent alert after stopping the worker beyond its deadline, followed by recovery. The prepared files and local tests do not substitute for those results.

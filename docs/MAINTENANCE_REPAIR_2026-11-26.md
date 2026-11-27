# November 26 maintenance repairs

This review started at 23:49 UTC on November 26 (Pacific afternoon). It used
the existing SSH key and single-IP rule. No account, spending, firewall,
Discord permission or notification-route changes were needed.

## Verified defects and changes

**Atlassian — existing `source:atlassian-direct` ticket.** The official public
listings endpoint returned 221 unique requisitions. Ten Australia entries used
`careers-australia-atlassian.icims.com`, a legitimate destination absent from the
adapter's exact hostname allowlist. One unfamiliar destination rejected the
entire collection, including US listings. The employer's own requisition 25481
page contained an Apply link to that same hostname and requisition. Added that
one reviewed hostname. Unknown hosts, conflicting duplicates and mismatched
requisition IDs still fail validation. US geography and degree filters remain
unchanged; collecting an Australian row does not make it eligible for US alerts.

The focused regression failed before the fix and passed afterward. Two live
staged collections returned all 221 unique records and five filter matches.
These are filter matches, not proof that every application form is accessible.
The sampled employer page and application portal returned HTTP 200, but the
portal did not expose enough job content to prove application accessibility.
No posting/application validator was weakened.

**Backup completeness — `backup:local` evidence.** The successful daily backup
proof listed only the main and maintenance databases, although the independent
member pipeline has its own job identities and delivery ledger. Both backup
modes now include the configured member database and verify all tables after
restore. A missing member file fails rather than creating an empty replacement.
The supervisor rejects main-only backup evidence when a member DB is configured.
Tests cover preservation of a pending delivery and failure when an off-host
restore omits the member file. Container mode with an independently configured
host member DB fails explicitly; this installation uses native systemd.

The native backup units permit access to the existing member state directory.
The local backup timeout is 45 minutes: the previous successful main-only backup
took 25 minutes 50 seconds. This retains verification and a bounded lifetime.
The bucket connection remains outstanding; local verification does not establish
automatic off-host protection.

**AI marketing classification.** Inspecting the restored Atlassian collection
also exposed a false positive: its AI Buyer Journey Marketing Intern was
classified as ML/AI because the title mentioned AI. The actual duties inventory
campaign assets, use existing AI tools and recommend marketing changes; they do
not establish model engineering or ML research. A regression reproduced the
incorrect inclusion. AI marketing now needs a concrete technical title or
software/model-development duties to qualify as ML/AI. Separately named
data/software/product roles and real ML engineering at marketing teams remain
eligible. The source, countries, degree settings and delivered notification
history are preserved. One earlier false-positive alert had already been
delivered before this follow-up classification repair; it is retained for audit.
The same evidence check is shared by personal classification and member routing;
a separate member regression reproduced and blocked the false `intern-ml-ai`
route. Classifier code hashes invalidate cached decisions automatically.

## Validation and reversible rollout

The source/backup stage passed **458 tests plus 136 subtests**, and
**10 backup tests**. Repair CI for code commit
`5c15ff25498d1059079e54fb2fd1954e56d93ed6` passed (run 45915212683).
The subsequent classification repair passed **460 tests plus 138 subtests**
locally, with all **10 backup tests**; its CI passed for
`2e161ab62eb493e2c5f3871fe6842219f86ec8e7` (run 45917296768).
The final shared classifier/member implementation passed **461 tests plus 138
subtests** locally and on the Azure staging release, with **10 backup tests**.
CI passed for `55404e2b417b06959ad979b75e686ff63e7ff3d6`
(run 45917962630). Its live staged Atlassian collection still returned all 221
identities; four passed the personal filters, and the marketing example was
excluded by both pipelines.
Before rollout, consistent snapshots of all three production databases were
copied off the VM. Compressed and raw SHA-256 hashes, SQLite integrity and all
table row counts matched after local extraction. The private proof and copies
are under `work/maintenance/nov26-followup` and `work/private`; no database or
credential material is committed.

Both release symlinks switched at an idle lock boundary. JSON configurations and
private environment files were preserved. Previous releases and unit drop-in
contents are retained under `/root/atlassian-member-backup-3cc0a135336e` for
code-only rollback. The final classification follow-up switched both releases
to `atlassian-{personal,member}-c5e9568842e1`; its immediate code/unit rollback
record is `/root/ai-marketing-c5e9568842e1`. The verified three-database off-VM
snapshot preceded this maintenance rollout; the running member-inclusive daily
backup was not interrupted by either code switch. Never restore old SQLite data
as a routine code rollback.

Final production acceptance at 00:57:55 UTC on November 27 (November 26 Pacific):

| Evidence | Actual result |
| --- | --- |
| Final personal runs | 18471 and 18472 completed; Atlassian returned 221 records in each, zero source failures for that adapter |
| Final member runs | 966, 967 and 968 completed; 968 included the three existing access-restricted Workday failures |
| Delivery queues | No pending notifications or failed deliveries in either latest run |
| Source recovery | Discord acknowledged `source:atlassian-direct` recovery; receipt `1575667959815348346` |
| Corrected persisted job | The marketing example now has `classification=exclude`, with the same identity, first-seen time and earlier delivery receipt |
| Backup | Actual systemd local backup completed 00:17:07–00:45:01 UTC, exit 0; primary, maintenance and member table hashes verified |
| Supervisor | Completed at 00:57:48 UTC; fresh valid local restore proof, no open critical tickets or delivery failures; independent monitor configured |
| Runtime | Both live releases' application modules and backup code match the final tested code; all 16 webhook route mappings retained |
| Disk | 18 GiB available after backup, 73% used |

The primary worker is still **degraded**, with 47 existing failed sources. The
three member Workday access restrictions are checked on their slower configured
cadence, so intervening successful polls do not establish restored coverage.
The primary validation-due queue rose from 2,591 at initial observation to 2,944;
the member queue fell from 1,421 to 1,345. Existing validation-lag/growth issues
remain open for throughput review. These repairs do not establish that every
source is healthy or every link is verified. Final personal poll durations were
345 and 247 seconds; the cold member classifier run took about 142 seconds and
subsequent runs about 49 seconds. Shared locking prevents overlap but can delay
the next nominal five-minute start. Upstream feed delays remain additional.

The source and local-backup repair tickets resolved under the real supervisor.
The classification repair has an evidence-backed resolved audit ticket,
`classification:ai-marketing-tools`. The completed agent review was recorded as
the service account. Automatic off-host backup remains unconfigured; the
predeployment copies on the owner's computer are separate from that outstanding
scheduled-bucket setup. Private detailed evidence is in
`work/maintenance/nov26-followup`; no secret or SQLite contents are published.

## Review scope and remaining cursor

Read live source health, completed personal/member runs, maintenance tickets,
notification receipts, daily restore proof, disk/memory and GitHub CI. Existing
access-restricted sources remain incomplete; warnings are not proof that the
whole worker is down. Existing Atlassian destination-baseline review remains
separate from the repaired collection failure. Old Mission remains outside this
repair at the owner's request.

Verified Simplify's canonical public repositories remain unarchived with default
branch `dev` and feed path `.github/scripts/listings.json`:

| Feed | Latest observed feed commit | Commit time (UTC) |
| --- | --- | --- |
| New-Grad-Positions | `f988c4244f4c65aff443246299d33f218249bd4a` | November 26, 23:01:19 |
| Summer2027-Internships | `a04f359309761b12410ee43f817ab7aed06bc6bd` | November 26, 22:31:48 |

The actual scheduled member feed collections were successful. Five-minute
polling still cannot eliminate upstream feed delay. This was a targeted review
of Atlassian's official destination, not a new audit of every employer.
Dependency PRs #1, #2 and #5 have passing existing checks; they were inventoried,
not comprehensively reviewed or merged. Remaining review cursor includes those
dependency proposals, Trexquant's 404, MSCI schema evidence, the Atlassian
destination baseline and incomplete direct business/consulting coverage.

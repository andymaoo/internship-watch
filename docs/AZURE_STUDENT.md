# Azure student deployment preparation

This is the proposed first-year host, not an existing deployment. No subscription, server or paid resource was created. [HOSTING.md](HOSTING.md) contains the measured sizing, complete estimate, primary sources and expiry tradeoffs.

## User account steps

1. Open [Azure for Students](https://azure.microsoft.com/en-us/free/students) and choose **Start free**. Complete Microsoft sign-in and academic verification in the provider's page. Use the full student offer with $100 credit, not Students Starter. GitHub Education approval is not needed for this direct route. Do not provide a password or verification code in chat.
2. Verify that the subscription shows the student credit, its expiry, and the eligible free services. Leave spending protection enabled and do not upgrade to pay as you go. Confirm the free **B2ats_v2** VM hours and **64 GiB P6** disk allowance before creating the proposed resources. Subscription/region quota can prevent creation even when the public offer advertises a size; inspect it before changing plans.
3. Use a supported provider login or SSH connection for setup. The only later host details needed are its SSH username/address and an authorized public-key connection. Keep the private SSH key locally. The existing private GitHub repository and local source package avoid any need to paste a GitHub token into chat or cloud-init.
4. Separately sign in to [Healthchecks](https://healthchecks.io/) and verify the email address that should receive independent alerts. Create the scraper and backup checks described in [CONNECTIONS.md](CONNECTIONS.md); put their ping URLs in the existing private `.env` fields below. A dedicated private [Backblaze B2](https://www.backblaze.com/cloud-storage) bucket and bucket-scoped key are the proposed off-host destination; another user-controlled S3 destination can be substituted after reviewing cost.

## Proposed resource settings

| Setting | Proposed value |
|---|---|
| Subscription | Azure for Students, spending protection retained |
| Dedicated resource group | `internship-watch` |
| Region | East US if available under the student quota; reprice/recheck any alternative |
| Image | Ubuntu Server 24.04 LTS x64, ordinary free image, no paid marketplace software |
| Size | Standard_B2ats_v2, 2 vCPU / 1 GiB, normal allocation (not Spot) |
| OS disk | One 64 GiB Premium SSD P6 LRS, **only after verifying the free allowance**; ordinary managed persistent disk |
| Network | One ordinary VNet/subnet/NIC and one regional Standard IPv4 |
| Inbound | SSH port 22 restricted to the user's current public IP; key authentication |
| Extras | No paid NAT Gateway, Bastion, load balancer, Azure Backup vault, paid monitoring workspace, or public HTTP port |
| Runtime | Supplied systemd worker, five-minute polling; daily independent backup timer |
| State | `/var/lib/internship-watch/jobs.sqlite3`, migrated from the current consistent snapshot |

The first-year VM/disk allowances make IPv4 the approximately $3.65/month Azure debit (730-hour month), covered by the $100 credit if it is not consumed elsewhere. Expected B2 overage at current size is approximately $0–$0.03/month outside Azure credit. If the disk allowance is missing, stop before creation and use the documented E4 alternative only after checking its extra I/O charges. After 12 months, the unchanged P6 configuration is approximately $20.72/month before renewed credit and extras; arrange a cost review and migration/renewal decision before then. The $100 student renewal is not evidence of renewed free VM/disk hours.

## Private secret locations

On this PC, edit the existing file:

`C:\Users\o3ti3\Documents\Codex\2026-09-18\c\work\job-scraper\.env`

`DISCORD_WEBHOOK_URL` is already saved and tested; leave it intact. Fill `HEALTHCHECKS_PING_URL=` for the five-minute scraper check and `BACKUP_HEALTHCHECKS_PING_URL=` for the separate daily backup check. Email is configured and verified in Healthchecks, not in this file. The B2 fields are `RESTIC_REPOSITORY`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` and `RESTIC_PASSWORD_FILE`; the last points to a separate private encryption-password file. None of these values belong in the repository, report or chat.

On Linux, use `/etc/internship-watch.env` for the worker and `/etc/internship-watch-backup.env` for backups. Install the code, persistent database, permissions, service and timer using [DEPLOYMENT.md](DEPLOYMENT.md) and [CONNECTIONS.md](CONNECTIONS.md). Migrate the supplied SQLite snapshot before the first collection so acknowledged Discord messages and the initial digest stay suppressed.

## Host acceptance before declaring deployment

Measure consecutive naturally scheduled runs with every enabled source after the final release is installed. Record source counts, cycle timing, CPU-credit trend, total/peak RAM including the OS, database/WAL/disk growth, validation queue count and age, and discovery-to-decision latency. Confirm the VM finishes cycles inside five minutes without exhausting credits or swapping. The previous Windows measurements are planning evidence, not a result from this Azure machine.

Then test real Discord delivery and durable failed-delivery retry, one controlled source outage and recovery, service restart and host reboot with stable IDs and outbox, remote encrypted backup plus independent restore, and Healthchecks email failure/recovery after actually stopping the worker beyond its deadline. Configure credit/budget notifications in Azure and verify the free-service counters after first usage. Do not declare success from merely creating resources or seeing the process running.

Access the updated private report through the SSH tunnel or SFTP instructions in [DEPLOYMENT.md](DEPLOYMENT.md). Update and stop commands are in [OPERATIONS.md](OPERATIONS.md). Stopping the worker does not stop Azure resource charges; deallocating a VM can still leave billable disks/IPs. Preserve and verify off-host backups before intentionally retiring resources.

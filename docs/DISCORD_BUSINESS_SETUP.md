# Discord setup for business categories

Setup completed November 26, 2026. All four channels and incoming webhooks are
live; both Azure workers loaded sixteen route mappings. Each channel was verified
synced to its existing member-readable, read-only category permissions. Each
received one labeled routing test, with Discord receipt and visible UI checks.
Controlled failed-delivery retry and a fresh-process duplicate check passed.
No further owner setup is needed for these feeds. Instructions below remain a
reference for future credential rotation. Temporary local URL transfer values
were cleared after verification; active credentials are in Azure's root-only
/etc/internship-watch-member.env, not in this repository.

| Channel | Verified channel ID | Test message receipt |
| --- | --- | --- |
| intern-consulting | 1575439089769910333 | 1575443504094646284 |
| new-grad-consulting | 1575439417105981480 | 1575443499409477634 |
| intern-strategy-and-business-analysis | 1575439282905288765 | 1575443496960139267 |
| new-grad-strategy-and-business-analysis | 1575439610287235122 | 1575443501523673242 |

Keep the existing twelve feed webhooks, #watch-ops and #watch-digest unchanged.
Technical product-management roles continue to use intern-pm and new-grad-pm.

Create four text channels under the existing public-to-server Internships and
New Grad categories. Sync category permissions: @everyone can View Channel and
Read Message History, ordinary members cannot Send Messages or create threads.
Keep operations and digest channels private. Paid Whop access is not configured.

| Channel | Private JSON routing key |
| --- | --- |
| intern-consulting | intern-consulting |
| new-grad-consulting | new-grad-consulting |
| intern-strategy-and-business-analysis | intern-strategy-and-business-analysis |
| new-grad-strategy-and-business-analysis | new-grad-strategy-and-business-analysis |

Technology and strategy consulting share consulting channels. Product strategy
and business analysis share strategy-and-business-analysis channels. The four
classification categories remain distinct in stored records; shared channels do
not merge positions or suppress different jobs. The earlier eight-route layout
is superseded. No automatic channel-name lookup is used: webhook mapping is explicit.

In Discord: Server Settings -> Integrations -> Webhooks -> New Webhook. Select
one corresponding channel for each webhook. Copy each URL only to its matching
field in the root-only Azure file /etc/internship-watch-member.env, using sudoedit.
The existing MEMBER_DISCORD_WEBHOOKS_JSON value is one quoted JSON object. Add
the four keys above to that existing object; do not replace its twelve existing
entries. Do not paste URLs into chat, commit them, or share them with members.
Keep root ownership and mode 0600 on the file.

An empty template for only the four additions is at
work/private/business-webhooks.template.json on this computer. It contains no
credentials and is not loaded automatically. Enter URLs privately; ask the agent
to merge and validate them on Azure when ready. This requires no new bot token.

Until these destinations exist, eligible messages for those categories stay
queued. Existing categories remain usable. After configuration, verify webhook
server/channel IDs and a labeled test per new channel, then retry queued
unconfigured deliveries under the shared collection lock. Do not reset delivered
records, baseline flags or new-job dedupe keys to force messages to appear.

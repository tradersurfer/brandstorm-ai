# Privacy — BrandStorm AI plugin (v0.3.0)

Local prototype. No accounts, no personal data, no connected-account
data (books, Drive, email, social accounts, or similar) is shipped
with this plugin or collected by it. The installer supplies their own
brief on install / at run time — industry, region, states, Nice Class
— and nothing is pre-filled. The demo and tests use only fictional
inputs and obviously fake strings.

## What is NOT collected or shipped

- Any personal name, address, email, phone number, or account of any
  person — including the author's own accounts. The author's
  Meta/Facebook/Instagram connections belong to Muse, NOT to this
  plugin, and are never used here.
- Any private business information, client data, prices, offers,
  service lists, locations, or client lists.
- Any `.env` file, credential, API key, token, or login.
- Any log, screenshot, or file from a private machine or profile.
- Any domain, handle, or trademark registration — the plugin only
  *checks* availability; it never registers anything.

## What the plugin sends, and to whom (network calls, disclosed)

Every network call is a public availability check, and only the
candidate name (and, for Tier 2, the Nice Class) is sent:

| Tier | Call | Data sent |
|---|---|---|
| 1 Domain | DNS-over-HTTPS to Google (`dns.google/resolve`) with Cloudflare fallback — keyless until a GoDaddy key exists | The candidate domain name (e.g. `cascaderidge.com`) |
| 2 USPTO | Trademark Search companion API behind `tmsearch.uspto.gov` — keyless, undocumented; an official USPTO key is optional | The candidate name + target Nice Class |
| 3 State registries | None. Portals are form/session-gated, so the plugin returns manual-check links only — it never queries a portal | Nothing |
| 4 Social | Public profile-page HTTP checks on X, YouTube, Facebook, LinkedIn company pages | The candidate handle (e.g. `cascaderidge`) |

No other network calls are made. There is no telemetry, no analytics,
no crash reporting, and no retention: run results live only in the
local `data/results.json` file on the machine that ran the brief, and
the dashboard serves them only on localhost.

## Keys

Optional keys (GoDaddy, USPTO, LLM) are declared in `plugin.yaml`
as `type: secret` with an `env:` name. They are stored in the
installer's own Hermes secret scope / `.env`, are never written to
`config.yaml`, never logged, never echoed in errors or results, and
never committed. The plugin works fully keyless without them — Tier 1
falls back to DNS-over-HTTPS, Tier 2 to the keyless companion API,
and generation is combinatorial with no model key.

## Honesty rule (standing)

A tier that cannot check reports `unknown` with the reason — never a
fake clear. Instagram, TikTok, and LinkedIn personal profiles return
no server-side signal and are reported unknown; display-name checks
are unknown on all platforms; Tier 3 is always a manual check in
v0.3. Unknown never changes a badge.

## Before any public submission

Run the local privacy check and review the diff by hand. If a private
value ever appears, remove it before committing — a catalog pin is a
full commit SHA, and reviewers read exactly that commit.

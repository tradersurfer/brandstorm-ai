# BrandStorm AI — Key Setup Guide (v0.3)

> **Who owns the keys? NOBODY at BrandStorm does — there is no
> hosted backend and no hosted key store.** BrandStorm AI is a local
> prototype / Hermes plugin that runs on the installer's own machine.
> Every key below belongs to the installer: it is created in the
> installer's own account, stored in the installer's own Hermes
> install (Hermes config / environment variables), and never sent to
> BrandStorm or to any BrandStorm server — there is no server.
> Never paste a key into chat, a ticket, or a shared doc, and never
> commit one to the repo.

## The short version

BrandStorm works out of the box with **zero keys**. Keys are optional
per-tier upgrades, never a prerequisite:

| Tier | With zero keys (today) | With a key (upgrade) |
|---|---|---|
| 1 Domain | Keyless DNS-over-HTTPS (likely available, not a guarantee) | GoDaddy API — authoritative registrar answer |
| 2 USPTO | Companion API (unofficial, no key) | TSDR API — official verification by serial number |
| 3 State | Manual check links | No key exists for this — manual links stay |
| 4 Social | HTTP-status checks (X, YouTube, Facebook, LinkedIn company) | Meta / TikTok / LinkedIn APIs — **not built yet** |
| Generator | Combinatorial word bank | LLM key — **not built yet** |

How a Hermes agent walks the user through any key below: the agent
asks which upgrade the user wants, tells them exactly where to create
it in their own account, waits while they create it, then tells them
where to paste it — and then runs a check that reports only
"keyed" / "keyless", never the key value.

## Where keys go

Set them as environment variables in the shell / Hermes install
that runs BrandStorm, then restart the server (or re-run the CLI):

```bash
export BRANDSTORM_GODADDY_KEY="..."
export BRANDSTORM_GODADDY_SECRET="..."
export BRANDSTORM_USPTO_KEY="..."
export BRANDSTORM_LLM_KEY="..."
```

In a Hermes install, the same values go in the plugin's config
fields (the Hermes config screen) instead of the shell. Either way
they live only on the installer's machine. Check what BrandStorm
sees — labels only, never values — with:

```bash
python3 -c "from brandstorm.keys import keys_status; print(keys_status())"
# {'domain': 'keyless', 'uspto': 'keyless', 'state': 'keyless', 'social': 'keyless', 'llm': 'keyless'}
```

To remove a key, unset the variable (or clear the Hermes config
field) and restart. BrandStorm falls back to the keyless path.

**Never log a key value — not even partially.** The code never
prints one; don't paste one into a log, a screenshot, or chat
either. If a key leaks, revoke it in the provider's dashboard and
create a fresh one.

---

## 1. GoDaddy — Tier 1 (domain availability)

**What it unlocks:** authoritative domain availability from the
registrar instead of DNS inference. A "taken" / "available" answer
from GoDaddy is a registrar answer; DNS can only say "no DNS
presence found".

**What the agent asks first:** "Do you have a GoDaddy account with
domains on it?" The availability API is reported to need an account
with 50+ domains (some sources say only *bulk* availability checks
need that — verify at signup). If the account doesn't qualify,
stay on the keyless DNS path; it works fine.

**Create it (in your own GoDaddy account):**

1. Sign in at [developer.godaddy.com](https://developer.godaddy.com/)
   with your own GoDaddy account.
2. Open **API Keys** (developer.godaddy.com/keys) and create a
   **Production** key. (There is a separate OTE/test environment at
   api.ote-godaddy.com; OTE keys do not work against production and
   vice versa. BrandStorm uses production.)
3. Copy the **Key** and the **Secret** shown once at creation.
   The secret is shown only once — save it somewhere safe
   (a password manager), not in the repo.

**Paste it:**

```bash
export BRANDSTORM_GODADDY_KEY="<your key>"
export BRANDSTORM_GODADDY_SECRET="<your secret>"
```

Both must be set; one without the other counts as absent and the
keyless DNS path is used. Restart the server / re-run the CLI.

**What BrandStorm does with it:** `GET
https://api.godaddy.com/v1/domains/available?domain={name}&checkType=FAST&forTransfer=false`
with header `Authorization: sso-key {KEY}:{SECRET}`. On any error
(auth failure, 4xx/5xx, timeout) that TLD reports **unknown** with
the reason — it never silently falls back to DNS, so the dashboard
method label stays honest.

**Status: implemented, needs a live key to verify.** No GoDaddy key
exists yet, so the keyed path has never run against the real API.
Note: GoDaddy's developer landing page now fronts a v3 API
(Bearer PAT, `GET /v3/domains/check-availability`) while v1/sso-key
remains the documented path for a key+secret pair. If GoDaddy
retires v1/sso-key, the keyed path will need a PAT-based update.

**Namecheap is NOT an option:** the account checked does not
meet Namecheap's API requirements, so no Namecheap path is built.
Do not offer it as an alternative.

---

## 2. USPTO TSDR — Tier 2 (trademark verification)

**What it unlocks:** official verification of each trademark match
against USPTO's Trademark Status and Document Retrieval (TSDR) API
instead of trusting the unofficial companion API alone.

**Know this first:** TSDR has **no wordmark-search endpoint**. It
is identifier-driven retrieval only — you look a case up by its
serial number. So the key does not replace the search: the companion
API still finds candidate marks, and TSDR then verifies each match
by serial number. If TSDR verification fails, the tier reports
**unknown**, never a companion-only result labelled "TSDR".

**Create it (in your own USPTO account):**

1. Create / sign in to a free USPTO account at
   [account.uspto.gov](https://account.uspto.gov/).
2. Open the **API Manager** (account.uspto.gov/api-manager) and
   request a key for the **Trademark Status and Document Retrieval
   (TSDR)** API product.
3. Copy the key. It is a TSDR key, not a patent (ODP) key — the two
   are not interchangeable and must not be sent to each other's
   hosts.

**Paste it:**

```bash
export BRANDSTORM_USPTO_KEY="<your TSDR key>"
```

Restart the server / re-run the CLI.

**What BrandStorm does with it:** for each companion match,
`GET https://tsdrapi.uspto.gov/ts/cd/casestatus/sn{serial}/info`
with headers `USPTO-API-KEY: {key}` and `Accept: application/json`.
Published rate limits: 60 requests/key/minute (peak), 120
off-peak. Matches verified this way carry `tsdr_verified: true`
in the results JSON.

**Status: implemented, needs a live key to verify.** No key exists
yet to test with — a dev-portal key is still in progress, so the
keyed path has never run against the real TSDR API.

---

## 3. Meta / Instagram — Tier 4 (not built yet)

**What it would unlock:** real Instagram + Facebook handle and
display-name checks via the Instagram Graph and Facebook Graph
APIs, replacing the current "unknown, never guessed" for Instagram
and the login-redirect signal for Facebook.

**Status: no client exists yet.** Do not create a key for
BrandStorm until the client is built. When it is, the reserved
env names are:

- `BRANDSTORM_META_APP_ID` / `BRANDSTORM_META_APP_SECRET` (reserved
  — no client reads them yet)

**Where you would create it (your own account):**
[developers.facebook.com](https://developers.facebook.com/) — create
a free Meta developer app, add the Instagram Graph / Facebook Graph
products. Instagram Graph needs an Instagram Business or Creator
account linked to a Facebook Page; some Facebook Graph endpoints
need app review. Verify the exact permissions at signup.

**Important:** Meta/Facebook/Instagram connected via Muse
connectors are **NOT used by the plugin**. The plugin never
touches anyone's Muse-connected Meta accounts; a
future Meta client would use the installer's own developer app
only.

---

## 4. TikTok — Tier 4 (not built yet)

**What it would unlock:** real TikTok handle / display-name checks.

**Status: no client exists yet.** Reserved env name (no client
reads it yet): `BRANDSTORM_TIKTOK_KEY`.

**Where you would create it (your own account):**
[TikTok for Developers](https://developers.tiktok.com/) — free
developer account. Handle-availability endpoints are limited;
verify at signup what is actually checkable before building
against it.

---

## 5. LinkedIn — Tier 4 (not built yet)

**What it would unlock:** real LinkedIn profile/company handle
checks, replacing the current HTTP 200/404 company-page signal
and the "unknown" for personal profiles.

**Status: no client exists yet.** Reserved env name (no client
reads it yet): `BRANDSTORM_LINKEDIN_KEY`.

**Where you would create it (your own account):**
[LinkedIn Developers](https://www.linkedin.com/developers/) — free
developer app. Company/profile search endpoints are restricted
and need approval; verify at signup.

---

## 6. LLM — name generation (not built yet)

**What it would unlock:** model-generated names to replace or
augment the combinatorial word-bank generator.

**Status: no client exists yet.** The env name is already read by
`brandstorm/keys.py` (presence only — it changes the dashboard
label), but nothing generates with it yet:

```bash
export BRANDSTORM_LLM_KEY="<your provider key>"
```

**Where you would create it (your own account):** your LLM
provider of choice (e.g. OpenRouter — free-tier models turn over
fast, re-verify the free lineup live before relying on it). Paid
tiers are per-token; verify pricing at signup. The key belongs to
the installer's own provider account, as with every key above.

---

## Troubleshooting

| Symptom | What it means | Fix |
|---|---|---|
| Dashboard still says "keyless (DNS)" after setting GoDaddy vars | The server/CLI was started before the vars were set, or only one of key/secret is set | Set **both** vars, restart the process |
| Domain TLDs report "unknown" with a GoDaddy auth error | Key/secret wrong, OTE key used against production, or the account doesn't meet the API requirements | Re-copy from developer.godaddy.com (Production key), verify account eligibility |
| USPTO tier reports "unknown" with a TSDR error | Key wrong / not a TSDR key, or TSDR rate limit (60/min peak) | Check the key is a TSDR key from account.uspto.gov/api-manager; wait and retry |
| `keys_status()` shows "keyed" but results say "companion" | Stale `data/results.json` from a keyless run | Re-run the brief; the dashboard shows the latest run only |
| Any key leaked | Assume it is compromised | Revoke it in the provider dashboard, create a fresh one, update the install — never reuse the leaked one |

## Key inventory (what exists, what doesn't)

- GoDaddy key/secret: **does not exist yet** — in progress.
- USPTO TSDR key: **does not exist yet** — dev-portal
  request in progress.
- Meta / TikTok / LinkedIn keys: **do not exist** — no clients yet.
- LLM key: **does not exist** — no client yet.
- Namecheap API: **not an option** (account doesn't
  meet requirements).

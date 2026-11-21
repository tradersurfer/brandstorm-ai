# BrandStorm AI — Production & Hermes Submission Checklist

What it takes to run this at production level and be ready for Hermes
submission and merge. Written 2026-11-12 against the v0.2 repo's ACTUAL
state; updated 2026-11-13 for v0.3 — nothing here is claimed done
unless it is done.

## Status snapshot (v0.3, 2026-11-13)

| Area | Status |
|---|---|
| Name generation (combinatorial, brief-driven) | DONE — generic, no hardcoded anchors |
| Tier 1 Domain (keyless DNS-over-HTTPS) | LIVE, inference only; GoDaddy keyed path implemented, needs a live key to verify |
| Tier 2 USPTO (tmsearch companion API, no key) | LIVE, unofficial; TSDR serial-verification path implemented, needs a live key to verify |
| Tier 3 State registries (Playwright adapters, 8 states) | BUILT but BLOCKED live — every portal attempt returns unknown in the VM (AZ CAPTCHA, CA blocked, FL/NY navigation, TX no public search, DC 0×0, MD no render, VA cookie gate); manual links remain; laptop re-test pending |
| Tier 4 Social (X, YT, FB, LinkedIn company) | PARTIAL live — IG/TT/profile + display name unknown |
| Dashboard + run-a-brief form | DONE — Light/Dark/System theme, light default, readability pass |
| Zero-key-first UX (keys optional, never logged) | DONE — `brandstorm/keys.py`, per-tier method shown honestly |
| Unit tests (no network) | DONE — 117 tests, all passing |
| Example + sample briefs, labeled | DONE |
| Privacy: no secrets, no personal data in repo | DONE (private files moved out in v0.2; `PRIVACY.md` added in v0.3) |
| Hermes plugin packaging (plugin.yaml, tools) | DONE — `hermes doctor` / `validate` still to run on the laptop |
| API keys | GoDaddy in progress; USPTO dev portal in progress; Namecheap NOT an option (account doesn't meet requirements); Meta via Muse connectors only — NOT used by the plugin |
| Production hosting / auth / rate limits | TODO — local server only |

---

## (a) API keys & accounts needed

Each row: what it unlocks, and what is known about cost/access.
Anything marked "verify at signup" was NOT verified in this build —
do not quote it as fact.

| Account / key | Unlocks | Access notes |
|---|---|---|
| **GoDaddy API key** | Authoritative domain availability + Broker/Premium pricing for Tier 1. Turns DNS inference into a registrar answer. Keyed path implemented in v0.3 (v1/sso-key) — needs a live key to verify. | GoDaddy account in progress. API access itself is free with an account; availability checks are free — verify at signup. **Namecheap is NOT an option** — the account checked does not meet Namecheap's API requirements, so no Namecheap path is built. Open questions: v1/sso-key vs v3/PAT auth for fresh accounts; whether the availability endpoint needs 50+ domains on the account — verify at signup. |
| **USPTO account + TSDR API key** (account.uspto.gov) | Official verification of companion-API matches by serial number for Tier 2. Note: TSDR has NO wordmark-search endpoint — it cannot replace the companion API as the discovery path, only verify matches. | USPTO dev-portal request in progress. USPTO developer accounts are free; TSDR API access is free — verify at signup. Keyed path implemented in v0.3, needs a live key to verify. |
| **Meta developer app** (Instagram Graph + Facebook Graph APIs) | Real Instagram + Facebook handle/display-name checks for Tier 4. | Free developer app; Instagram Graph needs an Instagram Business/Creator account linked to a Facebook Page; Facebook Graph needs app review for some endpoints — verify at signup. NOTE: Meta/Facebook/Instagram accounts connected via Muse connectors are NOT used by the plugin — a future Meta client would use the installer's own developer app only. |
| **TikTok developer account** | Real TikTok handle/display-name checks for Tier 4. | Free developer account; handle-availability endpoints are limited — verify at signup. |
| **LinkedIn developer app** | Real LinkedIn profile/company handle checks for Tier 4. | Free developer app, but company/profile search endpoints are restricted and need approval — verify at signup. The current company-page check (HTTP 200/404) works without a key but is unofficial. |
| **LLM provider key** (e.g. OpenRouter) | Model-generated names to replace/augment the combinatorial generator. | Free-tier models existed at last check (Nov 5, 2026: Nemotron 3 Ultra free, GLM Flash free — from the CEO Pack live model check). Free lineups turn over fast — RE-VERIFY live before relying on them. Paid tiers are per-token; verify pricing at signup. |
| **GitHub account** (`tradersurfer93`) | Public repo for the plugin + catalog PR. Catalog entries can only be submitted by the owner or a major contributor. | Already exists. No cost for a public repo. |

**What you do NOT need to buy:** no domains, no handles, no servers
to start. The prototype runs on localhost with stdlib Python.

## (b) Engineering still needed

- **State registry automation, continued** — Playwright adapters exist
  for 8 states (AZ, CA, TX, FL, NY, DC, MD, VA) but every portal
  blocked the automated browser in the VM (AZ CAPTCHA, CA blocked,
  FL/NY navigation failures, TX no public search, DC 0×0 input, MD no
  render, VA cookie gate). Next: re-test on the laptop (normal
  network, no sandbox MITM proxy — FL/NY failures may be sandbox
  artifacts); where a portal stays blocked, keep manual links and
  consider state bulk-data feeds. The sweep already stops after 2
  consecutive blocks instead of hammering a portal.
- **Rate-limit & backoff policy** — the live tiers currently have no
  retry/backoff. Add per-tier budgets, exponential backoff on
  429/403/999, and a per-run cap. USPTO's companion API and the
  social platforms WILL rate-limit a 100-name batch run at production
  volume; a run that hits a limit must report "unknown" with the
  reason, never a fake clear.
- **Caching** — cache domain/USPTO/social results per (name, class)
  with a TTL (e.g. 24h) so re-runs and watchlists don't re-hit every
  endpoint. Cache must be local to the install, never shared.
- **Verify the keyed paths live** — GoDaddy (v1/sso-key vs v3/PAT) and
  TSDR (serial verification) are implemented but have never run
  against a real API. Run both with real keys and record the outcome;
  until then Tier 1 stays DNS inference and Tier 2 stays companion
  API in production terms.
- **Harden the Facebook check** — the final-URL signal works today
  (verified 2026-11-12) but Facebook changes login flows often. Treat
  it as a soft signal: on any unexpected redirect shape, return
  "unknown", not "taken"/"free".
- **LLM generator** — wire a model key behind `generator.generate`
  with the word-bank generator as fallback/offline mode. Validate
  model output the same way: compound only, anchor token present,
  unique in batch.
- **Error handling & run durability** — a run that crashes mid-way
  currently loses partial results. Persist per-candidate results as
  they complete; resume a failed run instead of restarting it.
- **Server hardening** — `api/server.py` is a localhost demo server
  with no auth. A hosted version needs auth, per-user rate limits,
  and input validation on inline briefs (size caps on batch, anchors,
  and geography text). Do NOT expose the current server publicly.
- **Integration tests** — the unit suite is no-network only. Add a
  small live smoke test (5 names, all tiers) that runs on demand and
  reports per-tier live/stubbed, plus a fixture-based test for the
  dashboard form.
- **Registry URL maintenance** — re-run
  `python3 -m scripts.verify_registries` on a schedule. 12 of 51 SOS
  hosts close automated connections from this VM; 5 URLs were
  corrected to SOS homepages in v0.2 after 404s. Treat the map as
  living data, not a one-time table.

## (c) Hermes plugin packaging — DONE in v0.3 (laptop validation pending)

Modeled on the CEO Pack plugin (the author's shipped Hermes plugin —
`~/workspace/ceo-pack/`, `plugin.yaml` v0.4.0, 14 tools). What v0.3
shipped, in this repo:

- **Plugin manifest (`plugin.yaml`)** — name `brandstorm`, version
  `0.3.0`, description, author `tradersurfer93`, license MIT,
  `requires_hermes: ">=0.21.6"` (copied from ceo-pack), `provides_tools`
  (4 tools), `config_schema` (all optional, nothing pre-filled; the
  four key fields are `type: secret` with `env:`).
- **Tools** (`plugin/tools.py`, thin wrappers over the existing
  pipeline — no forked logic): `brandstorm_brief` (validate/build a
  brief from user input), `brandstorm_run` (generate + clear a batch),
  `brandstorm_results` (read the shortlist + per-tier evidence),
  `brandstorm_state_links` (manual-check links for requested states).
  Each tool declares its arguments and returns structured results —
  no free-text guessing.
- **Config schema** — the installer enters their OWN industry, region,
  states, and class at install time. Nothing is pre-filled: no
  business name, no location, no anchors, no API keys shipped in the
  repo. API keys (GoDaddy, USPTO, social, LLM) go in config as
  optional secret fields the user fills in after install — never
  committed, never logged. **Open question:** the `type: secret` +
  `env:` shape follows the community Hermes plugin guide, NOT the
  upstream Nous source — `hermes plugins validate .` on the laptop is
  the deciding check.
- **Network use, declared honestly** — unlike CEO Pack (no network),
  BrandStorm MUST make live HTTP calls (DNS, USPTO, social). The
  manifest/docs say so, list every endpoint family, and state that no
  user data is sent anywhere except the public availability checks
  themselves (a candidate name + class is the only thing sent, and
  only to the check endpoint). See `PRIVACY.md`.
- **No data retention** — runs live in the install's local data
  folder only. No telemetry, no account, no cloud copy. `PRIVACY.md`
  lists what is excluded: API keys, personal names, business data,
  logs, and any private name-check files.
- **Install flow** — install by name from the catalog; on first run,
  prompt for the brief (industry, region, states, class, anchors) and
  offer the labeled sample brief as a one-click demo. A first run
  must complete offline-safe: if the network is unavailable, every
  tier reports unknown with the reason — never a fake result.
- **Validation steps (before any submission)** — run on the machine
  that will ship it (steps also in `docs/LAPTOP_TEST.md`):
  1. `hermes plugins doctor .` — clean.
  2. `hermes plugins validate . --install-deps` — clean.
  3. `python3 -m unittest discover -s tests -v` — all pass (114).
  4. Demo flow: `python demo/demo_flow.py` — fictional brief, no
     network beyond the live tiers, no credentials, end-to-end run
     producing a shortlist. (Verified in the VM: 5 names, 1 clean.)
  5. Test the demo flow 20x back-to-back after the final push and
     report results (CEO Pack's pre-submit bar — our own bar, NOT a
     Nous requirement).
  6. Privacy scan: grep the repo for secrets, keys, personal names,
     and private data; review the diff by hand before the push.
  - NOTE: steps 1–2 cannot run in the cloud VM (no Hermes binary
    here). The laptop's Hermes Desktop was reset/reinstalled
    2026-11-12, so verification may now be possible — run it on the
    laptop per `docs/LAPTOP_TEST.md`.

## (d) Submission checklist — regular catalog merge (NOT a hackathon)

The hackathon is over. There is no Typeform and no demo video for
Nous submissions anymore. Submission is a regular human-reviewed
catalog PR, per the catalog submission guide (verified 2026-11-13):
https://hermes-agent.nousresearch.com/docs/developer-guide/plugins/catalog-submission

How regular merging works: entries are added ONLY via a PR to the
`hermes-agent` repo, reviewed and merged by a maintainer — no
self-serve registry, no automated ingestion, no form. Every entry
pins a full 40-character commit SHA (branches, tags, and short SHAs
are rejected). The entry may be submitted by the plugin repo's owner
or a major contributor. Declared capabilities must match what the
plugin actually registers at the pinned commit, and `hermes plugins
validate` runs a security scan at admission (`dangerous` fails the
entry). The plugin's README at the pinned commit renders its catalog
page, and `screenshots:` in the entry fills the gallery. SHA bumps
are new PRs, re-reviewed like any other change.

- [ ] All of (b) that is marked production-blocking is done
      (at minimum: TSDR key wired OR the unofficial API risk
      disclosed in the docs, Playwright state checks for the top
      states OR manual links clearly labeled, rate-limit/backoff
      in place, LLM generator OR combinatorial generator clearly
      labeled as such).
- [ ] All of (c) validation steps pass, including the 20x demo run
      (our own pre-submit bar from CEO Pack, NOT a Nous requirement).
- [ ] `plugin.yaml` complete: name, version, author, license,
      `requires_hermes`, tools, config schema with no pre-filled
      personal data.
- [ ] `README.md`, `ARCHITECTURE.md`, `IDEA.md`,
      `PRODUCTION_CHECKLIST.md`, and `PRIVACY.md` current and
      consistent with the shipped code.
- [ ] Privacy scan clean; diff reviewed by hand.
- [ ] Push to the public repo (owner `tradersurfer93`); note the
      full 40-character commit SHA — catalog entries pin a full SHA,
      not a branch or tag. A SHA-bump is a new PR, so keep changes
      small after opening it.
- [ ] Catalog PR to the `hermes-agent` repo with the catalog entry
      (name, repo, full SHA, `requires_hermes`, capabilities,
      `screenshots:` with the dashboard screenshots). Write the
      disclosure lines in the PR description: live network calls
      (DNS, USPTO, social), no data retention, keys via Hermes
      config only. No Typeform, no demo video, no X post required
      for the submission itself.
- [ ] If the GitHub App route will not open a PR upstream, open the
      catalog PR manually from the fork's compare page in GitHub web.

## What the owner needs to have / decide

1. **Accounts:** GitHub (`tradersurfer93` — have), GoDaddy account (in
   progress — key/secret not yet created), USPTO account (dev-portal
   request in progress), Meta developer app, TikTok developer
   account, LinkedIn developer app, LLM provider account. Create
   them when the corresponding tier is built — not all at once.
   Namecheap is NOT an option (account doesn't meet its API
   requirements). Meta/Facebook/Instagram via Muse connectors are
   NOT used by the plugin.
2. **A healthy Hermes install** to run the live verification on
   (laptop was reset/reinstalled 2026-11-12 — verify per
   `docs/LAPTOP_TEST.md`).
3. **Decisions:** plugin name is `brandstorm` (decided in v0.3); free
   vs paid tiers (free single runs; paid for batch reports,
   monitoring, extension — only once tiers are authoritative),
   data-retention policy (local-only is the proposal).
4. **Nothing to buy yet.** Keys are created free; the only future
   costs are optional paid API tiers and paid LLM usage — verify
   pricing at signup before committing to any of them.

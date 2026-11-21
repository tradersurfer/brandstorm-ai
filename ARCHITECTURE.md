# BrandStorm AI — Architecture Handoff (Source of Truth)

**Project home:** BrandStorm AI side chat.
**Repo:** `~/workspace/brandstorm-ai/`
**Status:** v0.3 DONE 2026-11-13 (local only). Generic product; zero-key
first; Hermes plugin packaged (`plugin.yaml` brandstorm 0.3.0, 4 tools);
Playwright Tier 3 adapters built (portals block automation — see §3);
dashboard Light/Dark/System, light default.
**Last updated:** 2026-11-13

> This file is the working spec. If anything conflicts with it, this file wins
> until the owner says otherwise.

## Target Deliverable

Name-Storming & Automated Clearance Engine (Plugin / Web App).
Target platform: Browser Extension / Web Application Core.

## 0. Generic-by-design rule (v0.2 correction)

The product must work for a stranger anywhere. Nothing about the
author's location, businesses, or past clients is baked into the
product: no default geography, no default brand, no default anchors.
Anything from a past brief survives ONLY as a clearly labeled example
or test fixture (see "Examples policy" below). A user in Arizona who
installs this via Hermes sees sample data and their own brief — nothing
else.

## 1. Executive Summary & Core Problem Statement

Existing naming tools output taken or generic names without real-time legal or
technical verification. Founders end up generating 50–100 candidate names only
to find that 90%+ hit hard brick walls on active USPTO trademarks in their
class, unavailable .com domains, or taken social handles.

BrandStorm AI solves this by combining multi-direction AI generation with a
real-time 4-tier screening pipeline (Domain APIs, USPTO/Legal databases,
Secretary of State corporate filings, and Social Media handles) — all
driven by the user's own brief: their industry, their region, their
Nice Class.

## 2. Core Functional Requirements & User Input Schema (v2)

The plugin must accept structured parameters from the user before launching
the generation loop. Example — the labeled sample brief shipped with
the repo (a Phoenix, Arizona specialty coffee roastery; replace it
with your own):

```json
{
  "industry": "Specialty Coffee Roastery",
  "geographic_scope": "Phoenix, Arizona / US National",
  "states": ["AZ"],
  "brand_aesthetic": ["Rustic", "Artisan", "Modern", "Minimalist"],
  "direct_anchor_rules": {
    "must_include_exact_variations": ["Desert Roast", "Sonora Roast", "Desert Roast Coffee"],
    "enforce_compound_structure": true
  },
  "candidate_batch_size": 50,
  "nice_class": "030",
  "tlds": ["com", "co", "studio", "supply", "app"]
}
```

Schema v2 changes:
- `geographic_scope` — free text describing where the brand operates.
- `states` — explicit list of US state/DC codes to check in Tier 3.
  If absent/empty, Tier 3 reports `not_requested` with guidance and
  NEVER silently defaults to any region.
- `nice_class` — the Nice Class as a string (e.g. `"025"`, `"030"`).
- `tlds` — which TLDs Tier 1 checks.

### Geography resolution (precedence)

1. Explicit `states` always wins.
2. Otherwise, region phrases in `geographic_scope` are resolved via
   the alias map (`brandstorm/regions.py`): "DMV" → DC/MD/VA,
   "California" → CA, "Pacific Northwest" → WA/OR, "New England" →
   CT/MA/ME/NH/RI/VT, full state names, and bare two-letter codes
   that are not common English words.
3. Nothing matched → no states → Tier 3 `not_requested`.

"US National" on its own resolves to no states: a national scope is
not a state filing.

## 3. Automated 4-Tier Real-Time Clearance Architecture

AI Generation Engine (50–100 structured candidates) feeds a parallel clearance
screening pipeline:

- **Tier 1: Domain APIs (GoDaddy/Namecheap)** — .com, .co, etc. Available /
  Taken / Broker-Premium.
- **Tier 2: USPTO Search (Nice Class / TESS)** — exact / phonetic match in
  the brief's class.
- **Tier 3: State Biz (Secretary of State corporate filings)** — the
  states the user asked for, from the all-50-states + DC registry map.
- **Tier 4: Social Audit (X, YouTube, Facebook, LinkedIn, IG, TikTok)** —
  username AND display name, exact and formatted handles.

Output: Filtered Output Dashboard — green 100% Clean | yellow Partial |
red Taken.

### Pipeline Tiers Defined

- **Tier 1: Real-Time Domain Verification** — pings GoDaddy/Namecheap APIs
  (`/v3/domains/check-availability`) for .com, .co, .studio, .supply, and
  .app. Classifies domain status into Available, Taken, or Broker/Premium.
  (v0.3: keyless DNS-over-HTTPS by default — strong signal, not a
  registrar guarantee. When `BRANDSTORM_GODADDY_KEY` +
  `BRANDSTORM_GODADDY_SECRET` are both set, the GoDaddy availability API
  (v1/sso-key, per GoDaddy's docs) is used instead; keyed errors report
  `unknown` and never silently fall back to DNS. The keyed path is
  implemented but needs a live key to verify — no key exists yet. Note:
  GoDaddy's docs now front a v3 API with Bearer PAT auth; v1/sso-key
  may not work for fresh accounts — verify at signup. See
  `docs/KEY_SETUP.md`.)
- **Tier 2: USPTO & Trademark Database Scraper / API** — automated
  exact-match, prefix-match, and phonetic checks against tmsearch.uspto.gov
  filtered specifically by the target Goods & Services class from the
  brief. (v0.3: companion API still discovers candidates keyless. When
  `BRANDSTORM_USPTO_KEY` is set, each match is then verified by serial
  against the official TSDR API (`GET tsdrapi.uspto.gov/ts/cd/casestatus/sn{serial}/info`,
  header `USPTO-API-KEY`) — TSDR has NO wordmark-search endpoint, it is
  identifier-driven retrieval only, so the companion API stays the
  discovery path. Any TSDR error makes the whole tier `unknown`, never
  companion-only results labeled "tsdr". Implemented, needs a live key
  to verify.)
- **Tier 3: Corporate Business Registry Scrapers** — checks the
  Secretary of State business search portals for exactly the states
  the user requested (all 50 states + DC in
  `brandstorm/clearance/registries.py`, with per-URL verification
  status in `registries_verification.json`). v0.3 adds Playwright
  adapters (`brandstorm/clearance/state_live.py`) for AZ, CA, TX, FL,
  NY, DC, MD, VA: each adapter fills the portal's entity-name search
  and parses found/not-found. HONEST OUTCOME (verified 2026-11-13 in
  the VM): **no portal returned a usable found/not-found answer.**
  AZ eCorp presents a 6-character image CAPTCHA on every submit; CA
  bizfile is security-service blocked; FL Sunbiz / NY DOS navigation
  never completes from this sandbox; TX SOSDirect has no public entity
  search; DC BOSS renders a 0×0 search input; MD submits with no
  visible result; VA SCC stalls behind the cookie-consent gate. Every
  live attempt therefore returns `unknown` with the specific reason
  plus the manual link — never a guess. The found/not-found parsing
  path is implemented and unit-tested against page-text fixtures only;
  the first live found/not-found is first-of-its-kind evidence and
  needs eyeballing. The batch sweep stops after 2 consecutive
  captcha/bot-blocks instead of hammering a blocked portal. Env
  kill-switch `BRANDSTORM_STATE_LIVE=0` forces manual-only. States
  without an adapter stay `manual`; a brief naming no states stays
  `not_requested`. NOTE: FL/NY navigation failures may be sandbox
  egress artifacts (the VM's MITM proxy) rather than real portal
  behavior — the laptop test phase must re-check which blocks are
  real. A live exact entity match makes a name partial at best (it
  cannot downgrade a USPTO conflict); fuzzy found, unknown, and manual
  never change a badge.
- **Tier 4: Social Media Handle Audit** — checks availability for exact
  and formatted handles (@name, @wearname, @name.co) across X, YouTube,
  Facebook, LinkedIn (company), Instagram, and TikTok — plus the
  spaced display name on each platform.
  - Username, LIVE: X and YouTube via HTTP status (404 = likely free,
    200 = taken); Facebook via final URL (login redirect = likely
    free, profile URL = taken); LinkedIn company pages via HTTP
    status (200 = slug taken, 404 = slug likely free).
  - Username, UNKNOWN (never guessed): Instagram, TikTok (login wall,
    200 for everything), LinkedIn personal profiles (HTTP 999 for
    everything).
  - Display name: UNKNOWN on all platforms in v0.2 (search pages are
    login/JS-gated or echo the query with no existence signal).
    Display-name checks are informational only and NEVER change a
    badge.

## 3A. Zero-key-first architecture + Hermes plugin (v0.3)

**Zero-key-first:** the product works out of the box with ZERO keys —
keyless DoH domains, unofficial USPTO companion API, HTTP-status social
checks, manual state links (plus Playwright attempts). Keys are optional
per-tier upgrades, never a prerequisite, and never a install-time wall:
- Tier 1: `BRANDSTORM_GODADDY_KEY` + `BRANDSTORM_GODADDY_SECRET` → GoDaddy
  availability API. Absent → keyless DoH.
- Tier 2: `BRANDSTORM_USPTO_KEY` → TSDR serial verification. Absent →
  companion API only.
- Generator / social APIs: env names reserved (`BRANDSTORM_LLM_KEY`),
  no clients yet — no key is asked for.
- Keys come from the installer's own Hermes secret scope / env vars
  (`brandstorm/keys.py` returns only `keyed`/`keyless` labels, never a
  value). They are never logged, never committed, never sent anywhere
  except the check endpoint itself. **Nobody hosts a backend and
  nobody hosts keys** — every key belongs to the installer, created in
  their own account, stored in their own Hermes install. Guided setup
  lives in `docs/KEY_SETUP.md` (written as the flow a Hermes agent
  walks the user through). The dashboard and CLI show the per-tier
  method honestly — "keyless (DNS)" vs "keyed (GoDaddy)", "companion
  API" vs "TSDR (keyed)".

**Hermes plugin packaging:** `plugin.yaml` at the repo root — name
`brandstorm`, version `0.3.0`, author `tradersurfer93`, MIT,
`requires_hermes >=0.21.6`, tools `brandstorm_brief`,
`brandstorm_run`, `brandstorm_results`, `brandstorm_state_links`
(thin wrappers in `plugin/` over the existing `brandstorm` pipeline —
no forked logic). `config_schema` is ALL optional, NOTHING pre-filled
(industry, region, states, class + the four key fields as
`type: secret` with `env:` — the secret shape follows the community
Hermes plugin guide, NOT verified against upstream Nous source; the
deciding check is `hermes plugins validate .` on the laptop).
`PRIVACY.md` discloses every network call, no retention, no telemetry,
no account. `demo/demo_flow.py` runs a fictional 5-name brief with
zero keys. Live verification (`hermes plugins doctor .` /
`hermes plugins validate . --install-deps`) runs on the laptop only —
see `docs/LAPTOP_TEST.md` (repo lives at `C:\Projects\BrandStormAI`).

**Dashboard theme (v0.3):** Light / Dark / System toggle, LIGHT
default, persisted in `localStorage`, applied before first paint (no
flash). Light theme is white/very-light-gray with dark text, same gold
accent; the v0.2 dark theme is preserved exactly as the Dark option.
Readability pass on both themes: 16px base font, 34px stat numbers,
14px row padding, roomier detail view. All features kept.

## 4. Direct Engineering Prompt for Codex / AI Lead

Role: Senior Full-Stack Engineer and AI Systems Architect.

Objective: Build an end-to-end prototype for BrandStorm AI — a
name-generation and multi-tier real-time clearance plugin that outputs
verified, non-taken business names for ANY user, ANY industry, ANY
region.

Core Feature Requirements:

- **Structured Input Form:** Collect Industry, Region/Location, Brand Vibe,
  Target Class, States to check, and optional Direct Anchors
  (must-use words/phrases from the user's own brief). Nothing is
  pre-filled with anyone's business or location.
- **AI Name Generator (50–100 Batch):** Generate compound, distinctive names
  that avoid single-word collisions while incorporating the user's
  anchors — anchors come only from the brief, never from the code.
- **Clearance Pipeline Module:** Write asynchronous worker functions to verify
  each candidate across:
  - Domain Checker: Node.js/Python script using the GoDaddy API or direct DNS
    lookup.
  - Trademark Search Module: Query USPTO data via scraping or TM API for
    active live marks in the specified Nice Class.
  - State Registry Module: return the SOS portal links for exactly the
    states the user requested (all 50 + DC map); never default to a region.
  - Social Handle Audit: Check username availability (exact + formatted
    handles) and display-name availability on X, YouTube, Facebook,
    LinkedIn, Instagram, TikTok. Report unknown with the reason where a
    platform gives no server-side signal.
- **UI Dashboard:** Render a visual table scoring each name with status
  badges:
  - 🟢 Clean (Domain + Trademark + Handle clear)
  - 🟡 Partial (Domain taken, but Trademark clear)
  - 🔴 Conflict (Active USPTO Trademark in target class)
  Plus a per-platform × handle-variant matrix and a display-name row
  with reasons, and a run-a-brief form (industry, geography, states,
  class, batch, aesthetics, anchors).

Deliverables: Provide a clean modular repository architecture (Frontend TUI/UI
+ Backend API Services) with full code for the clearance validation pipeline.

## Examples policy

- `briefs/sample-arizona-coffee.json` — the DEFAULT sample brief,
  clearly labeled SAMPLE in the file and the UI. A fictional Phoenix
  coffee roastery. Replace it with your own brief.
- `briefs/examples/bynd-streetwear.json` — the FIRST validation run
  (2026-11-11, 100 names, Class 025: 44 clean / 56 partial / 0
  conflict). Kept as a regression/example fixture only. Its output
  is preserved at `data/examples/bynd-run-2026-11-11.json`.
- Private name-check data never ships in this repo. (Three personal
  research files were moved out of `data/` in v0.2 — see
  `data/README.md`.)

## Standing Constraints (locked 2026-11-11, reaffirmed 2026-11-12)

- **Local prototype only for now** — no GitHub push, no PR, no API keys, no
  paid services, no purchases, no domain or handle registrations.
- **Domain checks run keyless via DNS-over-HTTPS** by default; a GoDaddy
  key, when the installer supplies their own, switches Tier 1 to the
  registrar API. DNS signal is solid but not absolute proof — say so
  in results.
- **v0.3 generation is combinatorial from word banks** (no model key wired
  yet). An LLM generator gets wired later with a key. Anchors come only
  from the brief.
- **Nobody hosts a backend and nobody hosts keys.** Every key belongs to
  the installer, created in their own account, stored in their own
  Hermes install. Keys are never logged, never committed, never sent
  anywhere except the check endpoint itself.
- **Never fake a clearance result** — report what each tier actually checked
  live vs what is stubbed. Unknown means unknown, with the reason.

## v0.3 Build Scope (done 2026-11-13)

- Playwright Tier 3 adapters for AZ, CA, TX, FL, NY, DC, MD, VA
  (`brandstorm/clearance/state_live.py`, `scripts/smoke_state.py`,
  `BRANDSTORM_STATE_LIVE=0` kill-switch, stop-after-2-blocks sweep).
  Honest outcome: built and wired, but no portal returned a usable
  found/not-found answer in the VM (AZ CAPTCHA, CA blocked, FL/NY
  navigation failures, TX no public search, DC 0×0 input, MD no
  render, VA cookie gate) — every attempt returns `unknown` + manual
  link. Laptop re-test required: some blocks may be sandbox egress
  artifacts.
- Hermes plugin packaging: `plugin.yaml` (brandstorm 0.3.0, 4 tools,
  all-optional config, secret fields), `plugin/` thin wrappers,
  `PRIVACY.md`, `demo/demo_flow.py` (fictional 5-name brief, zero
  keys), `docs/LAPTOP_TEST.md`. `hermes doctor` / `validate` still
  to run on the laptop.
- Zero-key-first UX: `brandstorm/keys.py` (labels only, never values),
  GoDaddy keyed path (v1/sso-key, needs live key to verify) and TSDR
  keyed path (serial verification, needs live key to verify),
  per-tier method shown honestly in dashboard + CLI,
  `docs/KEY_SETUP.md` guided setup with the no-backend rule up front.
- Dashboard: Light/Dark/System theme (light default, persisted,
  no-flash) + readability pass (16px base, 34px stats, roomier rows
  and detail view). All features kept.
- Tests: 47 → 117, all passing (28 state-live + 3 sweep-stop, 20 plugin, 19
  keys/theme, all no-network).

## v0.2 Build Scope (done 2026-11-12)

- Geography driven by the user's search: brief schema v2
  (`geographic_scope` + `states`), region-alias map, explicit-states-wins
  precedence, `not_requested` when no states are named.
- All-50-states + DC registry map with per-URL verification
  (39/51 answered at least once across verification passes; 12 hosts
  close automated connections — recorded, not hidden).
- De-branded product: example brief moved to `briefs/examples/`,
  Arizona sample brief is the default, private name-check files moved
  out of the repo, all user-facing copy scrubbed.
- Tier 4: username variants (@name, @wearname, @name.co) + display-name
  checks; Facebook and LinkedIn company added live, Instagram/TikTok/
  LinkedIn-profile unknown with verified reasons.
- Dashboard: run-a-brief form, Tier 4 matrix + display-name row,
  geography-aware state chip.
- Docs + `PRODUCTION_CHECKLIST.md` (what production/Hermes submission
  still needs).

## v0.1 Proof (preserved)

- 100-name streetwear validation run, 2026-11-11: 44 clean, 56 partial,
  0 conflict; .com available 94/100. Output preserved at
  `data/examples/bynd-run-2026-11-11.json`. Key finding: 48 candidates
  flagged the same live Class 025 mark (serial 97042722) — the
  pipeline caught an encumbered lead token before anyone used it.

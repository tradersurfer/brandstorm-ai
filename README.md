# BrandStorm AI — Name-Storming & Automated Clearance Engine (v0.3)

Name generation + a real-time 4-tier clearance pipeline (domain, USPTO
trademark, state business registries, social handles) with a green / yellow /
red dashboard. Generic by design: it runs YOUR brief — your industry,
your region, your Nice Class. Nothing about any one person, business, or
place is baked in. Local prototype — works with zero keys; keys are
optional per-tier upgrades, never a prerequisite. Nobody hosts a backend
and nobody hosts keys.

## Quick start

```bash
# 1. Run the labeled sample brief end-to-end (50 candidates, all 4 tiers)
python3 -m scripts.run_brief briefs/sample-arizona-coffee.json

# 2. Open the dashboard
python3 api/server.py
# -> http://127.0.0.1:8000/
```

Stdlib only for the core — Python 3.10+ (tested on 3.12), no pip installs.
Playwright is needed only for the live Tier 3 state checks:
`pip install playwright` (browsers: `python -m playwright install chromium`).

## Zero keys, by design

BrandStorm works out of the box with **zero keys** — keyless DNS-over-HTTPS
domains, the unofficial USPTO companion API, HTTP-status social checks,
manual state links (plus Playwright attempts). Keys are optional per-tier
upgrades, set as environment variables (or in the Hermes plugin config):

| Env vars | Unlocks |
|---|---|
| `BRANDSTORM_GODADDY_KEY` + `BRANDSTORM_GODADDY_SECRET` | Tier 1 via the GoDaddy availability API instead of DNS inference |
| `BRANDSTORM_USPTO_KEY` | Tier 2 matches verified by serial against the official TSDR API |
| `BRANDSTORM_LLM_KEY` | Reserved for a future model-based generator (no client yet) |

No key is ever logged or committed — the code only ever reports
`keyed` / `keyless` labels. The dashboard and CLI show which method each
tier actually used. Full guided setup (where to create each key in your
own account, where to paste it) is in `docs/KEY_SETUP.md`. There is no
backend: every key belongs to the installer, created in their own
account, stored in their own Hermes install.

## What it does

1. **Structured input** — a brief JSON (industry, geographic scope,
   states, brand aesthetic, Nice Class, direct anchor rules, batch
   size). The shipped sample is a fictional Phoenix, Arizona specialty
   coffee roastery (`briefs/sample-arizona-coffee.json`, labeled
   SAMPLE in the file and the UI). See "Write your own brief" below.
2. **Name generator** — deterministic combinatorial generation from
   curated word banks: compound names only (2+ tokens, no single-word
   collisions), every name carrying an anchor token from YOUR brief's
   must-include variations. v0.3 has NO LLM wired; an LLM generator can
   be plugged in behind `brandstorm.generator.generate`. A 3+ word
   variation also yields an acronym lead from its initials
   (e.g. "Desert Roast Coffee" → DRC).
3. **Clearance pipeline** — async workers run 4 tiers per candidate:
   - **Tier 1 Domain** — keyless DNS-over-HTTPS by default (Google
     primary, Cloudflare fallback) for .com, .co, .studio, .supply,
     .app. A record present = taken; NXDOMAIN = likely available. DNS
     absence is a strong signal, not a registrar guarantee — the
     dashboard says so. With both GoDaddy env vars set, the GoDaddy
     availability API is used instead (implemented, needs a live key
     to verify); keyed errors report `unknown` and never silently fall
     back to DNS.
   - **Tier 2 USPTO** — live search against the Trademark Search
     companion API behind tmsearch.uspto.gov (undocumented, no key;
     verified live 2026-11-11). Live marks only, filtered to the
     target Nice Class from your brief. Exact / prefix / phonetic
     (Soundex) matching done locally. With `BRANDSTORM_USPTO_KEY` set,
     each match is verified by serial against the official TSDR API
     (TSDR has no wordmark-search endpoint — it is retrieval only, so
     the companion API stays the discovery path; implemented, needs a
     live key to verify).
   - **Tier 3 State registries** — Playwright adapters in v0.3 for AZ,
     CA, TX, FL, NY, DC, MD, VA (`brandstorm/clearance/state_live.py`):
     each attempts a live browser check of the portal's entity-name
     search for exactly the states your brief asks for (all 50 states
     + DC in `brandstorm/clearance/registries.py`). **Honest outcome
     (VM, 2026-11-13): no portal returned a usable found/not-found
     answer** — AZ eCorp CAPTCHAs every submit, CA is security-blocked,
     FL/NY navigation never completes from this sandbox, TX has no
     public entity search, DC renders a 0×0 input, MD submits with no
     visible result, VA stalls behind the cookie gate. Every attempt
     returns `unknown` with the specific reason plus the manual link —
     never a guess. States without an adapter stay `manual`. If your
     brief names no states, the tier reports `not_requested` — it never
     defaults to a region. `BRANDSTORM_STATE_LIVE=0` forces
     manual-only. Some blocks may be sandbox egress artifacts — the
     laptop test phase re-checks them (see `docs/LAPTOP_TEST.md`).
   - **Tier 4 Social** — username checks for three variants per
     candidate (@name, @wearname, @name.co) plus a display-name check
     (the spaced name). LIVE: X and YouTube via HTTP status
     (404 = likely free, 200 = taken); Facebook via final URL (login
     redirect = likely free, profile URL = taken); LinkedIn company
     pages via HTTP status (200 = slug taken, 404 = slug likely free).
     UNKNOWN, never guessed: Instagram, TikTok (login wall, 200 for
     everything), LinkedIn personal profiles (HTTP 999 for
     everything), and display names on all platforms (search is
     login/JS-gated or echoes the query with no existence signal —
     verified 2026-11-12).
4. **Dashboard** — table with 🟢 Clean / 🟡 Partial / 🔴 Conflict
   badges, per-tier breakdown per name (click a name: domain TLDs,
   USPTO matches, a per-platform × handle-variant social matrix, the
   display-name row with reasons, and the state manual-check links),
   filters, search, a run-a-brief form, and a Light / Dark / System
   theme toggle (light default, remembered in your browser). The tier
   notes box says which method each tier actually used
   (keyless vs keyed).

## Write your own brief

Copy the sample and change it. Every field is yours:

```json
{
  "industry": "Specialty Coffee Roastery",
  "geographic_scope": "Phoenix, Arizona / US National",
  "states": ["AZ"],
  "brand_aesthetic": ["Rustic", "Artisan", "Modern", "Minimalist"],
  "direct_anchor_rules": {
    "must_include_exact_variations": ["Desert Roast", "Sonora Roast"],
    "enforce_compound_structure": true
  },
  "candidate_batch_size": 50,
  "nice_class": "030",
  "tlds": ["com", "co", "studio", "supply", "app"]
}
```

- `geographic_scope` — free text. `states` — explicit state/DC codes
  for Tier 3. See "How region / state resolution works".
- `brand_aesthetic` — any of: Trendy, Minimalist, High-End,
  Urban Utility, Rustic, Artisan, Modern, Playful. Unknown names are
  ignored (that aesthetic just contributes no roots).
- `direct_anchor_rules.must_include_exact_variations` — the words
  every generated name must contain one token of. Omit it (or leave
  it empty) and the generator builds root + root compounds with no
  anchor rule.
- `nice_class` — Nice Class as a string (`"025"` apparel, `"030"`
  coffee/tea, `"042"` software services, ...).
- `candidate_batch_size` — how many names to generate (5–100 is sane).

Run it: `python3 -m scripts.run_brief briefs/my-brief.json`, or use
the form on the dashboard (it POSTs an inline brief to `/api/run`).
Override states from the CLI: `--states AZ,CA`.

## How region / state resolution works

Precedence — explicit `states` always wins:

1. **Explicit `states`** in the brief (e.g. `["AZ"]`). Unknown codes
   are dropped and reported in the run output.
2. **Region phrases in `geographic_scope`** (see
   `brandstorm/regions.py`): "DMV" → DC/MD/VA, "California" → CA,
   "Pacific Northwest" → WA/OR, "New England" → CT/MA/ME/NH/RI/VT,
   "Midwest", "Southeast", "Southwest", "Mountain West", "West Coast",
   "East Coast", "Mid-Atlantic", "Northeast", "Great Lakes",
   "Deep South", "Gulf Coast", plus every full state name and bare
   two-letter codes that are not common English words (IN, OR, ME are
   resolved via their full names only — "in" and "or" appear in
   ordinary text).
3. **Nothing matched → no states.** Tier 3 reports `not_requested`
   with guidance. "US National" alone resolves to no states — a
   national scope is not a state filing.

The resolved states, source, matched phrases, and dropped codes are
recorded in the run output under `geography`.

## Badge rules

- 🔴 **Conflict** — an active USPTO mark in the target class matches exactly.
- 🟡 **Partial** — .com taken but trademark clear; or a similar live mark;
  or a taken handle on any live platform; or a checked tier came back
  inconclusive.
- 🟢 **Clean** — .com available + USPTO fully clear + handles free on
  every live platform. State filings are a manual-check flag unless a
  live check ran: a live exact entity match in a requested state makes
  a name partial at best (it cannot downgrade a USPTO conflict); fuzzy
  found, unknown, and manual never change a badge. Unknown platforms
  (Instagram, TikTok, LinkedIn profile) and unknown display-name checks
  never change a badge in either direction — they are shown with their
  reasons, not hidden.

## Handle variants (Tier 4)

Per candidate, three username variants are checked on every platform:

| Variant | Example for "Desert Ridge" |
|---|---|
| compact | `desertridge` |
| wear + compact | `weardesertridge` |
| compact + "co" | `desertridgeco` |

The spec's `@name.co` display form maps to the `compact + "co"`
username because platforms do not allow dots in usernames. The spaced
display name ("Desert Ridge") is checked separately and reported per
platform — unknown everywhere in v0.2, with the reason shown.

## Repo layout

```
brandstorm-ai/
  ARCHITECTURE.md            source of truth (handoff spec)
  IDEA.md                    the project, for Hermes projects
  PRODUCTION_CHECKLIST.md    what production + Hermes submission still need
  PRIVACY.md                 what is/isn't collected, network calls, no retention
  plugin.yaml                Hermes plugin manifest (brandstorm 0.3.0)
  plugin/                    thin Hermes tool wrappers (no forked pipeline)
  demo/demo_flow.py          fictional 5-name demo, zero keys
  docs/KEY_SETUP.md          guided key setup (no-backend rule up front)
  docs/LAPTOP_TEST.md        live verification steps for the laptop
  briefs/sample-arizona-coffee.json   labeled sample brief (default)
  briefs/examples/           first validation brief (fixture) + README
  brandstorm/
    generator.py  words.py  phonetics.py  scoring.py  pipeline.py
    regions.py               geography resolution
    keys.py                  env key detection (labels only, never values)
    clearance/
      domain.py  uspto.py  state.py  state_live.py  social.py
      registries.py  registries_verification.json
  api/server.py              stdlib server: dashboard + /api/run + /api/results
  frontend/index.html        dashboard (vanilla JS, no deps) + run form + theme
  scripts/run_brief.py       CLI runner
  scripts/smoke_state.py     live Tier 3 smoke check (AZ)
  scripts/verify_registries.py  status-check every SOS URL
  data/results.json          latest run output
  data/examples/             preserved validation runs
  tests/                     unit tests, no network (test_brandstorm,
                             test_state_live, test_plugin, test_keys_theme)
```

## Tests

```bash
python3 -m unittest discover -s tests -v   # 117 tests, all passing
```

## What each tier actually checks (live vs stubbed)

| Tier | Status in v0.3 | Evidence |
|---|---|---|
| 1 Domain | LIVE (keyless DoH by default; GoDaddy keyed path implemented, needs a live key to verify) | Google dns.google/resolve + Cloudflare fallback, verified 2026-11-11 |
| 2 USPTO | LIVE (companion API; TSDR serial-verification path implemented, needs a live key to verify) | tmsearch.uspto.gov companion API, verified 2026-11-11. TSDR has no wordmark-search endpoint — retrieval by serial only |
| 3 State | ATTEMPTED (Playwright) — no portal returned found/not-found in the VM | AZ CAPTCHA, CA blocked, FL/NY navigation fails, TX no public search, DC 0×0 input, MD no render, VA cookie gate (2026-11-13). Manual links for the states you asked for; laptop re-test pending |
| 4 Social | PARTIAL | X + YouTube + Facebook + LinkedIn company live via username checks (verified 2026-11-12); IG + TikTok + LinkedIn profile unknown (login wall / HTTP 999); display name unknown on all platforms |

## Hermes plugin

`plugin.yaml` (brandstorm 0.3.0) + `plugin/` (4 tools:
`brandstorm_brief`, `brandstorm_run`, `brandstorm_results`,
`brandstorm_state_links`) + `PRIVACY.md`. Config is all optional,
nothing pre-filled; keys are `type: secret` fields (the secret shape
follows the community Hermes plugin guide — the deciding check is
`hermes plugins validate .` on the laptop). Live verification steps
are in `docs/LAPTOP_TEST.md`; the repo lives at
`C:\Projects\BrandStormAI` on the laptop.

## Examples

- `briefs/examples/bynd-streetwear.json` — the first validation brief
  (2026-11-11, 100 names, Class 025: 44 clean / 56 partial / 0
  conflict). Its output is preserved at
  `data/examples/bynd-run-2026-11-11.json`. Re-run it as a regression
  check after pipeline changes; live data moves, so small shifts are
  expected.
- `briefs/sample-arizona-coffee.json` — the default sample brief.
  Fictional data, clearly labeled.

Private name-check data never ships in this repo — see `data/README.md`.

## What it needs to go real (v0.4+)

- **GoDaddy key/secret** — verify the keyed Tier 1 path against the live
  API (implemented, never run with a real key). Open question: v1/sso-key
  vs the newer v3/PAT auth, and whether the availability endpoint needs
  50+ domains on the account — verify at signup. Namecheap is NOT an
  option (account doesn't meet its API requirements).
- **USPTO TSDR API key** (account.uspto.gov) — verify the keyed Tier 2
  serial-verification path against the live API.
- **State registry automation, continued** — the Playwright adapters exist
  but the portals block automation in the VM. Re-test on the laptop
  (normal network, no sandbox proxy); where a portal stays blocked,
  keep manual links and consider state bulk-data feeds.
- **Social APIs / authenticated checks** — Instagram Graph, TikTok,
  Facebook, and LinkedIn official APIs (or a compliant handle-check
  service) for real IG/TT/profile signals and display-name checks.
- **LLM key** — to replace/augment the combinatorial generator with
  model-generated names.

Full list, with the Hermes submission path, in `PRODUCTION_CHECKLIST.md`.

## Standing constraints (locked 2026-11-11, reaffirmed 2026-11-12)

- Local prototype only: no GitHub push, no PR, no API keys, no paid
  services, no purchases, no domain or handle registrations.
- Never fake a clearance result. An inconclusive tier is reported as
  unknown, with the reason — not as clear.
- No personal data ships in this repo. Sample and example fixtures are
  labeled as such.
- Nobody hosts a backend and nobody hosts keys. Keys belong to the
  installer, in their own account and their own Hermes install.

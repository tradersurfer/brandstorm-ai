# BrandStorm AI — IDEA

**One-liner:** Generate 50–100 brand names and screen every one through live
domain, trademark, state-filing, and social-handle checks — so founders only
ever see names they can actually use.

**Status:** v0.3 DONE (2026-11-13, local only). Generic product — no
hardcoded geography, brand, or anchors. Zero keys out of the box;
Hermes plugin packaged; Playwright Tier 3 adapters built; Light/Dark/
System dashboard, light default. Proven on real briefs, plus a labeled
sample brief anyone can run. Ready for the laptop live-test phase.
**Author:** tradersurfer93
**Repo:** `~/workspace/brandstorm-ai/`
**Source of truth:** `ARCHITECTURE.md` · **How it runs:** `README.md`

---

## The problem

Naming tools spit out 50–100 candidate names with no real verification.
Founders fall in love with a name, then hit a wall: an active USPTO
trademark in their class, a taken .com, a taken Instagram handle. Over 90%
of generated names die on one of those three walls — after the founder
already spent time and emotion on them.

## The product

A name-storming and automated clearance engine. The user fills in a
structured brief, the engine generates compound, distinctive names, and a
parallel 4-tier pipeline clears each one in real time:

1. **Tier 1 — Domain:** .com, .co, .studio, .supply, .app availability.
   Available / Taken / Broker-Premium.
2. **Tier 2 — USPTO trademark:** exact, prefix, and phonetic matches against
   live marks, filtered to the target Nice Class (e.g. Class 025 Apparel).
3. **Tier 3 — State business registries:** Secretary of State filings
   for exactly the states the user asks for (all 50 states + DC in the
   registry map). No states named → not requested, never a silent
   default.
4. **Tier 4 — Social handles:** username (@name, @wearname, @name.co)
   AND display name across X, YouTube, Facebook, LinkedIn, Instagram,
   and TikTok.

**Output:** a dashboard with one badge per name — 🟢 Clean (domain +
trademark + handle clear), 🟡 Partial (usable with a flag), 🔴 Conflict
(active trademark in the target class). Click any name for the per-tier
breakdown.

### Input brief (the labeled sample)

The repo ships with a clearly labeled sample brief — a fictional
Phoenix, Arizona specialty coffee roastery. Replace it with your own:

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
  "nice_class": "030"
}
```

Any brief works the same way — change the industry, region, vibe, Nice
Class, states, anchors, and batch size, and the engine runs the same
pipeline. The first validation brief (a streetwear brief) is kept only
as a labeled example/regression fixture in `briefs/examples/`.

---

## Proof: v0.1 already ran on a real brief

The example streetwear brief (100 candidates, Class 025), run 2026-11-11
and preserved at `data/examples/bynd-run-2026-11-11.json`:

| Result | Count |
|---|---|
| 🟢 Clean | 44 |
| 🟡 Partial | 56 |
| 🔴 Conflict | 0 |
| .com available | 94 / 100 |

- **114/114 unit tests pass** (no network). Core is stdlib-only
  Python; Playwright is needed only for the live Tier 3 checks.
- **Domain tier LIVE** (keyless DNS-over-HTTPS by default; a GoDaddy
  keyed path is implemented and needs a live key to verify).
  **USPTO tier LIVE** (tmsearch companion API, no key; a TSDR
  serial-verification path is implemented and needs a live key to
  verify). **State tier: Playwright adapters built** for 8 states —
  but no portal returned a usable found/not-found answer in the VM
  (AZ CAPTCHA, CA blocked, FL/NY navigation failures, TX no public
  search, DC 0×0 input, MD no render, VA cookie gate), so every
  attempt reports `unknown` with the reason plus the manual link.
  **Social tier partial** — X, YouTube, Facebook, and LinkedIn
  company live via username checks; Instagram and TikTok sit behind
  a login wall, reported as unknown, never guessed. (v0.2 added
  Facebook and LinkedIn company as live username checks, plus
  display-name checks that are unknown everywhere with verified
  reasons.)
- **Zero keys out of the box.** Keys are optional per-tier upgrades
  from the installer's own account — nobody hosts a backend, nobody
  hosts keys. Guided setup in `docs/KEY_SETUP.md`.

**The finding that proves the point:** 48 of the 100 candidates flag the
same live Class 025 mark — serial **97042722**. A plain name
generator would have handed over a list full of names built on an
already-encumbered lead token. BrandStorm caught it before anyone fell
in love with one. Clean winners from the run include names built on the
brief's own anchors — the point is the pipeline, not any one name.

**v0.3 sample re-run (2026-11-13, Arizona coffee, Class 030):** 50 names
— 2 clean (Desert Mono, Desert Makers), 47 partial, 1 conflict (Desert
Creek, exact live Class 030 mark serial 87886765). Tier 3 AZ live
attempt returned `unknown` (eCorp CAPTCHA) with the manual link —
reported honestly, not hidden.

**Run it yourself:**

```bash
pip install playwright   # Tier 3 live checks only; core is stdlib-only
python3 -m scripts.run_brief briefs/sample-arizona-coffee.json
python3 -m scripts.run_brief briefs/examples/bynd-streetwear.json --out data/examples/bynd-run-2026-11-12.json
python3 api/server.py   # dashboard at http://127.0.0.1:8000/
python3 -m unittest discover -s tests -v   # 117 tests
python3 demo/demo_flow.py   # fictional 5-name demo, zero keys
```

---

## How it's built (v0.3)

```
brandstorm-ai/
  ARCHITECTURE.md            source of truth (handoff spec)
  IDEA.md                    this file — the project, for Hermes projects
  README.md                  setup, badge rules, live-vs-stubbed table
  PRODUCTION_CHECKLIST.md    what production + Hermes submission still need
  PRIVACY.md                 what is/isn't collected, network calls, no retention
  plugin.yaml                Hermes plugin manifest (brandstorm 0.3.0)
  plugin/                    thin Hermes tool wrappers (no forked pipeline)
  demo/demo_flow.py          fictional 5-name demo, zero keys
  docs/KEY_SETUP.md          guided key setup (no-backend rule up front)
  docs/LAPTOP_TEST.md        live verification steps for the laptop
  briefs/sample-arizona-coffee.json   labeled sample brief (default)
  briefs/examples/bynd-streetwear.json  first validation brief (fixture)
  brandstorm/
    generator.py  words.py  phonetics.py  scoring.py  pipeline.py
    regions.py               geography resolution (aliases, states)
    keys.py                  env key detection (labels only, never values)
    clearance/  domain.py  uspto.py  state.py  state_live.py  social.py
    clearance/  registries.py  registries_verification.json (all 50 + DC)
  api/server.py              stdlib server: dashboard + /api/run + /api/results
  frontend/index.html        dashboard (vanilla JS, no deps) + run form + Light/Dark/System theme
  scripts/run_brief.py       CLI runner
  scripts/smoke_state.py     live Tier 3 smoke check (AZ)
  scripts/verify_registries.py  status-check every SOS URL
  data/results.json          latest run output
  data/examples/bynd-run-2026-11-11.json   preserved v0.1 run
  tests/                     114 unit tests, no network
```

v0.3 generation is combinatorial from curated word banks (compound names
only, anchor token in every name) — anchors come only from the brief, no
model key wired yet.

---

## Roadmap — how to expand this

### Done in v0.3

- **Playwright Tier 3 adapters** for AZ, CA, TX, FL, NY, DC, MD, VA —
  built and wired, with a kill-switch and stop-after-2-blocks. Honest
  outcome: no portal returned a usable found/not-found answer in the
  VM (AZ CAPTCHA, CA blocked, FL/NY navigation failures, TX no public
  search, DC 0×0 input, MD no render, VA cookie gate). Manual links
  remain the real path; laptop re-test will show which blocks are real
  vs sandbox artifacts.
- **Hermes plugin packaging:** `plugin.yaml` (brandstorm 0.3.0, 4
  tools, all-optional config, secret fields), thin `plugin/` wrappers,
  `PRIVACY.md`, zero-key `demo/demo_flow.py`, `docs/LAPTOP_TEST.md`.
  `hermes doctor` / `validate` still to run on the laptop.
- **Zero-key-first UX:** works with no keys at all; GoDaddy and TSDR
  keyed paths implemented (both need a live key to verify); dashboard
  and CLI show each tier's method honestly; `docs/KEY_SETUP.md`
  guided setup with the no-backend rule up front. Namecheap is NOT an
  option (account doesn't meet its API requirements).
- **Dashboard theme + readability:** Light / Dark / System, light
  default, persisted, no-flash; 16px base font, 34px stat numbers,
  roomier rows and detail view. All features kept.

### v0.4 — make every tier real

- **LLM generator:** wire a model key behind `generator.generate` so names
  are model-written, not just combinatorial — keep the word-bank generator
  as a fallback and for offline runs.
- **Verify the keyed paths live:** GoDaddy (v1/sso-key vs v3/PAT) and
  TSDR (serial verification) with real keys, once the accounts are ready.
- **State registries, continued:** laptop re-test of the Playwright
  adapters; where a portal stays blocked, keep manual links and
  consider state bulk-data feeds.
- **Social, completed:** Instagram Graph + TikTok + Facebook + LinkedIn
  official APIs (or a compliant handle-check service) so IG/TT/profile
  checks stop reporting unknown, and display-name checks get a real
  signal.

### v0.5 — make it a product

- **Browser extension:** highlight a name anywhere on the web, right-click
  → run the clearance pipeline, badge it in place.
- **Multi-class + multi-industry briefs:** any Nice Class, any industry —
  the brief schema already supports it; add saved brief templates
  (streetwear, food, SaaS, beauty, fitness).
- **Client-ready reports:** one-page PDF/share link per run — clean names,
  flags, and the evidence behind each badge.
- **Watchlist / monitoring:** re-check a shortlist weekly; alert if a new
  mark files or a domain gets taken.
- **Hermes catalog submission:** regular merge — catalog PR with full-SHA
  pin, no Typeform, no demo video (the hackathon is over).

### Beyond — where it can go

- **Agency mode:** run clearance as a client service for agencies —
  brand naming + clearance report as a packaged deliverable for new
  businesses.
- **Name scoring:** rank clean names by distinctiveness, pronounceability,
  and domain/handle strength, not just pass/fail.
- **Batch compare:** run the same anchors across classes or regions and
  show where a name is safe and where it isn't.
- **Monetization:** free single runs, paid for batch reports, monitoring,
  and the extension — only once the tiers are authoritative, never on
  stubbed results.

---

## Rules (locked — don't break these while expanding)

- **Local prototype only for now:** no GitHub push, no PR, no API keys, no
  paid services, no purchases, no domain or handle registrations — until
  the owner says go.
- **Never fake a clearance result.** An inconclusive tier is reported as
  unknown, with the reason — not as clear. A stubbed tier says stubbed.
- **Nobody hosts a backend and nobody hosts keys.** Keys belong to the
  installer, in their own account and their own Hermes install.
- **DNS absence is a signal, not a registrar guarantee** — the dashboard
  must keep saying so.
- **Keep the spec honest:** `ARCHITECTURE.md` stays the source of truth;
  update it when the pipeline changes, don't let it drift.

---

## Why this one matters

Every new business needs a name first, and a name that survives contact
with reality. BrandStorm turns the riskiest, most emotional step of
starting a business into a checked, explainable result. It already
caught a live trademark 48 names deep into its first real run. That's
the product.

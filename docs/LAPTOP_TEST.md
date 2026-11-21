# BrandStorm AI v0.3 — Laptop Test (live verification)

Live verification runs **on the laptop, NOT in the cloud VM**.
The laptop's Hermes Desktop was reset/reinstalled 2026-11-12, so
plugin verification may now be possible — confirm it here, live.

## Setup

Repo location on the laptop: `C:\Projects\BrandStormAI`

The folder is populated from a zip (the parent supplies the download
link after verification). Unzip it to `C:\Projects\BrandStormAI`
so the repo root — `plugin.yaml`, `plugin/`, `brandstorm/`, `api/`,
`tests/` — sits directly under that path.

Requirements:

- Python 3.10+ (tested on 3.12 in the VM). Check with:
  ```powershell
  python --version
  ```
  Windows uses `python`, not `python3`. If `python` is not found,
  install Python from python.org and tick "Add python.exe to PATH".
- Playwright, for the live Tier 3 state checks (v0.3 has Playwright
  adapters for AZ, CA, TX, FL, NY, DC, MD, VA — they attempt a live
  browser check and fall back to `unknown` + manual link whenever a
  portal blocks automation, which most of them do; install so the
  laptop can run the attempts):
  ```powershell
  pip install playwright
  python -m playwright install chromium
  ```
- No API keys needed. The v0.3 test runs keyless (DNS-over-HTTPS,
  USPTO companion API, public social checks). Do NOT paste any key
  into the repo, the terminal, or a chat message.

## 1. Unit tests (no network)

```powershell
cd C:\Projects\BrandStormAI
python -m unittest discover -s tests -v
```

Expected: the full suite passes (117 tests: 47 v0.2 tests + 28
Tier 3 live tests + 3 sweep-stop tests + 20 plugin tests + 19 key/theme tests). If any
test fails, stop and report the failing test name + output — do not
edit code to make a failing test pass without saying so.

## 2. Sample brief run (live, keyless)

```powershell
cd C:\Projects\BrandStormAI
python -m scripts.run_brief briefs/sample-arizona-coffee.json
```

Expected: 50 candidates generated, 4-tier clearance runs (a few
minutes — live DNS + USPTO + social checks), a summary line like
`Results: 50 total | 🟢 N clean | 🟡 N partial | 🔴 N conflict`,
and `data/results.json` written. Small count shifts vs the VM run
are normal — live data moves.

## 3. Plugin demo (live, keyless, 5 names)

```powershell
cd C:\Projects\BrandStormAI
python demo/demo_flow.py
```

Expected: fictional Portland tea-house brief, 5 names cleared, a
shortlist printed, Oregon state-registry link shown. No keys used,
no files written.

## 4. Dashboard

```powershell
cd C:\Projects\BrandStormAI
python api/server.py
```

Then open http://127.0.0.1:8000/ in the browser. (Windows
equivalent of the VM's `python3 api/server.py` is `python
api/server.py`.) Expected: the dashboard shows the latest run with
🟢/🟡/🔴 badges, per-tier breakdowns, and the run-a-brief form.
Stop the server with Ctrl+C when done. Do NOT leave it running.

## 5. Hermes plugin verification

```powershell
cd C:\Projects\BrandStormAI
hermes plugins doctor .
hermes plugins validate . --install-deps
```

Expected: doctor discovers the plugin (`brandstorm` v0.3.0, 4 tools:
`brandstorm_brief`, `brandstorm_run`, `brandstorm_results`,
`brandstorm_state_links`) and validate passes. These two commands
are the real check for the `plugin.yaml` manifest — including the
`type: secret` config fields, which could NOT be verified in the VM
(see "Known unknowns" below). If validate flags the secret fields,
note the exact error and report it back — do not hand-edit the
manifest to force a pass.

Optional install check (only after doctor + validate pass):

```powershell
hermes plugins install C:\Projects\BrandStormAI
hermes plugins enable brandstorm
hermes plugins list
```

Then in Hermes, ask for a brief for a fictional brand and confirm
the four tools are offered. Do NOT install from any other path.

## Known unknowns (could not be verified in the VM)

- `hermes plugins doctor .` / `hermes plugins validate .` cannot run
  in the cloud VM (no Hermes binary here). They must run on the
  laptop, per step 5.
- The `type: secret` + `env:` shape in `plugin.yaml` `config_schema`
  follows the community Hermes plugin guide (manifest v2 example:
  `api_key: {type: secret, env: MY_PLUGIN_API_KEY, ...}` — secrets
  never touch `config.yaml`, values live in the Hermes secret scope /
  `.env`). It was NOT verified against the upstream Nous Hermes
  source. Laptop `validate` is the deciding check.
- `requires_hermes: ">=0.21.6"` is copied from ceo-pack's
  `plugin.yaml`, which was verified in the VM.

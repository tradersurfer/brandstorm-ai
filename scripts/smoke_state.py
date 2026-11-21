"""Live smoke check for Tier 3 (v0.3) — Arizona eCorp via Playwright.

Checks one known-taken name ("Walmart" — certainly registered in AZ)
and one gibberish name, and prints what the browser actually saw
(page title, result/evidence, status, reason). Run from the repo root:

    python3 scripts/smoke_state.py [STATE] [NAME ...]

Defaults: AZ, Walmart + a gibberish name. Exits 0 if the check ran
(even when the portal answers "unknown" — an honest unknown is a valid
smoke result); exits 2 only if the script itself crashes.
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from brandstorm.clearance import state_live


def main() -> int:
    state = (sys.argv[1] if len(sys.argv) > 1 else "AZ").upper()
    names = sys.argv[2:] or ["Walmart", "Zqxjkvwmplth"]
    adapter = state_live.ADAPTERS.get(state)
    print(f"state: {state}")
    print(f"adapter: {'yes' if adapter else 'NO — manual fallback only'}")
    if adapter:
        print(f"portal: {adapter['url']}")
        print(f"method: {adapter['method']}")
    print(f"names: {names}")
    print("-" * 70)
    outcomes: dict[str, dict] = {}
    for name in names:
        print(f"--- {name!r} in {state} ---")
        try:
            out = state_live.check_state_live(name, state, timeout=90)
        except Exception as e:  # noqa: BLE001 — smoke must report, not crash
            print(f"  SCRIPT ERROR: {e}")
            continue
        outcomes[name] = out
        print(f"  status:   {out.get('status')}")
        print(f"  found:    {out.get('found')}")
        print(f"  exact:    {out.get('exact')}")
        print(f"  method:   {out.get('method')}")
        print(f"  evidence: {out.get('evidence')}")
        print(f"  reason:   {out.get('reason') or '(none)'}")
        print(f"  manual:   {out.get('manual_url')}")
    print("-" * 70)
    print("raw JSON:")
    print(json.dumps(outcomes, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

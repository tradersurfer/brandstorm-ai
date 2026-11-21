"""BrandStorm AI plugin demo — fictional brief, end to end, zero keys.

Run from the repo root:  python3 demo/demo_flow.py

Fictional brief: "Cascade Leaf Tea", a Portland, Oregon specialty tea
house. Nothing real, nothing personal. Small batch (5 names) through
the plugin tools: brief -> run -> results -> state links.

Keyless paths only: Tier 1 runs DNS-over-HTTPS, Tier 2 the keyless
USPTO companion API, Tier 4 public profile checks. No credentials
are read or needed. The demo does NOT overwrite data/results.json
(write_results=False) — the repo's sample run stays intact.
"""

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from plugin import tools as t  # noqa: E402

BRIEF = {
    "industry": "Specialty Tea House",
    "geographic_scope": "Portland, Oregon / US National",
    "states": ["OR"],
    "brand_aesthetic": ["Rustic", "Artisan", "Modern", "Minimalist"],
    "nice_class": "030",
    "candidate_batch_size": 5,
    "tlds": ["com", "co"],
    "must_include_exact_variations": ["Cascade Leaf", "Fern Leaf", "Cascade Leaf Tea"],
}


def show(title, obj):
    print(f"\n=== {title} ===")
    print(json.dumps(obj, indent=2))


def main():
    print("BRANDSTORM AI — plugin demo (fictional brief, zero keys)")
    print("Brief: Cascade Leaf Tea — Portland, Oregon specialty tea house")

    brief = t.brandstorm_brief(BRIEF)
    show("[1] BRIEF — validated, no network", brief)
    if brief.get("status") != "success":
        return 1

    print("\n[2] RUN — generating 5 names, clearing all 4 tiers (live keyless checks)...", flush=True)
    run = t.brandstorm_run({"brief": brief["brief"], "write_results": False})
    if run.get("status") != "success":
        show("[2] RUN — error", run)
        return 1
    show("[2] RUN — summary", {
        "summary": run["summary"],
        "shortlist": run["shortlist"],
        "tier_notes": run["tier_notes"],
        "geography": run["geography"],
    })
    for r in run["results"]:
        print(f"  {r['badge'].upper():8} {r['name']:<28} {r['reason']}")

    show("[3] RESULTS — shortlist + per-tier evidence (from the run)",
         {"shortlist": run["shortlist"],
          "evidence": [{k: r[k] for k in ("name", "badge", "domain", "uspto", "state")}
                       for r in run["results"]]})

    show("[4] STATE LINKS — Tier 3 is manual, links only, never a result",
         t.brandstorm_state_links({"states": ["OR"]}))

    print("\nDemo done. No keys used, no files written, nothing registered.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

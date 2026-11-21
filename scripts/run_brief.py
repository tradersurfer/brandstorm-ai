#!/usr/bin/env python3
"""Run a BrandStorm brief end-to-end: generate -> clear (4 tiers) -> dashboard data.

Usage:
    python3 -m scripts.run_brief briefs/sample-arizona-coffee.json
    python3 -m scripts.run_brief briefs/examples/bynd-streetwear.json --limit 20 --out data/examples/bynd-run-2026-11-12.json
    python3 -m scripts.run_brief briefs/sample-arizona-coffee.json --states AZ,CA

Writes results JSON for the dashboard and prints a summary. Stdlib only.

Geography: Tier 3 checks the brief's explicit "states" list. A --states
override replaces it. If neither is given, region phrases in
"geographic_scope" are resolved (e.g. "DMV" -> DC/MD/VA); if nothing
resolves, Tier 3 reports "not_requested" — it never defaults to a region.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from brandstorm import generator, pipeline  # noqa: E402
from brandstorm.keys import annotate_tier_notes, keys_status, tier_method_label  # noqa: E402
from brandstorm.regions import resolve_states  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_BRIEF = os.path.join(ROOT, "briefs", "sample-arizona-coffee.json")


def main() -> int:
    parser = argparse.ArgumentParser(description="BrandStorm AI — run a naming brief")
    parser.add_argument("brief", nargs="?", default=DEFAULT_BRIEF,
                        help="Path to a brief JSON file (default: the labeled sample brief)")
    parser.add_argument("--limit", type=int, default=None, help="Limit candidates (default: brief batch size)")
    parser.add_argument("--out", default=os.path.join(ROOT, "data", "results.json"))
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--states", default=None,
                        help="Comma-separated state codes for Tier 3, e.g. AZ,CA — overrides the brief")
    args = parser.parse_args()

    with open(args.brief) as f:
        brief = json.load(f)

    states_arg = [s.strip() for s in args.states.split(",")] if args.states else None
    states, source, matched, dropped = resolve_states(
        brief.get("geographic_scope"), states_arg if states_arg is not None else brief.get("states"))
    if brief.get("sample"):
        print(f"Sample brief: {brief.get('label', '')}")
    print(f"Brief: {brief.get('industry')} | {brief.get('geographic_scope')}")
    print(f"Aesthetic: {', '.join(brief.get('brand_aesthetic', []))} | Class {brief.get('nice_class', '025')}")
    print(f"Tier 3 states: {states or 'none requested'} (source: {source}"
          + (f", matched: {', '.join(matched)}" if matched else "")
          + (f", dropped unknown codes: {', '.join(dropped)}" if dropped else "") + ")")
    names = generator.generate(brief, count=args.limit or brief.get("candidate_batch_size", 100), seed=args.seed)
    print(f"Generated {len(names)} candidates (deterministic, combinatorial — no LLM in v0.2)")
    print(f"Sample: {', '.join(names[:5])}")

    started = _dt.datetime.now(_dt.timezone.utc)
    print("Running 4-tier clearance (this takes a few minutes — live DNS + USPTO + social checks)...", flush=True)

    def progress(done, total):
        if done % 10 == 0 or done == total:
            print(f"  {done}/{total} candidates cleared", flush=True)

    results = pipeline.run(names, nice_class=str(brief.get("nice_class", "025")),
                           tlds=brief.get("tlds"),
                           states=brief.get("states") if states_arg is None else states_arg,
                           geographic_scope=brief.get("geographic_scope"),
                           progress=progress)
    summary = pipeline.summarize(results)
    ended = _dt.datetime.now(_dt.timezone.utc)

    payload = {
        "brief": brief,
        "generated_at": started.isoformat(),
        "finished_at": ended.isoformat(),
        "duration_seconds": round((ended - started).total_seconds(), 1),
        "summary": summary,
        # Tier notes are adjusted AFTER pipeline.tier_notes() returns
        # (pipeline.py is not edited): the method label is honest
        # about keyless vs keyed. keys_status() holds labels only,
        # never a key value.
        "tier_notes": annotate_tier_notes(pipeline.tier_notes(states)),
        "keys_status": keys_status(),
        "geography": {"states": states, "source": source, "matched": matched, "dropped": dropped},
        "results": results,
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w") as f:
        json.dump(payload, f, indent=2)

    print()
    print(f"Results: {summary['total']} total | "
          f"🟢 {summary['clean']} clean | 🟡 {summary['partial']} partial | 🔴 {summary['conflict']} conflict")
    # Key status is labels only — never a key value.
    print(f"Keys: domain {tier_method_label('domain')} | "
          f"USPTO {tier_method_label('uspto')} | "
          f"LLM {tier_method_label('llm')} — see docs/KEY_SETUP.md to add one")
    print(f".com available: {summary['com_available']} | .com taken: {summary['com_taken']} | "
          f"USPTO unknown: {summary['uspto_unknown']} | domain unknown: {summary['domain_unknown']}")
    print("Top clean names:")
    for r in [x for x in results if x["badge"] == "clean"][:10]:
        print(f"  🟢 {r['name']}")
    print(f"Wrote {args.out} — open the dashboard with: python3 api/server.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

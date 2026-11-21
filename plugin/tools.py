"""BrandStorm AI — Hermes plugin tool handlers (v0.3.0).

Thin wrappers ONLY. Every tool delegates to the existing
``brandstorm.generator`` / ``brandstorm.pipeline`` / ``brandstorm.regions``
functions — no pipeline logic is forked or duplicated here.

Handlers take an args dict (or JSON string) and always return a plain
dict with a ``status`` field; they never raise on bad input.
No keys are read, logged, or echoed here. The pipeline's keyless
paths (DNS-over-HTTPS, USPTO companion API, public social pages) need
no credentials; optional keys live in the installer's Hermes secret
scope / env and are read by the clearance modules, never by these tools.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import sys

# The brandstorm package lives at the repo root, next to this plugin
# package — same sys.path pattern scripts/run_brief.py uses.
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from brandstorm import generator, pipeline  # noqa: E402
from brandstorm.clearance import registries as _registries  # noqa: E402
from brandstorm.clearance import state as _state_mod  # noqa: E402
from brandstorm.regions import resolve_states  # noqa: E402

DEFAULT_TLDS = ["com", "co", "studio", "supply", "app"]
DEFAULT_CLASS = "025"
MAX_BATCH = 100

RESULTS_PATH = os.path.join(_ROOT, "data", "results.json")


# ---------------------------------------------------------------- helpers

def _ok(payload):
    payload = dict(payload)
    payload.setdefault("status", "success")
    return payload


def _err(message):
    return {"status": "error", "error": message}


def _prep(args):
    """Coerce args to a dict. Returns (args, error_dict)."""
    if args is None:
        args = {}
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except ValueError:
            return None, _err("Arguments string is not valid JSON.")
    if not isinstance(args, dict):
        return None, _err("Arguments must be a JSON object.")
    return args, None


def _str_field(args, key, required=False, default=""):
    value = args.get(key, default)
    if value is None:
        value = default
    if not isinstance(value, str):
        return None, _err(f"{key} must be text, got {type(value).__name__}.")
    value = value.strip()
    if required and not value:
        return None, _err(f"Need {key}.")
    return value, None


def _str_list(args, key, default=None):
    """Accept a list of strings or a comma-separated string."""
    value = args.get(key)
    if value is None:
        return list(default or []), None
    if isinstance(value, str):
        return [s.strip() for s in value.split(",") if s.strip()], None
    if isinstance(value, list):
        if not all(isinstance(v, str) for v in value):
            return None, _err(f"{key} must be a list of strings.")
        return [v.strip() for v in value if v.strip()], None
    return None, _err(f"{key} must be a list of strings or a comma-separated string.")


def _int_field(args, key, default, minimum, maximum):
    value = args.get(key, default)
    if value is None:
        value = default
    if isinstance(value, bool) or not isinstance(value, int):
        return None, _err(f"{key} must be a whole number.")
    if not minimum <= value <= maximum:
        return None, _err(f"{key} must be between {minimum} and {maximum}, got {value}.")
    return value, None


def _build_brief(args):
    """Validate user input into a brief dict (no network).

    Returns (brief, geography, error_dict). geography is the
    resolve_states audit trail: codes, source, matched, dropped.
    """
    industry, e = _str_field(args, "industry", required=True)
    if e:
        return None, None, e
    scope, e = _str_field(args, "geographic_scope")
    if e:
        return None, None, e
    states_raw, e = _str_list(args, "states")
    if e:
        return None, None, e
    aesthetics, e = _str_list(args, "brand_aesthetic")
    if e:
        return None, None, e
    nice_class, e = _str_field(args, "nice_class", default=DEFAULT_CLASS)
    if e:
        return None, None, e
    if not nice_class:
        nice_class = DEFAULT_CLASS
    batch, e = _int_field(args, "candidate_batch_size", 50, 1, MAX_BATCH)
    if e:
        return None, None, e
    tlds, e = _str_list(args, "tlds", default=DEFAULT_TLDS)
    if e:
        return None, None, e
    if not tlds:
        tlds = list(DEFAULT_TLDS)
    variations, e = _str_list(args, "must_include_exact_variations")
    if e:
        return None, None, e
    if not variations:
        # Accept the nested shape too: a brief built by brandstorm_brief
        # stores anchors under direct_anchor_rules.
        nested_rules = args.get("direct_anchor_rules")
        if isinstance(nested_rules, dict):
            variations, e = _str_list(nested_rules, "must_include_exact_variations")
            if e:
                return None, None, e

    codes, source, matched, dropped = resolve_states(scope, states_raw or None)

    brief = {
        "industry": industry,
        "geographic_scope": scope,
        "states": codes,
        "brand_aesthetic": aesthetics,
        "nice_class": nice_class,
        "candidate_batch_size": batch,
        "tlds": [t.lower() for t in tlds],
        "direct_anchor_rules": {
            "must_include_exact_variations": variations,
            "enforce_compound_structure": True,
        },
    }
    geography = {"states": codes, "source": source, "matched": matched, "dropped": dropped}
    return brief, geography, None


# ---------------------------------------------------------------- tools

def brandstorm_brief(args, **kwargs):
    """Validate/build a brief dict from user input. No network, no keys."""
    args, bad = _prep(args)
    if bad:
        return bad
    brief, geography, e = _build_brief(args)
    if e:
        return e
    return _ok({"brief": brief, "geography": geography})


def brandstorm_run(args, **kwargs):
    """Generate + clear a batch via pipeline.run. Returns summary + results.

    Accepts either a nested ``brief`` dict (as built by
    brandstorm_brief) or the same fields flat. Writes the run payload
    to data/results.json unless ``write_results`` is false or ``out``
    names another path.
    """
    args, bad = _prep(args)
    if bad:
        return bad
    flat = dict(args)
    nested = args.get("brief")
    if isinstance(nested, dict):
        merged = dict(nested)
        for key, value in flat.items():
            if key not in ("brief", "write_results", "out") and value not in (None, "", [], {}):
                merged[key] = value
        flat = merged
    brief, geography, e = _build_brief(flat)
    if e:
        return e

    names = generator.generate(brief, count=brief["candidate_batch_size"])
    started = _dt.datetime.now(_dt.timezone.utc)
    results = pipeline.run(
        names,
        nice_class=str(brief["nice_class"]),
        tlds=brief["tlds"],
        states=brief["states"],
        geographic_scope=brief["geographic_scope"],
    )
    ended = _dt.datetime.now(_dt.timezone.utc)
    summary = pipeline.summarize(results)

    out = args.get("out")
    write_results = args.get("write_results", True)
    results_path = None
    if write_results:
        results_path = out or RESULTS_PATH
        payload = {
            "brief": brief,
            "generated_at": started.isoformat(),
            "finished_at": ended.isoformat(),
            "duration_seconds": round((ended - started).total_seconds(), 1),
            "summary": summary,
            "tier_notes": pipeline.tier_notes(geography["states"]),
            "geography": geography,
            "results": results,
        }
        os.makedirs(os.path.dirname(results_path), exist_ok=True)
        with open(results_path, "w") as f:
            json.dump(payload, f, indent=2)

    return _ok({
        "brief": brief,
        "geography": geography,
        "names": names,
        "summary": summary,
        "tier_notes": pipeline.tier_notes(geography["states"]),
        "shortlist": [r["name"] for r in results if r.get("badge") == "clean"],
        "results": results,
        "results_path": results_path,
    })


def brandstorm_results(args, **kwargs):
    """Read the shortlist + per-tier evidence from data/results.json."""
    args, bad = _prep(args)
    if bad:
        return bad
    badge, e = _str_field(args, "badge")
    if e:
        return e
    if badge and badge not in ("clean", "partial", "conflict"):
        return _err("badge must be clean, partial, or conflict.")
    limit, e = _int_field(args, "limit", 50, 1, MAX_BATCH)
    if e:
        return e
    results_path = args.get("results_path") or RESULTS_PATH
    if not os.path.exists(results_path):
        return _err(
            f"No results file at {results_path} yet. "
            "Run brandstorm_run first."
        )
    with open(results_path) as f:
        payload = json.load(f)
    results = payload.get("results", [])
    if badge:
        results = [r for r in results if r.get("badge") == badge]
    return _ok({
        "summary": payload.get("summary", {}),
        "brief": payload.get("brief", {}),
        "geography": payload.get("geography", {}),
        "tier_notes": payload.get("tier_notes", {}),
        "generated_at": payload.get("generated_at"),
        "shortlist": [r["name"] for r in payload.get("results", []) if r.get("badge") == "clean"],
        "results": results[:limit],
        "results_path": results_path,
    })


def brandstorm_state_links(args, **kwargs):
    """Manual-check links for the requested states (Tier 3 is manual).

    Returns the SOS portal entry per state. Status is always
    ``manual`` (or ``not_requested``) — never clear/taken, because
    the portals are form/session-gated and nothing was checked.
    """
    args, bad = _prep(args)
    if bad:
        return bad
    states_raw, e = _str_list(args, "states")
    if e:
        return e
    scope, e = _str_field(args, "geographic_scope")
    if e:
        return e
    codes, source, matched, dropped = resolve_states(scope, states_raw or None)
    if not codes:
        return _ok({
            "status": "not_requested",
            "states": {},
            "geography": {"states": [], "source": source, "matched": matched, "dropped": dropped},
            "guidance": _state_mod.GUIDANCE,
        })
    entries = {}
    for code in codes:
        entry = _registries.get_registry(code)
        if entry:
            entries[code] = {
                "name": entry["name"],
                "portal": entry["portal"],
                "url": entry["url"],
                "note": entry["note"],
                "verified": entry.get("verified", False),
                "verified_status": entry.get("verified_status"),
            }
    return _ok({
        "status": "manual",
        "method": (
            "Tier 3 is manual in v0.3: state portals are form/session-gated, "
            "so check each name at the portal link. These links are not results."
        ),
        "states": entries,
        "geography": {"states": codes, "source": source, "matched": matched, "dropped": dropped},
    })

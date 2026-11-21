"""Clearance pipeline — runs all 4 tiers per candidate in parallel.

Design: one ThreadPoolExecutor per tier (each tier has its own politeness
budget), candidates processed concurrently. A tier that errors or is
blocked reports "unknown" for that candidate — never a fake clear.

Geography: Tier 3 states are resolved ONCE per run from the brief
(explicit ``states`` wins over region phrases in ``geographic_scope`` —
see brandstorm/regions.py). A brief with no states gets Tier 3 status
"not_requested", never a silent default.
"""

from __future__ import annotations

import datetime as _dt
import os as _os
from concurrent.futures import ThreadPoolExecutor, as_completed

from .clearance import domain as _domain
from .clearance import social as _social
from .clearance import state as _state
from .clearance import uspto as _uspto
from .generator import compact
from .regions import resolve_states
from .scoring import score

# Worker counts — modest on the unofficial USPTO companion API.
DOMAIN_WORKERS = 16
USPTO_WORKERS = 6
SOCIAL_WORKERS = 10


def _run_one(name: str, nice_class: str, tlds: list[str], states: list[str],
             state_result: dict | None = None) -> dict:
    result = {"name": name, "compact": compact(name)}
    result["domain"] = _domain.check_domain(result["compact"], tlds)
    result["uspto"] = _uspto.check_uspto(name, nice_class)
    result["state"] = state_result if state_result is not None else _state.check_state(name, states=states)
    result["social"] = _social.check_social(result["compact"], display_name=name)
    badge, reason = score(result)
    result["badge"] = badge
    result["reason"] = reason
    result["checked_at"] = _dt.datetime.now(_dt.timezone.utc).isoformat()
    return result


def run(names: list[str], nice_class: str = "025", tlds: list[str] | None = None,
        states: list[str] | None = None, geographic_scope: str | None = None,
        progress=None, state_live: bool = True) -> list[dict]:
    """Run the full pipeline over all names. Returns results in input order.

    ``states`` (explicit codes) wins over ``geographic_scope`` aliases.
    Callers that need the resolution detail should call
    ``regions.resolve_states`` themselves (run_brief does).

    Tier 3 live checks: ``state_live=True`` (default) attempts the
    Playwright adapters for states that have one, sweeping each such
    state once with a shared browser before the tier pool starts
    (see clearance.state.check_state_batch). Env
    BRANDSTORM_STATE_LIVE=0 forces manual-only for offline runs.
    A live attempt that fails is reported "unknown" with its reason —
    never a guessed taken/clear.
    """
    tlds = tlds or _domain.TLDS
    resolved, _source, _matched, _dropped = resolve_states(geographic_scope, states)
    live_enabled = bool(state_live) and _os.environ.get("BRANDSTORM_STATE_LIVE", "1") != "0"
    live_state_results: dict[str, dict] = {}
    if live_enabled and resolved:
        try:
            live_state_results = _state.check_state_batch(names, resolved, live=True)
        except Exception:
            live_state_results = {}
    results: dict[str, dict] = {}
    done = 0
    with ThreadPoolExecutor(max_workers=max(DOMAIN_WORKERS, USPTO_WORKERS, SOCIAL_WORKERS)) as pool:
        futures = {pool.submit(_run_one, name, nice_class, tlds, resolved,
                               live_state_results.get(name)): name for name in names}
        for fut in as_completed(futures):
            name = futures[fut]
            try:
                results[name] = fut.result()
            except Exception as e:  # a tier crashed on this candidate — record it
                results[name] = {
                    "name": name, "compact": compact(name),
                    "domain": {"status": "unknown"}, "uspto": {"status": "unknown"},
                    "state": live_state_results.get(name) or _state.check_state(name, states=resolved),
                    "social": {
                        "platforms": {},
                        "live_platforms": _social.LIVE_PLATFORMS,
                        "display_name": {
                            "name": name,
                            "platforms": _social.check_display_name(name),
                        },
                    },
                    "badge": "partial", "reason": f"pipeline error: {e}",
                    "checked_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
                }
            done += 1
            if progress:
                progress(done, len(names))
    return [results[n] for n in names]


def tier_notes(states: list[str] | None, state_live_attempted: bool | None = None) -> dict:
    """Honest per-tier notes for the dashboard. Shared by the CLI and the server
    so a form run shows the same notes as a CLI run.

    ``state_live_attempted``: True when Playwright live checks were attempted
    for the requested states (the v0.3 default); False when live checks were
    disabled (BRANDSTORM_STATE_LIVE=0). None means "decide from the env",
    same rule as pipeline.run.
    """
    if state_live_attempted is None:
        import os as _os
        state_live_attempted = _os.environ.get("BRANDSTORM_STATE_LIVE", "1") != "0"
    if not states:
        state_note = (
            "NOT REQUESTED — the brief named no states, so no state filings were checked. "
            "Add \"states\" (e.g. [\"AZ\"]) or a region in \"geographic_scope\" to check them."
        )
    elif state_live_attempted:
        state_note = (
            f"ATTEMPTED (Playwright) — live browser checks attempted for {', '.join(states)}; "
            "portals that block automation return unknown with the reason — see per-candidate "
            "details. Manual check links included per candidate."
        )
    else:
        state_note = (
            f"MANUAL — live checks disabled (BRANDSTORM_STATE_LIVE=0); manual check links "
            f"included per candidate for {', '.join(states)}."
        )
    return {
        "domain": "LIVE — DNS-over-HTTPS (Google primary, Cloudflare fallback). NXDOMAIN = likely available (not a registrar guarantee).",
        "uspto": "LIVE — tmsearch.uspto.gov companion API (undocumented, no key). Live marks only, target Nice Class. Exact/prefix/phonetic matched locally.",
        "state": state_note,
        "social": "PARTIAL — X + YouTube + Facebook + LinkedIn company live (username checks). Instagram + TikTok + LinkedIn profile return no signal — unknown, never guessed. Display name unknown on all platforms (search is login/JS-gated).",
    }


def summarize(results: list[dict]) -> dict:
    counts = {"clean": 0, "partial": 0, "conflict": 0}
    for r in results:
        counts[r.get("badge", "partial")] += 1
    return {
        "total": len(results),
        "clean": counts["clean"],
        "partial": counts["partial"],
        "conflict": counts["conflict"],
        "com_available": sum(1 for r in results if r.get("domain", {}).get("tlds", {}).get("com") == "available"),
        "com_taken": sum(1 for r in results if r.get("domain", {}).get("tlds", {}).get("com") == "taken"),
        "uspto_unknown": sum(1 for r in results if r.get("uspto", {}).get("status") == "unknown"),
        "domain_unknown": sum(1 for r in results if r.get("domain", {}).get("tlds", {}).get("com") == "unknown"),
    }

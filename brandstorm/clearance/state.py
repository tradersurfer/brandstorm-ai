"""Tier 3 — State business registries.

v0.2: manual-check links only (portals are form/session-gated).
v0.3: live Playwright adapters exist for AZ, CA, TX, FL, NY, DC, MD, VA
(see brandstorm/clearance/state_live.py). When ``live=True``,
``check_state`` delegates to the live adapter for each state that has
one; states without an adapter keep the manual-link fallback, and any
live attempt that fails reports "unknown" with the specific reason and
the manual link — NEVER a guessed taken/clear.

Default is ``live=False`` (v0.2 manual behaviour) so existing callers
and tests are unaffected; the pipeline passes ``live=True`` explicitly
when the run opts into live checks (pipeline ``state_live`` flag,
default True; env BRANDSTORM_STATE_LIVE=0 forces manual-only).

What changed in v0.2: the tier is USER-DRIVEN. v0.1 hardcoded three
states; v0.2 checks exactly the states the user's brief asks for
(explicit ``states`` list, or region phrases in ``geographic_scope`` —
see brandstorm/regions.py). If the brief names no states, the tier
returns "not_requested" with guidance — it never silently defaults to
any region.
"""

from __future__ import annotations

from .registries import get_registry
from . import state_live as _live

GUIDANCE = (
    "No states requested in this brief. Add a \"states\" list "
    '(e.g. ["AZ"]) or name a region in "geographic_scope" '
    '(e.g. "Phoenix, Arizona") to check state filings.'
)


def _manual_entry(code: str) -> dict:
    entry = get_registry(code)
    out = {
        "name": entry["name"] if entry else code,
        "portal": entry["portal"] if entry else "",
        "url": entry["url"] if entry else "",
        "note": entry["note"] if entry else "",
        "verified": entry.get("verified", False) if entry else False,
        "verified_status": entry.get("verified_status") if entry else None,
        "check": "manual",
        "found": None,
        "exact": False,
        "evidence": None,
        "reason": "no live adapter for this state — manual check via the portal link",
        "method": "manual",
        "manual_url": entry["url"] if entry else None,
    }
    return out


def _live_entry(code: str, outcome: dict) -> dict:
    """Merge a live outcome into the v0.2 registry-entry shape."""
    entry = _manual_entry(code)
    entry.update({
        "check": "live" if outcome.get("status") == "live" else "unknown",
        "found": outcome.get("found"),
        "exact": bool(outcome.get("exact")),
        "evidence": outcome.get("evidence"),
        "reason": outcome.get("reason") or "",
        "method": outcome.get("method") or "playwright",
        "manual_url": outcome.get("manual_url") or entry["url"],
    })
    return entry


def _assemble(name: str, per_state: dict[str, dict], requested: bool = True) -> dict:
    """Build the Tier 3 result dict from per-state entries."""
    if not per_state:
        if not requested:
            return {
                "tier": 3,
                "name": "State Business Registries",
                "live": False,
                "method": "No states requested in this brief.",
                "status": "not_requested",
                "guidance": GUIDANCE,
                "states": {},
            }
        return {
            "tier": 3,
            "name": "State Business Registries",
            "live": False,
            "method": "No known states requested — every code was dropped.",
            "status": "manual",
            "states": {},
        }
    checks = {e.get("check") for e in per_state.values()}
    any_live = "live" in checks
    if checks == {"manual"}:
        status = "manual"
    elif checks == {"live"}:
        status = "live"
    elif checks == {"unknown"}:
        status = "unknown"
    else:
        status = "mixed"
    codes = ", ".join(per_state) or "none"
    if status == "manual":
        method = (
            "Manual check via the links below "
            f"({codes}) — no live adapter for these states."
        )
    elif status == "live":
        method = f"Live Playwright check via the state portals ({codes})."
    elif status == "unknown":
        method = (
            "Live check attempted but inconclusive for every state "
            f"({codes}) — see per-state reasons; manual links included."
        )
    else:
        method = (
            "Mixed: some states checked live, some manual or inconclusive "
            f"({codes}) — see per-state outcomes."
        )
    return {
        "tier": 3,
        "name": "State Business Registries",
        "live": any_live,
        "method": method,
        "status": status,
        "states": per_state,
    }


def check_state(name: str, states: list[str] | None = None, live: bool = False) -> dict:
    """Return state-filing outcomes for the requested states.

    states=None/[] -> {"status": "not_requested", ...} with guidance.
    live=False (default) -> {"status": "manual", ...} with portal links (v0.2).
    live=True -> per state: live adapter attempt when one exists
    ("live" with found True/False, or "unknown" with reason), manual
    fallback otherwise. Overall status: live | manual | unknown | mixed.
    """
    states = states or []
    if not states:
        return _assemble(name, {}, requested=False)
    per_state: dict[str, dict] = {}
    for code in states:
        entry = get_registry(code)
        if not entry:
            continue  # unknown code dropped, as in v0.2
        if live and _live.has_adapter(code):
            try:
                outcome = _live.check_state_live(name, code)
            except Exception as e:  # noqa: BLE001 — adapter crash is "unknown"
                outcome = {
                    "status": "unknown", "found": None, "exact": False,
                    "evidence": None, "method": "playwright",
                    "reason": f"adapter error: {e}",
                    "manual_url": entry["url"],
                }
            per_state[code] = _live_entry(code, outcome)
        else:
            per_state[code] = _manual_entry(code)
    return _assemble(name, per_state)


def check_state_batch(names: list[str], states: list[str] | None = None,
                      live: bool = False) -> dict[str, dict]:
    """Tier 3 outcomes for many names at once: {name: check_state result}.

    With live=True, each state with an adapter is swept once with a
    single shared browser (see state_live.check_state_live_batch);
    states without an adapter stay manual. Without live, this is just
    check_state(live=False) per name.
    """
    states = states or []
    if not states:
        return {n: _assemble(n, {}, requested=False) for n in names}
    if not live:
        return {n: check_state(n, states=states, live=False) for n in names}
    adapter_states = [c for c in states if get_registry(c) and _live.has_adapter(c)]
    manual_states = [c for c in states if get_registry(c) and not _live.has_adapter(c)]
    batch_outcomes: dict[str, dict[str, dict]] = {}
    for code in adapter_states:
        try:
            outcomes = _live.check_state_live_batch(names, code)
        except Exception as e:  # noqa: BLE001 — batch crash marks the state unknown
            outcomes = {
                n: {
                    "status": "unknown", "found": None, "exact": False,
                    "evidence": None, "method": "playwright",
                    "reason": f"adapter error: {e}",
                    "manual_url": get_registry(code)["url"],
                }
                for n in names
            }
        for n, outcome in outcomes.items():
            batch_outcomes.setdefault(n, {})[code] = _live_entry(code, outcome)
    out: dict[str, dict] = {}
    for n in names:
        per_state = dict(batch_outcomes.get(n, {}))
        for code in manual_states:
            per_state[code] = _manual_entry(code)
        out[n] = _assemble(n, per_state)
    return out

"""Badge scoring for a cleared candidate.

Badges (per the handoff):
- green  Clean    — .com available, USPTO fully clear, handles clear.
  When .com availability was inferred from DNS (the keyless default),
  the Clean reason says so — DNS-clear is not a registrar guarantee.
  Only a registrar-authoritative method (GoDaddy) gets the unqualified
  reason.
- yellow Partial  — .com taken but trademark clear, or a similar live mark,
                    or a taken handle, or a checked tier came back unknown.
- red    Conflict — an active USPTO mark in the target class matches exactly.

Rules that protect the badge from things that were never verified:
- State filings are "manual" / "not_requested" / "unknown" in v0.2/v0.3
  (form/session-gated portals) and are shown as a separate flag; they
  do not block a green badge, because the spec's green definition is
  domain + trademark + handle. The dashboard says so on every green row.
  ONE exception (v0.3): a LIVE exact entity match — an entity with this
  exact name actually returned by a state portal — makes a name partial
  at best. Unknown/manual state outcomes never change a badge.
- Only LIVE platforms (X, YouTube, Facebook, LinkedIn company — the
  ones with a real server-side signal) can block green as inconclusive
  when their check fails. Instagram, TikTok, and LinkedIn profile are
  always unknown (login wall / HTTP 999) — a documented limitation,
  shown on the row, not a badge blocker; otherwise green would be
  impossible.
- Display-name checks are unknown on every platform in v0.2 and NEVER
  change a badge in either direction — they are informational only.
- A taken handle on ANY live platform keeps a name at partial at best.
"""

from __future__ import annotations

CLEAN = "clean"
PARTIAL = "partial"
CONFLICT = "conflict"

# Fallback for results produced before v0.2 recorded live_platforms.
_DEFAULT_LIVE_PLATFORMS = ["X", "YouTube"]


def score(result: dict) -> tuple[str, str]:
    """Return (badge, reason) for a pipeline result dict."""
    domain = result.get("domain", {})
    uspto = result.get("uspto", {})
    social = result.get("social", {})

    # Red: exact live USPTO match in the target class.
    exact_live = [m for m in uspto.get("matches", []) if m.get("kind") == "exact" and m.get("alive")]
    if exact_live:
        marks = ", ".join(sorted({m["wordmark"] for m in exact_live})[:3])
        return CONFLICT, f"Active USPTO mark in Class {uspto.get('nice_class')}: {marks}"

    reasons: list[str] = []
    com = domain.get("tlds", {}).get("com")
    if com == "taken":
        reasons.append(".com taken")
    elif com == "unknown":
        reasons.append(".com check inconclusive")

    similar = [m for m in uspto.get("matches", []) if m.get("kind") in ("prefix", "phonetic") and m.get("alive")]
    if similar:
        kinds = sorted({m["kind"] for m in similar})
        reasons.append(f"similar live mark ({'/'.join(kinds)}) — review")
    if uspto.get("status") == "unknown":
        reasons.append("USPTO check inconclusive")

    taken_handles = []
    for platform, handles in social.get("platforms", {}).items():
        for handle, status in handles.items():
            if status == "taken":
                taken_handles.append(f"@{handle} on {platform}")
    if taken_handles:
        reasons.append("handle taken: " + ", ".join(taken_handles[:3]))

    # Only LIVE-checked platforms can block green as inconclusive.
    live_platforms = social.get("live_platforms") or _DEFAULT_LIVE_PLATFORMS
    unknown_platforms = [
        p for p in live_platforms
        if any(s == "unknown" for s in social.get("platforms", {}).get(p, {}).values())
    ]
    if unknown_platforms:
        reasons.append("handle check inconclusive: " + ", ".join(sorted(set(unknown_platforms))))

    # Display-name checks are informational only — never a badge factor.
    # State filings never block green either (see module docstring) —
    # EXCEPT a live exact entity match (v0.3): an entity with this exact
    # name is actually registered in a checked state, so the name is
    # partial at best. Unknown/manual state outcomes never change a badge.

    state = result.get("state", {})
    for code, entry in (state.get("states") or {}).items():
        if (entry.get("check") == "live" and entry.get("found") is True
                and entry.get("exact")):
            reasons.append(f"state entity match in {code} — review")
            break

    if reasons:
        return PARTIAL, "; ".join(reasons)

    # Clean. When .com availability was inferred from DNS (the keyless
    # default), say so in the reason — DNS-clear is not a registrar
    # guarantee. Only a registrar-authoritative method (GoDaddy) gets
    # the unqualified reason. A missing method defaults to the caveat.
    if domain.get("method") == "godaddy":
        return CLEAN, "Domain (.com) + trademark + handles clear"
    return CLEAN, ("Domain (.com) + trademark + handles clear "
                   "(DNS-clear only — not a registrar guarantee)")

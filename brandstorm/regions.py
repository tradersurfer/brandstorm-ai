"""Geography resolution for Tier 3 (state filings).

The product is generic: nothing about a user's location is assumed.
Tier 3 checks exactly the states the user's brief asks for.

Precedence (highest first):
  1. Explicit ``states`` in the brief — a list of state/DC codes, e.g.
     ["AZ"]. Always wins; unknown codes are dropped and reported.
  2. Region aliases / state names found in ``geographic_scope`` free text
     (e.g. "DMV" -> DC/MD/VA, "California" -> CA, "Pacific Northwest" ->
     WA/OR). A bare two-letter code is only matched when it is not a
     common English word ("IN", "OR", "ME" would false-positive on
     ordinary text, so they are only resolved via their full state name).
  3. Nothing matched -> no states. Tier 3 then reports "not_requested"
     with guidance, and NEVER silently defaults to any region.

"US National" / "national" on its own resolves to no states: a national
scope is not a state filing, and guessing a state would be wrong.
"""

from __future__ import annotations

import re

from .clearance.registries import REGISTRIES

# Full state / district names (lowercase) -> code.
STATE_NAMES: dict[str, str] = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
    "california": "CA", "colorado": "CO", "connecticut": "CT",
    "delaware": "DE", "district of columbia": "DC",
    "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID",
    "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS",
    "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
    "massachusetts": "MA", "michigan": "MI", "minnesota": "MN",
    "mississippi": "MS", "missouri": "MO", "montana": "MT",
    "nebraska": "NE", "nevada": "NV", "new hampshire": "NH",
    "new jersey": "NJ", "new mexico": "NM", "new york": "NY",
    "north carolina": "NC", "north dakota": "ND", "ohio": "OH",
    "oklahoma": "OK", "oregon": "OR", "pennsylvania": "PA",
    "rhode island": "RI", "south carolina": "SC", "south dakota": "SD",
    "tennessee": "TN", "texas": "TX", "utah": "UT", "vermont": "VT",
    "virginia": "VA", "washington": "WA", "west virginia": "WV",
    "wisconsin": "WI", "wyoming": "WY",
}

# Common region phrases (lowercase) -> state codes.
ALIASES: dict[str, list[str]] = {
    "dmv": ["DC", "MD", "VA"],
    "dc area": ["DC", "MD", "VA"],
    "dc metro": ["DC", "MD", "VA"],
    "washington dc area": ["DC", "MD", "VA"],
    "washington metropolitan": ["DC", "MD", "VA"],
    "district of columbia": ["DC"],
    "washington dc": ["DC"],
    "washington, d.c.": ["DC"],
    "washington d.c.": ["DC"],
    "new york city": ["NY"],
    "nyc": ["NY"],
    "upstate new york": ["NY"],
    "bay area": ["CA"],
    "silicon valley": ["CA"],
    "socal": ["CA"],
    "southern california": ["CA"],
    "norcal": ["CA"],
    "northern california": ["CA"],
    "pacific northwest": ["WA", "OR"],
    "pnw": ["WA", "OR"],
    "new england": ["CT", "MA", "ME", "NH", "RI", "VT"],
    "midwest": ["IL", "IN", "MI", "OH", "WI", "IA", "KS", "MN", "MO", "NE", "ND", "SD"],
    "mid-atlantic": ["DC", "DE", "MD", "NJ", "NY", "PA", "VA", "WV"],
    "northeast": ["CT", "MA", "ME", "NH", "NJ", "NY", "PA", "RI", "VT"],
    "southeast": ["AL", "FL", "GA", "KY", "MS", "NC", "SC", "TN", "VA", "WV"],
    "southwest": ["AZ", "NM", "OK", "TX"],
    "mountain west": ["CO", "ID", "MT", "NV", "UT", "WY"],
    "rocky mountains": ["CO", "ID", "MT", "UT", "WY"],
    "rockies": ["CO", "ID", "MT", "UT", "WY"],
    "west coast": ["CA", "OR", "WA"],
    "east coast": ["CT", "DE", "FL", "GA", "MA", "MD", "ME", "NC", "NH", "NJ", "NY", "PA", "RI", "SC", "VA"],
    "gulf coast": ["AL", "FL", "LA", "MS", "TX"],
    "great lakes": ["IL", "IN", "MI", "MN", "NY", "OH", "PA", "WI"],
    "deep south": ["AL", "GA", "LA", "MS", "SC"],
}

# Bare two-letter codes safe to match as whole words in free text.
# Excluded: IN, OR, ME, HI, ID, OH, OK, MA, PA, LA, NE, DE, AL, AR, IA,
# UT, MO (common English words / interjections — resolve those states
# via their full name instead).
SAFE_BARE_CODES = {
    "AZ", "CA", "TX", "FL", "NY", "WA", "CO", "GA", "NC", "SC", "VA",
    "MD", "DC", "NJ", "CT", "MI", "MN", "WI", "KS", "KY", "TN", "MS",
    "NV", "MT", "WY", "ND", "SD", "WV", "VT", "NH", "RI", "AK",
}

_DC_PHRASES = {"district of columbia", "washington dc", "washington, d.c.", "washington d.c."}


def resolve_states(geographic_scope: str | None = None,
                   states: list[str] | None = None) -> tuple[list[str], str, list[str], list[str]]:
    """Resolve which states Tier 3 should check.

    Returns (codes, source, matched, dropped):
      codes   — validated state/DC codes, in brief order / alias order.
      source  — "explicit" | "alias" | "none".
      matched — phrases/codes that produced the resolution (audit trail).
      dropped — explicit codes that are not real state codes.
    """
    if states:
        codes: list[str] = []
        dropped: list[str] = []
        for s in states:
            code = (s or "").strip().upper()
            if code in REGISTRIES:
                if code not in codes:
                    codes.append(code)
            elif code:
                dropped.append(s)
        return codes, "explicit", list(codes), dropped

    scope = (geographic_scope or "").lower()
    if not scope.strip():
        return [], "none", [], []

    codes = []
    matched: list[str] = []

    def _add(code: str, phrase: str) -> None:
        if code not in codes:
            codes.append(code)
        if phrase not in matched:
            matched.append(phrase)

    is_dc_scope = any(p in scope for p in _DC_PHRASES)
    # Longest phrases first so "washington dc area" wins over "washington".
    for phrase in sorted(ALIASES, key=len, reverse=True):
        if phrase in scope:
            for code in ALIASES[phrase]:
                _add(code, phrase)
    for name, code in STATE_NAMES.items():
        # "Washington" alone means the state; "Washington DC" is the district.
        if name == "washington" and is_dc_scope:
            continue
        if name in scope:
            _add(code, name)
    for code in sorted(SAFE_BARE_CODES):
        if re.search(rf"\b{code.lower()}\b", scope):
            _add(code, code.lower())

    if codes:
        return codes, "alias", matched, []
    return [], "none", [], []

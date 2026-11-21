"""Zero-key-first key plumbing (v0.3).

BrandStorm works out of the box with ZERO keys: keyless DoH domains,
the unofficial USPTO companion API, HTTP-status social checks, and
manual state links. Keys are optional per-tier upgrades, never a
prerequisite.

This module is the ONLY place that reads key environment variables,
and it returns ONLY booleans and display labels — never a key value,
not even partially. The clearance tiers that actually need a key
(domain.py, uspto.py) read ``os.environ`` themselves at call time for
the HTTP request; they never route the value through here, and they
never log it.

Environment variables (names only — values live in the installer's
own Hermes install / shell, never in this repo):

- ``BRANDSTORM_GODADDY_KEY`` + ``BRANDSTORM_GODADDY_SECRET`` — Tier 1
  authoritative domain availability (GoDaddy v1 API, sso-key auth).
  BOTH must be set; one without the other counts as absent.
- ``BRANDSTORM_USPTO_KEY`` — Tier 2 official TSDR verification
  (tsdrapi.uspto.gov, ``USPTO-API-KEY`` header).
- ``BRANDSTORM_LLM_KEY`` — future LLM name generation (no client
  exists yet; the combinatorial generator stays the default).

Social API keys (Meta/Instagram, TikTok, LinkedIn) have no clients
yet, so no readers exist for them here — their env names are defined
in docs/KEY_SETUP.md only. Do not invent clients.
"""

from __future__ import annotations

import os

# Env var NAMES only. Never export the values.
GODADDY_KEY_ENV = "BRANDSTORM_GODADDY_KEY"
GODADDY_SECRET_ENV = "BRANDSTORM_GODADDY_SECRET"
USPTO_KEY_ENV = "BRANDSTORM_USPTO_KEY"
LLM_KEY_ENV = "BRANDSTORM_LLM_KEY"


def _present(name: str) -> bool:
    """True only if the env var is set to a non-blank value."""
    return bool(os.environ.get(name, "").strip())


def godaddy_present() -> bool:
    """True only when BOTH the GoDaddy key and secret are set."""
    return _present(GODADDY_KEY_ENV) and _present(GODADDY_SECRET_ENV)


def uspto_key_present() -> bool:
    """True only when a USPTO (TSDR) key is set."""
    return _present(USPTO_KEY_ENV)


def llm_key_present() -> bool:
    """True only when an LLM key is set (no LLM client exists yet)."""
    return _present(LLM_KEY_ENV)


def keys_status() -> dict:
    """Per-tier key state. Values are ONLY "keyed" or "keyless".

    Never contains a key value, a key fragment, or a key length.
    Tiers with no key concept yet (state: manual links; social: no
    clients exist) always report "keyless".
    """
    return {
        "domain": "keyed" if godaddy_present() else "keyless",
        "uspto": "keyed" if uspto_key_present() else "keyless",
        "state": "keyless",
        "social": "keyless",
        "llm": "keyed" if llm_key_present() else "keyless",
    }


def tier_method_label(tier: str) -> str:
    """Short honest display label for a tier's method, e.g. "keyed (GoDaddy)".

    Unknown tier names return "keyless".
    """
    labels = {
        "domain": "keyed (GoDaddy)" if godaddy_present() else "keyless (DNS)",
        "uspto": "TSDR (keyed)" if uspto_key_present() else "companion API",
        "state": "manual links",
        "social": "keyless (HTTP status)",
        "llm": "keyed (LLM)" if llm_key_present() else "keyless (word bank)",
    }
    return labels.get(tier, "keyless")


def annotate_tier_notes(notes: dict) -> dict:
    """Rewrite the domain/USPTO tier notes to name the method honestly.

    Takes the dict from ``pipeline.tier_notes()`` (pipeline.py is NOT
    edited) and returns a NEW dict; the input is left untouched.
    State/social notes pass through unchanged.
    """
    out = dict(notes)
    if godaddy_present():
        out["domain"] = (
            "KEYED (GoDaddy) — authoritative availability via the GoDaddy v1 API "
            "(GET /v1/domains/available, sso-key auth). Implemented, needs a live "
            "key to verify. On any API error that TLD reports unknown — it never "
            "falls back to DNS, so the method label stays honest."
        )
    else:
        out["domain"] = (
            "KEYLESS (DNS) — DNS-over-HTTPS (Google primary, Cloudflare fallback). "
            "NXDOMAIN = likely available (not a registrar guarantee)."
        )
    if uspto_key_present():
        out["uspto"] = (
            "KEYED (TSDR) — the companion API still finds candidate marks, then "
            "each match is verified against the official TSDR API "
            "(tsdrapi.uspto.gov, USPTO-API-KEY header). Implemented, needs a live "
            "key to verify. TSDR has no wordmark-search endpoint, so it verifies "
            "by serial number; on any TSDR error the tier reports unknown."
        )
    else:
        out["uspto"] = (
            "KEYLESS (companion API) — tmsearch.uspto.gov companion API "
            "(undocumented, no key). Live marks only, target Nice Class. "
            "Exact/prefix/phonetic matched locally."
        )
    return out

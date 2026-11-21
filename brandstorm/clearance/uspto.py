"""Tier 2 — USPTO trademark search: keyless companion API, or keyed TSDR.

KEYLESS (default, zero keys): the Trademark Search companion service
behind the official UI at tmsearch.uspto.gov. This is an UNOFFICIAL,
undocumented companion API — not a published USPTO developer API —
discovered via the UI's own configuration.json
(serviceUrlSearchElastic). It currently answers without an API key,
behind AWS WAF. Verified live 2026-11-11 from this VM:
  GET  https://tmsearch.uspto.gov/configuration.json
  POST https://tmsearch.uspto.gov/prod-stage-v1-0-0/tmsearch
       (Elasticsearch-style body; response envelope hits.totalValue / hits.hits[].source)

KEYED (BRANDSTORM_USPTO_KEY set): the official TSDR API verifies each
match the companion API found. Important, verified against USPTO's
docs (developer.uspto.gov TSDR API; spec at
data.uspto.gov/swagger/tsdr-swagger.yaml): TSDR has NO wordmark-search
endpoint — it is identifier-driven retrieval only. So the keyed path
is discovery via the companion API + verification by serial number:
  GET https://tsdrapi.uspto.gov/ts/cd/casestatus/sn{serial}/info
  Header: USPTO-API-KEY: {key}
  Header: Accept: application/json
  (Rate limits published by USPTO: 60 requests/key/minute peak,
  120 off-peak; key from account.uspto.gov/api-manager.)
On ANY TSDR error (auth failure, 4xx/5xx, timeout, unparseable body)
the whole tier reports "unknown" with the reason — the code NEVER
falls back to companion-only results and labels them "tsdr". Status:
implemented, needs a live key to verify (no key exists yet to test with).

The versioned companion path (prod-stage-v1-0-0) can change; the
client re-discovers it from configuration.json on each run and falls
back to the last known path. If WAF blocks us, the tier reports
"unknown" — never a fake clear.

Matching is done LOCALLY on returned hits:
- exact:    normalized wordmark == normalized candidate
- prefix:   one startswith the other (normalized)
- phonetic: Soundex(first token) equal but spelling differs
Only LIVE marks (alive=true) in the target Nice Class count.
"""

from __future__ import annotations

import json
import os
import re
import xml.etree.ElementTree as _ET

from ..keys import USPTO_KEY_ENV, uspto_key_present
from ..phonetics import soundex
from . import http_get, http_post_json

_CONFIG_URL = "https://tmsearch.uspto.gov/configuration.json"
_FALLBACK_BASE = "https://tmsearch.uspto.gov/prod-stage-v1-0-0/"
_SEARCH_PATH = "tmsearch"

# Official TSDR API (keyed verification by serial number only).
_TSDR_BASE = "https://tsdrapi.uspto.gov"
_TSDR_CASESTATUS = _TSDR_BASE + "/ts/cd/casestatus/sn{serial}/info"

_base_cache: str | None = None


def _discover_base() -> str:
    global _base_cache
    if _base_cache:
        return _base_cache
    status, body, _ = http_get(_CONFIG_URL, timeout=10.0)
    if status == 200:
        try:
            import json
            base = json.loads(body).get("serviceUrlSearchElastic")
            if base:
                _base_cache = base if base.endswith("/") else base + "/"
                return _base_cache
        except Exception:
            pass
    _base_cache = _FALLBACK_BASE
    return _base_cache


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def _classify_hit(wordmark: str, candidate: str) -> str | None:
    """'exact' | 'prefix' | 'phonetic' | None for one live hit."""
    wm, cand = _norm(wordmark), _norm(candidate)
    if not wm or not cand:
        return None
    if wm == cand:
        return "exact"
    if wm.startswith(cand) or cand.startswith(wm):
        return "prefix"
    # Phonetic: first tokens sound alike but are spelled differently.
    # Identical first tokens are NOT phonetic (e.g. live "DESERT RLTY" vs
    # candidate "DESERT YARD" share the anchor word, not a sound-alike).
    wm_tok, cand_tok = wm.split()[0], cand.split()[0]
    if wm_tok != cand_tok and soundex(wm_tok) == soundex(cand_tok):
        return "phonetic"
    return None


def _parse_tsdr_body(body: bytes) -> dict:
    """Extract a live/dead signal from a TSDR case-status response.

    TSDR content-negotiates: JSON with ``Accept: application/json``,
    ST96 XML otherwise. Returns {"status_text": str|None,
    "dead": bool|None}. "dead" is True only on an explicit DEAD
    signal; anything unparseable leaves it None (unknown, not dead).
    """
    text = (body or b"").decode("utf-8", "replace").strip()
    if not text:
        return {"status_text": None, "dead": None}
    try:
        data = json.loads(text)
        return _tsdr_from_json(data)
    except Exception:
        pass
    try:
        root = _ET.fromstring(text)
    except Exception:
        return {"status_text": None, "dead": None}
    status_text: str | None = None
    dead: bool | None = None
    for el in root.iter():
        tag = el.tag.rsplit("}", 1)[-1].lower()
        val = (el.text or "").strip()
        if not val:
            continue
        if tag in ("livedeadindicator", "live-dead-indicator", "marklivedead"):
            dead = val.upper() == "DEAD"
            status_text = status_text or val
        elif tag in ("statuscode", "statusdescription", "markstatus"):
            status_text = status_text or val
    return {"status_text": status_text, "dead": dead}


def _tsdr_from_json(data, _depth: int = 0) -> dict:
    """Walk a TSDR JSON tree for a status / live-dead signal."""
    status_text: str | None = None
    dead: bool | None = None
    if isinstance(data, dict):
        for key, val in data.items():
            lk = str(key).lower()
            if isinstance(val, str) and val.strip():
                if "livedead" in lk or lk in ("live_dead", "marklivedead"):
                    dead = val.strip().upper() == "DEAD"
                    status_text = status_text or val.strip()
                elif lk in ("statuscode", "statusdescription", "status", "markstatus"):
                    status_text = status_text or val.strip()
            elif isinstance(val, (dict, list)) and _depth < 6:
                sub = _tsdr_from_json(val, _depth + 1)
                status_text = status_text or sub["status_text"]
                dead = sub["dead"] if dead is None else dead
    elif isinstance(data, list) and _depth < 6:
        for item in data:
            sub = _tsdr_from_json(item, _depth + 1)
            status_text = status_text or sub["status_text"]
            dead = sub["dead"] if dead is None else dead
    return {"status_text": status_text, "dead": dead}


def _tsdr_verify(serial: str, timeout: float = 10.0) -> tuple[dict | None, str | None]:
    """Verify one serial against the official TSDR API.

    Returns (parsed_status, error_reason). parsed_status is None on
    error. The key is read from the environment here, at call time,
    and is never logged or returned.
    """
    digits = re.sub(r"\D", "", serial or "")
    if not digits:
        return None, "TSDR verification needs a serial number"
    url = _TSDR_CASESTATUS.format(serial=digits)
    headers = {
        "Accept": "application/json",
        "USPTO-API-KEY": os.environ.get(USPTO_KEY_ENV, ""),
    }
    status, body, err = http_get(url, timeout=timeout, headers=headers)
    if status is None:
        return None, f"TSDR request failed: {err or 'transport error'}"
    if status in (401, 403):
        return None, f"TSDR auth failed (HTTP {status}) — check the USPTO key"
    if status == 404:
        # The gateway can return 404 for an invalid key; never read it
        # as "case not found".
        return None, "TSDR returned HTTP 404 — case not found or key rejected"
    if status == 429:
        return None, "TSDR rate-limited (HTTP 429)"
    if status != 200:
        return None, f"TSDR returned HTTP {status}"
    return _parse_tsdr_body(body), None


def _verify_matches_tsdr(matches: list[dict]) -> tuple[list[dict], str | None]:
    """Verify every companion match against TSDR. On ANY verification
    error returns ([], reason) — the tier must report unknown, never
    a companion-only result labelled "tsdr"."""
    verified: list[dict] = []
    for m in matches:
        parsed, err = _tsdr_verify(str(m.get("serial") or ""))
        if err is not None or parsed is None:
            return [], err or "TSDR verification failed"
        m = dict(m)
        m["tsdr_verified"] = True
        m["tsdr_status"] = parsed.get("status_text")
        if parsed.get("dead") is True:
            m["alive"] = False
        verified.append(m)
    return verified, None


def search_marks(wordmark: str, nice_class: str, size: int = 10) -> tuple[list[dict], str]:
    """Search live marks for a wordmark in a Nice class.

    Returns (matches, status) where status is 'ok' | 'unknown'.
    Each match: {wordmark, serial, status, alive, classes, kind}.
    Keyed matches also carry tsdr_verified=True and tsdr_status.
    """
    base = _discover_base()
    body = {
        "query": {
            "bool": {
                "must": [
                    {"match": {"wordmark": wordmark}},
                    {"term": {"internationalClass": nice_class}},
                    {"term": {"alive": True}},
                ]
            }
        },
        "size": size,
    }
    status, data, err = http_post_json(base + _SEARCH_PATH, body, timeout=20.0)
    if status is None or data is None:
        _set_last_error(f"companion API request failed: {err or 'transport error'}")
        return [], "unknown"
    if status in (403, 429):
        _set_last_error(f"companion API blocked/rate-limited (HTTP {status})")
        return [], "unknown"  # WAF / rate limit — never fake a clear
    if status != 200:
        _set_last_error(f"companion API returned HTTP {status}")
        return [], "unknown"
    matches: list[dict] = []
    for hit in (data.get("hits", {}) or {}).get("hits", []) or []:
        src = hit.get("source", {}) or {}
        kind = _classify_hit(src.get("wordmark") or "", wordmark)
        if kind is None:
            continue
        matches.append({
            "wordmark": src.get("wordmark"),
            "serial": src.get("serialNumber") or src.get("id"),
            "status": src.get("statusDescription"),
            "alive": bool(src.get("alive")),
            "classes": src.get("internationalClass"),
            "kind": kind,
        })
    if uspto_key_present():
        # Keyed path: TSDR verifies each match by serial number.
        # TSDR has no search endpoint, so discovery stays companion;
        # verification is what the key buys. Any verification error
        # makes the whole tier unknown — never companion-only results
        # labelled "tsdr".
        verified, tsdr_err = _verify_matches_tsdr(matches)
        if tsdr_err is not None:
            _set_last_error(tsdr_err)
            return [], "unknown"
        _set_last_error(None)
        return verified, "ok"
    _set_last_error(None)
    return matches, "ok"


_LAST_ERROR: str | None = None


def _set_last_error(err: str | None) -> None:
    global _LAST_ERROR
    _LAST_ERROR = err


def check_uspto(name: str, nice_class: str = "025") -> dict:
    """Check USPTO marks. "method" is the short code ("tsdr" | "companion");
    "method_detail" is the human-readable description."""
    matches, status = search_marks(name, nice_class)
    keyed = uspto_key_present()
    result = {
        "tier": 2,
        "name": "USPTO Trademark Search",
        "live": status == "ok",
        "method": "tsdr" if keyed else "companion",
        "method_detail": (
            "Companion API finds candidates; each match verified against the official "
            "TSDR API (tsdrapi.uspto.gov, USPTO-API-KEY header). TSDR has no wordmark-"
            "search endpoint — verification is by serial number. Implemented, needs a "
            "live key to verify."
            if keyed else
            "POST tmsearch.uspto.gov companion API (undocumented, no key); live marks "
            "only, Nice Class " + nice_class
        ),
        "nice_class": nice_class,
        "status": status,
        "matches": matches,
        "exact_live": any(m["kind"] == "exact" and m["alive"] for m in matches),
    }
    if _LAST_ERROR is not None:
        result["error"] = _LAST_ERROR
    return result

"""Tier 1 — Domain availability: keyless DNS-over-HTTPS, or keyed GoDaddy.

KEYLESS (default, zero keys): availability is inferred from DNS — a
domain that resolves (A record present) is TAKEN; a domain that
returns NXDOMAIN is very likely AVAILABLE. That signal is strong but
NOT absolute proof — a domain can be registered without any DNS
records, so "available" here means "no DNS presence found", not a
registrar guarantee.

KEYED (both BRANDSTORM_GODADDY_KEY and BRANDSTORM_GODADDY_SECRET set):
authoritative availability from the GoDaddy v1 API, per GoDaddy's
developer docs (developer.godaddy.com/doc/endpoint/domains):
  GET https://api.godaddy.com/v1/domains/available
      ?domain={fqdn}&checkType=FAST&forTransfer=false
  Authorization: sso-key {KEY}:{SECRET}
Response JSON: {"available": bool, "definitive": bool, "domain": ...}.
On ANY error in the keyed path (auth failure, 4xx/5xx, timeout,
unparseable body) that TLD reports "unknown" with the reason — the
code NEVER silently falls back to DoH, because that would mislabel
the method. Status: implemented, needs a live key to verify (no key
exists yet). Caveats found while reading the docs: GoDaddy's landing
page now fronts a v3 API (Bearer PAT, GET /v3/domains/check-availability)
while v1/sso-key remains the documented path for the key+secret pair
this module uses; and several sources report the availability API
needs 50+ domains on the account (others say only bulk checks do) —
verify at signup before relying on it.

Primary keyless resolver: Google dns.google/resolve. Fallback:
Cloudflare cloudflare-dns.com/dns-query (application/dns-json).
"""

from __future__ import annotations

import json
import os
import urllib.parse

from . import http_get
from ..keys import GODADDY_KEY_ENV, GODADDY_SECRET_ENV, godaddy_present

TLDS = ["com", "co", "studio", "supply", "app"]

_RESOLVERS = [
    "https://dns.google/resolve?name={name}&type=A",
    "https://cloudflare-dns.com/dns-query?name={name}&type=A",
]
_CF_HEADERS = {"Accept": "application/dns-json"}

_GODADDY_BASE = "https://api.godaddy.com"
_GODADDY_AVAILABLE = _GODADDY_BASE + "/v1/domains/available"


def _godaddy_status(name: str, timeout: float = 8.0) -> tuple[str, str | None]:
    """Authoritative availability for one FQDN via the GoDaddy v1 API.

    Returns (status, error_reason). status is 'taken' | 'available' |
    'unknown'. The key/secret are read from the environment here, at
    call time, and are never logged or returned.
    """
    key = os.environ.get(GODADDY_KEY_ENV, "")
    secret = os.environ.get(GODADDY_SECRET_ENV, "")
    url = _GODADDY_AVAILABLE + "?domain=" + urllib.parse.quote(name) + "&checkType=FAST&forTransfer=false"
    headers = {
        "Accept": "application/json",
        "Authorization": "sso-key " + key + ":" + secret,
    }
    status, body, err = http_get(url, timeout=timeout, headers=headers)
    if status is None:
        return "unknown", f"GoDaddy request failed: {err or 'transport error'}"
    if status in (401, 403):
        return "unknown", f"GoDaddy auth failed (HTTP {status}) — check the key/secret"
    if status == 429:
        return "unknown", "GoDaddy rate-limited (HTTP 429)"
    if status != 200:
        return "unknown", f"GoDaddy returned HTTP {status}"
    try:
        data = json.loads(body)
    except Exception:
        return "unknown", "GoDaddy returned an unparseable response"
    available = data.get("available")
    if not isinstance(available, bool):
        return "unknown", "GoDaddy response had no availability flag"
    return ("available" if available else "taken"), None


def _doh_status(name: str, timeout: float = 8.0) -> str:
    """'taken' | 'available' | 'unknown' for one fully-qualified domain name."""
    for template in _RESOLVERS:
        url = template.format(name=urllib.parse.quote(name))
        headers = _CF_HEADERS if "cloudflare" in template else None
        status, body, err = http_get(url, timeout=timeout, headers=headers)
        if status is None or status != 200:
            continue  # try the next resolver
        try:
            data = json.loads(body)
        except Exception:
            continue
        dns_status = data.get("Status")
        if dns_status == 0 and data.get("Answer"):
            return "taken"
        if dns_status == 3:  # NXDOMAIN
            return "available"
        if dns_status == 0 and not data.get("Answer"):
            # NOERROR with no records: no DNS presence. Treat as available
            # with the same caveat as NXDOMAIN (see module docstring).
            return "available"
        # Other DNS statuses (2 SERVFAIL, etc.) -> try next resolver.
    return "unknown"


def check_domain(compact_name: str, tlds: list[str] | None = None) -> dict:
    """Check each TLD for a compact name. Returns per-TLD status + summary.

    "method" is the short code ("godaddy" | "doh"); "method_detail" is
    the human-readable description. When keys are present the keyed
    path is used for EVERY TLD — no silent DoH fallback.
    """
    tlds = tlds or TLDS
    per_tld: dict[str, str] = {}
    error: str | None = None
    if godaddy_present():
        for tld in tlds:
            status, err = _godaddy_status(f"{compact_name}.{tld}")
            per_tld[tld] = status
            if err and error is None:
                error = err
        result = {
            "tier": 1,
            "name": "Domain (GoDaddy)",
            "live": True,
            "method": "godaddy",
            "method_detail": (
                "GoDaddy v1 API (GET /v1/domains/available, sso-key auth); "
                "authoritative registrar answer. Implemented, needs a live key to verify."
            ),
            "tlds": per_tld,
            "com": per_tld.get("com", "unknown"),
        }
    else:
        for tld in tlds:
            per_tld[tld] = _doh_status(f"{compact_name}.{tld}")
        result = {
            "tier": 1,
            "name": "Domain (DNS-over-HTTPS)",
            "live": True,
            "method": "doh",
            "method_detail": (
                "Google dns.google/resolve, Cloudflare fallback; A-record presence = taken, "
                "NXDOMAIN = likely available (not a registrar guarantee)"
            ),
            "tlds": per_tld,
            "com": per_tld.get("com", "unknown"),
        }
    if error is not None:
        result["error"] = error
    return result

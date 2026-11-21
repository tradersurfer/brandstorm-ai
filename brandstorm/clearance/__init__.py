"""Shared helpers for clearance tiers: polite HTTP + result shape."""

from __future__ import annotations

import json
import urllib.error
import urllib.request

USER_AGENT = "BrandStormAI/0.2 (prototype)"


def http_get_final(url: str, timeout: float = 10.0, headers: dict | None = None) -> tuple[int | None, bytes, str | None, str]:
    """GET a URL, following redirects. Returns (status, body, final_url, error).

    Needed by the Facebook check: a free handle returns HTTP 200 but the
    final URL is a login redirect, while a taken handle stays on the
    profile URL. Status alone cannot tell them apart.
    """
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **(headers or {})}, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read(), resp.geturl(), ""
    except urllib.error.HTTPError as e:
        try:
            final = e.geturl()
        except Exception:
            final = None
        try:
            return e.code, e.read(), final, ""
        except Exception:
            return e.code, b"", final, ""
    except Exception as e:  # timeout, DNS failure, TLS error, ...
        return None, b"", None, f"{type(e).__name__}: {e}"


def http_get(url: str, timeout: float = 10.0, headers: dict | None = None) -> tuple[int | None, bytes, str]:
    """GET a URL. Returns (status_code, body, error). status None on transport error."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **(headers or {})}, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read(), ""
    except urllib.error.HTTPError as e:
        try:
            return e.code, e.read(), ""
        except Exception:
            return e.code, b"", ""
    except Exception as e:  # timeout, DNS failure, TLS error, ...
        return None, b"", f"{type(e).__name__}: {e}"


def http_post_json(url: str, payload: dict, timeout: float = 20.0) -> tuple[int | None, dict | None, str]:
    """POST JSON. Returns (status_code, parsed_json_or_None, error)."""
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json", "User-Agent": USER_AGENT},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read() or b"{}"), ""
    except urllib.error.HTTPError as e:
        try:
            body = e.read()
            return e.code, json.loads(body or b"{}"), ""
        except Exception:
            return e.code, None, ""
    except Exception as e:
        return None, None, f"{type(e).__name__}: {e}"

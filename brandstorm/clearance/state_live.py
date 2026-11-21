"""Tier 3 — LIVE state business registry checks via Playwright (v0.3).

One adapter per state. Each adapter knows its portal URL (taken from
``brandstorm/clearance/registries.py``), how to fill the entity-name
search, submit it, and parse found / not-found from what the browser
actually saw.

HONESTY CONTRACT (same as the rest of Tier 3): on ANY failure —
timeout, bot-block, captcha, unexpected page shape, navigation error —
the adapter returns ``status: "unknown"`` with the SPECIFIC reason and
the manual portal link. It never guesses taken/clear. ``found=True``
means an entity with that/similar name was actually returned; ``exact``
is True only when the top returned name normalises to the queried name.

What the live probes on 2026-11-13 actually found (sandbox egress):
- AZ eCorp: form fills and submits fine, but every submit is met with
  a 6-character image CAPTCHA ("User validation required to continue").
  Verified twice, including with automation flags masked. AZ is
  therefore live-attempted but honestly ``unknown`` (captcha).
- CA bizfile: the portal's security service blocks the request outright
  ("This request was blocked by our security service", errorCode 15).
- FL Sunbiz / NY DOS: navigation fails repeatedly from this sandbox
  (ERR_EMPTY_RESPONSE / ERR_CERT_AUTHORITY_INVALID) — the portals never
  render, so no search can be attempted.
- TX SOSDirect: landing page loads, but there is no public entity-name
  search form on it — entity search lives inside the SOSDirect account
  portal, and the visible ``#query`` box is site search, not entity
  search (the adapter refuses to use it).
- DC BOSS / MD Business Express / VA SCC CIS: pages load but the search
  UI is inconsistent (DC's search input renders 0x0 on some loads; MD
  submits with no visible result; VA stalls behind a cookie gate).
  The generic adapter attempts them and reports ``unknown`` with the
  specific reason when the flow cannot be completed.

Sandbox egress note: this VM reaches the internet through an
authenticating MITM egress proxy (``https_proxy`` env). Chromium
cannot authenticate to it directly (CONNECT fails) and does not trust
its CA, so when the sandbox CA bundle
(``/run/hatch/egress-tls/ca-bundle.pem``) is present this module spins
up a tiny in-process localhost CONNECT relay that adds the
Proxy-Authorization header from the env proxy URL, and launches
Chromium against the relay with ``ignore_https_errors=True`` (the
egress proxy re-signs TLS with the sandbox CA). On a normal machine
(no sandbox CA bundle) Playwright is launched directly, using the env
proxy if one is set, with normal certificate verification. The relay
never logs the proxy credential.
"""

from __future__ import annotations

import base64
import os
import re
import select
import socket
import threading

from .registries import get_registry

# Phrases that mean "a human check is being demanded / we are blocked".
BLOCK_PHRASES = (
    "user validation required",
    "enter the 6 characters",
    "verify you are human",
    "are you a robot",
    "not a robot",
    "blocked by our security service",
    "security service",
    "access denied",
    "unusual traffic",
    "captcha",
    "verify your identity",
)

# Phrases that mean "the portal searched and found nothing".
NO_RESULT_PHRASES = (
    "no records found",
    "no results found",
    "no results",
    "no entities found",
    "no matches found",
    "no business found",
    "0 results",
    "nothing found",
    "search returned no",
)

_SANDBOX_CA_BUNDLE = "/run/hatch/egress-tls/ca-bundle.pem"

# Legal suffixes stripped when comparing a returned name to the query.
_SUFFIXES = ("llc", "inc", "corp", "corporation", "co", "ltd", "lp", "llp", "pllc")


def _normalise_name(name: str) -> str:
    """Lowercase, drop punctuation, drop a trailing legal suffix."""
    tokens = re.sub(r"[^a-z0-9 ]", " ", name.lower()).split()
    while tokens and tokens[-1] in _SUFFIXES:
        tokens.pop()
    return " ".join(tokens)


def _manual_url(code: str) -> str | None:
    entry = get_registry(code)
    return entry["url"] if entry else None


# ---------------------------------------------------------------------------
# Sandbox CONNECT relay (see module docstring — sandbox-only path).
# ---------------------------------------------------------------------------

_relay_lock = threading.Lock()
_relay_port: int | None = None


def _proxy_env_url() -> str | None:
    return os.environ.get("https_proxy") or os.environ.get("HTTPS_PROXY")


def _in_sandbox() -> bool:
    return bool(_proxy_env_url()) and os.path.exists(_SANDBOX_CA_BUNDLE)


def _relay_handle(client: socket.socket, up_host: str, up_port: int, auth: str) -> None:
    try:
        data = b""
        while b"\r\n\r\n" not in data:
            chunk = client.recv(4096)
            if not chunk:
                return
            data += chunk
            if len(data) > 65536:
                return
        line = data.split(b"\r\n")[0].decode("latin-1")
        parts = line.split(" ")
        if len(parts) < 2 or parts[0] != "CONNECT":
            client.sendall(b"HTTP/1.1 405 Method Not Allowed\r\n\r\n")
            return
        hostport = parts[1]
        upstream = socket.create_connection((up_host, up_port), timeout=20)
        upstream.sendall(
            f"CONNECT {hostport} HTTP/1.1\r\n"
            f"Host: {hostport}\r\n"
            f"Proxy-Authorization: Basic {auth}\r\n"
            "Proxy-Connection: keep-alive\r\n\r\n".encode("latin-1")
        )
        resp = b""
        while b"\r\n\r\n" not in resp:
            chunk = upstream.recv(4096)
            if not chunk:
                raise RuntimeError("no CONNECT response from egress proxy")
            resp += chunk
        if b" 200 " not in resp.split(b"\r\n")[0]:
            client.sendall(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
            upstream.close()
            return
        client.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")

        def _pump(src: socket.socket, dst: socket.socket) -> None:
            try:
                while True:
                    ready, _, _ = select.select([src], [], [], 120)
                    if not ready:
                        break
                    chunk = src.recv(65536)
                    if not chunk:
                        break
                    dst.sendall(chunk)
            except Exception:
                pass
            try:
                dst.shutdown(socket.SHUT_WR)
            except Exception:
                pass

        t = threading.Thread(target=_pump, args=(upstream, client), daemon=True)
        t.start()
        _pump(client, upstream)
        t.join(timeout=5)
    except Exception:
        pass
    finally:
        try:
            client.close()
        except Exception:
            pass


def _ensure_sandbox_relay() -> int:
    """Start (once per process) the localhost CONNECT relay. Returns its port."""
    global _relay_port
    with _relay_lock:
        if _relay_port is not None:
            return _relay_port
        from urllib.parse import urlparse

        parsed = urlparse(_proxy_env_url())
        up_host, up_port = parsed.hostname, parsed.port or 3128
        auth = base64.b64encode(
            f"{parsed.username or ''}:{parsed.password or ''}".encode()
        ).decode()
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("127.0.0.1", 0))
        srv.listen(50)
        port = srv.getsockname()[1]

        def _serve() -> None:
            while True:
                try:
                    conn, _ = srv.accept()
                except Exception:
                    return
                threading.Thread(
                    target=_relay_handle, args=(conn, up_host, up_port, auth), daemon=True
                ).start()

        threading.Thread(target=_serve, daemon=True).start()
        _relay_port = port
        return port


def _launch_kwargs() -> tuple[dict, bool]:
    """(playwright launch kwargs, ignore_https_errors) for this machine."""
    if _in_sandbox():
        port = _ensure_sandbox_relay()
        return {"proxy": {"server": f"http://127.0.0.1:{port}"}}, True
    proxy_url = _proxy_env_url()
    if proxy_url:
        return {"proxy": {"server": proxy_url}}, False
    return {}, False


# ---------------------------------------------------------------------------
# Adapters
#
# Each adapter: the portal search URL plus how to drive it. ``fill`` is a
# Playwright selector for the entity-name input (None = generic discovery);
# ``submit_text`` is the button text to click (None = press Enter);
# ``pre`` is an optional list of (selector-or-text, kind) steps to run
# before filling (e.g. cookie consent, "Business Name" radio).
# ---------------------------------------------------------------------------

ADAPTERS: dict[str, dict] = {
    "AZ": {
        "url": "https://arizonabusinesscenter.azcc.gov/businesssearch",
        "fill": "#businessName",
        "submit_text": "Business Search",
        "pre": [("Exact Match", "text")],
        "method": "playwright: fill #businessName, Exact Match, submit",
    },
    "CA": {
        "url": "https://bizfileonline.sos.ca.gov/search/business",
        "fill": None,
        "submit_text": None,
        "pre": [],
        "method": "playwright: generic entity-name search form",
    },
    "TX": {
        "url": "https://www.sos.state.tx.us/corp/sosda/index.shtml",
        "fill": None,
        "submit_text": None,
        "pre": [],
        "method": "playwright: generic entity-name search form (site search excluded)",
    },
    "FL": {
        "url": "https://search.sunbiz.org/Inquiry/CorporationSearch/ByName",
        "fill": None,
        "submit_text": None,
        "pre": [],
        "method": "playwright: generic entity-name search form",
    },
    "NY": {
        "url": "https://apps.dos.ny.gov/publicInquiry/EntitySearch",
        "fill": None,
        "submit_text": None,
        "pre": [],
        "method": "playwright: generic entity-name search form",
    },
    "DC": {
        "url": "https://boss.dc.gov/homepage",
        "fill": None,
        "submit_text": None,
        "pre": [],
        "method": "playwright: generic entity-name search form",
    },
    "MD": {
        "url": "https://egov.maryland.gov/BusinessExpress/EntitySearch",
        "fill": None,
        "submit_text": "Search",
        "pre": [("Business Name", "text")],
        "method": "playwright: 'Business Name' search, submit",
    },
    "VA": {
        "url": "https://cis.scc.virginia.gov/",
        "fill": None,
        "submit_text": None,
        "pre": [("Accept", "button")],
        "method": "playwright: cookie consent, then generic entity-name search form",
    },
}


def has_adapter(code: str) -> bool:
    return (code or "").strip().upper() in ADAPTERS


def adapter_codes() -> list[str]:
    return sorted(ADAPTERS)


def _classify_body(body: str, name: str) -> tuple[bool | None, str | None, bool]:
    """Classify a results page body.

    Returns (found, top_result_name, blocked): found None means the page
    could not be classified (unexpected shape) — never a guess.
    """
    low = body.lower()
    for phrase in BLOCK_PHRASES:
        if phrase in low:
            return None, None, True
    for phrase in NO_RESULT_PHRASES:
        if phrase in low:
            return False, None, False
    norm = _normalise_name(name)
    if norm:
        # Look for the queried name (or its compact form) in the body.
        compact = norm.replace(" ", "")
        for line in (ln.strip() for ln in body.splitlines() if ln.strip()):
            line_norm = _normalise_name(line)
            if line_norm and (line_norm == norm or line_norm.replace(" ", "") == compact
                              or norm in line_norm):
                return True, line[:120], False
    return None, None, False


def _generic_fill_and_submit(page, name: str, adapter: dict, timeout_ms: int) -> None:
    """Fill the entity-name input and submit, discovering the form.

    Prefers inputs whose id/name/placeholder/label mentions
    business/entity/company/corp/name; refuses the site-search box
    (e.g. TX ``#query``) by requiring that signal. Raises RuntimeError
    with a specific reason when no usable form is found.
    """
    info = page.evaluate("""() => {
      const out = [];
      document.querySelectorAll('input').forEach((el, i) => {
        const r = el.getBoundingClientRect();
        const label = (el.closest('label')?.innerText || '') + ' ' +
          (document.querySelector(`label[for="${el.id}"]`)?.innerText || '');
        out.push({i, type: el.type || '', name: el.name || '', id: el.id || '',
                  ph: el.placeholder || '', label: label.trim().slice(0, 80),
                  visible: r.width > 0 && r.height > 0 && el.type !== 'hidden'});
      });
      return out;
    }""")
    best = None
    best_score = 0
    for cand in info:
        if not cand["visible"]:
            continue
        if cand["type"] not in ("text", "search", ""):
            continue
        hay = f"{cand['name']} {cand['id']} {cand['ph']} {cand['label']}".lower()
        score = 0
        if re.search(r"business|entity|company|corp", hay):
            score += 3
        if "name" in hay:
            score += 2
        if cand["id"] == "query" or cand["name"] == "query":
            score -= 5  # site search, not entity search (TX)
        if score > best_score:
            best_score, best = score, cand
    if best is None or best_score <= 0:
        raise RuntimeError("no entity-name search form found on the portal page")
    page.locator(f"input >> nth={best['i']}").fill(name, timeout=timeout_ms)
    submit_text = adapter.get("submit_text")
    clicked = False
    if submit_text:
        try:
            page.get_by_role("button", name=submit_text).first.click(timeout=5000)
            clicked = True
        except Exception:
            pass
    if not clicked:
        try:
            page.locator("button:has-text('Search'), input[type=submit]").first.click(timeout=5000)
            clicked = True
        except Exception:
            pass
    if not clicked:
        page.keyboard.press("Enter")


def _search_once(page, name: str, code: str, timeout_ms: int) -> dict:
    """Drive one search on an already-open page. Returns the outcome dict."""
    adapter = ADAPTERS[code]
    manual_url = adapter["url"]
    try:
        page.goto(adapter["url"], timeout=timeout_ms, wait_until="domcontentloaded")
    except Exception as e:
        return {
            "status": "unknown", "found": None, "evidence": None,
            "method": adapter["method"],
            "reason": f"navigation failed: {str(e).splitlines()[0][:200] if str(e) else 'unknown error'}",
            "manual_url": manual_url,
        }
    page.wait_for_timeout(3000)
    try:
        for text, kind in adapter.get("pre", []):
            try:
                if kind == "button":
                    page.get_by_role("button", name=text).first.click(timeout=5000)
                else:
                    page.get_by_text(text, exact=True).first.click(timeout=5000)
                page.wait_for_timeout(500)
            except Exception:
                pass  # pre-step optional (cookie banner / radio may be absent)
        if adapter.get("fill"):
            page.locator(adapter["fill"]).fill(name, timeout=timeout_ms)
            submit_text = adapter.get("submit_text")
            if submit_text:
                page.get_by_role("button", name=submit_text).last.click(timeout=timeout_ms)
            else:
                page.keyboard.press("Enter")
        else:
            _generic_fill_and_submit(page, name, adapter, timeout_ms)
    except Exception as e:
        # If the page that loaded is itself a block/captcha page, say so
        # instead of "no form found" (e.g. CA's security-service block).
        try:
            body = page.inner_text("body")
            found_b, _, blocked_b = _classify_body(body, name)
            if blocked_b:
                phrase = next((p for p in BLOCK_PHRASES if p in body.lower()), "bot-check")
                return {
                    "status": "unknown", "found": None, "evidence": None,
                    "method": adapter["method"],
                    "reason": f"portal presented a bot-check/block ({phrase}) — human check required",
                    "manual_url": manual_url,
                }
        except Exception:
            pass
        return {
            "status": "unknown", "found": None, "evidence": None,
            "method": adapter["method"],
            "reason": f"search form could not be driven: {str(e).splitlines()[0][:200] if str(e) else 'unknown error'}",
            "manual_url": manual_url,
        }
    page.wait_for_timeout(5000)
    try:
        title = page.title()
        body = page.inner_text("body")
    except Exception as e:
        return {
            "status": "unknown", "found": None, "evidence": None,
            "method": adapter["method"],
            "reason": f"results page could not be read: {str(e).splitlines()[0][:200] if str(e) else 'unknown error'}",
            "manual_url": manual_url,
        }
    found, top, blocked = _classify_body(body, name)
    snippet = body[:300].replace("\n", " | ")
    if blocked:
        phrase = next((p for p in BLOCK_PHRASES if p in body.lower()), "bot-check")
        return {
            "status": "unknown", "found": None,
            "evidence": f"page title {title!r}; portal presented a bot-check ({phrase}); snippet: {snippet[:200]}",
            "method": adapter["method"],
            "reason": f"portal presented a bot-check/captcha ({phrase}) — human check required",
            "manual_url": manual_url,
        }
    if found is True:
        exact = _normalise_name(top or "") == _normalise_name(name)
        return {
            "status": "live", "found": True, "exact": exact,
            "evidence": f"page title {title!r}; top result: {top!r}",
            "method": adapter["method"], "reason": "",
            "manual_url": manual_url,
        }
    if found is False:
        return {
            "status": "live", "found": False, "exact": False,
            "evidence": f"page title {title!r}; portal reported no matching entities; snippet: {snippet[:200]}",
            "method": adapter["method"], "reason": "",
            "manual_url": manual_url,
        }
    return {
        "status": "unknown", "found": None,
        "evidence": f"page title {title!r}; snippet: {snippet[:200]}",
        "method": adapter["method"],
        "reason": "unexpected page shape after submit — could not tell found from not-found",
        "manual_url": manual_url,
    }


def check_state_live(name: str, state_code: str, timeout: int = 60) -> dict:
    """Live-check one name in one state via Playwright.

    Returns {"status": "live"|"unknown", "found": bool|None,
    "exact": bool, "evidence": ..., "method": ..., "reason": ...,
    "manual_url": ...}. Unknown is always honest: the reason says what
    actually happened and ``manual_url`` points at the portal.
    """
    code = (state_code or "").strip().upper()
    adapter = ADAPTERS.get(code)
    manual_url = adapter["url"] if adapter else _manual_url(code)
    if not adapter:
        return {
            "status": "unknown", "found": None, "exact": False,
            "evidence": None, "method": "no live adapter for this state",
            "reason": f"no live adapter for {code} — manual check only",
            "manual_url": manual_url,
        }
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {
            "status": "unknown", "found": None, "exact": False,
            "evidence": None, "method": adapter["method"],
            "reason": "Playwright is not installed — run `pip install playwright`",
            "manual_url": manual_url,
        }
    timeout_ms = max(10, timeout) * 1000
    last_error: dict | None = None
    try:
        launch_kwargs, ignore_https = _launch_kwargs()
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True, **launch_kwargs)
            try:
                ctx = browser.new_context(ignore_https_errors=ignore_https)
                page = ctx.new_page()
                try:
                    # One retry for transient navigation failures only.
                    result = _search_once(page, name, code, timeout_ms)
                    if result["status"] == "unknown" and result["reason"].startswith("navigation failed"):
                        result = _search_once(page, name, code, timeout_ms)
                    return result
                finally:
                    page.close()
                    ctx.close()
            finally:
                browser.close()
    except Exception as e:  # noqa: BLE001 — any browser failure is "unknown"
        last_error = {
            "status": "unknown", "found": None, "exact": False,
            "evidence": None, "method": adapter["method"],
            "reason": f"browser error: {str(e).splitlines()[0][:200] if str(e) else 'unknown error'}",
            "manual_url": manual_url,
        }
    return last_error or {
        "status": "unknown", "found": None, "exact": False,
        "evidence": None, "method": adapter["method"],
        "reason": "browser error: unknown error", "manual_url": manual_url,
    }


def check_state_live_batch(names: list[str], state_code: str, timeout: int = 60) -> dict[str, dict]:
    """Live-check many names in one state, reusing a single browser.

    Returns {name: outcome dict}. If the portal keeps returning
    inconclusive (unknown) results, the sweep stops after 3 consecutive
    unknowns and the remaining names are marked unknown with that
    reason, instead of hammering an unusable portal once per name.
    Any decisive result (found / not-found) resets the counter, so a
    working portal is never cut short.
    """
    code = (state_code or "").strip().upper()
    adapter = ADAPTERS.get(code)
    if not adapter:
        return {
            n: {
                "status": "unknown", "found": None, "exact": False,
                "evidence": None, "method": "no live adapter for this state",
                "reason": f"no live adapter for {code} — manual check only",
                "manual_url": _manual_url(code),
            }
            for n in names
        }
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {
            n: {
                "status": "unknown", "found": None, "exact": False,
                "evidence": None, "method": adapter["method"],
                "reason": "Playwright is not installed — run `pip install playwright`",
                "manual_url": adapter["url"],
            }
            for n in names
        }
    timeout_ms = max(10, timeout) * 1000
    out: dict[str, dict] = {}
    try:
        launch_kwargs, ignore_https = _launch_kwargs()
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True, **launch_kwargs)
            try:
                ctx = browser.new_context(ignore_https_errors=ignore_https)
                page = ctx.new_page()
                try:
                    consecutive_unknown = 0
                    for name in names:
                        result = _search_once(page, name, code, timeout_ms)
                        out[name] = result
                        if result["status"] == "unknown":
                            consecutive_unknown += 1
                            if consecutive_unknown >= 3:
                                last_reason = (result.get("reason") or "inconclusive")[:200]
                                stopped = {
                                    "status": "unknown", "found": None, "exact": False,
                                    "evidence": None, "method": adapter["method"],
                                    "reason": "sweep stopped: portal returned inconclusive "
                                              f"(unknown) results on 3 consecutive searches (last: {last_reason}) "
                                              "— human check required",
                                    "manual_url": adapter["url"],
                                }
                                for remaining in names[names.index(name) + 1:]:
                                    out[remaining] = dict(stopped)
                                break
                        else:
                            consecutive_unknown = 0
                finally:
                    page.close()
                    ctx.close()
            finally:
                browser.close()
    except Exception as e:  # noqa: BLE001 — browser failure marks the rest unknown
        reason = f"browser error: {str(e).splitlines()[0][:200] if str(e) else 'unknown error'}"
        for n in names:
            out.setdefault(n, {
                "status": "unknown", "found": None, "exact": False,
                "evidence": None, "method": adapter["method"],
                "reason": reason, "manual_url": adapter["url"],
            })
    return out

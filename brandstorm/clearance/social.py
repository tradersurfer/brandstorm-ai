"""Tier 4 — Social handle audit: username AND display name.

Verified live 2026-11-12 from this VM (two taken/free handle pairs each):

USERNAME (handle) checks — per candidate, three variants:
  @<compact>, @wear<compact>, @<compact>co
  (the spec's @name / @wearname / @name.co formats; the ".co" display
  form maps to the compact+"co" username because platforms do not
  allow dots in usernames).

  LIVE (real server-side signal):
  - X (x.com/{handle}): 404 = likely free, 200 = taken.
  - YouTube (youtube.com/@{handle}): 404 = likely free, 200 = taken.
  - Facebook (facebook.com/{handle}): status is 200 either way — the
    signal is the FINAL URL. Taken stays on the profile/page URL;
    free redirects to facebook.com/login/?next=... Verified on
    nike + cocacola (taken) vs two gibberish handles (free).
  - LinkedIn company (linkedin.com/company/{handle}): 200 = that slug
    is taken, 404 = that slug is likely free. Verified on nike (200)
    vs two gibberish slugs (404). Note: 404 means the SLUG is free,
    not that the company does not exist (coca-cola 404s because the
    real slug is the-coca-cola-company).

  UNKNOWN (no server-side signal — reported unknown, never guessed):
  - Instagram: 200 for taken AND free handles (login wall).
  - TikTok: 200 for taken AND free handles; body markers unreliable.
  - LinkedIn profile (linkedin.com/in/{handle}): HTTP 999 for taken
    AND free handles alike.

DISPLAY NAME checks — the spaced name as it would appear (e.g.
"Desert Ridge"): UNKNOWN on every platform, with the reason.
  - X search redirects to the login/onboarding flow for any query.
  - YouTube search returns 200 but echoes the query in the page with
    no existence signal (a gibberish query returns a full results
    page that still contains the query string).
  - Instagram / TikTok / Facebook / LinkedIn display-name search
    needs a logged-in session or an official search API.
  Display-name checks NEVER change a badge in either direction.
"""

from __future__ import annotations

from . import http_get, http_get_final

# platform -> URL template for a username check
_LIVE_STATUS_PLATFORMS = {
    "X": "https://x.com/{handle}",
    "YouTube": "https://www.youtube.com/@{handle}",
    "LinkedIn (company)": "https://www.linkedin.com/company/{handle}",
}

_UNKNOWN_PLATFORMS = {
    "Instagram": "Login-walled: returns HTTP 200 for taken and free handles alike; no server-side signal.",
    "TikTok": "Returns HTTP 200 for taken and free handles alike; body markers unreliable. No server-side signal.",
    "LinkedIn (profile)": "Returns HTTP 999 for taken and free handles alike; no server-side signal.",
}

_DISPLAY_NAME_REASONS = {
    "X": "X search redirects to the login/onboarding flow for any query — no server-side signal.",
    "YouTube": "YouTube search returns a results page that echoes the query with no existence signal.",
    "Instagram": "Display-name search needs a logged-in session or the official API.",
    "TikTok": "Display-name search needs a logged-in session or the official API.",
    "Facebook": "Display-name search needs a logged-in session or the official API.",
    "LinkedIn (company)": "Display-name search needs a logged-in session or the official API.",
    "LinkedIn (profile)": "Display-name search needs a logged-in session or the official API.",
}

# Platforms whose "unknown" result blocks a green badge: only platforms
# with a real signal, when that signal failed (rate limit, block, error).
# Unknown-only platforms and display-name checks never block green.
LIVE_PLATFORMS = ["X", "YouTube", "Facebook", "LinkedIn (company)"]


def handle_variants(compact_name: str) -> list[str]:
    """The three username variants checked per candidate."""
    return [compact_name, f"wear{compact_name}", f"{compact_name}co"]


def _check_status_platform(url: str) -> str:
    status, _body, err = http_get(url, timeout=10.0)
    if status == 404:
        return "free"
    if status == 200:
        return "taken"
    return "unknown"  # 429 / 403 / 999 / timeout / transport error


def _check_facebook(handle: str) -> str:
    """Facebook's signal is the final URL, not the status (200 either way)."""
    status, _body, final_url, err = http_get_final(
        f"https://www.facebook.com/{handle}", timeout=10.0
    )
    if final_url is None:
        return "unknown"
    if "/login/" in final_url:
        return "free"  # free handle -> redirected to login with ?next=
    if status == 200:
        return "taken"  # stayed on the profile/page URL
    return "unknown"


def check_display_name(display_name: str) -> dict:
    """Display-name availability per platform — unknown everywhere in v0.2.

    Pure function (no network): every platform's display-name search is
    login/JS-gated or echoes the query without an existence signal, as
    verified 2026-11-12. Returns {platform: {"status": "unknown",
    "reason": ...}} so the dashboard can show WHY, and scoring can
    ignore it explicitly.
    """
    return {
        platform: {"status": "unknown", "reason": reason}
        for platform, reason in _DISPLAY_NAME_REASONS.items()
    }


def check_social(compact_name: str, display_name: str | None = None) -> dict:
    handles = handle_variants(compact_name)
    platforms: dict[str, dict[str, str]] = {}
    for platform, template in _LIVE_STATUS_PLATFORMS.items():
        platforms[platform] = {
            handle: _check_status_platform(template.format(handle=handle)) for handle in handles
        }
    platforms["Facebook"] = {handle: _check_facebook(handle) for handle in handles}
    for platform in _UNKNOWN_PLATFORMS:
        platforms[platform] = {handle: "unknown" for handle in handles}
    return {
        "tier": 4,
        "name": "Social Handle Audit",
        "live": True,
        "method": (
            "Username: X + YouTube + LinkedIn company via HTTP status "
            "(404 = likely free, 200 = taken); Facebook via final URL "
            "(login redirect = likely free, profile URL = taken). "
            "Instagram + TikTok + LinkedIn profile return no signal — unknown, never guessed. "
            "Display name: unknown on all platforms (search is login/JS-gated)."
        ),
        "handles": handles,
        "live_platforms": LIVE_PLATFORMS,
        "platforms": platforms,
        "display_name": {
            "name": display_name or compact_name,
            "platforms": check_display_name(display_name or compact_name),
        },
        "unknown_reasons": _UNKNOWN_PLATFORMS,
    }

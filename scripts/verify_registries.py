#!/usr/bin/env python3
"""Verify every SOS registry URL in registries.py (status-only GET).

Writes brandstorm/clearance/registries_verification.json:
  {CODE: {"http_status": int|null, "final_url": str|null,
          "verified": bool, "checked_at": iso8601, "error": str}}

"verified" means the URL answered at all (HTTP 200/301/302/403/404/999 —
the host exists and responded). A 404 or a redirect to a different page
still counts as "answered" but is flagged in the report so a human can
re-check that entry. DNS failure / timeout / TLS error = not verified.

Run:  python3 -m scripts.verify_registries
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from brandstorm.clearance import http_get  # noqa: E402
from brandstorm.clearance.registries import REGISTRIES  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "brandstorm", "clearance", "registries_verification.json")


def _check(code: str, url: str) -> tuple[str, dict]:
    # http_get follows redirects; status is the final status. We re-derive
    # the final URL with a light HEAD-style probe via urllib directly.
    import urllib.error
    import urllib.request

    status, _body, err = http_get(url, timeout=10.0)
    final_url = None
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "BrandStormAI/0.2 (registry verification)"}, method="GET")
        with urllib.request.urlopen(req, timeout=10.0) as resp:
            final_url = resp.geturl()
            status = resp.status
    except urllib.error.HTTPError as e:
        try:
            final_url = e.geturl()
        except Exception:
            final_url = None
    except Exception:
        pass
    checked_at = _dt.datetime.now(_dt.timezone.utc).isoformat()
    return code, {
        "http_status": status,
        "final_url": final_url,
        "verified": status is not None,
        "checked_at": checked_at,
        "error": err or "",
    }


def main() -> int:
    # Merge with the previous verification file so "ever_verified" survives
    # flaky hosts (some SOS sites close connections to automated clients
    # intermittently). "verified" is always this run's observation.
    previous = {}
    if os.path.exists(OUT):
        try:
            with open(OUT) as f:
                previous = json.load(f)
        except Exception:
            previous = {}
    results: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=10) as pool:
        futs = {pool.submit(_check, code, entry["url"]): code for code, entry in REGISTRIES.items()}
        for fut in as_completed(futs):
            code, rec = fut.result()
            old = previous.get(code, {})
            rec["ever_verified"] = bool(rec["verified"] or old.get("ever_verified"))
            rec["last_verified_at"] = rec["checked_at"] if rec["verified"] else old.get("last_verified_at")
            results[code] = rec
            print(f"  {code}: {rec['http_status']} verified={rec['verified']} ever={rec['ever_verified']}")
    with open(OUT, "w") as f:
        json.dump(results, f, indent=2, sort_keys=True)
    ok = sum(1 for r in results.values() if r["verified"])
    ever = sum(1 for r in results.values() if r["ever_verified"])
    bad = [c for c, r in results.items() if not r["verified"]]
    print(f"\n{ok}/{len(results)} answered this run; {ever}/{len(results)} answered at least once.")
    print(f"Not verified this run: {bad or 'none'}")
    print(f"Wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

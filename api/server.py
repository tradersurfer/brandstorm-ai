#!/usr/bin/env python3
"""BrandStorm AI local server (stdlib only).

Serves the dashboard + results API:
    python3 api/server.py [--port 8000]

Routes:
    /                      -> frontend/index.html
    /data/results.json     -> latest run results
    /api/results           -> same as above (JSON)
    /api/run               -> POST {"brief": "briefs/sample-arizona-coffee.json", "limit": 50}
                              or {"brief": {<inline brief dict>}, ...}
                              runs the pipeline and returns the summary.
                              Optional top-level "states" / "geographic_scope"
                              override the brief's geography.
"""

from __future__ import annotations

import json
import os
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = os.path.join(ROOT, "data", "results.json")
DEFAULT_BRIEF = "briefs/sample-arizona-coffee.json"


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)

    def log_message(self, *args):  # keep the console clean
        pass

    def _send_json(self, payload, status=200):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ("/", ""):
            self.path = "/frontend/index.html"
            return super().do_GET()
        if path == "/api/results":
            if not os.path.exists(RESULTS):
                return self._send_json({"error": "no run yet — run: python3 -m scripts.run_brief briefs/sample-arizona-coffee.json"}, 404)
            with open(RESULTS) as f:
                return self._send_json(json.load(f))
        return super().do_GET()

    def do_POST(self):
        path = urlparse(self.path).path
        if path != "/api/run":
            return self._send_json({"error": "unknown route"}, 404)
        length = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except Exception:
            return self._send_json({"error": "invalid JSON"}, 400)
        from brandstorm import generator, pipeline
        from brandstorm.keys import annotate_tier_notes, keys_status
        from brandstorm.regions import resolve_states
        import datetime as _dt

        started = _dt.datetime.now(_dt.timezone.utc)
        brief_arg = body.get("brief", DEFAULT_BRIEF)
        if isinstance(brief_arg, dict):
            brief = brief_arg
        else:
            brief_path = os.path.join(ROOT, brief_arg)
            if not os.path.exists(brief_path):
                return self._send_json({"error": f"brief not found: {brief_arg}"}, 400)
            with open(brief_path) as f:
                brief = json.load(f)
        # Top-level overrides (from the dashboard form) win over the brief.
        if body.get("geographic_scope") is not None:
            brief["geographic_scope"] = body["geographic_scope"]
        if body.get("states") is not None:
            brief["states"] = body["states"]
        brief.setdefault("nice_class", "025")
        brief.setdefault("candidate_batch_size", 50)

        states, source, matched, dropped = resolve_states(
            brief.get("geographic_scope"), brief.get("states"))
        names = generator.generate(brief, count=body.get("limit") or brief.get("candidate_batch_size", 100))
        results = pipeline.run(names, nice_class=str(brief.get("nice_class", "025")),
                               tlds=brief.get("tlds"),
                               states=brief.get("states"),
                               geographic_scope=brief.get("geographic_scope"))
        summary = pipeline.summarize(results)
        ended = _dt.datetime.now(_dt.timezone.utc)
        payload = {
            "brief": brief,
            "generated_at": started.isoformat(),
            "finished_at": ended.isoformat(),
            "duration_seconds": round((ended - started).total_seconds(), 1),
            "summary": summary,
            # Tier notes are adjusted AFTER pipeline.tier_notes() returns
            # (pipeline.py is not edited): the method label is honest
            # about keyless vs keyed. keys_status() holds labels only,
            # never a key value.
            "tier_notes": annotate_tier_notes(pipeline.tier_notes(states)),
            "keys_status": keys_status(),
            "geography": {"states": states, "source": source, "matched": matched, "dropped": dropped},
            "results": results,
        }
        os.makedirs(os.path.dirname(RESULTS), exist_ok=True)
        with open(RESULTS, "w") as f:
            json.dump(payload, f, indent=2)
        return self._send_json({"summary": summary, "geography": payload["geography"],
                                "results_file": "data/results.json"})


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"BrandStorm AI dashboard: http://127.0.0.1:{args.port}/")
    print("Run a brief first if no results yet: python3 -m scripts.run_brief briefs/sample-arizona-coffee.json")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")

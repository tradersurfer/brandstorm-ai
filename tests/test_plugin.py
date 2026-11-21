"""Plugin tests for BrandStorm AI v0.3 (stdlib unittest, NO network).

Covers: plugin.yaml parses with the required fields, the four tool
functions validate a brief without network, brandstorm_run with a
mocked pipeline.run, brandstorm_results against a fixture file,
brandstorm_state_links, register(ctx) wiring, and the demo flow with
mocked network. Live network is never touched here — the live demo
run happens on the laptop (see docs/LAPTOP_TEST.md).
"""

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import plugin as plugin_pkg  # noqa: E402
from plugin import tools  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

BRIEF = {
    "industry": "Specialty Tea House",
    "geographic_scope": "Portland, Oregon / US National",
    "states": ["OR"],
    "brand_aesthetic": ["Rustic", "Artisan"],
    "nice_class": "030",
    "candidate_batch_size": 5,
    "tlds": ["com", "co"],
    "must_include_exact_variations": ["Cascade Leaf", "Fern Leaf"],
}

FAKE_RESULTS = [
    {"name": "Cascade Ridge", "compact": "cascaderidge", "badge": "clean",
     "reason": "clear", "domain": {"tlds": {"com": "available"}},
     "uspto": {"status": "clear"}, "state": {"status": "manual"},
     "social": {"platforms": {}}},
    {"name": "Fern Hollow", "compact": "fernhollow", "badge": "partial",
     "reason": ".com taken", "domain": {"tlds": {"com": "taken"}},
     "uspto": {"status": "clear"}, "state": {"status": "manual"},
     "social": {"platforms": {}}},
    {"name": "Cascade Leaf", "compact": "cascadeleaf", "badge": "conflict",
     "reason": "live mark", "domain": {"tlds": {"com": "available"}},
     "uspto": {"status": "conflict"}, "state": {"status": "manual"},
     "social": {"platforms": {}}},
]


class TestPluginYaml(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(ROOT, "plugin.yaml")) as f:
            self.manifest = yaml.safe_load(f)

    def test_required_fields(self):
        m = self.manifest
        self.assertEqual(m["name"], "brandstorm")
        self.assertEqual(m["version"], "0.3.0")
        self.assertEqual(m["author"], "tradersurfer93")
        self.assertEqual(m["license"], "MIT")
        self.assertIn("description", m)
        self.assertTrue(m["description"])
        self.assertEqual(m["requires_hermes"], ">=0.21.6")
        self.assertEqual(
            m["provides_tools"],
            ["brandstorm_brief", "brandstorm_run", "brandstorm_results", "brandstorm_state_links"],
        )

    def test_config_schema_all_optional_nothing_prefilled(self):
        schema = self.manifest["config_schema"]
        for key in ("industry", "region", "states", "class"):
            self.assertIn(key, schema)
            self.assertEqual(schema[key]["type"], "str")
            self.assertEqual(schema[key]["default"], "")
        for key in ("godaddy_key", "godaddy_secret", "uspto_key", "llm_key"):
            self.assertIn(key, schema)
            self.assertEqual(schema[key]["type"], "secret")
            self.assertIn("env", schema[key])
            # Secrets carry no pre-filled value.
            self.assertNotIn("default", schema[key])
            self.assertFalse(schema[key].get("default", ""))

    def test_no_personal_data_in_manifest(self):
        text = open(os.path.join(ROOT, "plugin.yaml")).read().lower()
        for banned in ("adrian", "jecigroup", "moneyvibes", "facebook.com", "instagram.com"):
            self.assertNotIn(banned, text)


class TestBrief(unittest.TestCase):
    def test_valid_brief_no_network(self):
        out = tools.brandstorm_brief(BRIEF)
        self.assertEqual(out["status"], "success")
        brief = out["brief"]
        self.assertEqual(brief["industry"], "Specialty Tea House")
        self.assertEqual(brief["nice_class"], "030")
        self.assertEqual(brief["candidate_batch_size"], 5)
        self.assertEqual(out["geography"]["states"], ["OR"])
        self.assertEqual(out["geography"]["source"], "explicit")

    def test_missing_industry_is_error(self):
        out = tools.brandstorm_brief({"geographic_scope": "Portland, Oregon"})
        self.assertEqual(out["status"], "error")
        self.assertIn("industry", out["error"])

    def test_unknown_state_dropped_and_reported(self):
        out = tools.brandstorm_brief({**BRIEF, "states": ["OR", "XX"]})
        self.assertEqual(out["status"], "success")
        self.assertEqual(out["brief"]["states"], ["OR"])
        self.assertEqual(out["geography"]["dropped"], ["XX"])

    def test_batch_size_bounds(self):
        self.assertEqual(tools.brandstorm_brief({**BRIEF, "candidate_batch_size": 0})["status"], "error")
        self.assertEqual(tools.brandstorm_brief({**BRIEF, "candidate_batch_size": 101})["status"], "error")

    def test_region_alias_resolves_states(self):
        out = tools.brandstorm_brief({"industry": "Tea", "geographic_scope": "Pacific Northwest"})
        self.assertEqual(out["geography"]["states"], ["WA", "OR"])
        self.assertEqual(out["geography"]["source"], "alias")

    def test_no_states_means_not_requested(self):
        out = tools.brandstorm_brief({"industry": "Tea"})
        self.assertEqual(out["geography"]["states"], [])
        self.assertEqual(out["geography"]["source"], "none")


class TestRunMocked(unittest.TestCase):
    def test_brief_round_trip_keeps_anchors(self):
        """A brief built by brandstorm_brief, fed back into a run,
        must keep its anchor words (nested direct_anchor_rules shape)."""
        built = tools.brandstorm_brief(BRIEF)["brief"]
        self.assertEqual(
            built["direct_anchor_rules"]["must_include_exact_variations"],
            ["Cascade Leaf", "Fern Leaf"])
        rebuilt, _, err = tools._build_brief(built)
        self.assertIsNone(err)
        self.assertEqual(
            rebuilt["direct_anchor_rules"]["must_include_exact_variations"],
            ["Cascade Leaf", "Fern Leaf"])

    def test_run_with_mocked_pipeline(self):
        fake = [dict(r) for r in FAKE_RESULTS]
        with mock.patch("brandstorm.pipeline.run", return_value=fake) as run_mock:
            with tempfile.TemporaryDirectory() as tmp:
                out_path = os.path.join(tmp, "results.json")
                out = tools.brandstorm_run(
                    {"brief": BRIEF, "write_results": True, "out": out_path})
                # The run payload was written where asked (read it before
                # the temp dir is cleaned up).
                with open(out_path) as f:
                    payload = json.load(f)
        self.assertEqual(out["status"], "success")
        run_mock.assert_called_once()
        self.assertEqual(out["summary"]["total"], 3)
        self.assertEqual(out["summary"]["clean"], 1)
        self.assertEqual(out["summary"]["partial"], 1)
        self.assertEqual(out["summary"]["conflict"], 1)
        self.assertEqual(out["shortlist"], ["Cascade Ridge"])
        self.assertEqual(len(out["results"]), 3)
        # Generated names honour the brief's anchors.
        for name in out["names"]:
            self.assertTrue(
                any(tok in name.lower() for tok in ("cascade", "fern", "leaf")),
                f"{name!r} carries no anchor token")
        self.assertEqual(payload["summary"]["total"], 3)
        self.assertEqual(payload["brief"]["industry"], "Specialty Tea House")

    def test_run_accepts_flat_fields(self):
        with mock.patch("brandstorm.pipeline.run", return_value=[]):
            out = tools.brandstorm_run({**BRIEF, "write_results": False})
        self.assertEqual(out["status"], "success")
        self.assertEqual(out["summary"]["total"], 0)


class TestResults(unittest.TestCase):
    def _write_fixture(self, tmp):
        path = os.path.join(tmp, "results.json")
        payload = {
            "brief": BRIEF,
            "generated_at": "2026-11-13T00:00:00+00:00",
            "summary": {"total": 3, "clean": 1, "partial": 1, "conflict": 1},
            "tier_notes": {"domain": "LIVE", "uspto": "LIVE", "state": "STUBBED", "social": "PARTIAL"},
            "geography": {"states": ["OR"], "source": "explicit", "matched": ["OR"], "dropped": []},
            "results": FAKE_RESULTS,
        }
        with open(path, "w") as f:
            json.dump(payload, f)
        return path

    def test_reads_shortlist_and_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_fixture(tmp)
            out = tools.brandstorm_results({"results_path": path})
        self.assertEqual(out["status"], "success")
        self.assertEqual(out["shortlist"], ["Cascade Ridge"])
        self.assertEqual(out["summary"]["total"], 3)
        self.assertEqual(len(out["results"]), 3)
        clean = out["results"][0]
        self.assertEqual(clean["domain"]["tlds"]["com"], "available")
        self.assertEqual(clean["uspto"]["status"], "clear")
        self.assertEqual(clean["state"]["status"], "manual")

    def test_badge_filter(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_fixture(tmp)
            out = tools.brandstorm_results({"results_path": path, "badge": "clean"})
        self.assertEqual(len(out["results"]), 1)
        self.assertEqual(out["results"][0]["name"], "Cascade Ridge")
        # Shortlist is badge-independent: all clean names from the file.
        self.assertEqual(out["shortlist"], ["Cascade Ridge"])

    def test_missing_file_is_error_not_crash(self):
        out = tools.brandstorm_results({"results_path": "/nonexistent/results.json"})
        self.assertEqual(out["status"], "error")
        self.assertIn("brandstorm_run", out["error"])


class TestStateLinks(unittest.TestCase):
    def test_oregon_link(self):
        out = tools.brandstorm_state_links({"states": ["OR"]})
        self.assertEqual(out["status"], "manual")
        entry = out["states"]["OR"]
        self.assertEqual(entry["name"], "Oregon")
        self.assertTrue(entry["url"].startswith("http"))
        self.assertIn("portal", entry)

    def test_no_states_not_requested(self):
        out = tools.brandstorm_state_links({})
        self.assertEqual(out["status"], "not_requested")
        self.assertEqual(out["states"], {})
        self.assertIn("guidance", out)

    def test_region_alias(self):
        out = tools.brandstorm_state_links({"geographic_scope": "Pacific Northwest"})
        self.assertEqual(sorted(out["states"]), ["OR", "WA"])


class TestRegister(unittest.TestCase):
    def test_register_wires_four_tools(self):
        registered = {}

        class FakeCtx:
            def register_tool(self, name, toolset, schema, handler):
                registered[name] = {"toolset": toolset, "schema": schema, "handler": handler}

            def register_command(self, name, fn, description=None):
                registered.setdefault("_commands", {})[name] = fn

        plugin_pkg.register(FakeCtx())
        for name in ("brandstorm_brief", "brandstorm_run", "brandstorm_results", "brandstorm_state_links"):
            self.assertIn(name, registered)
            self.assertEqual(registered[name]["toolset"], "brandstorm")
            self.assertTrue(callable(registered[name]["handler"]))
            self.assertEqual(registered[name]["schema"]["name"], name)


class TestDemoFlowMocked(unittest.TestCase):
    def test_demo_runs_with_zero_keys_mocked_network(self):
        """Demo flow end to end with the network layer mocked (no keys,
        no live calls). The live run happens on the laptop."""
        import runpy

        fake = [dict(r) for r in FAKE_RESULTS[:2]]
        buf = io.StringIO()
        with mock.patch("brandstorm.pipeline.run", return_value=fake):
            with contextlib.redirect_stdout(buf):
                try:
                    runpy.run_path(
                        os.path.join(ROOT, "demo", "demo_flow.py"),
                        run_name="__main__",
                    )
                except SystemExit as e:
                    self.assertEqual(e.code, 0)
        output = buf.getvalue()
        self.assertIn("Cascade Leaf Tea", output)
        self.assertIn("BRIEF", output)
        self.assertIn("RUN", output)
        self.assertIn("STATE LINKS", output)
        self.assertIn("No keys used", output)


if __name__ == "__main__":
    unittest.main()

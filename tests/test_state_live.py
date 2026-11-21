"""Unit tests for BrandStorm AI v0.3 Tier 3 live checks (no network).

Every live-adapter call is mocked: no browser is launched, no portal
is contacted. The real browser behaviour is covered by
scripts/smoke_state.py (manual live run).
"""

import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from brandstorm import pipeline, scoring
from brandstorm.clearance import registries, state
from brandstorm.clearance import state_live


def _live_outcome(found=True, exact=True, status="live", reason=""):
    return {
        "status": status, "found": found, "exact": exact,
        "evidence": "page title 'X'; top result: 'Walmart'",
        "method": "playwright: test",
        "reason": reason,
        "manual_url": "https://example.invalid/portal",
    }


def _clean_base():
    return {
        "domain": {"tlds": {"com": "available"}},
        "uspto": {"status": "ok", "matches": [], "nice_class": "030"},
        "social": {
            "live_platforms": ["X", "YouTube", "Facebook", "LinkedIn (company)"],
            "platforms": {
                "X": {"walmart": "free"},
                "YouTube": {"walmart": "free"},
                "Facebook": {"walmart": "free"},
                "LinkedIn (company)": {"walmart": "free"},
            },
        },
    }


class TestAdapters(unittest.TestCase):
    def test_eight_adapters(self):
        self.assertEqual(state_live.adapter_codes(),
                         ["AZ", "CA", "DC", "FL", "MD", "NY", "TX", "VA"])

    def test_adapter_shape(self):
        for code, ad in state_live.ADAPTERS.items():
            for key in ("url", "fill", "submit_text", "pre", "method"):
                self.assertIn(key, ad, code)
            self.assertTrue(ad["url"].startswith("https://"), code)
            self.assertTrue(ad["method"], code)

    def test_adapter_urls_match_registries(self):
        # Every adapter URL is the registry portal URL, except AZ and DC,
        # whose adapters point at the landing page the portal home
        # redirects to (same host, deeper path — observed live).
        for code, ad in state_live.ADAPTERS.items():
            reg = registries.get_registry(code)
            self.assertIsNotNone(reg, code)
            if code == "AZ":
                # ecorp.azcc.gov redirects to arizonabusinesscenter.azcc.gov
                self.assertTrue(ad["url"].endswith("azcc.gov/businesssearch"), code)
            elif code == "DC":
                from urllib.parse import urlparse
                self.assertEqual(urlparse(ad["url"]).netloc,
                                 urlparse(reg["url"]).netloc, code)
            else:
                self.assertEqual(ad["url"], reg["url"], code)

    def test_has_adapter(self):
        self.assertTrue(state_live.has_adapter("AZ"))
        self.assertTrue(state_live.has_adapter("az"))  # case-insensitive
        self.assertFalse(state_live.has_adapter("WY"))
        self.assertFalse(state_live.has_adapter("XX"))

    def test_no_adapter_returns_unknown_with_manual_link(self):
        out = state_live.check_state_live("Walmart", "WY")
        self.assertEqual(out["status"], "unknown")
        self.assertIsNone(out["found"])
        self.assertTrue(out["reason"])
        self.assertTrue(out["manual_url"].startswith("https://"))


class TestClassifyBody(unittest.TestCase):
    def test_captcha_is_blocked_not_found(self):
        found, _, blocked = state_live._classify_body(
            "User validation required to continue | Enter the 6 characters shown",
            "Walmart")
        self.assertIsNone(found)
        self.assertTrue(blocked)

    def test_security_block_is_blocked(self):
        found, _, blocked = state_live._classify_body(
            "This request was blocked by our security service", "Walmart")
        self.assertIsNone(found)
        self.assertTrue(blocked)

    def test_no_records_means_not_found(self):
        found, top, blocked = state_live._classify_body(
            "Search results\nNo records found for your search", "Zqxjkvwmpl")
        self.assertIs(found, False)
        self.assertIsNone(top)
        self.assertFalse(blocked)

    def test_returned_name_means_found(self):
        found, top, blocked = state_live._classify_body(
            "Search results\nWALMART STORES, INC.\nActive", "Walmart")
        self.assertIs(found, True)
        self.assertIn("WALMART", top)
        self.assertFalse(blocked)

    def test_unrelated_page_is_unclassifiable(self):
        found, _, blocked = state_live._classify_body(
            "Welcome to our homepage\nPlease try again later", "Walmart")
        self.assertIsNone(found)
        self.assertFalse(blocked)

    def test_normalise_strips_suffix_and_case(self):
        self.assertEqual(state_live._normalise_name("Walmart Stores, Inc."), "walmart stores")
        self.assertEqual(state_live._normalise_name("WALMART LLC"), "walmart")
        self.assertEqual(state_live._normalise_name("Desert Roast Coffee Co."), "desert roast coffee")


class TestStateTierLive(unittest.TestCase):
    def test_live_found_exact_is_live(self):
        with mock.patch.object(state_live, "check_state_live",
                               return_value=_live_outcome(found=True, exact=True)):
            r = state.check_state("Walmart", states=["AZ"], live=True)
        self.assertEqual(r["status"], "live")
        self.assertTrue(r["live"])
        entry = r["states"]["AZ"]
        self.assertEqual(entry["check"], "live")
        self.assertIs(entry["found"], True)
        self.assertIs(entry["exact"], True)
        self.assertTrue(entry["url"].startswith("https://"))  # v0.2 shape kept

    def test_live_not_found_is_still_live(self):
        with mock.patch.object(state_live, "check_state_live",
                               return_value=_live_outcome(found=False, exact=False)):
            r = state.check_state("Zqxjkvwmpl", states=["AZ"], live=True)
        self.assertEqual(r["status"], "live")
        self.assertIs(r["states"]["AZ"]["found"], False)

    def test_live_unknown_reports_reason_and_manual_link(self):
        with mock.patch.object(state_live, "check_state_live",
                               return_value=_live_outcome(found=None, exact=False,
                                                          status="unknown",
                                                          reason="portal presented a bot-check/captcha")):
            r = state.check_state("Walmart", states=["AZ"], live=True)
        self.assertEqual(r["status"], "unknown")
        self.assertFalse(r["live"])
        entry = r["states"]["AZ"]
        self.assertEqual(entry["check"], "unknown")
        self.assertIn("captcha", entry["reason"])
        self.assertTrue(entry["manual_url"].startswith("https://"))

    def test_no_adapter_stays_manual_even_when_live(self):
        r = state.check_state("Walmart", states=["WY"], live=True)
        self.assertEqual(r["status"], "manual")
        self.assertEqual(r["states"]["WY"]["check"], "manual")
        self.assertTrue(r["states"]["WY"]["url"].startswith("https://"))

    def test_mixed_live_and_manual(self):
        with mock.patch.object(state_live, "check_state_live",
                               return_value=_live_outcome(found=False, exact=False)):
            r = state.check_state("Walmart", states=["AZ", "WY"], live=True)
        self.assertEqual(r["status"], "mixed")
        self.assertEqual(r["states"]["AZ"]["check"], "live")
        self.assertEqual(r["states"]["WY"]["check"], "manual")

    def test_adapter_exception_is_unknown_with_reason(self):
        with mock.patch.object(state_live, "check_state_live",
                               side_effect=RuntimeError("browser exploded")):
            r = state.check_state("Walmart", states=["AZ"], live=True)
        self.assertEqual(r["status"], "unknown")
        self.assertIn("browser exploded", r["states"]["AZ"]["reason"])
        self.assertTrue(r["states"]["AZ"]["manual_url"].startswith("https://"))

    def test_default_is_still_manual_v02(self):
        # No live flag -> v0.2 behaviour, no browser touched.
        with mock.patch.object(state_live, "check_state_live",
                               side_effect=AssertionError("must not be called")):
            r = state.check_state("Walmart", states=["AZ"])
        self.assertEqual(r["status"], "manual")

    def test_batch_uses_one_sweep_per_adapter_state(self):
        with mock.patch.object(state_live, "check_state_live_batch",
                               return_value={"Walmart": _live_outcome(found=True, exact=True),
                                             "Zqxjkvwmpl": _live_outcome(found=False, exact=False)}) as m:
            out = state.check_state_batch(["Walmart", "Zqxjkvwmpl"], ["AZ", "WY"], live=True)
        m.assert_called_once()
        self.assertEqual(out["Walmart"]["status"], "mixed")  # live AZ + manual WY
        self.assertEqual(out["Zqxjkvwmpl"]["states"]["AZ"]["found"], False)
        self.assertEqual(out["Zqxjkvwmpl"]["states"]["WY"]["check"], "manual")


class TestBatchStopRule(unittest.TestCase):
    """The sweep must stop after 3 consecutive inconclusive (unknown)
    results of ANY kind — not just bot-checks. Regression test for the
    v0.3 BYND run, where DC/MD/VA returned 'no form found' /
    'unexpected page shape' on every name and the sweep ground through
    all 100 names x 3 states because only bot-check reasons counted.
    """

    def _run_batch(self, side_effect, names):
        import types
        fake_pw = mock.MagicMock()
        fake_pw.__enter__.return_value = fake_pw
        fake_pw.__exit__.return_value = False
        fake_module = types.SimpleNamespace(sync_playwright=lambda: fake_pw)
        with mock.patch.dict(sys.modules, {
                "playwright": types.SimpleNamespace(),
                "playwright.sync_api": fake_module}):
            with mock.patch.object(state_live, "_search_once",
                                   side_effect=side_effect) as search:
                out = state_live.check_state_live_batch(names, "DC")
        return out, search

    def _unknown(self, reason):
        return {"status": "unknown", "found": None, "exact": False,
                "evidence": None, "method": "playwright: test",
                "reason": reason, "manual_url": "https://example.invalid/"}

    def test_stops_after_three_consecutive_unknowns_any_reason(self):
        names = ["A", "B", "C", "D", "E"]
        out, search = self._run_batch(
            [self._unknown("no entity-name search form found")] * 3, names)
        self.assertEqual(search.call_count, 3)
        self.assertEqual(out["D"]["reason"].split(":")[0], "sweep stopped")
        self.assertEqual(out["E"]["reason"], out["D"]["reason"])
        self.assertEqual(out["D"]["status"], "unknown")

    def test_decisive_result_resets_the_counter(self):
        names = ["A", "B", "C", "D", "E", "F", "G"]
        side_effect = [
            self._unknown("no form found"),
            self._unknown("no form found"),
            _live_outcome(found=False, status="live"),  # decisive: not-found
            self._unknown("unexpected page shape"),
            self._unknown("unexpected page shape"),
            self._unknown("unexpected page shape"),
            self._unknown("unexpected page shape"),  # never reached
        ]
        out, search = self._run_batch(side_effect, names)
        self.assertEqual(search.call_count, 6)
        self.assertEqual(out["G"]["reason"].split(":")[0], "sweep stopped")
        self.assertEqual(out["C"]["status"], "live")

    def test_bot_check_unknowns_also_stop(self):
        names = ["A", "B", "C", "D"]
        out, search = self._run_batch(
            [self._unknown("portal presented a bot-check/captcha")] * 3, names)
        self.assertEqual(search.call_count, 3)
        self.assertIn("sweep stopped", out["D"]["reason"])


class TestScoringLiveState(unittest.TestCase):
    def _with_state(self, check, found, exact):
        r = _clean_base()
        r["state"] = {
            "status": "live" if check == "live" else check,
            "states": {"AZ": {"check": check, "found": found, "exact": exact}},
        }
        return r

    def test_live_exact_match_makes_partial(self):
        badge, reason = scoring.score(self._with_state("live", True, True))
        self.assertEqual(badge, "partial")
        self.assertIn("AZ", reason)

    def test_live_exact_match_does_not_downgrade_conflict(self):
        r = self._with_state("live", True, True)
        r["uspto"]["matches"] = [{"kind": "exact", "alive": True, "wordmark": "WALMART"}]
        badge, _ = scoring.score(r)
        self.assertEqual(badge, "conflict")

    def test_live_fuzzy_match_does_not_change_badge(self):
        # Found but not exact (portal fuzzy search) — the one rule is exact-only.
        badge, _ = scoring.score(self._with_state("live", True, False))
        self.assertEqual(badge, "clean")

    def test_live_not_found_does_not_change_badge(self):
        badge, _ = scoring.score(self._with_state("live", False, False))
        self.assertEqual(badge, "clean")

    def test_live_unknown_never_changes_badge(self):
        badge, _ = scoring.score(self._with_state("unknown", None, False))
        self.assertEqual(badge, "clean")

    def test_manual_never_changes_badge(self):
        badge, _ = scoring.score(self._with_state("manual", None, False))
        self.assertEqual(badge, "clean")


class TestTierNotesWording(unittest.TestCase):
    """Grok review fix: the dashboard tier note must not market Tier 3 as
    'LIVE' when every portal returns unknown in practice."""

    def test_state_note_says_attempted_not_live(self):
        note = pipeline.tier_notes(["AZ"])["state"]
        self.assertTrue(note.startswith("ATTEMPTED (Playwright)"), note)
        self.assertFalse(note.startswith("LIVE"), note)
        self.assertIn("unknown with the reason", note)

    def test_state_note_manual_when_disabled(self):
        note = pipeline.tier_notes(["AZ"], state_live_attempted=False)["state"]
        self.assertTrue(note.startswith("MANUAL"), note)

    def test_domain_note_carries_dns_caveat(self):
        note = pipeline.tier_notes(["AZ"])["domain"]
        self.assertIn("not a registrar guarantee", note)


class TestPipelineStateLive(unittest.TestCase):
    def _mock_tiers(self):
        return (
            mock.patch.object(pipeline._domain, "check_domain",
                              return_value={"tlds": {"com": "available"}}),
            mock.patch.object(pipeline._uspto, "check_uspto",
                              return_value={"status": "ok", "matches": [], "nice_class": "030"}),
            mock.patch.object(pipeline._social, "check_social",
                              return_value={
                                  "live_platforms": ["X", "YouTube"],
                                  "platforms": {"X": {"walmart": "free"},
                                                "YouTube": {"walmart": "free"}},
                                  "display_name": {"name": "Walmart", "platforms": {}},
                              }),
        )

    def test_pipeline_uses_live_batch_and_scores_exact_match(self):
        live_result = state.check_state("Walmart", states=["AZ"], live=False)
        live_result = dict(live_result)
        live_result["status"] = "live"
        live_result["live"] = True
        live_result["states"] = {"AZ": {"check": "live", "found": True, "exact": True,
                                        "url": "https://example.invalid/"}}
        mocks = self._mock_tiers()
        with mocks[0], mocks[1], mocks[2], \
                mock.patch.object(state, "check_state_batch",
                                  return_value={"Walmart": live_result}) as batch:
            results = pipeline.run(["Walmart"], states=["AZ"])
        batch.assert_called_once()
        self.assertEqual(results[0]["state"]["status"], "live")
        self.assertEqual(results[0]["badge"], "partial")  # live exact match

    def test_pipeline_env_flag_forces_manual_only(self):
        mocks = self._mock_tiers()
        with mocks[0], mocks[1], mocks[2], \
                mock.patch.object(state, "check_state_batch") as batch, \
                mock.patch.dict(os.environ, {"BRANDSTORM_STATE_LIVE": "0"}):
            results = pipeline.run(["Walmart"], states=["AZ"])
        batch.assert_not_called()
        self.assertEqual(results[0]["state"]["status"], "manual")
        self.assertEqual(results[0]["badge"], "clean")

    def test_pipeline_state_live_false_forces_manual_only(self):
        mocks = self._mock_tiers()
        with mocks[0], mocks[1], mocks[2], \
                mock.patch.object(state, "check_state_batch") as batch:
            results = pipeline.run(["Walmart"], states=["AZ"], state_live=False)
        batch.assert_not_called()
        self.assertEqual(results[0]["state"]["status"], "manual")


if __name__ == "__main__":
    unittest.main()

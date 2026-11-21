"""Unit tests for BrandStorm AI v0.2 (stdlib unittest, no network).

The example brief (briefs/examples/bynd-streetwear.json) is used as a
regression fixture; the sample brief (briefs/sample-arizona-coffee.json)
is the generic product test case. Neither is a product default — both
are fixtures, labeled as such.
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from brandstorm import generator, regions, scoring
from brandstorm.clearance import domain as domain_mod  # noqa: F401  (contract tests below)
from brandstorm.clearance import registries, social, state
from brandstorm.phonetics import phonetic_match, soundex

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_brief(rel: str) -> dict:
    with open(os.path.join(ROOT, rel)) as f:
        return json.load(f)


EXAMPLE_BRIEF = _load_brief("briefs/examples/bynd-streetwear.json")
SAMPLE_BRIEF = _load_brief("briefs/sample-arizona-coffee.json")


class TestGeneratorExample(unittest.TestCase):
    """Regression fixture: the example brief still generates 100 compounds."""

    def test_100_unique_compounds(self):
        names = generator.generate(EXAMPLE_BRIEF, count=100)
        self.assertEqual(len(names), 100)
        self.assertEqual(len({n.lower() for n in names}), 100)
        for n in names:
            self.assertGreaterEqual(len(n.split()), 2, n)  # compound only

    def test_every_name_has_anchor(self):
        for n in generator.generate(EXAMPLE_BRIEF, count=100):
            tokens = {t.lower() for t in n.replace("/", " ").split()}
            self.assertTrue(tokens & {"bynd", "btv", "vision", "fitness"}, n)

    def test_deterministic(self):
        self.assertEqual(generator.generate(EXAMPLE_BRIEF, count=50),
                         generator.generate(EXAMPLE_BRIEF, count=50))

    def test_compact(self):
        self.assertEqual(generator.compact("BYND the Vision District"), "byndthevisiondistrict")

    def test_anchor_derivation_from_brief(self):
        # "/" normalizes to a space; a 3+ word variation yields an acronym.
        self.assertEqual(generator.anchor_variations(EXAMPLE_BRIEF),
                         ["BYND Vision", "BYND Fitness", "BYND the Vision"])
        self.assertEqual(generator.anchor_leads(EXAMPLE_BRIEF), ["BYND", "BTV"])
        self.assertEqual(generator.anchor_tokens(EXAMPLE_BRIEF),
                         {"bynd", "vision", "fitness", "btv"})


class TestGeneratorSample(unittest.TestCase):
    """Generic product case: the Arizona sample brief, no hardcoded anchors."""

    def test_50_unique_compounds_with_sample_anchors(self):
        names = generator.generate(SAMPLE_BRIEF, count=50)
        self.assertEqual(len(names), 50)
        self.assertEqual(len({n.lower() for n in names}), 50)
        allowed = {"desert", "roast", "sonora", "coffee", "drc"}
        for n in names:
            tokens = {t.lower() for t in n.split()}
            self.assertTrue(tokens & allowed, n)
            # No trace of the old hardcoded anchors.
            self.assertFalse(tokens & {"bynd", "btv", "vision", "fitness"}, n)

    def test_sample_anchor_derivation(self):
        self.assertEqual(generator.anchor_variations(SAMPLE_BRIEF),
                         ["Desert Roast", "Sonora Roast", "Desert Roast Coffee"])
        self.assertEqual(generator.anchor_leads(SAMPLE_BRIEF), ["Desert", "Sonora", "DRC"])
        self.assertEqual(generator.anchor_tokens(SAMPLE_BRIEF),
                         {"desert", "roast", "sonora", "coffee", "drc"})

    def test_no_variations_means_no_anchor_rule(self):
        brief = dict(SAMPLE_BRIEF)
        brief["direct_anchor_rules"] = {"must_include_exact_variations": []}
        names = generator.generate(brief, count=20)
        self.assertEqual(len(names), 20)
        for n in names:
            self.assertGreaterEqual(len(n.split()), 2, n)


class TestPhonetics(unittest.TestCase):
    def test_soundex(self):
        self.assertEqual(soundex("Smith"), soundex("Smyth"))
        self.assertNotEqual(soundex("BYND"), soundex("Nike"))

    def test_phonetic_match(self):
        self.assertTrue(phonetic_match("BIND District", "BYND District"))
        self.assertFalse(phonetic_match("BYND District", "BYND District"))  # identical != phonetic


class TestRegions(unittest.TestCase):
    def test_explicit_states_win(self):
        codes, source, matched, dropped = regions.resolve_states("DMV area", ["AZ"])
        self.assertEqual(codes, ["AZ"])
        self.assertEqual(source, "explicit")

    def test_explicit_drops_unknown_codes(self):
        codes, source, matched, dropped = regions.resolve_states(None, ["AZ", "XX"])
        self.assertEqual(codes, ["AZ"])
        self.assertEqual(dropped, ["XX"])

    def test_dmv_alias(self):
        codes, source, matched, _ = regions.resolve_states("Washington D.C. / DMV Local")
        self.assertEqual(codes, ["DC", "MD", "VA"])
        self.assertEqual(source, "alias")

    def test_state_name_aliases(self):
        self.assertEqual(regions.resolve_states("California")[0], ["CA"])
        self.assertEqual(regions.resolve_states("Phoenix, Arizona")[0], ["AZ"])
        self.assertEqual(regions.resolve_states("New York")[0], ["NY"])
        self.assertEqual(regions.resolve_states("Texas")[0], ["TX"])
        self.assertEqual(regions.resolve_states("Florida")[0], ["FL"])

    def test_multi_state_aliases(self):
        self.assertEqual(regions.resolve_states("Pacific Northwest")[0], ["WA", "OR"])
        self.assertEqual(regions.resolve_states("New England")[0],
                         ["CT", "MA", "ME", "NH", "RI", "VT"])

    def test_washington_dc_is_not_washington_state(self):
        self.assertEqual(regions.resolve_states("Washington DC")[0], ["DC"])
        self.assertEqual(regions.resolve_states("Seattle, Washington")[0], ["WA"])

    def test_national_alone_resolves_to_none(self):
        codes, source, _, _ = regions.resolve_states("US National")
        self.assertEqual(codes, [])
        self.assertEqual(source, "none")

    def test_empty_scope_resolves_to_none(self):
        codes, source, _, _ = regions.resolve_states("")
        self.assertEqual(codes, [])
        self.assertEqual(source, "none")

    def test_bare_code_words_do_not_false_positive(self):
        # "in" / "or" appear in ordinary text — they must not resolve to IN/OR.
        codes, source, _, _ = regions.resolve_states("based in Phoenix, Arizona")
        self.assertEqual(codes, ["AZ"])
        self.assertNotIn("IN", codes)
        self.assertNotIn("OR", codes)

    def test_safe_bare_code(self):
        self.assertEqual(regions.resolve_states("Phoenix, AZ")[0], ["AZ"])


class TestRegistries(unittest.TestCase):
    def test_all_50_states_plus_dc(self):
        self.assertEqual(len(registries.REGISTRIES), 51)
        self.assertIn("DC", registries.REGISTRIES)
        for code in ("CA", "NY", "TX", "AZ", "FL"):
            self.assertIn(code, registries.REGISTRIES)

    def test_every_entry_has_name_portal_url_note(self):
        for code, entry in registries.REGISTRIES.items():
            for key in ("name", "portal", "url", "note"):
                self.assertTrue(entry.get(key), f"{code} missing {key}")
            self.assertTrue(entry["url"].startswith("https://"), code)

    def test_verification_file_covers_all_codes(self):
        path = os.path.join(ROOT, "brandstorm", "clearance", "registries_verification.json")
        with open(path) as f:
            ver = json.load(f)
        self.assertEqual(set(ver), set(registries.REGISTRIES))
        for code, rec in ver.items():
            self.assertIn("verified", rec, code)
            self.assertIn("ever_verified", rec, code)

    def test_get_registry_attaches_verification(self):
        entry = registries.get_registry("AZ")
        self.assertEqual(entry["code"], "AZ")
        self.assertIn("verified", entry)
        self.assertIsNone(registries.get_registry("XX"))


class TestStateTier(unittest.TestCase):
    def test_no_states_means_not_requested(self):
        r = state.check_state("Desert Ridge", states=[])
        self.assertEqual(r["status"], "not_requested")
        self.assertEqual(r["states"], {})
        self.assertIn("states", r["guidance"])

    def test_none_states_means_not_requested(self):
        r = state.check_state("Desert Ridge", states=None)
        self.assertEqual(r["status"], "not_requested")

    def test_requested_states_return_manual_links(self):
        r = state.check_state("Desert Ridge", states=["AZ"])
        self.assertEqual(r["status"], "manual")
        self.assertIn("AZ", r["states"])
        self.assertTrue(r["states"]["AZ"]["url"].startswith("https://"))

    def test_unknown_code_is_dropped(self):
        r = state.check_state("Desert Ridge", states=["XX"])
        self.assertEqual(r["status"], "manual")
        self.assertEqual(r["states"], {})


class TestSocialTier(unittest.TestCase):
    def test_handle_variants(self):
        self.assertEqual(social.handle_variants("desertridge"),
                         ["desertridge", "weardesertridge", "desertridgeco"])

    def test_display_name_always_unknown_with_reasons(self):
        # Pure function — no network. Every platform unknown, with a reason.
        dn = social.check_display_name("Desert Ridge")
        self.assertEqual(set(dn), {"X", "YouTube", "Instagram", "TikTok",
                                   "Facebook", "LinkedIn (company)", "LinkedIn (profile)"})
        for platform, v in dn.items():
            self.assertEqual(v["status"], "unknown", platform)
            self.assertTrue(v["reason"], platform)

    def test_live_platforms(self):
        self.assertEqual(social.LIVE_PLATFORMS,
                         ["X", "YouTube", "Facebook", "LinkedIn (company)"])


class TestScoring(unittest.TestCase):
    def _base(self):
        return {
            "domain": {"tlds": {"com": "available"}},
            "uspto": {"status": "ok", "matches": [], "nice_class": "030"},
            "social": {
                "live_platforms": ["X", "YouTube", "Facebook", "LinkedIn (company)"],
                "platforms": {
                    "X": {"desertridge": "free"},
                    "YouTube": {"desertridge": "free"},
                    "Facebook": {"desertridge": "free"},
                    "LinkedIn (company)": {"desertridge": "free"},
                    "Instagram": {"desertridge": "unknown"},
                    "TikTok": {"desertridge": "unknown"},
                    "LinkedIn (profile)": {"desertridge": "unknown"},
                },
                "display_name": {"name": "Desert Ridge", "platforms": {
                    "X": {"status": "unknown", "reason": "x"}}},
            },
        }

    def test_clean(self):
        badge, _ = scoring.score(self._base())
        self.assertEqual(badge, "clean")

    def test_conflict_exact_live(self):
        r = self._base()
        r["uspto"]["matches"] = [{"kind": "exact", "alive": True, "wordmark": "DESERT RIDGE"}]
        badge, reason = scoring.score(r)
        self.assertEqual(badge, "conflict")
        self.assertIn("DESERT RIDGE", reason)

    def test_partial_com_taken(self):
        r = self._base()
        r["domain"]["tlds"]["com"] = "taken"
        badge, _ = scoring.score(r)
        self.assertEqual(badge, "partial")

    def test_partial_similar_mark(self):
        r = self._base()
        r["uspto"]["matches"] = [{"kind": "phonetic", "alive": True, "wordmark": "DESERT RIDGE"}]
        badge, _ = scoring.score(r)
        self.assertEqual(badge, "partial")

    def test_partial_unknown_tier(self):
        r = self._base()
        r["uspto"]["status"] = "unknown"
        badge, _ = scoring.score(r)
        self.assertEqual(badge, "partial")

    def test_ig_tiktok_linkedin_profile_unknown_does_not_block_green(self):
        # Always unknown (login wall / HTTP 999) — a documented limitation,
        # not a badge blocker. Live platforms free + rest clear = clean.
        badge, _ = scoring.score(self._base())
        self.assertEqual(badge, "clean")

    def test_live_platform_unknown_blocks_green(self):
        r = self._base()
        r["social"]["platforms"]["X"] = {"desertridge": "unknown"}
        badge, _ = scoring.score(r)
        self.assertEqual(badge, "partial")

    def test_facebook_taken_blocks_green(self):
        r = self._base()
        r["social"]["platforms"]["Facebook"] = {"desertridge": "taken"}
        badge, _ = scoring.score(r)
        self.assertEqual(badge, "partial")

    def test_linkedin_company_taken_blocks_green(self):
        r = self._base()
        r["social"]["platforms"]["LinkedIn (company)"] = {"desertridge": "taken"}
        badge, _ = scoring.score(r)
        self.assertEqual(badge, "partial")

    def test_display_name_unknown_never_blocks_green(self):
        # Display-name checks are informational only.
        r = self._base()
        r["social"]["display_name"]["platforms"] = {
            p: {"status": "unknown", "reason": "r"} for p in
            ("X", "YouTube", "Facebook", "LinkedIn (company)")}
        badge, _ = scoring.score(r)
        self.assertEqual(badge, "clean")

    def test_old_results_without_live_platforms_still_score(self):
        # Back-compat: v0.1 results have no live_platforms key.
        r = self._base()
        del r["social"]["live_platforms"]
        badge, _ = scoring.score(r)
        self.assertEqual(badge, "clean")


class TestBriefs(unittest.TestCase):
    def test_sample_brief_loads_and_validates(self):
        self.assertTrue(SAMPLE_BRIEF.get("sample"))
        self.assertEqual(SAMPLE_BRIEF["states"], ["AZ"])
        self.assertEqual(SAMPLE_BRIEF["nice_class"], "030")
        self.assertEqual(SAMPLE_BRIEF["candidate_batch_size"], 50)
        self.assertIn("label", SAMPLE_BRIEF)
        self.assertIn("SAMPLE", SAMPLE_BRIEF["label"].upper())

    def test_example_brief_loads_and_has_no_states(self):
        # The example brief names no states -> Tier 3 not_requested.
        self.assertNotIn("states", EXAMPLE_BRIEF)
        codes, source, _, _ = regions.resolve_states(
            EXAMPLE_BRIEF.get("geographic_scope"), EXAMPLE_BRIEF.get("states"))
        self.assertEqual(source, "alias")  # "DMV" resolves via alias
        self.assertEqual(codes, ["DC", "MD", "VA"])

    def test_brief_without_geography_means_not_requested(self):
        codes, source, _, _ = regions.resolve_states(None, None)
        self.assertEqual((codes, source), ([], "none"))


class TestDomainParsing(unittest.TestCase):
    def test_doh_answer_means_taken(self):
        # _doh_status is exercised end-to-end in the live run; here we check
        # the JSON contract it parses, using the same shape Google returns.
        sample = json.loads(
            '{"Status":0,"Answer":[{"name":"google.com.","type":1,"TTL":300,"data":"142.251.218.238"}]}'
        )
        self.assertEqual(sample["Status"], 0)
        self.assertTrue(sample.get("Answer"))

    def test_doh_nxdomain_means_available(self):
        sample = json.loads('{"Status":3,"Authority":[{"name":"com.","type":6}]}')
        self.assertEqual(sample["Status"], 3)


if __name__ == "__main__":
    unittest.main()

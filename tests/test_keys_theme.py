"""Unit tests for BrandStorm AI v0.3: zero-key plumbing + dashboard theme.

No network: every HTTP call is mocked at the clearance helpers
(http_get / http_post_json). Fake keys are obvious placeholders
("TEST-KEY" etc.) — never real credentials — and are only used to
prove the keyed path is selected and the auth header is formed.
"""

import json
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from brandstorm import keys as keys_mod
from brandstorm.clearance import domain as domain_mod
from brandstorm.clearance import uspto as uspto_mod

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FAKE_KEY = "TEST-KEY-PLACEHOLDER"
FAKE_SECRET = "TEST-SECRET-PLACEHOLDER"


def _clear_key_env():
    for var in (keys_mod.GODADDY_KEY_ENV, keys_mod.GODADDY_SECRET_ENV,
                keys_mod.USPTO_KEY_ENV, keys_mod.LLM_KEY_ENV):
        os.environ.pop(var, None)


class TestKeysModule(unittest.TestCase):
    def setUp(self):
        _clear_key_env()

    def tearDown(self):
        _clear_key_env()

    def test_absent_keys_are_keyless(self):
        self.assertFalse(keys_mod.godaddy_present())
        self.assertFalse(keys_mod.uspto_key_present())
        self.assertFalse(keys_mod.llm_key_present())
        self.assertEqual(keys_mod.keys_status(), {
            "domain": "keyless", "uspto": "keyless", "state": "keyless",
            "social": "keyless", "llm": "keyless",
        })

    def test_godaddy_needs_both_key_and_secret(self):
        os.environ[keys_mod.GODADDY_KEY_ENV] = FAKE_KEY
        self.assertFalse(keys_mod.godaddy_present(), "key without secret must not count")
        os.environ[keys_mod.GODADDY_SECRET_ENV] = FAKE_SECRET
        self.assertTrue(keys_mod.godaddy_present())
        os.environ[keys_mod.GODADDY_SECRET_ENV] = "   "
        self.assertFalse(keys_mod.godaddy_present(), "blank secret must not count")

    def test_uspto_and_llm_presence(self):
        os.environ[keys_mod.USPTO_KEY_ENV] = FAKE_KEY
        os.environ[keys_mod.LLM_KEY_ENV] = FAKE_KEY
        self.assertTrue(keys_mod.uspto_key_present())
        self.assertTrue(keys_mod.llm_key_present())
        self.assertEqual(keys_mod.keys_status()["uspto"], "keyed")
        self.assertEqual(keys_mod.keys_status()["llm"], "keyed")

    def test_keys_status_never_returns_a_key_value(self):
        os.environ[keys_mod.GODADDY_KEY_ENV] = FAKE_KEY
        os.environ[keys_mod.GODADDY_SECRET_ENV] = FAKE_SECRET
        os.environ[keys_mod.USPTO_KEY_ENV] = FAKE_KEY
        os.environ[keys_mod.LLM_KEY_ENV] = FAKE_KEY
        status = keys_mod.keys_status()
        blob = json.dumps(status)
        for secret in (FAKE_KEY, FAKE_SECRET):
            self.assertNotIn(secret, blob)
            self.assertNotIn(secret[:6], blob)
        self.assertEqual(set(status.values()), {"keyed", "keyless"})

    def test_tier_method_labels(self):
        self.assertEqual(keys_mod.tier_method_label("domain"), "keyless (DNS)")
        self.assertEqual(keys_mod.tier_method_label("uspto"), "companion API")
        os.environ[keys_mod.GODADDY_KEY_ENV] = FAKE_KEY
        os.environ[keys_mod.GODADDY_SECRET_ENV] = FAKE_SECRET
        os.environ[keys_mod.USPTO_KEY_ENV] = FAKE_KEY
        self.assertEqual(keys_mod.tier_method_label("domain"), "keyed (GoDaddy)")
        self.assertEqual(keys_mod.tier_method_label("uspto"), "TSDR (keyed)")
        self.assertEqual(keys_mod.tier_method_label("nonsense"), "keyless")

    def test_annotate_tier_notes_names_the_method(self):
        base = {"domain": "old", "uspto": "old", "state": "keep me", "social": "keep me"}
        keyless = keys_mod.annotate_tier_notes(base)
        self.assertIn("KEYLESS (DNS)", keyless["domain"])
        self.assertIn("KEYLESS (companion API)", keyless["uspto"])
        self.assertEqual(keyless["state"], "keep me")
        self.assertEqual(base["domain"], "old", "input dict must not be mutated")
        os.environ[keys_mod.GODADDY_KEY_ENV] = FAKE_KEY
        os.environ[keys_mod.GODADDY_SECRET_ENV] = FAKE_SECRET
        os.environ[keys_mod.USPTO_KEY_ENV] = FAKE_KEY
        keyed = keys_mod.annotate_tier_notes(base)
        self.assertIn("KEYED (GoDaddy)", keyed["domain"])
        self.assertIn("KEYED (TSDR)", keyed["uspto"])
        self.assertIn("needs a live key to verify", keyed["domain"])
        self.assertIn("needs a live key to verify", keyed["uspto"])


class TestDomainKeyedPath(unittest.TestCase):
    def setUp(self):
        _clear_key_env()

    def tearDown(self):
        _clear_key_env()

    @staticmethod
    def _doh_nxdomain(url, timeout=8.0, headers=None):
        return 200, b'{"Status":3}', ""

    @staticmethod
    def _godaddy_available(url, timeout=8.0, headers=None):
        assert "api.godaddy.com/v1/domains/available" in url
        assert headers["Authorization"] == f"sso-key {FAKE_KEY}:{FAKE_SECRET}"
        return 200, b'{"available": true, "definitive": true, "domain": "x.com"}', ""

    def test_keyless_uses_doh_and_reports_method_doh(self):
        with mock.patch.object(domain_mod, "http_get", side_effect=self._doh_nxdomain):
            result = domain_mod.check_domain("desertridge", tlds=["com"])
        self.assertEqual(result["method"], "doh")
        self.assertEqual(result["com"], "available")
        self.assertNotIn("error", result)

    def test_keyed_uses_godaddy_and_reports_method_godaddy(self):
        os.environ[keys_mod.GODADDY_KEY_ENV] = FAKE_KEY
        os.environ[keys_mod.GODADDY_SECRET_ENV] = FAKE_SECRET
        with mock.patch.object(domain_mod, "http_get", side_effect=self._godaddy_available) as m:
            result = domain_mod.check_domain("desertridge", tlds=["com", "co"])
        self.assertEqual(result["method"], "godaddy")
        self.assertEqual(result["tlds"], {"com": "available", "co": "available"})
        self.assertEqual(m.call_count, 2, "one GoDaddy call per TLD, no DoH calls")

    def test_keyed_taken_maps_to_taken(self):
        os.environ[keys_mod.GODADDY_KEY_ENV] = FAKE_KEY
        os.environ[keys_mod.GODADDY_SECRET_ENV] = FAKE_SECRET
        fake = mock.Mock(return_value=(200, b'{"available": false, "definitive": true}', ""))
        with mock.patch.object(domain_mod, "http_get", fake):
            result = domain_mod.check_domain("google", tlds=["com"])
        self.assertEqual(result["com"], "taken")

    def test_keyed_error_is_unknown_never_doh_fallback(self):
        """Auth failure / 5xx / timeout -> unknown for that TLD, and the
        DoH resolvers are never consulted (that would mislabel the method)."""
        os.environ[keys_mod.GODADDY_KEY_ENV] = FAKE_KEY
        os.environ[keys_mod.GODADDY_SECRET_ENV] = FAKE_SECRET
        calls = []

        def _fail(url, timeout=8.0, headers=None):
            calls.append(url)
            return 401, b'{"code":"UNABLE_TO_AUTHENTICATE"}', ""

        with mock.patch.object(domain_mod, "http_get", side_effect=_fail):
            result = domain_mod.check_domain("desertridge", tlds=["com", "co"])
        self.assertEqual(result["method"], "godaddy")
        self.assertEqual(result["tlds"], {"com": "unknown", "co": "unknown"})
        self.assertIn("error", result)
        self.assertTrue(all("godaddy.com" in u for u in calls),
                        "every call must be GoDaddy — no DoH fallback")
        self.assertTrue(all("dns.google" not in u and "cloudflare" not in u for u in calls))

    def test_keyed_unparseable_body_is_unknown(self):
        os.environ[keys_mod.GODADDY_KEY_ENV] = FAKE_KEY
        os.environ[keys_mod.GODADDY_SECRET_ENV] = FAKE_SECRET
        fake = mock.Mock(return_value=(200, b'not json', ""))
        with mock.patch.object(domain_mod, "http_get", fake):
            result = domain_mod.check_domain("desertridge", tlds=["com"])
        self.assertEqual(result["com"], "unknown")
        self.assertIn("error", result)


class TestUsptoKeyedPath(unittest.TestCase):
    def setUp(self):
        _clear_key_env()
        self._old_base = uspto_mod._base_cache
        uspto_mod._base_cache = "https://tmsearch.uspto.gov/prod-stage-v1-0-0/"

    def tearDown(self):
        _clear_key_env()
        uspto_mod._base_cache = self._old_base

    @staticmethod
    def _companion_hit(wordmark="DESERT RIDGE", serial="97054561"):
        return {
            "hits": {"hits": [{"source": {
                "wordmark": wordmark, "serialNumber": serial,
                "statusDescription": "LIVE", "alive": True,
                "internationalClass": ["025"],
            }}]}
        }

    def test_keyless_uses_companion_and_reports_method_companion(self):
        with mock.patch.object(uspto_mod, "http_post_json",
                               return_value=(200, self._companion_hit(), "")):
            result = uspto_mod.check_uspto("Desert Ridge", "025")
        self.assertEqual(result["method"], "companion")
        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["exact_live"])
        self.assertNotIn("tsdr_verified", result["matches"][0])

    def test_keyed_verifies_via_tsdr_and_reports_method_tsdr(self):
        os.environ[keys_mod.USPTO_KEY_ENV] = FAKE_KEY
        tsdr_calls = []

        def _tsdr_get(url, timeout=10.0, headers=None):
            tsdr_calls.append((url, headers))
            assert "tsdrapi.uspto.gov/ts/cd/casestatus/sn97054561/info" in url
            assert headers["USPTO-API-KEY"] == FAKE_KEY
            return 200, b'{"status": "LIVE", "liveDeadIndicator": "LIVE"}', ""

        with mock.patch.object(uspto_mod, "http_post_json",
                               return_value=(200, self._companion_hit(), "")), \
             mock.patch.object(uspto_mod, "http_get", side_effect=_tsdr_get):
            result = uspto_mod.check_uspto("Desert Ridge", "025")
        self.assertEqual(result["method"], "tsdr")
        self.assertEqual(result["status"], "ok")
        self.assertEqual(len(tsdr_calls), 1)
        self.assertTrue(result["matches"][0]["tsdr_verified"])
        self.assertTrue(result["exact_live"])

    def test_keyed_tsdr_auth_failure_is_unknown_not_companion_fallback(self):
        os.environ[keys_mod.USPTO_KEY_ENV] = FAKE_KEY
        with mock.patch.object(uspto_mod, "http_post_json",
                               return_value=(200, self._companion_hit(), "")), \
             mock.patch.object(uspto_mod, "http_get",
                               return_value=(401, b'{}', "")):
            result = uspto_mod.check_uspto("Desert Ridge", "025")
        self.assertEqual(result["method"], "tsdr")
        self.assertEqual(result["status"], "unknown")
        self.assertEqual(result["matches"], [])
        self.assertFalse(result["exact_live"])
        self.assertIn("error", result)

    def test_keyed_tsdr_dead_signal_flips_alive(self):
        os.environ[keys_mod.USPTO_KEY_ENV] = FAKE_KEY
        with mock.patch.object(uspto_mod, "http_post_json",
                               return_value=(200, self._companion_hit(), "")), \
             mock.patch.object(uspto_mod, "http_get",
                               return_value=(200, b'{"liveDeadIndicator": "DEAD"}', "")):
            result = uspto_mod.check_uspto("Desert Ridge", "025")
        self.assertEqual(result["status"], "ok")
        self.assertFalse(result["matches"][0]["alive"])
        self.assertFalse(result["exact_live"])

    def test_tsdr_body_parser_json_and_xml(self):
        parsed = uspto_mod._parse_tsdr_body(b'{"case": {"liveDeadIndicator": "DEAD"}}')
        self.assertTrue(parsed["dead"])
        parsed = uspto_mod._parse_tsdr_body(
            b'<case><liveDeadIndicator>LIVE</liveDeadIndicator>'
            b'<statusCode>LIVE</statusCode></case>')
        self.assertFalse(parsed["dead"])
        self.assertEqual(parsed["status_text"], "LIVE")
        parsed = uspto_mod._parse_tsdr_body(b'not json or xml')
        self.assertIsNone(parsed["dead"])


class TestDashboardTheme(unittest.TestCase):
    def test_index_has_theme_toggle_light_dark_system(self):
        with open(os.path.join(ROOT, "frontend", "index.html")) as f:
            html = f.read()
        for needle in ('data-theme-choice="light"', 'data-theme-choice="dark"',
                       'data-theme-choice="system"', 'brandstorm-theme',
                       'localStorage', 'prefers-color-scheme'):
            self.assertIn(needle, html, needle)
        # Light is the default: the pre-paint script falls back to 'light'
        # and the :root variables are the light palette.
        self.assertIn("|| 'light'", html)
        self.assertIn('[data-theme="light"]', html)
        self.assertIn('[data-theme="dark"]', html)
        self.assertIn('--bg: #f7f7f8', html)
        self.assertIn('--bg: #0e0e11', html)  # original dark palette kept
        self.assertIn('#f5c518', html)  # same gold accent in both themes

    def test_index_keeps_every_feature(self):
        with open(os.path.join(ROOT, "frontend", "index.html")) as f:
            html = f.read()
        for needle in ('id="q"', 'id="runBtn"', 'id="tierNotes"', 'id="stats"',
                       'detailHtml', 'tierChips', 'id="fIndustry"', 'id="fStates"',
                       'display_name', 'data-f="clean"', 'data-f="conflict"',
                       '/api/run', '/api/results'):
            self.assertIn(needle, html, needle)

    def test_index_shows_tier_method(self):
        with open(os.path.join(ROOT, "frontend", "index.html")) as f:
            html = f.read()
        self.assertIn('Domain method:', html)
        self.assertIn('USPTO method:', html)
        self.assertIn('keys_status', html)


if __name__ == "__main__":
    unittest.main()

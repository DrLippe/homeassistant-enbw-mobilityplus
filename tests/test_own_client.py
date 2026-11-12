"""Contract tests for the independent API client: no credentials or network."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "enbw_mobilityplus"
SPEC = importlib.util.spec_from_file_location("own_enbw_client", ROOT / "providers" / "client.py")
MODULE = importlib.util.module_from_spec(SPEC)
import sys
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class FakeResponse:
    def __init__(self, status, location=None):
        self.status_code = status
        self.url = "https://myenergykey.com/authorize"
        self.headers = {"location": location} if location else {}


class OwnClientContractTest(unittest.TestCase):
    def setUp(self):
        self.client = MODULE.EnBWMobilityPlusClient()

    def tearDown(self):
        self.client.close()

    def test_code_and_matching_state(self):
        response = FakeResponse(302, "emob://myenergykey.com/android/com.enbw.ev/callback?code=CODE&state=STATE")
        self.assertEqual(self.client._follow_code(response, "STATE"), "CODE")

    def test_wrong_state_is_rejected(self):
        response = FakeResponse(302, "emob://myenergykey.com/android/com.enbw.ev/callback?code=CODE&state=BAD")
        with self.assertRaises(MODULE.EnBWAuthError):
            self.client._follow_code(response, "STATE")

    def test_oauth_error_without_secret(self):
        response = FakeResponse(302, "emob://myenergykey.com/callback?error=login_required&state=STATE")
        with self.assertRaises(MODULE.EnBWAuthError) as context:
            self.client._follow_code(response, "STATE")
        self.assertNotIn("STATE", str(context.exception))

    def test_external_redirect_is_blocked(self):
        with self.assertRaises(MODULE.EnBWAuthError):
            self.client._redirect("https://myenergykey.com/", "https://attacker.example/")

    def test_android_callback_pkce_parameters(self):
        from urllib.parse import urlsplit, parse_qs
        import base64
        import hashlib
        auth = self.client.begin_authorization()
        params = parse_qs(urlsplit(auth.authorize_url).query)
        self.assertEqual(params["redirect_uri"], [
            "emob://myenergykey.com/android/com.enbw.ev/callback"])
        self.assertEqual(params["state"], [auth.state])
        self.assertEqual(params["nonce"], [auth.nonce])
        self.assertEqual(params["code_challenge_method"], ["S256"])
        expected = base64.urlsafe_b64encode(
            hashlib.sha256(auth.verifier.encode()).digest()).rstrip(b"=").decode()
        self.assertEqual(params["code_challenge"], [expected])

    def test_finish_android_callback(self):
        from unittest.mock import Mock
        auth = self.client.begin_authorization()
        self.client._token = Mock(return_value=MODULE.Token(3600))
        self.client.load_profile = Mock()
        result = self.client.complete_authorization(
            f"emob://myenergykey.com/android/com.enbw.ev/callback"
            f"?code=AUTHCODE&state={auth.state}", auth)
        self.assertEqual(result.expires_in, 3600)
        self.client._token.assert_called_once()
        self.client.load_profile.assert_called_once()

    def test_reject_wrong_callback_and_state(self):
        auth = self.client.begin_authorization()
        for callback in (
            f"https://myenergykey.com/android/com.enbw.ev/callback?code=x&state={auth.state}",
            f"emob://evil.example/android/com.enbw.ev/callback?code=x&state={auth.state}",
            "emob://myenergykey.com/android/com.enbw.ev/callback?code=x&state=wrong",
        ):
            with self.subTest(callback=callback):
                with self.assertRaises(MODULE.EnBWAuthError):
                    self.client.complete_authorization(callback, auth)

    def test_affinity_cookies_are_forwarded(self):
        import httpx
        response = httpx.Response(200, headers=[
            ("set-cookie", "ARRAffinity=affinity; Path=/"),
            ("set-cookie", "JSESSIONID=session; Path=/"),
        ])
        self.client._capture_backend_cookies(response)
        self.client.access_token = "test"
        headers = self.client._get_headers()
        self.assertIn("ARRAffinity=affinity", headers["cookie"])
        self.assertIn("JSESSIONID=session", headers["cookie"])
        self.assertNotIn("random=value", headers["cookie"])

    def test_history_parsing(self):
        self.client._json = lambda *args, **kwargs: {
            "chargingHistoryEntries": [{"startedAt": "2026-11-12T10:00:00+01:00", "energyInKwh": 3.7}]
        }
        self.assertEqual(self.client.get_charging_history()[0].energy_in_kwh, 3.7)

    def test_active_parsing(self):
        self.client._json = lambda *args, **kwargs: {
            "activeChargingSessions": [{"transactionId": "tx-1"}]
        }
        self.assertEqual(self.client.get_active_sessions()[0]["transactionId"], "tx-1")


if __name__ == "__main__":
    unittest.main()

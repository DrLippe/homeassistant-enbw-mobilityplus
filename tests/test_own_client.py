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

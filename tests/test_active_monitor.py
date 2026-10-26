"""Contract tests for the EnBW Android active-session response."""

import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock


ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "enbw_mobilityplus"


def load_provider():
    """Load the adapter without requiring a Home Assistant installation."""
    for package in ("enbw_test", "enbw_test.providers"):
        obj = types.ModuleType(package)
        obj.__path__ = [str(ROOT)]
        sys.modules[package] = obj
    fake_upstream = types.ModuleType("enbw_mobilityplus_client")
    fake_upstream.EnBWMobilityPlusClient = Mock
    sys.modules["enbw_mobilityplus_client"] = fake_upstream
    for name, path in (
        ("enbw_test.model", ROOT / "model.py"),
        ("enbw_test.providers.enbw", ROOT / "providers" / "enbw.py"),
    ):
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules["enbw_test.providers.enbw"]


class ActiveMonitorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.adapter = load_provider()

    def provider_for(self, response):
        client = Mock()
        client.api_base_url = "https://api.example.invalid/emobility-complete/api/v2"
        client._get_headers.return_value = {"authorization": "test"}
        client.client.get.return_value = response
        provider = self.adapter.EnBWProvider("example@example.com", "test")
        provider._client = client
        return provider, client

    def test_active_session_fields_and_url(self):
        response = Mock()
        response.json.return_value = {"activeChargingSessions": [{
            "transactionId": "abc", "evseId": "DE*ABC", "address": "Kassel",
            "lastChargingPowerInKw": 48.5, "energyInKwh": 12.3,
            "batteryStateOfChargeInPercent": 75,
            "durationInSeconds": 900, "totalCostInEur": 7.5,
        }]}
        provider, client = self.provider_for(response)
        live = provider.fetch_active()
        self.assertEqual(live.primary.transaction_id, "abc")
        self.assertEqual(live.primary.location, "Kassel")
        self.assertEqual(live.primary.power_kw, 48.5)
        self.assertEqual(live.primary.soc_percent, 75)
        client.client.get.assert_called_once_with(
            "https://api.example.invalid/emobility-complete/api/v2/chargings/active",
            headers={"authorization": "test"},
        )

    def test_empty_is_inactive_and_missing_values_are_unknown(self):
        response = Mock()
        response.json.return_value = {"activeChargingSessions": []}
        provider, _ = self.provider_for(response)
        self.assertEqual(provider.fetch_active().sessions, ())
        response.json.return_value = {"activeChargingSessions": [{"transactionId": "a"}]}
        self.assertIsNone(provider.fetch_active().primary.power_kw)

    def test_malformed_response_is_not_inactive(self):
        response = Mock()
        response.json.return_value = {}
        provider, _ = self.provider_for(response)
        with self.assertRaises(ValueError):
            provider.fetch_active()

    def test_http_error_is_not_inactive(self):
        response = Mock()
        response.raise_for_status.side_effect = RuntimeError("403")
        provider, _ = self.provider_for(response)
        with self.assertRaises(RuntimeError):
            provider.fetch_active()


if __name__ == "__main__":
    unittest.main()

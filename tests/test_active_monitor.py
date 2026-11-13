"""Contract tests for the EnBW Android active-session response."""

import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock, patch


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
    fake_httpx = types.ModuleType("httpx")
    fake_httpx.HTTPStatusError = type("HTTPStatusError", (Exception,), {})
    fake_httpx.TimeoutException = type("TimeoutException", (Exception,), {})
    fake_httpx.ConnectError = type("ConnectError", (Exception,), {})
    sys.modules["httpx"] = fake_httpx
    for name, path in (
        ("enbw_test.model", ROOT / "model.py"),
        ("enbw_test.diagnostics", ROOT / "diagnostics.py"),
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

    def test_login_without_auth_trace_hook(self):
        """Client construction must match the successful standalone script."""
        adapter = self.adapter
        client = Mock()
        client.login.return_value.expires_in = 3600
        with patch.object(adapter, "EnBWMobilityPlusClient", return_value=client), \
             patch.object(adapter, "_log_runtime_versions"):
            provider = adapter.EnBWProvider("example@example.com", "password")
            self.assertIs(provider._ensure_login(), client)
        client.login.assert_called_once_with("example@example.com", "password")
        provider.close()

    def test_runtime_report_once(self):
        adapter = self.adapter
        adapter._log_runtime_versions.cache_clear()
        with unittest.mock.patch.object(adapter, "_LOGGER") as logger:
            adapter._log_runtime_versions()
            adapter._log_runtime_versions()
            logger.warning.assert_called_once()
            logged_args = logger.warning.call_args.args
            self.assertIn("auth_trace=disabled", logged_args[0])
            self.assertEqual(len(logged_args), 5)
        adapter._log_runtime_versions.cache_clear()

    def test_active_session_fields_and_url(self):
        response = Mock()
        response.json.return_value = {"activeChargingSessions": [{
            "transactionId": "abc", "evseId": "DE*ABC", "address": "Kassel",
            "chargePointType": "DC",
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
        self.assertEqual(live.primary.charge_point_type, "DC")
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

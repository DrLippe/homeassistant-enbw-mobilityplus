"""Token expiry, refresh fallback and safe setup-error diagnostics."""

from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from test_active_monitor import load_provider


class TokenHandlingTest(unittest.TestCase):
    def setUp(self):
        self.adapter = load_provider()
        self.client = Mock()
        self.client.refresh_token = "refresh-token"
        self.client.refresh_access_token.return_value = SimpleNamespace(expires_in=3600)
        self.provider = self.adapter.EnBWProvider("person@example.invalid", "private-password")
        self.provider._client = self.client

    def test_401_refreshes_and_retries(self):
        operation = Mock(side_effect=[ValueError("Failed to get charging history: 401 - secret-token"), "ok"])
        self.assertEqual(self.provider._with_auth(operation), "ok")
        self.client.refresh_access_token.assert_called_once()
        self.assertEqual(operation.call_count, 2)

    def test_403_does_not_trigger_authentication(self):
        operation = Mock(side_effect=ValueError("Failed to get charging history: 403"))
        with self.assertRaises(ValueError):
            self.provider._with_auth(operation)
        self.client.refresh_access_token.assert_not_called()

    def test_server_error_does_not_trigger_authentication(self):
        operation = Mock(side_effect=ValueError("Failed to get charging history: 503"))
        with self.assertRaises(ValueError):
            self.provider._with_auth(operation)
        self.client.refresh_access_token.assert_not_called()

    def test_proactive_refresh(self):
        self.provider._access_expires_at = 0
        self.assertEqual(self.provider._with_auth(lambda client: "ok"), "ok")
        self.client.refresh_access_token.assert_called_once()

    def test_refresh_failure_falls_back_to_login(self):
        self.client.refresh_access_token.side_effect = ValueError("Token refresh failed: 400 - secret-token")
        replacement = Mock()
        replacement.login.return_value = SimpleNamespace(expires_in=3600)
        self.adapter.EnBWMobilityPlusClient = lambda: replacement
        self.provider._access_expires_at = 0
        self.assertEqual(self.provider._with_auth(lambda client: "ok"), "ok")
        replacement.login.assert_called_once()

    def test_diagnostic_omits_secret_response(self):
        diagnostic = __import__("enbw_test.diagnostics", fromlist=["diagnostic_message"])
        message = diagnostic.diagnostic_message(ValueError("Token exchange failed: 400 - token=very-secret"))
        self.assertIn("Token-Austausch", message)
        self.assertIn("HTTP 400", message)
        self.assertNotIn("very-secret", message)

    def test_redirect_status_diagnostic(self):
        diagnostic = __import__("enbw_test.diagnostics", fromlist=["diagnostic_message"])
        self.assertIn("HTTP 302", diagnostic.diagnostic_message(ValueError("Identifier submission failed: 302")))

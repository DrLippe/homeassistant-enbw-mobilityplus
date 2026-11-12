"""Tests for safe and deliberately low-information Auth0 diagnostics."""
import importlib.util
import logging
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

import httpx

PATH = Path(__file__).resolve().parents[1] / "custom_components/enbw_mobilityplus/auth_trace.py"
SPEC = importlib.util.spec_from_file_location("test_auth_trace_module", PATH)
module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)


class TraceTests(unittest.TestCase):
    def test_400_never_logs_secrets_or_response_body(self):
        secret = "password-and-token-VERY-SECRET"
        request = httpx.Request(
            "POST", "https://myenergykey.com/u/login/password?state=" + secret,
            headers={"Authorization": "Bearer " + secret},
            content="password=" + secret,
        )
        response = httpx.Response(400, request=request, text=secret)
        with self.assertLogs(module._LOGGER.name, level="WARNING") as captured:
            module.trace_auth0_response(response)
        message = "\n".join(captured.output)
        self.assertIn("step=password", message)
        self.assertIn("HTTP 400", message)
        self.assertNotIn(secret, message)

    def test_location_is_classified_without_url(self):
        token = "private-state-123"
        self.assertEqual(
            module._redirect_step("https://myenergykey.com/u/passkey-enrollment?state=" + token),
            "passkey_enrollment",
        )
        self.assertEqual(
            module._redirect_step("https://unknown.example/secret?token=" + token),
            "external_or_app_callback",
        )

    def test_non_auth_host_is_ignored(self):
        response = httpx.Response(
            400, request=httpx.Request("POST", "https://api.emp.emob-enbw.com/login")
        )
        with patch.object(module._LOGGER, "warning") as warning:
            module.trace_auth0_response(response)
        warning.assert_not_called()

    def test_hook_installed_only_once(self):
        client = Mock()
        client.client.event_hooks = {"response": []}
        module.attach_auth0_trace(client)
        module.attach_auth0_trace(client)
        self.assertEqual(client.client.event_hooks["response"], [module.trace_auth0_response])


if __name__ == "__main__":
    unittest.main()

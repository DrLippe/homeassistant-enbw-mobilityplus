"""Verify that Auth0 diagnosis reveals only booleans and fixed step names."""
import importlib.util
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
    def test_400_reports_consistency_without_any_secret(self):
        secret = "private-state-VERY-SECRET"
        password = "secret-password-DONT-LOG"
        trace = module.Auth0Trace()
        request1 = httpx.Request("GET", "https://myenergykey.com/authorize?state=" + secret)
        request2 = httpx.Request("GET", "https://myenergykey.com/u/login/identifier?state=" + secret)
        trace(httpx.Response(302, request=request1, headers={"location": "/u/login/identifier?state=" + secret}))
        trace(httpx.Response(200, request=request2))
        request3 = httpx.Request(
            "POST", "https://myenergykey.com/u/login/identifier?state=" + secret,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Referer": "https://myenergykey.com/u/login/identifier?state=" + secret,
                "Cookie": "sid=" + password,
            },
            data={"username": "user@example.com", "password": password, "state": secret},
        )
        with self.assertLogs(module._LOGGER.name, level="WARNING") as output:
            trace(httpx.Response(400, request=request3, text=password))
        log = "\n".join(output.output)
        self.assertIn("step=identifier", log)
        self.assertIn("initial_state_present=True", log)
        self.assertIn("state_matches_initial=True", log)
        self.assertIn("state_form_matches_query=True", log)
        self.assertIn("page_state_matches_query=True", log)
        self.assertIn("cookie_present=True", log)
        self.assertNotIn(secret, log)
        self.assertNotIn(password, log)
        self.assertNotIn("user@example.com", log)

    def test_mismatch_is_boolean_only(self):
        trace = module.Auth0Trace()
        trace(httpx.Response(200, request=httpx.Request(
            "GET", "https://myenergykey.com/authorize?state=one"
        )))
        request = httpx.Request(
            "POST", "https://myenergykey.com/u/login/password?state=two",
            headers={"content-type": "application/x-www-form-urlencoded"},
            data={"state": "other", "password": "not-for-logs"},
        )
        with self.assertLogs(module._LOGGER.name, level="WARNING") as output:
            trace(httpx.Response(400, request=request))
        msg = output.output[0]
        self.assertIn("state_matches_initial=False", msg)
        self.assertIn("state_form_matches_query=False", msg)
        self.assertNotIn("not-for-logs", msg)

    def test_location_is_classified_without_url(self):
        self.assertEqual(module._redirect_step(
            "https://myenergykey.com/u/passkey-enrollment?state=private"
        ), "passkey_enrollment")
        self.assertEqual(module._redirect_step(
            "https://unknown.example/secret?token=private"
        ), "external_or_app_callback")

    def test_non_auth_host_is_ignored(self):
        response = httpx.Response(400, request=httpx.Request(
            "POST", "https://api.emp.emob-enbw.com/login"
        ))
        with patch.object(module._LOGGER, "warning") as warning:
            module.Auth0Trace()(response)
        warning.assert_not_called()

    def test_hook_installed_only_once_per_client(self):
        client = Mock()
        client.client.event_hooks = {"response": []}
        module.attach_auth0_trace(client)
        module.attach_auth0_trace(client)
        self.assertEqual(len(client.client.event_hooks["response"]), 1)
        self.assertIsInstance(client.client.event_hooks["response"][0], module.Auth0Trace)


if __name__ == "__main__":
    unittest.main()

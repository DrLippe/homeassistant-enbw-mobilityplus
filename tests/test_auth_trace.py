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

    def test_actual_html_form_and_referer_diagnostics(self):
        trace = module.Auth0Trace()
        secret = "SECRET_PRIVATE"
        html = (
            '<html><form action="/u/login/identifier" method="post">'
            '<input name="username"><input type="hidden" name="state" value="' + secret + '">'
            '<input name="_csrf" value="' + secret + '"></form></html>'
        )
        get_request = httpx.Request(
            "GET", "https://myenergykey.com/u/login/identifier?state=" + secret
        )
        trace(httpx.Response(
            200, request=get_request, text=html,
            headers={"content-type": "text/html"},
        ))
        request = httpx.Request(
            "POST", "https://myenergykey.com/u/login/identifier?state=" + secret,
            data={"state": secret, "username": "demo@example.com"},
            headers={
                "Referer": "https://myenergykey.com/u/login/identifier?state=" + secret,
            },
        )
        with self.assertLogs(module._LOGGER.name, level="WARNING") as logs:
            trace(httpx.Response(400, request=request, text="hidden-error-" + secret))
        line = logs.output[0]
        self.assertIn("referer_matches_actual_page=True", line)
        self.assertIn("html_form_found=True", line)
        self.assertIn("form_action_matches_post=True", line)
        self.assertIn("expected_fields_missing=True", line)
        self.assertNotIn(secret, line)
        self.assertNotIn("demo@example.com", line)

    def test_html_parser_does_not_publish_unknown_field_names(self):
        trace = module.Auth0Trace()
        page = httpx.Request(
            "GET", "https://myenergykey.com/u/login/identifier?state=s"
        )
        trace(httpx.Response(
            200, request=page,
            text='<form action="/u/login/identifier"><input name="secret_dynamic_custom_field"></form>',
            headers={"content-type": "text/html"},
        ))
        request = httpx.Request(
            "POST", "https://myenergykey.com/u/login/identifier?state=s",
            data={"state": "s"},
        )
        with self.assertLogs(module._LOGGER.name, level="WARNING") as logs:
            trace(httpx.Response(400, request=request))
        self.assertNotIn("secret_dynamic_custom_field", logs.output[0])
        self.assertIn("html_form_found=True", logs.output[0])

    def test_chunked_html_without_content_length_is_inspected(self):
        trace = module.Auth0Trace()
        req = httpx.Request("GET", "https://myenergykey.com/u/login/identifier?state=xyz")
        html = '<html><form action="/u/login/identifier"><input name="state"></form></html>'
        response = httpx.Response(
            200, request=req, text=html,
            headers={"content-type": "text/html; charset=utf-8", "transfer-encoding": "chunked"},
        )
        trace(response)
        self.assertEqual(trace._html_inspection, "inspected")
        self.assertEqual(len(trace._form_actions), 1)
        self.assertEqual(response.text, html)

    def test_javascript_shell_is_distinguished_from_uninspected(self):
        trace = module.Auth0Trace()
        req = httpx.Request("GET", "https://myenergykey.com/u/login/identifier?state=xyz")
        trace(httpx.Response(
            200, request=req,
            text='<html><div id="root"></div><script src="/login.js"></script></html>',
            headers={"content-type": "text/html"},
        ))
        self.assertEqual(trace._html_inspection, "inspected")
        self.assertEqual(trace._form_actions, [])
        self.assertTrue(trace._javascript_present)
        self.assertTrue(trace._app_root_present)
        post = httpx.Request(
            "POST", "https://myenergykey.com/u/login/identifier?state=xyz",
            data={"state": "xyz", "username": "private@example.com"},
        )
        with self.assertLogs(module._LOGGER.name, level="WARNING") as logs:
            trace(httpx.Response(400, request=post, text="private"))
        message = logs.output[0]
        self.assertIn("html_inspection=inspected", message)
        self.assertIn("html_form_found=False", message)
        self.assertIn("javascript_present=True", message)
        self.assertIn("app_root_present=True", message)
        self.assertNotIn("private@example.com", message)

    def test_non_html_is_reported_as_not_inspected(self):
        trace = module.Auth0Trace()
        req = httpx.Request("GET", "https://myenergykey.com/u/login/identifier?state=xyz")
        trace(httpx.Response(
            200, request=req, text='{"challenge":"hidden"}',
            headers={"content-type": "application/json"},
        ))
        self.assertEqual(trace._html_inspection, "non_html")
        self.assertIsNone(trace._form_actions)

    def test_hook_installed_only_once_per_client(self):
        client = Mock()
        client.client.event_hooks = {"response": []}
        module.attach_auth0_trace(client)
        module.attach_auth0_trace(client)
        self.assertEqual(len(client.client.event_hooks["response"]), 1)
        self.assertIsInstance(client.client.event_hooks["response"][0], module.Auth0Trace)


if __name__ == "__main__":
    unittest.main()

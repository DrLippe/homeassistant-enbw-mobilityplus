"""Conservative Auth0 redirect diagnostics for the third-party EnBW client.

Never inspect request/response bodies, query parameters, cookies, form data,
authorization headers, tokens or callback URLs. Only allow-listed steps are logged.
"""
from __future__ import annotations

import logging
from urllib.parse import urlsplit

_LOGGER = logging.getLogger(__name__)
_AUTH_HOST = "myenergykey.com"
_STEPS = {
    "/authorize": "authorize",
    "/u/login/identifier": "identifier",
    "/u/login/password": "password",
    "/u/login/identifier/password": "identifier_password",
    "/authorize/resume": "authorize_resume",
    "/oauth/token": "oauth_token",
}
_REDIRECT_PATHS = {
    "/u/login/identifier": "identifier",
    "/u/login/password": "password",
    "/u/passkey-enrollment": "passkey_enrollment",
    "/u/passkey-enrollment-local": "passkey_enrollment_local",
    "/authorize/resume": "authorize_resume",
    "/android/com.enbw.ev/callback": "android_callback",
    "/ios/com.enbw.ev/callback": "ios_callback",
}


def _step(path: str) -> str:
    """Return a fixed, non-sensitive step name instead of arbitrary URL paths."""
    return _STEPS.get(path, "other_auth_step")


def _redirect_step(location: str) -> str:
    """Categorize Location without exposing the Location URL or query."""
    if not location:
        return "none"
    parts = urlsplit(location)
    if parts.hostname and parts.hostname != _AUTH_HOST:
        return "external_or_app_callback"
    return _REDIRECT_PATHS.get(parts.path, "other_auth_step")


def trace_auth0_response(response) -> None:
    """HTTPX response hook: status/step-only, no body or cookie access."""
    req = response.request
    url = req.url
    if url.host != _AUTH_HOST:
        return
    status = response.status_code
    step = _step(url.path)
    if 300 <= status < 400:
        location = response.headers.get("location", "")
        _LOGGER.debug(
            "EnBW Auth0 HTTP %d: step=%s, next=%s",
            status, step, _redirect_step(location),
        )
    elif status >= 400:
        # Identical output regardless of email, password, session or error body.
        _LOGGER.warning("EnBW Auth0 HTTP %d: step=%s", status, step)
    else:
        _LOGGER.debug("EnBW Auth0 HTTP %d: step=%s", status, step)


def attach_auth0_trace(client) -> None:
    """Attach a passive observer to mawiak's existing HTTPX session."""
    hooks = client.client.event_hooks.setdefault("response", [])
    if trace_auth0_response not in hooks:
        hooks.append(trace_auth0_response)

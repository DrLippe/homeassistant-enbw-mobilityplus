"""Minimal, privacy-preserving diagnostics for mawiak Auth0 login.

Only fixed step names, HTTP statuses and booleans are logged. The request's
OAuth state values are compared ephemerally in memory but never persisted.
Response HTML can be inspected in memory, but is never logged.
"""
from __future__ import annotations

import logging
from html.parser import HTMLParser
from urllib.parse import parse_qs, urljoin, urlsplit

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
    return _STEPS.get(path, "other_auth_step")


def _redirect_step(location: str) -> str:
    if not location:
        return "none"
    parts = urlsplit(location)
    if parts.hostname and parts.hostname != _AUTH_HOST:
        return "external_or_app_callback"
    return _REDIRECT_PATHS.get(parts.path, "other_auth_step")


def _single_state(values: dict) -> str | None:
    states = values.get("state", [])
    return states[0] if len(states) == 1 and states[0] else None


class _LoginFormParser(HTMLParser):
    """Inspect only allow-listed *names*, never form values or text."""

    _KNOWN = frozenset({
        "username", "state", "captcha", "js-available", "is-brave",
        "webauthn-available", "webauthn-platform-available",
        "allow-passkeys", "acul-sdk", "password", "_csrf", "csrf",
    })

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.fields = set()
        self.actions = []
        self.has_script = False
        self.has_app_root = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "input":
            name = attrs.get("name")
            if name in self._KNOWN:
                self.fields.add(name)
        elif tag == "form":
            self.actions.append(attrs.get("action", ""))
        elif tag == "script":
            self.has_script = True
        elif tag in ("div", "main") and attrs.get("id") in ("root", "app", "auth0-lock-container"):
            self.has_app_root = True


class Auth0Trace:
    """Per-client response observer, deliberately never affects HTTP requests."""

    def __init__(self) -> None:
        self._initial_state: str | None = None
        self._last_page_step: str | None = None
        self._last_page_state: str | None = None
        self._last_page_url: str | None = None
        self._form_fields: set[str] | None = None
        self._form_actions: list[str] | None = None
        self._html_inspection = "not_attempted"
        self._javascript_present = False
        self._app_root_present = False

    def __call__(self, response) -> None:
        request = response.request
        url = request.url
        if url.host != _AUTH_HOST:
            return

        status = response.status_code
        step = _step(url.path)
        query_state = _single_state(parse_qs(url.query.decode("ascii", "ignore")))
        if step == "authorize" and request.method == "GET":
            self._initial_state = query_state
            self._last_page_step = None
            self._last_page_state = None
            self._last_page_url = None
            self._form_fields = None
            self._form_actions = None
            self._html_inspection = "not_attempted"
            self._javascript_present = False
            self._app_root_present = False

        if request.method == "GET" and status == 200:
            self._last_page_step = step
            self._last_page_state = query_state
            self._last_page_url = str(url)
            self._form_fields = None
            self._form_actions = None
            # The upstream client uses a normal (non-streaming) HTTPX request.
            # The response hook runs before the client reads response.text.
            # HTTPX caches response.read(), preserving its content for mawiak.
            if url.path.startswith("/u/login/"):
                content_type = response.headers.get("content-type", "").lower()
                if "text/html" not in content_type:
                    self._html_inspection = "non_html"
                else:
                    length = response.headers.get("content-length", "")
                    if length.isdigit() and int(length) > 262144:
                        self._html_inspection = "too_large"
                    else:
                        try:
                            # Some Auth0 HTML is chunked or compressed and has
                            # no Content-Length. Inspect it anyway, with a
                            # conservative maximum accepted HTML size.
                            raw = response.read()
                            if len(raw) > 262144:
                                self._html_inspection = "too_large"
                            else:
                                parser = _LoginFormParser()
                                parser.feed(raw.decode("utf-8", "replace"))
                                self._form_fields = parser.fields
                                self._form_actions = parser.actions
                                self._javascript_present = parser.has_script
                                self._app_root_present = parser.has_app_root
                                self._html_inspection = "inspected"
                        except Exception:
                            # Diagnostics may never interrupt authentication.
                            self._html_inspection = "read_error"

        if step in ("identifier", "password") and request.method == "POST" and status >= 400:
            # These names are fixed. No email, password, token, URL or raw state
            # is interpolated into a log message.
            body_state = None
            try:
                if request.headers.get("content-type", "").startswith(
                    "application/x-www-form-urlencoded"
                ):
                    body_state = _single_state(
                        parse_qs(request.content.decode("ascii", "ignore"))
                    )
            except (ValueError, RuntimeError, UnicodeError):
                pass

            referer = request.headers.get("referer", "")
            parsed_referer = urlsplit(referer)
            referer_state = _single_state(parse_qs(parsed_referer.query))
            referer_matches = (
                bool(referer)
                and parsed_referer.hostname == _AUTH_HOST
                and parsed_referer.path == url.path
                and bool(query_state)
                and referer_state == query_state
            )
            page_referer_matches = bool(
                self._last_page_url
                and referer
                and urlsplit(referer) == urlsplit(self._last_page_url)
            )
            form_action_matches = bool(
                self._form_actions is not None
                and any(
                    urlsplit(urljoin(self._last_page_url, action)).path == url.path
                    and urlsplit(urljoin(self._last_page_url, action)).hostname == _AUTH_HOST
                    for action in self._form_actions if self._last_page_url
                )
            )
            missing_known_fields = (
                bool(self._form_fields - set(parse_qs(
                    request.content.decode("utf-8", "replace"),
                    keep_blank_values=True,
                )))
                if self._form_fields is not None and
                request.headers.get("content-type", "").startswith(
                    "application/x-www-form-urlencoded"
                )
                else None
            )
            _LOGGER.warning(
                "EnBW Auth0 HTTP %d: step=%s, initial_state_present=%s, "
                "query_state_present=%s, form_state_present=%s, "
                "state_matches_initial=%s, state_form_matches_query=%s, "
                "previous_page=%s, page_state_matches_query=%s, "
                "cookie_present=%s, referer_matches_request=%s, "
                "referer_matches_actual_page=%s, html_form_found=%s, "
                "form_action_matches_post=%s, expected_fields_missing=%s, "
                "html_inspection=%s, javascript_present=%s, app_root_present=%s",
                status, step,
                bool(self._initial_state), bool(query_state), bool(body_state),
                bool(query_state and self._initial_state and query_state == self._initial_state),
                bool(query_state and body_state and query_state == body_state),
                self._last_page_step or "none",
                bool(query_state and self._last_page_state and query_state == self._last_page_state),
                bool(request.headers.get("cookie")),
                referer_matches,
                page_referer_matches,
                bool(self._form_actions),
                form_action_matches,
                missing_known_fields,
                self._html_inspection,
                self._javascript_present,
                self._app_root_present,
            )
            return

        if 300 <= status < 400:
            _LOGGER.debug(
                "EnBW Auth0 HTTP %d: step=%s, next=%s",
                status, step, _redirect_step(response.headers.get("location", "")),
            )
        elif status >= 400:
            _LOGGER.warning("EnBW Auth0 HTTP %d: step=%s", status, step)
        else:
            _LOGGER.debug("EnBW Auth0 HTTP %d: step=%s", status, step)


# Preserve the public hook name for backward compatibility with existing tests
# and integrations. It has no cross-request state.
trace_auth0_response = Auth0Trace()


def attach_auth0_trace(client) -> None:
    """Attach one independent, per-client observer to mawiak's HTTPX session."""
    hooks = client.client.event_hooks.setdefault("response", [])
    if not any(isinstance(hook, Auth0Trace) for hook in hooks):
        hooks.append(Auth0Trace())

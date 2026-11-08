"""Safe, actionable API diagnostics without credentials or response bodies."""

import re
from traceback import extract_tb

import httpx


_STAGES = (
    ("Identifier submission", "Anmeldung: Benutzername"),
    ("Failed to load password page", "Anmeldung: Passwortseite"),
    ("Login failed", "Anmeldung: Passwortübermittlung"),
    ("Authorization failed", "Anmeldung: Autorisierung"),
    ("Could not extract authorization code", "Anmeldung: Autorisierungscode"),
    ("Token exchange failed", "Anmeldung: Token-Austausch"),
    ("Token refresh failed", "Token-Erneuerung"),
    ("Failed to fetch user profile", "Anmeldung: Profil"),
    ("Failed to get profiles", "Profilabruf"),
    ("Failed to get charging history", "Ladehistorie"),
    ("Charging account ID not set", "Ladekonto"),
    ("Unexpected EnBW active", "Aktive Ladesitzungen: Datenformat"),
)


def diagnostic_message(exc: BaseException) -> str:
    """Expose only an error class, known operation and HTTP code.

    Upstream ValueErrors can embed raw HTTP response bodies (and therefore
    personal data or tokens); never log their unfiltered text or traceback.
    """
    message = str(exc)
    stage = next((name for marker, name in _STAGES if marker in message), None)
    if isinstance(exc, httpx.TimeoutException):
        stage = "Zeitüberschreitung"
    elif isinstance(exc, httpx.ConnectError):
        stage = "Netzwerkverbindung"
    elif isinstance(exc, httpx.HTTPStatusError):
        stage = stage or "HTTP-Anfrage"

    status = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None
    if status is None and stage:
        match = re.search(r"(?:^|[:\s])([345]\d\d)(?=\D|$)", message)
        if match:
            status = int(match.group(1))

    result = f"{type(exc).__name__}"
    if stage:
        result += f" – {stage}"
    if status is not None:
        result += f" (HTTP {status})"
    if not stage and exc.__traceback__ is not None:
        frames = extract_tb(exc.__traceback__)
        if frames:
            result += f" – {frames[-1].name}()"
    return result


def is_unauthorized(exc: BaseException) -> bool:
    """Only unauthorized (401) is evidence of an expired access token."""
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code == 401
    message = str(exc)
    return any(marker in message for marker in ("Failed to get charging history", "Failed to get profiles")) and bool(
        re.search(r":\s*401(?=\D|$)", message)
    )

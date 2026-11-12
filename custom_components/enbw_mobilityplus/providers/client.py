"""Standalone, unofficial EnBW mobility+ client.

API endpoints and Android Auth0/PKCE behavior were identified in mobility+ APK.
The password-form fallback is experimental and may require interactive Auth0 login.
No dependency on mawiak/enbw-mobilityplus-client.
"""
from __future__ import annotations

import base64
import hashlib
import secrets
from dataclasses import dataclass
from urllib.parse import parse_qs, urljoin, urlsplit

import httpx

AUTH = "https://myenergykey.com"
ROOT = "https://api.emp.emob-enbw.com/emobility-complete/api"
CLIENT_ID = "MCVlPomnunRHO86S3Ju1JUJENA8hEI4i"
REDIRECT = "com.enbw.ev://myenergykey.com/ios/com.enbw.ev/callback"
AUDIENCE = "https://pro-login.enbw.com/"
SCOPE = "email offline_access openid"
CUSTOM_SCOPE = (
    "read:bsr:emp read:bsr:lms read:bsr:cmdm read:bsr:permission "
    "read:bsr:airship read:bsr:thunderhead read:bsr:smart-mobility read:bsr:mobilityplus-engage"
)
API_KEY = "g6dm9b1vnhs456m98cre53dj5x"
SUBSCRIPTION_KEY = "c7097f4712dd4c20aae95ff6ad95d171"


class EnBWAuthError(ValueError):
    """Non-secret authentication error for Home Assistant logs."""

    def __init__(self, stage: str, status: int | None = None, reason: str | None = None):
        self.stage, self.status, self.reason = stage, status, reason
        super().__init__(f"{stage}" + (f" HTTP {status}" if status else "") +
                         (f" ({reason})" if reason else ""))


@dataclass(frozen=True)
class Token:
    expires_in: int


@dataclass(frozen=True)
class HistoryEntry:
    started_at: str
    stopped_at: str | None
    evse_id: str | None
    energy_in_kwh: float
    total_costs_in_eur: float | None
    address: str | None
    operator: str | None
    duration_in_seconds: int | None
    charge_plug_type: str | None
    charging_price_per_kwh_in_cent: float | None
    blocking_fee_costs_in_eur: float | None


class EnBWMobilityPlusClient:
    """Own EnBW HTTP/OAuth client, used only from executor jobs."""

    api_base_url = f"{ROOT}/v2"

    def __init__(self):
        self.client = httpx.Client(timeout=25, follow_redirects=False)
        self.access_token = None
        self.refresh_token = None
        self.charging_account_id = None

    @staticmethod
    def _query(url):
        parsed = urlsplit(url)
        return {**parse_qs(parsed.query), **parse_qs(parsed.fragment)}

    @staticmethod
    def _redirect(current, location):
        dest = urljoin(current, location)
        parsed = urlsplit(dest)
        # Never send credentials/cookies to an untrusted authorization host.
        if parsed.scheme != "https" or parsed.hostname != "myenergykey.com":
            raise EnBWAuthError("redirect", reason="unexpected_destination")
        return dest

    def _follow_code(self, response, state):
        for _ in range(20):
            if response.status_code not in (301, 302, 303, 307, 308):
                return None
            location = response.headers.get("location")
            if not location:
                raise EnBWAuthError("redirect", response.status_code, "missing_location")
            destination = urljoin(str(response.url), location)
            params = self._query(destination)
            if "error" in params:
                raise EnBWAuthError("authorization", reason="oauth_error")
            if "code" in params:
                if params.get("state", [None])[0] != state:
                    raise EnBWAuthError("authorization", reason="state_mismatch")
                return params["code"][0]
            response = self.client.get(self._redirect(str(response.url), location))
        raise EnBWAuthError("redirect", reason="too_many_redirects")

    def login(self, email, password):
        verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode()
        challenge = base64.urlsafe_b64encode(
            hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        state = secrets.token_urlsafe(32)
        params = {
            "client_id": CLIENT_ID, "code_challenge": challenge,
            "code_challenge_method": "S256", "audience": AUDIENCE,
            "redirect_uri": REDIRECT, "scope": SCOPE, "custom_scope": CUSTOM_SCOPE,
            "response_type": "code", "state": state, "viewsignup": "false",
        }
        response = self.client.get(f"{AUTH}/authorize", params=params)
        for _ in range(12):
            if response.status_code not in (301, 302, 303, 307, 308):
                break
            loc = response.headers.get("location")
            if not loc:
                raise EnBWAuthError("authorize", reason="missing_redirect")
            response = self.client.get(self._redirect(str(response.url), loc))
        if response.status_code != 200:
            raise EnBWAuthError("authorize", response.status_code)

        form = {
            "username": email, "captcha": "", "js-available": "true",
            "is-brave": "false", "webauthn-available": "true",
            "webauthn-platform-available": "true", "allow-passkeys": "true",
            "state": state, "acul-sdk": "@auth0/auth0-acul-js@1.3.0",
        }
        headers = {"content-type": "application/x-www-form-urlencoded", "origin": AUTH}
        response = self.client.post(
            f"{AUTH}/u/login/identifier", params={"state": state},
            data=form, headers=headers)
        if response.status_code not in (302, 303):
            raise EnBWAuthError("identifier", response.status_code)
        loc = response.headers.get("location")
        if not loc:
            raise EnBWAuthError("identifier", reason="missing_redirect")
        page = self.client.get(self._redirect(str(response.url), loc))
        if page.status_code != 200:
            raise EnBWAuthError("password_page", page.status_code)

        form["password"] = password
        response = self.client.post(
            f"{AUTH}/u/login/password", params={"state": state},
            data=form, headers=headers)
        if response.status_code not in (302, 303):
            raise EnBWAuthError("password_submission", response.status_code)
        code = self._follow_code(response, state)
        if not code:
            raise EnBWAuthError("authorization", reason="code_missing")
        token = self._token({
            "grant_type": "authorization_code", "code": code,
            "code_verifier": verifier, "client_id": CLIENT_ID, "redirect_uri": REDIRECT,
        })
        profiles = self._json("v1/profiles", with_account=False)
        if not isinstance(profiles, list) or not profiles:
            raise EnBWAuthError("profiles", reason="no_profile")
        self.charging_account_id = profiles[0].get("chargingAccountId")
        if not self.charging_account_id:
            raise EnBWAuthError("profiles", reason="no_charging_account_id")
        return token

    def _token(self, data):
        response = self.client.post(
            f"{AUTH}/oauth/token", json=data,
            headers={"accept": "application/json", "user-agent": "mobility+/506"})
        if response.status_code != 200:
            raise EnBWAuthError("token", response.status_code)
        payload = response.json()
        self.access_token = payload["access_token"]
        self.refresh_token = payload.get("refresh_token") or self.refresh_token
        return Token(int(payload.get("expires_in", 3600)))

    def refresh_access_token(self):
        if not self.refresh_token:
            raise EnBWAuthError("refresh", reason="missing_refresh_token")
        return self._token({
            "grant_type": "refresh_token", "refresh_token": self.refresh_token,
            "client_id": CLIENT_ID, "custom_scope": CUSTOM_SCOPE,
        })

    def _get_headers(self, include_charging_account=True):
        if not self.access_token:
            raise EnBWAuthError("api", reason="unauthenticated")
        headers = {
            "accept": "application/json", "accept-language": "de",
            "authorization": f"Bearer {self.access_token}",
            "apikey": API_KEY, "ocp-apim-subscription-key": SUBSCRIPTION_KEY,
            "platform": "Android", "appversion": "8.19.0", "versioncode": "425",
        }
        if include_charging_account and self.charging_account_id:
            headers["charging-account-id"] = self.charging_account_id
        return headers

    def _json(self, path, *, with_account=True, params=None):
        response = self.client.get(
            f"{ROOT}/{path}", params=params,
            headers=self._get_headers(include_charging_account=with_account))
        response.raise_for_status()
        return response.json()

    def get_charging_history(self, limit=100, offset=0):
        data = self._json("v2/chargings/history",
                          params={"limit": limit, "offset": offset})
        entries = data.get("chargingHistoryEntries") if isinstance(data, dict) else None
        if not isinstance(entries, list):
            raise ValueError("Unexpected EnBW history response")
        result = []
        for item in entries:
            result.append(HistoryEntry(
                started_at=item["startedAt"], stopped_at=item.get("stoppedAt"),
                evse_id=item.get("evseId"), energy_in_kwh=float(item.get("energyInKwh") or 0),
                total_costs_in_eur=item.get("totalCostsInEur"),
                address=item.get("address"), operator=item.get("operator"),
                duration_in_seconds=item.get("durationInSeconds"),
                charge_plug_type=item.get("chargePlugType"),
                charging_price_per_kwh_in_cent=item.get("chargingPricePerKwhInCent"),
                blocking_fee_costs_in_eur=item.get("blockingFeeCostsInEur"),
            ))
        return result

    def get_active_sessions(self):
        data = self._json("v2/chargings/active")
        sessions = data.get("activeChargingSessions") if isinstance(data, dict) else None
        if not isinstance(sessions, list):
            raise ValueError("Unexpected active sessions response")
        return sessions

    def close(self):
        self.client.close()

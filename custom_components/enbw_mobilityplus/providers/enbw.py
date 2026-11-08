"""EnBW mobility+ adapter around mawiak's Python client."""

from datetime import datetime
import logging
from threading import RLock
from time import monotonic
from typing import Callable, TypeVar

from enbw_mobilityplus_client import EnBWMobilityPlusClient
import httpx

from ..diagnostics import diagnostic_message, is_unauthorized
from ..model import ActiveCharge, ChargeSession, LiveSnapshot, ProviderSnapshot

T = TypeVar("T")
_REFRESH_MARGIN_SECONDS = 120
_LOGGER = logging.getLogger(__name__)


def _timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class EnBWProvider:
    """Isolate the synchronous third-party API from the HA event loop."""

    def __init__(self, email: str, password: str) -> None:
        self.email = email
        self.password = password
        self._client: EnBWMobilityPlusClient | None = None
        self._lock = RLock()
        self._access_expires_at: float | None = None

    def _ensure_login(self) -> EnBWMobilityPlusClient:
        if self._client is None:
            client = EnBWMobilityPlusClient()
            try:
                token = client.login(self.email, self.password)
            except Exception:
                client.close()
                raise
            self._client = client
            self._record_expiry(token.expires_in)
        return self._client

    def _record_expiry(self, lifetime: int) -> None:
        self._access_expires_at = monotonic() + max(0, lifetime)

    def _refresh_or_login(self) -> None:
        """Try refresh-token grant, then a new login if necessary."""
        client = self._client
        if client is not None and client.refresh_token:
            try:
                token = client.refresh_access_token()
            except (httpx.ConnectError, httpx.TimeoutException):
                raise
            except Exception as exc:
                # A revoked/expired refresh token may require full sign-in.
                _LOGGER.warning("EnBW Refresh Token rejected: %s; trying new login", diagnostic_message(exc))
            else:
                self._record_expiry(token.expires_in)
                return
        self.refresh_login()

    def _with_auth(self, operation: Callable[[EnBWMobilityPlusClient], T]) -> T:
        """Refresh before expiry and recover one 401 without retrying other errors."""
        with self._lock:
            client = self._ensure_login()
            if self._access_expires_at is not None and monotonic() >= self._access_expires_at - _REFRESH_MARGIN_SECONDS:
                self._refresh_or_login()
                client = self._ensure_login()
            try:
                return operation(client)
            except Exception as exc:
                if not is_unauthorized(exc):
                    raise

            # Refresh succeeded but the API might still reject the token or
            # cookie context; a full login then gets one final attempt.
            self._refresh_or_login()
            client = self._ensure_login()
            try:
                return operation(client)
            except Exception as exc:
                if not is_unauthorized(exc):
                    raise
            self.refresh_login()
            return operation(self._ensure_login())

    def fetch(self) -> ProviderSnapshot:
        """Fetch all pages, rather than silently presenting the last 25 as totals."""
        return self._with_auth(lambda client: self._fetch_history(client))

    def _fetch_history(self, client: EnBWMobilityPlusClient) -> ProviderSnapshot:
        entries = []
        page_size = 100
        offset = 0
        while True:
            page = client.get_charging_history(limit=page_size, offset=offset)
            entries.extend(page)
            if len(page) < page_size:
                break
            offset += len(page)
            if offset >= 10000:
                raise ValueError("EnBW history exceeds the safety pagination limit")

        sessions = []
        for entry in entries:
            start = _timestamp(entry.started_at)
            if start is None:
                continue
            sessions.append(
                ChargeSession(
                    identifier=f"{entry.evse_id}:{entry.started_at}",
                    started_at=start,
                    stopped_at=_timestamp(entry.stopped_at),
                    energy_kwh=entry.energy_in_kwh,
                    cost_eur=entry.total_costs_in_eur,
                    station=entry.address,
                    operator=entry.operator,
                    duration_seconds=entry.duration_in_seconds,
                    details={
                        "evse_id": entry.evse_id,
                        "plug_type": entry.charge_plug_type,
                        "charging_price_cent_per_kwh": entry.charging_price_per_kwh_in_cent,
                        "blocking_fee_eur": entry.blocking_fee_costs_in_eur,
                    },
                )
            )
        sessions.sort(key=lambda session: session.started_at, reverse=True)
        return ProviderSnapshot(
            sessions=tuple(sessions),
            total_sessions=len(sessions),
            total_energy_kwh=round(sum(s.energy_kwh for s in sessions), 3),
            total_cost_eur=round(sum(s.cost_eur or 0 for s in sessions), 2),
            last_session=sessions[0] if sessions else None,
        )

    def fetch_active(self) -> LiveSnapshot:
        """Query the active-session endpoint found in EnBW's Android app.

        Never turn an HTTP error or malformed response into 'not charging'.
        """
        return self._with_auth(self._fetch_active)

    def _fetch_active(self, client: EnBWMobilityPlusClient) -> LiveSnapshot:
        response = client.client.get(
            f"{client.api_base_url}/chargings/active",
            headers=client._get_headers(),
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict) or not isinstance(payload.get("activeChargingSessions"), list):
            raise ValueError("Unexpected EnBW active charging response")

        sessions = []
        for item in payload["activeChargingSessions"]:
            if not isinstance(item, dict):
                raise ValueError("Unexpected EnBW active session entry")
            sessions.append(
                ActiveCharge(
                    transaction_id=item.get("transactionId"),
                    evse_id=item.get("evseId"),
                    location=item.get("address"),
                    operator=item.get("operator"),
                    power_kw=item.get("lastChargingPowerInKw"),
                    energy_kwh=item.get("energyInKwh"),
                    soc_percent=item.get("batteryStateOfChargeInPercent"),
                    duration_seconds=item.get("durationInSeconds"),
                    cost_eur=item.get("totalCostInEur"),
                    charge_point_type=item.get("chargePointType"),
                )
            )
        return LiveSnapshot(tuple(sessions))

    def refresh_login(self) -> None:
        """Retry expired sessions with a fresh login and cookie context."""
        with self._lock:
            self.close()
            self._ensure_login()

    def close(self) -> None:
        with self._lock:
            if self._client:
                self._client.close()
                self._client = None
            self._access_expires_at = None

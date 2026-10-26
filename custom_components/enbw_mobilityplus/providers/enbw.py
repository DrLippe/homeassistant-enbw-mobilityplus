"""EnBW mobility+ adapter around mawiak's Python client."""

from datetime import datetime

from enbw_mobilityplus_client import EnBWMobilityPlusClient

from ..model import ChargeSession, ProviderSnapshot


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

    def _ensure_login(self) -> EnBWMobilityPlusClient:
        if self._client is None:
            client = EnBWMobilityPlusClient()
            try:
                client.login(self.email, self.password)
            except Exception:
                client.close()
                raise
            self._client = client
        return self._client

    def fetch(self) -> ProviderSnapshot:
        """Fetch all pages, rather than silently presenting the last 25 as totals."""
        client = self._ensure_login()
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

    def refresh_login(self) -> None:
        """Retry expired sessions with a fresh login and cookie context."""
        self.close()
        self._ensure_login()

    def close(self) -> None:
        if self._client:
            self._client.close()
            self._client = None

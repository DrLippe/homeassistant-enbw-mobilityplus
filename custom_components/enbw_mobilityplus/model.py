"""Charging history data models."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class ChargeSession:
    """A completed charging session."""

    identifier: str
    started_at: datetime
    stopped_at: datetime | None
    energy_kwh: float
    cost_eur: float | None = None
    station: str | None = None
    operator: str | None = None
    duration_seconds: int | None = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderSnapshot:
    """EnBW charging history and optional live values.

    Unknown live values remain None; completed history cannot determine live state.
    """

    sessions: tuple[ChargeSession, ...]
    total_sessions: int
    total_energy_kwh: float
    total_cost_eur: float
    last_session: ChargeSession | None
    connected: bool | None = None
    charging: bool | None = None
    tariff: str | None = None


@dataclass(frozen=True)
class ActiveCharge:
    """Values exposed by EnBW's active charging monitor (nullable upstream)."""

    transaction_id: str | None
    evse_id: str | None
    location: str | None
    operator: str | None
    power_kw: float | None
    energy_kwh: float | None
    soc_percent: int | None
    duration_seconds: int | None
    cost_eur: float | None


@dataclass(frozen=True)
class LiveSnapshot:
    """All simultaneously active sessions; not a physical cable sensor."""

    sessions: tuple[ActiveCharge, ...]

    @property
    def primary(self) -> ActiveCharge | None:
        return self.sessions[0] if self.sessions else None

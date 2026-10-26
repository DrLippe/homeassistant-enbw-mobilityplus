"""Provider-neutral charging data contract."""

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
    """Normalized values common to all providers.

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

"""Adapt our immutable charging history to the tariff comparison schema.

Adaptation of the MIT-licensed tariff logic from
https://github.com/sluggyly1991/enbw-mobilityplus-homeassistant
See LICENSE.upstream.
"""
from __future__ import annotations

from datetime import datetime

from .model import ProviderSnapshot
from .tariff import compare_tariffs


def tariff_comparison(snapshot: ProviderSnapshot, now: datetime, options: dict | None = None) -> dict:
    """Only completed sessions; no additional requests to EnBW."""
    rows = [
        {
            "started_at": session.started_at.isoformat(),
            "energy_in_kwh": session.energy_kwh,
            "operator": session.operator or "",
            "evse_id": session.details.get("evse_id") or "",
        }
        for session in snapshot.sessions
    ]
    # The provider fetches the entire paginated history, or fails explicitly
    # when the 10,000-session limit is reached.
    return compare_tariffs(
        {"sessions": rows, "limit_reached": False}, now, options
    )

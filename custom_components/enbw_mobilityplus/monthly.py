"""Local monthly summaries from already downloaded EnBW charging sessions."""
from __future__ import annotations

from datetime import datetime

from .model import ProviderSnapshot


def month_summary(snapshot: ProviderSnapshot, now: datetime) -> dict:
    """Group by the Home Assistant local month; do not call the API."""
    sessions = [
        session
        for session in snapshot.sessions
        if (local := session.started_at.astimezone(now.tzinfo)).year == now.year
        and local.month == now.month
    ]
    energy = sum(float(session.energy_kwh) for session in sessions)
    has_costs = all(session.cost_eur is not None for session in sessions)
    cost = sum(float(session.cost_eur) for session in sessions) if has_costs else None
    return {
        "energy": round(energy, 3),
        "cost": round(cost, 2) if cost is not None else None,
        "count": len(sessions),
        "price": round(cost / energy, 4) if cost is not None and energy > 0 else None,
    }


def recent_sessions(snapshot: ProviderSnapshot, limit: int = 50) -> list[dict]:
    """Bound dashboard attributes; omit missing cost rather than assuming zero."""
    return [
        {
            "started_at": s.started_at.isoformat(),
            "stopped_at": s.stopped_at.isoformat() if s.stopped_at else None,
            "address": s.station,
            "energy_in_kwh": s.energy_kwh,
            "total_costs_in_eur": s.cost_eur,
            "operator": s.operator,
        }
        for s in snapshot.sessions[:limit]
    ]

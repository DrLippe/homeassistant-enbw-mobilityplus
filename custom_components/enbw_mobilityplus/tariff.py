# Adapted from sluggyly1991/enbw-mobilityplus-homeassistant (MIT license).
# Copyright (c) 2026 Marc Szymkowiak, sluggyly1991.
# See LICENSE.upstream for the full license text.
"""Conservative tariff comparison using volumes, never historical paid prices."""

from calendar import monthrange
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

DEFAULTS = {
    "current_tariff": "M",
    "tariff_s_fee": 0.0,
    "tariff_s_price": 56.0,
    "tariff_m_fee": 5.99,
    "tariff_m_price": 46.0,
    "tariff_l_fee": 11.99,
    "tariff_l_price": 39.0,
    "tariff_prices_checked": "2026-11-06",
}
SOURCE = "https://www.enbw.com/elektromobilitaet/produkte/ladetarife"


def next_tariff_date(started):
    """One calendar month, clipping to the target month's last day."""
    year, month = started.year + (started.month == 12), started.month % 12 + 1
    return started.replace(year=year, month=month, day=min(started.day, monthrange(year, month)[1]))


def compare_tariffs(history, now, options=None):
    """Compare S/M/L tariffs over three complete local calendar months.

    A session before the window is required as a conservative coverage check.
    An API returning an apparently complete but silently shortened archive cannot
    be detected. German EnBW EVSEs only; roaming rates are identical across tiers.
    """
    settings = {**DEFAULTS, **(options or {})}
    end = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    index = end.year * 12 + end.month - 1 - 3
    start = end.replace(year=index // 12, month=index % 12 + 1)
    result = {
        "recommendation": "Prüfen",
        "reason": "insufficient_history",
        "monthly_savings": None,
        "break_even_kwh": None,
        "average_energy": None,
        "current_month_savings": None,
        "current_tariff": settings["current_tariff"],
        "target_tariff": None,
        "period_start": start.date().isoformat(),
        "period_end": (end - timedelta(days=1)).date().isoformat(),
        "price_source": SOURCE,
        "prices_checked": settings["tariff_prices_checked"],
        "basis": "three_complete_months_german_enbw_only",
    }
    try:
        started = (
            date.fromisoformat(settings["tariff_started_on"])
            if settings.get("tariff_started_on")
            else None
        )
        switch_on = (
            date.fromisoformat(settings["tariff_next_switch_on"])
            if settings.get("tariff_next_switch_on")
            else next_tariff_date(started)
            if started
            else None
        )
        if started and (started > now.date() or switch_on < started):
            raise ValueError
        result.update(
            tariff_started_on=started.isoformat() if started else None,
            next_switch_on=switch_on.isoformat() if switch_on else None,
            switch_allowed=now.date() >= switch_on if switch_on else None,
        )
    except (ValueError, TypeError):
        result["reason"] = "invalid_switch_dates"
        return result
    try:
        checked = date.fromisoformat(settings["tariff_prices_checked"])
        if not 0 <= (now.date() - checked).days <= 31:
            result["reason"] = "prices_outdated"
            return result
        prices = {}
        for tariff in "SML":
            fee = Decimal(str(settings[f"tariff_{tariff.lower()}_fee"]))
            price = Decimal(str(settings[f"tariff_{tariff.lower()}_price"])) / 100
            if not fee.is_finite() or not price.is_finite() or fee < 0 or price < 0:
                raise ValueError
            prices[tariff] = (fee, price)
        current = settings["current_tariff"]
        rank = "SML".index(current)
    except (ValueError, TypeError, InvalidOperation):
        result["reason"] = "invalid_prices"
        return result
    if history.get("limit_reached", True):
        result["reason"] = "history_limit_reached"
        return result
    volume, current_volume = Decimal(0), Decimal(0)
    oldest = now
    for row in history.get("sessions", []):
        try:
            dt = datetime.fromisoformat(row["started_at"].replace("Z", "+00:00"))
            if dt.tzinfo is None:
                raise ValueError
            dt = dt.astimezone(now.tzinfo)
            energy = Decimal(str(row["energy_in_kwh"]))
            if not energy.is_finite() or energy < 0:
                raise ValueError
        except (KeyError, ValueError, TypeError, InvalidOperation):
            result["reason"] = "invalid_history"
            return result
        oldest = min(oldest, dt)
        if str(row.get("operator", "")).strip().casefold() != "enbw" or not str(
            row.get("evse_id", "")
        ).upper().startswith("DE*EBW*"):
            continue
        if start <= dt < end:
            volume += energy
        if end <= dt <= now:
            current_volume += energy
    if oldest > start:
        return result
    average = volume / 3
    fee, price = prices[current]
    candidates = [t for t in "SML" if t != current]
    target = min(candidates, key=lambda t: prices[t][0] + average * prices[t][1])
    target_fee, target_price = prices[target]
    savings = fee + average * price - target_fee - average * target_price

    def money(value):
        return float(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

    result.update(
        recommendation="Ja" if savings > 0 else "Nein",
        reason="alternative_cheaper" if savings > 0 else "current_tariff_cheaper_or_equal",
        direction="upgrade" if "SML".index(target) > rank else "downgrade",
        threshold_relation="above"
        if price > target_price
        else "below"
        if price < target_price
        else None,
        target_tariff=target,
        monthly_savings=money(savings),
        average_energy=round(float(average), 3),
        current_month_energy=round(float(current_volume), 3),
        current_month_savings=money(
            fee + current_volume * price - target_fee - current_volume * target_price
        ),
        current_monthly_cost=money(fee + average * price),
        target_monthly_cost=money(target_fee + average * target_price),
        current_fee=float(fee),
        target_fee=float(target_fee),
        current_price_ct=float(price * 100),
        target_price_ct=float(target_price * 100),
        break_even_kwh=round(float(max(Decimal(0), (target_fee - fee) / (price - target_price))), 3)
        if price != target_price
        else None,
    )
    return result

"""Tests for the adaptation from our existing EnBW history model (no HA needed)."""
import importlib.util
from datetime import datetime
from pathlib import Path
import sys
import types
import unittest
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "enbw_mobilityplus"
PKG = "enbw_tariff_test"


def load_module(name):
    module_name = f"{PKG}.{name}"
    spec = importlib.util.spec_from_file_location(module_name, ROOT / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


package = types.ModuleType(PKG)
package.__path__ = [str(ROOT)]
sys.modules[PKG] = package
model = load_module("model")
load_module("tariff")
adapter = load_module("tariff_adapter")


class TariffAdapterTest(unittest.TestCase):
    now = datetime(2026, 11, 13, tzinfo=ZoneInfo("Europe/Berlin"))

    def snapshot(self, include_old=True):
        rows = []
        if include_old:
            rows.append(("2026-07-01T12:00:00+02:00", 1, "EnBW", "DE*EBW*TEST"))
        for month in (8, 9, 10):
            rows.append((f"2026-{month:02}-15T12:00:00+02:00", 160, "EnBW", "DE*EBW*TEST"))
        rows.append(("2026-10-17T12:00:00+02:00", 10000, "Other", "DE*OTHER*TEST"))
        sessions = tuple(
            model.ChargeSession(
                identifier=str(index),
                started_at=datetime.fromisoformat(start),
                stopped_at=None,
                energy_kwh=energy,
                operator=operator,
                details={"evse_id": evse},
            )
            for index, (start, energy, operator, evse) in enumerate(rows)
        )
        return model.ProviderSnapshot(
            sessions=sessions,
            total_sessions=len(sessions),
            total_energy_kwh=sum(x.energy_kwh for x in sessions),
            total_cost_eur=0,
            last_session=sessions[-1],
        )

    def test_upgrade_and_filter_roaming(self):
        result = adapter.tariff_comparison(self.snapshot(), self.now, {"current_tariff": "M"})
        self.assertEqual(result["recommendation"], "Ja")
        self.assertEqual(result["target_tariff"], "L")
        self.assertEqual(result["monthly_savings"], 5.2)
        self.assertEqual(result["average_energy"], 160)
        self.assertEqual(result["basis"], "three_complete_months_german_enbw_only")

    def test_incomplete_history_is_not_a_recommendation(self):
        result = adapter.tariff_comparison(self.snapshot(False), self.now)
        self.assertEqual(result["recommendation"], "Prüfen")
        self.assertEqual(result["reason"], "insufficient_history")

    def test_outdated_prices_are_not_a_recommendation(self):
        result = adapter.tariff_comparison(
            self.snapshot(), self.now, {"tariff_prices_checked": "2026-09-01"}
        )
        self.assertEqual(result["reason"], "prices_outdated")


if __name__ == "__main__":
    unittest.main()

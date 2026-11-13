"""Monthly and recent history calculations, without Home Assistant."""
import importlib.util
from datetime import datetime
from pathlib import Path
import sys
import types
import unittest
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "enbw_mobilityplus"
PKG = "enbw_month_test"
package = types.ModuleType(PKG)
package.__path__ = [str(ROOT)]
sys.modules[PKG] = package


def load_module(name):
    spec = importlib.util.spec_from_file_location(f"{PKG}.{name}", ROOT / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


model = load_module("model")
monthly = load_module("monthly")


class MonthTest(unittest.TestCase):
    def test_local_month_and_unknown_price(self):
        rows = (
            model.ChargeSession("a", datetime.fromisoformat("2026-10-31T23:30:00+00:00"), None, 4.0, 2.0),
            model.ChargeSession("b", datetime.fromisoformat("2026-11-12T12:00:00+01:00"), None, 6.0, None),
            model.ChargeSession("c", datetime.fromisoformat("2026-10-15T12:00:00+02:00"), None, 99.0, 50.0),
        )
        snapshot = model.ProviderSnapshot(rows, len(rows), 109.0, 52.0, rows[0])
        now = datetime(2026, 11, 13, tzinfo=ZoneInfo("Europe/Berlin"))
        result = monthly.month_summary(snapshot, now)
        self.assertEqual(result["energy"], 10)
        self.assertEqual(result["count"], 2)
        self.assertIsNone(result["cost"])
        self.assertIsNone(result["price"])
        self.assertEqual(len(monthly.recent_sessions(snapshot)), 3)

    def test_empty_month_is_zero(self):
        snapshot = model.ProviderSnapshot((), 0, 0, 0, None)
        now = datetime(2026, 11, 13, tzinfo=ZoneInfo("Europe/Berlin"))
        result = monthly.month_summary(snapshot, now)
        self.assertEqual(result["cost"], 0)
        self.assertEqual(result["energy"], 0)
        self.assertIsNone(result["price"])


if __name__ == "__main__":
    unittest.main()

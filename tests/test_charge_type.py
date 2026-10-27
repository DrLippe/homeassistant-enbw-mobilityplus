"""Check explicit, conservative connector mappings."""

import importlib.util
from pathlib import Path
import unittest


SPEC = importlib.util.spec_from_file_location(
    "charge_type", Path(__file__).resolve().parents[1] / "custom_components" / "enbw_mobilityplus" / "charge_type.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ChargeTypeTest(unittest.TestCase):
    def test_known_ac(self):
        for value in ("AC", "ac", "TYPE_2", "type-2", "SCHUKO"):
            with self.subTest(value=value):
                self.assertEqual(MODULE.normalize_charge_type(value), "AC")

    def test_known_dc(self):
        for value in ("DC", "CCS", "CCS_2", "CHADEMO"):
            with self.subTest(value=value):
                self.assertEqual(MODULE.normalize_charge_type(value), "DC")

    def test_unknown_is_not_guessed(self):
        for value in ("FAST", "HPC", "ULTRAFAST", "", None, "TYPE_UNKNOWN"):
            with self.subTest(value=value):
                self.assertIsNone(MODULE.normalize_charge_type(value))

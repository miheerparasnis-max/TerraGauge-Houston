"""Export helpers that turn model checks into published numbers."""

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("export_web", ROOT / "scripts" / "export_web.py")
export_web = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(export_web)


class BlendTestTests(unittest.TestCase):
    def test_blending_toward_neighbours_is_scored_against_gps(self):
        gps = [{"station_id": "OKEK", "longitude": -95.40, "latitude": 29.80, "up_mm_year": -5.0}]
        raw = {"a": (-95.40, 29.80, -9.0, 4.0), "b": (-95.41, 29.80, -5.5, 0.5)}
        shrunk = {"a": (-6.0, 1.0), "b": (-5.5, 0.5)}
        out = export_web.blend_test(raw, shrunk, gps, exclude=set())
        self.assertEqual(out["squares"], 2)
        self.assertEqual((out["typical_before_mm_year"], out["typical_after_mm_year"]), (2.2, 0.8))
        self.assertEqual(out["pulled_share_pct"], 50.0)  # only "a" leans mostly on its neighbourhood

    def test_reference_and_deep_seated_stations_are_never_the_truth(self):
        gps = [{"station_id": "DEN2", "longitude": -95.40, "latitude": 29.80, "up_mm_year": -5.0},
               {"station_id": "NETP", "longitude": -95.40, "latitude": 29.80, "up_mm_year": -5.0}]
        self.assertIsNone(export_web.blend_test({"a": (-95.40, 29.80, -9.0, 4.0)}, {"a": (-6.0, 1.0)}, gps, exclude={"DEN2"}))


if __name__ == "__main__":
    unittest.main()

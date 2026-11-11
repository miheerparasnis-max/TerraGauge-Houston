import unittest

from backend.hazards import chance_over, flood_class, harvey_check

try:
    import numpy as np
except ImportError:  # pragma: no cover
    np = None


class FloodTests(unittest.TestCase):
    def test_classes(self):
        self.assertEqual(flood_class("AE", None), "1pct")
        self.assertEqual(flood_class("VE", None), "1pct")
        self.assertEqual(flood_class("X", "0.2 PCT ANNUAL CHANCE FLOOD HAZARD"), "0.2pct")
        self.assertEqual(flood_class("X", "AREA WITH REDUCED FLOOD RISK DUE TO LEVEE"), "levee")
        self.assertEqual(flood_class("X", "AREA OF MINIMAL FLOOD HAZARD"), "minimal")
        self.assertIsNone(flood_class("OPEN WATER", None))

    def test_chance_over_30_years(self):
        self.assertAlmostEqual(chance_over(0.01, 30), 0.26, places=2)

    def test_harvey_ratio(self):
        cells = [{"cell_id": f"c{i}", "longitude": -95.0 + i * 0.01, "latitude": 29.5} for i in range(4)]
        zones = {"c0": ("AE", None), "c1": ("X", "AREA OF MINIMAL FLOOD HAZARD"), "c2": ("X", "AREA OF MINIMAL FLOOD HAZARD"), "c3": ("X", "AREA OF MINIMAL FLOOD HAZARD")}
        marks = [{"lon": -95.0, "lat": 29.5}] * 3 + [{"lon": -94.98, "lat": 29.5}]
        out = harvey_check(marks, cells, zones)
        row = next(r for r in out["rows"] if r["class"] == "1pct")
        self.assertEqual(out["marks"], 4)
        self.assertAlmostEqual(row["ratio"], 3.0)


@unittest.skipIf(np is None, "numpy needed")
class DroughtBendingTests(unittest.TestCase):
    def test_step_in_rate_is_bending(self):
        from backend.hazards import drought_and_bending

        dates = [f"{2016 + i // 4}-{1 + 3 * (i % 4):02d}-15" for i in range(32)]
        years = np.array([2016 + i / 4 + 0.04 for i in range(32)])
        cells = []
        for i in range(6):
            for j in range(3):
                rate = -20 if i >= 3 else -2
                cells.append({"cell_id": f"epsg3857-1km-{i}-{j}", "longitude": -95 + i * 0.01, "latitude": 29.7 + j * 0.01, "opera_series_mm": (rate * (years - 2016) * np.cos(np.radians(38))).tolist()})
        out = drought_and_bending({"dates": dates, "cells": cells})
        self.assertGreater(out["epsg3857-1km-2-1"]["bend_mm_year_km"], 15)
        self.assertLess(out["epsg3857-1km-0-1"]["bend_mm_year_km"], 1)


if __name__ == "__main__":
    unittest.main()

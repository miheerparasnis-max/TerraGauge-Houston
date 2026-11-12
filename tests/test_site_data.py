"""Checks on the exported website data (web/public/data). Skipped if not built."""
import json
import math
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "web" / "public" / "data"
GRID = ROOT / "data" / "derived" / "provisional" / "grid_cells.json"
ACTIONS = {"investigate_first", "add_monitoring", "review_disagreement", "observe", "no_clear_motion", "insufficient_data"}


@unittest.skipUnless((DATA / "cells.json").is_file() and (DATA / "meta.json").is_file(), "site data not exported")
class SiteDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cells = json.loads((DATA / "cells.json").read_text(encoding="utf-8"))
        cls.meta = json.loads((DATA / "meta.json").read_text(encoding="utf-8"))
        cls.by_id = {c["id"]: c for c in cls.cells}

    def test_ids_unique(self):
        self.assertEqual(len(self.by_id), len(self.cells))

    @unittest.skipUnless(GRID.is_file(), "grid not built")
    def test_every_grid_square_present(self):
        grid = {c["cell_id"] for c in json.loads(GRID.read_text(encoding="utf-8"))["cells"]}
        self.assertEqual(grid - set(self.by_id), set())

    def test_numbers_finite_and_sane(self):
        for c in self.cells:
            for k in ("rate", "se", "los"):
                v = c.get(k)
                if v is not None:
                    self.assertTrue(math.isfinite(v), (c["id"], k))
            if c["rate"] is not None and c["act"] != "insufficient_data":
                self.assertLess(abs(c["rate"]), 60, c["id"])
            self.assertTrue(29.0 < c["lat"] < 30.5 and -96.2 < c["lon"] < -94.5, c["id"])

    def test_actions_and_confidence(self):
        for c in self.cells:
            self.assertIn(c["act"], ACTIONS)
            if c["act"] == "insufficient_data":
                self.assertIsNone(c["conf"])
            else:
                self.assertIn(c["conf"], ("high", "medium", "low"))
            if c["act"] in ("investigate_first", "add_monitoring"):
                self.assertTrue(c["flood"]["sfha"], c["id"])
                self.assertLess(c["rate"], 0, c["id"])

    def test_counts_match(self):
        counts = {}
        for c in self.cells:
            counts[c["act"]] = counts.get(c["act"], 0) + 1
        for k, n in counts.items():
            self.assertEqual(self.meta["counts"]["action"].get(k), n, k)

    def test_forecast_ranges(self):
        years = [str(y) for y in self.meta["forecast"]["years"]]
        self.assertTrue(years)
        for c in self.cells:
            f = c.get("future")
            if not f:
                continue
            self.assertEqual(sorted(f["by"]), years)
            prev = 0.0
            for y in years:
                v = f["by"][y]
                self.assertLessEqual(v["lo"], v["c"] + 0.05)
                self.assertGreaterEqual(v["hi"], v["c"] - 0.05)
                width = v["hi"] - v["lo"]
                self.assertGreaterEqual(width + 0.05, prev)
                prev = width

    def test_sensor_and_node_sites(self):
        sensors, nodes = self.meta["sensors"], self.meta["nodes"]
        self.assertEqual([s["rank"] for s in sensors], list(range(1, len(sensors) + 1)))
        for s in sensors:
            self.assertEqual(self.by_id[s["id"]]["act"], "add_monitoring")
        for n in nodes:
            self.assertIn(n["id"], self.by_id)
            self.assertGreater(self.by_id[n["id"]]["gps"]["km"], self.meta["thresholds"]["gps_covered_km"])

    def test_gap_sites(self):
        gaps = self.meta.get("gaps", [])
        self.assertTrue(gaps)
        for g in gaps:
            c = self.by_id[g["id"]]
            self.assertNotIn("satellite", c["src"])
            self.assertEqual(c["act"], "insufficient_data")
            self.assertGreaterEqual(c["gps"]["km"], 4.0)

    def test_weighted_rates_stay_close_for_precise_squares(self):
        for c in self.cells:
            if c.get("raw") is not None and c["src"] == ["satellite"] and c["quality"]["fitSe"] is not None and c["quality"]["fitSe"] < 1.0:
                self.assertLess(abs(c["raw"] - c["rate"]), 5.0, c["id"])

    def test_hazard_levels(self):
        for c in self.cells:
            h = c.get("hz")
            if h:
                self.assertIn(h["dl"], ("high", "medium", "low"))
                self.assertIn(h["bl"], ("high", "medium", "low", None))
                self.assertNotIn("estimated", c["src"])


if __name__ == "__main__":
    unittest.main()

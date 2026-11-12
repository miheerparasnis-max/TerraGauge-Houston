import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("build_grid", ROOT / "scripts" / "build_grid.py")
build_grid = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build_grid)  # type: ignore[union-attr]


class GridTests(unittest.TestCase):
    def test_grid_covers_box_without_gaps(self):
        ids = build_grid.grid_ids((-95.5, 29.7, -95.4, 29.8))
        cols = {i for i, _ in ids}
        rows = {j for _, j in ids}
        self.assertEqual(len(ids), len(cols) * len(rows))
        self.assertGreater(len(ids), 100)

    def test_round_trip(self):
        x, y = build_grid.merc(-95.37, 29.76)
        lon, lat = build_grid.lonlat(x, y)
        self.assertAlmostEqual(lon, -95.37, places=6)
        self.assertAlmostEqual(lat, 29.76, places=6)

    def test_zone_lookup_prefers_high_risk_and_respects_holes(self):
        square = [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0], [0.0, 0.0]]
        hole = [[0.4, 0.4], [0.6, 0.4], [0.6, 0.6], [0.4, 0.6], [0.4, 0.4]]
        feats = [
            {"properties": {"FLD_ZONE": "X", "ZONE_SUBTY": "AREA OF MINIMAL FLOOD HAZARD", "SFHA_TF": "F"}, "geometry": {"type": "Polygon", "coordinates": [square]}},
            {"properties": {"FLD_ZONE": "AE", "ZONE_SUBTY": None, "SFHA_TF": "T"}, "geometry": {"type": "Polygon", "coordinates": [square, hole]}},
        ]
        z = build_grid.ZoneLookup(feats, size=0.5)
        self.assertEqual(z.zone(0.2, 0.2), ("AE", None, True))
        self.assertEqual(z.zone(0.5, 0.5)[0], "X")
        self.assertEqual(z.zone(2.0, 2.0), (None, None, False))


if __name__ == "__main__":
    unittest.main()

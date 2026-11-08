import unittest

from backend.insights import backtest, confidence, priority, project, sensor_plan, vertical_rate


class InsightTests(unittest.TestCase):
    def test_vertical_rate_is_larger_than_los(self):
        self.assertLess(vertical_rate(-8), -8)

    def test_confidence_levels(self):
        self.assertEqual(confidence(se_vertical=1.0, residual_sd_mm=10, gps_difference_mm_year=1.0)[0], "high")
        self.assertEqual(confidence(se_vertical=1.0, residual_sd_mm=10, gps_difference_mm_year=None)[0], "medium")
        self.assertEqual(confidence(se_vertical=6.0, residual_sd_mm=25, gps_difference_mm_year=8)[0], "low")
        self.assertEqual(confidence(se_vertical=1.0, residual_sd_mm=10, gps_difference_mm_year=None, neighbor_difference_mm_year=15)[0], "low")

    def test_priority_order(self):
        self.assertEqual(priority(rate_vertical=None, significant=False, level=None, flood_zone_sfha=False)[0], "no_data")
        self.assertEqual(priority(rate_vertical=-1, significant=False, level="high", flood_zone_sfha=True)[0], "stable")
        self.assertEqual(priority(rate_vertical=-12, significant=True, level="high", flood_zone_sfha=False)[0], "urgent")
        self.assertEqual(priority(rate_vertical=-6, significant=True, level="medium", flood_zone_sfha=True)[0], "urgent")
        self.assertEqual(priority(rate_vertical=-6, significant=True, level="medium", flood_zone_sfha=False)[0], "high")
        self.assertEqual(priority(rate_vertical=-12, significant=True, level="low", flood_zone_sfha=False)[0], "watch")
        self.assertEqual(priority(rate_vertical=-90, significant=True, level="high", flood_zone_sfha=False)[0], "check")
        self.assertEqual(priority(rate_vertical=-12, significant=True, level="high", flood_zone_sfha=False, open_water=True)[0], "no_data")

    def test_projection_band_widens_with_time(self):
        a, b = project(-10, 1, 1, 1.0, 2), project(-10, 1, 5, 1.0, 2)
        self.assertAlmostEqual(b["center_mm"], -50)
        self.assertGreater(b["high_mm"] - b["low_mm"], a["high_mm"] - a["low_mm"])

    def test_backtest_detects_persistent_rates(self):
        dates = [f"{2016 + i // 4}-{1 + 3 * (i % 4):02d}-01" for i in range(20)]
        cells = []
        for k in range(30):
            rate = -k
            cells.append({"opera_series_mm": [rate * (i * 0.25) for i in range(20)]})
        result = backtest(cells, dates, "2018-07-01")
        self.assertGreater(result["correlation"], 0.99)
        self.assertEqual(result["best_damping"], 1.0)
        self.assertTrue(result["beats_no_motion"])

    def test_sensor_plan_spreads_out_and_skips_covered(self):
        base = dict(priority="urgent", confidence="high", sfha=False, rate=-15)
        cells = [
            {**base, "id": "a", "lon": -95.6, "lat": 29.9, "gps_km": 6},
            {**base, "id": "b", "lon": -95.601, "lat": 29.9, "gps_km": 6},   # too close to a
            {**base, "id": "c", "lon": -95.3, "lat": 29.7, "gps_km": 1},     # already covered
            {**base, "id": "d", "lon": -95.2, "lat": 29.6, "gps_km": 5},
        ]
        plan = sensor_plan(cells, [], count=5)
        self.assertEqual([c["id"] for c in plan], ["a", "d"])
        self.assertEqual(plan[0]["rank"], 1)


if __name__ == "__main__":
    unittest.main()

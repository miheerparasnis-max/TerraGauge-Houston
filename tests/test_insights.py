import unittest

import re

from backend.insights import confidence, priority, sensor_plan, vertical_rate


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

    def test_priority_reasons_are_windowed_and_inside_the_claims_policy(self):
        record = "the 2016-2021 satellite record"
        cases = [
            dict(rate_vertical=-1, significant=False, level="high", flood_zone_sfha=False),
            dict(rate_vertical=-12, significant=True, level="high", flood_zone_sfha=False),
            dict(rate_vertical=-6, significant=True, level="medium", flood_zone_sfha=True),
            dict(rate_vertical=-6, significant=True, level="medium", flood_zone_sfha=False),
            dict(rate_vertical=-12, significant=True, level="low", flood_zone_sfha=False),
        ]
        for case in cases:
            _, reason = priority(**case, record=record)
            self.assertIn(record, reason)
            self.assertIsNone(re.search(r"sinking|predict|forecast|will flood", reason, flags=re.IGNORECASE), reason)

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

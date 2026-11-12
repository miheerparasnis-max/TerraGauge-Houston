import unittest

from backend.ingestion.provisional import chain_sum, deramp_pair, fit_plane, opera_series


def _pair(dates, values):
    return {"parameters": {"acquisition_dates": dates}, "cells": [
        {"cell_id": f"c{i}", "longitude": -95.3 + (i % 5) * 0.01, "latitude": 29.7 + (i // 5) * 0.01, "pair_los_displacement_mm": v, "coherence_median": 0.8, "valid_fraction": 0.9, "in_main_connected_component": True}
        for i, v in enumerate(values)]}


class ProvisionalTests(unittest.TestCase):
    def test_fit_plane_recovers_coefficients(self):
        pts = [(x, y, 2 + 3 * x - 4 * y) for x in range(4) for y in range(4)]
        a, b, c = fit_plane(pts)
        self.assertAlmostEqual(a, 2); self.assertAlmostEqual(b, 3); self.assertAlmostEqual(c, -4)

    def test_deramp_removes_pure_ramp(self):
        pair = _pair(["2025-11-02", "2025-11-14"], [0.0] * 25)
        for cell in pair["cells"]:
            cell["pair_los_displacement_mm"] = 100 * (cell["longitude"] + 95.3) + 50 * (cell["latitude"] - 29.7) + 7
        result = deramp_pair(pair)
        self.assertTrue(all(abs(c["pair_los_displacement_mm"]) < 1e-6 for c in result["cells"]))
        self.assertIsNotNone(result["cells"][3]["pair_los_displacement_before_deramp_mm"])

    def test_chain_sum_requires_consecutive_pairs_and_sums(self):
        a = _pair(["2025-11-02", "2025-11-14"], [1.0] * 25)
        b = _pair(["2025-11-14", "2025-11-26"], [2.0] * 25)
        result = chain_sum([b, a])
        self.assertEqual(result["parameters"]["acquisition_dates"], ["2025-11-02", "2025-11-26"])
        self.assertAlmostEqual(result["cells"][0]["pair_los_displacement_mm"], 3.0)
        with self.assertRaises(ValueError):
            chain_sum([a, _pair(["2025-11-26", "2025-12-08"], [1.0] * 25)])

    def test_opera_series_rereferences_and_fits_velocity(self):
        def product(ref, sec, step):
            return {"parameters": {"reference_date": ref, "secondary_date": sec}, "cells": [
                {"cell_id": "ref1", "longitude": -95.0, "latitude": 29.0, "opera_pair_displacement_mm": 5.0, "opera_valid_fraction": 1, "opera_water_fraction": 0},
                {"cell_id": "ref2", "longitude": -95.0, "latitude": 29.001, "opera_pair_displacement_mm": 5.0, "opera_valid_fraction": 1, "opera_water_fraction": 0},
                {"cell_id": "ref3", "longitude": -95.001, "latitude": 29.0, "opera_pair_displacement_mm": 5.0, "opera_valid_fraction": 1, "opera_water_fraction": 0},
                {"cell_id": "sink", "longitude": -95.5, "latitude": 29.5, "opera_pair_displacement_mm": 5.0 + step, "opera_valid_fraction": 1, "opera_water_fraction": 0},
                {"cell_id": "lake", "longitude": -95.6, "latitude": 29.6, "opera_pair_displacement_mm": 5.0, "opera_valid_fraction": 1, "opera_water_fraction": 1},
            ]}
        products = [product("2017-01-01", "2018-01-01", -10), product("2018-01-01", "2019-01-01", -10), product("2019-01-01", "2020-01-01", -10)]
        result = opera_series(products, (-95.01, 28.99, -94.99, 29.01))
        sink = next(c for c in result["cells"] if c["cell_id"] == "sink")
        self.assertAlmostEqual(sink["opera_los_velocity_mm_year"], -10, delta=0.1)
        self.assertNotIn("lake", [c["cell_id"] for c in result["cells"]])

    def test_opera_series_withholds_incomplete_time_series(self):
        products = []
        for ref, sec, sink_value in [("2017-01-01", "2018-01-01", -5.0), ("2018-01-01", "2019-01-01", None), ("2019-01-01", "2020-01-01", -5.0)]:
            refs = [{"cell_id": f"ref{i}", "longitude": -95.0, "latitude": 29.0 + i / 1000, "opera_pair_displacement_mm": 0.0, "opera_valid_fraction": 1, "opera_water_fraction": 0} for i in range(3)]
            products.append({"parameters": {"reference_date": ref, "secondary_date": sec}, "cells": [*refs, {"cell_id": "sink", "longitude": -95.5, "latitude": 29.5, "opera_pair_displacement_mm": sink_value, "opera_valid_fraction": 1, "opera_water_fraction": 0}]})
        result = opera_series(products, (-95.01, 28.99, -94.99, 29.01))
        self.assertNotIn("sink", [c["cell_id"] for c in result["cells"]])


if __name__ == "__main__":
    unittest.main()


class OperaClassificationTests(unittest.TestCase):
    def test_action_order(self):
        from backend.decision import classify_opera_velocity
        from backend.model import Label, Thresholds

        t = Thresholds()
        common = dict(velocity_se_mm_year=0.5, noise_floor_mm_year=1.5, flood_exposed=True, thresholds=t)
        self.assertEqual(classify_opera_velocity(velocity_mm_year=None, **{**common, "velocity_se_mm_year": None}, gps_distance_km=1)[0], Label.INSUFFICIENT_DATA)
        self.assertEqual(classify_opera_velocity(velocity_mm_year=-10, gps_distance_km=5, **common)[0], Label.ADD_MONITORING)
        self.assertEqual(classify_opera_velocity(velocity_mm_year=-10, gps_distance_km=1, **common)[0], Label.INVESTIGATE_SIGNAL)
        self.assertEqual(classify_opera_velocity(velocity_mm_year=-2, gps_distance_km=1, **common)[0], Label.CONTEXT_ONLY)
        # A large velocity with a huge fit error is not a candidate.
        self.assertEqual(classify_opera_velocity(velocity_mm_year=-10, gps_distance_km=1, velocity_se_mm_year=8, noise_floor_mm_year=1.5, flood_exposed=None, thresholds=t)[0], Label.CONTEXT_ONLY)


class MergeFramesTests(unittest.TestCase):
    def test_secondary_frame_is_shifted_and_only_fills_gaps(self):
        from backend.ingestion.provisional import merge_frames

        params = {"reference_date": "2020-01-01", "secondary_date": "2020-04-01"}
        cell = lambda i, v, f=1.0: {"cell_id": f"c{i}", "longitude": 0, "latitude": 0, "opera_pair_displacement_mm": v, "opera_valid_fraction": f}  # noqa: E731
        primary = {"parameters": params, "cells": [cell(i, 10.0) for i in range(30)] + [{"cell_id": "c99", "opera_pair_displacement_mm": None, "opera_valid_fraction": 0.0}]}
        secondary = {"parameters": params, "cells": [cell(i, 7.0) for i in range(30)] + [cell(99, 1.0), cell(100, 2.0)]}
        merged, stats = merge_frames(primary, secondary)
        by = {c["cell_id"]: c for c in merged["cells"]}
        self.assertEqual(stats["offset_mm"], 3.0)
        self.assertEqual(stats["added"], 2)
        self.assertEqual(by["c99"]["opera_pair_displacement_mm"], 4.0)
        self.assertEqual(by["c100"]["opera_pair_displacement_mm"], 5.0)
        self.assertEqual(by["c5"]["opera_pair_displacement_mm"], 10.0)

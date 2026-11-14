import unittest

from backend.ingestion.corrections import empty_correction_record
from backend.ingestion.provisional import chain_sum, deramp_pair, fit_plane, opera_series


def _pair(dates, values):
    return {"parameters": {"acquisition_dates": dates}, "applied_corrections": empty_correction_record(), "cells": [
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


class GappedSeriesTests(unittest.TestCase):
    def test_gap_does_not_inflate_uncertainty_or_bias_rate(self):
        products = []
        dates = [f"{2016 + k // 4}-{1 + 3 * (k % 4):02d}-01" for k in range(25)]
        for k in range(24):
            refs = [{"cell_id": f"ref{i}", "longitude": -95.0, "latitude": 29.0 + i / 1000, "opera_pair_displacement_mm": 0.0, "opera_valid_fraction": 1, "opera_water_fraction": 0} for i in range(3)]
            cells = [*refs, {"cell_id": "full", "longitude": -95.5, "latitude": 29.5, "opera_pair_displacement_mm": -2.5, "opera_valid_fraction": 1, "opera_water_fraction": 0},
                     {"cell_id": "gap", "longitude": -95.6, "latitude": 29.5, "opera_pair_displacement_mm": None if k == 11 else -2.5, "opera_valid_fraction": 1, "opera_water_fraction": 0}]
            products.append({"parameters": {"reference_date": dates[k], "secondary_date": dates[k + 1]}, "cells": cells})
        result = {c["cell_id"]: c for c in opera_series(products, (-95.01, 28.99, -94.99, 29.01))["cells"]}
        self.assertAlmostEqual(result["gap"]["opera_los_velocity_mm_year"], -10.0, delta=0.05)
        self.assertLess(result["gap"]["opera_velocity_se_mm_year"], 0.05)
        self.assertEqual(result["gap"]["opera_links_filled"], [11])


class FrameMergeTests(unittest.TestCase):
    def test_merged_frame_never_moves_the_reference(self):
        from backend.ingestion.provisional import merge_frames

        def product(ref, sec, ref_value, south_ref_value):
            cells = [{"cell_id": f"ref{i}", "longitude": -95.0, "latitude": 29.0 + i / 1000, "opera_pair_displacement_mm": ref_value + i if i else None, "opera_valid_fraction": 1, "opera_water_fraction": 0} for i in range(4)]
            cells += [{"cell_id": f"ov{i}", "longitude": -95.3, "latitude": 29.3, "opera_pair_displacement_mm": 1.0, "opera_valid_fraction": 1, "opera_water_fraction": 0} for i in range(25)]
            south = [{"cell_id": "ref0", "longitude": -95.0, "latitude": 29.0, "opera_pair_displacement_mm": south_ref_value, "opera_valid_fraction": 1, "opera_water_fraction": 0}]
            south += [{"cell_id": f"ov{i}", "longitude": -95.3, "latitude": 29.3, "opera_pair_displacement_mm": 1.0, "opera_valid_fraction": 1, "opera_water_fraction": 0} for i in range(25)]
            south += [{"cell_id": "far", "longitude": -95.5, "latitude": 29.2, "opera_pair_displacement_mm": -4.0, "opera_valid_fraction": 1, "opera_water_fraction": 0}]
            return {"parameters": {"reference_date": ref, "secondary_date": sec}, "cells": cells}, {"parameters": {"reference_date": ref, "secondary_date": sec}, "cells": south}

        dates = ["2017-01-01", "2018-01-01", "2019-01-01", "2020-01-01"]
        plain, merged = [], []
        for a, b in zip(dates, dates[1:]):
            p, s = product(a, b, 0.0, 50.0)   # the south frame puts a wild value in a reference square F38238 lacks
            plain.append(p); merged.append(merge_frames(p, s)[0])
        ref = {"ref0", "ref1", "ref2", "ref3"}
        self.assertEqual(opera_series(plain, reference_cell_ids=ref)["reference_offsets_mm"], opera_series(merged, reference_cell_ids=ref)["reference_offsets_mm"])
        far = next(c for c in opera_series(merged, reference_cell_ids=ref)["cells"] if c["cell_id"] == "far")
        self.assertAlmostEqual(far["opera_los_velocity_mm_year"], -6.0, delta=0.01)

import json
import unittest
from pathlib import Path

from backend.ingestion.provisional import compare_opera_gps, region_cell_ids, stable_gps_reference
from backend.ingestion.station_types import DEEP_SEATED_GNSS, display_gps_rate, is_deep_seated

ROOT = Path(__file__).resolve().parents[1]


def station(station_id, up=0.0, years=20.0, end=2024.0, lon=-95.4, lat=29.8):
    return {"station_id": station_id, "longitude": lon, "latitude": lat, "up_mm_year": up, "history_years": years,
            "start_decimal_year": end - years, "end_decimal_year": end, "samples": int(years * 365)}


class DeepSeatedStationTests(unittest.TestCase):
    def test_the_five_published_deep_seated_stations(self):
        # Wang et al. (2022), J. Surv. Eng. 148(4): 04022008.
        self.assertEqual(set(DEEP_SEATED_GNSS), {"ADKS", "LKHU", "NETP", "TXEX", "UHKD"})
        self.assertEqual(DEEP_SEATED_GNSS["TXEX"]["anchor_depth_m"], 936)
        self.assertTrue(is_deep_seated("NETP"))
        self.assertFalse(is_deep_seated("COH2"))

    def test_stable_reference_never_uses_a_deep_seated_station(self):
        stations = [station("ADKS", -0.5), station("NETP", 0.3), station("COH2", -0.5), station("THSU", 0.7)]
        reference, held_out = stable_gps_reference(stations)
        used = {s["station_id"] for s in reference + held_out}
        self.assertEqual(used, {"COH2", "THSU"})

    def test_excluding_a_deep_seated_station_does_not_move_other_stations(self):
        stations = [station("AAAA"), station("ADKS"), station("BBBB"), station("CCCC")]
        reference, held_out = stable_gps_reference(stations)
        # Split on AAAA, ADKS, BBBB, CCCC first, then drop ADKS from its half.
        self.assertEqual([s["station_id"] for s in reference], ["AAAA", "BBBB"])
        self.assertEqual([s["station_id"] for s in held_out], ["CCCC"])

    def test_radar_comparison_never_uses_a_deep_seated_station(self):
        series = {"cells": [{"cell_id": "c", "longitude": -95.4, "latitude": 29.8, "opera_los_velocity_mm_year": -1.0}]}
        stations = [station("TXEX", 3.4), station("NETP", 0.3), station("OKEK", -9.0)]
        rows = compare_opera_gps(series, stations)["stations"]
        self.assertEqual([r["station_id"] for r in rows], ["OKEK"])

    def test_campaign_stations_never_enter_the_headline_comparison(self):
        # PR-5 / V3: campaign-style stations (< 0.5 position days a day) are reported apart.
        series = {"cells": [{"cell_id": "c", "longitude": -95.4, "latitude": 29.8, "opera_los_velocity_mm_year": -1.0}]}
        sparse = dict(station("PA20", -4.0), samples=int(20 * 365 * 0.14))
        out = compare_opera_gps(series, [station("OKEK", -9.0), sparse])
        self.assertEqual([r["station_id"] for r in out["stations"]], ["OKEK"])
        self.assertEqual([r["station_id"] for r in out["campaign_stations"]["stations"]], ["PA20"])
        self.assertEqual(out["stats"]["station_count"], 1)

    def test_region_cells_are_those_within_the_radius_of_any_reference_station(self):
        stations = {"DEN2": station("DEN2", lon=-95.0, lat=29.0), "TMCC": station("TMCC", lon=-95.5, lat=29.5)}
        cells = [{"cell_id": "near", "longitude": -95.01, "latitude": 29.0}, {"cell_id": "far", "longitude": -95.25, "latitude": 29.25},
                 {"cell_id": "near2", "longitude": -95.5, "latitude": 29.52}]
        self.assertEqual(region_cell_ids(stations, ["DEN2", "TMCC"], cells, 3.0), {"near", "near2"})
        with self.assertRaises(ValueError):
            region_cell_ids(stations, ["ADKS"], cells, 3.0)

    def test_implausible_gps_rates_are_not_displayed_as_motion(self):
        self.assertEqual(display_gps_rate(-9.0), (-9.0, None))
        self.assertEqual(display_gps_rate(-615.6), (None, "implausible_in_source"))
        self.assertEqual(display_gps_rate(None), (None, None))

    def test_preregistration_excludes_deep_seated_stations(self):
        reference = json.loads((ROOT / "config" / "preregistration.json").read_text(encoding="utf-8"))["reference"]
        used = set(reference["reference_stations"]) | set(reference["held_out_stable_stations"])
        self.assertFalse(used & set(DEEP_SEATED_GNSS))
        self.assertTrue(set(DEEP_SEATED_GNSS) <= set(reference["station_rule"]["excluded_station_ids"]))


if __name__ == "__main__":
    unittest.main()

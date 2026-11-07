import json
import tempfile
import unittest
from pathlib import Path

from backend.ingestion.houston import build_houston_evidence


class HoustonEvidenceBuildTests(unittest.TestCase):
    def test_build_preserves_pairwise_limits_and_withholds_cell_flood_label(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            nisar = {
                "parameters": {"acquisition_dates": ["2025-11-02", "2025-11-14"]},
                "cells": [
                    {"cell_id": "a", "longitude": -95.3, "latitude": 29.7, "pair_los_displacement_mm": -10, "coherence_median": 0.6, "valid_fraction": 0.8, "in_main_connected_component": True},
                    {"cell_id": "b", "longitude": -95.31, "latitude": 29.71, "pair_los_displacement_mm": -14, "coherence_median": 0.7, "valid_fraction": 0.9, "in_main_connected_component": True},
                    {"cell_id": "c", "longitude": -95.32, "latitude": 29.72, "pair_los_displacement_mm": -12, "coherence_median": 0.8, "valid_fraction": 0.9, "in_main_connected_component": True},
                ],
            }
            houstonnet = {"stations": [{"station_id": "GPS-1", "longitude": -95.3, "latitude": 29.7, "up_mm_year": -4, "start_decimal_year": 2020, "end_decimal_year": 2024}]}
            groundwater = {"series": [{"site_id": "USGS-1", "longitude": -95.3, "latitude": 29.7, "depth_change_ft": 1.2}]}
            fema = {"source_layer": "FEMA NFHL", "stations": [{"site_id": "USGS-1", "flood_zone": "AE"}]}
            paths = []
            for name, payload in (("nisar.json", nisar), ("gps.json", houstonnet), ("water.json", groundwater), ("fema.json", fema)):
                path = root / name
                path.write_text(json.dumps(payload), encoding="utf-8")
                paths.append(path)
            result = build_houston_evidence(*paths, reference_bbox=(-95.4, 29.6, -95.2, 29.8))
            self.assertGreater(result["reference_scatter_mm"], 0)
            self.assertIn("one pairwise LOS observation", result["limitations"][0])
            self.assertIsNone(result["cells"][0]["flood_exposed"])
            self.assertFalse(result["cells"][0]["evidence"]["gps_comparison_time_matched"])

    def test_build_uses_saved_cell_flood_context_when_available(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            nisar = {"parameters": {"acquisition_dates": ["2025-11-02", "2025-11-14"]}, "cells": [
                {"cell_id": "a", "longitude": -95.3, "latitude": 29.7, "pair_los_displacement_mm": -10, "coherence_median": 0.6, "valid_fraction": 0.8, "in_main_connected_component": True},
                {"cell_id": "b", "longitude": -95.31, "latitude": 29.71, "pair_los_displacement_mm": -14, "coherence_median": 0.7, "valid_fraction": 0.9, "in_main_connected_component": True},
                {"cell_id": "c", "longitude": -95.32, "latitude": 29.72, "pair_los_displacement_mm": -12, "coherence_median": 0.8, "valid_fraction": 0.9, "in_main_connected_component": True},
            ]}
            empty = {"stations": []}
            groundwater = {"series": []}
            flood_context = {"source_layer": "FEMA NFHL", "cells": [{"cell_id": "a", "flood_exposed": True, "flood_zone": "AE"}]}
            paths = []
            for name, payload in (("nisar.json", nisar), ("gps.json", empty), ("water.json", groundwater), ("fema.json", empty), ("flood.json", flood_context)):
                path = root / name
                path.write_text(json.dumps(payload), encoding="utf-8")
                paths.append(path)
            result = build_houston_evidence(*paths[:4], cell_flood_context_path=paths[4])
            self.assertTrue(result["cells"][0]["flood_exposed"])
            self.assertEqual(result["cells"][0]["evidence"]["flood_zone"], "AE")


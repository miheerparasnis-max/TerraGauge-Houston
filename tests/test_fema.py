import json
import tempfile
import unittest
from pathlib import Path

from backend.ingestion.fema import classify_cell_centers, join_nfhl_point_responses


class FemaIngestionTests(unittest.TestCase):
    def test_joins_flood_zone_to_one_evidence_site(self):
        groundwater = {"series": [{"site_id": "123", "site_name": "Example", "longitude": -95.0, "latitude": 29.5, "cell_id": "cell"}]}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "groundwater.json").write_text(json.dumps(groundwater), encoding="utf-8")
            (root / "fema-123.json").write_text(json.dumps({"features": [{"attributes": {"FLD_ZONE": "AE", "ZONE_SUBTY": "FLOODWAY", "SFHA_TF": "T"}}]}), encoding="utf-8")
            result = join_nfhl_point_responses(root / "groundwater.json", root)
        station = result["stations"][0]
        self.assertEqual(station["flood_zone"], "AE")
        self.assertTrue(station["is_special_flood_hazard_area"])

    def test_polygon_context_classifies_cell_center_without_extrapolating_depth(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            nisar = root / "nisar.json"
            overlay = root / "overlay.json"
            nisar.write_text(json.dumps({"cells": [
                {"cell_id": "inside", "longitude": -95.30, "latitude": 29.70},
                {"cell_id": "outside", "longitude": -95.10, "latitude": 29.70},
            ]}), encoding="utf-8")
            overlay.write_text(json.dumps({"source_layer": "FEMA NFHL", "features": [{
                "properties": {"OBJECTID": 1, "FLD_ZONE": "AE", "ZONE_SUBTY": None, "SFHA_TF": "T"},
                "geometry": {"type": "Polygon", "coordinates": [[[-95.4, 29.6], [-95.2, 29.6], [-95.2, 29.8], [-95.4, 29.8], [-95.4, 29.6]]]},
            }]}), encoding="utf-8")
            result = classify_cell_centers(nisar, overlay)
            self.assertTrue(result["cells"][0]["flood_exposed"])
            self.assertEqual(result["cells"][0]["flood_zone"], "AE")
            self.assertIsNone(result["cells"][1]["flood_exposed"])
            self.assertIn("not a cell-area percentage", result["limitations"][0])

    def test_cell_without_matching_polygon_is_unknown_not_unexposed(self):
        # MASTER B8: a flood null is never coerced to exposed or not exposed.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "nisar.json").write_text(json.dumps({"cells": [{"cell_id": "gap", "longitude": -95.0, "latitude": 29.0}]}), encoding="utf-8")
            (root / "overlay.json").write_text(json.dumps({"features": []}), encoding="utf-8")
            cell = classify_cell_centers(root / "nisar.json", root / "overlay.json")["cells"][0]
        self.assertIsNone(cell["flood_exposed"])
        self.assertIsNone(cell["flood_zone"])
        self.assertEqual(cell["matching_polygon_count"], 0)

    def test_non_sfha_polygon_is_not_exposed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "nisar.json").write_text(json.dumps({"cells": [{"cell_id": "x", "longitude": -95.30, "latitude": 29.70}]}), encoding="utf-8")
            (root / "overlay.json").write_text(json.dumps({"features": [{
                "properties": {"FLD_ZONE": "X", "ZONE_SUBTY": "AREA OF MINIMAL FLOOD HAZARD", "SFHA_TF": "F"},
                "geometry": {"type": "Polygon", "coordinates": [[[-95.4, 29.6], [-95.2, 29.6], [-95.2, 29.8], [-95.4, 29.8], [-95.4, 29.6]]]},
            }]}), encoding="utf-8")
            cell = classify_cell_centers(root / "nisar.json", root / "overlay.json")["cells"][0]
        self.assertIs(cell["flood_exposed"], False)
        self.assertEqual(cell["flood_zone"], "X")

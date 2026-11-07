import json
import tempfile
import unittest
from pathlib import Path

from backend.ingestion.fema import join_nfhl_point_responses


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

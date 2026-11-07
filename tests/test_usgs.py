import json
import tempfile
import unittest
from pathlib import Path

from backend.ingestion.usgs import import_groundwater_daily


class UsgsIngestionTests(unittest.TestCase):
    def test_depth_change_sign_is_explicit(self):
        payload = {"value": {"timeSeries": [{
            "sourceInfo": {"siteName": "Example well", "siteCode": [{"value": "123"}], "geoLocation": {"geogLocation": {"longitude": -95.0, "latitude": 29.5}}},
            "variable": {"variableCode": [{"value": "72019"}], "variableName": "Depth to water level", "unit": {"unitCode": "ft"}},
            "values": [{"value": [{"dateTime": "2025-01-01", "value": "10.0"}, {"dateTime": "2025-02-01", "value": "12.5"}]}],
        }]}}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "usgs.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            result = import_groundwater_daily(path)
        self.assertEqual(result["series"][0]["depth_change_ft"], 2.5)
        self.assertIn("deeper", result["sign_convention"])

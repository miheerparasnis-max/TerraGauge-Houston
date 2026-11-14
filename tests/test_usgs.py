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


class UsgsNoDataTests(unittest.TestCase):
    def test_no_data_value_is_not_a_water_level(self):
        payload = {"value": {"timeSeries": [{
            "sourceInfo": {"siteName": "Example well", "siteCode": [{"value": "123"}], "geoLocation": {"geogLocation": {"longitude": -95.0, "latitude": 29.5}}},
            "variable": {"variableCode": [{"value": "72019"}], "unit": {"unitCode": "ft"}, "noDataValue": -999999.0},
            "values": [{"value": [{"dateTime": "2025-01-01", "value": "10.0"}, {"dateTime": "2025-02-01", "value": "11.0"}, {"dateTime": "2025-03-01", "value": "-999999"}]}],
        }]}}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "usgs.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            result = import_groundwater_daily(path)
        self.assertEqual(result["series"][0]["depth_change_ft"], 1.0)
        self.assertEqual(result["series"][0]["last_observation"]["time"], "2025-02-01")


if __name__ == "__main__":
    unittest.main()

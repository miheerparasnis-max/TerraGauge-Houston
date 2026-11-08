import tempfile
import unittest
from pathlib import Path

from backend.ingestion.compaction import import_extensometer_csv


class ExtensometerTests(unittest.TestCase):
    def test_explicit_mapping_preserves_station_change(self):
        content = "site,lon,lat,day,compaction\nE-1,-95.2,29.7,2024-01-01,1.2\nE-1,-95.2,29.7,2025-01-01,1.7\n"
        mapping = {"station_id": "site", "longitude": "lon", "latitude": "lat", "date": "day", "cumulative_compaction": "compaction"}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "extenso.csv"
            path.write_text(content, encoding="utf-8")
            result = import_extensometer_csv(path, mapping)
        station = result["stations"][0]
        self.assertEqual(station["observation_count"], 2)
        self.assertAlmostEqual(station["cumulative_compaction_change"], 0.5)
        self.assertIn("not a citywide map", result["limitations"][0])

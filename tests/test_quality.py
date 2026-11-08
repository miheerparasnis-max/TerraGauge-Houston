import unittest

from backend.ingestion.quality import validate_pair_artifact


class PairIntegrityTests(unittest.TestCase):
    def test_accepts_structurally_valid_pair(self):
        artifact = {
            "artifact_type": "nisar_gunw_pair_cells",
            "parameters": {"acquisition_dates": ["2026-01-01", "2026-01-13"], "bounding_box": [-96, 29, -95, 30]},
            "source_processing_corrections": {"/flag": True},
            "cells": [{"cell_id": "one", "longitude": -95.5, "latitude": 29.5, "in_main_connected_component": True}],
        }
        import json
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "pair.json"
            path.write_text(json.dumps(artifact), encoding="utf-8")
            self.assertTrue(validate_pair_artifact(path)["pass"])

    def test_rejects_duplicate_cells(self):
        import json
        import tempfile
        from pathlib import Path
        artifact = {"artifact_type": "nisar_gunw_pair_cells", "parameters": {"acquisition_dates": ["2026-01-01", "2026-01-13"], "bounding_box": [-96, 29, -95, 30]}, "source_processing_corrections": {}, "cells": [{"cell_id": "one", "longitude": -95.5, "latitude": 29.5}, {"cell_id": "one", "longitude": -95.5, "latitude": 29.5}]}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "pair.json"
            path.write_text(json.dumps(artifact), encoding="utf-8")
            self.assertFalse(validate_pair_artifact(path)["pass"])

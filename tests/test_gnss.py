import json
import tempfile
import unittest
from pathlib import Path

from backend.ingestion.gnss import groundtruth_report


def write_sessions(root, quality=("fixed", "fixed", "fixed"), stations=("NETP", "NETP", "NETP")):
    sessions = []
    for index, (height, q, station) in enumerate(zip((10.0, 12.0, 11.0), quality, stations), start=1):
        raw = root / f"session-{index}.rtcm"
        rinex = root / f"session-{index}.obs"
        raw.write_bytes(b"raw-observation")
        rinex.write_text("rinex-observation", encoding="utf-8")
        sessions.append({"session_id": f"s{index}", "raw_observation_log": str(raw), "rinex_observation_file": str(rinex), "static_solution_height_mm": height, "session_hours": 2, "antenna_fixed": True, "cors_station": station, "cors_overlap": True, "solution": {"quality": q}})
    manifest = root / "manifest.json"
    manifest.write_text(json.dumps({"sessions": sessions}), encoding="utf-8")
    return manifest


class GroundTruthReportTests(unittest.TestCase):
    def test_pass_requires_real_session_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            report = groundtruth_report(write_sessions(Path(directory)))
            self.assertTrue(report["pass"])
            self.assertGreater(report["vertical_session_scatter_mm"], 0)
            self.assertEqual(report["cors_stations"], ["NETP"])

    def test_float_solution_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            report = groundtruth_report(write_sessions(Path(directory), quality=("fixed", "float", "fixed")))
            self.assertFalse(report["pass"])
            self.assertIsNone(report["vertical_session_scatter_mm"])

    def test_mixed_bases_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertFalse(groundtruth_report(write_sessions(Path(directory), stations=("NETP", "ZHU1", "NETP")))["pass"])

    def test_missing_rinex_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = root / "session.rtcm"
            raw.write_bytes(b"raw-observation")
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({"sessions": [{"session_id": "s1", "raw_observation_log": str(raw), "rinex_observation_file": str(root / "missing.obs"), "static_solution_height_mm": 10, "session_hours": 2, "antenna_fixed": True, "cors_station": "NETP", "cors_overlap": True}]}), encoding="utf-8")
            self.assertFalse(groundtruth_report(manifest)["pass"])

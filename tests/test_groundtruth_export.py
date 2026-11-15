"""The Hardware page's GroundTruth status: stages, and no absolute height or location ever exported."""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("export_web", ROOT / "scripts" / "export_web.py")
export_web = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(export_web)


class GroundTruthExportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.raw = base / "raw"
        self.raw.mkdir()
        self.saved = (export_web.GROUNDTRUTH_RAW, export_web.GROUNDTRUTH_MANIFEST, export_web.GROUNDTRUTH_REPORT, export_web.GROUNDTRUTH_DIAGNOSTICS)
        export_web.GROUNDTRUTH_RAW = self.raw
        export_web.GROUNDTRUTH_MANIFEST = base / "manifest.json"
        export_web.GROUNDTRUTH_REPORT = base / "report.json"
        export_web.GROUNDTRUTH_DIAGNOSTICS = base / "diagnostics.json"

    def tearDown(self):
        export_web.GROUNDTRUTH_RAW, export_web.GROUNDTRUTH_MANIFEST, export_web.GROUNDTRUTH_REPORT, export_web.GROUNDTRUTH_DIAGNOSTICS = self.saved
        self.tmp.cleanup()

    def record(self, n, start):
        (self.raw / f"session{n}.rtcm3").write_bytes(b"\xd3" * 64)
        (self.raw / f"session{n}.start.txt").write_text(f"session{n} start {start}\n", encoding="utf-8")

    def test_nothing_recorded(self):
        self.assertEqual(export_web.groundtruth_meta()["status"], "none")

    def test_recorded_but_not_solved(self):
        for n, t in enumerate(["2026-11-14T17:05:14Z", "2026-11-14T19:13:41Z", "2026-11-14T21:35:07Z"], start=1):
            self.record(n, t)
        gt = export_web.groundtruth_meta()
        self.assertEqual((gt["status"], gt["recorded"], gt["processed"], gt["days"]), ("recorded", 3, 0, 1))

    def test_passed_exports_only_relative_heights(self):
        heights = [-21_345_011.2, -21_345_008.9, -21_345_010.4]
        sessions = [{"session_id": f"session{i}", "static_solution_height_mm": h, "session_hours": 2.0,
                     "window_utc": [f"2026-11-1{i}T17:00:00Z", f"2026-11-1{i}T19:00:00Z"],
                     "solution": {"quality": "fixed", "fixed_epoch_share": 0.9, "sigma_3d_mm": 4.0}} for i, h in enumerate(heights, start=1)]
        export_web.GROUNDTRUTH_MANIFEST.write_text(json.dumps({"sessions": sessions}), encoding="utf-8")
        export_web.GROUNDTRUTH_REPORT.write_text(json.dumps({"pass": True, "vertical_session_scatter_mm": 1.17}), encoding="utf-8")
        gt = export_web.groundtruth_meta()
        self.assertEqual((gt["status"], gt["processed"], gt["days"], gt["scatterMm"]), ("passed", 3, 3, 1.2))
        self.assertAlmostEqual(sum(s["offsetMm"] for s in gt["sessions"]), 0.0, delta=0.15)  # offsets are rounded to 0.1 mm
        text = json.dumps(gt)
        self.assertNotIn("21345", text)  # no absolute height
        for banned in ("lat", "lon", "height_mm", "raw_observation_log"):
            self.assertNotIn(banned, text)

    def test_inconclusive_review_withholds_heights(self):
        sessions = [{"session_id": f"session{i}", "static_solution_height_mm": h, "session_hours": 2.0,
                     "window_utc": ["2026-11-14T17:00:00Z", "2026-11-14T19:00:00Z"],
                     "solution": {"quality": "float", "fixed_epoch_share": 0.1, "sigma_3d_mm": 20.0}} for i, h in enumerate([2732.5, 4581.2, -1060.9], start=1)]
        export_web.GROUNDTRUTH_MANIFEST.write_text(json.dumps({"sessions": sessions, "review": {"status": "inconclusive", "summary": "Too few clean satellites."}}), encoding="utf-8")
        export_web.GROUNDTRUTH_REPORT.write_text(json.dumps({"pass": False, "vertical_session_scatter_mm": None}), encoding="utf-8")
        gt = export_web.groundtruth_meta()
        self.assertEqual((gt["status"], gt["processed"], gt["scatterMm"], gt["reason"]), ("inconclusive", 3, None, "Too few clean satellites."))
        self.assertTrue(all(s["offsetMm"] is None for s in gt["sessions"]))
        self.assertNotIn("21345", json.dumps(gt))

    def test_signal_diagnostics_carry_no_position(self):
        export_web.GROUNDTRUTH_DIAGNOSTICS.write_text(json.dumps({"clear_sky_dbhz": 40, "sessions": [{"session_id": "session1", "seconds": 7156, "satellites_tracked": 45, "steady_satellites_median": 7,
            "phase_break_share": 0.27, "gps_l1_cn0_by_direction": {"N": 33, "SW": 48}, "gps_l1_cn0_high": 30}]}), encoding="utf-8")
        gt = export_web.groundtruth_meta()
        self.assertEqual((gt["signal"][0]["steady"], gt["clearSkyDbHz"]), (7, 40))
        for banned in ("lat", "lon", "height"):
            self.assertNotIn(banned, json.dumps(gt))


if __name__ == "__main__":
    unittest.main()

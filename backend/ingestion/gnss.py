"""GroundTruth Node session-manifest validation and pass/fail reporting."""

from __future__ import annotations

import json
from pathlib import Path
from statistics import stdev
from typing import Any


REQUIRED = ("session_id", "raw_observation_log", "rinex_observation_file", "static_solution_height_mm", "session_hours", "antenna_fixed", "cors_station", "cors_overlap")


def groundtruth_report(manifest_path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    sessions = payload.get("sessions")
    if not isinstance(sessions, list):
        raise ValueError("manifest requires a sessions array")
    findings = []
    heights = []
    for session in sessions:
        absent = [key for key in REQUIRED if key not in session]
        raw = Path(session.get("raw_observation_log", ""))
        rinex = Path(session.get("rinex_observation_file", ""))
        raw_ok = raw.is_file() and raw.stat().st_size > 0
        rinex_ok = rinex.is_file() and rinex.stat().st_size > 0
        static_height = session.get("static_solution_height_mm")
        static_ok = isinstance(static_height, (int, float)) and not isinstance(static_height, bool)
        if static_ok:
            heights.append(float(static_height))
        findings.append({"session_id": session.get("session_id"), "missing_fields": absent, "raw_log_nonempty": raw_ok, "rinex_nonempty": rinex_ok, "static_solution_present": static_ok, "antenna_fixed": session.get("antenna_fixed") is True, "cors_station": session.get("cors_station"), "cors_overlap": session.get("cors_overlap") is True})
    passes = len(sessions) >= 3 and len(heights) == len(sessions) and all(not item["missing_fields"] and item["raw_log_nonempty"] and item["rinex_nonempty"] and item["static_solution_present"] and item["antenna_fixed"] and item["cors_overlap"] for item in findings)
    return {"artifact_type": "groundtruth_node_report", "pass": passes, "sessions": findings, "session_count": len(sessions), "vertical_session_scatter_mm": stdev(heights) if passes else None, "claim": "Stationary receiver repeatability only; this result does not measure subsidence." if passes else "Logging prototype only; do not report a detectability result.", "required_cors_station": "NETP", "limitations": ["A pass requires three or more fixed-antenna sessions, non-empty raw and RINEX files, overlapping CORS data, and static solutions."]}


def write_groundtruth_report(manifest_path: str | Path, output_path: str | Path) -> None:
    Path(output_path).write_text(json.dumps(groundtruth_report(manifest_path), indent=2), encoding="utf-8")

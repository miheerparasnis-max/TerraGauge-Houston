"""Structural validation for compact NISAR pair artifacts before downstream joins."""

from __future__ import annotations

import json
from math import isfinite
from pathlib import Path
from typing import Any

from .corrections import validate_correction_record


def validate_pair_artifact(input_path: str | Path) -> dict[str, Any]:
    """Return an auditable pass/fail report; never silently repair source data."""
    artifact = json.loads(Path(input_path).read_text(encoding="utf-8"))
    findings: list[str] = []
    cells = artifact.get("cells")
    if artifact.get("artifact_type") != "nisar_gunw_pair_cells":
        findings.append("artifact_type is not nisar_gunw_pair_cells")
    if not isinstance(cells, list) or not cells:
        findings.append("cells must be a non-empty array")
        cells = []
    parameters = artifact.get("parameters", {})
    dates = parameters.get("acquisition_dates", []) if isinstance(parameters, dict) else []
    if not isinstance(dates, list) or len(dates) != 2 or not all(isinstance(item, str) and len(item) >= 10 for item in dates) or (len(dates) == 2 and dates[0] >= dates[1]):
        findings.append("acquisition_dates must contain two chronological ISO dates")
    bbox = parameters.get("bounding_box") if isinstance(parameters, dict) else None
    if not isinstance(bbox, list) or len(bbox) != 4 or not all(isinstance(item, (int, float)) for item in bbox):
        findings.append("a four-value WGS84 bounding_box is required for a compact study artifact")
        bbox = None
    ids = [row.get("cell_id") for row in cells if isinstance(row, dict)]
    if len(ids) != len(cells) or len(set(ids)) != len(ids):
        findings.append("cells must have unique string cell_id values")
    main_count = 0
    for row in cells:
        if not isinstance(row, dict):
            continue
        lon, lat = row.get("longitude"), row.get("latitude")
        if isinstance(lon, bool) or isinstance(lat, bool) or not isinstance(lon, (int, float)) or not isinstance(lat, (int, float)) or not isfinite(lon) or not isfinite(lat) or not (-180 <= lon <= 180 and -90 <= lat <= 90):
            findings.append("at least one cell has invalid longitude/latitude")
            break
        if bbox is not None and not (bbox[0] <= lon <= bbox[2] and bbox[1] <= lat <= bbox[3]):
            findings.append("at least one cell lies outside the declared study bounding box")
            break
        main_count += int(row.get("in_main_connected_component") is True)
    corrections = artifact.get("source_processing_corrections")
    if not isinstance(corrections, dict):
        findings.append("source processing-correction flags are missing")
    applied = artifact.get("applied_corrections")
    findings.extend(f"applied_corrections: {finding}" for finding in validate_correction_record(applied))
    return {
        "artifact_type": "terragauge_nisar_pair_integrity_report",
        "input_artifact": str(input_path),
        "pass": not findings,
        "finding_count": len(findings),
        "findings": findings,
        "cell_count": len(cells),
        "main_connected_component_cell_count": main_count,
        "correction_flag_count": len(corrections) if isinstance(corrections, dict) else 0,
        "applied_corrections": applied if isinstance(applied, dict) else None,
        "claim": "Structural validation only; passing does not establish ground motion, a stable reference region, or a temporal rate.",
    }


def write_pair_integrity_report(input_path: str | Path, output_path: str | Path) -> None:
    Path(output_path).write_text(json.dumps(validate_pair_artifact(input_path), indent=2), encoding="utf-8")

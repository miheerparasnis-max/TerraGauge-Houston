"""Conservative temporal-network inversion for referenced GUNW pair artifacts."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any
import json

import numpy as np


def _day(value: str) -> date:
    return date.fromisoformat(value[:10])


def _reference(pair: dict[str, Any], reference_cell_id: str) -> dict[str, dict[str, Any]]:
    reference = next((item for item in pair["cells"] if item["cell_id"] == reference_cell_id), None)
    if reference is None or reference.get("pair_los_displacement_mm") is None:
        raise ValueError(f"Reference cell {reference_cell_id!r} is absent or invalid")
    value = float(reference["pair_los_displacement_mm"])
    return {
        item["cell_id"]: {**item, "pair_los_displacement_mm": None if item.get("pair_los_displacement_mm") is None else float(item["pair_los_displacement_mm"]) - value}
        for item in pair["cells"]
    }


def invert_gunw_network(pair_artifacts: list[dict[str, Any]], reference_cell_id: str) -> dict[str, Any]:
    """Produce LOS rates only for a connected, redundant network with 5+ dates.

    Input pair displacements are referenced to the same stable cell. The result
    remains a lower-bound product because atmospheric covariance is not modeled.
    """
    if len(pair_artifacts) < 3:
        raise ValueError("at least three pair artifacts are required")
    edges: list[tuple[str, str, dict[str, dict[str, Any]]]] = []
    for artifact in pair_artifacts:
        dates = artifact.get("parameters", {}).get("acquisition_dates")
        if not isinstance(dates, (list, tuple)) or len(dates) != 2:
            raise ValueError("each pair artifact needs two acquisition_dates")
        start, end = str(dates[0]), str(dates[1])
        if "unknown" in start or "unknown" in end:
            raise ValueError("replace unknown acquisition dates before inversion")
        edges.append((start, end, _reference(artifact, reference_cell_id)))
    dates = sorted({value for start, end, _ in edges for value in (start, end)}, key=_day)
    if len(dates) < 5:
        raise ValueError("at least five acquisition dates are required before an empirical rate is emitted")
    positions = {value: offset for offset, value in enumerate(dates)}
    cell_ids = sorted({cell_id for _, _, records in edges for cell_id in records})
    outputs: list[dict[str, Any]] = []
    for cell_id in cell_ids:
        observations = []
        exemplar = None
        for start, end, records in edges:
            record = records.get(cell_id)
            if record is not None and record.get("pair_los_displacement_mm") is not None:
                exemplar = record
                observations.append((start, end, float(record["pair_los_displacement_mm"]), record))
        if exemplar is None:
            continue
        matrix, vector = [], []
        for start, end, displacement, _ in observations:
            row = np.zeros(len(dates) - 1)
            if positions[start] > 0:
                row[positions[start] - 1] = -1.0
            if positions[end] > 0:
                row[positions[end] - 1] = 1.0
            matrix.append(row)
            vector.append(displacement)
        design, values = np.asarray(matrix), np.asarray(vector)
        rank = int(np.linalg.matrix_rank(design))
        adequate = rank == len(dates) - 1 and len(observations) - (len(dates) - 1) >= 2
        result: dict[str, Any] = {
            "cell_id": cell_id,
            "longitude": exemplar["longitude"],
            "latitude": exemplar["latitude"],
            "coherence_median": float(np.median([record.get("coherence_median", np.nan) for _, _, _, record in observations])),
            "valid_fraction": float(np.mean([record.get("valid_fraction", 0.0) for _, _, _, record in observations])),
            "in_main_connected_component": all(bool(record.get("in_main_connected_component")) for _, _, _, record in observations),
            "observation_count": len(dates),
            "temporal_network_adequate": adequate,
            "source_status": "source_derived",
        }
        if adequate:
            unknown_history, residuals, _, _ = np.linalg.lstsq(design, values, rcond=None)
            history = np.concatenate(([0.0], unknown_history))
            years = np.array([(_day(item) - _day(dates[0])).days / 365.25 for item in dates])
            slope, _ = np.polyfit(years, history, 1)
            degrees_of_freedom = len(values) - rank
            sigma = float(np.sqrt(np.sum(residuals) / degrees_of_freedom)) if residuals.size and degrees_of_freedom > 0 else None
            intervals = np.diff(sorted((_day(item) - _day(dates[0])).days for item in dates))
            result.update({"los_rate_mm_year": float(slope), "epoch_sigma_mm": sigma, "interval_days": float(np.median(intervals)), "history_mm": {item: float(value) for item, value in zip(dates, history)}})
        else:
            result.update({"los_rate_mm_year": None, "epoch_sigma_mm": None, "interval_days": None})
        outputs.append(result)
    return {
        "artifact_type": "nisar_gunw_temporal_network",
        "reference_cell_id": reference_cell_id,
        "acquisition_dates": dates,
        "limitations": ["Pairs are referenced to the declared stable cell.", "Rates require five dates and two redundant edges.", "Residual scatter does not model atmospheric covariance."],
        "cells": outputs,
    }


def invert_files(input_paths: list[str], output_path: str, reference_cell_id: str) -> None:
    artifacts = [json.loads(Path(path).read_text(encoding="utf-8")) for path in input_paths]
    Path(output_path).write_text(json.dumps(invert_gunw_network(artifacts, reference_cell_id), indent=2), encoding="utf-8")

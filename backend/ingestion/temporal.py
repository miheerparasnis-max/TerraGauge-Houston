"""Conservative temporal-network inversion for referenced GUNW pair artifacts."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any
import json

import numpy as np


def _day(value: str) -> date:
    return date.fromisoformat(value[:10])


def _network_edges(pair_artifacts: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Read chronological, date-normalized graph edges from pair artifacts."""
    edges: list[dict[str, str]] = []
    for artifact in pair_artifacts:
        dates = artifact.get("parameters", {}).get("acquisition_dates")
        if not isinstance(dates, (list, tuple)) or len(dates) != 2:
            raise ValueError("each pair artifact needs two acquisition_dates")
        start, end = str(dates[0])[:10], str(dates[1])[:10]
        if "unknown" in start or "unknown" in end:
            raise ValueError("replace unknown acquisition dates before temporal diagnosis")
        if _day(start) >= _day(end):
            raise ValueError("each pair artifact needs two chronological acquisition_dates")
        edges.append({"reference_date": start, "secondary_date": end})
    return edges


def _component_count(dates: list[str], edges: list[dict[str, str]]) -> int:
    """Count date-graph components without assuming the inputs are connected."""
    neighbors = {item: set() for item in dates}
    for edge in edges:
        start, end = edge["reference_date"], edge["secondary_date"]
        neighbors[start].add(end)
        neighbors[end].add(start)
    visited: set[str] = set()
    components = 0
    for root in dates:
        if root in visited:
            continue
        components += 1
        frontier = [root]
        visited.add(root)
        while frontier:
            current = frontier.pop()
            for neighbor in neighbors[current]:
                if neighbor not in visited:
                    visited.add(neighbor)
                    frontier.append(neighbor)
    return components


def diagnose_gunw_network(pair_artifacts: list[dict[str, Any]]) -> dict[str, Any]:
    """Describe whether the input graph can support a rate before selecting a reference.

    This is intentionally separate from inversion: graph redundancy is an
    objective data-completeness check, while reference-region choice requires
    scientific review.
    """
    edges = _network_edges(pair_artifacts)
    dates = sorted({item for edge in edges for item in edge.values()}, key=_day)
    unique_edge_keys = {(edge["reference_date"], edge["secondary_date"]) for edge in edges}
    unique_edges = [
        {"reference_date": start, "secondary_date": end}
        for start, end in sorted(unique_edge_keys, key=lambda edge: (_day(edge[0]), _day(edge[1])))
    ]
    component_count = _component_count(dates, unique_edges)
    independent_edges_needed = max(0, len(dates) - component_count)
    redundant_edges = max(0, len(unique_edges) - independent_edges_needed)
    duplicate_pair_edge_count = len(edges) - len(unique_edges)
    if component_count != 1:
        rate_status = "withheld_disconnected_network"
        next_requirement = "Add valid pairs that connect every acquisition date into one same-track network before selecting a reference region or fitting a rate."
    elif duplicate_pair_edge_count:
        rate_status = "withheld_duplicate_pair_edges"
        next_requirement = "Remove duplicate acquisition-pair artifacts and add at least two distinct same-track cross-pairs or repeat pairs before inversion."
    elif len(dates) < 5:
        rate_status = "withheld_insufficient_dates"
        next_requirement = "Add valid same-track acquisitions until the network contains at least five dates, then add independent loop-closure edges before inversion."
    elif redundant_edges < 2:
        rate_status = "withheld_insufficient_redundancy"
        next_requirement = "Add at least two valid same-track cross-pairs or repeat pairs before emitting a temporal LOS rate; select and document a stable reference region before inversion."
    else:
        rate_status = "eligible_for_reference_review_and_inversion"
        next_requirement = "Document a science-reviewed stable reference region, then invert the network with covariance and residual checks."
    return {
        "artifact_type": "nisar_gunw_temporal_network_diagnostic",
        "acquisition_dates": dates,
        "pair_edges": edges,
        "date_count": len(dates),
        "pair_count": len(edges),
        "unique_pair_count": len(unique_edges),
        "duplicate_pair_edge_count": duplicate_pair_edge_count,
        "connected_component_count": component_count,
        "independent_edges_needed_for_connectivity": independent_edges_needed,
        "redundant_edges": redundant_edges,
        "minimum_redundant_edges_for_rate": 2,
        "rate_status": rate_status,
        "next_requirement": next_requirement,
        "limitations": ["A connected chain can reconstruct relative epochs but has no independent loop closure.", "Duplicate pair artifacts never count as independent loop closures.", "This diagnostic does not select a reference region or estimate motion."],
    }


def _reference(pair: dict[str, Any], reference_cell_id: str) -> dict[str, dict[str, Any]]:
    reference = next((item for item in pair["cells"] if item["cell_id"] == reference_cell_id), None)
    if reference is None or reference.get("pair_los_displacement_mm") is None:
        raise ValueError(f"Reference cell {reference_cell_id!r} is absent or invalid")
    value = float(reference["pair_los_displacement_mm"])
    return {
        item["cell_id"]: {**item, "pair_los_displacement_mm": None if item.get("pair_los_displacement_mm") is None else float(item["pair_los_displacement_mm"]) - value}
        for item in pair["cells"]
    }


def invert_gunw_network(
    pair_artifacts: list[dict[str, Any]],
    reference_cell_id: str,
    *,
    reference_status: str = "provisional_unreviewed",
) -> dict[str, Any]:
    """Produce LOS rates only for a connected, redundant network with 5+ dates.

    Input pair displacements are referenced to the same stable cell. The result
    remains a lower-bound product because atmospheric covariance is not modeled.
    """
    if reference_status != "reviewed":
        raise ValueError("temporal inversion requires reference_status='reviewed'; a candidate reference region is not sufficient")
    diagnostic = diagnose_gunw_network(pair_artifacts)
    if diagnostic["rate_status"] != "eligible_for_reference_review_and_inversion":
        raise ValueError(f"temporal inversion withheld: {diagnostic['rate_status']}")
    edges: list[tuple[str, str, dict[str, dict[str, Any]]]] = []
    for artifact in pair_artifacts:
        dates = artifact.get("parameters", {}).get("acquisition_dates")
        if not isinstance(dates, (list, tuple)) or len(dates) != 2:
            raise ValueError("each pair artifact needs two acquisition_dates")
        start, end = str(dates[0])[:10], str(dates[1])[:10]
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
        "reference_status": reference_status,
        "network_diagnostic": diagnostic,
        "acquisition_dates": dates,
        "limitations": ["Pairs are referenced to the declared stable cell.", "Rates require five dates and two redundant edges.", "Residual scatter does not model atmospheric covariance."],
        "cells": outputs,
    }


def invert_files(input_paths: list[str], output_path: str, reference_cell_id: str, reference_status: str = "provisional_unreviewed") -> None:
    artifacts = [json.loads(Path(path).read_text(encoding="utf-8")) for path in input_paths]
    Path(output_path).write_text(json.dumps(invert_gunw_network(artifacts, reference_cell_id, reference_status=reference_status), indent=2), encoding="utf-8")


def write_network_diagnostic(input_paths: list[str], output_path: str) -> None:
    artifacts = [json.loads(Path(path).read_text(encoding="utf-8")) for path in input_paths]
    Path(output_path).write_text(json.dumps(diagnose_gunw_network(artifacts), indent=2), encoding="utf-8")

"""Validated JSON fixture/loading adapter for a frontend-independent API."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .model import CellInput, Evidence


class ValidationError(ValueError):
    pass


def _number(value: Any, name: str, allow_none: bool = True) -> float | None:
    if value is None and allow_none:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError(f"{name} must be a number")
    return float(value)


def cell_from_dict(payload: dict[str, Any]) -> CellInput:
    if not isinstance(payload, dict):
        raise ValidationError("cell must be an object")
    cell_id = payload.get("cell_id")
    if not isinstance(cell_id, str) or not cell_id.strip() or len(cell_id) > 80:
        raise ValidationError("cell_id must be a non-empty string of at most 80 characters")
    evidence_data = payload.get("evidence", {})
    if not isinstance(evidence_data, dict):
        raise ValidationError("evidence must be an object")
    dates = evidence_data.get("nisar_acquisition_dates", [])
    if not isinstance(dates, list) or not all(isinstance(item, str) for item in dates):
        raise ValidationError("nisar_acquisition_dates must be a list of strings")
    evidence = Evidence(
        nisar_acquisition_dates=dates,
        opera_rate_mm_year=_number(evidence_data.get("opera_rate_mm_year"), "opera_rate_mm_year"),
        nearest_gps_station=_optional_string(evidence_data.get("nearest_gps_station"), "nearest_gps_station"),
        gps_distance_km=_number(evidence_data.get("gps_distance_km"), "gps_distance_km"),
        gps_projected_rate_mm_year=_number(evidence_data.get("gps_projected_rate_mm_year"), "gps_projected_rate_mm_year"),
        gps_residual_mm_year=_number(evidence_data.get("gps_residual_mm_year"), "gps_residual_mm_year"),
        gps_uncertainty_mm_year=_number(evidence_data.get("gps_uncertainty_mm_year"), "gps_uncertainty_mm_year"),
        usgs_site_id=_optional_string(evidence_data.get("usgs_site_id"), "usgs_site_id"),
        flood_source=_optional_string(evidence_data.get("flood_source"), "flood_source"),
    )
    observations = payload.get("observation_count")
    if observations is not None and (isinstance(observations, bool) or not isinstance(observations, int) or observations < 0):
        raise ValidationError("observation_count must be a non-negative integer")
    for flag in ("in_main_connected_component", "flood_exposed"):
        if not isinstance(payload.get(flag), bool):
            raise ValidationError(f"{flag} must be a boolean")
    return CellInput(
        cell_id=cell_id,
        longitude=_number(payload.get("longitude"), "longitude", allow_none=False),  # type: ignore[arg-type]
        latitude=_number(payload.get("latitude"), "latitude", allow_none=False),  # type: ignore[arg-type]
        los_rate_mm_year=_number(payload.get("los_rate_mm_year"), "los_rate_mm_year"),
        epoch_sigma_mm=_number(payload.get("epoch_sigma_mm"), "epoch_sigma_mm"),
        interval_days=_number(payload.get("interval_days"), "interval_days"),
        observation_count=observations,
        coherence_median=_number(payload.get("coherence_median"), "coherence_median"),
        valid_fraction=_number(payload.get("valid_fraction"), "valid_fraction"),
        in_main_connected_component=payload["in_main_connected_component"],
        flood_exposed=payload["flood_exposed"],
        evidence=evidence,
        source_status=_optional_string(payload.get("source_status"), "source_status") or "source_derived",
    )


def _optional_string(value: Any, name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or len(value) > 200:
        raise ValidationError(f"{name} must be a string of at most 200 characters")
    return value


def load_cells(path: str | Path) -> list[CellInput]:
    with Path(path).open(encoding="utf-8") as stream:
        raw = json.load(stream)
    if not isinstance(raw, dict) or not isinstance(raw.get("cells"), list):
        raise ValidationError("dataset must be an object with a cells array")
    return [cell_from_dict(item) for item in raw["cells"]]

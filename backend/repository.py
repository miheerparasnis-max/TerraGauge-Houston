"""Validated JSON fixture/loading adapter for a frontend-independent API."""

from __future__ import annotations

import json
from datetime import date
from math import isfinite
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
    result = float(value)
    if not isfinite(result):
        raise ValidationError(f"{name} must be finite")
    return result


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
    for value in dates:
        try:
            date.fromisoformat(value[:10])
        except ValueError as error:
            raise ValidationError("nisar_acquisition_dates must begin with ISO dates") from error
    evidence = Evidence(
        nisar_acquisition_dates=dates,
        nearest_gps_station=_optional_string(evidence_data.get("nearest_gps_station"), "nearest_gps_station"),
        gps_distance_km=_number(evidence_data.get("gps_distance_km"), "gps_distance_km"),
        historic_gps_up_mm_year=_number(evidence_data.get("historic_gps_up_mm_year"), "historic_gps_up_mm_year"),
        historic_gps_start_year=_number(evidence_data.get("historic_gps_start_year"), "historic_gps_start_year"),
        historic_gps_end_year=_number(evidence_data.get("historic_gps_end_year"), "historic_gps_end_year"),
        gps_comparison_time_matched=_bool(evidence_data.get("gps_comparison_time_matched", False), "gps_comparison_time_matched"),
        gps_projected_displacement_mm=_number(evidence_data.get("gps_projected_displacement_mm"), "gps_projected_displacement_mm"),
        gps_residual_mm=_number(evidence_data.get("gps_residual_mm"), "gps_residual_mm"),
        gps_uncertainty_mm=_number(evidence_data.get("gps_uncertainty_mm"), "gps_uncertainty_mm"),
        usgs_site_id=_optional_string(evidence_data.get("usgs_site_id"), "usgs_site_id"),
        usgs_distance_km=_number(evidence_data.get("usgs_distance_km"), "usgs_distance_km"),
        groundwater_depth_change_ft=_number(evidence_data.get("groundwater_depth_change_ft"), "groundwater_depth_change_ft"),
        nearest_extensometer_station=_optional_string(evidence_data.get("nearest_extensometer_station"), "nearest_extensometer_station"),
        extensometer_distance_km=_number(evidence_data.get("extensometer_distance_km"), "extensometer_distance_km"),
        cumulative_compaction_change_ft=_number(evidence_data.get("cumulative_compaction_change_ft"), "cumulative_compaction_change_ft"),
        opera_historic_pair_displacement_mm=_number(evidence_data.get("opera_historic_pair_displacement_mm"), "opera_historic_pair_displacement_mm"),
        opera_historic_valid_fraction=_number(evidence_data.get("opera_historic_valid_fraction"), "opera_historic_valid_fraction"),
        opera_historic_water_fraction=_number(evidence_data.get("opera_historic_water_fraction"), "opera_historic_water_fraction"),
        flood_source=_optional_string(evidence_data.get("flood_source"), "flood_source"),
        flood_zone=_optional_string(evidence_data.get("flood_zone"), "flood_zone"),
    )
    observations = payload.get("observation_count")
    if observations is not None and (isinstance(observations, bool) or not isinstance(observations, int) or observations < 0):
        raise ValidationError("observation_count must be a non-negative integer")
    if not isinstance(payload.get("in_main_connected_component"), bool):
        raise ValidationError("in_main_connected_component must be a boolean")
    flood_exposed = payload.get("flood_exposed")
    if flood_exposed is not None and not isinstance(flood_exposed, bool):
        raise ValidationError("flood_exposed must be a boolean or null")
    longitude = _number(payload.get("longitude"), "longitude", allow_none=False)
    latitude = _number(payload.get("latitude"), "latitude", allow_none=False)
    if not -180 <= longitude <= 180:
        raise ValidationError("longitude must be between -180 and 180")
    if not -90 <= latitude <= 90:
        raise ValidationError("latitude must be between -90 and 90")
    temporal_rate = _number(payload.get("temporal_los_rate_mm_year"), "temporal_los_rate_mm_year")
    temporal_adequate = _bool(payload.get("temporal_network_adequate", False), "temporal_network_adequate")
    if temporal_rate is not None and (not temporal_adequate or observations is None or observations < 5):
        raise ValidationError("temporal_los_rate_mm_year requires an adequate network with at least five observations")
    if temporal_adequate and (observations is None or observations < 5):
        raise ValidationError("temporal_network_adequate requires at least five observations")
    return CellInput(
        cell_id=cell_id,
        longitude=longitude,
        latitude=latitude,
        pair_los_displacement_mm=_number(payload.get("pair_los_displacement_mm"), "pair_los_displacement_mm"),
        reference_scatter_mm=_number(payload.get("reference_scatter_mm"), "reference_scatter_mm"),
        coherence_median=_number(payload.get("coherence_median"), "coherence_median"),
        valid_fraction=_number(payload.get("valid_fraction"), "valid_fraction"),
        in_main_connected_component=payload["in_main_connected_component"],
        flood_exposed=flood_exposed,
        evidence=evidence,
        source_status=_optional_string(payload.get("source_status"), "source_status") or "source_derived",
        temporal_los_rate_mm_year=temporal_rate,
        temporal_network_adequate=temporal_adequate,
        observation_count=observations,
    )


def _optional_string(value: Any, name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or len(value) > 200:
        raise ValidationError(f"{name} must be a string of at most 200 characters")
    return value


def _bool(value: Any, name: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{name} must be a boolean")
    return value


def dataset_status(path: str | Path) -> str | None:
    """Top-level `dataset_status` of a cells file, so clients can see demo data."""
    with Path(path).open(encoding="utf-8") as stream:
        raw = json.load(stream)
    status = raw.get("dataset_status") if isinstance(raw, dict) else None
    return status if isinstance(status, str) else None


def load_cells(path: str | Path) -> list[CellInput]:
    with Path(path).open(encoding="utf-8") as stream:
        raw = json.load(stream)
    if not isinstance(raw, dict) or not isinstance(raw.get("cells"), list):
        raise ValidationError("dataset must be an object with a cells array")
    cells = [cell_from_dict(item) for item in raw["cells"]]
    identifiers = [cell.cell_id for cell in cells]
    if len(set(identifiers)) != len(identifiers):
        raise ValidationError("dataset contains duplicate cell_id values")
    return cells

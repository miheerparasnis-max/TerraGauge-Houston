"""Build one source-derived, frontend-ready Houston evidence dataset."""

from __future__ import annotations

import json
from math import asin, cos, radians, sin, sqrt
from pathlib import Path
from statistics import median
from typing import Any


def _distance_km(longitude_a: float, latitude_a: float, longitude_b: float, latitude_b: float) -> float:
    radius_km = 6371.0088
    latitude_delta = radians(latitude_b - latitude_a)
    longitude_delta = radians(longitude_b - longitude_a)
    value = sin(latitude_delta / 2) ** 2 + cos(radians(latitude_a)) * cos(radians(latitude_b)) * sin(longitude_delta / 2) ** 2
    return 2 * radius_km * asin(sqrt(value))


def _nearest(longitude: float, latitude: float, rows: list[dict[str, Any]], id_key: str) -> tuple[dict[str, Any], float] | tuple[None, None]:
    if not rows:
        return None, None
    row = min(rows, key=lambda item: _distance_km(longitude, latitude, float(item["longitude"]), float(item["latitude"])))
    return row, _distance_km(longitude, latitude, float(row["longitude"]), float(row["latitude"]))


def _robust_scatter(values: list[float]) -> float:
    center = median(values)
    deviations = [abs(value - center) for value in values]
    return 1.4826 * median(deviations)


def build_houston_evidence(nisar_path: str | Path, houstonnet_path: str | Path, groundwater_path: str | Path, fema_path: str | Path, reference_bbox: tuple[float, float, float, float] | None = None, cell_flood_context_path: str | Path | None = None, compaction_path: str | Path | None = None, opera_path: str | Path | None = None, reference_status: str = "provisional_unreviewed", reference_cell_ids: set[str] | None = None) -> dict[str, Any]:
    """Join actual source-derived artifacts without fabricating a cell flood overlay.

    FEMA data currently exists only at USGS monitoring locations. Therefore
    `flood_exposed` remains null for NISAR cells, preserving an honest
    context-only label until a true cell/polygon flood overlay is ingested.
    """
    nisar = json.loads(Path(nisar_path).read_text(encoding="utf-8"))
    houstonnet = json.loads(Path(houstonnet_path).read_text(encoding="utf-8"))
    groundwater = json.loads(Path(groundwater_path).read_text(encoding="utf-8"))
    fema = json.loads(Path(fema_path).read_text(encoding="utf-8"))
    flood_context = json.loads(Path(cell_flood_context_path).read_text(encoding="utf-8")) if cell_flood_context_path else None
    compaction = json.loads(Path(compaction_path).read_text(encoding="utf-8")) if compaction_path else None
    opera = json.loads(Path(opera_path).read_text(encoding="utf-8")) if opera_path else None
    opera_cells = {row["cell_id"]: row for row in opera.get("cells", [])} if opera else {}
    flood_cells = {row["cell_id"]: row for row in flood_context.get("cells", [])} if flood_context else {}
    good = [row for row in nisar["cells"] if row.get("in_main_connected_component") and row.get("coherence_median") is not None and row.get("coherence_median") >= 0.4 and row.get("valid_fraction", 0) >= 0.5 and row.get("pair_los_displacement_mm") is not None]
    if not good:
        raise ValueError("NISAR artifact contains no cells passing the reference quality gate")
    reference_cells = []
    if reference_cell_ids is not None:
        reference_cells = [row for row in good if row["cell_id"] in reference_cell_ids]
        if len(reference_cells) < 3:
            raise ValueError("reference cell set needs at least three quality-controlled cells")
    elif reference_bbox is not None:
        west, south, east, north = reference_bbox
        reference_cells = [row for row in good if west <= float(row["longitude"]) <= east and south <= float(row["latitude"]) <= north]
        if len(reference_cells) < 3:
            raise ValueError("reference region needs at least three quality-controlled cells")
    # InSAR is relative: every cell is re-referenced to the median of the
    # reference region before any threshold is applied. Without this step a
    # constant phase offset across the frame would make every cell look like a
    # "signal" (the raw Houston pair has a frame-wide offset of ~20 mm).
    reference_median = median(float(row["pair_los_displacement_mm"]) for row in reference_cells) if reference_cells else None
    scatter = _robust_scatter([float(row["pair_los_displacement_mm"]) - reference_median for row in reference_cells]) if reference_cells else None
    groundwater_by_site: dict[str, dict[str, Any]] = {}
    for row in groundwater["series"]:
        groundwater_by_site.setdefault(row["site_id"], row)
    fema_by_site = {row["site_id"]: row for row in fema["stations"]}
    groundwater_sites = []
    for site_id, row in groundwater_by_site.items():
        flood = fema_by_site.get(site_id, {})
        groundwater_sites.append({**row, "flood_zone": flood.get("flood_zone"), "flood_source": fema.get("source_layer")})
    cells = []
    for row in nisar["cells"]:
        longitude, latitude = float(row["longitude"]), float(row["latitude"])
        gps, gps_distance = _nearest(longitude, latitude, houstonnet["stations"], "station_id")
        water, water_distance = _nearest(longitude, latitude, groundwater_sites, "site_id")
        extensometer, extensometer_distance = _nearest(longitude, latitude, compaction.get("stations", []) if compaction else [], "station_id")
        historic_opera = opera_cells.get(row["cell_id"])
        evidence = {
            "nisar_acquisition_dates": nisar["parameters"]["acquisition_dates"],
            "nearest_gps_station": gps.get("station_id") if gps else None,
            "gps_distance_km": gps_distance,
            "historic_gps_up_mm_year": gps.get("up_mm_year") if gps else None,
            "historic_gps_start_year": gps.get("start_decimal_year") if gps else None,
            "historic_gps_end_year": gps.get("end_decimal_year") if gps else None,
            "gps_comparison_time_matched": False,
            "usgs_site_id": water.get("site_id") if water else None,
            "usgs_distance_km": water_distance,
            "groundwater_depth_change_ft": water.get("depth_change_ft") if water else None,
            "nearest_extensometer_station": extensometer.get("station_id") if extensometer else None,
            "extensometer_distance_km": extensometer_distance,
            "cumulative_compaction_change_ft": extensometer.get("cumulative_compaction_change") if extensometer else None,
            "opera_historic_pair_displacement_mm": historic_opera.get("opera_pair_displacement_mm") if historic_opera else None,
            "opera_historic_valid_fraction": historic_opera.get("opera_valid_fraction") if historic_opera else None,
            "opera_historic_water_fraction": historic_opera.get("opera_water_fraction") if historic_opera else None,
            "flood_source": flood_context.get("source_layer") if flood_context else (water.get("flood_source") if water else None),
            "flood_zone": flood_cells.get(row["cell_id"], {}).get("flood_zone") if flood_context else (water.get("flood_zone") if water else None),
        }
        cells.append({
            "cell_id": row["cell_id"],
            "longitude": longitude,
            "latitude": latitude,
            "pair_los_displacement_mm": (float(row["pair_los_displacement_mm"]) - reference_median) if (reference_median is not None and row.get("pair_los_displacement_mm") is not None) else row.get("pair_los_displacement_mm"),
            "pair_los_displacement_raw_mm": row.get("pair_los_displacement_mm"),
            "reference_scatter_mm": scatter,
            "coherence_median": row.get("coherence_median"),
            "valid_fraction": row.get("valid_fraction"),
            "in_main_connected_component": bool(row.get("in_main_connected_component")),
            "flood_exposed": flood_cells.get(row["cell_id"], {}).get("flood_exposed") if flood_context else None,
            "evidence": evidence,
            "source_status": "source_derived_context_only" if scatter is None else ("source_derived_provisional_reference" if reference_status != "reviewed" else "source_derived"),
            "temporal_los_rate_mm_year": None,
            "temporal_network_adequate": False,
        })
    return {
        "dataset_status": ("source_derived_pairwise_evidence_provisional_reference_unreviewed" if reference_status != "reviewed" else "source_derived_pairwise_evidence_reviewed_reference") if scatter is not None and flood_context else "source_derived_pairwise_evidence_without_validated_reference_region" if scatter is None and flood_context else "source_derived_context_only_without_validated_reference_region_or_cell_flood_overlay" if scatter is None else "source_derived_context_only_without_cell_flood_overlay",
        "artifact_type": "terragauge_houston_pairwise_evidence_cells",
        "applied_corrections": nisar.get("applied_corrections"),
        "reference_scatter_mm": scatter,
        "reference_median_mm": reference_median,
        "reference_status": reference_status if scatter is not None else None,
        "reference_region_bbox": list(reference_bbox) if reference_bbox is not None and reference_cell_ids is None else None,
        "reference_cell_ids": sorted(row["cell_id"] for row in reference_cells) if reference_cell_ids is not None else None,
        "reference_cell_count": len(reference_cells),
        "reference_scatter_method": "1.4826 times median absolute deviation inside the explicitly supplied, independently justified stable-reference region; this is a planning threshold, not a full atmospheric uncertainty model." if scatter is not None else "Not calculated: a stable reference region has not been independently justified.",
        "limitations": [
            "NISAR data in this artifact is one pairwise LOS observation, not an annual rate.",
            "No pair-signal threshold is applied until an independently justified stable-reference region is supplied.",
            "HoustonNet values are historic context and are not time-matched validation of the NISAR pair.",
            "FEMA classifications are available at USGS monitoring locations only; no cell-level flood overlay is asserted." if not flood_context else "FEMA context is sampled at the aggregated NISAR-cell center and is not flood depth, parcel advice, or a forecast.",
            "OPERA historical values, when present, are a single 2016 pairwise LOS context field; they are not an annual historical trend or a direct validation of NISAR.",
        ],
        "sources": {"nisar": str(nisar_path), "houstonnet": str(houstonnet_path), "groundwater": str(groundwater_path), "fema": str(fema_path), "cell_flood_context": str(cell_flood_context_path) if cell_flood_context_path else None, "compaction": str(compaction_path) if compaction_path else None, "opera_historic_pair": str(opera_path) if opera_path else None},
        "cells": cells,
    }


def write_houston_evidence(nisar_path: str | Path, houstonnet_path: str | Path, groundwater_path: str | Path, fema_path: str | Path, output_path: str | Path, reference_bbox: tuple[float, float, float, float] | None = None, cell_flood_context_path: str | Path | None = None, compaction_path: str | Path | None = None, opera_path: str | Path | None = None, reference_status: str = "provisional_unreviewed") -> None:
    Path(output_path).write_text(json.dumps(build_houston_evidence(nisar_path, houstonnet_path, groundwater_path, fema_path, reference_bbox, cell_flood_context_path, compaction_path, opera_path, reference_status), indent=2), encoding="utf-8")

"""Produce review candidates for, but never automatically certify, a radar reference region."""

from __future__ import annotations

import json
from math import asin, cos, floor, radians, sin, sqrt
from pathlib import Path
from statistics import median
from typing import Any


def _distance_km(lon_a: float, lat_a: float, lon_b: float, lat_b: float) -> float:
    radius = 6371.0088
    d_lat, d_lon = radians(lat_b - lat_a), radians(lon_b - lon_a)
    value = sin(d_lat / 2) ** 2 + cos(radians(lat_a)) * cos(radians(lat_b)) * sin(d_lon / 2) ** 2
    return 2 * radius * asin(sqrt(value))


def build_reference_review_candidates(nisar_path: str | Path, houstonnet_path: str | Path, patch_degrees: float = 0.05) -> dict[str, Any]:
    """Rank low-amplitude, high-quality patches with nearby low-rate GPS context.

    This is a reviewer aid only. A single NISAR pair cannot establish stability;
    no output of this function may be passed as `--reference-bbox` without an
    independent scientific justification recorded by the team.
    """
    nisar = json.loads(Path(nisar_path).read_text(encoding="utf-8"))
    stations = json.loads(Path(houstonnet_path).read_text(encoding="utf-8")).get("stations", [])
    quality = [cell for cell in nisar.get("cells", []) if cell.get("in_main_connected_component") and (cell.get("coherence_median") or 0) >= 0.7 and (cell.get("valid_fraction") or 0) >= 0.8 and cell.get("pair_los_displacement_mm") is not None]
    if not quality:
        raise ValueError("no cells pass the strict reference-candidate quality gate")
    low_motion_limit = sorted(abs(float(cell["pair_los_displacement_mm"])) for cell in quality)[max(0, round((len(quality) - 1) * 0.25))]
    candidate_cells = []
    for cell in quality:
        lon, lat = float(cell["longitude"]), float(cell["latitude"])
        nearby = min(stations, key=lambda station: _distance_km(lon, lat, float(station["longitude"]), float(station["latitude"])), default=None)
        distance = _distance_km(lon, lat, float(nearby["longitude"]), float(nearby["latitude"])) if nearby else None
        historic_up = float(nearby["up_mm_year"]) if nearby and nearby.get("up_mm_year") is not None else None
        if abs(float(cell["pair_los_displacement_mm"])) <= low_motion_limit and distance is not None and distance <= 5 and historic_up is not None and abs(historic_up) <= 2:
            candidate_cells.append({**cell, "nearest_houstonnet_station": nearby["station_id"], "gps_distance_km": distance, "historic_gps_up_mm_year": historic_up})
    patches: dict[tuple[int, int], list[dict[str, Any]]] = {}
    for cell in candidate_cells:
        key = (floor(float(cell["longitude"]) / patch_degrees), floor(float(cell["latitude"]) / patch_degrees))
        patches.setdefault(key, []).append(cell)
    ranked = []
    for key, cells in patches.items():
        if len(cells) < 3:
            continue
        longitudes, latitudes = [float(cell["longitude"]) for cell in cells], [float(cell["latitude"]) for cell in cells]
        ranked.append({
            "review_bbox_wgs84": [min(longitudes), min(latitudes), max(longitudes), max(latitudes)],
            "candidate_cell_count": len(cells),
            "median_abs_pair_los_displacement_mm": median(abs(float(cell["pair_los_displacement_mm"])) for cell in cells),
            "median_coherence": median(float(cell["coherence_median"]) for cell in cells),
            "median_historic_gps_up_mm_year": median(float(cell["historic_gps_up_mm_year"]) for cell in cells),
            "nearest_stations": sorted({cell["nearest_houstonnet_station"] for cell in cells}),
        })
    ranked.sort(key=lambda patch: (-patch["candidate_cell_count"], patch["median_abs_pair_los_displacement_mm"]))
    return {
        "artifact_type": "terragauge_reference_region_review_candidates",
        "strict_quality_cell_count": len(quality),
        "low_motion_quartile_limit_mm": low_motion_limit,
        "candidate_cell_count": len(candidate_cells),
        "review_patches": ranked[:25],
        "decision": "No reference region is certified by this artifact.",
        "required_human_review": ["Confirm absence of local deformation mechanisms and land-use changes.", "Check the candidate across a future same-track NISAR temporal network.", "Document why the region is stable before using it for a threshold."],
    }


def write_reference_review_candidates(nisar_path: str | Path, houstonnet_path: str | Path, output_path: str | Path) -> None:
    Path(output_path).write_text(json.dumps(build_reference_review_candidates(nisar_path, houstonnet_path), indent=2), encoding="utf-8")

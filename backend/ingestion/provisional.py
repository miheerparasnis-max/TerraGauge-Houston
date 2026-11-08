"""Provisional, clearly-labelled processing steps used to make a reviewable map.

Everything here is a documented, reversible transformation of already-derived
artifacts. Outputs carry ``provisional`` flags so the interface can never
present them as team-reviewed science.

Steps
-----
1. ``deramp_pair``: remove a best-fit plane from one NISAR GUNW pair. A 12-day
   L-band pair over Houston contains tens of millimetres of long-wavelength
   ionospheric/atmospheric ramp; real subsidence over 12 days is ~0.5 mm, so a
   frame-wide plane is overwhelmingly noise. The raw value is kept.
2. ``chain_sum``: add consecutive pairs (d12 + d23 + ... = d1N). Intermediate
   acquisition noise cancels, so the sum behaves like one 60-day pair with
   five times the signal of a 12-day pair. It is still not a rate.
3. ``opera_series``: chain historic OPERA DISP-S1 products (each "relative to a
   specified date"), re-reference every product to the same spatial patch,
   and fit a least-squares LOS velocity per cell.
4. ``compare_opera_gps``: approximate check of OPERA LOS velocity against
   HoustonNet vertical rates projected into LOS (vertical-only assumption,
   overlapping but not identical time windows).
"""

from __future__ import annotations

from datetime import date
from math import cos, radians, sqrt
from statistics import median
from typing import Any

PROVISIONAL_NOTE = "Provisional: reference region and processing choices have not yet been reviewed by the team."


def _good_nisar(cell: dict[str, Any], coherence_min: float = 0.4, valid_min: float = 0.5) -> bool:
    return bool(cell.get("in_main_connected_component")) and cell.get("pair_los_displacement_mm") is not None and (cell.get("coherence_median") or 0) >= coherence_min and (cell.get("valid_fraction") or 0) >= valid_min


def _in_bbox(cell: dict[str, Any], bbox: tuple[float, float, float, float] | list[float]) -> bool:
    west, south, east, north = bbox
    return west <= float(cell["longitude"]) <= east and south <= float(cell["latitude"]) <= north


def fit_plane(points: list[tuple[float, float, float]]) -> tuple[float, float, float]:
    """Least-squares z = a + b*x + c*y using normal equations (no numpy needed)."""
    if len(points) < 3:
        raise ValueError("at least three points are required to fit a plane")
    n = float(len(points))
    sx = sum(p[0] for p in points); sy = sum(p[1] for p in points); sz = sum(p[2] for p in points)
    sxx = sum(p[0] * p[0] for p in points); syy = sum(p[1] * p[1] for p in points); sxy = sum(p[0] * p[1] for p in points)
    sxz = sum(p[0] * p[2] for p in points); syz = sum(p[1] * p[2] for p in points)
    matrix = [[n, sx, sy], [sx, sxx, sxy], [sy, sxy, syy]]
    vector = [sz, sxz, syz]

    def det3(m: list[list[float]]) -> float:
        return (m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1]) - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0]) + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0]))

    determinant = det3(matrix)
    if abs(determinant) < 1e-12:
        raise ValueError("points are degenerate for a plane fit")
    solution = []
    for column in range(3):
        replaced = [row[:] for row in matrix]
        for row in range(3):
            replaced[row][column] = vector[row]
        solution.append(det3(replaced) / determinant)
    return solution[0], solution[1], solution[2]


def deramp_pair(artifact: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of a NISAR pair artifact with a best-fit plane removed."""
    good = [cell for cell in artifact["cells"] if _good_nisar(cell)]
    # Centre coordinates to keep the normal equations well conditioned.
    x0 = median(float(c["longitude"]) for c in good); y0 = median(float(c["latitude"]) for c in good)
    a, b, c = fit_plane([(float(cell["longitude"]) - x0, float(cell["latitude"]) - y0, float(cell["pair_los_displacement_mm"])) for cell in good])
    cells = []
    for cell in artifact["cells"]:
        row = dict(cell)
        value = cell.get("pair_los_displacement_mm")
        row["pair_los_displacement_before_deramp_mm"] = value
        if value is not None:
            row["pair_los_displacement_mm"] = float(value) - (a + b * (float(cell["longitude"]) - x0) + c * (float(cell["latitude"]) - y0))
        cells.append(row)
    result = {key: value for key, value in artifact.items() if key != "cells"}
    result["deramp"] = {"method": "least-squares plane in longitude/latitude over quality-passing cells", "fit_cell_count": len(good), "origin": [x0, y0], "coefficients_mm": {"offset": a, "per_degree_longitude": b, "per_degree_latitude": c}, "status": "provisional", "rationale": "Removes long-wavelength ionospheric/atmospheric ramp; over 12 days real subsidence is far smaller than the ramp. Also removes any real signal that is planar across the whole frame."}
    result["cells"] = cells
    return result


def chain_sum(artifacts: list[dict[str, Any]]) -> dict[str, Any]:
    """Sum consecutive NISAR pairs into one cumulative pseudo-pair."""
    ordered = sorted(artifacts, key=lambda item: item["parameters"]["acquisition_dates"][0])
    for previous, current in zip(ordered, ordered[1:]):
        if previous["parameters"]["acquisition_dates"][1] != current["parameters"]["acquisition_dates"][0]:
            raise ValueError("pairs must form a consecutive chain (each secondary date equals the next reference date)")
    by_id = [{cell["cell_id"]: cell for cell in artifact["cells"]} for artifact in ordered]
    cells = []
    for cell in ordered[0]["cells"]:
        members = [lookup.get(cell["cell_id"]) for lookup in by_id]
        complete = all(member is not None and _good_nisar(member) for member in members)
        cells.append({
            "cell_id": cell["cell_id"], "longitude": cell["longitude"], "latitude": cell["latitude"],
            "pair_los_displacement_mm": sum(float(m["pair_los_displacement_mm"]) for m in members) if complete else None,
            "coherence_median": min(float(m["coherence_median"]) for m in members) if complete else None,
            "valid_fraction": min(float(m["valid_fraction"]) for m in members) if complete else 0.0,
            "in_main_connected_component": complete,
            "pairs_used": len(members) if complete else 0,
            "source_status": "source_derived_chain_sum",
        })
    first, last = ordered[0]["parameters"]["acquisition_dates"][0], ordered[-1]["parameters"]["acquisition_dates"][1]
    return {
        "artifact_type": "nisar_gunw_pair_cells",
        "chain_of": [artifact["parameters"]["acquisition_dates"] for artifact in ordered],
        "parameters": {**ordered[0]["parameters"], "acquisition_dates": [first, last]},
        "source_processing_corrections": ordered[0].get("source_processing_corrections"),
        "limitations": [
            f"Sum of {len(ordered)} consecutive pairs = cumulative LOS displacement {first} to {last}; behaves like one longer pair, not a rate.",
            "Coherence and valid fraction are the minimum across member pairs; a cell must pass quality in every pair.",
            "Unwrapping errors in any member pair propagate into the sum.",
        ],
        "status": "provisional",
        "cells": cells,
    }


def _decimal_year(value: str) -> float:
    day = date.fromisoformat(value[:10])
    start = date(day.year, 1, 1)
    return day.year + (day - start).days / ((date(day.year + 1, 1, 1) - start).days)


def opera_series(artifacts: list[dict[str, Any]], reference_bbox: tuple[float, float, float, float] | list[float] | None = None, valid_min: float = 0.5, water_max: float = 0.5, reference_cell_ids: set[str] | None = None) -> dict[str, Any]:
    """Chain OPERA products, re-reference each, and fit LOS velocity per cell."""
    by_reference: dict[str, list[dict[str, Any]]] = {}
    for artifact in artifacts:
        by_reference.setdefault(artifact["parameters"]["reference_date"], []).append(artifact)

    def longest(from_date: str) -> list[dict[str, Any]]:
        best: list[dict[str, Any]] = []
        for product in by_reference.get(from_date, []):
            candidate = [product] + longest(product["parameters"]["secondary_date"])
            if len(candidate) > len(best):
                best = candidate
        return best

    chain = max((longest(start) for start in by_reference), key=len, default=[])
    if len(chain) < 3:
        raise ValueError("fewer than three chained OPERA products")
    lookups, offsets = [], []
    for product in chain:
        lookup = {cell["cell_id"]: cell for cell in product["cells"]}
        reference = [float(c["opera_pair_displacement_mm"]) for c in product["cells"] if c.get("opera_pair_displacement_mm") is not None and (c.get("opera_valid_fraction") or 0) >= valid_min and ((c["cell_id"] in reference_cell_ids) if reference_cell_ids is not None else _in_bbox(c, reference_bbox))]
        if len(reference) < 3:
            raise ValueError(f"reference patch has fewer than three valid OPERA cells in product starting {product['parameters']['reference_date']}")
        lookups.append(lookup); offsets.append(median(reference))
    dates = [chain[0]["parameters"]["reference_date"]] + [product["parameters"]["secondary_date"] for product in chain]
    years = [_decimal_year(value) for value in dates]
    cells = []
    for cell in chain[0]["cells"]:
        members = [lookup.get(cell["cell_id"]) for lookup in lookups]
        ok = all(m is not None and m.get("opera_pair_displacement_mm") is not None and (m.get("opera_valid_fraction") or 0) >= valid_min and (m.get("opera_water_fraction") or 0) <= water_max for m in members)
        if not ok:
            continue
        series = [0.0]
        for member, offset in zip(members, offsets):
            series.append(series[-1] + float(member["opera_pair_displacement_mm"]) - offset)
        mean_t = sum(years) / len(years); mean_d = sum(series) / len(series)
        sxx = sum((t - mean_t) ** 2 for t in years)
        slope = sum((t - mean_t) * (d - mean_d) for t, d in zip(years, series)) / sxx
        intercept = mean_d - slope * mean_t
        residuals = [d - (intercept + slope * t) for t, d in zip(years, series)]
        residual_sd = sqrt(sum(r * r for r in residuals) / (len(series) - 2))
        cells.append({
            "cell_id": cell["cell_id"], "longitude": cell["longitude"], "latitude": cell["latitude"],
            "opera_los_velocity_mm_year": slope,
            "opera_velocity_se_mm_year": residual_sd / sqrt(sxx),
            "opera_residual_sd_mm": residual_sd,
            "opera_cumulative_los_mm": series[-1],
            "opera_series_mm": [round(value, 2) for value in series],
        })
    return {
        "artifact_type": "opera_houston_los_velocity_provisional",
        "status": "provisional",
        "dates": dates,
        "product_count": len(chain),
        "reference_bbox": list(reference_bbox) if reference_bbox is not None else None,
        "reference_cell_ids": sorted(reference_cell_ids) if reference_cell_ids is not None else None,
        "reference_offsets_mm": offsets,
        "method": "Chained OPERA DISP-S1 products (each relative to its own reference date) after subtracting the reference-patch median from every product; ordinary least-squares slope of cumulative LOS displacement vs. time.",
        "limitations": [
            "LOS velocity, not vertical subsidence. Positive = toward the satellite.",
            "Standard error assumes independent residuals; real uncertainty is larger (temporal correlation, seasonal clay motion).",
            "The reference patch is provisional and unreviewed; a moving reference biases every velocity.",
            "A cell is included only if it passes valid-fraction and water checks in every product.",
            PROVISIONAL_NOTE,
        ],
        "cells": cells,
    }


def stable_gps_reference(stations: list[dict[str, Any]], max_abs_up_mm_year: float = 1.0, min_history_years: float = 10.0, min_end_year: float = 2021.0) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Split long-history, near-zero-vertical-rate HoustonNet stations into reference and held-out halves.

    Alternating by sorted station id keeps the split deterministic and spatially mixed.
    Held-out stable stations are never used to define the reference, so the
    later comparison is not circular for them.
    """
    stable = sorted((s for s in stations if s.get("up_mm_year") is not None and abs(float(s["up_mm_year"])) <= max_abs_up_mm_year and (s.get("history_years") or 0) >= min_history_years and (s.get("end_decimal_year") or 0) >= min_end_year), key=lambda s: s["station_id"])
    return stable[0::2], stable[1::2]


def nearest_cell_ids(stations: list[dict[str, Any]], cells: list[dict[str, Any]], max_distance_km: float = 1.0) -> set[str]:
    from .houston import _distance_km

    ids: set[str] = set()
    for station in stations:
        lon, lat = float(station["longitude"]), float(station["latitude"])
        best = min(cells, key=lambda cell: _distance_km(lon, lat, float(cell["longitude"]), float(cell["latitude"])), default=None)
        if best is not None and _distance_km(lon, lat, float(best["longitude"]), float(best["latitude"])) <= max_distance_km:
            ids.add(best["cell_id"])
    return ids


def compare_opera_gps(series: dict[str, Any], stations: list[dict[str, Any]], incidence_deg: float = 38.0, max_distance_km: float = 1.0, min_overlap_start: float = 2016.5, min_history_end: float = 2021.0, exclude_station_ids: set[str] | None = None) -> dict[str, Any]:
    """Approximate agreement check between OPERA LOS velocity and GPS vertical rate."""
    from .houston import _distance_km

    rows = []
    projection = cos(radians(incidence_deg))
    for station in stations:
        if exclude_station_ids and station["station_id"] in exclude_station_ids:
            continue
        if station.get("up_mm_year") is None or (station.get("start_decimal_year") or 9999) > min_overlap_start or (station.get("end_decimal_year") or 0) < min_history_end:
            continue
        lon, lat = float(station["longitude"]), float(station["latitude"])
        best = min(series["cells"], key=lambda cell: _distance_km(lon, lat, float(cell["longitude"]), float(cell["latitude"])), default=None)
        if best is None:
            continue
        distance = _distance_km(lon, lat, float(best["longitude"]), float(best["latitude"]))
        if distance > max_distance_km:
            continue
        gps_los = float(station["up_mm_year"]) * projection
        rows.append({"station_id": station["station_id"], "cell_id": best["cell_id"], "distance_km": distance, "gps_up_mm_year": station["up_mm_year"], "gps_los_approx_mm_year": gps_los, "opera_los_mm_year": best["opera_los_velocity_mm_year"], "residual_mm_year": best["opera_los_velocity_mm_year"] - gps_los})
    stats: dict[str, Any] = {"station_count": len(rows)}
    if len(rows) >= 5:
        xs = [r["gps_los_approx_mm_year"] for r in rows]; ys = [r["opera_los_mm_year"] for r in rows]
        mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
        cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys)); vx = sum((x - mx) ** 2 for x in xs); vy = sum((y - my) ** 2 for y in ys)
        stats["pearson_r"] = cov / sqrt(vx * vy) if vx > 0 and vy > 0 else None
        stats["median_abs_residual_mm_year"] = median(abs(r["residual_mm_year"]) for r in rows)
        stats["median_residual_mm_year"] = median(r["residual_mm_year"] for r in rows)
    return {
        "artifact_type": "opera_vs_houstonnet_approximate_comparison",
        "status": "provisional",
        "incidence_deg_assumed": incidence_deg,
        "method": f"GPS vertical rate × cos(incidence) compared with OPERA LOS velocity at the nearest OPERA cell within {max_distance_km:g} km.",
        "limitations": [
            "Approximate only: ignores horizontal GPS motion, uses one assumed incidence angle, and GPS windows are longer than the OPERA 2016-2021 window.",
            "This is a sanity check of the provisional reference, not a formal validation.",
            "Stations used to define the reference are excluded from this comparison.",
        ],
        "stats": stats,
        "stations": rows,
    }

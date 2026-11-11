"""Plain-language answers built from the OPERA velocity record.

TerraGauge answers three questions for each 1 km cell, all about the past
satellite record (no projections: MASTER claims policy, section 20):

1. Where did the ground move?     ``vertical_rate``
2. How sure are we?               ``confidence``
3. Where should sensors go first? ``priority`` + ``sensor_plan``

Conventions: rates are mm/yr, negative = moved down, relative to the reference
GPS stations. Radar measures along the satellite's line of sight (LOS);
``vertical_rate`` converts with the assumption that the motion is vertical
(it ignores any horizontal movement) and one approximate look angle.
"""

from __future__ import annotations

from math import asin, cos, radians, sin, sqrt
from statistics import median
from typing import Any

INCIDENCE_DEG = 38.0  # approximate Sentinel-1 IW incidence over Houston
STABLE_MM_YEAR = 3.0  # below this a vertical rate is reported as "about stable"
IMPLAUSIBLE_MM_YEAR = 40.0  # faster than any Houston rate on record: treat as a data problem


def distance_km(lon_a: float, lat_a: float, lon_b: float, lat_b: float) -> float:
    d_lat, d_lon = radians(lat_b - lat_a), radians(lon_b - lon_a)
    value = sin(d_lat / 2) ** 2 + cos(radians(lat_a)) * cos(radians(lat_b)) * sin(d_lon / 2) ** 2
    return 2 * 6371.0088 * asin(sqrt(value))


def vertical_rate(los_mm_year: float, incidence_deg: float = INCIDENCE_DEG) -> float:
    return los_mm_year / cos(radians(incidence_deg))


def confidence(*, se_vertical: float, residual_sd_mm: float, gps_difference_mm_year: float | None, neighbor_difference_mm_year: float | None = None) -> tuple[str, list[str]]:
    """High / Medium / Low confidence in a cell's rate, with plain reasons.

    Points: precise fit (+2 if standard error <= 2.5 mm/yr, +1 if <= 5);
    nearby GPS agrees within 3 mm/yr (+1) or disagrees by more than 5 (-1);
    very jumpy record (residual scatter > 18 mm) (-1);
    differs from the median of squares within 3 km by more than 10 mm/yr (-1).
    High >= 3, Medium = 2, Low <= 1.
    """
    score, reasons = 0, []
    if se_vertical <= 2.5:
        score += 2; reasons.append(f"The satellite record fits a steady trend closely (±{se_vertical:.1f} mm/yr).")
    elif se_vertical <= 5.0:
        score += 1; reasons.append(f"The satellite record fits a trend reasonably well (±{se_vertical:.1f} mm/yr).")
    else:
        reasons.append(f"The satellite record is noisy here (±{se_vertical:.1f} mm/yr).")
    if gps_difference_mm_year is None:
        reasons.append("No long-running GPS station within 3 km to cross-check.")
    elif abs(gps_difference_mm_year) <= 3.0:
        score += 1; reasons.append(f"A nearby GPS station agrees within {abs(gps_difference_mm_year):.1f} mm/yr.")
    elif abs(gps_difference_mm_year) > 5.0:
        score -= 1; reasons.append(f"A nearby GPS station disagrees by {abs(gps_difference_mm_year):.1f} mm/yr.")
    else:
        reasons.append(f"A nearby GPS station differs by {abs(gps_difference_mm_year):.1f} mm/yr, a partial match.")
    if residual_sd_mm > 18.0:
        score -= 1; reasons.append("The record jumps around a lot from one measurement to the next.")
    if neighbor_difference_mm_year is not None:
        if abs(neighbor_difference_mm_year) > 10.0:
            score -= 1; reasons.append(f"It differs from the squares around it by {abs(neighbor_difference_mm_year):.0f} mm/yr, which can mean a local glitch.")
        elif abs(neighbor_difference_mm_year) <= 4.0:
            reasons.append("It matches the squares around it.")
    level = "high" if score >= 3 else "medium" if score == 2 else "low"
    return level, reasons


def priority(*, rate_vertical: float | None, significant: bool, level: str | None, flood_zone_sfha: bool, open_water: bool = False, record: str = "the satellite record") -> tuple[str, str]:
    """Return (priority, one-line reason).

    Priority: urgent / high / watch / stable / check (implausible reading) / no_data.
    Reasons describe the past record named by ``record`` (for example "the
    2016-2021 satellite record") and never project forward.
    """
    if rate_vertical is None or open_water:
        return "no_data", "Not enough reliable satellite data here (often trees, fields, or open water)."
    if abs(rate_vertical) > IMPLAUSIBLE_MM_YEAR:
        return "check", f"The reading ({rate_vertical:.0f} mm a year) is faster than anything measured in Houston, so it is probably a data problem."
    if not significant or rate_vertical > -STABLE_MM_YEAR:
        return "stable", f"No clear up-or-down motion beyond measurement noise in {record}."
    sure = level in ("high", "medium")
    if rate_vertical <= -10 and sure:
        return "urgent", f"Moved down about {abs(rate_vertical):.0f} mm a year in {record}, clearly above measurement noise."
    if rate_vertical <= -5 and flood_zone_sfha and sure:
        return "urgent", f"Moved down about {abs(rate_vertical):.0f} mm a year in {record}, inside a FEMA high-risk flood zone."
    if rate_vertical <= -5 and sure:
        return "high", f"Moved down about {abs(rate_vertical):.0f} mm a year in {record}."
    return "watch", f"Possible downward motion of about {abs(rate_vertical):.0f} mm a year in {record}, but the evidence is weaker."


PRIORITY_WEIGHT = {"urgent": 3.0, "high": 2.0, "watch": 1.0}
CONFIDENCE_WEIGHT = {"high": 1.0, "medium": 0.75, "low": 0.4}


def sensor_plan(cells: list[dict[str, Any]], stations: list[dict[str, Any]], count: int = 15, min_separation_km: float = 4.0, covered_km: float = 2.0) -> list[dict[str, Any]]:
    """Pick sensor sites: areas that moved down, far from any GPS station, spread out.

    Uses each cell's ``area_rate`` (median of squares within 3 km) when given,
    so one noisy square can't top the list. Score = area downward speed ×
    priority weight × confidence weight × distance factor (farther from the
    nearest station is better, capped at 8 km) × 1.3 inside a FEMA high-risk
    flood zone. Greedy selection keeps sites ``min_separation_km`` apart.
    """
    scored = []
    for cell in cells:
        if cell["priority"] not in PRIORITY_WEIGHT or cell["gps_km"] is None or cell["gps_km"] <= covered_km:
            continue
        speed = min(0.0, cell.get("area_rate", cell["rate"]))
        score = abs(speed) * PRIORITY_WEIGHT[cell["priority"]] * CONFIDENCE_WEIGHT[cell["confidence"]] * min(cell["gps_km"], 8.0) / 8.0 * (1.3 if cell["sfha"] else 1.0)
        if score > 0:
            scored.append((score, cell))
    scored.sort(key=lambda item: -item[0])
    chosen: list[dict[str, Any]] = []
    for score, cell in scored:
        if all(distance_km(cell["lon"], cell["lat"], c["lon"], c["lat"]) >= min_separation_km for c in chosen):
            chosen.append({**cell, "score": score})
        if len(chosen) >= count:
            break
    for rank, cell in enumerate(chosen, start=1):
        cell["rank"] = rank
    return chosen


def gps_difference(cell_lon: float, cell_lat: float, rate_vertical: float, stations: list[dict[str, Any]], within_km: float = 3.0, min_years: float = 5.0) -> tuple[float | None, str | None, float | None]:
    best = None
    for station in stations:
        if station.get("up_mm_year") is None or (station.get("history_years") or 0) < min_years:
            continue
        d = distance_km(cell_lon, cell_lat, float(station["longitude"]), float(station["latitude"]))
        if d <= within_km and (best is None or d < best[0]):
            best = (d, station)
    if best is None:
        return None, None, None
    return rate_vertical - float(best[1]["up_mm_year"]), best[1]["station_id"], best[0]


def neighborhood_medians(cells: list[dict[str, Any]], radius_km: float = 3.0) -> dict[str, float]:
    """Median rate of the other cells within ``radius_km`` (grid-hashed)."""
    buckets: dict[tuple[int, int], list[dict[str, Any]]] = {}
    size = 0.05
    for cell in cells:
        buckets.setdefault((int(cell["lon"] // size), int(cell["lat"] // size)), []).append(cell)
    out: dict[str, float] = {}
    for cell in cells:
        bx, by = int(cell["lon"] // size), int(cell["lat"] // size)
        near = [o["rate"] for dx in (-1, 0, 1) for dy in (-1, 0, 1) for o in buckets.get((bx + dx, by + dy), []) if o is not cell and distance_km(cell["lon"], cell["lat"], o["lon"], o["lat"]) <= radius_km]
        if len(near) >= 3:
            out[cell["id"]] = median(near)
    return out

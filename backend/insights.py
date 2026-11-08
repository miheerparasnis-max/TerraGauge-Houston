"""Plain-language answers built from the OPERA velocity record.

TerraGauge answers four questions for each 1 km cell:

1. Where is the ground moving?   ``vertical_rate``
2. How sure are we?               ``confidence``
3. Where is it heading?           ``backtest`` + ``project``
4. Where should sensors go first? ``priority`` + ``sensor_plan``

Conventions: rates are mm/yr, negative = sinking. Radar measures along the
satellite's line of sight (LOS); ``vertical_rate`` converts with the
assumption that Houston's motion is mostly vertical (true for subsidence, but
it ignores any horizontal movement).
"""

from __future__ import annotations

from datetime import date
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


def decimal_year(value: str) -> float:
    day = date.fromisoformat(value[:10])
    start = date(day.year, 1, 1)
    return day.year + (day - start).days / (date(day.year + 1, 1, 1) - start).days


def _slope(times: list[float], values: list[float]) -> float:
    mt, mv = sum(times) / len(times), sum(values) / len(values)
    sxx = sum((t - mt) ** 2 for t in times)
    return sum((t - mt) * (v - mv) for t, v in zip(times, values)) / sxx


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


def backtest(cells: list[dict[str, Any]], dates: list[str], split_date: str) -> dict[str, Any]:
    """Can a rate measured before ``split_date`` predict the rate after it?

    Compares three forecasts of each cell's later rate: the earlier rate
    (persistence), a damped earlier rate (best single factor 0..1), and zero
    (no motion). Reports median absolute error and correlation. The winning
    damping factor is what ``project`` uses.
    """
    years = [decimal_year(d) for d in dates]
    split = max(i for i, d in enumerate(dates) if d <= split_date)
    if split < 3 or len(dates) - split < 4:
        raise ValueError("each side of the split needs at least four dates")
    before, after = [], []
    for cell in cells:
        series = cell["opera_series_mm"]
        before.append(vertical_rate(_slope(years[: split + 1], series[: split + 1])))
        after.append(vertical_rate(_slope(years[split:], series[split:])))
    mb, ma = sum(before) / len(before), sum(after) / len(after)
    cov = sum((b - mb) * (a - ma) for b, a in zip(before, after))
    vb, va = sum((b - mb) ** 2 for b in before), sum((a - ma) ** 2 for a in after)
    corr = cov / sqrt(vb * va) if vb > 0 and va > 0 else 0.0
    mae = lambda preds: median(abs(a - p) for a, p in zip(after, preds))  # noqa: E731
    candidates = {round(k / 10, 1): mae([b * k / 10 for b in before]) for k in range(0, 11)}
    best_alpha = min(candidates, key=lambda k: (candidates[k], -k))
    fast = [(b, a) for b, a in zip(before, after) if b <= -8]
    return {
        "train": [dates[0], dates[split]],
        "test": [dates[split], dates[-1]],
        "cells": len(before),
        "correlation": corr,
        "mae_persistence_mm_year": candidates[1.0],
        "mae_no_motion_mm_year": candidates[0.0],
        "best_damping": best_alpha,
        "mae_best_mm_year": candidates[best_alpha],
        "fast_cells": len(fast),
        "fast_median_before_mm_year": median(b for b, _ in fast) if fast else None,
        "fast_median_after_mm_year": median(a for _, a in fast) if fast else None,
        # A forecast counts as "tested" only if it is clearly better than
        # assuming no motion (>=10% lower error) and the two periods agree
        # at least moderately (correlation >= 0.3).
        "beats_no_motion": best_alpha > 0 and candidates[best_alpha] <= 0.9 * candidates[0.0] and corr >= 0.3,
    }


def project(rate_vertical: float, se_vertical: float, years_ahead: float, damping: float, model_error_mm_year: float) -> dict[str, float]:
    """Straight-line projection with a widening uncertainty band (about 80%).

    The band combines the cell's own rate error with a citywide model error
    (from the GPS comparison and backtest), both growing with time.
    """
    center = rate_vertical * damping * years_ahead
    spread = 1.28 * sqrt(se_vertical ** 2 + model_error_mm_year ** 2) * years_ahead
    return {"center_mm": center, "low_mm": center - spread, "high_mm": center + spread}


def priority(*, rate_vertical: float | None, significant: bool, level: str | None, flood_zone_sfha: bool, open_water: bool = False) -> tuple[str, str]:
    """Return (priority, one-line reason).

    Priority: urgent / high / watch / stable / check (implausible reading) / no_data.
    """
    if rate_vertical is None or open_water:
        return "no_data", "Not enough reliable satellite data here (often trees, fields, or open water)."
    if abs(rate_vertical) > IMPLAUSIBLE_MM_YEAR:
        return "check", f"The reading ({rate_vertical:.0f} mm a year) is faster than anything measured in Houston, so it is probably a data problem."
    if not significant or rate_vertical > -STABLE_MM_YEAR:
        return "stable", "No clear sinking beyond measurement noise."
    sure = level in ("high", "medium")
    if rate_vertical <= -10 and sure:
        return "urgent", f"Sinking about {abs(rate_vertical):.0f} mm a year, and we're fairly sure."
    if rate_vertical <= -5 and flood_zone_sfha and sure:
        return "urgent", f"Sinking about {abs(rate_vertical):.0f} mm a year inside a FEMA high-risk flood zone."
    if rate_vertical <= -5 and sure:
        return "high", f"Sinking about {abs(rate_vertical):.0f} mm a year."
    return "watch", f"Possible sinking of about {abs(rate_vertical):.0f} mm a year, but the evidence is weaker."


PRIORITY_WEIGHT = {"urgent": 3.0, "high": 2.0, "watch": 1.0}
CONFIDENCE_WEIGHT = {"high": 1.0, "medium": 0.75, "low": 0.4}


def sensor_plan(cells: list[dict[str, Any]], stations: list[dict[str, Any]], count: int = 15, min_separation_km: float = 4.0, covered_km: float = 2.0) -> list[dict[str, Any]]:
    """Pick sensor sites: sinking areas far from any GPS station, spread out.

    Uses each cell's ``area_rate`` (median of squares within 3 km) when given,
    so one noisy square can't top the list. Score = area sinking speed ×
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

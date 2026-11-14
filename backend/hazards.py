"""Natural-hazard views built from the ground-movement record.

None of these predict *when* a disaster happens. They say what the measured
ground does to a hazard if it comes:

* drought  - Houston's clay shrinks in droughts. Squares that dropped most in
  the 2018 and 2023 droughts (beyond their normal trend and season) are the
  ones most likely to crack foundations and break water mains next time.
  Tested: using only pre-2023 data, the 2018 response picked out 2023's
  worst-hit squares (scripts/build_hazards.py reports the score).
* bending  - where the sinking rate changes sharply over ~1 km, the ground
  bends; that strains pipes, roads and slabs and can mark a slipping fault.
  Tested: hotspots in 2016-2021 stayed hotspots in 2021-2026.
* flood    - FEMA's flood zone gives the yearly odds of a big flood; the
  satellite-measured drop since 2016 gives how much deeper the same flood
  already stands. Flood depths are never forecast (D-040).
"""
from __future__ import annotations

import re
from datetime import date
from math import cos, radians
from typing import Any

INCIDENCE_DEG = 38.0
DROUGHT_EPOCHS = ("2018-08-13", "2023-10-04")   # end of the 2018 and 2023 Texas droughts

# FEMA zone -> chance of a flood at least that big in any one year
ZONE_ODDS = {"1pct": 0.01, "0.2pct": 0.002, "levee": 0.002, "minimal": 0.0}


def _decimal_year(value: str) -> float:
    d = date.fromisoformat(value[:10])
    start = date(d.year, 1, 1)
    return d.year + (d - start).days / (date(d.year + 1, 1, 1) - start).days


def _grid_index(cell_id: str) -> tuple[int, int] | None:
    m = re.search(r"(-?\d+)-(-?\d+)$", cell_id)
    return (int(m.group(1)), int(m.group(2))) if m else None


def _seasonal_fit(np, times, series):
    x = times - 2016.0
    design = np.c_[np.ones_like(x), x, np.sin(2 * np.pi * times), np.cos(2 * np.pi * times)]
    coef = np.linalg.lstsq(design, series.T, rcond=None)[0]
    return coef, series - (design @ coef).T


def drought_and_bending(velocity: dict[str, Any], exclude: set[str] | None = None) -> dict[str, dict[str, float]]:
    """Per cell: drought drop (mm, average extra drop in past droughts) and
    bending (mm/yr per km, steepest change in sinking rate to a neighbour)."""
    import numpy as np

    exclude = exclude or set()
    dates = velocity["dates"]
    cells = velocity["cells"]
    times = np.array([_decimal_year(d) for d in dates])
    series = np.array([c["opera_series_mm"] for c in cells], dtype=float) / cos(radians(INCIDENCE_DEG))
    coef, resid = _seasonal_fit(np, times, series)
    rate = coef[1].copy()
    # Bending uses noise-weighted rates (see backend.insights.shrink_to_neighbours)
    # so one noisy square can't fake a sharp bend.
    from backend.insights import shrink_to_neighbours

    dof = max(len(times) - 4, 1)
    slope_se = np.sqrt((resid ** 2).sum(axis=1) / dof) / np.sqrt(((times - times.mean()) ** 2).sum())
    plain = {c["cell_id"]: (float(c["longitude"]), float(c["latitude"]), float(r), float(e)) for c, r, e in zip(cells, rate, slope_se) if abs(r) <= 40}
    weighted = shrink_to_neighbours(plain, floor_mm_year=1.5)
    bend_rate = np.array([weighted.get(c["cell_id"], (r, 0))[0] for c, r in zip(cells, rate)])
    cols = [dates.index(d) for d in DROUGHT_EPOCHS if d in dates]
    drop = resid[:, cols].mean(axis=1) if cols else np.zeros(len(cells))

    ids = [c["cell_id"] for c in cells]
    grid = {_grid_index(cid): n for n, cid in enumerate(ids)}
    usable = np.array([(cid not in exclude) and abs(r) <= 40 for cid, r in zip(ids, rate)])
    out: dict[str, dict[str, float]] = {}
    for n, cid in enumerate(ids):
        ij = _grid_index(cid)
        bend = None
        if usable[n] and ij is not None:
            diffs = [abs(bend_rate[n] - bend_rate[k]) for k in (grid.get((ij[0] + a, ij[1] + b)) for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1))) if k is not None and usable[k]]
            if len(diffs) >= 2:
                bend = float(max(diffs))
        out[cid] = {"drought_drop_mm": float(drop[n]), "bend_mm_year_km": bend, "seasonal_mm": float(np.hypot(coef[2][n], coef[3][n]))}
    return out


def drought_backtest(velocity: dict[str, Any], test_epoch: str = "2023-10-04", train_epoch: str = "2018-08-13") -> dict[str, float]:
    """Pretend it's early 2023: does the 2018 drought response pick out the
    squares that dropped most in the 2023 drought?"""
    import numpy as np

    dates = velocity["dates"]
    times = np.array([_decimal_year(d) for d in dates])
    series = np.array([c["opera_series_mm"] for c in velocity["cells"]], dtype=float) / cos(radians(INCIDENCE_DEG))
    cut = next(i for i, t in enumerate(times) if t >= _decimal_year(test_epoch) - 0.6)
    coef, resid = _seasonal_fit(np, times[:cut], series[:, :cut])
    t = _decimal_year(test_epoch)
    expected = coef[0] + coef[1] * (t - 2016) + coef[2] * np.sin(2 * np.pi * t) + coef[3] * np.cos(2 * np.pi * t)
    actual = series[:, dates.index(test_epoch)] - expected
    score = -resid[:, dates.index(train_epoch)]
    ok = np.abs(coef[1]) <= 40
    flagged = ok & (score >= np.percentile(score[ok], 90))
    worst = actual <= np.percentile(actual[ok], 10)
    ranks = np.argsort(np.argsort(score[ok])) + 1
    w = worst[ok]
    auc = (ranks[w].sum() - w.sum() * (w.sum() + 1) / 2) / (w.sum() * (~w).sum())
    return {
        "flagged_median_drop_mm": float(-np.median(actual[flagged])),
        "others_median_drop_mm": float(-np.median(actual[ok & ~flagged])),
        "flagged_share_in_worst10_pct": float(100 * worst[flagged].mean()),
        "auc": float(auc),
        "cells": int(ok.sum()),
    }


def bending_stability(velocity: dict[str, Any], split: str = "2021-05-05") -> dict[str, float]:
    """Do 2016-2021 bending hotspots stay hotspots in 2021-2026?"""
    import numpy as np

    dates = velocity["dates"]
    k = dates.index(split)
    first = {**velocity, "dates": dates[: k + 1], "cells": [{**c, "opera_series_mm": c["opera_series_mm"][: k + 1]} for c in velocity["cells"]]}
    second = {**velocity, "dates": dates[k:], "cells": [{**c, "opera_series_mm": c["opera_series_mm"][k:]} for c in velocity["cells"]]}
    a, b = drought_and_bending(first), drought_and_bending(second)
    pairs = np.array([(a[c]["bend_mm_year_km"], b[c]["bend_mm_year_km"]) for c in a if a[c]["bend_mm_year_km"] is not None and b[c]["bend_mm_year_km"] is not None])
    top = pairs[:, 0] >= np.percentile(pairs[:, 0], 90)
    return {
        "r": float(np.corrcoef(pairs[:, 0], pairs[:, 1])[0, 1]),
        "hotspot_later_median": float(np.median(pairs[top, 1])),
        "others_later_median": float(np.median(pairs[~top, 1])),
        "cells": int(len(pairs)),
    }


def flood_class(zone: str | None, subtype: str | None) -> str | None:
    if zone in ("A", "AE", "AO", "AH", "VE", "V"):
        return "1pct"
    if zone == "X" and subtype:
        if "0.2 PCT" in subtype or "1 PCT DEPTH" in subtype:
            return "0.2pct"
        if "LEVEE" in subtype:
            return "levee"
    if zone == "X":
        return "minimal"
    return None


def chance_over(annual: float, years: int) -> float:
    return 1 - (1 - annual) ** years


def harvey_check(marks: list[dict[str, Any]], cells: list[dict[str, Any]], zone_of: dict[str, tuple[str | None, str | None]]) -> dict[str, Any]:
    """Where did Hurricane Harvey's surveyed flood marks fall, by flood class?

    Compares each class's share of flood marks with its share of the map, so a
    class with 3x more marks than area flooded 3x more often than average.
    """
    import math

    centers = [(c["cell_id"], c["longitude"], c["latitude"]) for c in cells]
    buckets: dict[tuple[int, int], list[int]] = {}
    for n, (_, lon, lat) in enumerate(centers):
        buckets.setdefault((int(lon // 0.02), int(lat // 0.02)), []).append(n)

    def nearest(lon: float, lat: float) -> str | None:
        best, best_d = None, 0.9
        bx, by = int(lon // 0.02), int(lat // 0.02)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for n in buckets.get((bx + dx, by + dy), []):
                    d = math.hypot((centers[n][1] - lon) * 96.5, (centers[n][2] - lat) * 111.0)
                    if d < best_d:
                        best, best_d = centers[n][0], d
        return best

    area: dict[str, int] = {}
    for cid, _, _ in centers:
        k = flood_class(*zone_of.get(cid, (None, None)))
        if k:
            area[k] = area.get(k, 0) + 1
    hits: dict[str, int] = {}
    for m in marks:
        cid = nearest(m["lon"], m["lat"])
        k = flood_class(*zone_of.get(cid, (None, None))) if cid else None
        if k:
            hits[k] = hits.get(k, 0) + 1
    total_hits, total_area = sum(hits.values()), sum(area.values())
    rows = []
    for k in ("1pct", "0.2pct", "levee", "minimal"):
        if area.get(k):
            mark_share = hits.get(k, 0) / total_hits if total_hits else 0.0
            area_share = area[k] / total_area
            rows.append({"class": k, "marks": hits.get(k, 0), "mark_pct": 100 * mark_share, "area_pct": 100 * area_share, "ratio": mark_share / area_share})
    return {"marks": total_hits, "rows": rows}

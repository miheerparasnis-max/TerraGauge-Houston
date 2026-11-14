"""Export the combined, plain-language TerraGauge dataset for the website.

Run after scripts/build_provisional.py:  python3 scripts/export_web.py

One map, all sources kept scientifically distinct. For each 1 km cell:
- movement: the historical OPERA satellite rate converted to vertical. GPS is
  a separate point-scale comparison and coverage signal; it is never blended
  into a satellite trend from a different time window.
- confidence: High / Medium / Low with reasons (backend.insights.confidence).
- future: deliberately withheld. The held-out test does not support a
  long-range forecast, and the historical reference choice remains unreviewed.
- priority + sensor plan (backend.insights.priority / sensor_plan).
All science logic is in Python; the website only displays these numbers.
"""

from __future__ import annotations

import json
import sys
from math import sqrt
from pathlib import Path
from statistics import median

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.detection import rate_uncertainty_mm_year  # noqa: E402
from backend.insights import (  # noqa: E402
    backtest, confidence, distance_km, gps_difference, neighborhood_medians, priority, sensor_plan, vertical_rate,
)
from backend.model import Thresholds  # noqa: E402

DERIVED = Path("data/derived")
PROV = DERIVED / "provisional"
LAYERS = DERIVED / "nasa_layers"
OUT = Path("web/public/data")


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def r(value, digits=1):
    return None if value is None else round(float(value), digits)


def robust_sd(values: list[float]) -> float:
    center = median(values)
    return 1.4826 * median(abs(v - center) for v in values)


def main() -> None:
    thresholds = Thresholds()
    velocity_files = sorted(PROV.glob("opera_houston_los_velocity_*.json"))
    if not velocity_files:
        raise FileNotFoundError("No OPERA velocity export found; run scripts/build_provisional.py first.")
    opera = load(velocity_files[-1])
    comparison = load(PROV / "opera_vs_houstonnet_comparison.json")
    build = load(PROV / "build_report.json")
    pair = load(PROV / "terragauge_houston_evidence_pair_20251102_20251114.json")
    chain = load(PROV / "terragauge_houston_evidence_chain_20251102_20260101.json")
    stations = load(DERIVED / "houstonnet_2024_summary.json")["stations"]
    extensometers = load(DERIVED / "usgs_houston_extensometer_compaction_2023.json")["stations"]
    wells = load(DERIVED / "usgs_houston_groundwater_2025-01-01_2026-11-07.json")["series"]
    flood = {row["cell_id"]: row for row in load(DERIVED / "fema_nfhl_houston_cell_context_2026-11-07.json")["cells"]}
    opera_cells = {row["cell_id"]: row for row in opera["cells"]}
    nasa = {}
    for name in ("nasadem", "dswx", "dist"):
        path = LAYERS / f"{name}_houston_cells.json"
        if path.is_file():
            artifact = load(path)
            nasa[name] = {"meta": {k: v for k, v in artifact.items() if k != "cells"}, "cells": {row["cell_id"]: row for row in artifact["cells"]}}

    dates = opera["dates"]
    data_start, data_end = dates[0], dates[-1]

    # Noise floor from the reference stations (LOS), as in the decision rules.
    reference_ids = set(opera.get("reference_cell_ids") or [])
    ref_v = [opera_cells[c]["opera_los_velocity_mm_year"] for c in reference_ids if c in opera_cells]
    noise_los = robust_sd(ref_v)
    sig_threshold_vertical = vertical_rate(thresholds.pair_signal_sigma_multiplier * noise_los)

    # Citywide model error: robust spread of OPERA-vs-GPS differences (vertical).
    diffs = [vertical_rate(row["residual_mm_year"]) for row in comparison["stations"]]
    model_error = robust_sd(diffs)

    # Prediction test: split the record in the middle.
    split_date = dates[len(dates) // 2]
    bt = backtest(opera["cells"], dates, split_date)
    damping = bt["best_damping"] if bt["beats_no_motion"] else 1.0

    sat_rates = [{"id": c["cell_id"], "lon": float(c["longitude"]), "lat": float(c["latitude"]), "rate": vertical_rate(c["opera_los_velocity_mm_year"])} for c in opera["cells"] if abs(vertical_rate(c["opera_los_velocity_mm_year"])) <= 40]
    neighbors = neighborhood_medians(sat_rates)
    long_history = [s for s in stations if (s.get("history_years") or 0) >= 10 and s.get("up_mm_year") is not None]
    # Coverage counts any station still reporting (data through 2022 or later).
    active = [s for s in stations if (s.get("end_decimal_year") or 0) >= 2022]
    cells, rows_for_plan = [], []
    counts = {"priority": {}, "confidence": {}}
    for row in pair["cells"]:
        cid, lon, lat = row["cell_id"], float(row["longitude"]), float(row["latitude"])
        ev = row["evidence"]
        op = opera_cells.get(cid)
        f = flood.get(cid, {})
        sfha = f.get("flood_exposed") is True

        # GPS remains a point-scale comparison and coverage source. It is not
        # blended with the 2016–2021 satellite trend because its time window is
        # generally different.
        near = min(long_history, key=lambda s: distance_km(lon, lat, s["longitude"], s["latitude"]))
        near_km = distance_km(lon, lat, near["longitude"], near["latitude"])
        cover = min(active, key=lambda s: distance_km(lon, lat, s["longitude"], s["latitude"]))
        cover_km = distance_km(lon, lat, cover["longitude"], cover["latitude"])
        sources = []
        rate = se = None
        if op:
            rate_sat = vertical_rate(op["opera_los_velocity_mm_year"])
            se_sat = sqrt(vertical_rate(op["opera_velocity_se_mm_year"]) ** 2 + model_error ** 2)
            rate, se = rate_sat, se_sat
            sources.append("satellite")

        if rate is not None:
            if op:
                diff, check_id, check_km = gps_difference(lon, lat, vertical_rate(op["opera_los_velocity_mm_year"]), stations)
                area = neighbors.get(cid)
                level, conf_reasons = confidence(se_vertical=vertical_rate(op["opera_velocity_se_mm_year"]), residual_sd_mm=op["opera_residual_sd_mm"], gps_difference_mm_year=diff, neighbor_difference_mm_year=(vertical_rate(op["opera_los_velocity_mm_year"]) - area) if area is not None else None)
            else:
                diff = check_id = check_km = None
                level, conf_reasons = "low", ["No satellite trend passed the quality checks in this square. Nearby GPS is shown as context, not substituted for a 1 km satellite measurement."]
            significant = abs(rate) >= sig_threshold_vertical and abs(rate) >= 2 * se
            pri, pri_reason = priority(rate_vertical=rate, significant=significant, level=level, flood_zone_sfha=sfha, open_water=f.get("flood_zone") == "OPEN WATER" or (nasa.get("dswx", {}).get("cells", {}).get(cid, {}).get("water_fraction") or 0) > 0.5)
            future = None
        else:
            diff = check_id = check_km = None
            level, conf_reasons, significant, future = None, ["No satellite reading passed the quality checks here, and no GPS station is inside the square."], False, None
            pri, pri_reason = priority(rate_vertical=None, significant=False, level=None, flood_zone_sfha=sfha)

        needs_sensor = pri in ("urgent", "high", "watch") and cover_km > thresholds.gps_nearby_km
        counts["priority"][pri] = counts["priority"].get(pri, 0) + 1
        if level:
            counts["confidence"][level] = counts["confidence"].get(level, 0) + 1
        cell = {
            "id": cid, "lon": r(lon, 5), "lat": r(lat, 5),
            "rate": r(rate), "se": r(se), "src": sources, "sig": significant,
            "conf": level, "confWhy": conf_reasons,
            "pri": pri, "priWhy": pri_reason, "needsSensor": needs_sensor,
            "future": future,
            "series": op["opera_series_mm"] if op else None,
            "gps": {"id": cover["station_id"], "km": r(cover_km, 1), "up": cover["up_mm_year"], "y0": r(cover.get("start_decimal_year"), 0), "y1": r(cover.get("end_decimal_year"), 0)},
            "check": {"id": check_id, "km": r(check_km, 1), "diff": r(diff)} if check_id else None,
            "flood": {"zone": f.get("flood_zone"), "sub": f.get("zone_subtype"), "sfha": sfha},
            "well": {"km": r(ev.get("usgs_distance_km")), "dd": r(ev.get("groundwater_depth_change_ft"), 2)} if ev.get("usgs_site_id") else None,
            "ext": {"km": r(ev.get("extensometer_distance_km")), "c": r(ev.get("cumulative_compaction_change_ft"), 2)} if ev.get("nearest_extensometer_station") else None,
            "nisar": {"d": r(row.get("pair_los_displacement_mm")), "ok": row["in_main_connected_component"] and (row.get("coherence_median") or 0) >= thresholds.coherence_min and (row.get("valid_fraction") or 0) >= thresholds.valid_fraction_min},
        }
        for name, layer in nasa.items():
            value = layer["cells"].get(cid)
            if value:
                cell[name] = {k: r(v, 3) for k, v in value.items() if isinstance(v, (int, float)) and k != "valid_pixels"}
        cells.append(cell)
        if rate is not None and pri in ("urgent", "high", "watch"):
            rows_for_plan.append({"id": cid, "lon": lon, "lat": lat, "rate": rate, "area_rate": neighbors.get(cid, rate), "priority": pri, "confidence": level, "gps_km": cover_km, "sfha": sfha})

    plan = sensor_plan(rows_for_plan, stations, count=15)
    by_id = {c["id"]: c for c in cells}
    sensor_sites = []
    for site in plan:
        c = by_id[site["id"]]
        sensor_sites.append({"rank": site["rank"], "id": site["id"], "lon": r(site["lon"], 5), "lat": r(site["lat"], 5), "rate": c["rate"], "areaRate": r(site["area_rate"]), "conf": c["conf"], "gpsKm": c["gps"]["km"], "sfha": c["flood"]["sfha"], "zone": c["flood"]["zone"], "future2035": None})

    def check(source: dict, days: int) -> dict:
        xs, ys = [], []
        for row in source["cells"]:
            op = opera_cells.get(row["cell_id"])
            if op and row["pair_los_displacement_mm"] is not None and row["in_main_connected_component"] and (row["coherence_median"] or 0) >= 0.4 and (row["valid_fraction"] or 0) >= 0.5:
                xs.append(float(row["pair_los_displacement_mm"])); ys.append(op["opera_los_velocity_mm_year"] * days / 365.25)
        if len(xs) < 2:
            return {"cells": len(xs), "days": days, "noise_mm": None, "signal_mm": None, "r": None, "status": "insufficient_overlap"}
        mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
        sx = sqrt(sum((x - mx) ** 2 for x in xs) / len(xs)); sy = sqrt(sum((y - my) ** 2 for y in ys) / len(ys))
        correlation = None if sx == 0 or sy == 0 else sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (len(xs) * sx * sy)
        return {"cells": len(xs), "days": days, "noise_mm": sx, "signal_mm": sy, "r": correlation, "status": "available" if correlation is not None else "zero_variance"}

    sigma = pair["reference_scatter_mm"]
    detect = []
    for rate_t in (5, 10, 20):
        n = next((k for k in range(3, 5000) if rate_uncertainty_mm_year(sigma, 12, k) <= rate_t / thresholds.detection_sigma), None)
        detect.append({"rate": rate_t, "passes": n, "years": r((n - 1) * 12 / 365.25, 1) if n else None})

    meta = {
        "status": "provisional_unreviewed",
        "record": {"start": data_start, "end": data_end, "dates": dates, "products": opera["product_count"], "extendedThroughOpera2026": data_end >= "2026-01-01"},
        "thresholds": {"stable_mm_year": round(sig_threshold_vertical, 1), "gps_covered_km": thresholds.gps_nearby_km},
        "counts": counts,
        "validation": {"stations": comparison["stats"]["station_count"], "r": comparison["stats"].get("pearson_r"), "typical_diff_mm_year": r(vertical_rate(comparison["stats"]["median_abs_residual_mm_year"]), 1), "points": [{"id": p["station_id"], "gps": r(p["gps_up_mm_year"]), "sat": r(vertical_rate(p["opera_los_mm_year"]))} for p in comparison["stations"]]},
        "forecast": {"mode": "withheld", "reason": "The historical reference region is still unreviewed and the held-out back-test did not support extrapolating the 2016–2021 trend.", "damping": damping, "model_error_mm_year": r(model_error, 2), "base": data_end, "years": [], "backtest": {k: (r(v, 2) if isinstance(v, float) else v) for k, v in bt.items()}},
        "nisar": {"pair": check(pair, 12), "chain": check(chain, 60), "detect": detect, "sigma_mm": r(sigma, 1)},
        "reference": build["reference"],
        "sensors": sensor_sites,
        "nasaLayers": {k: v["meta"].get("source") for k, v in nasa.items()},
    }
    sites = {
        "gps": [{"id": s["station_id"], "lon": s["longitude"], "lat": s["latitude"], "up": s["up_mm_year"], "y0": s["start_decimal_year"], "y1": s["end_decimal_year"]} for s in stations],
        "ext": [{"id": s["station_id"], "name": s.get("station_name"), "lon": s["longitude"], "lat": s["latitude"], "c": s.get("cumulative_compaction_change"), "d0": s["first_observation"]["date"], "d1": s["last_observation"]["date"]} for s in extensometers],
        "wells": [{"id": s["site_id"], "name": s.get("site_name"), "lon": s["longitude"], "lat": s["latitude"], "dd": r(s.get("depth_change_ft"), 2), "t0": s["first_observation"]["time"][:10], "t1": s["last_observation"]["time"][:10]} for s in wells],
    }
    OUT.mkdir(parents=True, exist_ok=True)
    for stale in ("ledger.json",):
        (OUT / stale).unlink(missing_ok=True)
    (OUT / "cells.json").write_text(json.dumps(cells, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    (OUT / "meta.json").write_text(json.dumps(meta, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    (OUT / "sites.json").write_text(json.dumps(sites, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"cells": len(cells), "counts": counts, "stable_threshold": sig_threshold_vertical, "model_error": model_error, "forecast": meta["forecast"]["mode"], "backtest": meta["forecast"]["backtest"], "sensors": [(s["rank"], s["rate"], s["gpsKm"], s["zone"]) for s in sensor_sites]}, indent=1))


if __name__ == "__main__":
    main()

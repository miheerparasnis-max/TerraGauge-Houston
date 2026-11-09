"""Export the combined TerraGauge dataset for the website (one map, four views).

Run after scripts/build_provisional.py and scripts/build_forecast.py:

    python3 scripts/export_web.py

For each 1 km square:
- Movement: OPERA satellite rate (2016-2026) converted to vertical, blended
  with a GPS station's rate when one is within 1 km (inverse-variance).
- Confidence: High / Medium / Low with reasons (backend.insights.confidence).
- Future: the tested ML forecast (backend.forecast) for 2027-2031.
- Priority: the plan's action labels (backend.insights.action_label); the
  numbered sensor pins are the top "Add monitoring here" squares.
- Detectability: how long NISAR (and a permanent GPS station) would need to
  measure this square's rate, shown in each square's card.
All science runs in Python; the website only displays these numbers.
"""

from __future__ import annotations

import json
import sys
from math import cos, radians, sqrt
from pathlib import Path
from statistics import median

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.insights import (  # noqa: E402
    IMPLAUSIBLE_MM_YEAR, action_label, confidence, decimal_year, distance_km, gps_difference, neighborhood_medians, passes_to_detect, vertical_rate,
)
from backend.model import Thresholds  # noqa: E402

DERIVED = Path("data/derived")
PROV = DERIVED / "provisional"
LAYERS = DERIVED / "nasa_layers"
OUT = Path("web/public/data")
GPS_SIGMA_MM_YEAR = 0.5       # assumed uncertainty of a >=10-year HoustonNet rate
GPS_BLEND_KM = 1.0
GPS_DAILY_SIGMA_MM = 4.0      # typical daily vertical scatter of a permanent GPS station (assumption)
SENSOR_COUNT = 15             # permanent GPS stations to suggest
SENSOR_SPACING_KM = 4.0
NODE_COUNT = 30               # low-cost nodes to suggest
NODE_SPACING_KM = 3.0
NODE_DAILY_SIGMA_MM = 10.0    # planning assumption for a low-cost node until our hardware test measures it
NODE_MAX_YEARS = 2.0          # only suggest nodes where they could confirm the sinking within this time
ESTIMATE_RADIUS_KM = 3.0
ESTIMATE_MIN_NEIGHBORS = 4
COS = cos(radians(38.0))


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def r(value, digits=1):
    return None if value is None else round(float(value), digits)


def robust_sd(values: list[float]) -> float:
    center = median(values)
    return 1.4826 * median(abs(v - center) for v in values)


def main() -> None:
    t = Thresholds()
    opera = load(PROV / "opera_houston_los_velocity.json")
    comparison = load(PROV / "opera_vs_houstonnet_comparison.json")
    build = load(PROV / "build_report.json")
    pair = load(PROV / "terragauge_houston_evidence_pair_20251102_20251114.json")
    chain = load(PROV / "terragauge_houston_evidence_chain_20251102_20260101.json")
    ml_path = PROV / "ml_forecast.json"
    ml = load(ml_path) if ml_path.is_file() else None
    stations = load(DERIVED / "houstonnet_2024_summary.json")["stations"]
    extensometers = load(DERIVED / "usgs_houston_extensometer_compaction_2023.json")["stations"]
    wells = load(DERIVED / "usgs_houston_groundwater_2025-01-01_2026-11-07.json")["series"]
    flood = {row["cell_id"]: row for row in load(DERIVED / "fema_nfhl_houston_cell_context_2026-11-07.json")["cells"]}
    opera_cells = {row["cell_id"]: row for row in opera["cells"]}
    ml_cells = {row["cell_id"]: row for row in ml["cell_forecasts"]} if ml and ml["passes"] else {}
    nasa = {}
    for name in ("nasadem", "dswx", "dist"):
        path = LAYERS / f"{name}_houston_cells.json"
        if path.is_file():
            artifact = load(path)
            nasa[name] = {"meta": {k: v for k, v in artifact.items() if k != "cells"}, "cells": {row["cell_id"]: row for row in artifact["cells"]}}

    dates = opera["dates"]
    base_year = decimal_year(dates[-1])
    years = list(range(int(base_year) + 1, int(base_year + (ml["tested_horizon_years"] if ml else 0) + 0.5) + 1)) if ml_cells else []

    reference_ids = set(opera.get("reference_cell_ids") or [])
    noise_los = robust_sd([opera_cells[c]["opera_los_velocity_mm_year"] for c in reference_ids if c in opera_cells])
    stable_vertical = vertical_rate(t.pair_signal_sigma_multiplier * noise_los)
    model_error = robust_sd([vertical_rate(row["residual_mm_year"]) for row in comparison["stations"]])
    nisar_sigma = pair["reference_scatter_mm"]

    sat_rates = [{"id": c["cell_id"], "lon": float(c["longitude"]), "lat": float(c["latitude"]), "rate": vertical_rate(c["opera_los_velocity_mm_year"])} for c in opera["cells"] if abs(vertical_rate(c["opera_los_velocity_mm_year"])) <= IMPLAUSIBLE_MM_YEAR]
    area = neighborhood_medians(sat_rates)
    long_history = [s for s in stations if (s.get("history_years") or 0) >= 10 and s.get("up_mm_year") is not None]
    active = [s for s in stations if (s.get("end_decimal_year") or 0) >= 2022 and s.get("up_mm_year") is not None]

    cells, candidates = [], []
    counts = {"action": {}, "confidence": {}}
    for row in pair["cells"]:
        cid, lon, lat = row["cell_id"], float(row["longitude"]), float(row["latitude"])
        ev = row["evidence"]
        op = opera_cells.get(cid)
        f = flood.get(cid, {})
        sfha = f.get("flood_exposed") is True
        open_water = f.get("flood_zone") == "OPEN WATER" or (nasa.get("dswx", {}).get("cells", {}).get(cid, {}).get("water_fraction") or 0) > 0.5

        blend = min(long_history, key=lambda s: distance_km(lon, lat, s["longitude"], s["latitude"]))
        blend_km = distance_km(lon, lat, blend["longitude"], blend["latitude"])
        cover = min(active, key=lambda s: distance_km(lon, lat, s["longitude"], s["latitude"]))
        cover_km = distance_km(lon, lat, cover["longitude"], cover["latitude"])

        sources, rate, se, sat_los = [], None, None, None
        if op:
            sat_los = op["opera_los_velocity_mm_year"]
            rate = vertical_rate(sat_los)
            se = sqrt(vertical_rate(op["opera_velocity_se_mm_year"]) ** 2 + model_error ** 2)
            sources.append("satellite")
            if blend_km <= GPS_BLEND_KM:
                w_s, w_g = 1 / se ** 2, 1 / GPS_SIGMA_MM_YEAR ** 2
                rate = (rate * w_s + blend["up_mm_year"] * w_g) / (w_s + w_g)
                se = sqrt(1 / (w_s + w_g))
                sources.append("gps")
        elif blend_km <= GPS_BLEND_KM:
            rate, se = float(blend["up_mm_year"]), GPS_SIGMA_MM_YEAR
            sources.append("gps")

        level, conf_why, check = None, [], None
        if rate is not None and op:
            diff, check_id, check_km = gps_difference(lon, lat, vertical_rate(sat_los), stations)
            a = area.get(cid)
            level, conf_why = confidence(se_vertical=vertical_rate(op["opera_velocity_se_mm_year"]), residual_sd_mm=op["opera_residual_sd_mm"], gps_difference_mm_year=diff, neighbor_difference_mm_year=(vertical_rate(sat_los) - a) if a is not None else None, disturbed_share=nasa.get("dist", {}).get("cells", {}).get(cid, {}).get("disturbed_fraction"))
            if "gps" in sources and level != "high":
                level, conf_why = "high", conf_why + ["A GPS station sits inside this square, so its precise reading is blended in."]
            if check_id:
                check = {"id": check_id, "km": r(check_km), "diff": r(diff)}
        elif rate is not None:
            level, conf_why = "high", ["A long-running GPS station sits inside this square."]

        significant = rate is not None and abs(rate) >= stable_vertical and abs(rate) >= 2 * (se or 0)
        sat_vertical = vertical_rate(sat_los) if sat_los is not None else rate
        act, act_why = action_label(rate_vertical=sat_vertical if sat_vertical is not None else None, significant=significant, flood_zone_sfha=sfha, gps_km=cover_km, gps_rate=cover["up_mm_year"], covered_km=t.gps_nearby_km, open_water=open_water)
        if act == "insufficient_data":
            level, conf_why = None, []
        counts["action"][act] = counts["action"].get(act, 0) + 1
        if level:
            counts["confidence"][level] = counts["confidence"].get(level, 0) + 1

        future = None
        fc = ml_cells.get(cid)
        if fc and act != "insufficient_data":
            future = {"rate": r(fc["rate_mm_year"]), "low": r(fc["low_mm_year"]), "high": r(fc["high_mm_year"]), "recent": r(fc["recent_rate_mm_year"]),
                      "by": {str(y): {"c": r(fc["rate_mm_year"] * (y - base_year) / 10), "lo": r(fc["low_mm_year"] * (y - base_year) / 10), "hi": r(fc["high_mm_year"] * (y - base_year) / 10)} for y in years}}

        detect = None
        if rate is not None and act != "insufficient_data" and rate < 0:
            n_nisar = passes_to_detect(rate * COS, nisar_sigma, 12)
            n_gps = passes_to_detect(rate, GPS_DAILY_SIGMA_MM, 1)
            n_node = passes_to_detect(rate, NODE_DAILY_SIGMA_MM, 1, max_passes=4000)
            detect = {"nisarMonths": r((n_nisar - 1) * 12 / 30.44, 0) if n_nisar else None, "gpsWeeks": r((n_gps - 1) / 7, 0) if n_gps else None, "nodeWeeks": r((n_node - 1) / 7, 0) if n_node else None}

        cell = {
            "id": cid, "lon": r(lon, 5), "lat": r(lat, 5),
            "rate": r(rate), "se": r(se), "los": r(sat_los), "src": sources, "sig": significant,
            "conf": level, "confWhy": conf_why,
            "act": act, "actWhy": act_why,
            "future": future, "detect": detect,
            "series": op["opera_series_mm"] if op and act != "insufficient_data" else None,
            "quality": {"periods": op.get("opera_links_used") if op else None, "periodsTotal": opera["product_count"], "fitSe": r(vertical_rate(op["opera_velocity_se_mm_year"])) if op else None,
                        "nisarCoh": r(row.get("coherence_median"), 2), "nisarValid": r(row.get("valid_fraction"), 2), "nisarOk": bool(row["in_main_connected_component"] and (row.get("coherence_median") or 0) >= t.coherence_min and (row.get("valid_fraction") or 0) >= t.valid_fraction_min)},
            "gps": {"id": cover["station_id"], "km": r(cover_km), "up": cover["up_mm_year"], "y0": r(cover.get("start_decimal_year"), 0), "y1": r(cover.get("end_decimal_year"), 0)},
            "check": check,
            "flood": {"zone": f.get("flood_zone"), "sub": f.get("zone_subtype"), "sfha": sfha},
            "well": {"km": r(ev.get("usgs_distance_km")), "dd": r(ev.get("groundwater_depth_change_ft"), 2)} if ev.get("usgs_site_id") else None,
            "ext": {"km": r(ev.get("extensometer_distance_km")), "c": r(ev.get("cumulative_compaction_change_ft"), 2)} if ev.get("nearest_extensometer_station") else None,
        }
        for name, layer in nasa.items():
            value = layer["cells"].get(cid)
            if value:
                cell[name] = {k: r(v, 3) for k, v in value.items() if isinstance(v, (int, float)) and k != "valid_pixels"}
        cells.append(cell)
        if act == "add_monitoring":
            candidates.append({"id": cid, "lon": lon, "lat": lat, "area": area.get(cid, sat_vertical), "rate": rate, "gpsKm": cover_km, "conf": level, "zone": f.get("flood_zone")})

    # Fill gaps: squares without a reliable reading (but not water) get an
    # estimate from measured squares within 3 km (inverse-distance weighting).
    # Tested by hiding measured squares: typical error ~1 mm/yr, 80% within ~3 mm/yr.
    measured = [c for c in cells if "satellite" in c["src"] and c["act"] != "insufficient_data" and c["los"] is not None]
    buckets: dict[tuple[int, int], list[dict]] = {}
    for c in measured:
        buckets.setdefault((int(c["lon"] // 0.05), int(c["lat"] // 0.05)), []).append(c)

    def neighbours(lon: float, lat: float) -> list[tuple[float, dict]]:
        bx, by = int(lon // 0.05), int(lat // 0.05)
        out = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for o in buckets.get((bx + dx, by + dy), []):
                    d = distance_km(lon, lat, o["lon"], o["lat"])
                    if 0.01 < d <= ESTIMATE_RADIUS_KM:
                        out.append((d, o))
        return out

    loo = []
    for c in measured[::3]:
        near = neighbours(c["lon"], c["lat"])
        if len(near) >= ESTIMATE_MIN_NEIGHBORS:
            w = [1 / max(d, 0.5) ** 2 for d, _ in near]
            loo.append(abs(sum(wi * vertical_rate(o["los"]) for wi, (_, o) in zip(w, near)) / sum(w) - vertical_rate(c["los"])))
    loo.sort()
    estimate_error = {"median": loo[len(loo) // 2], "p80": loo[int(len(loo) * 0.8)], "tested": len(loo)}
    estimated = 0
    for c in cells:
        if c["act"] != "insufficient_data" or c["flood"]["zone"] == "OPEN WATER" or (c.get("dswx", {}).get("water_fraction") or 0) > 0.5:
            continue
        near = neighbours(c["lon"], c["lat"])
        if len(near) < ESTIMATE_MIN_NEIGHBORS:
            continue
        w = [1 / max(d, 0.5) ** 2 for d, _ in near]
        est = sum(wi * vertical_rate(o["los"]) for wi, (_, o) in zip(w, near)) / sum(w)
        est_se = estimate_error["p80"] / 1.28
        sig = abs(est) >= stable_vertical and abs(est) >= 2 * est_se
        counts["action"]["insufficient_data"] -= 1
        act, act_why = action_label(rate_vertical=est, significant=sig, flood_zone_sfha=c["flood"]["sfha"], gps_km=c["gps"]["km"], gps_rate=c["gps"]["up"], covered_km=t.gps_nearby_km)
        counts["action"][act] = counts["action"].get(act, 0) + 1
        counts["confidence"]["low"] = counts["confidence"].get("low", 0) + 1
        futures = [(wi, o["future"]) for wi, (_, o) in zip(w, near) if o.get("future")]
        future = None
        if futures:
            sw = sum(wi for wi, _ in futures)
            avg = lambda key: sum(wi * f[key] for wi, f in futures) / sw  # noqa: E731
            fr, lo_, hi_ = avg("rate"), avg("low") - est_se, avg("high") + est_se
            future = {"rate": r(fr), "low": r(lo_), "high": r(hi_), "recent": r(avg("recent")), "by": {str(y): {"c": r(fr * (y - base_year) / 10), "lo": r(lo_ * (y - base_year) / 10), "hi": r(hi_ * (y - base_year) / 10)} for y in years}}
        n_nisar = passes_to_detect(est * COS, nisar_sigma, 12) if est < 0 else None
        n_gps = passes_to_detect(est, GPS_DAILY_SIGMA_MM, 1) if est < 0 else None
        n_node = passes_to_detect(est, NODE_DAILY_SIGMA_MM, 1, max_passes=4000) if est < 0 else None
        c.update({
            "rate": r(est), "se": r(est_se), "src": ["estimated"], "sig": sig, "est": len(near),
            "conf": "low", "confWhy": [f"No direct measurement: estimated from {len(near)} measured squares within {ESTIMATE_RADIUS_KM:g} km.", f"In testing, estimates like this were within {estimate_error['p80']:.1f} mm/yr of the real value 80% of the time."],
            "act": act, "actWhy": act_why + " (Estimated from neighbouring squares.)", "future": future,
            "detect": {"nisarMonths": r((n_nisar - 1) * 12 / 30.44, 0) if n_nisar else None, "gpsWeeks": r((n_gps - 1) / 7, 0) if n_gps else None, "nodeWeeks": r((n_node - 1) / 7, 0) if n_node else None} if est < 0 else None,
        })
        estimated += 1

    # Sensor sites: the "Add monitoring here" squares in the fastest-sinking
    # areas (median of squares within 3 km), kept at least 4 km apart.
    candidates.sort(key=lambda c: c["area"])
    sensors: list[dict] = []
    for c in candidates:
        if all(distance_km(c["lon"], c["lat"], s["lon"], s["lat"]) >= SENSOR_SPACING_KM for s in sensors):
            sensors.append(c)
        if len(sensors) >= SENSOR_COUNT:
            break
    by_id = {c["id"]: c for c in cells}
    for rank, s in enumerate(sensors, start=1):
        by_id[s["id"]]["sensorRank"] = rank
    sensor_out = [{"rank": i + 1, "id": s["id"], "lon": r(s["lon"], 5), "lat": r(s["lat"], 5), "areaRate": r(s["area"]), "rate": r(s["rate"]), "gpsKm": r(s["gpsKm"]), "conf": s["conf"], "zone": s["zone"], "weeks": (by_id[s["id"]].get("detect") or {}).get("gpsWeeks")} for i, s in enumerate(sensors)]

    # Low-cost nodes: cheaper, noisier, so spread wider. Candidates are sinking
    # squares (Add monitoring here or Observe) with no GPS within 2 km, where a
    # node could confirm the sinking within NODE_MAX_YEARS, away from the
    # permanent-station sites and each other.
    node_candidates = []
    for c in cells:
        weeks = (c.get("detect") or {}).get("nodeWeeks")
        if c["act"] in ("add_monitoring", "observe") and c["gps"]["km"] > t.gps_nearby_km and c["rate"] is not None and c["rate"] < 0 and weeks is not None and weeks <= NODE_MAX_YEARS * 52:
            node_candidates.append({"id": c["id"], "lon": c["lon"], "lat": c["lat"], "area": area.get(c["id"], c["rate"]), "rate": c["rate"], "weeks": weeks, "act": c["act"], "zone": c["flood"]["zone"], "est": "estimated" in c["src"]})
    node_candidates.sort(key=lambda c: c["area"])
    nodes: list[dict] = []
    for c in node_candidates:
        if all(distance_km(c["lon"], c["lat"], s["lon"], s["lat"]) >= SENSOR_SPACING_KM for s in sensors) and all(distance_km(c["lon"], c["lat"], n["lon"], n["lat"]) >= NODE_SPACING_KM for n in nodes):
            nodes.append(c)
        if len(nodes) >= NODE_COUNT:
            break
    for rank, n in enumerate(nodes, start=1):
        by_id[n["id"]]["nodeRank"] = rank
    node_out = [{"rank": i + 1, "id": n["id"], "lon": r(n["lon"], 5), "lat": r(n["lat"], 5), "areaRate": r(n["area"]), "weeks": n["weeks"], "act": n["act"], "zone": n["zone"], "est": n["est"]} for i, n in enumerate(nodes)]

    def nisar_check(source: dict, days: int) -> dict:
        xs, ys = [], []
        for row in source["cells"]:
            op = opera_cells.get(row["cell_id"])
            if op and row["pair_los_displacement_mm"] is not None and row["in_main_connected_component"] and (row["coherence_median"] or 0) >= 0.4 and (row["valid_fraction"] or 0) >= 0.5:
                xs.append(float(row["pair_los_displacement_mm"])); ys.append(op["opera_los_velocity_mm_year"] * days / 365.25)
        mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
        sx = sqrt(sum((x - mx) ** 2 for x in xs) / len(xs)); sy = sqrt(sum((y - my) ** 2 for y in ys) / len(ys))
        return {"cells": len(xs), "days": days, "noise_mm": sx, "signal_mm": sy, "r": sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (len(xs) * sx * sy)}

    detect_table = []
    for v in (5, 10, 20):
        n = passes_to_detect(v * COS, nisar_sigma, 12)
        detect_table.append({"rate": v, "passes": n, "years": r((n - 1) * 12 / 365.25, 1) if n else None})

    forecast_meta = None
    if ml:
        forecast_meta = {k: ml[k] for k in ("passes", "train_window", "test_window", "tested_horizon_years", "cells", "best_baseline", "interval_coverage_10_90", "interval_coverage_raw", "model", "features", "feature_importance", "limitations")}
        forecast_meta["scores"] = {name: {k: r(v, 2) for k, v in s.items()} for name, s in ml["scores"].items()}
        forecast_meta["base"] = dates[-1]
        forecast_meta["years"] = years

    meta = {
        "status": "provisional_unreviewed",
        "record": {"start": dates[0], "end": dates[-1], "dates": dates, "products": opera["product_count"]},
        "thresholds": {"stable_mm_year": r(stable_vertical), "gps_covered_km": t.gps_nearby_km, "gps_blend_km": GPS_BLEND_KM, "disagree_mm_year": 5.0, "sensor_spacing_km": SENSOR_SPACING_KM, "incidence_deg": 38, "gps_daily_sigma_mm": GPS_DAILY_SIGMA_MM},
        "counts": counts,
        "validation": {"stations": comparison["stats"]["station_count"], "r": comparison["stats"].get("pearson_r"), "typical_diff_mm_year": r(vertical_rate(comparison["stats"]["median_abs_residual_mm_year"])), "points": [{"id": p["station_id"], "gps": r(p["gps_up_mm_year"]), "sat": r(vertical_rate(p["opera_los_mm_year"]))} for p in comparison["stations"]]},
        "forecast": forecast_meta,
        "nisar": {"pair": nisar_check(pair, 12), "chain": nisar_check(chain, 60), "detect": detect_table, "sigma_mm": r(nisar_sigma)},
        "reference": build["reference"],
        "sensors": sensor_out,
        "nodes": node_out,
        "estimates": {"count": estimated, "radius_km": ESTIMATE_RADIUS_KM, "min_neighbors": ESTIMATE_MIN_NEIGHBORS, "median_error_mm_year": r(estimate_error["median"]), "p80_error_mm_year": r(estimate_error["p80"]), "tested": estimate_error["tested"]},
        "hardware": {"node_daily_sigma_mm": NODE_DAILY_SIGMA_MM, "node_max_years": NODE_MAX_YEARS, "node_spacing_km": NODE_SPACING_KM, "gps_daily_sigma_mm": GPS_DAILY_SIGMA_MM,
                     "node_weeks_10": r((passes_to_detect(-10, NODE_DAILY_SIGMA_MM, 1, max_passes=4000) - 1) / 7, 0), "gps_weeks_10": r((passes_to_detect(-10, GPS_DAILY_SIGMA_MM, 1) - 1) / 7, 0),
                     "node_weeks_5": r((passes_to_detect(-5, NODE_DAILY_SIGMA_MM, 1, max_passes=4000) - 1) / 7, 0), "gps_weeks_5": r((passes_to_detect(-5, GPS_DAILY_SIGMA_MM, 1) - 1) / 7, 0)},
        "nasaLayers": {k: v["meta"].get("source") for k, v in nasa.items()},
    }
    sites = {
        "gps": [{"id": s["station_id"], "lon": s["longitude"], "lat": s["latitude"], "up": s["up_mm_year"], "y0": s["start_decimal_year"], "y1": s["end_decimal_year"]} for s in stations],
        "ext": [{"id": s["station_id"], "name": s.get("station_name"), "lon": s["longitude"], "lat": s["latitude"], "c": s.get("cumulative_compaction_change"), "d0": s["first_observation"]["date"], "d1": s["last_observation"]["date"]} for s in extensometers],
        "wells": [{"id": s["site_id"], "name": s.get("site_name"), "lon": s["longitude"], "lat": s["latitude"], "dd": r(s.get("depth_change_ft"), 2), "t0": s["first_observation"]["time"][:10], "t1": s["last_observation"]["time"][:10]} for s in wells],
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "cells.json").write_text(json.dumps(cells, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    (OUT / "meta.json").write_text(json.dumps(meta, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    (OUT / "sites.json").write_text(json.dumps(sites, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"cells": len(cells), "counts": counts, "stable": stable_vertical, "years": years, "sensors": len(sensor_out), "nodes": [(n["rank"], n["areaRate"], n["weeks"], n["act"], n["est"]) for n in node_out[:8]], "estimates": meta["estimates"], "hardware": meta["hardware"]}, indent=1))


if __name__ == "__main__":
    main()

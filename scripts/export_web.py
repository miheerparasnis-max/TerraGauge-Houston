"""Export the combined TerraGauge dataset for the website (one map, four views).

Run after scripts/build_provisional.py and scripts/build_forecast.py:

    python3 scripts/export_web.py

For each 1 km square:
- Movement: OPERA satellite rate (2016-2026) converted to vertical, blended
  with a GPS station's rate when one is within 1 km (inverse-variance).
- Confidence: High / Medium / Low with reasons (backend.insights.confidence).
- Future: the benchmark-winning trend forecast (backend.forecast.seasonal_area_rates)
  with tested 80% ranges, 2027-2031.
- Priority: the plan's action labels (backend.insights.action_label); the
  numbered sensor pins are the top "Add monitoring here" squares.
- Detectability: how long NISAR (and a permanent GPS station) would need to
  measure this square's rate, shown in each square's card.
Rates are relative to the pre-registered reference GPS stations. Every input and
output is hashed into data/manifests/web_export.json (backend.provenance).
All science runs in Python; the website only displays these numbers.
"""

from __future__ import annotations

import json
import sys
from math import cos, radians, sqrt
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.insights import (  # noqa: E402
    IMPLAUSIBLE_MM_YEAR, action_label, shrink_to_neighbours, confidence, decimal_year, distance_km, gps_difference, neighborhood_medians, passes_to_detect, vertical_rate,
)
from backend.ingestion.station_types import DEEP_SEATED_GNSS, display_gps_rate, is_deep_seated  # noqa: E402
from backend.model import Thresholds  # noqa: E402
from backend.provenance import ProvenanceLog  # noqa: E402
from backend.publish_guard import assert_publishable  # noqa: E402

DERIVED = ROOT / "data" / "derived"
PROV = DERIVED / "provisional"
LAYERS = DERIVED / "nasa_layers"
INVENTORY = ROOT / "data" / "manifests" / "nisar_track062_inventory_20261110.json"
MANIFEST = ROOT / "data" / "manifests" / "web_export.json"
OUT = ROOT / "web" / "public" / "data"
BUILD_COMMAND = "python3 scripts/build_provisional.py"
GPS_SIGMA_MM_YEAR = 0.5       # assumed uncertainty of a >=10-year HoustonNet rate
GPS_BLEND_KM = 1.0
GPS_DAILY_SIGMA_MM = 6.5      # daily vertical scatter of a HoustonNet station: 5-8 mm RMS (Wang et al., 2022, J. Surv. Eng. 148(4))
SENSOR_COUNT = 15             # permanent GPS stations to suggest
SENSOR_SPACING_KM = 4.0
NODE_COUNT = 30               # low-cost nodes to suggest
NODE_SPACING_KM = 3.0
COVER_KM = 6.0                # every "Add monitoring here" square has a suggested site at most this far away
NODE_DAILY_SIGMA_MM = 10.0    # planning assumption for a low-cost node until our hardware test measures it
NODE_MAX_YEARS = 2.0          # only suggest nodes where they could confirm the sinking within this time
ESTIMATE_RADIUS_KM = 3.0
ESTIMATE_MIN_NEIGHBORS = 4
GPS_EST_RADIUS_KM = 10.0      # outside satellite coverage: estimate from GPS stations this close
GPS_EST_MIN_STATIONS = 3
GAP_COUNT = 12                # low-cost "fill the gap" nodes where nothing measures the ground
GAP_SPACING_KM = 6.0
GAP_MIN_GPS_KM = 4.0
COS = cos(radians(38.0))


LOG: ProvenanceLog | None = None


def blend_test(raw: dict, shrunk: dict, gps: list[dict], exclude: set[str], radius_km: float = 3.0) -> dict:
    """Does blending shaky squares with their neighbourhood bring them closer to GPS?

    Every satellite square within ``radius_km`` of a long-history GPS station (not a
    reference station, not deep-seated) is compared with that station's vertical rate,
    before and after blending. Also reports how many squares the blend moves mostly
    toward their neighbourhood (neighbourhood weight above one half)."""
    before, after = [], []
    for cid, (lon, lat, rate, _se) in raw.items():
        if cid not in shrunk:
            continue
        near = [g for g in gps if g["station_id"] not in exclude and not is_deep_seated(g["station_id"]) and distance_km(lon, lat, g["longitude"], g["latitude"]) <= radius_km]
        if not near:
            continue
        g = min(near, key=lambda s: distance_km(lon, lat, s["longitude"], s["latitude"]))
        truth = display_gps_rate(g.get("up_mm_year"))[0]
        before.append(abs(rate - truth)); after.append(abs(shrunk[cid][0] - truth))
    # neighbourhood weight = 1 - own weight / total weight; total weight = 1 / blended se^2
    pulled = sum(1 for cid, (_lo, _la, _rate, se) in raw.items() if cid in shrunk and (1 / max(se, 0.3) ** 2) < (1 / shrunk[cid][1] ** 2) / 2)
    q = lambda xs, p: sorted(xs)[min(len(xs) - 1, int(p * len(xs)))]  # noqa: E731
    return {"squares": len(before), "radius_km": radius_km, "typical_before_mm_year": r(median(before)), "typical_after_mm_year": r(median(after)),
            "worst10_before_mm_year": r(q(before, 0.9)), "worst10_after_mm_year": r(q(after, 0.9)),
            "pulled_share_pct": r(100 * pulled / max(1, len(shrunk)), 0)} if before else None


def load(path: Path) -> dict:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    assert_publishable(payload, str(path))
    if LOG is not None:
        LOG.read(path)
    return payload


def r(value, digits=1):
    return None if value is None else round(float(value), digits)


GROUNDTRUTH_RAW = ROOT / "data" / "raw" / "groundtruth"
GROUNDTRUTH_MANIFEST = ROOT / "data" / "groundtruth_session_manifest.json"
GROUNDTRUTH_REPORT = DERIVED / "groundtruth" / "groundtruth_report.json"
NISAR_NOISE = DERIVED / "nisar_noise_measured.json"
GROUNDTRUTH_DIAGNOSTICS = DERIVED / "groundtruth" / "groundtruth_diagnostics.json"


def groundtruth_meta() -> dict:
    """Status of our fixed-antenna GroundTruth sessions for the Hardware page.

    Stages: "none" (nothing recorded), "recorded" (raw logs exist, not yet solved
    against a NOAA CORS base), "processed" (heights solved, report not passing), "inconclusive"
    (reviewed: the data cannot support a result, heights withheld), "passed"
    (three or more ambiguity-fixed sessions against one base). Only each session's height relative to the
    sessions' average leaves this script: never the absolute height or location.
    This is the receiver's own repeatability, never land motion.
    """
    recorded = []
    for log in sorted(GROUNDTRUTH_RAW.glob("session*.rtcm3")):
        start = log.with_suffix(".start.txt")
        if log.stat().st_size > 0 and start.is_file():
            recorded.append({"id": log.stem, "start": start.read_text(encoding="utf-8").split()[2]})
    out: dict = {"status": "recorded" if recorded else "none", "recorded": len(recorded), "processed": 0,
                 "days": len({x["start"][:10] for x in recorded}), "sessions": [], "pass": False, "scatterMm": None}
    if GROUNDTRUTH_MANIFEST.is_file():
        solved = [s for s in load(GROUNDTRUTH_MANIFEST)["sessions"] if isinstance(s.get("static_solution_height_mm"), (int, float))]
        if solved:
            mean = sum(s["static_solution_height_mm"] for s in solved) / len(solved)
            out["sessions"] = [{
                "id": s["session_id"], "window": s.get("window_utc"), "hours": s.get("session_hours"),
                "offsetMm": r(s["static_solution_height_mm"] - mean), "quality": s.get("solution", {}).get("quality"),
                "fixedShare": s.get("solution", {}).get("fixed_epoch_share"), "sigmaMm": s.get("solution", {}).get("sigma_3d_mm"),
            } for s in solved]
            out["processed"] = len(solved)
            out["recorded"] = max(out["recorded"], len(solved))
            out["days"] = len({(s.get("window_utc") or ["?"])[0][:10] for s in solved}) or out["days"]
            out["status"] = "processed"
    if GROUNDTRUTH_REPORT.is_file() and out["processed"]:
        report = load(GROUNDTRUTH_REPORT)
        out["pass"] = bool(report.get("pass"))
        out["scatterMm"] = r(report.get("vertical_session_scatter_mm"))
        if out["pass"]:
            out["status"] = "passed"
    review = load(GROUNDTRUTH_MANIFEST).get("review", {}) if GROUNDTRUTH_MANIFEST.is_file() else {}
    if not out["pass"] and out["processed"] and review.get("status") == "inconclusive":
        # Heights from an unresolved solution can be metres off: say why, show no height at all.
        out["status"] = "inconclusive"
        out["reason"] = review.get("summary")
        out["scatterMm"] = None
        for x in out["sessions"]:
            x["offsetMm"] = None
        rough = review.get("rough_heights_by_method", {})
        out["roughHeights"] = {"note": rough.get("note"), "methods": [{"label": x["label"], "offsetsM": x["offsets_m"]} for x in rough.get("methods", [])]}
    if GROUNDTRUTH_DIAGNOSTICS.is_file():
        diag = load(GROUNDTRUTH_DIAGNOSTICS)
        out["clearSkyDbHz"] = diag.get("clear_sky_dbhz")
        out["signal"] = [{"id": x["session_id"], "seconds": x["seconds"], "tracked": x["satellites_tracked"], "steady": x["steady_satellites_median"],
                          "breakShare": x["phase_break_share"], "byDirection": x["gps_l1_cn0_by_direction"], "high": x["gps_l1_cn0_high"]} for x in diag["sessions"]]
    return out


def robust_sd(values: list[float]) -> float:
    center = median(values)
    return 1.4826 * median(abs(v - center) for v in values)


def relative(path: Path) -> str:
    return Path(path).resolve().relative_to(ROOT).as_posix()


def main() -> None:
    global LOG
    LOG = ProvenanceLog(ROOT, regenerate={relative(PROV / "terragauge_houston_evidence_pair_20251102_20251114.json"): BUILD_COMMAND, relative(PROV / "terragauge_houston_evidence_chain_20251102_20260101.json"): BUILD_COMMAND})
    t = Thresholds()
    opera = load(PROV / "opera_houston_los_velocity.json")
    comparison = load(PROV / "opera_vs_houstonnet_comparison.json")
    build = load(PROV / "build_report.json")
    pair = load(PROV / "terragauge_houston_evidence_pair_20251102_20251114.json")
    chain = load(PROV / "terragauge_houston_evidence_chain_20251102_20260101.json")
    ml_path = PROV / "ml_forecast.json"
    ml = load(ml_path) if ml_path.is_file() else None
    backtest_path = PROV / "backtest_recent.json"
    backtest = load(backtest_path)["results"] if backtest_path.is_file() else []
    bench_path = PROV / "forecast_benchmark.json"
    bench = load(bench_path) if bench_path.is_file() else None
    from backend.forecast import seasonal_area_rates
    forecast_rates = seasonal_area_rates(opera) if bench else {}
    all_stations = load(DERIVED / "houstonnet_2024_summary.json")["stations"]
    # Deep-seated antennas sit on deep extensometer anchors and do not measure
    # the land surface (Wang et al. 2022): never blend, cross-check, or count
    # them as surface coverage. They still appear on the GPS layer, labelled.
    stations = [s for s in all_stations if not is_deep_seated(s["station_id"])]
    extensometers = load(DERIVED / "usgs_houston_extensometer_compaction_2023.json")["stations"]
    wells = load(DERIVED / "usgs_houston_groundwater_2025-01-01_2026-11-07.json")["series"]
    # Older summaries kept USGS's no-data value (-999999 ft) as a last reading;
    # treat any change that size as unknown rather than a real water level.
    clean_dd = lambda v: None if v is None or abs(float(v)) > 1000 else v  # noqa: E731
    for s_ in wells:
        s_["depth_change_ft"] = clean_dd(s_.get("depth_change_ft"))
    grid_path = PROV / "grid_cells.json"
    if grid_path.is_file():
        # Full 1 km grid (scripts/build_grid.py): every square in the study box,
        # with its FEMA zone sampled at 25 points.
        grid = load(grid_path)["cells"]
        flood = {row["cell_id"]: row for row in grid}
    else:
        grid = None
        flood = {row["cell_id"]: row for row in load(DERIVED / "fema_nfhl_houston_cell_context_2026-11-07.json")["cells"]}
    opera_cells = {row["cell_id"]: row for row in opera["cells"]}
    ml_cells = {row["cell_id"]: row for row in ml["cell_forecasts"]} if ml else {}
    nasa = {}
    for name in ("nasadem", "dswx", "dist"):
        path = LAYERS / f"{name}_houston_cells.json"
        if path.is_file():
            artifact = load(path)
            nasa[name] = {"meta": {k: v for k, v in artifact.items() if k != "cells"}, "cells": {row["cell_id"]: row for row in artifact["cells"]}}

    dates = opera["dates"]
    base_year = decimal_year(dates[-1])
    tested = float(max((b["years_ahead"] for b in bench["bands_80"]), default=0)) if bench else 0.0
    years = list(range(int(base_year) + 1, int(base_year + tested + 0.5) + 1)) if bench else []

    # Forecast = season-aware trend averaged with its 3 km neighbourhood
    # (backend.forecast.seasonal_area_rates), the most accurate method in the
    # walk-forward benchmark (scripts/forecast_benchmark.py). Each year's 80%
    # range = the 80th-percentile error seen that many years ahead in that
    # benchmark, made non-decreasing.
    bands = []
    running = 0.0
    for b in sorted(bench["bands_80"] if bench else [], key=lambda b: b["years_ahead"]):
        running = max(running, b["half_width_cm"] * 10)
        bands.append((float(b["years_ahead"]), running))

    def band_at(h: float) -> float:
        if not bands:
            return 0.0
        if h <= bands[0][0]:
            return bands[0][1] * h / bands[0][0]
        for (h0, b0), (h1, b1) in zip(bands, bands[1:]):
            if h <= h1:
                return b0 + (b1 - b0) * (h - h0) / (h1 - h0)
        return bands[-1][1]

    reference_ids = set(opera.get("reference_cell_ids") or [])
    noise_los = robust_sd([opera_cells[c]["opera_los_velocity_mm_year"] for c in reference_ids if c in opera_cells])
    stable_vertical = vertical_rate(t.pair_signal_sigma_multiplier * noise_los)
    model_error = robust_sd([vertical_rate(row["residual_mm_year"]) for row in comparison["stations"]])
    # NISAR per-pass noise. Measured from the 22-pair archive when available
    # (scripts/measure_nisar_noise.py): it grows with distance from the reference
    # region because the atmosphere decorrelates with distance. Falls back to the
    # scatter inside the reference region of one pair, which understates it.
    nisar_noise = load(NISAR_NOISE) if NISAR_NOISE.is_file() else None
    nisar_sigma = nisar_noise["median_sigma_mm"] if nisar_noise else pair["reference_scatter_mm"]
    noise_curve = sorted((b["median_distance_km"], b["median_sigma_mm"]) for b in (nisar_noise or {}).get("by_distance_from_region_a", []))

    def nisar_sigma_at(lon: float, lat: float) -> float:
        if not noise_curve:
            return nisar_sigma
        d = distance_km(lon, lat, *nisar_noise["region_a_center"])
        if d <= noise_curve[0][0]:
            return noise_curve[0][1]
        for (d0, s0), (d1, s1) in zip(noise_curve, noise_curve[1:]):
            if d <= d1:
                return s0 + (s1 - s0) * (d - d0) / (d1 - d0)
        return noise_curve[-1][1]

    sat_rates = [{"id": c["cell_id"], "lon": float(c["longitude"]), "lat": float(c["latitude"]), "rate": vertical_rate(c["opera_los_velocity_mm_year"])} for c in opera["cells"] if abs(vertical_rate(c["opera_los_velocity_mm_year"])) <= IMPLAUSIBLE_MM_YEAR]
    area = neighborhood_medians(sat_rates)

    # Noise-weighted rates: each square's own rate is combined with the median
    # of satellite squares within 3 km, weighted by how precise each is
    # (backend.insights.shrink_to_neighbours). Precise squares keep their own
    # value; noisy ones (about 1 in 10) are pulled toward their neighbourhood.
    # Weights use each square's own trend-fit error, so clean records keep
    # their local detail. Tested against GPS stations within 3 km (2,584
    # squares, pre-registered reference): typical gap 1.9 -> 1.7 mm/yr,
    # worst 10% 7.6 -> 6.5 mm/yr.
    raw_rates = {c["cell_id"]: (float(c["longitude"]), float(c["latitude"]), vertical_rate(c["opera_los_velocity_mm_year"]),
                                vertical_rate(c["opera_velocity_se_mm_year"]))
                 for c in opera["cells"] if abs(vertical_rate(c["opera_los_velocity_mm_year"])) <= IMPLAUSIBLE_MM_YEAR}
    shrunk = shrink_to_neighbours(raw_rates, floor_mm_year=1.5)
    long_history = [s for s in stations if (s.get("history_years") or 0) >= 10 and display_gps_rate(s.get("up_mm_year"))[0] is not None]
    shrink_test = blend_test(raw_rates, shrunk, long_history, set((opera.get("reference") or {}).get("stations") or []) | {"DEN2", "TMCC"})
    active = [s for s in stations if (s.get("end_decimal_year") or 0) >= 2022 and s.get("up_mm_year") is not None]

    cells, candidates = [], []
    counts = {"action": {}, "confidence": {}}
    pair_rows = {row["cell_id"]: row for row in pair["cells"]}
    universe = [pair_rows.get(g["cell_id"]) or {"cell_id": g["cell_id"], "longitude": g["longitude"], "latitude": g["latitude"], "evidence": {}} for g in grid] if grid else pair["cells"]
    for row in universe:
        cid, lon, lat = row["cell_id"], float(row["longitude"]), float(row["latitude"])
        ev = dict(row["evidence"])
        if not ev.get("usgs_site_id") and wells:
            w = min(wells, key=lambda s: distance_km(lon, lat, s["longitude"], s["latitude"]))
            ev.update(usgs_site_id=w["site_id"], usgs_distance_km=distance_km(lon, lat, w["longitude"], w["latitude"]), groundwater_depth_change_ft=w.get("depth_change_ft"))
        if not ev.get("nearest_extensometer_station") and extensometers:
            x = min(extensometers, key=lambda s: distance_km(lon, lat, s["longitude"], s["latitude"]))
            ev.update(nearest_extensometer_station=x["station_id"], extensometer_distance_km=distance_km(lon, lat, x["longitude"], x["latitude"]), cumulative_compaction_change_ft=x.get("cumulative_compaction_change"))
        op = opera_cells.get(cid)
        f = flood.get(cid, {})
        sfha = f.get("flood_exposed") is True
        open_water = f.get("flood_zone") == "OPEN WATER" or (nasa.get("dswx", {}).get("cells", {}).get(cid, {}).get("water_fraction") or 0) > 0.5

        blend = min(long_history, key=lambda s: distance_km(lon, lat, s["longitude"], s["latitude"]))
        blend_km = distance_km(lon, lat, blend["longitude"], blend["latitude"])
        cover = min(active, key=lambda s: distance_km(lon, lat, s["longitude"], s["latitude"]))
        cover_km = distance_km(lon, lat, cover["longitude"], cover["latitude"])

        sources, rate, se, sat_los, gps_weight, sat_rate = [], None, None, None, 0.0, None
        if op:
            sat_los = op["opera_los_velocity_mm_year"]
            # Weighted rate for the map; the square's own uncertainty for "is it clearly moving?"
            se = sqrt(vertical_rate(op["opera_velocity_se_mm_year"]) ** 2 + model_error ** 2)
            rate = shrunk.get(cid, (vertical_rate(sat_los), se))[0]
            sat_rate = rate
            sources.append("satellite")
            if blend_km <= GPS_BLEND_KM:
                w_s, w_g = 1 / se ** 2, 1 / GPS_SIGMA_MM_YEAR ** 2
                rate = (rate * w_s + blend["up_mm_year"] * w_g) / (w_s + w_g)
                se = sqrt(1 / (w_s + w_g))
                gps_weight = w_g / (w_s + w_g)
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
        sat_vertical = sat_rate if sat_rate is not None else rate
        act, act_why = action_label(rate_vertical=sat_vertical if sat_vertical is not None else None, significant=significant, flood_zone_sfha=sfha, gps_km=cover_km, gps_rate=display_gps_rate(cover["up_mm_year"])[0], covered_km=t.gps_nearby_km, open_water=open_water)
        if "gps" in sources and act != "review_disagreement" and rate is not None:
            # A GPS station inside the square is blended in: label the rate the map shows.
            act, act_why = action_label(rate_vertical=rate, significant=significant, flood_zone_sfha=sfha, gps_km=cover_km, gps_rate=None, covered_km=t.gps_nearby_km, open_water=open_water)
        if act == "insufficient_data":
            level, conf_why = None, []
            if open_water:
                act_why = "Open water: radar can't measure the ground under water."
            elif not op and rate is None:
                act_why = "Outside the area the NASA OPERA satellite product covers, so there's no direct reading."
        counts["action"][act] = counts["action"].get(act, 0) + 1
        if level:
            counts["confidence"][level] = counts["confidence"].get(level, 0) + 1

        future = None
        fc = ml_cells.get(cid)
        if rate is not None and act != "insufficient_data" and years:
            f_rate = rate
            if op and cid in forecast_rates:
                f_rate = forecast_rates[cid] * (1 - gps_weight) + (blend["up_mm_year"] * gps_weight if gps_weight else 0.0)
            by = {}
            for y in years:
                h = y - base_year
                half = band_at(h)
                by[str(y)] = {"c": r(f_rate * h / 10), "lo": r((f_rate * h - half) / 10), "hi": r((f_rate * h + half) / 10)}
            per_year = band_at(tested) / tested
            future = {"rate": r(f_rate), "low": r(f_rate - per_year), "high": r(f_rate + per_year), "recent": r(fc["recent_rate_mm_year"]) if fc else None, "by": by}

        detect = None
        if rate is not None and act != "insufficient_data" and rate < 0:
            n_nisar = passes_to_detect(rate * COS, nisar_sigma_at(lon, lat), 12)
            n_gps = passes_to_detect(rate, GPS_DAILY_SIGMA_MM, 1)
            n_node = passes_to_detect(rate, NODE_DAILY_SIGMA_MM, 1, max_passes=4000)
            detect = {"nisarMonths": r((n_nisar - 1) * 12 / 30.44, 0) if n_nisar else None, "gpsWeeks": r((n_gps - 1) / 7, 0) if n_gps else None, "nodeWeeks": r((n_node - 1) / 7, 0) if n_node else None}

        cell = {
            "id": cid, "lon": r(lon, 5), "lat": r(lat, 5),
            "rate": r(rate), "se": r(se), "los": r(sat_los), "raw": r(vertical_rate(sat_los)) if sat_los is not None and "gps" not in sources and abs(vertical_rate(sat_los) - (sat_rate or 0)) >= 1 else None, "src": sources, "sig": significant,
            "conf": level, "confWhy": conf_why,
            "act": act, "actWhy": act_why,
            "future": future, "detect": detect,
            "series": op["opera_series_mm"] if op and act != "insufficient_data" else None,
            "quality": {"periods": op.get("opera_links_used") if op else None, "periodsTotal": opera["product_count"], "fitSe": r(vertical_rate(op["opera_velocity_se_mm_year"])) if op else None,
                        "nisarCoh": r(row.get("coherence_median"), 2), "nisarValid": r(row.get("valid_fraction"), 2), "nisarOk": bool(row.get("in_main_connected_component") and (row.get("coherence_median") or 0) >= t.coherence_min and (row.get("valid_fraction") or 0) >= t.valid_fraction_min)},
            "gps": {"id": cover["station_id"], "km": r(cover_km), "up": display_gps_rate(cover["up_mm_year"])[0], "y0": r(cover.get("start_decimal_year"), 0), "y1": r(cover.get("end_decimal_year"), 0)},
            "check": check,
            "flood": {"zone": f.get("flood_zone"), "sub": f.get("zone_subtype"), "sfha": sfha, "share": f.get("sfha_share")},
            "well": {"km": r(ev.get("usgs_distance_km")), "dd": r(clean_dd(ev.get("groundwater_depth_change_ft")), 2)} if ev.get("usgs_site_id") else None,
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
            # compare with the hidden square's own raw reading (not its weighted value)
            loo.append(abs(sum(wi * o["rate"] for wi, (_, o) in zip(w, near)) / sum(w) - vertical_rate(c["los"])))
    loo.sort()
    estimate_error = {"median": loo[len(loo) // 2], "p80": loo[int(len(loo) * 0.8)], "tested": len(loo)}
    def apply_estimate(c: dict, est: float, est_se: float, n: int, source: str, why: list[str], tag: str) -> None:
        nonlocal estimated
        sig = abs(est) >= stable_vertical and abs(est) >= 2 * est_se
        counts["action"]["insufficient_data"] -= 1
        act, act_why = action_label(rate_vertical=est, significant=sig, flood_zone_sfha=c["flood"]["sfha"], gps_km=c["gps"]["km"], gps_rate=c["gps"]["up"], covered_km=t.gps_nearby_km)
        counts["action"][act] = counts["action"].get(act, 0) + 1
        counts["confidence"]["low"] = counts["confidence"].get("low", 0) + 1
        future = None
        if years:
            by = {}
            for y in years:
                h = y - base_year
                half = sqrt(band_at(h) ** 2 + (est_se * h) ** 2)
                by[str(y)] = {"c": r(est * h / 10), "lo": r((est * h - half) / 10), "hi": r((est * h + half) / 10)}
            per_year = sqrt(band_at(tested) ** 2 + (est_se * tested) ** 2) / tested
            future = {"rate": r(est), "low": r(est - per_year), "high": r(est + per_year), "recent": None, "by": by}
        n_nisar = passes_to_detect(est * COS, nisar_sigma_at(c["lon"], c["lat"]), 12) if est < 0 else None
        n_gps = passes_to_detect(est, GPS_DAILY_SIGMA_MM, 1) if est < 0 else None
        n_node = passes_to_detect(est, NODE_DAILY_SIGMA_MM, 1, max_passes=4000) if est < 0 else None
        c.update({
            "rate": r(est), "se": r(est_se), "src": ["estimated"], "estFrom": source, "sig": sig, "est": n,
            "conf": "low", "confWhy": why,
            "act": act, "actWhy": act_why + tag, "future": future,
            "detect": {"nisarMonths": r((n_nisar - 1) * 12 / 30.44, 0) if n_nisar else None, "gpsWeeks": r((n_gps - 1) / 7, 0) if n_gps else None, "nodeWeeks": r((n_node - 1) / 7, 0) if n_node else None} if est < 0 else None,
        })
        estimated += 1

    estimated = 0
    for c in cells:
        if c["act"] != "insufficient_data" or c["flood"]["zone"] == "OPEN WATER" or (c.get("dswx", {}).get("water_fraction") or 0) > 0.5:
            continue
        near = neighbours(c["lon"], c["lat"])
        if len(near) < ESTIMATE_MIN_NEIGHBORS:
            continue
        w = [1 / max(d, 0.5) ** 2 for d, _ in near]
        est = sum(wi * o["rate"] for wi, (_, o) in zip(w, near)) / sum(w)
        apply_estimate(c, est, estimate_error["p80"] / 1.28, len(near), "satellite",
                       [f"No direct measurement: estimated from {len(near)} measured squares within {ESTIMATE_RADIUS_KM:g} km.", f"In testing, estimates like this were within {estimate_error['p80']:.1f} mm/yr of the real value 80% of the time."],
                       " (Estimated from neighbouring squares.)")

    # Outside the satellite product's coverage (mostly the far south): estimate
    # from nearby GPS stations with at least 5 years of record. Tested by
    # predicting satellite-measured squares from GPS alone.
    gps_ok = [s for s in stations if s.get("up_mm_year") is not None and (s.get("history_years") or 0) >= 5 and abs(s["up_mm_year"]) <= IMPLAUSIBLE_MM_YEAR]

    def gps_idw(lon: float, lat: float):
        near = sorted(((distance_km(lon, lat, s["longitude"], s["latitude"]), s) for s in gps_ok), key=lambda p: p[0])
        near = [(d, s) for d, s in near if d <= GPS_EST_RADIUS_KM][:8]
        if len(near) < GPS_EST_MIN_STATIONS:
            return None, near
        w = [1 / max(d, 1.0) ** 2 for d, _ in near]
        return sum(wi * s["up_mm_year"] for wi, (_, s) in zip(w, near)) / sum(w), near

    gps_test = []
    for c in measured[::2]:
        if "gps" in c["src"]:
            continue
        g, _ = gps_idw(c["lon"], c["lat"])
        if g is not None:
            gps_test.append(abs(g - vertical_rate(c["los"])))
    gps_test.sort()
    gps_error = {"median": gps_test[len(gps_test) // 2], "p80": gps_test[int(len(gps_test) * 0.8)], "tested": len(gps_test)} if gps_test else None
    gps_estimated = 0
    for c in cells:
        if c["act"] != "insufficient_data" or not gps_error or c["flood"]["zone"] == "OPEN WATER" or (c.get("dswx", {}).get("water_fraction") or 0) > 0.5:
            continue
        g, near = gps_idw(c["lon"], c["lat"])
        if g is None:
            c["actWhy"] = f"Nobody measures this ground: outside the satellite's coverage, with fewer than {GPS_EST_MIN_STATIONS} GPS stations within {GPS_EST_RADIUS_KM:g} km. A sensor here would give the first reading."
            continue
        apply_estimate(c, g, gps_error["p80"] / 1.28, len(near), "gps",
                       [f"Outside the satellite's coverage: estimated from {len(near)} GPS stations within {GPS_EST_RADIUS_KM:g} km (nearest {near[0][0]:.1f} km).",
                        f"In testing against satellite-measured squares, GPS-only estimates were within {gps_error['p80']:.1f} mm/yr 80% of the time."],
                       " (Estimated from nearby GPS stations; outside satellite coverage.)")
        gps_estimated += 1

    # Stripe squares: the satellite's ~990 m blocks don't tile our 1 km grid
    # exactly, so about every 7th row and column of squares gets no block of
    # its own. When at least two of the four squares touching it are measured,
    # it is filled from them. Tested by filling 5,735 measured squares from
    # their touching neighbours: median error 0.65 mm/yr, 80% within 1.9,
    # better than a typical single measurement (median se 2.6). So these get
    # the lowest confidence among the squares they are filled from, and are
    # drawn like measured squares. Where two stripes cross, diagonal
    # neighbours are used (at least 3).
    import re as _re2
    rank_of = {"low": 0, "medium": 1, "high": 2}
    level_of = {0: "low", 1: "medium", 2: "high"}
    grid_index = {}
    for c in cells:
        mm = _re2.search(r"(-?\d+)-(-?\d+)$", c["id"])
        grid_index[(int(mm.group(1)), int(mm.group(2)))] = c
    direct = lambda o: o is not None and o["act"] != "insufficient_data" and "estimated" not in o["src"] and o["rate"] is not None and o.get("conf")  # noqa: E731
    stripe_filled = 0
    for (i, j), c in grid_index.items():
        if c.get("estFrom") != "satellite":
            continue
        touching = [grid_index.get((i + a, j + b)) for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1))]
        touching = [o for o in touching if direct(o)]
        if len(touching) < 2:
            # where two stripes cross, use the diagonal neighbours too
            touching = [grid_index.get((i + a, j + b)) for a in (-1, 0, 1) for b in (-1, 0, 1) if (a, b) != (0, 0)]
            touching = [o for o in touching if direct(o)]
            if len(touching) < 3:
                continue
        fill = sum(o["rate"] for o in touching) / len(touching)
        level = level_of[min(rank_of[o["conf"]] for o in touching)]
        counts["confidence"]["low"] -= 1
        counts["confidence"][level] = counts["confidence"].get(level, 0) + 1
        # the label, forecast and confirm-time follow the filled rate
        sig = abs(fill) >= stable_vertical and abs(fill) >= 2 * (c["se"] or 0)
        counts["action"][c["act"]] -= 1
        act, act_why = action_label(rate_vertical=fill, significant=sig, flood_zone_sfha=c["flood"]["sfha"], gps_km=c["gps"]["km"], gps_rate=c["gps"]["up"], covered_km=t.gps_nearby_km)
        counts["action"][act] = counts["action"].get(act, 0) + 1
        if c.get("future"):
            for y, v in c["future"]["by"].items():
                h = int(y) - base_year
                half = (v["hi"] - v["lo"]) / 2
                v.update({"c": r(fill * h / 10), "lo": r(fill * h / 10 - half), "hi": r(fill * h / 10 + half)})
            c["future"]["rate"] = r(fill)
        n_gps = passes_to_detect(fill, GPS_DAILY_SIGMA_MM, 1) if fill < 0 else None
        n_node = passes_to_detect(fill, NODE_DAILY_SIGMA_MM, 1, max_passes=4000) if fill < 0 else None
        n_nisar = passes_to_detect(fill * COS, nisar_sigma_at(c["lon"], c["lat"]), 12) if fill < 0 else None
        c["detect"] = {"nisarMonths": r((n_nisar - 1) * 12 / 30.44, 0) if n_nisar else None, "gpsWeeks": r((n_gps - 1) / 7, 0) if n_gps else None, "nodeWeeks": r((n_node - 1) / 7, 0) if n_node else None} if fill < 0 else None
        c.update({"sig": sig, "act": act, "actWhy": act_why + " (Filled from the measured squares touching it.)"})
        c.update({"rate": r(fill), "conf": level, "adj": len(touching), "estFrom": "satellite",
                  "confWhy": [f"Between measured squares: the satellite's grid blocks don't line up exactly with our 1 km squares, so this one is filled from the {len(touching)} measured squares touching it.",
                              "In testing, fills like this were within 1.9 mm/yr of the real value 80% of the time, better than a typical single satellite measurement.",
                              f"Confidence is the lowest of the squares it is filled from ({', '.join(sorted({o['conf'] for o in touching}))})."]})
        stripe_filled += 1

    # Sensor sites: "Add monitoring here" squares, never where we are already
    # highly confident. Ranked by the sinking of the surrounding area
    # (median within 3 km), with less certain squares first among similar
    # rates (Low counts fully, Medium 80%), kept at least 4 km apart.
    uncertainty = {"low": 1.0, "medium": 0.8}
    conf_now = {c["id"]: c.get("conf") for c in cells}
    by_conf = lambda cand: conf_now.get(cand["id"], cand["conf"])  # noqa: E731
    candidates = [c for c in candidates if by_conf(c) in uncertainty]
    candidates.sort(key=lambda c: c["area"] * uncertainty[by_conf(c)])
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
        if c["act"] in ("add_monitoring", "observe") and c.get("conf") != "high" and c["gps"]["km"] > t.gps_nearby_km and c["rate"] is not None and c["rate"] < 0 and weeks is not None and weeks <= NODE_MAX_YEARS * 52:
            node_candidates.append({"id": c["id"], "lon": c["lon"], "lat": c["lat"], "area": area.get(c["id"], c["rate"]), "rate": c["rate"], "weeks": weeks, "act": c["act"], "zone": c["flood"]["zone"], "est": "estimated" in c["src"]})
    node_candidates.sort(key=lambda c: c["area"])
    nodes: list[dict] = []
    for c in node_candidates:
        if all(distance_km(c["lon"], c["lat"], s["lon"], s["lat"]) >= SENSOR_SPACING_KM for s in sensors) and all(distance_km(c["lon"], c["lat"], n["lon"], n["lat"]) >= NODE_SPACING_KM for n in nodes):
            nodes.append(c)
        if len(nodes) >= NODE_COUNT:
            break
    # Every "Add monitoring here" square gets a suggested site within
    # COVER_KM: where neither a permanent-station site nor a node above is that
    # close, add low-cost nodes, each placed to cover as many of the remaining
    # squares as possible (fastest-sinking first among ties).
    monitor = [c for c in cells if c["act"] == "add_monitoring"]
    placed = sensors + nodes
    left = [c for c in monitor if all(distance_km(c["lon"], c["lat"], o["lon"], o["lat"]) > COVER_KM for o in placed)]
    while left:
        def covers(c: dict) -> int:
            return sum(1 for o in left if abs(o["lat"] - c["lat"]) < 0.06 and distance_km(c["lon"], c["lat"], o["lon"], o["lat"]) <= COVER_KM)
        best = max(left, key=lambda c: (covers(c), -(c["rate"] or 0)))
        nodes.append({"id": best["id"], "lon": best["lon"], "lat": best["lat"], "area": area.get(best["id"], best["rate"]), "rate": best["rate"], "weeks": (best.get("detect") or {}).get("nodeWeeks"),
                      "act": best["act"], "zone": best["flood"]["zone"], "est": "estimated" in best["src"], "cover": True})
        left = [o for o in left if distance_km(best["lon"], best["lat"], o["lon"], o["lat"]) > COVER_KM]
    for rank, n in enumerate(nodes, start=1):
        by_id[n["id"]]["nodeRank"] = rank
    sites_all = [("gps", s_["rank"], s_) for s_ in ({"rank": i + 1, **x} for i, x in enumerate(sensors))] + [("node", i + 1, x) for i, x in enumerate(nodes)]
    for c in monitor:
        kind, rank, site = min(sites_all, key=lambda k: distance_km(c["lon"], c["lat"], k[2]["lon"], k[2]["lat"]))
        c["near"] = {"kind": kind, "rank": rank, "km": r(distance_km(c["lon"], c["lat"], site["lon"], site["lat"]))}
    node_out = [{"rank": i + 1, "id": n["id"], "lon": r(n["lon"], 5), "lat": r(n["lat"], 5), "areaRate": r(n["area"]), "weeks": n["weeks"], "act": n["act"], "zone": n["zone"], "est": n["est"], "cover": bool(n.get("cover"))} for i, n in enumerate(nodes)]

    # "Fill the gap" nodes: land squares outside the satellite's coverage whose
    # nearest GPS is far away. Nothing measures the ground there directly, so a
    # node gives the first reading. Flood-zone squares first, then the most
    # isolated, kept apart from each other and from the other sites.
    gap_candidates = [c for c in cells if "satellite" not in c["src"] and c["id"] not in opera_cells and c["flood"]["zone"] != "OPEN WATER"
                      and (c.get("dswx", {}).get("water_fraction") or 0) <= 0.5 and c["gps"]["km"] >= GAP_MIN_GPS_KM]
    # Rank by the size of the blind area around each square (unmeasured,
    # un-estimated land within 3 km), so a node sits in the middle of the
    # biggest blind spots rather than on the edge of the study box.
    blind = [c for c in cells if c["act"] == "insufficient_data" and c["flood"]["zone"] != "OPEN WATER" and (c.get("dswx", {}).get("water_fraction") or 0) <= 0.5]
    blind_ids = {c["id"] for c in blind}
    gap_candidates = [c for c in gap_candidates if c["id"] in blind_ids]
    for c in gap_candidates:
        c["_blind"] = sum(1 for o in blind if abs(o["lon"] - c["lon"]) < 0.035 and abs(o["lat"] - c["lat"]) < 0.03 and distance_km(c["lon"], c["lat"], o["lon"], o["lat"]) <= 3.0)
    gap_candidates.sort(key=lambda c: (not c["flood"]["sfha"], -c["_blind"], -c["gps"]["km"]))
    gaps: list[dict] = []
    taken = sensors + nodes
    for c in gap_candidates:
        if all(distance_km(c["lon"], c["lat"], g["lon"], g["lat"]) >= GAP_SPACING_KM for g in gaps) and all(distance_km(c["lon"], c["lat"], o["lon"], o["lat"]) >= NODE_SPACING_KM for o in taken):
            gaps.append(c)
        if len(gaps) >= GAP_COUNT:
            break
    for rank, g in enumerate(gaps, start=1):
        by_id[g["id"]]["gapRank"] = rank
    gap_out = [{"rank": i + 1, "id": g["id"], "lon": r(g["lon"], 5), "lat": r(g["lat"], 5), "gpsKm": r(g["gps"]["km"]), "zone": g["flood"]["zone"], "sfha": g["flood"]["sfha"], "rate": g["rate"], "blindKm2": g["_blind"]} for i, g in enumerate(gaps)]
    for c in gap_candidates:
        c.pop("_blind", None)

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
    if bench:
        forecast_meta = {
            "method": bench["chosen"],
            "base": dates[-1],
            "years": years,
            "tested_horizon_years": tested,
            "bands_cm": [{"years_ahead": h, "half_width_cm": r(b / 10, 2)} for h, b in bands],
            "benchmark": {k: bench[k] for k in ("table", "test_cases", "origins")},
            "backtest": backtest,
            "ml_tested": True,
            "limitations": [
                "The forecast continues each square's season-aware 2016-2026 trend, averaged with its neighbours; it cannot foresee changes in groundwater pumping or rules.",
                f"Tested up to {tested:.0f} years ahead in {bench['test_cases']} walk-forward tests; later years are not offered.",
                "Ranges come from real walk-forward test errors (80% of squares fell inside), not from a formula.",
                "Year-to-year shrink-swell of Houston's clay (dry vs wet years) can't be predicted; the range covers it.",
            ],
        }

    # Hazard views (backend/hazards.py, scripts/build_hazards.py)
    hazards_meta = None
    hz_path = PROV / "hazards.json"
    if hz_path.is_file():
        hz_all = load(hz_path)
        hz_cells = hz_all["cells"]
        measured = [c for c in cells if "estimated" not in c["src"] and c["act"] != "insufficient_data" and c["id"] in hz_cells]
        drops = sorted(hz_cells[c["id"]]["drought_drop_mm"] for c in measured)
        typical = drops[len(drops) // 2] if drops else 0.0
        q10 = drops[int(0.10 * len(drops))] if drops else 0.0
        q30 = drops[int(0.30 * len(drops))] if drops else 0.0
        bend_hi, bend_mid = 10.0, 5.0
        for c in measured:
            h = hz_cells[c["id"]]
            d = h["drought_drop_mm"]
            b = h["bend_mm_year_km"]
            c["hz"] = {
                "drop": r(typical - d),
                "dl": "high" if d <= q10 else "medium" if d <= q30 else "low",
                "bend": r(b) if b is not None else None,
                "bl": None if b is None else "high" if b >= bend_hi else "medium" if b >= bend_mid else "low",
            }
        # Stripe squares (filled from touching squares) take the average
        # drought drop and bending of the measured squares they were filled
        # from, so the hazard views don't show the grid's stripes.
        for (i, j), c in grid_index.items():
            if not c.get("adj") or c.get("hz"):
                continue
            near = [grid_index.get((i + a2, j + b2)) for a2 in (-1, 0, 1) for b2 in (-1, 0, 1) if (a2, b2) != (0, 0)]
            near = [o for o in near if o is not None and o.get("hz") and "estimated" not in o["src"]]
            if len(near) < 2:
                continue
            d = typical - sum(o["hz"]["drop"] for o in near) / len(near)
            bends = [o["hz"]["bend"] for o in near if o["hz"]["bend"] is not None]
            b = sum(bends) / len(bends) if bends else None
            c["hz"] = {"drop": r(typical - d), "dl": "high" if d <= q10 else "medium" if d <= q30 else "low",
                       "bend": r(b) if b is not None else None,
                       "bl": None if b is None else "high" if b >= bend_hi else "medium" if b >= bend_mid else "low", "filled": True}
        harvey_path = PROV / "harvey_check.json"
        harvey = load(harvey_path) if harvey_path.is_file() else None
        if harvey:
            for c in cells:
                h = harvey["cells"].get(c["id"])
                if h:
                    c["harvey"] = {"wet": h[0], "ft": h[1]}
        hazards_meta = {
            "tests": hz_all["tests"],
            "drought": {"epochs": ["2018-08-13", "2023-10-04"], "high_mm": r(typical - q10), "medium_mm": r(typical - q30)},
            "bend": {"high": bend_hi, "medium": bend_mid},
            "flood": {"basis": "measured drop since the first satellite date; flood depths are not forecast (D-046)"},
            "harvey": {k: harvey.get(k) for k in ("source", "areas", "squares", "by_class", "flooded_area_outside_high_risk_pct", "by_sinking", "high_water_marks", "depth_by_class")} if harvey else None,
        }

    inventory = load(INVENTORY)
    chain_report = inventory["chain"]
    nisar_archive = {
        "passes": chain_report["date_count"], "pairs": chain_report["pair_count"],
        "first": chain_report["first_date"], "last": chain_report["last_date"],
        "processedPairs": sum(1 for granule in inventory["granules"] if granule.get("in_repo") or (ROOT / "data" / "derived" / f"nisar_gunw_houston_{granule['reference_date'].replace('-', '')}_{granule['secondary_date'].replace('-', '')}_pair_cells.json").is_file()),
        "retrieved": inventory["retrieved_utc"][:10], "inventory": relative(INVENTORY),
    }
    meta = {
        "status": "provisional_unreviewed",
        "nisarArchive": nisar_archive,
        "record": {"start": dates[0], "end": dates[-1], "dates": dates, "products": opera["product_count"]},
        "thresholds": {"stable_mm_year": r(stable_vertical), "gps_covered_km": t.gps_nearby_km, "gps_blend_km": GPS_BLEND_KM, "disagree_mm_year": 5.0, "sensor_spacing_km": SENSOR_SPACING_KM, "incidence_deg": 38, "gps_daily_sigma_mm": GPS_DAILY_SIGMA_MM},
        "counts": counts,
        "validation": {"stations": comparison["stats"]["station_count"], "r": comparison["stats"].get("pearson_r"), "typical_diff_mm_year": r(vertical_rate(comparison["stats"]["median_abs_residual_mm_year"])), "points": [{"id": p["station_id"], "gps": r(p["gps_up_mm_year"]), "sat": r(vertical_rate(p["opera_los_mm_year"]))} for p in comparison["stations"]]},
        "forecast": forecast_meta,
        "hazards": hazards_meta,
        "nisar": {"pair": nisar_check(pair, 12), "chain": nisar_check(chain, 60), "detect": detect_table, "sigma_mm": r(nisar_sigma),
                  "noise": {"measured": bool(nisar_noise), "pairs": (nisar_noise or {}).get("pairs"), "near_mm": noise_curve[0][1] if noise_curve else None, "far_mm": noise_curve[-1][1] if noise_curve else None,
                            "near_km": noise_curve[0][0] if noise_curve else None, "far_km": noise_curve[-1][0] if noise_curve else None}},
        "blendTest": shrink_test,
        "reference": build["reference"],
        "sensors": sensor_out,
        "nodes": node_out,
        "gaps": gap_out,
        "gpsEstimates": {"count": gps_estimated, "radius_km": GPS_EST_RADIUS_KM, "min_stations": GPS_EST_MIN_STATIONS, "median_error_mm_year": r(gps_error["median"]) if gps_error else None, "p80_error_mm_year": r(gps_error["p80"]) if gps_error else None, "tested": gps_error["tested"] if gps_error else 0},
        "estimates": {"stripeFilled": stripe_filled, "count": estimated - gps_estimated, "radius_km": ESTIMATE_RADIUS_KM, "min_neighbors": ESTIMATE_MIN_NEIGHBORS, "median_error_mm_year": r(estimate_error["median"]), "p80_error_mm_year": r(estimate_error["p80"]), "tested": estimate_error["tested"]},
        "hardware": {"node_daily_sigma_mm": NODE_DAILY_SIGMA_MM, "node_max_years": NODE_MAX_YEARS, "node_spacing_km": NODE_SPACING_KM, "gps_daily_sigma_mm": GPS_DAILY_SIGMA_MM,
                     "node_weeks_10": r((passes_to_detect(-10, NODE_DAILY_SIGMA_MM, 1, max_passes=4000) - 1) / 7, 0), "gps_weeks_10": r((passes_to_detect(-10, GPS_DAILY_SIGMA_MM, 1) - 1) / 7, 0),
                     "node_weeks_5": r((passes_to_detect(-5, NODE_DAILY_SIGMA_MM, 1, max_passes=4000) - 1) / 7, 0), "gps_weeks_5": r((passes_to_detect(-5, GPS_DAILY_SIGMA_MM, 1) - 1) / 7, 0)},
        "groundtruth": groundtruth_meta(),
        "nasaLayers": {k: v["meta"].get("source") for k, v in nasa.items()},
        "provenance": {"manifest": relative(MANIFEST)},
        "stations": {"total": len(all_stations), "deepSeated": sorted(s["station_id"] for s in all_stations if is_deep_seated(s["station_id"])), "rateWithheld": sorted(s["station_id"] for s in all_stations if display_gps_rate(s.get("up_mm_year"))[1])},
    }
    sites = {
        "gps": [{"id": s["station_id"], "lon": s["longitude"], "lat": s["latitude"], "up": display_gps_rate(s["up_mm_year"])[0], "flag": display_gps_rate(s["up_mm_year"])[1], "deepAnchorM": DEEP_SEATED_GNSS.get(s["station_id"], {}).get("anchor_depth_m"), "y0": s["start_decimal_year"], "y1": s["end_decimal_year"]} for s in all_stations],
        "ext": [{"id": s["station_id"], "name": s.get("station_name"), "lon": s["longitude"], "lat": s["latitude"], "c": s.get("cumulative_compaction_change"), "d0": s["first_observation"]["date"], "d1": s["last_observation"]["date"]} for s in extensometers],
        "wells": [{"id": s["site_id"], "name": s.get("site_name"), "lon": s["longitude"], "lat": s["latitude"], "dd": r(s.get("depth_change_ft"), 2), "t0": s["first_observation"]["time"][:10], "t1": s["last_observation"]["time"][:10]} for s in wells],
    }
    OUT.mkdir(parents=True, exist_ok=True)
    # Fast first load: cells.json holds only what the map, legends and
    # downloads need (~4 MB); each square's full record lives in a 16 km tile
    # under details/, fetched when someone opens that square.
    import re as _re

    tl_times = [decimal_year(d) for d in dates]
    t0 = tl_times[0]

    def timelapse(c: dict) -> list[int] | None:
        """Ground-level change since 2016 at each satellite date (vertical mm).
        Clean records show the measurement (lightly smoothed); noisy or
        estimated squares show their trend."""
        if c["act"] == "insufficient_data" or c["rate"] is None:
            return None
        op = opera_cells.get(c["id"])
        fit = (c.get("quality") or {}).get("fitSe")
        if op and "estimated" not in c["src"] and fit is not None and fit <= 5:
            v = [x / COS for x in op["opera_series_mm"]]
            sm = [v[0]] + [(v[k - 1] + v[k] + v[k + 1]) / 3 for k in range(1, len(v) - 1)] + [v[-1]]
            return [round(x - sm[0]) for x in sm]
        return [round(c["rate"] * (t - t0)) for t in tl_times]

    slim_keys = ("id", "lon", "lat", "rate", "se", "src", "sig", "conf", "act", "est", "estFrom", "adj", "sensorRank", "nodeRank", "gapRank", "hz", "harvey")
    slim = []
    tiles: dict[str, dict] = {}
    for c in cells:
        row = {k: c[k] for k in slim_keys if k in c}
        row["flood"] = c["flood"]
        if c.get("nasadem", {}).get("elevation_m") is not None:
            row["elev"] = c["nasadem"]["elevation_m"]
        if c.get("future"):
            row["future"] = {"rate": c["future"]["rate"], "by": {y: {"c": v["c"]} for y, v in c["future"]["by"].items()}}
        tl = timelapse(c)
        if tl:
            row["tl"] = tl
        slim.append(row)
        m = _re.search(r"(-?\d+)-(-?\d+)$", c["id"])
        key = f"{int(m.group(1)) // 16}_{int(m.group(2)) // 16}"
        tiles.setdefault(key, {})[c["id"]] = c
    details_dir = OUT / "details"
    details_dir.mkdir(parents=True, exist_ok=True)
    for key, rows in tiles.items():
        (details_dir / f"{key}.json").write_text(json.dumps(rows, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    meta["timelapse"] = {"dates": dates}
    # Pre-registered OPERA -> NISAR prediction test (D-041, D-048): status as scored.
    pt = DERIVED / "prediction" / "prediction_test_result.json"
    if pt.is_file():
        res = load(pt)
        meta["predictionTest"] = {"status": res["status"], "pairs": res["target_chain"]["pairs"], "first": res["target_chain"]["first"], "last": res["target_chain"]["last"],
                                  "squares": res["squares"]["used"], "power": res["power"]["power"], "verdict": res.get("verdict"), "result": res.get("result")}
    (OUT / "cells.json").write_text(json.dumps(slim, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    (OUT / "meta.json").write_text(json.dumps(meta, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    (OUT / "sites.json").write_text(json.dumps(sites, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    for name in ("cells.json", "meta.json", "sites.json"):
        LOG.wrote(OUT / name)
    LOG.write(MANIFEST, artifact_type="terragauge_web_export_manifest", command="python3 scripts/export_web.py",
              extra={"note": "Per-square detail tiles (web/public/data/details/) are written alongside cells.json from the same records."})
    print(json.dumps({"cells": len(cells), "counts": counts, "stable": stable_vertical, "years": years, "sensors": len(sensor_out), "nodes": [(n["rank"], n["areaRate"], n["weeks"], n["act"], n["est"]) for n in node_out[:8]], "estimates": meta["estimates"], "gpsEstimates": meta["gpsEstimates"], "gaps": len(gap_out), "hardware": meta["hardware"]}, indent=1))


if __name__ == "__main__":
    main()

"""Export the combined, plain-language TerraGauge dataset for the website.

Run after scripts/build_provisional.py:  python3 scripts/export_web.py

One map, all sources combined. For each 1 km cell, describing the past record
only (no projections: MASTER claims policy, section 20):
- movement: the OPERA satellite line-of-sight rate converted to a
  vertical-equivalent rate (assumes vertical motion and one look angle),
  blended with a GPS station's rate when one is within 1 km (inverse-variance
  weighting); GPS alone where the satellite has no reading but a station is
  within 1 km. Rates are relative to the reference GPS stations.
- confidence: High / Medium / Low with reasons (backend.insights.confidence).
- priority + sensor plan (backend.insights.priority / sensor_plan).
Every input and output is hashed into data/manifests/web_export.json, so each
number on the site traces to an artifact (MASTER section 0, rule 3).
All science logic is in Python; the website only displays these numbers.
"""

from __future__ import annotations

import json
import sys
from math import sqrt
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.insights import (  # noqa: E402
    INCIDENCE_DEG, confidence, distance_km, gps_difference, neighborhood_medians, priority, sensor_plan, vertical_rate,
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
GPS_SIGMA_MM_YEAR = 0.5      # assumed uncertainty of a >=10-year HoustonNet rate
GPS_BLEND_KM = 1.0


def load(path: Path) -> dict:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    assert_publishable(payload, str(path))
    return payload


def r(value, digits=1):
    return None if value is None else round(float(value), digits)


def robust_sd(values: list[float]) -> float:
    center = median(values)
    return 1.4826 * median(abs(v - center) for v in values)


def relative(path: Path) -> str:
    return Path(path).resolve().relative_to(ROOT).as_posix()


def main() -> None:
    pair_path = PROV / "terragauge_houston_evidence_pair_20251102_20251114.json"
    chain_path = PROV / "terragauge_houston_evidence_chain_20251102_20260101.json"
    log = ProvenanceLog(ROOT, regenerate={relative(pair_path): BUILD_COMMAND, relative(chain_path): BUILD_COMMAND})

    def get(path: Path) -> dict:
        payload = load(path)
        log.read(path)
        return payload

    thresholds = Thresholds()
    velocity_files = sorted(PROV.glob("opera_houston_los_velocity_*.json"))
    opera = get(velocity_files[-1])
    comparison = get(PROV / "opera_vs_houstonnet_comparison.json")
    build = get(PROV / "build_report.json")
    pair = get(pair_path)
    chain = get(chain_path)
    all_stations = get(DERIVED / "houstonnet_2024_summary.json")["stations"]
    # Deep-seated antennas (on deep extensometer anchors) do not measure the land
    # surface: never blend, cross-check, or count them as surface coverage.
    stations = [s for s in all_stations if not is_deep_seated(s["station_id"])]
    extensometers = get(DERIVED / "usgs_houston_extensometer_compaction_2023.json")["stations"]
    wells = get(DERIVED / "usgs_houston_groundwater_2025-01-01_2026-11-07.json")["series"]
    # USGS marks missing days with -999999 ft; a change that size is a no-data
    # value, never a water level (the ingestion skips it too). Show it as unknown.
    clean_dd = lambda v: None if v is None or abs(float(v)) > 1000 else v  # noqa: E731
    flood = {row["cell_id"]: row for row in get(DERIVED / "fema_nfhl_houston_cell_context_2026-11-07.json")["cells"]}
    inventory = get(INVENTORY)
    opera_cells = {row["cell_id"]: row for row in opera["cells"]}
    # D-042: the map used to hold only the NISAR evidence footprint, which hid
    # measured OPERA squares outside it. Add them, with the FEMA zone sampled at
    # the square's centre exactly as fema_nfhl_houston_cell_context does.
    pair_ids = {row["cell_id"] for row in pair["cells"]}
    extra = [c for cid, c in opera_cells.items() if cid not in pair_ids]
    if extra:
        from scripts.build_grid import OVERLAY, ZoneLookup
        lookup = ZoneLookup(get(OVERLAY)["features"])
        for c in extra:
            zone, sub, sfha = lookup.zone(float(c["longitude"]), float(c["latitude"]))
            flood[c["cell_id"]] = {"cell_id": c["cell_id"], "flood_zone": zone, "zone_subtype": sub, "flood_exposed": sfha if zone else None}
    rows = pair["cells"] + [{"cell_id": c["cell_id"], "longitude": c["longitude"], "latitude": c["latitude"], "evidence": {}, "outside_nisar": True} for c in extra]
    # Squares that no OPERA product ever assigned a pixel block to: the ~990 m
    # blocks skip about a fifth of the ~870 m (on the ground) map squares.
    opera_seen = set()
    for path in sorted(DERIVED.glob("opera_disp_houston_*_pair_cells.json")):
        opera_seen |= {c["cell_id"] for c in get(path)["cells"]}
    nasa = {}
    for name in ("nasadem", "dswx", "dist"):
        path = LAYERS / f"{name}_houston_cells.json"
        if path.is_file():
            artifact = get(path)
            nasa[name] = {"meta": {k: v for k, v in artifact.items() if k != "cells"}, "cells": {row["cell_id"]: row for row in artifact["cells"]}}

    dates = opera["dates"]
    data_start, data_end = dates[0], dates[-1]
    record_text = f"the {data_start[:4]}–{data_end[:4]} satellite record"

    # Noise floor from the reference stations (LOS), as in the decision rules.
    reference_ids = set(opera.get("reference_cell_ids") or [])
    ref_v = [opera_cells[c]["opera_los_velocity_mm_year"] for c in reference_ids if c in opera_cells]
    noise_los = robust_sd(ref_v)
    sig_threshold_vertical = vertical_rate(thresholds.pair_signal_sigma_multiplier * noise_los)

    # Citywide model error: robust spread of OPERA-vs-GPS differences (vertical).
    diffs = [vertical_rate(row["residual_mm_year"]) for row in comparison["stations"]]
    model_error = robust_sd(diffs)

    sat_rates = [{"id": c["cell_id"], "lon": float(c["longitude"]), "lat": float(c["latitude"]), "rate": vertical_rate(c["opera_los_velocity_mm_year"])} for c in opera["cells"] if abs(vertical_rate(c["opera_los_velocity_mm_year"])) <= 40]
    neighbors = neighborhood_medians(sat_rates)
    long_history = [s for s in stations if (s.get("history_years") or 0) >= 10 and display_gps_rate(s.get("up_mm_year"))[0] is not None]
    # Coverage counts any station still reporting (data through 2022 or later).
    active = [s for s in stations if (s.get("end_decimal_year") or 0) >= 2022]
    cells, rows_for_plan = [], []
    counts = {"priority": {}, "confidence": {}}
    for row in rows:
        cid, lon, lat = row["cell_id"], float(row["longitude"]), float(row["latitude"])
        ev = row["evidence"]
        op = opera_cells.get(cid)
        f = flood.get(cid, {})
        sfha = f.get("flood_exposed") is True

        # Nearest long-history GPS station (for blending and coverage).
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
            if near_km <= GPS_BLEND_KM:
                w_s, w_g = 1 / se_sat ** 2, 1 / GPS_SIGMA_MM_YEAR ** 2
                rate = (rate_sat * w_s + near["up_mm_year"] * w_g) / (w_s + w_g)
                se = sqrt(1 / (w_s + w_g))
                sources.append("gps")
        elif near_km <= GPS_BLEND_KM:
            rate, se = float(near["up_mm_year"]), GPS_SIGMA_MM_YEAR
            sources.append("gps")

        if rate is not None:
            if op:
                diff, check_id, check_km = gps_difference(lon, lat, vertical_rate(op["opera_los_velocity_mm_year"]), stations)
                area = neighbors.get(cid)
                level, conf_reasons = confidence(se_vertical=vertical_rate(op["opera_velocity_se_mm_year"]), residual_sd_mm=op["opera_residual_sd_mm"], gps_difference_mm_year=diff, missing_dates=len(op.get("opera_links_filled") or []), total_dates=opera["product_count"], neighbor_difference_mm_year=(vertical_rate(op["opera_los_velocity_mm_year"]) - area) if area is not None else None)
                if sources == ["satellite", "gps"] and level != "high":
                    level = "high"; conf_reasons = conf_reasons + ["A GPS station sits inside this square, so its precise reading is blended in."]
            else:
                diff = check_id = check_km = None
                level, conf_reasons = "high", ["A long-running GPS station sits inside this square."]
            significant = abs(rate) >= sig_threshold_vertical and abs(rate) >= 2 * se
            pri, pri_reason = priority(rate_vertical=rate, significant=significant, level=level, flood_zone_sfha=sfha, open_water=f.get("flood_zone") == "OPEN WATER" or (nasa.get("dswx", {}).get("cells", {}).get(cid, {}).get("water_fraction") or 0) > 0.5, record=record_text)
        else:
            diff = check_id = check_km = None
            level, conf_reasons, significant = None, ["No satellite reading passed the quality checks here, and no GPS station is inside the square."], False
            pri, pri_reason = priority(rate_vertical=None, significant=False, level=None, flood_zone_sfha=sfha, record=record_text)
            if cid not in opera_seen:
                level, conf_reasons = None, ["Not measured at this resolution: the satellite product's ~990 m pixel blocks skip some 1 km map squares. This is a gridding gap, not a sign that the ground here is stable."]
                pri_reason = "Not measured at this resolution (gridding gap); see the squares around it."

        needs_sensor = pri in ("urgent", "high", "watch") and cover_km > thresholds.gps_nearby_km
        counts["priority"][pri] = counts["priority"].get(pri, 0) + 1
        if level:
            counts["confidence"][level] = counts["confidence"].get(level, 0) + 1
        cell = {
            "id": cid, "lon": r(lon, 5), "lat": r(lat, 5),
            "rate": r(rate), "se": r(se), "src": sources, "sig": significant,
            "conf": level, "confWhy": conf_reasons,
            "pri": pri, "priWhy": pri_reason, "needsSensor": needs_sensor,
            "series": op["opera_series_mm"] if op and not op.get("opera_links_filled") else None,  # a bridged gap is not drawn as data (D-042)
            "gps": {"id": cover["station_id"], "km": r(cover_km, 1), "up": display_gps_rate(cover["up_mm_year"])[0], "flag": display_gps_rate(cover["up_mm_year"])[1], "y0": r(cover.get("start_decimal_year"), 0), "y1": r(cover.get("end_decimal_year"), 0)},
            "check": {"id": check_id, "km": r(check_km, 1), "diff": r(diff)} if check_id else None,
            "flood": {"zone": f.get("flood_zone"), "sub": f.get("zone_subtype"), "sfha": sfha},
            "well": {"km": r(ev.get("usgs_distance_km")), "dd": r(clean_dd(ev.get("groundwater_depth_change_ft")), 2)} if ev.get("usgs_site_id") else None,
            "ext": {"km": r(ev.get("extensometer_distance_km")), "c": r(ev.get("cumulative_compaction_change_ft"), 2)} if ev.get("nearest_extensometer_station") else None,
            "nisar": None if row.get("outside_nisar") else {"d": r(row.get("pair_los_displacement_mm")), "ok": row["in_main_connected_component"] and (row.get("coherence_median") or 0) >= thresholds.coherence_min and (row.get("valid_fraction") or 0) >= thresholds.valid_fraction_min},
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
        sensor_sites.append({"rank": site["rank"], "id": site["id"], "lon": r(site["lon"], 5), "lat": r(site["lat"], 5), "rate": c["rate"], "areaRate": r(site["area_rate"]), "conf": c["conf"], "gpsKm": c["gps"]["km"], "sfha": c["flood"]["sfha"], "zone": c["flood"]["zone"]})

    def check(source: dict, days: int) -> dict:
        xs, ys = [], []
        for row in source["cells"]:
            op = opera_cells.get(row["cell_id"])
            if op and row["pair_los_displacement_mm"] is not None and row["in_main_connected_component"] and (row["coherence_median"] or 0) >= 0.4 and (row["valid_fraction"] or 0) >= 0.5:
                xs.append(float(row["pair_los_displacement_mm"])); ys.append(op["opera_los_velocity_mm_year"] * days / 365.25)
        mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
        sx = sqrt(sum((x - mx) ** 2 for x in xs) / len(xs)); sy = sqrt(sum((y - my) ** 2 for y in ys) / len(ys))
        return {"cells": len(xs), "days": days, "noise_mm": sx, "signal_mm": sy, "r": sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (len(xs) * sx * sy)}

    chain_report = inventory["chain"]
    nisar_archive = {
        "passes": chain_report["date_count"],
        "pairs": chain_report["pair_count"],
        "first": chain_report["first_date"],
        "last": chain_report["last_date"],
        "processedPairs": sum(1 for granule in inventory["granules"] if granule.get("in_repo")),
        "retrieved": inventory["retrieved_utc"][:10],
        "inventory": relative(INVENTORY),
    }
    meta = {
        "status": "provisional_unreviewed",
        "record": {"start": data_start, "end": data_end, "dates": dates, "products": opera["product_count"]},
        "geometry": {"incidence_deg": INCIDENCE_DEG, "assumption": "vertical-only motion"},
        "thresholds": {"stable_mm_year": round(sig_threshold_vertical, 1), "gps_covered_km": thresholds.gps_nearby_km, "gps_blend_km": GPS_BLEND_KM},
        "counts": counts,
        "validation": {"stations": comparison["stats"]["station_count"], "r": comparison["stats"].get("pearson_r"), "typical_diff_mm_year": r(vertical_rate(comparison["stats"]["median_abs_residual_mm_year"]), 1), "points": [{"id": p["station_id"], "gps": r(p["gps_up_mm_year"]), "sat": r(vertical_rate(p["opera_los_mm_year"]))} for p in comparison["stations"]]},
        "nisar": {"pair": check(pair, 12), "chain": check(chain, 60)},
        "nisarArchive": nisar_archive,
        "reference": build["reference"],
        "sensors": sensor_sites,
        "nasaLayers": {k: v["meta"].get("source") for k, v in nasa.items()},
        "provenance": {"manifest": relative(MANIFEST)},
        "stations": {"total": len(all_stations), "deepSeated": sorted(s["station_id"] for s in all_stations if is_deep_seated(s["station_id"])), "rateWithheld": sorted(s["station_id"] for s in all_stations if display_gps_rate(s.get("up_mm_year"))[1])},
    }
    sites = {
        "gps": [{"id": s["station_id"], "lon": s["longitude"], "lat": s["latitude"], "up": display_gps_rate(s["up_mm_year"])[0], "flag": display_gps_rate(s["up_mm_year"])[1], "deepAnchorM": DEEP_SEATED_GNSS.get(s["station_id"], {}).get("anchor_depth_m"), "y0": s["start_decimal_year"], "y1": s["end_decimal_year"]} for s in all_stations],
        "ext": [{"id": s["station_id"], "name": s.get("station_name"), "lon": s["longitude"], "lat": s["latitude"], "c": s.get("cumulative_compaction_change"), "d0": s["first_observation"]["date"], "d1": s["last_observation"]["date"]} for s in extensometers],
        "wells": [{"id": s["site_id"], "name": s.get("site_name"), "lon": s["longitude"], "lat": s["latitude"], "dd": r(clean_dd(s.get("depth_change_ft")), 2), "t0": s["first_observation"]["time"][:10], "t1": s["last_observation"]["time"][:10]} for s in wells],
    }
    OUT.mkdir(parents=True, exist_ok=True)
    for stale in ("ledger.json",):
        (OUT / stale).unlink(missing_ok=True)
    for name, payload in (("cells.json", cells), ("meta.json", meta), ("sites.json", sites)):
        (OUT / name).write_text(json.dumps(payload, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
        log.wrote(OUT / name)
    log.write(MANIFEST, artifact_type="terragauge_web_export_manifest", command="python3 scripts/export_web.py", extra={"note": "Inputs marked tracked: false are regenerable intermediates; their hashes must match data/manifests/provisional_build.json."})
    print(json.dumps({"cells": len(cells), "counts": counts, "stable_threshold": sig_threshold_vertical, "model_error": model_error, "validation": comparison["stats"], "sensors": [(s["rank"], s["rate"], s["gpsKm"], s["zone"]) for s in sensor_sites]}, indent=1))


if __name__ == "__main__":
    main()

"""Export compact, precomputed JSON for the static TerraGauge website.

Run after scripts/build_provisional.py:  python3 scripts/export_web.py
All science logic runs here (in Python, via backend.decision); the website only
displays the results.
"""

from __future__ import annotations

import json
import sys
from math import sqrt
from pathlib import Path
from statistics import median

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.decision import classify_cell, classify_opera_velocity  # noqa: E402
from backend.detection import rate_uncertainty_mm_year  # noqa: E402
from backend.model import Thresholds  # noqa: E402
from backend.repository import cell_from_dict  # noqa: E402

DERIVED = Path("data/derived")
PROV = DERIVED / "provisional"
OUT = Path("web/public/data")
LAYERS = DERIVED / "nasa_layers"
SHORT = {"investigate_satellite_signal": "I", "add_ground_monitoring": "A", "context_only": "C", "review_time_matched_mismatch": "R", "insufficient_radar_evidence": "X"}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def r(value, digits=2):
    return None if value is None else round(float(value), digits)


def robust_sd(values: list[float]) -> float:
    center = median(values)
    return 1.4826 * median(abs(v - center) for v in values)


def main() -> None:
    thresholds = Thresholds()
    pair = load(PROV / "terragauge_houston_evidence_pair_20251102_20251114.json")
    chain = load(PROV / "terragauge_houston_evidence_chain_20251102_20260101.json")
    opera = load(PROV / "opera_houston_los_velocity_20160712_20210505.json")
    comparison = load(PROV / "opera_vs_houstonnet_comparison.json")
    build = load(PROV / "build_report.json")
    stations = load(DERIVED / "houstonnet_2024_summary.json")["stations"]
    extensometers = load(DERIVED / "usgs_houston_extensometer_compaction_2023.json")["stations"]
    wells = load(DERIVED / "usgs_houston_groundwater_2025-01-01_2026-11-07.json")["series"]
    flood = {row["cell_id"]: row for row in load(DERIVED / "fema_nfhl_houston_cell_context_2026-11-07.json")["cells"]}
    opera_cells = {row["cell_id"]: row for row in opera["cells"]}
    chain_cells = {row["cell_id"]: row for row in chain["cells"]}
    raw_pair = {row["cell_id"]: row for row in load(PROV / "nisar_gunw_houston_20251102_20251114_deramped.json")["cells"]}
    nasa = {}
    for name in ("nasadem", "dswx", "dist"):
        path = LAYERS / f"{name}_houston_cells.json"
        if path.is_file():
            artifact = load(path)
            nasa[name] = {"meta": {k: v for k, v in artifact.items() if k != "cells"}, "cells": {row["cell_id"]: row for row in artifact["cells"]}}

    reference_ids = set(opera.get("reference_cell_ids") or [])
    reference_velocities = [opera_cells[cid]["opera_los_velocity_mm_year"] for cid in reference_ids if cid in opera_cells]
    opera_noise = robust_sd(reference_velocities) if len(reference_velocities) >= 3 else None

    reasons: list[str] = []
    reason_index: dict[str, int] = {}

    def rid(text_list: list[str]) -> list[int]:
        out = []
        for text in text_list:
            if text not in reason_index:
                reason_index[text] = len(reasons)
                reasons.append(text)
            out.append(reason_index[text])
        return out

    cells, counts = [], {"opera": {}, "pair": {}, "chain": {}}
    for row in pair["cells"]:
        cid = row["cell_id"]
        ev = row["evidence"]
        pair_result = classify_cell(cell_from_dict(row), thresholds)
        chain_row = chain_cells[cid]
        chain_result = classify_cell(cell_from_dict(chain_row), thresholds)
        op = opera_cells.get(cid)
        op_label, op_reasons, op_threshold = classify_opera_velocity(
            velocity_mm_year=op["opera_los_velocity_mm_year"] if op else None,
            velocity_se_mm_year=op["opera_velocity_se_mm_year"] if op else None,
            noise_floor_mm_year=opera_noise, gps_distance_km=ev.get("gps_distance_km"), flood_exposed=row.get("flood_exposed"), thresholds=thresholds)
        for key, label in (("opera", op_label.value), ("pair", pair_result.label.value), ("chain", chain_result.label.value)):
            counts[key][label] = counts[key].get(label, 0) + 1
        f = flood.get(cid, {})
        cell = {
            "id": cid, "lon": r(row["longitude"], 5), "lat": r(row["latitude"], 5),
            "L": {"o": SHORT[op_label.value], "p": SHORT[pair_result.label.value], "c": SHORT[chain_result.label.value]},
            "R": {"o": rid(op_reasons), "p": rid(pair_result.reasons), "c": rid(chain_result.reasons)},
            "n": {"d": r(row["pair_los_displacement_mm"]), "raw": r(raw_pair.get(cid, {}).get("pair_los_displacement_before_deramp_mm")), "coh": r(row["coherence_median"], 3), "vf": r(row["valid_fraction"], 3), "main": row["in_main_connected_component"]},
            "ch": {"d": r(chain_row["pair_los_displacement_mm"]), "coh": r(chain_row["coherence_median"], 3), "vf": r(chain_row["valid_fraction"], 3)},
            "o": {"v": r(op["opera_los_velocity_mm_year"]), "se": r(op["opera_velocity_se_mm_year"]), "cum": r(op["opera_cumulative_los_mm"], 1), "s": op["opera_series_mm"]} if op else None,
            "f": {"z": f.get("flood_zone"), "sub": f.get("zone_subtype"), "x": f.get("flood_exposed")},
            "g": {"id": ev.get("nearest_gps_station"), "km": r(ev.get("gps_distance_km")), "up": ev.get("historic_gps_up_mm_year"), "y0": ev.get("historic_gps_start_year"), "y1": ev.get("historic_gps_end_year")},
            "w": {"id": ev.get("usgs_site_id"), "km": r(ev.get("usgs_distance_km")), "dd": r(ev.get("groundwater_depth_change_ft"))},
            "e": {"id": ev.get("nearest_extensometer_station"), "km": r(ev.get("extensometer_distance_km")), "c": r(ev.get("cumulative_compaction_change_ft"))},
        }
        for name, layer in nasa.items():
            value = layer["cells"].get(cid)
            if value:
                cell[name] = {k: r(v, 3) if isinstance(v, (int, float)) and not isinstance(v, bool) else v for k, v in value.items() if k not in ("cell_id", "longitude", "latitude")}
        cells.append(cell)

    # NISAR signal check: does the radar pair agree with the validated OPERA record?
    def check(source: dict, days: int) -> dict:
        xs, ys = [], []
        for row in source["cells"]:
            op = opera_cells.get(row["cell_id"])
            if op and row["pair_los_displacement_mm"] is not None and row["in_main_connected_component"] and (row["coherence_median"] or 0) >= 0.4 and (row["valid_fraction"] or 0) >= 0.5:
                xs.append(float(row["pair_los_displacement_mm"])); ys.append(op["opera_los_velocity_mm_year"] * days / 365.25)
        mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
        sx = sqrt(sum((x - mx) ** 2 for x in xs) / len(xs)); sy = sqrt(sum((y - my) ** 2 for y in ys) / len(ys))
        corr = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (len(xs) * sx * sy)
        return {"cells": len(xs), "days": days, "nisar_sd_mm": sx, "expected_signal_sd_mm": sy, "pearson_r_vs_opera": corr}

    pair_check, chain_check = check(pair, 12), check(chain, 60)
    sigma = pair["reference_scatter_mm"]
    detect = []
    for rate in (-5, -10, -20):
        n = next((k for k in range(3, 5000) if rate_uncertainty_mm_year(sigma, 12, k) <= abs(rate) / thresholds.detection_sigma), None)
        detect.append({"rate_mm_year": rate, "observations": n, "years": r((n - 1) * 12 / 365.25, 1) if n else None})

    meta = {
        "generated": "2026-11-08",
        "status": "provisional_unreviewed",
        "reasons": reasons,
        "thresholds": {"coherence_min": thresholds.coherence_min, "valid_fraction_min": thresholds.valid_fraction_min, "sigma_multiplier": thresholds.pair_signal_sigma_multiplier, "gps_nearby_km": thresholds.gps_nearby_km},
        "views": {
            "opera": {"title": "OPERA 2016–2021 motion", "dates": [opera["dates"][0], opera["dates"][-1]], "products": opera["product_count"], "noise_floor_mm_year": opera_noise, "threshold_mm_year": thresholds.pair_signal_sigma_multiplier * opera_noise if opera_noise else None, "counts": counts["opera"], "dates_all": opera["dates"]},
            "pair": {"title": "NISAR 12-day pair", "dates": ["2025-11-02", "2025-11-14"], "reference_scatter_mm": pair["reference_scatter_mm"], "reference_median_mm": pair["reference_median_mm"], "threshold_mm": thresholds.pair_signal_sigma_multiplier * pair["reference_scatter_mm"], "counts": counts["pair"]},
            "chain": {"title": "NISAR 60-day chain", "dates": ["2025-11-02", "2026-01-01"], "reference_scatter_mm": chain["reference_scatter_mm"], "reference_median_mm": chain["reference_median_mm"], "threshold_mm": thresholds.pair_signal_sigma_multiplier * chain["reference_scatter_mm"], "counts": counts["chain"]},
        },
        "reference": build["reference"],
        "signal_check": {"pair": pair_check, "chain": chain_check},
        "detectability": {"sigma_mm": sigma, "interval_days": 12, "rows": detect},
        "gps_validation": comparison["stats"] | {"incidence_deg_assumed": comparison["incidence_deg_assumed"], "method": comparison["method"], "limitations": comparison["limitations"]},
        "gps_validation_points": [{k: r(v, 2) if isinstance(v, float) else v for k, v in row.items()} for row in comparison["stations"]],
        "nasa_layers": {name: layer["meta"] for name, layer in nasa.items()},
        "limitations": {
            "opera": opera["limitations"],
            "nisar": pair["limitations"] + ["A best-fit plane was removed from each pair (deramp) before referencing; this removes long-wavelength ionospheric/atmospheric ramps and any real frame-wide planar motion."],
        },
    }
    sites = {
        "gps": [{"id": s["station_id"], "lon": s["longitude"], "lat": s["latitude"], "up": s["up_mm_year"], "y0": s["start_decimal_year"], "y1": s["end_decimal_year"], "ref": s["station_id"] in set(build["reference"]["reference_stations"])} for s in stations],
        "ext": [{"id": s["station_id"], "name": s.get("station_name"), "lon": s["longitude"], "lat": s["latitude"], "c": s.get("cumulative_compaction_change"), "d0": s["first_observation"]["date"], "d1": s["last_observation"]["date"], "interval": s.get("compaction_interval")} for s in extensometers],
        "wells": [{"id": s["site_id"], "name": s.get("site_name"), "lon": s["longitude"], "lat": s["latitude"], "dd": r(s.get("depth_change_ft")), "t0": s["first_observation"]["time"][:10], "t1": s["last_observation"]["time"][:10]} for s in wells],
    }
    ledger = []
    for path in sorted((DERIVED.parent / "manifests").glob("*.json")):
        ledger.append({"manifest": path.name, "record": load(path)})
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "cells.json").write_text(json.dumps(cells, separators=(",", ":")), encoding="utf-8")
    (OUT / "meta.json").write_text(json.dumps(meta, separators=(",", ":")), encoding="utf-8")
    (OUT / "sites.json").write_text(json.dumps(sites, separators=(",", ":")), encoding="utf-8")
    (OUT / "ledger.json").write_text(json.dumps(ledger, separators=(",", ":")), encoding="utf-8")
    print(json.dumps({"cells": len(cells), "counts": counts, "opera_noise": opera_noise, "pair_check": pair_check, "chain_check": chain_check, "detect": detect}, indent=1))


if __name__ == "__main__":
    main()

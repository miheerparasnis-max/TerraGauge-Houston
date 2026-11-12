"""Build the provisional (clearly labelled, unreviewed) TerraGauge Houston datasets.

Run from the repository root:  python3 scripts/build_provisional.py
Swap PROVISIONAL_REFERENCE_BBOX for a team-reviewed region and re-run with
--reference-status reviewed when the stable reference is approved.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.decision import classify_cell  # noqa: E402
from backend.ingestion.houston import build_houston_evidence  # noqa: E402
from backend.ingestion.provisional import chain_sum, compare_opera_gps, deramp_pair, merge_frames, nearest_cell_ids, opera_series, stable_gps_reference  # noqa: E402
from backend.model import Thresholds  # noqa: E402
from backend.repository import cell_from_dict  # noqa: E402

DERIVED = Path("data/derived")
OUT = DERIVED / "provisional"
PAIRS = ["20251102_20251114", "20251114_20251126", "20251126_20251208", "20251208_20251220", "20251220_20260101"]
# Provisional reference: cells at half of the long-history HoustonNet stations
# whose published vertical rate is within +/-1 mm/yr. The other half are held
# out so the OPERA-vs-GPS comparison is not circular. The single-patch
# candidate in terragauge_reference_review_candidates_2026-11-07.json is in
# farmland where OPERA has too few coherent pixels in several products.
MAX_ABS_UP = 1.0


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def save(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")


def summarize(evidence: dict) -> dict:
    counts: dict[str, int] = {}
    for row in evidence["cells"]:
        label = classify_cell(cell_from_dict(row), Thresholds()).label.value
        counts[label] = counts.get(label, 0) + 1
    return counts


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference-status", default="provisional_unreviewed", choices=["provisional_unreviewed", "reviewed"])
    args = parser.parse_args()
    stations = load(DERIVED / "houstonnet_2024_summary.json")["stations"]
    reference_stations, held_out = stable_gps_reference(stations, MAX_ABS_UP)
    deramped = []
    for name in PAIRS:
        artifact = deramp_pair(load(DERIVED / f"nisar_gunw_houston_{name}_pair_cells.json"))
        save(OUT / f"nisar_gunw_houston_{name}_deramped.json", artifact)
        deramped.append(artifact)
    save(OUT / "nisar_gunw_houston_chain_20251102_20260101_deramped.json", chain_sum(deramped))

    common = dict(
        houstonnet_path=DERIVED / "houstonnet_2024_summary.json",
        groundwater_path=DERIVED / "usgs_houston_groundwater_2025-01-01_2026-11-07.json",
        fema_path=DERIVED / "fema_nfhl_usgs_station_join_2026-11-07.json",
        cell_flood_context_path=DERIVED / "fema_nfhl_houston_cell_context_2026-11-07.json",
        compaction_path=DERIVED / "usgs_houston_extensometer_compaction_2023.json",
        opera_path=DERIVED / "opera_disp_houston_20160712_20161109_pair_cells.json",
        reference_status=args.reference_status,
    )
    report = {"reference": {"method": f"Cells at HoustonNet GPS stations with at least 10 years of data and a published vertical rate within ±{MAX_ABS_UP:g} mm/yr; every other such station is held out for checking", "reference_stations": [s["station_id"] for s in reference_stations], "held_out_stable_stations": [s["station_id"] for s in held_out]}}
    for key, source in (("pair_20251102_20251114", OUT / "nisar_gunw_houston_20251102_20251114_deramped.json"), ("chain_20251102_20260101", OUT / "nisar_gunw_houston_chain_20251102_20260101_deramped.json")):
        nisar_cells = load(source)["cells"]
        evidence = build_houston_evidence(nisar_path=source, reference_cell_ids=nearest_cell_ids(reference_stations, nisar_cells), **common)
        evidence["reference_method"] = report["reference"]["method"]
        save(OUT / f"terragauge_houston_evidence_{key}.json", evidence)
        report[key] = {"reference_median_mm": evidence["reference_median_mm"], "reference_scatter_mm": evidence["reference_scatter_mm"], "reference_cells": evidence["reference_cell_count"], "labels": summarize(evidence)}

    operas = [load(path) for path in sorted(DERIVED.glob("opera_disp_houston_*_pair_cells.json"))]
    # South Houston: add the neighbouring frame F38239 where it exists
    # (scripts/fetch_opera_south.py), lined up on the overlap band.
    south = {}
    for path in sorted((DERIVED / "opera_f38239").glob("opera_disp_f38239_*_pair_cells.json")):
        a = load(path)
        south[(a["parameters"]["reference_date"], a["parameters"]["secondary_date"])] = a
    merges = []
    for k, artifact in enumerate(operas):
        key = (artifact["parameters"]["reference_date"], artifact["parameters"]["secondary_date"])
        if key in south:
            operas[k], stats = merge_frames(artifact, south[key])
            merges.append({"dates": list(key), **stats})
    if merges:
        report_frames = {"frame": "F38239", "products_merged": sum(1 for m in merges if m["added"]), "products_found": len(merges), "per_product": merges}
    else:
        report_frames = None
    velocity = opera_series(operas, reference_cell_ids=nearest_cell_ids(reference_stations, operas[0]["cells"]))
    velocity["reference_method"] = report["reference"]["method"]
    for stale in OUT.glob("opera_houston_los_velocity_*.json"):
        stale.unlink()
    save(OUT / "opera_houston_los_velocity.json", velocity)
    comparison = compare_opera_gps(velocity, stations, exclude_station_ids={s["station_id"] for s in reference_stations})
    save(OUT / "opera_vs_houstonnet_comparison.json", comparison)
    report["opera"] = {"cells": len(velocity["cells"]), "products": velocity["product_count"], "gps_comparison": comparison["stats"], "south_frame": report_frames}
    save(OUT / "build_report.json", report)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

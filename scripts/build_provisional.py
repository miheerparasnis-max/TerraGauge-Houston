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

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.decision import classify_cell  # noqa: E402
from backend.ingestion.houston import build_houston_evidence  # noqa: E402
from backend.ingestion.provisional import chain_sum, compare_opera_gps, deramp_pair, nearest_cell_ids, opera_series, stable_gps_reference  # noqa: E402
from backend.model import Thresholds  # noqa: E402
from backend.provenance import ProvenanceLog  # noqa: E402
from backend.publish_guard import assert_publishable  # noqa: E402
from backend.repository import cell_from_dict  # noqa: E402

DERIVED = ROOT / "data" / "derived"
OUT = DERIVED / "provisional"
MANIFEST = ROOT / "data" / "manifests" / "provisional_build.json"
PAIRS = ["20251102_20251114", "20251114_20251126", "20251126_20251208", "20251208_20251220", "20251220_20260101"]
# Provisional reference: cells at half of the long-history HoustonNet stations
# whose published vertical rate is within +/-1 mm/yr. The other half are held
# out so the OPERA-vs-GPS comparison is not circular. The single-patch
# candidate in terragauge_reference_review_candidates_2026-11-07.json is in
# farmland where OPERA has too few coherent pixels in several products.
MAX_ABS_UP = 1.0


LOG: ProvenanceLog | None = None  # set by main(); records every input and output with SHA-256


def load(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert_publishable(payload, str(path))
    if LOG is not None:
        LOG.read(path)
    return payload


def save(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    if LOG is not None:
        LOG.wrote(path)


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
    global LOG
    LOG = ProvenanceLog(ROOT)
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
    velocity = opera_series(operas, reference_cell_ids=nearest_cell_ids(reference_stations, operas[0]["cells"]))
    velocity["reference_method"] = report["reference"]["method"]
    save(OUT / "opera_houston_los_velocity_20160712_20210505.json", velocity)
    comparison = compare_opera_gps(velocity, stations, exclude_station_ids={s["station_id"] for s in reference_stations})
    save(OUT / "opera_vs_houstonnet_comparison.json", comparison)
    report["opera"] = {"cells": len(velocity["cells"]), "products": velocity["product_count"], "gps_comparison": comparison["stats"]}
    save(OUT / "build_report.json", report)
    for path in (value for value in common.values() if isinstance(value, Path)):
        LOG.read(path)  # read directly by build_houston_evidence
    LOG.write(MANIFEST, artifact_type="terragauge_provisional_build_manifest", command="python3 scripts/build_provisional.py", extra={"note": "Outputs marked tracked: false are gitignored regenerable intermediates; scripts/export_web.py reads two of them and records the same hashes."})
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

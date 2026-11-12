"""Freeze the OPERA predictor for the pre-registered OPERA -> NISAR prediction test.

Writes the per-cell OPERA LOS rate over the predictor window in
config/prediction_test.json (ending before the NISAR test window, so the
predictor cannot see the test period). Run once and commit before any NISAR
pair after the window start is processed:

    python3 scripts/freeze_prediction.py
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.ingestion.provisional import opera_series, region_cell_ids  # noqa: E402

CONFIG = ROOT / "config" / "prediction_test.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    config = load(CONFIG)
    predictor, target = config["predictor"], config["target"]
    if predictor["end"] >= target["window_start"]:
        sys.exit("The predictor window must end before the NISAR test window starts.")
    prereg = load(ROOT / "config" / "preregistration.json")["reference"]
    stations = {s["station_id"]: s for s in load(ROOT / "data" / "derived" / "houstonnet_2024_summary.json")["stations"]}
    operas = [load(p) for p in sorted((ROOT / "data" / "derived").glob("opera_disp_houston_*_pair_cells.json"))]
    operas = [a for a in operas if predictor["start"] <= a["parameters"]["reference_date"] and a["parameters"]["secondary_date"] <= predictor["end"]]
    reference = region_cell_ids(stations, prereg["reference_stations"], operas[0]["cells"], float(prereg["region_a_radius_km"]))
    series = opera_series(operas, reference_cell_ids=reference)
    if (series["dates"][0], series["dates"][-1]) != (predictor["start"], predictor["end"]):
        sys.exit(f"Chain covers {series['dates'][0]} to {series['dates'][-1]}, not the registered window.")
    out = {
        "artifact_type": "terragauge_prediction_predictor",
        "config": str(CONFIG.relative_to(ROOT)),
        "config_sha256": hashlib.sha256(CONFIG.read_bytes()).hexdigest(),
        "window": [series["dates"][0], series["dates"][-1]],
        "products": series["product_count"],
        "reference_cell_ids": sorted(reference),
        "cells": [{"cell_id": c["cell_id"], "opera_los_velocity_mm_year": round(c["opera_los_velocity_mm_year"], 3)} for c in series["cells"]],
        "limitations": ["LOS rate relative to region A; positive = toward the satellite (supported empirically, see the fact-check ledger row 4)."],
    }
    path = ROOT / predictor["frozen_file"]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=0) + "\n", encoding="utf-8")
    print(f"{len(out['cells'])} cells, {out['products']} products, {out['window'][0]} to {out['window'][1]} -> {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

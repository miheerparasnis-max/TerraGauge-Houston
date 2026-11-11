"""Build the hazard views (drought, ground bending, flood) and their tests.

Writes data/derived/provisional/hazards.json. See backend/hazards.py.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.hazards import bending_stability, drought_and_bending, drought_backtest, harvey_check  # noqa: E402

DERIVED = Path(os.environ.get("TERRAGAUGE_DERIVED", ROOT / "data" / "derived"))
PROV = DERIVED / "provisional"


def main() -> None:
    velocity = json.loads((PROV / "opera_houston_los_velocity.json").read_text(encoding="utf-8"))
    water_path = DERIVED / "nasa_layers" / "dswx_houston_cells.json"
    water = set()
    if water_path.is_file():
        water = {r["cell_id"] for r in json.loads(water_path.read_text(encoding="utf-8"))["cells"] if r["water_fraction"] >= 0.5}
    cells = drought_and_bending(velocity, exclude=water)
    tests = {"drought": drought_backtest(velocity), "bending": bending_stability(velocity)}
    harvey_path = ROOT / "data" / "raw" / "harvey_usgs_high_water_marks.json"
    if harvey_path.is_file():
        flood = json.loads((DERIVED / "fema_nfhl_houston_cell_context_2026-11-07.json").read_text(encoding="utf-8"))
        zone_of = {r["cell_id"]: (r.get("flood_zone"), r.get("zone_subtype")) for r in flood["cells"]}
        marks = json.loads(harvey_path.read_text(encoding="utf-8"))["marks"]
        tests["harvey"] = harvey_check(marks, velocity["cells"], zone_of)
    else:
        print("No Harvey flood marks yet (run scripts/fetch_harvey.py); skipping the Harvey check.")
    (PROV / "hazards.json").write_text(json.dumps({"tests": tests, "cells": cells}, separators=(",", ":")), encoding="utf-8")
    print(json.dumps(tests, indent=1))


if __name__ == "__main__":
    main()

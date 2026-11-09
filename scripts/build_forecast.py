"""Train, test and run the ML forecast (needs scikit-learn).

    python3 scripts/build_forecast.py      # after scripts/build_provisional.py

Writes data/derived/provisional/ml_forecast.json; scripts/export_web.py picks it up.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.forecast import train_and_forecast  # noqa: E402

PROV = Path("data/derived/provisional")
SPLIT_DATE = "2021-05-05"  # first half of the record trains, second half tests


DERIVED = Path("data/derived")


def static_features() -> dict[str, dict[str, float]]:
    """Inputs that don't change over the forecast period and don't leak the answer."""
    out: dict[str, dict[str, float]] = {}
    flood = json.loads((DERIVED / "fema_nfhl_houston_cell_context_2026-11-07.json").read_text(encoding="utf-8"))
    for row in flood["cells"]:
        out.setdefault(row["cell_id"], {})["flood_zone_high_risk"] = 1.0 if row.get("flood_exposed") else 0.0
    layers = {"nasadem": ("elevation_m", "elevation_m"), "dswx": ("water_fraction", "surface_water_share"), "dist": ("disturbed_fraction", "land_disturbance_share")}
    for name, (key, feature) in layers.items():
        path = DERIVED / "nasa_layers" / f"{name}_houston_cells.json"
        if path.is_file():
            for row in json.loads(path.read_text(encoding="utf-8"))["cells"]:
                out.setdefault(row["cell_id"], {})[feature] = float(row[key])
    return out


def main() -> None:
    velocity = json.loads((PROV / "opera_houston_los_velocity.json").read_text(encoding="utf-8"))
    use_static = "--no-static" not in sys.argv
    result = train_and_forecast(velocity, SPLIT_DATE, static=static_features() if use_static else None)
    (PROV / "ml_forecast.json").write_text(json.dumps(result, separators=(",", ":")), encoding="utf-8")
    print(json.dumps(result["horizon_bands"], indent=1))
    summary = {k: result[k] for k in ("train_window", "test_window", "tested_horizon_years", "cells", "scores", "best_baseline", "interval_coverage_10_90", "passes", "feature_importance")}
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()

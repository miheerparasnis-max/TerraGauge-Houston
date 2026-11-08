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


def main() -> None:
    velocity = json.loads((PROV / "opera_houston_los_velocity.json").read_text(encoding="utf-8"))
    result = train_and_forecast(velocity, SPLIT_DATE)
    (PROV / "ml_forecast.json").write_text(json.dumps(result, separators=(",", ":")), encoding="utf-8")
    summary = {k: result[k] for k in ("train_window", "test_window", "tested_horizon_years", "cells", "scores", "best_baseline", "interval_coverage_10_90", "passes", "feature_importance")}
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()

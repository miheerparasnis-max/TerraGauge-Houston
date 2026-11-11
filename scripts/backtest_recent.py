"""Out-of-time backtest: pretend it's an earlier date and predict up to the latest data.

For each cutoff (e.g. March 2025), the model may only use satellite data up to
that date. It learns from the past ("given window A, what happened next?"),
then predicts the change from the cutoff to the newest observation, which we
compare with what really happened.

    python3 scripts/backtest_recent.py    # needs numpy and scikit-learn

Writes data/derived/provisional/backtest_recent.json.
"""

from __future__ import annotations

import json
import sys
from math import cos, radians
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402

from backend.forecast import INCIDENCE_DEG, _decimal_year, _level_at, _model, window_features  # noqa: E402

PROV = Path("data/derived/provisional")
sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_forecast import static_features  # noqa: E402

CUTOFFS = ["2025-03-27", "2024-04-01", "2023-04-07", "2022-03-19", "2021-05-05"]
MAX_WINDOW_YEARS = 4.8


def main() -> None:
    velocity = json.loads((PROV / "opera_houston_los_velocity.json").read_text(encoding="utf-8"))
    dates = velocity["dates"]
    times = np.array([_decimal_year(d) for d in dates])
    cells = velocity["cells"]
    series = np.array([c["opera_series_mm"] for c in cells], dtype=float) / cos(radians(INCIDENCE_DEG))
    lon = np.array([c["longitude"] for c in cells]); lat = np.array([c["latitude"] for c in cells])
    static = static_features()
    names = sorted({k for row in static.values() for k in row})
    S = np.array([[static.get(c["cell_id"], {}).get(k, np.nan) for k in names] for c in cells], dtype=float)
    end = len(dates) - 1
    results = []
    for cutoff in CUTOFFS:
        c = dates.index(cutoff)
        horizon = times[end] - times[c]
        # Training example: features from the window ending at (cutoff - horizon),
        # target = what happened over the next `horizon` years, up to the cutoff.
        train_end = int(np.searchsorted(times, times[c] - horizon, side="right") - 1)
        # The ML model needs an earlier "features -> what happened next" example
        # that fits entirely before the cutoff; for long horizons there isn't one.
        ml_ok = train_end >= 6
        window = min(MAX_WINDOW_YEARS, times[train_end] - times[0]) if ml_ok else min(MAX_WINDOW_YEARS, times[c] - times[0])
        test_start = int(np.searchsorted(times, times[c] - window))
        X_now = np.c_[window_features(np, times, series, lon, lat, test_start, c + 1), S]
        train_start = int(np.searchsorted(times, times[train_end] - window)) if ml_ok else 0
        if ml_ok:
            X_train = np.c_[window_features(np, times, series, lon, lat, train_start, train_end + 1), S]
            y_train = _level_at(np, times[: c + 1], series[:, : c + 1], times[c]) - _level_at(np, times[: c + 1], series[:, : c + 1], times[train_end])
            predicted = _model("mean").fit(X_train, y_train).predict(X_now)
        else:
            predicted = np.full(len(cells), np.nan)
        actual = _level_at(np, times, series, times[end]) - _level_at(np, times[: c + 1], series[:, : c + 1], times[c])
        past_rate = X_now[:, 0] * horizon
        long_rate = np.linalg.lstsq(np.c_[np.ones(c + 1), times[: c + 1]], series[:, : c + 1].T, rcond=None)[0][1]
        long_term = long_rate * horizon
        fast = long_rate <= -10
        err = np.abs(actual - predicted)
        long_err = np.abs(actual - long_term)
        results.append({
            "cutoff": cutoff,
            "predict_to": dates[end],
            "years_ahead": round(float(horizon), 2),
            "ml_training_window": [dates[train_start], dates[train_end]] if ml_ok else None,
            "cells": int(len(actual)),
            "ml_typical_error_cm": round(float(np.median(err)) / 10, 2) if ml_ok else None,
            "long_term_rate_typical_error_cm": round(float(np.median(long_err)) / 10, 2),
            "long_term_rate_p80_error_cm": round(float(np.quantile(long_err, 0.8)) / 10, 2),
            "fast_long_term_error_cm": round(float(np.median(long_err[fast])) / 10, 2),
            "past_rate_typical_error_cm": round(float(np.median(np.abs(actual - past_rate))) / 10, 2),
            "no_motion_typical_error_cm": round(float(np.median(np.abs(actual))) / 10, 2),
            "fast_ml_error_cm": round(float(np.median(err[fast])) / 10, 2) if ml_ok else None,
            "fast_past_rate_error_cm": round(float(np.median(np.abs(actual - past_rate)[fast])) / 10, 2),
            "long_term_within_2cm_pct": round(float(np.mean(long_err <= 20)) * 100, 1),
            "ml_correlation": round(float(np.corrcoef(actual, predicted)[0, 1]), 3) if ml_ok else None,
            "long_term_correlation": round(float(np.corrcoef(actual, long_term)[0, 1]), 3),
            "actual_median_cm": round(float(np.median(actual)) / 10, 2),
            "ml_predicted_median_cm": round(float(np.median(predicted)) / 10, 2) if ml_ok else None,
            "long_term_predicted_median_cm": round(float(np.median(long_term)) / 10, 2),
            "fast_actual_median_cm": round(float(np.median(actual[fast])) / 10, 2),
            "fast_ml_predicted_median_cm": round(float(np.median(predicted[fast])) / 10, 2) if ml_ok else None,
            "fast_long_term_predicted_median_cm": round(float(np.median(long_term[fast])) / 10, 2),
        })
        print(json.dumps(results[-1]))
    (PROV / "backtest_recent.json").write_text(json.dumps({"artifact_type": "terragauge_out_of_time_backtest", "method": __doc__.strip(), "results": results}, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()

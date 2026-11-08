"""Machine-learning forecast of each cell's future sinking rate, with an honest test.

Question: given a cell's satellite record over one ~5-year window, how fast
will it move over the NEXT ~5 years?

Training/test design (no peeking at the future):
- Features come only from the earlier window (e.g. 2016-07 to 2021-05):
  overall rate, early-half rate, late-half rate, acceleration (late - early),
  scatter of the record around its trend, the median rate and acceleration of
  squares within 3 km, and location.
- Target is the least-squares rate over the later window (2021-05 to 2026-03).
- Evaluation uses 5-fold *spatial block* cross-validation (~10 km blocks), so
  the model is always scored on parts of the city it did not train on.
- It is compared with simple baselines: no motion, "the past rate continues",
  a damped past rate, and the neighbourhood rate. It is only used if it beats
  all of them.

Forecast: the final model is retrained on all cells and applied to features
from the most recent window of the same length, giving the expected average
rate for the next ~5 years. Ranges come from quantile models (10th/90th
percentile) whose coverage is checked in the same cross-validation.
Ground-water, compaction and GPS rates are NOT used as features because their
records overlap the target period (that would leak the answer).
"""

from __future__ import annotations

from datetime import date
from math import cos, radians
from typing import Any

INCIDENCE_DEG = 38.0


def _decimal_year(value: str) -> float:
    d = date.fromisoformat(value[:10])
    start = date(d.year, 1, 1)
    return d.year + (d - start).days / (date(d.year + 1, 1, 1) - start).days


def _slopes(np, times, series, start: int, stop: int):
    window = times[start:stop]
    design = np.c_[np.ones(len(window)), window]
    coef = np.linalg.lstsq(design, series[:, start:stop].T, rcond=None)[0]
    fitted = (design @ coef).T
    return coef[1], (series[:, start:stop] - fitted).std(axis=1)


def _neighbourhood(np, lon, lat, values, radius_km: float = 3.0):
    size = 0.05
    buckets: dict[tuple[int, int], list[int]] = {}
    for i, (x, y) in enumerate(zip(lon, lat)):
        buckets.setdefault((int(x // size), int(y // size)), []).append(i)
    out = np.full(len(values), np.nan)
    for i, (x, y) in enumerate(zip(lon, lat)):
        bx, by = int(x // size), int(y // size)
        idx = np.array([j for dx in (-1, 0, 1) for dy in (-1, 0, 1) for j in buckets.get((bx + dx, by + dy), []) if j != i], dtype=int)
        if idx.size == 0:
            continue
        near = idx[np.hypot((lon[idx] - x) * 96.5, (lat[idx] - y) * 111.0) <= radius_km]
        if near.size >= 3:
            out[i] = np.median(values[near])
    return out


FEATURES = ["rate", "rate_first_half", "rate_second_half", "acceleration", "scatter", "area_rate", "area_acceleration", "lon", "lat"]


def window_features(np, times, series, lon, lat, start: int, stop: int):
    middle = start + (stop - start) // 2
    rate, scatter = _slopes(np, times, series, start, stop)
    first, _ = _slopes(np, times, series, start, middle + 1)
    second, _ = _slopes(np, times, series, middle, stop)
    acceleration = second - first
    area_rate = _neighbourhood(np, lon, lat, rate)
    area_acc = _neighbourhood(np, lon, lat, acceleration)
    # Isolated cells (fewer than 3 neighbours within 3 km) fall back to their own values.
    area_rate = np.where(np.isnan(area_rate), rate, area_rate)
    area_acc = np.where(np.isnan(area_acc), acceleration, area_acc)
    return np.c_[rate, first, second, acceleration, scatter, area_rate, area_acc, lon, lat]


def _model(kind: str, alpha: float | None = None):
    from sklearn.ensemble import HistGradientBoostingRegressor

    params = dict(max_iter=300, learning_rate=0.05, max_leaf_nodes=31, min_samples_leaf=40, l2_regularization=1.0, random_state=0)
    if kind == "quantile":
        return HistGradientBoostingRegressor(loss="quantile", quantile=alpha, **params)
    return HistGradientBoostingRegressor(**params)


def train_and_forecast(velocity: dict[str, Any], split_date: str, folds: int = 5, block_deg: float = 0.1, seed: int = 0) -> dict[str, Any]:
    import numpy as np

    dates = velocity["dates"]
    times = np.array([_decimal_year(d) for d in dates])
    cells = velocity["cells"]
    projection = cos(radians(INCIDENCE_DEG))
    series = np.array([c["opera_series_mm"] for c in cells], dtype=float) / projection  # vertical mm
    lon = np.array([c["longitude"] for c in cells], dtype=float)
    lat = np.array([c["latitude"] for c in cells], dtype=float)
    split = max(i for i, d in enumerate(dates) if d <= split_date)
    if split < 6 or len(dates) - split < 6:
        raise ValueError("need at least six dates on each side of the split")
    span_train = times[split] - times[0]
    X = window_features(np, times, series, lon, lat, 0, split + 1)
    y, _ = _slopes(np, times, series, split, len(dates))

    blocks = np.floor(lon / block_deg).astype(int) * 100000 + np.floor(lat / (block_deg * 0.9)).astype(int)
    unique = np.unique(blocks)
    assignment = dict(zip(unique, np.random.default_rng(seed).integers(0, folds, len(unique))))
    fold = np.array([assignment[b] for b in blocks])
    pred, low, high = np.zeros_like(y), np.zeros_like(y), np.zeros_like(y)
    for f in range(folds):
        train, test = fold != f, fold == f
        if test.sum() == 0 or train.sum() < 50:
            continue
        pred[test] = _model("mean").fit(X[train], y[train]).predict(X[test])
        low[test] = _model("quantile", 0.1).fit(X[train], y[train]).predict(X[test])
        high[test] = _model("quantile", 0.9).fit(X[train], y[train]).predict(X[test])

    def score(p):
        err = y - p
        fast = X[:, 0] <= -10
        return {"median_abs_error": float(np.median(np.abs(err))), "mean_abs_error": float(np.mean(np.abs(err))), "correlation": float(np.corrcoef(y, p)[0, 1]) if np.std(p) > 0 else None, "fast_median_abs_error": float(np.median(np.abs(err[fast]))) if fast.any() else None}

    rate = X[:, 0]
    damping = float(np.sum(rate * y) / np.sum(rate * rate))
    baselines = {
        "no_motion": score(np.zeros_like(y)),
        "past_rate_continues": score(rate),
        "damped_past_rate": score(damping * rate),
        "area_rate": score(X[:, 5]),
    }
    model_score = score(pred)
    raw_coverage = float(np.mean((y >= low) & (y <= high)))
    # Conformal calibration: a symmetric band around the forecast whose
    # half-width is proportional to the quantile models' spread, scaled so
    # that 80% of held-out truths fall inside it.
    half = np.maximum((high - low) / 2.0, 0.25)
    scale = float(np.quantile(np.abs(y - pred) / half, 0.8))
    coverage = float(np.mean(np.abs(y - pred) <= scale * half))
    best_baseline = min(baselines, key=lambda k: baselines[k]["median_abs_error"])
    passes = model_score["median_abs_error"] < baselines[best_baseline]["median_abs_error"] * 0.9

    # Final models on all cells, applied to the most recent window of equal length.
    start = int(np.searchsorted(times, times[-1] - span_train))
    X_now = window_features(np, times, series, lon, lat, start, len(dates))
    final = _model("mean").fit(X, y)
    q10 = _model("quantile", 0.1).fit(X, y)
    q90 = _model("quantile", 0.9).fit(X, y)
    future_rate = final.predict(X_now)
    future_half = scale * np.maximum((q90.predict(X_now) - q10.predict(X_now)) / 2.0, 0.25)
    future_low, future_high = future_rate - future_half, future_rate + future_half
    horizon_years = float(times[-1] - times[split])
    importances = None
    try:
        from sklearn.inspection import permutation_importance

        # In-sample diagnostic: which inputs the final model leans on most.
        result = permutation_importance(final, X, y, n_repeats=3, random_state=seed, scoring="neg_median_absolute_error")
        importances = {name: float(v) for name, v in zip(FEATURES, result.importances_mean)}
    except Exception:  # pragma: no cover - optional diagnostic
        pass

    return {
        "artifact_type": "terragauge_ml_forecast",
        "status": "provisional",
        "method": __doc__.strip().split("\n\n")[1] if __doc__ else "",
        "model": "Gradient-boosted trees (scikit-learn HistGradientBoostingRegressor) for the mean; quantile versions for the 10th and 90th percentiles.",
        "features": FEATURES,
        "train_window": [dates[0], dates[split]],
        "test_window": [dates[split], dates[-1]],
        "forecast_features_window": [dates[start], dates[-1]],
        "tested_horizon_years": horizon_years,
        "cells": int(len(y)),
        "folds": folds,
        "scores": {"model": model_score, **baselines},
        "best_baseline": best_baseline,
        "interval_coverage_raw": raw_coverage,
        "interval_scale": scale,
        "interval_coverage_10_90": coverage,
        "passes": bool(passes),
        "feature_importance": importances,
        "forecast_base_date": dates[-1],
        "cell_forecasts": [
            {"cell_id": c["cell_id"], "rate_mm_year": float(r), "low_mm_year": float(lo), "high_mm_year": float(hi), "recent_rate_mm_year": float(X_now[i, 0])}
            for i, (c, r, lo, hi) in enumerate(zip(cells, future_rate, future_low, future_high))
        ],
        "limitations": [
            f"Tested only up to {horizon_years:.1f} years ahead; years beyond that are not offered.",
            "Assumes the next five years behave like the last ten (no major change in groundwater rules or pumping).",
            "Rates are vertical, converted from the satellite's slanted view assuming the ground moves mostly up and down.",
            "Ranges are calibrated so that 80% of held-out test cells fell inside them; they are not a guarantee for any single square.",
        ],
    }

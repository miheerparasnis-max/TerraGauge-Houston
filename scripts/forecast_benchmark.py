"""Walk-forward benchmark of forecasting methods (the test that picks TerraGauge's forecast).

For every past date from mid-2018 on, each method may use ONLY satellite data
up to that date, and predicts each square's change in ground level 1, 2, 3
and 4 years later. Predictions are compared with what actually happened
(smoothed levels). Machine-learning models are trained only on earlier
"past -> what happened next" examples whose outcome was known by that date.

    python3 scripts/forecast_benchmark.py          # numpy; scikit-learn for the ML rows

Writes data/derived/provisional/forecast_benchmark.json, used by export_web.py.
"""

from __future__ import annotations

import json
import math
import os
import sys
from datetime import date
from pathlib import Path

import numpy as np

ROOT = Path(os.environ.get("TERRAGAUGE_DERIVED", "data/derived"))
OUT = ROOT / "provisional" / "forecast_benchmark.json"
COS = math.cos(math.radians(38.0))
HORIZONS = [1, 2, 3, 4, 5]
CHOSEN = "seasonal_area"


def dyear(s: str) -> float:
    d = date.fromisoformat(s[:10]); a = date(d.year, 1, 1)
    return d.year + (d - a).days / (date(d.year + 1, 1, 1) - a).days


v = json.loads((ROOT / "provisional" / "opera_houston_los_velocity.json").read_text())
DATES = v["dates"]; T = np.array([dyear(x) for x in DATES]); CELLS = v["cells"]
S = np.array([c["opera_series_mm"] for c in CELLS], float) / COS
LON = np.array([c["longitude"] for c in CELLS]); LAT = np.array([c["latitude"] for c in CELLS])
N, E = S.shape


def neighbours(radius_km: float = 3.0):
    size = 0.05; buckets: dict = {}
    for i, (x, y) in enumerate(zip(LON, LAT)):
        buckets.setdefault((int(x // size), int(y // size)), []).append(i)
    out = []
    for i, (x, y) in enumerate(zip(LON, LAT)):
        bx, by = int(x // size), int(y // size)
        idx = np.array([j for dx in (-1, 0, 1) for dy in (-1, 0, 1) for j in buckets.get((bx + dx, by + dy), []) if j != i], int)
        out.append(idx[np.hypot((LON[idx] - x) * 96.5, (LAT[idx] - y) * 111) <= radius_km] if idx.size else idx)
    return out


NEIGH = neighbours()


def area(values):
    out = np.array([np.median(values[n]) if len(n) >= 3 else np.nan for n in NEIGH])
    return np.where(np.isnan(out), values, out)


def level(t_target, upto=None, half=0.6):
    tt, ss = (T, S) if upto is None else (T[: upto + 1], S[:, : upto + 1])
    m = np.abs(tt - t_target) <= half
    if m.sum() < 3:
        m = np.zeros(len(tt), bool); m[np.argsort(np.abs(tt - t_target))[:3]] = True
    A = np.c_[np.ones(m.sum()), tt[m] - t_target]
    return np.linalg.lstsq(A, ss[:, m].T, rcond=None)[0][0]


def wls(c, start=0, w=None, seasonal=False):
    tt = T[start : c + 1]; x = tt - tt.mean()
    cols = [np.ones_like(x), x] + ([np.sin(2 * np.pi * tt), np.cos(2 * np.pi * tt)] if seasonal else [])
    A = np.column_stack(cols); w = np.ones_like(x) if w is None else w; sw = np.sqrt(w)
    return np.linalg.lstsq(A * sw[:, None], (S[:, start : c + 1] * sw).T, rcond=None)[0][1]


def theil(c):
    i, j = np.triu_indices(c + 1, 1); dt = T[j] - T[i]; keep = dt >= 0.5
    return np.median((S[:, j[keep]] - S[:, i[keep]]) / dt[keep], axis=1)


def seasonal_area_rate(c):
    """The chosen method: season-aware trend, averaged with the 3 km neighbourhood median."""
    r = wls(c, seasonal=True)
    return 0.5 * (r + area(r))


RATES = {
    "long_term": lambda c: wls(c),
    "recent_5yr": lambda c: wls(c, start=max(0, min(int(np.searchsorted(T, T[c] - 5)), c - 2))),
    "recency_weighted": lambda c: wls(c, w=0.5 ** ((T[c] - T[: c + 1]) / 2.0)),
    "robust_theil_sen": theil,
    "seasonal": lambda c: wls(c, seasonal=True),
    "area_smoothed": lambda c: area(wls(c)),
    "seasonal_area": seasonal_area_rate,
}
NAMES = {
    "no_motion": "No motion",
    "long_term": "Long-term rate",
    "recent_5yr": "Last 5 years' rate",
    "recency_weighted": "Recent years weighted more",
    "robust_theil_sen": "Robust trend (Theil-Sen)",
    "seasonal": "Season-aware trend",
    "area_smoothed": "Neighborhood-smoothed rate",
    "seasonal_area": "Season-aware + neighborhood (chosen)",
    "ml_gradient_boosting": "Machine learning (gradient boosting)",
}


def tasks():
    out = []
    for c in range(E):
        if T[c] - T[0] < 2.0:
            continue
        for H in HORIZONS:
            j = int(np.argmin(np.abs(T - (T[c] + H))))
            if j > c and abs(T[j] - (T[c] + H)) <= 0.35:
                out.append((c, H, j))
    return out


def ml_rows(task_list, truth, rate_cache):
    """Pooled gradient boosting, walk-forward: trained only on outcomes known by each origin."""
    from sklearn.ensemble import HistGradientBoostingRegressor

    rng = np.random.default_rng(0)
    feats = {}

    def X(c):
        if c not in feats:
            cols = [rate_cache(k, c) for k in RATES] + [area(rate_cache("recent_5yr", c)), np.full(N, T[c] - T[0])]
            feats[c] = np.column_stack(cols)
        return feats[c]

    sub = {o: rng.choice(N, min(1500, N), replace=False) for o in range(E)}
    rows = []
    for c in sorted({t[0] for t in task_list}):
        train = [(o, H, j) for o, H, j in task_list if j <= c]
        here = [t for t in task_list if t[0] == c]
        base = rate_cache(CHOSEN, c)
        if len(train) < 6:
            rows += [(c, H, j, float(np.median(np.abs(truth[(c, j)] - base * (T[j] - T[c]))))) for _, H, j in here]
            continue
        Xs, ys = [], []
        for o, H, j in train:
            idx = sub[o]; dt = T[j] - T[o]
            y = (level(T[j], upto=c) - level(T[o], upto=c))[idx] / dt - rate_cache(CHOSEN, o)[idx]
            Xs.append(np.c_[X(o)[idx], np.full(len(idx), dt)]); ys.append(y)
        model = HistGradientBoostingRegressor(max_iter=150, learning_rate=0.05, max_depth=3, min_samples_leaf=200, l2_regularization=5.0, random_state=0)
        model.fit(np.vstack(Xs), np.concatenate(ys))
        for _, H, j in here:
            dt = T[j] - T[c]
            pred = (base + model.predict(np.c_[X(c), np.full(N, dt)])) * dt
            rows.append((c, H, j, float(np.median(np.abs(truth[(c, j)] - pred)))))
    return rows


def main() -> None:
    task_list = tasks()
    truth = {(c, j): level(T[j]) - level(T[c]) for c, _, j in task_list}
    cache: dict = {}

    def rate_cache(name, c):
        if (name, c) not in cache:
            cache[(name, c)] = RATES[name](c)
        return cache[(name, c)]

    rows = {"no_motion": [(c, H, j, float(np.median(np.abs(truth[(c, j)])))) for c, H, j in task_list]}
    chosen_abs = {H: [] for H in HORIZONS}
    for name in RATES:
        rows[name] = []
        for c, H, j in task_list:
            err = np.abs(truth[(c, j)] - rate_cache(name, c) * (T[j] - T[c]))
            rows[name].append((c, H, j, float(np.median(err))))
            if name == CHOSEN:
                chosen_abs[H].append(err)
    try:
        rows["ml_gradient_boosting"] = ml_rows(task_list, truth, rate_cache)
    except ImportError:
        pass
    table = []
    for name, r in rows.items():
        per_h = {str(H): round(float(np.mean([x[3] for x in r if x[1] == H])) / 10, 2) for H in HORIZONS}
        table.append({"method": name, "label": NAMES[name], "overall_cm": round(float(np.mean([x[3] for x in r])) / 10, 2), "by_horizon_cm": per_h})
    table.sort(key=lambda m: m["overall_cm"])
    bands = [{"years_ahead": H, "half_width_cm": round(float(np.quantile(np.concatenate(chosen_abs[H]), 0.8)) / 10, 2), "tests": len(chosen_abs[H])} for H in HORIZONS]
    result = {
        "artifact_type": "terragauge_forecast_benchmark",
        "method": __doc__.strip(),
        "chosen": CHOSEN,
        "origins": [DATES[c] for c in sorted({t[0] for t in task_list})],
        "test_cases": len(task_list),
        "table": table,
        "bands_80": bands,
    }
    OUT.write_text(json.dumps(result, indent=1), encoding="utf-8")
    for m in table:
        print(f"{m['label']:40s} {m['overall_cm']:5.2f} cm  " + "  ".join(f"{h}y {v:4.2f}" for h, v in m["by_horizon_cm"].items()))
    print("80% bands:", bands)


if __name__ == "__main__":
    main()

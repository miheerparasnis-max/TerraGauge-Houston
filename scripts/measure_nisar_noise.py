"""Measure NISAR's per-pass noise over Houston from the real pair archive.

The website's "how long would NISAR need to confirm this sinking" used the
scatter inside the small reference region of one pair (about 3 mm). Atmospheric
delay decorrelates with distance, so squares far from the reference are noisier
than that. This script measures the noise each square actually shows:

1. take the same chain the prediction test uses (consecutive, ramp-removed pairs
   from config/prediction_test.json's window start, previewed pairs excluded);
2. for every square that passes the NISAR quality gate in every pair, build its
   displacement history (pair sums), referenced at each date to the median of the
   region-A squares;
3. fit a straight line through each history and keep the scatter of the residuals
   (n - 2 degrees of freedom). That is the per-date noise, plus any real
   non-linear motion such as the clay's seasonal swing, so it is an upper bound;
4. summarize the scatter overall and by distance from region A.

Writes data/derived/nisar_noise_measured.json, which scripts/export_web.py uses.

    python3 scripts/measure_nisar_noise.py
"""
from __future__ import annotations

import json
import re
import sys
from datetime import date
from math import asin, cos, radians, sin, sqrt
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.ingestion.provisional import _good_nisar, deramp_pair  # noqa: E402

DERIVED = ROOT / "data" / "derived"
CONFIG = ROOT / "config" / "prediction_test.json"
OUT = DERIVED / "nisar_noise_measured.json"
BINS_KM = [0, 10, 20, 30, 40, 60, 200]


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def km(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    p1, p2 = radians(lat1), radians(lat2)
    a = sin((p2 - p1) / 2) ** 2 + cos(p1) * cos(p2) * sin(radians(lon2 - lon1) / 2) ** 2
    return 12742.0 * asin(sqrt(a))


def chain_pairs(cfg: dict) -> list[dict]:
    excluded = set(cfg["target"]["previewed_pairs_excluded"])
    pairs = {}
    for p in sorted(DERIVED.glob("nisar_gunw_houston_*_pair_cells.json")):
        m = re.search(r"_(\d{8})_(\d{8})_pair_cells\.json$", p.name)
        if not m or f"{m.group(1)}_{m.group(2)}" in excluded:
            continue
        pairs[f"{m.group(1)[:4]}-{m.group(1)[4:6]}-{m.group(1)[6:]}"] = p
    chain, d = [], cfg["target"]["window_start"]
    while d in pairs:
        art = load(pairs[d])
        chain.append(art)
        d = art["parameters"]["acquisition_dates"][1]
    return chain


def main() -> None:
    cfg = load(CONFIG)
    frozen = load(ROOT / cfg["predictor"]["frozen_file"])
    region_a = set(frozen["reference_cell_ids"])
    chain = [deramp_pair(a) for a in chain_pairs(cfg)]
    if len(chain) < 6:
        sys.exit(f"only {len(chain)} contiguous pairs; need at least 6 to measure noise")
    dates = [chain[0]["parameters"]["acquisition_dates"][0]] + [a["parameters"]["acquisition_dates"][1] for a in chain]
    t = np.array([(date.fromisoformat(d) - date.fromisoformat(dates[0])).days / 365.25 for d in dates])

    lookups = [{c["cell_id"]: c for c in a["cells"]} for a in chain]
    meta = {c["cell_id"]: (float(c["longitude"]), float(c["latitude"])) for c in chain[0]["cells"]}
    ids = [cid for cid in meta if all(cid in lk and _good_nisar(lk[cid]) for lk in lookups)]
    steps = np.array([[float(lk[cid]["pair_los_displacement_mm"]) for lk in lookups] for cid in ids])  # cells x pairs
    series = np.concatenate([np.zeros((len(ids), 1)), np.cumsum(steps, axis=1)], axis=1)            # cells x dates
    ref_rows = [i for i, cid in enumerate(ids) if cid in region_a]
    if len(ref_rows) < 3:
        sys.exit(f"only {len(ref_rows)} region-A squares pass in every pair; cannot reference")
    series = series - np.median(series[ref_rows], axis=0)  # reference every date to region A

    design = np.vstack([np.ones_like(t), t]).T
    coef, *_ = np.linalg.lstsq(design, series.T, rcond=None)
    resid = series - (design @ coef).T
    sigma = np.sqrt((resid ** 2).sum(axis=1) / (len(t) - 2))

    ax = float(np.mean([meta[ids[i]][0] for i in ref_rows])); ay = float(np.mean([meta[ids[i]][1] for i in ref_rows]))
    dist = np.array([km(*meta[cid], ax, ay) for cid in ids])
    outside = np.array([cid not in region_a for cid in ids])
    bins = []
    for lo, hi in zip(BINS_KM, BINS_KM[1:]):
        sel = outside & (dist >= lo) & (dist < hi)
        if sel.sum() >= 20:
            bins.append({"from_km": lo, "to_km": hi, "squares": int(sel.sum()), "median_sigma_mm": round(float(np.median(sigma[sel])), 2),
                         "p80_sigma_mm": round(float(np.percentile(sigma[sel], 80)), 2), "median_distance_km": round(float(np.median(dist[sel])), 1)})
    out = {
        "artifact_type": "terragauge_nisar_noise_measured",
        "method": "Per-square scatter of the region-A-referenced NISAR displacement history about a straight line (n - 2 degrees of freedom), "
                  "from consecutive ramp-removed pairs; includes real non-linear motion, so it is an upper bound on noise.",
        "pairs": len(chain), "dates": [dates[0], dates[-1]], "epochs": len(dates),
        "squares": int(outside.sum()), "region_a_squares": len(ref_rows),
        "median_sigma_mm": round(float(np.median(sigma[outside])), 2),
        "p80_sigma_mm": round(float(np.percentile(sigma[outside], 80)), 2),
        "region_a_median_sigma_mm": round(float(np.median(sigma[ref_rows])), 2),
        "by_distance_from_region_a": bins,
        "region_a_center": [round(ax, 4), round(ay, 4)],
        "limitations": [
            "The 22 pairs span about ten months, so seasonal ground motion is not separated from noise.",
            "Ramp removal also removes any real motion that is planar across the frame.",
            "Simple nearest-neighbour chain with no loop closures: unwrapping errors are not independently checked.",
        ],
    }
    OUT.write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k not in ("limitations", "method")}, indent=1))


if __name__ == "__main__":
    main()

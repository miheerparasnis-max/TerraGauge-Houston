"""Score the pre-registered OPERA -> NISAR prediction test (D-041).

Every rule and threshold comes from config/prediction_test.json and
docs/preregistration/2026-11-12-opera-nisar-prediction.md. Order of work, as
registered:

1. Check the blocking conditions. If NISAR's line-of-sight sign convention has
   not been verified from the product, or fewer than 6 test pairs exist, the
   correlation is NOT computed.
2. Build the target: the longest contiguous chain of consecutive, ramp-removed
   NISAR pairs starting 2026-01-01, summed, referenced to region A.
3. Select squares (quality gate, complete predictor, OPERA water <= 0.5,
   outside region A) and list every dropped square with its reason.
4. Power analysis (1,000 simulations) - written to the output before scoring.
5. Only if not blocked: Spearman rho (square level), block-median rho with a
   10,000-permutation p-value (seed 20261112), decile difference, verdict.

Sign verification lives in config/los_sign.json, which a person fills in from
the products themselves (see the "BLOCKED" message for what it needs). This
script never guesses a sign.

    python3 scripts/score_prediction.py
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from statistics import median

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.ingestion.provisional import _good_nisar, chain_sum, deramp_pair  # noqa: E402

CONFIG = ROOT / "config" / "prediction_test.json"
SIGN = ROOT / "config" / "los_sign.json"
DERIVED = ROOT / "data" / "derived"
OUT = DERIVED / "prediction" / "prediction_test_result.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def ranks(a: np.ndarray) -> np.ndarray:
    """Average ranks along the last axis (ties share the mean rank)."""
    order = np.argsort(a, axis=-1, kind="mergesort")
    r = np.empty_like(order, dtype=float)
    np.put_along_axis(r, order, np.arange(a.shape[-1], dtype=float) + np.zeros(a.shape), axis=-1)
    if a.ndim == 1:
        _, inv, counts = np.unique(a, return_inverse=True, return_counts=True)
        if (counts > 1).any():
            sums = np.bincount(inv, weights=r)
            r = (sums / counts)[inv]
    return r


def spearman(x: np.ndarray, y: np.ndarray) -> float:
    rx, ry = ranks(x), ranks(y)
    rx, ry = rx - rx.mean(), ry - ry.mean()
    return float((rx * ry).sum() / np.sqrt((rx * rx).sum() * (ry * ry).sum()))


def perm_rho(x: np.ndarray, y: np.ndarray, n: int, rng: np.random.Generator) -> np.ndarray:
    """Spearman rho of x against n random permutations of y (vectorised)."""
    rx = ranks(x); rx = rx - rx.mean()
    ry = ranks(y); ry = ry - ry.mean()
    perms = np.stack([rng.permutation(ry) for _ in range(n)])
    return (perms @ rx) / np.sqrt((rx * rx).sum() * (ry * ry).sum())


def grid_ij(cell_id: str) -> tuple[int, int]:
    m = re.search(r"(-?\d+)-(-?\d+)$", cell_id)
    return int(m.group(1)), int(m.group(2))


def block_medians(ids: list[str], x: np.ndarray, y: np.ndarray, size: int, min_cells: int):
    groups: dict[tuple[int, int], list[int]] = {}
    for k, cid in enumerate(ids):
        i, j = grid_ij(cid)
        groups.setdefault((i // size, j // size), []).append(k)
    kept = {b: v for b, v in groups.items() if len(v) >= min_cells}
    bx = np.array([np.median(x[v]) for v in kept.values()])
    by = np.array([np.median(y[v]) for v in kept.values()])
    return list(kept), kept, bx, by, len(groups) - len(kept)


def main() -> None:
    cfg = load(CONFIG)
    target_cfg, inf, cells_cfg = cfg["target"], cfg["inference"], cfg["cells"]
    frozen_path = ROOT / cfg["predictor"]["frozen_file"]
    frozen = load(frozen_path)
    if frozen["config_sha256"] != hashlib.sha256(CONFIG.read_bytes()).hexdigest():
        sys.exit("config/prediction_test.json changed after the predictor was frozen. Refusing to score.")
    out: dict = {"artifact_type": "terragauge_prediction_test_result", "config": str(CONFIG.relative_to(ROOT)), "predictor": str(frozen_path.relative_to(ROOT)),
                 "predictor_sha256": hashlib.sha256(frozen_path.read_bytes()).hexdigest(), "blocking": [], "status": None}

    # ── Target chain: longest contiguous run of consecutive pairs from window_start ──
    excluded = set(target_cfg["previewed_pairs_excluded"])
    pairs = {}
    for p in sorted(DERIVED.glob("nisar_gunw_houston_*_pair_cells.json")):
        m = re.search(r"_(\d{8})_(\d{8})_pair_cells\.json$", p.name)
        if not m or f"{m.group(1)}_{m.group(2)}" in excluded:
            continue
        ref = f"{m.group(1)[:4]}-{m.group(1)[4:6]}-{m.group(1)[6:]}"
        if ref >= target_cfg["window_start"]:
            pairs[ref] = p
    chain, d = [], target_cfg["window_start"]
    while d in pairs:
        art = load(pairs[d])
        chain.append(art)
        d = art["parameters"]["acquisition_dates"][1]
    out["target_chain"] = {"pairs": len(chain), "first": chain[0]["parameters"]["acquisition_dates"][0] if chain else None, "last": chain[-1]["parameters"]["acquisition_dates"][1] if chain else None,
                           "members": [a["parameters"]["acquisition_dates"] for a in chain]}
    if len(chain) < target_cfg["min_pairs"]:
        out["blocking"].append(f"only {len(chain)} contiguous pairs from {target_cfg['window_start']} (need {target_cfg['min_pairs']})")

    # ── Sign convention: must be verified from the products, by a person ──
    sign = load(SIGN) if SIGN.is_file() else None
    sign_ok = bool(sign and sign.get("nisar", {}).get("verified_from") and sign.get("opera", {}).get("verified_from")
                   and sign["nisar"].get("positive_means") in ("toward_satellite", "away_from_satellite")
                   and sign["opera"].get("positive_means") in ("toward_satellite", "away_from_satellite"))
    if not sign_ok:
        out["blocking"].append("NISAR GUNW LOS sign convention not verified from the product (plan F-4); config/los_sign.json needs both products' "
                               "'positive_means' and 'verified_from' (the HDF5 attribute or specification section that states it)")

    if not chain:
        out["status"] = "blocked"
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
        sys.exit("No test pairs found.")

    deramped = [deramp_pair(a) for a in chain]
    summed = chain_sum(deramped)
    days = (np.datetime64(out["target_chain"]["last"]) - np.datetime64(out["target_chain"]["first"])).astype(int)
    out["target_chain"]["days"] = int(days)

    # ── Reference to region A (the frozen predictor's region-A squares) ──
    region_a = set(frozen["reference_cell_ids"])
    ref_vals = [c["pair_los_displacement_mm"] for c in summed["cells"] if c["cell_id"] in region_a and _good_nisar(c)]
    if len(ref_vals) < 3:
        out["blocking"].append(f"only {len(ref_vals)} region-A squares pass NISAR quality in every pair; cannot reference the target")
        ref_offset = None
    else:
        ref_offset = float(median(ref_vals))
    out["reference"] = {"region_a_squares": len(region_a), "region_a_passing": len(ref_vals), "offset_mm": ref_offset}

    # ── OPERA water fraction per square over the predictor window (median across products) ──
    water: dict[str, list[float]] = {}
    for p in sorted(DERIVED.glob("opera_disp_houston_*_pair_cells.json")):
        a = load(p)
        if not (cfg["predictor"]["start"] <= a["parameters"]["reference_date"] and a["parameters"]["secondary_date"] <= cfg["predictor"]["end"]):
            continue
        for c in a["cells"]:
            if c.get("opera_water_fraction") is not None:
                water.setdefault(c["cell_id"], []).append(float(c["opera_water_fraction"]))

    predictor = {c["cell_id"]: c["opera_los_velocity_mm_year"] for c in frozen["cells"]}
    dropped: dict[str, list[str]] = {"nisar_quality": [], "no_complete_predictor": [], "opera_water": [], "region_a": []}
    ids, xs, ys = [], [], []
    for c in summed["cells"]:
        cid = c["cell_id"]
        if cells_cfg["exclude_reference_region_cells"] and cid in region_a:
            dropped["region_a"].append(cid); continue
        if cells_cfg["require_nisar_quality_gate"] and not _good_nisar(c):
            dropped["nisar_quality"].append(cid); continue
        if cells_cfg["require_complete_opera_predictor"] and predictor.get(cid) is None:
            dropped["no_complete_predictor"].append(cid); continue
        w = water.get(cid)
        if w is None or median(w) > cells_cfg["max_opera_water_fraction"]:
            dropped["opera_water"].append(cid); continue
        ids.append(cid); xs.append(predictor[cid]); ys.append(c["pair_los_displacement_mm"] - (ref_offset or 0.0))
    x, y = np.array(xs), np.array(ys)
    out["squares"] = {"used": len(ids), "dropped_counts": {k: len(v) for k, v in dropped.items()}, "dropped": dropped}

    # ── Power, before any scoring ──
    rng = np.random.default_rng(inf["seed"])
    sigma = 1.4826 * float(np.median(np.abs(y - np.median(y)))) if len(y) else float("nan")
    block_keys, groups, _, by_real, blocks_dropped = block_medians(ids, x, y, inf["block_cells"], inf["min_cells_per_block"])
    share = float(np.clip(np.var(by_real) / np.var(y), 0, 1)) if len(by_real) > 1 and np.var(y) > 0 else 0.0
    expected = x * days / 365.25
    sims, hits = cfg["power"]["simulations"], 0
    all_blocks: dict[tuple[int, int], int] = {}
    block_of = np.array([all_blocks.setdefault((grid_ij(cid)[0] // inf["block_cells"], grid_ij(cid)[1] // inf["block_cells"]), len(all_blocks)) for cid in ids], dtype=int)
    for _ in range(sims):
        noise = rng.normal(0, sigma * np.sqrt(share), len(all_blocks))[block_of] + rng.normal(0, sigma * np.sqrt(1 - share), len(ids))
        ysim = expected + noise
        _, _, bx, bys, _ = block_medians(ids, x, ysim, inf["block_cells"], inf["min_cells_per_block"])
        rho = spearman(bx, bys)
        null = perm_rho(bx, bys, 1000, rng)
        if rho > 0 and (np.abs(null) >= abs(rho)).mean() < inf["alpha"]:
            hits += 1
    out["power"] = {"simulations": sims, "noise_sigma_mm": round(sigma, 3), "block_variance_share": round(share, 3), "blocks": len(by_real), "blocks_dropped_small": blocks_dropped,
                    "expected_signal_iqr_mm": [round(float(np.percentile(expected, 25)), 3), round(float(np.percentile(expected, 75)), 3)],
                    "power": round(hits / sims, 3),
                    "note": "Share of simulated runs (predictor x chain length + noise at the real field's spread) that pass. Noise sigma is an upper bound: it includes any real signal. Permutations per simulation: 1,000."}

    if out["blocking"]:
        out["status"] = "blocked"
        out["verdict"] = None
    else:
        same = sign["nisar"]["positive_means"] == sign["opera"]["positive_means"]
        expected_sign = 1 if same else -1
        rho_cells = spearman(x, y)
        _, _, bx, bys, _ = block_medians(ids, x, y, inf["block_cells"], inf["min_cells_per_block"])
        rho_blocks = spearman(bx, bys)
        null = perm_rho(bx, bys, inf["permutations"], np.random.default_rng(inf["seed"]))
        p_two = float((np.abs(null) >= abs(rho_blocks)).mean())
        q10, q90 = np.percentile(x, 10), np.percentile(x, 90)
        decile = float(np.median(y[x <= q10]) - np.median(y[x >= q90]))
        passed = np.sign(rho_blocks) == expected_sign and p_two < inf["alpha"]
        out["result"] = {"spearman_rho_cells": round(rho_cells, 4), "spearman_rho_block_medians": round(rho_blocks, 4), "p_block_permutation_two_sided": p_two,
                         "expected_sign": expected_sign, "decile_median_difference_mm": round(decile, 3)}
        out["status"] = "scored"
        out["verdict"] = "pass" if passed else cfg["null_wording"]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k not in ("squares", "target_chain")} | {"squares_used": out["squares"]["used"], "chain_pairs": out["target_chain"]["pairs"], "chain": [out["target_chain"]["first"], out["target_chain"]["last"]]}, indent=1))


if __name__ == "__main__":
    main()

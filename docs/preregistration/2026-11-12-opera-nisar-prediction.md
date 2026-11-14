# Pre-registration: OPERA → NISAR prediction test (2026-11-12)

Audience: the team, the executing agent, and judges checking that the prediction came before the data.
Machine-readable copy: `config/prediction_test.json`. The scorer must read every threshold from there. Commit hash: recorded in `docs/decisions.md` (D-041).

## Question

Does NASA's new radar (NISAR) see the same pattern of ground motion that nine years of Sentinel-1 (OPERA) showed?

## Why the test window starts on 2026-01-01

The first five NISAR pairs (2025-11-02 → 2026-01-01) have already been compared with OPERA on the website, so a test on them would not be blind. They are excluded and reported separately as "previewed".

The test uses only NISAR pairs from 2026-01-01 onward. On the day of registration, none of them had been downloaded or processed by the team. The archive lists 22 granules through 2026-10-16 (`data/manifests/nisar_track062_inventory_20261110.json`).

## The prediction, frozen now

- **Predictor:** the OPERA LOS rate per 1 km square over **2016-07-12 → 2025-09-23**, referenced to region A (`config/preregistration.json`). It ends before the test window starts, so it cannot see the test period.
- **Frozen file:** `data/derived/prediction/opera_predictor_20160712_20250923.json` (5,538 squares, 29 products, sha256 `3da45699…a3033d2b`), written by `scripts/freeze_prediction.py`.
- **Prediction:** squares where OPERA saw faster motion away from the satellite will show more motion away from the satellite in NISAR's cumulative displacement over the test chain.

## Rules

- **Target.** The cumulative NISAR LOS displacement over the longest contiguous chain of consecutive, ramp-removed pairs that starts 2026-01-01, referenced to region A. It needs at least 6 pairs, or the test is not run.
- **Squares.** A square counts only if it:
  - passes the NISAR quality gate;
  - has a complete OPERA predictor record;
  - has an OPERA water fraction of at most 0.5;
  - is outside region A.

  Every dropped square is listed with its reason.
- **Primary metric.** The Spearman rank correlation ρ between the predictor and the target, over squares. It is rank-based, so the two sensors' different look angles and wavelengths do not need a vertical conversion.
- **Inference.**
  - Squares are grouped into 10 × 10 km blocks, and blocks with fewer than 10 squares are dropped.
  - ρ is computed on the block medians, with a p-value from 10,000 permutations of the block medians (seed 20261112).
  - The test uses blocks because radar noise and subsidence are both spatially clustered; shuffling single squares would overstate significance.
- **Secondary metric.** The median target in the predictor's most-negative decile minus the median target in its most-positive decile, in mm.
- **Power first.** Before the real ρ is computed, the scorer simulates the target 1,000 times. Each simulation is the predictor times the chain duration, plus noise:
  - The noise σ is 1.4826 × MAD of the real target over the test squares. That is an upper bound on the noise, because it includes any real signal.
  - The noise has a block-level component sized from the same field.

  The scorer writes the power to its output before scoring.
- **Pass.** ρ has the sign implied by both products' verified LOS conventions, **and** the block-permutation p < 0.05.
- **Any other outcome** is reported as: "Not detected at the current NISAR record length. This does not mean the ground stopped moving."

## Blocking conditions (the test does not run)

- The NISAR GUNW LOS sign convention has not been read from the product (plan F-4). Without it, the expected sign of ρ is unknown.
- Fewer than 6 pairs after 2026-01-01 have been processed.

## Limitations to publish with any result

- The two sensors have different wavelengths (C-band against L-band), look directions, and time windows.
- The predictor and the target are relative to the same reference region, not absolute.
- The first five NISAR pairs were previewed before this registration and are excluded from the test.
- A pass shows agreement in pattern, not in rate. Even then, NISAR's rate is not released until the main pre-registration's release rule is met.

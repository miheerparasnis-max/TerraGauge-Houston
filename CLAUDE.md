# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

TerraGauge Houston is an evidence-first monitoring-priority system for Houston ground motion (NASA NISAR / OPERA InSAR, HoustonNet GPS, USGS groundwater + extensometer, FEMA flood zones, and a DIY stationary GNSS node). It explains what evidence exists at a location and what is missing. It must **not** forecast flooding, diagnose subsidence cause, turn a pairwise displacement into an annual rate, or present GNSS stationary repeatability as land motion. Preserve these safeguards (see README "Science safeguards") when changing code or UI copy.

## Commands

```bash
# Tests (stdlib unittest; core backend has no third-party deps)
python3 -m unittest discover -s tests -v
python3 -m unittest tests.test_insights -v                     # one module
python3 -m unittest tests.test_insights.SomeClass.test_name -v # one test

# API server (http://127.0.0.1:8000); override data with TERRAGAUGE_DATASET=/abs/path/cells.json
python3 -m backend

# Ingestion CLI (needs `pip install -r requirements.txt`: numpy, h5py, pyproj)
python3 -m backend.ingestion.cli <subcommand> ...   # inspect-h5, nisar-gunw, opera-disp, validate-nisar-pair, build-houston-evidence, ...

# Regenerate website data
python3 scripts/build_provisional.py   # writes data/derived/provisional/ (needs numpy)
python3 scripts/export_web.py          # writes web/public/data/

# Website (React + Vite + TS + MapLibre) in web/
cd web && npm install && npm run dev   # http://localhost:5173
npm run build                          # tsc -b && vite build (no lint/test scripts)
```

## Architecture

Three layers; scientific logic lives only in Python, the website just renders precomputed JSON.

1. **Core API (`backend/`, stdlib only).** `model.py` (dataclasses, `Label`, `Thresholds`) → `repository.py` (validates/loads the aggregated-cell JSON contract) → `decision.py` (explainable classification rules; quality gates first, then reference-scatter threshold, GPS/time-matching checks) → `service.py` (`TerraGaugeService`) → `api.py` (HTTP routes). `detection.py` holds GNSS session-noise math; `insights.py` produces the website's movement/confidence/future/priority outputs. `decision.classify_opera_velocity` is the OPERA-based equivalent used by the provisional build.

2. **Ingestion (`backend/ingestion/`, needs numpy/h5py/pyproj).** One adapter per source (`nisar.py`, `opera.py`, `houstonnet.py`, `usgs.py`, `compaction.py`, `fema.py`, `gnss.py`, `raster_layers.py`), driven by `cli.py`. Adapters write intermediate JSON artifacts carrying provenance, parameters, and limitations. Gates: `quality.py` (structural integrity of NISAR pairs), `temporal.py` (NISAR network diagnostic: withholds rate without ≥2 independent loop-closure edges), `opera_temporal.py` (withholds OPERA rate until re-referenced and GNSS-checked), `reference.py` (stable-reference handling). `houston.py` joins everything into the evidence dataset; `provisional.py` supports the website build.

3. **Data + website.** `data/derived/` holds checked source-derived artifacts (committed); `data/manifests/` records sources/checksums; `data/raw/` is gitignored (local-only HDF5/NetCDF). `data/sample_cells.json` is a demo fixture that must never appear as a real Houston result. `scripts/build_provisional.py` → `data/derived/provisional/` → `scripts/export_web.py` → `web/public/data/` → `web/src/` (`MapView.tsx`, `Card.tsx`, `Pages.tsx`, `labels.ts`).

## Things to know

- Everything from the provisional build is flagged `provisional_unreviewed` until a team-reviewed stable reference is chosen (`--reference-status reviewed`).
- The site defaults to OPERA-based priorities; NISAR 12-day pairs are noise-dominated (~18 mm cross-cell scatter of a ramp-removed pair, not a measured per-epoch σ, vs ~0.2 mm expected motion) and shown only as quality preview.
- OPERA DISP-S1 `water_mask`: 0 = water, 1 = land (this was previously inverted; don't reintroduce).
- NISAR displacements must be re-referenced (reference median subtracted); raw values are kept in `pair_los_displacement_raw_mm`.
- Do not assume NISAR GUNW phase corrections are applied. The `*CorrectionApplied` flags in the pair artifacts sit under `metadata/processingInformation/parameters/geocoding/` (audit A1, `docs/audit/2026-11-10-codebase-audit.md`). GUNW includes an ionospheric phase screen and tropospheric and tide lookup tables that are not applied by default. TerraGauge applies each correction exactly once, records which were applied in the artifact, and never applies a correction that the artifact already records as applied. Contract: `backend/ingestion/corrections.py`. Each flag in `applied_corrections` is `true` (applied), `false` (verified not applied), or `null` (unverified), and applying is refused twice or on an unverified state. Every current artifact is `null` (unverified), because the product's phase-correction state has not been read yet (plan step B1).
- NISAR wavelength is 0.241962 m (center frequency 1.239 GHz) from product metadata, not 0.238 m; λ/(4π) = 19.255 mm/rad. `nisar.py` reads it from the product's frequency-A center frequency; `--wavelength-m` is optional and is rejected if it disagrees. The LOS sign convention is not yet verified (plan F-4).
- The NISAR archive for track 062 / frame 016 / ascending holds 27 GUNW pairs on 28 dates (2025-11-02 to 2026-10-16) per `data/manifests/nisar_track062_inventory_20261110.json` (regenerate with `scripts/nisar_inventory.py`). It is a simple nearest-neighbor chain with no loop closures; the repo has processed only the first 5 pairs.
- Pre-registered rules live in `docs/preregistration/` and `config/preregistration.json`. Changing one after results exist is a deviation: log it in `docs/decisions.md` with results under both rules.
- Use a Python 3.14 venv with `requirements-layers.txt` for ingestion and the full test suite; `h5py` has no Python 3.15 wheel.
- `flood_exposed` may be `null`; never infer it from a station-point FEMA result. A cell with no matching FEMA polygon is `null` (unknown), never `false`.
- Every loader that feeds a published output (website, page, deck) must call `backend.publish_guard.assert_publishable`, which refuses demonstration data.
- Large regenerable intermediates under `data/derived/provisional/` are gitignored.
- Network-dependent scripts (`fetch_opera_extension.py`, `fetch_nasa_layers.py`) need an Earthdata login and download multi-GB data.

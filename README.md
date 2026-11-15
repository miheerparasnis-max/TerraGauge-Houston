# TerraGauge Houston

TerraGauge is an evidence-first monitoring-priority system for Houston ground motion. It combines ten years of Copernicus Sentinel-1 radar processed by NASA OPERA (DISP-S1, 2016-07-12 to 2026-03-22), the NASA-ISRO NISAR mission's first year of pairs, HoustonNet GPS, USGS groundwater and extensometer records, FEMA flood zones, and a stationary GNSS repeatability experiment to explain **what evidence exists at a location and what is still missing**.

It does **not** forecast flooding or flood depths, diagnose the cause of motion, turn a pairwise NISAR displacement into an annual rate, or present a GNSS receiver's stationary repeatability as land motion. Its one forward-looking output is a ground-sinking trend continuation, kept only in tested form: the method that won a walk-forward benchmark, 80% ranges from those tests, and no year beyond the tested 5-year horizon (D-045, D-046).

Everything is flagged `provisional_unreviewed` until the team approves the stable reference.

## Backend scope

This repository currently contains a dependency-free Python API with:

- transparent monitoring-priority rules;
- quality-mask enforcement;
- pairwise-signal gates that cannot silently become annual-rate claims;
- stationary GNSS session-noise calculations;
- validated JSON inputs and documented JSON outputs;
- a small demo fixture, visibly labeled as not source-derived; and
- a NISAR temporal-network diagnostic that refuses to emit a rate from a chain without independent loop closure; and
- structural integrity reports for every checked NISAR pair, including coordinate bounds, unique cell IDs, correction-flag preservation, and dominant-connected-component counts; and
- unit tests for the science and decision logic.

The frontend can call these endpoints without duplicating scientific logic.

## Run locally

The core API needs Python 3.11+ and no third-party packages. Ingestion and the
full test suite need the packages in `requirements.txt`; use **Python 3.14** for
that environment. As of 2026-11-10, `h5py` has no binary wheel for Python 3.15,
so a 3.15 environment cannot install the requirements without building HDF5.

```bash
python3.14 -m venv .venv
.venv/bin/pip install -r requirements-layers.txt   # requirements.txt plus rasterio and earthaccess
.venv/bin/python -m unittest discover -s tests -v   # expect 0 errors, 0 skips
.venv/bin/python -m backend
```

The API starts at `http://127.0.0.1:8000`.

## API contract

| Method | Route | Purpose |
|---|---|---|
| `GET` | `/health` | Service health check |
| `GET` | `/v1/summary` | Dataset status (shows when the demo fixture is loaded), label counts, active thresholds, and disclaimer |
| `GET` | `/v1/cells` | All analyzed 1 km cells |
| `GET` | `/v1/cells/{cell_id}` | One evidence card payload |
| `GET` | `/v1/data-ledger` | Versioned source-manifest records |
| `GET` | `/v1/opera-temporal-status` | Historical OPERA rate status and the reason a rate is withheld |
| `GET` | `/v1/review-packets/{cell_id}` | Required human checks before a priority is presented as a finding |
| `POST` | `/v1/analyze-cell` | Analyze a validated cell without saving it |
| `POST` | `/v1/gnss/noise-floor` | Calculate stationary GNSS session scatter |

### Example requests

```bash
curl http://127.0.0.1:8000/v1/summary
curl http://127.0.0.1:8000/v1/data-ledger
curl http://127.0.0.1:8000/v1/opera-temporal-status
curl http://127.0.0.1:8000/v1/cells/hou-001
curl -X POST http://127.0.0.1:8000/v1/gnss/noise-floor \
  -H 'Content-Type: application/json' \
  -d '{"session_heights_mm":[11.2, 8.9, 10.4], "session_hours":2}'
```

## Input data contract

The app reads an aggregated-cell JSON file such as `data/sample_cells.json`. Point the service at a source-derived dataset with:

```bash
TERRAGAUGE_DATASET=/absolute/path/to/cells.json python3 -m backend
```

Each cell must provide coordinates, pairwise LOS displacement/quality values, and any available GPS/USGS evidence. `flood_exposed` may be `null`; it must not be guessed from a station-point flood classification. The source-specific ingestion pipeline writes this contract after processing—not bypassing the API logic.

## Science safeguards

- NISAR motion is line-of-sight motion, not automatically vertical subsidence or an annual rate.
- A pair-signal threshold is calculated only from an explicitly supplied, independently justified stable-reference region.
- Historic HoustonNet values are context, not time-matched validation of the NISAR pair.
- A station-point FEMA result is context, not a cell-level flood classification.
- A GNSS node result represents stationary receiver repeatability, not observed land motion.
- The NISAR-derived artifacts preserve the product's correction flags. The flags recorded so far are geocoding flags; they do not show that phase corrections were applied to the unwrapped phase (audit A1). GUNW includes an ionospheric phase screen and tropospheric and tide lookup tables that are not applied by default. TerraGauge applies each correction exactly once, records which were applied in the artifact, and never applies a correction that the artifact already records as applied.
- The demo dataset is only for development and cannot appear as a real Houston result: `backend/publish_guard.py` refuses it in every build that produces a published output.

## Source-derived ingestion

The API is now paired with ingestion adapters for the real source products. They
write intermediate JSON artifacts with product paths, source filenames,
parameters, and limitations. They never silently turn a pair displacement into a
yearly rate.

Install ingestion-only dependencies in an isolated environment:

```bash
python3 -m pip install -r requirements.txt
```

### NISAR L2 GUNW

First inspect the actual Houston granule; do not assume a path or projection:

```bash
python3 -m backend.ingestion.cli inspect-h5 /path/to/NISAR_GUNW.h5 > data/derived/gunw-layout.json
```

Then extract one quality-preserving pair artifact. Use the verified product CRS,
x/y paths, and acquisition dates from the product metadata. The wavelength is
read from the product's frequency-A center frequency; `--wavelength-m` is optional
and is rejected if it disagrees by more than 0.1%:

```bash
python3 -m backend.ingestion.cli nisar-gunw /path/to/NISAR_GUNW.h5 data/derived/nisar-pair.json \
  --wavelength-m 0.241962 \
  --crs EPSG:32615 \
  --x-path /verified/x/path --y-path /verified/y/path \
  --reference-date YYYY-MM-DD --secondary-date YYYY-MM-DD
```

The documented default layer paths are under
`/science/LSAR/GUNW/grids/frequencyA/unwrappedInterferogram/HH/` for
`unwrappedPhase`, `coherenceMagnitude`, and `connectedComponents`. Verify them
with inspection before using them. GUNW phase is converted to pairwise LOS
displacement with `phase * wavelength / (4π)`; it is **not** made into a rate.

For the checked Houston example, `data/manifests/nisar_gunw_20251102_20251114.json`
records the source, checksum, coordinate system, and extraction bounds. Its compact
study-area artifact is `data/derived/nisar_gunw_houston_20251102_20251114_pair_cells.json`.
The raw HDF5 is intentionally local-only. Add `--bbox -95.95 29.4 -94.8 30.2` to
write only the Houston study area instead of the entire source frame.

Every compact pair artifact must pass the reproducible structural gate before it
can be joined to Houston context. It rejects duplicate cell IDs, invalid/outside
coordinates, missing product correction flags, a missing or invalid
`applied_corrections` record (`backend/ingestion/corrections.py`), and malformed
date metadata. It
also accepts only cells whose dominant local connected component matches the
scene-wide dominant component; this prevents isolated phase islands from being
treated as reliable evidence.

```bash
python3 -m backend.ingestion.cli validate-nisar-pair \
  data/derived/nisar_gunw_houston_20251102_20251114_pair_cells.json \
  data/derived/nisar_gunw_houston_20251102_20251114_pair_cells_integrity_report.json
```

### Multi-date NISAR network status

The NASA archive holds 27 track-062 frame-016 pairs on 28 dates (2025-11-02 to
2026-10-16), all nearest-neighbor, so the archive never supplies loop closures
(`data/manifests/nisar_track062_inventory_20261110.json`, regenerate with
`python3 scripts/nisar_inventory.py --out ...`). All 27 are processed into
`data/derived/nisar_gunw_houston_*_pair_cells.json`. The diagnostic over the
whole archive, `data/derived/nisar_track062_network_diagnostic_20251102_20261016.json`,
finds a connected **chain** with zero redundant edges, so the strict
(loop-closure) rule withholds a temporal rate. The earlier five-pair diagnostic
(`..._20251102_20260101.json`) is kept for the record.

Recreate the graph audit with:

```bash
python3 -m backend.ingestion.cli temporal-network-diagnostic \
  data/derived/nisar_track062_network_diagnostic_20251102_20261016.json \
  data/derived/nisar_gunw_houston_*_pair_cells.json
```

What the chain *can* support, under pre-registered rules:

- **Measured noise.** `scripts/measure_nisar_noise.py` measures each square's
  per-date scatter over the 22-pair chain (2026-01-01 to 2026-10-16): median
  11.1 mm, about 6 mm near the reference region rising to 16 mm at 45 km
  (`data/derived/nisar_noise_measured.json`). The website's NISAR confirmation
  times use this, at each square's distance.
- **OPERA → NISAR prediction test** (D-041, D-049). The frozen OPERA predictor
  (2016-07-12 to 2025-09-23) was scored against the blind 22-pair NISAR chain on
  1,287 squares: Spearman ρ = −0.60 (block medians −0.72), with the
  pre-registered sign, block-permutation p < 0.001. Verdict: pass
  (`data/derived/prediction/prediction_test_result.json`). This is a ranking test,
  not a NISAR rate.

### OPERA DISP-S1

OPERA context is ingested from the raw displacement layer and recommended mask,
not a portal screenshot or color ramp. The checked Houston artifact is
`data/derived/opera_disp_houston_20160712_20161016_pair_cells.json`: 10,580
quality-masked ~1 km cells from a real 2016 OPERA product. It is joined only as
historical pairwise context; no annual trend is claimed.

The same product's NASA OPERA water mask is aggregated into every OPERA cell as
`opera_water_fraction`. It is a review flag for wet/standing-water conditions,
not a flood-depth measurement.

```bash
python3 -m backend.ingestion.cli opera-disp /path/to/OPERA_DISP.nc data/derived/opera-pair.json \
  --crs EPSG:32615 --bbox -95.95 29.4 -94.8 30.2 --reference-date YYYY-MM-DD --secondary-date YYYY-MM-DD
```

Only `recommended_mask == 1` pixels are included. Build an OPERA historic trend
only after ingesting a dated sequence of products and documenting reference
handling.

### OPERA long-term rate engine

`opera-temporal-invert` records the status of a local historical OPERA subset.
Unlike raw NISAR GUNW, OPERA DISP-S1 products are already processed time-series
outputs; their reference/secondary timestamps must not be mistaken for a raw
interferogram network. A rate is withheld until the complete frame-level stack
is re-referenced to a science-reviewed stable spatial patch and checked against
co-temporal GNSS.

```bash
python3 -m backend.ingestion.cli opera-temporal-invert data/derived/opera_houston_temporal_rate.json \
  --reference-cell epsg3857-1km-REFERENCE-CELL \
  data/derived/opera_pair_*.json
```

When it passes, the output is an OPERA/Sentinel-1 **historical LOS rate with
documented limitations**, not automatically vertical subsidence. NISAR remains
the current mission-era layer and GNSS remains the station-level validation.

The website's rates come from the provisional build instead (below): the full
2016–2026 stack, re-referenced to the pre-registered region A and checked against
GPS, and flagged `provisional_unreviewed` until the team reviews the reference.

### HoustonNet velocities

Download and inspect the published HoustonNet release first. Map its exact CSV
headers explicitly; never guess a reference frame or time span:

```bash
python3 -m backend.ingestion.cli houstonnet-velocities input.csv data/derived/houstonnet-stations.json \
  --column-map '{"station_id":"site","longitude":"lon","latitude":"lat","east_mm_year":"east","north_mm_year":"north","up_mm_year":"up"}'
```

Before comparing GPS to radar, project ENU velocities into the NISAR line of
sight and use a matching time span.

### USGS groundwater evidence

Download an explicit time window from the USGS NWIS daily-values service, then
normalize it without treating water-level change as a motion measurement:

```bash
python3 -m backend.ingestion.cli usgs-groundwater usgs-groundwater.json data/derived/usgs-groundwater.json
```

`data/derived/usgs_houston_groundwater_2025-01-01_2026-11-07.json` is a
source-derived Houston example. A positive `depth_change_ft` means the water was
deeper below land surface at the end of the retrieved window; it is evidence for
an analyst to inspect, not proof of a causal mechanism.

### USGS/HGSD extensometer-compaction evidence

TerraGauge now has a production adapter for the official cumulative-compaction
table. The table must be downloaded from the USGS/HGSD release first and its
columns mapped explicitly—no field name is guessed. Its output is **mechanism
context** near a station, never a replacement for GNSS or a citywide motion map.

```bash
python3 -m backend.ingestion.cli usgs-extensometer input.csv data/derived/usgs_extensometer_compaction.json \
  --column-map '{"station_id":"site","longitude":"longitude","latitude":"latitude","date":"date","cumulative_compaction":"compaction"}' \
  --unit ft
```

The checked Houston output is
`data/derived/usgs_houston_extensometer_compaction_2023.json`, derived from the
official USGS 2023 release's TABLE1 plus TABLE2–15 layout. It contains all 14
published station series and is joined to the evidence cards by nearest station.

### FEMA flood-exposure evidence

Save a FEMA National Flood Hazard Layer point-query response for each evidence
station, then join those responses to the USGS locations:

```bash
python3 -m backend.ingestion.cli fema-nfhl-join usgs-groundwater.json responses/ data/derived/fema-join.json
```

The checked Houston join is
`data/derived/fema_nfhl_usgs_station_join_2026-11-07.json`. It classifies the
monitoring coordinates only; it must never be presented as a parcel-level flood
determination, flood depth, or a value for every radar cell.

## Current Houston evidence build

`data/derived/terragauge_houston_evidence_pair_20251102_20251114.json` is built from the checked NISAR, HoustonNet, USGS, and FEMA artifacts. `data/derived/fema_nfhl_houston_cell_context_2026-11-07.json` supplies actual FEMA flood-zone context at each aggregated NISAR-cell center.

```bash
python3 -m backend.ingestion.cli build-houston-evidence \
  data/derived/nisar_gunw_houston_20251102_20251114_pair_cells.json \
  data/derived/houstonnet_2024_summary.json \
  data/derived/usgs_houston_groundwater_2025-01-01_2026-11-07.json \
  data/derived/fema_nfhl_usgs_station_join_2026-11-07.json \
  data/derived/terragauge_houston_evidence_pair_20251102_20251114.json \
  --cell-flood-context data/derived/fema_nfhl_houston_cell_context_2026-11-07.json \
  --compaction data/derived/usgs_houston_extensometer_compaction_2023.json \
  --opera-historic-pair data/derived/opera_disp_houston_20160712_20161016_pair_cells.json
```

It intentionally returns context-only results until the team supplies an independently justified stable reference region. Its provenance appears at `/v1/data-ledger`. The reference-candidate report is available at `data/derived/terragauge_reference_review_candidates_2026-11-07.json`; it is a reviewer aid, never a self-certifying threshold.

## GroundTruth Node hardware record

The node is a Waveshare/Quectel LC29H(BS) dual-band receiver with a fixed outdoor antenna. Three two-hour static sessions were recorded on 2026-11-14 (17:05–19:05, 19:14–21:14, 21:35–23:35 UTC). The raw logs are complete and decode to RINEX.

```bash
python3 scripts/process_groundtruth.py --base zhu1      # RTKLIB-EX against a NOAA CORS base (netp or zhu1); checks base coverage, refuses mixed bases
python3 scripts/groundtruth_diagnostics.py               # tracking and signal strength by direction; no position leaves the script
python3 -m backend.ingestion.cli groundtruth-report data/groundtruth_session_manifest.json data/derived/groundtruth_report.json
```

**Result: inconclusive** (D-050). NOAA NETP posted no data after 19:00 UTC that day, so all three sessions were processed against ZHU1 (19 km). Satellites in the north-east half of the sky arrived weak (19–31 dB-Hz) and broke carrier lock often; a median of only 7, 11 and 12 satellites held an unbroken 10-minute phase arc. Only 7–13% of epochs reached a fixed solution, and relative GPS and multi-GNSS float PPP (CNES real-time products) gave heights that move by 0.5–5 m with reasonable processing choices. No session scatter is reported, and the node's 10 mm daily wobble stays a planning guess. A pass needs ambiguity-fixed solutions from one shared base (`tests/test_gnss.py`).

A passing report would show only stationary receiver repeatability. It never shows Houston land motion.

### macOS LC29H(BS) bring-up

The LC29H(BS) is a base-station model: its meaningful output is binary RTCM
raw-observation/correction data, not a consumer-GPS display. Before a real
session, use an open-sky, stationary antenna and the USB jumper position **A**.
The standard-library-only helper below can query the receiver, configure a
reversible 120-second bench Survey-in, and capture a raw log on macOS:

```bash
python3 scripts/lc29h_macos.py probe --port /dev/cu.usbserial-110
python3 scripts/lc29h_macos.py audit --port /dev/cu.usbserial-110
python3 scripts/lc29h_macos.py configure-test --port /dev/cu.usbserial-110
python3 scripts/lc29h_macos.py capture --port /dev/cu.usbserial-110 \
  --seconds 240 --output ~/Desktop/terragauge_rtcm_test.bin
python3 scripts/lc29h_macos.py bench-run --port /dev/cu.usbserial-110 \
  --survey-seconds 60 --capture-seconds 120 \
  --output ~/Desktop/terragauge_same_session.bin
```

`audit` sends only documented read-only LC29H(BS) status queries across the
standard UART speeds. A real receiver response includes additional fields;
an exact copy of the command alone is only an echo and does not verify a
USB-to-module connection.

`bench-run` keeps the port open while it starts a reversible Survey-in and
enables RTCM, eliminating a host-side port re-open as a possible cause of an
empty test capture. It does not save receiver configuration to flash.

The bench configuration is intentionally not saved to the receiver. A nonzero
log only shows that bytes were captured; keep the antenna fixed and use the
three-session GroundTruth manifest plus RTKLIB/RINEX conversion before making
any repeatability claim. An empty log is a diagnostic result, not evidence of
ground movement.

## Remaining source work

1. Science-review the pre-registered stable reference (region A), then rebuild with `--reference-status reviewed`.
2. Per-pixel radar geometry. The GPS check and the vertical conversion assume one 38° incidence angle and vertical-only motion (audit A9), which can be off by several percent. Fixing it needs OPERA's DISP-S1-STATIC layers (Earthdata login).
3. Read the NISAR GUNW phase-correction state (plan B1). Every `applied_corrections` flag is still `null` (unverified).
4. The NISAR archive gives no redundant pairs, so a NISAR rate stays withheld until cross-pairs or repeat pairs exist.
5. A new GroundTruth recording, if one happens: MSM7 output (adds Doppler) and a signal check in every direction in the first minutes (D-050).

## Website (provisional build)

A ready-made static website lives in `web/` (React + Vite + TypeScript + MapLibre). It reads precomputed JSON from `web/public/data/`; all science logic runs in Python.

```bash
cd web
npm install
npm run dev        # opens http://localhost:5173
```

The site opens on a scroll-story landing (`web/src/Landing.tsx`); `#map` skips straight to the dashboard. Every source it cites is an APA 7 entry with a link in `web/src/sources.ts`, rendered by `web/src/References.tsx`; the checks are logged in `docs/factcheck/`.

To publish it, deploy `web/` as a static Vite site (for example Vercel with Root Directory `web`, build `npm run build`, output `dist`). It needs no server: links are `#` anchors, and all data is in `web/public/data/`.

One combined map answers five questions (color the map by each). It has a square for every 1 km of the study box (-95.95 to -94.8, 29.4 to 30.2): 13,299 squares. 7,800 are measured by the satellite (261 of them blended with a GPS station inside the square), 80 by a GPS station alone, 4,242 are estimated (below), and 1,177 have no reading: open water, or too far from any measurement (each says why).

- **Movement:** OPERA satellite rate 2016–2026 converted to vertical (fixed 38° incidence), pulled toward its 3 km neighbourhood where a square's own fit is noisy (`shrink_to_neighbours`; 12% of squares are pulled noticeably), and blended with a GPS station's rate where one is within 1 km (inverse-variance). The blending is re-tested against GPS on every export (`meta.blendTest`: typical difference 2.1 → 2.0 mm/yr, worst tenth 8.6 → 7.8, 1,984 squares).
- **Confidence:** High / Medium / Low from the fit error, a GPS cross-check, record jumpiness, and agreement with neighboring squares.
- **Future:** each square's season-aware trend (trend + yearly sine/cosine for clay shrink-swell), averaged 50/50 with the median rate within 3 km, continued to 2031 (`backend.forecast.seasonal_area_rates`). Chosen by `scripts/forecast_benchmark.py`, a walk-forward test of 9 methods from 21 start dates (2018–2025) at 1–5 years ahead, 84 tests each. Typical error per square (with the pre-registered reference): chosen 1.32 cm, tied with Theil-Sen 1.32; neighbourhood-smoothed 1.33; long-term rate 1.35; recency-weighted 1.42; no motion 1.69; gradient-boosted ML 1.77. Year-by-year 80% ranges come from the same tests (±1.5, 2.5, 3.1, 3.9, 4.4 cm for 1–5 years). The ML model (`backend/forecast.py` train_and_forecast) is kept as a documented experiment: it scored well on spatial cross-validation but not on later years. Pooled ML (HistGradientBoosting, ExtraTrees, Ridge) and mean-reversion of the shared shrink-swell signal were also tried and did not help overall.
- **Priority:** the plan's labels, first rule wins: No measurement → Review disagreement (GPS within 2 km differs by >5 mm/yr) → Investigate first (sinking in FEMA high-risk zone, GPS within 2 km) → Add monitoring here (same, no GPS within 2 km) → Observe (sinking outside the high-risk zone) → No clear motion. The numbered sensor pins are the top "Add monitoring here" squares by area sinking rate, 4 km apart.

- **Hazards:** flood, drought and ground-bending views (see below).

Each square's card also shows why the label matters (flooding, drainage, infrastructure) and how long NISAR, a permanent GPS station, or a low-cost node would need to confirm its rate. Those times assume white noise, so real waits are likely longer. They use NISAR's measured per-pass noise at the square's distance from region A (6–16 mm), 6.5 mm of daily wobble for a permanent GPS station (the middle of HoustonNet's 5–8 mm, Wang et al. 2022), and 10 mm for a low-cost node (a planning guess; the GroundTruth test was inconclusive). Confirming 10 mm/yr takes about 1.4 years for NISAR and 20 weeks for a permanent station.

Squares with no direct reading (but not water) are estimated, and their cards say so (D-047 kept this branch's export):

- **Gridding gaps** (2,724). OPERA pixels are grouped into 990 m blocks, so some ~870 m map squares get none. These are filled from the measured squares touching them (tested: 80% within 1.9 mm/yr) and take the lowest confidence among those squares.
- **Other gaps** (1,309). Estimated from at least 4 measured squares within 3 km by inverse-distance weighting (tested by hiding measured squares: median error 0.9 mm/yr, 80% within 2.4 mm/yr). Drawn lighter, always Low confidence.
- **Outside satellite coverage** (209). Estimated from at least 3 GPS stations with 5+ years of record within 10 km (median error 2.1 mm/yr, 80% within 4.8). Low confidence.

The forecast also uses NASADEM elevation, OPERA DSWx surface water, OPERA DIST land disturbance, and FEMA zone as static inputs (`scripts/build_forecast.py`); DIST also lowers confidence where >20% of a square is disturbed.

The Hardware page compares a low-cost GPS node (our prototype cost about $74) with a permanent station, and lists where each would go: 15 permanent-station sites (numbered pins), 99 low-cost node sites (diamonds: 30 where a node could confirm the sinking within 2 years, plus enough to put one within 6 km of every flagged flood-zone square), and 12 sites where nothing measures the ground yet. It also shows the GroundTruth sessions as recorded but inconclusive.

Website features: a 2016–2026 time-lapse of the ground sinking (Movement view, "Watch 2016–2026"), a five-step guided tour ("Take the tour"), a "most at-risk areas" list (fastest forecast sinking in high-risk flood zones, 5 km apart), neighborhood names in each card (OpenStreetMap Nominatim), address/ZIP search and "use my location", hover read-outs, links that reopen the same view (`#map?mode=future&year=2030&cell=...`), per-square Copy link / Download / Print, "faster than X% of Houston" comparison, CSV and JSON downloads on the How we know page, phone layout with a bottom sheet, Esc closes a square.

Loading: `cells.json` carries only what the map needs (under 1 MB compressed); each square's full record is in `details/<tile>.json` (16 km tiles) and is fetched when the square is opened.

To regenerate the data the site shows:

```bash
python3 scripts/build_grid.py          # full 1 km grid + FEMA zone per square (25-point sample)
python3 scripts/build_grid.py --layers # re-sample NASADEM, DSWx, DIST on every square (rasterio, pyproj)
python3 scripts/build_provisional.py   # needs numpy; writes data/derived/provisional/
python3 scripts/build_forecast.py      # needs scikit-learn; ML experiment + static features
python3 scripts/backtest_recent.py     # earlier out-of-time test (to March 2026)
python3 scripts/forecast_benchmark.py  # walk-forward benchmark that picks the forecast method
python3 scripts/build_hazards.py       # drought, bending, tests
python3 scripts/measure_nisar_noise.py # measured NISAR per-pass noise, read by export_web
python3 scripts/export_web.py          # writes web/public/data/
python3 -m unittest discover -s tests  # 144 tests (Python 3.14 venv), incl. checks on the exported site data
```

Both builds refuse demonstration data (`backend/publish_guard.py`) and hash every input and output (`backend/provenance.py`). The website export records the two gitignored intermediates it reads, with the command that regenerates them; their hashes must match `data/manifests/provisional_build.json`. `tests/test_claims_policy.py` fails if a forbidden phrase or a projection reaches the site.

### What the provisional build does

Everything is flagged `provisional_unreviewed` until the team approves the reference:

1. **Ramp removal.** A best-fit plane is removed from each NISAR pair. The raw pairs have 13–43 mm of frame-wide ionospheric/atmospheric scatter; after removal, 3–10 mm. Raw values are kept.
2. **Re-referencing.** Every NISAR and OPERA product is referenced to the median of the pre-registered region A (`config/preregistration.json`, PR-4 with amendment A1): every cell within 3 km of GPS stations DEN2 or TMCC (59 OPERA cells, 52 NISAR cells). Deep-seated GNSS stations (ADKS, LKHU, NETP, TXEX, UHKD), whose antennas sit on deep extensometer anchors, are never used as surface references (Wang et al. 2022, *J. Surv. Eng.* 148(4): 04022008).
3. **60-day NISAR chain.** The first five consecutive pairs are summed (intermediate-date noise cancels). Still not a rate.
4. **OPERA velocity.** The 30 chained frame-F38238 DISP-S1 products (2016-07-12 to 2026-03-22, D-040) are re-referenced and fit with a least-squares LOS velocity per cell. Frame F38239 supplies only squares F38238 never measures (south Houston); its rows never set the datum (D-044). A square counts if at least 90% of products pass, with its rate from observed intervals only; gapped squares lose confidence and are not drawn as a series (D-042).
5. **Check against GPS** (V3, PR-5). OPERA velocity vs. HoustonNet vertical rate projected into LOS at the nearest square within 1 km, at 64 continuous stations (at least 0.5 position days a day; reference, deep-seated and withheld stations excluded): r = 0.68, median |difference| 1.3 mm/yr LOS (1.7 mm/yr up/down), bias +0.6 mm/yr LOS. The 67 campaign stations are reported apart (`campaign_stations`: r = 0.84) and never mixed into the headline (D-051). Approximate: vertical-only projection, one incidence angle, overlapping but different time windows. The positive correlation also confirms OPERA's sign (positive = toward the satellite).
6. **NISAR signal check.** One ramp-removed 12-day pair scatters ~18 mm across squares vs. ~0.2 mm of expected real motion, and a single pair or the 60-day chain shows no correlation with OPERA (r ≈ 0). The map therefore defaults to OPERA-based priorities (`backend.insights.action_label`). NISAR views remain a quality preview. Over the full 22-pair chain, NISAR does rank squares the way OPERA predicted (prediction test above).

To switch to a team-reviewed reference, change the reference selection in `scripts/build_provisional.py` and run it with `--reference-status reviewed`.

### Fixes in this build

- **OPERA water mask was inverted.** The DISP-S1 spec defines `water_mask` as 0 = water, 1 = land; the adapter counted `> 0` as water, so almost every Houston cell read as 100% water. Fixed in `backend/ingestion/opera.py`; derived artifacts corrected with `scripts/correct_opera_water_fraction.py` (water = 1 − old value).
- **NISAR displacements were not re-referenced.** The scatter threshold was computed, but the reference median was never subtracted, so a frame-wide offset (~20 mm) would have turned most cells into "signals". `build_houston_evidence` now subtracts the reference median and keeps the raw value in `pair_los_displacement_raw_mm`.

### Extending the record to 2026

Done (D-040): the record now runs to 2026-03-22. `scripts/fetch_opera_extension.py` is how the 11 extra OPERA products (about 3.7 GB) were downloaded and ingested; rerun it only to rebuild from raw files. The cross-sensor check against NISAR (validation test V2) needs a different set: the products dated inside the NISAR window (plan task T1.6).

```bash
python3 -m pip install earthaccess numpy h5py pyproj
python3 scripts/fetch_opera_extension.py --delete-raw
```

### More NASA layers

`scripts/fetch_nasa_layers.py` downloads **NASADEM** elevation, **OPERA DSWx-S1** surface water, and **OPERA DIST-ALERT** land disturbance for Houston and samples them onto the 1 km cells (`backend/ingestion/raster_layers.py`). It needs an Earthdata login and a network that reaches NASA:

```bash
python3 -m pip install earthaccess rasterio numpy
python3 scripts/fetch_nasa_layers.py
python3 scripts/export_web.py
```

Do not assume NISAR GUNW phase corrections are applied. The `*CorrectionApplied` flags in each pair artifact are geocoding flags (audit A1); GUNW's ionospheric phase screen and tropospheric and tide lookup tables are not applied by default. Every artifact's `applied_corrections` is still `null` (unverified, plan B1). The provisional build removes a best-fit plane from each pair instead, which takes out most frame-wide atmospheric and ionospheric delay but not local structure, so the measured per-pass noise grows with distance from the reference.

### Hazards (5th map mode)

TerraGauge doesn't predict when a disaster comes; it shows what Houston's moving ground does when one does (`backend/hazards.py`, `scripts/build_hazards.py`):

- **Flood:** FEMA zone gives the odds (1%/yr in 1-in-100-year zones, about 26% over 30 years); the satellite-measured drop since 2016 gives how much deeper the same flood already stands (measured, not forecast; flood depths are never forecast, D-046). Optional reality check against USGS Hurricane Harvey high-water marks: `python3 scripts/fetch_harvey.py`.
- **Harvey check:** `scripts/build_harvey.py` compares the flood view with the USGS Hurricane Harvey flood maps for the San Jacinto basin (Garvin 2018, doi:10.5066/F7VH5N3N; download San_Jacinto.zip and, optionally, Depth_San_Jacinto.zip from ScienceBase item 5a85f30fe4b00f54eb36d3a9 into data/raw/harvey/). With the San Jacinto and upper Brazos basins (3,349 squares: north/northeast Houston plus Richmond, Sugar Land and Fort Bend), high-risk squares had 67% of their area flooded versus 10% for low-risk squares (San Jacinto depth: median 8.8 ft vs 3.3 ft); 27% of the flooded area was outside high-risk zones. Sinking speed alone did not predict one storm's flood extent. (The USGS STN web service now requires a DOI login, so `fetch_harvey.py` is kept only for reference.)
- **Drought:** extra drop beyond trend and season in the 2018 and 2023 droughts (clay shrink). Tested out-of-time on 8,056 squares: the 2018 response picked 2023's worst-hit squares (flagged squares dropped a median 69 mm vs 18 mm; AUC 0.85).
- **Ground bending:** steepest change in sinking rate to a neighbouring 1 km square; strains pipes, roads and slabs and can mark Houston's slipping faults. Tested on 7,501 squares: 2016-2021 hotspots stayed hotspots in 2021-2026 (median 3.5 vs 0.8 mm/yr per km; r = 0.44).

```bash
python3 scripts/fetch_harvey.py      # optional, needs internet
python3 scripts/build_hazards.py     # needs numpy
python3 scripts/export_web.py
```

## Project rules, audit and pre-registration

`CLAUDE.md` and `MASTER.md` hold the project rules; `docs/` holds the codebase audit, execution plan, decisions log (`docs/decisions.md`), source fact-check, pre-registration (`config/preregistration.json`), AI-use record (`docs/ai-use.md`), team notes and Space Apps rule notes. Builds write SHA-256 provenance manifests to `data/manifests/` (`backend/provenance.py`).

The forecast is kept as a tested trend continuation, not an unqualified prediction: it is shown with year-by-year 80% ranges from 84 walk-forward tests on past years and is limited to the 5 years those tests covered (see "Future" above and `scripts/forecast_benchmark.py`). This replaces the earlier no-projection rule (decision recorded in `docs/decisions.md`).

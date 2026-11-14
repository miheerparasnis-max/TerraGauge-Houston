# TerraGauge Houston

TerraGauge is an evidence-first monitoring-priority backend for Houston ground-motion analysis. It combines NASA NISAR pairwise line-of-sight observations, historic local GPS context, USGS groundwater context, FEMA station-point context, and a stationary GNSS repeatability experiment to explain **what evidence exists at a location and what is still missing**.

It does **not** forecast flooding, diagnose the cause of motion, or claim that a weekend GNSS receiver measured subsidence.

> **SI disclosure:** AI assistance was used for code scaffolding, debugging,
> and documentation editing. Team members reviewed, tested, and take
> responsibility for the final implementation and claims.

## Backend scope

This repository currently contains a dependency-free Python API with:

- transparent monitoring-priority rules;
- quality-mask enforcement;
- pairwise-signal gates that cannot silently become annual-rate claims;
- stationary GNSS session-noise calculations;
- validated JSON inputs and documented JSON outputs;
- a small demo fixture, visibly labeled as not source-derived; and
- a five-pair NISAR temporal-network diagnostic that refuses to emit a rate from a chain without independent loop closure; and
- structural integrity reports for every checked NISAR pair, including coordinate bounds, unique cell IDs, correction-flag preservation, and dominant-connected-component counts; and
- unit tests for the science and decision logic.

The frontend can call these endpoints without duplicating scientific logic.

## Run locally

Requires Python 3.11+.

```bash
python3 -m unittest discover -s tests -v
python3 -m backend
```

The API starts at `http://127.0.0.1:8000`.

## API contract

| Method | Route | Purpose |
|---|---|---|
| `GET` | `/health` | Service health check |
| `GET` | `/v1/summary` | Label counts, active thresholds, and disclaimer |
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
- The NISAR-derived artifacts preserve the product's ionospheric and tropospheric correction flags; TerraGauge never recommends applying an atmospheric correction twice.
- The demo dataset is only for development and cannot appear as a real Houston result.

## Next backend work

## Source-derived ingestion

The API is now paired with ingestion adapters for the real source products. They
write intermediate JSON artifacts with product paths, source filenames,
parameters, and limitations. They never silently turn a pair displacement into a
yearly rate.

Install ingestion-only dependencies in an isolated environment. This includes
the Earthdata client and GeoTIFF reader used by the optional NASADEM, DSWx, and
DIST adapters:

```bash
python3 -m pip install -r requirements.txt
```

### NISAR L2 GUNW

First inspect the actual Houston granule; do not assume a path or projection:

```bash
python3 -m backend.ingestion.cli inspect-h5 /path/to/NISAR_GUNW.h5 > data/derived/gunw-layout.json
```

Then extract one quality-preserving pair artifact. Use the verified product CRS,
x/y paths, wavelength, and acquisition dates from the product metadata:

```bash
python3 -m backend.ingestion.cli nisar-gunw /path/to/NISAR_GUNW.h5 data/derived/nisar-pair.json \
  --wavelength-m 0.238 \
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
coordinates, missing product correction flags, and malformed date metadata. It
also accepts only cells whose dominant local connected component matches the
scene-wide dominant component; this prevents isolated phase islands from being
treated as reliable evidence.

```bash
python3 -m backend.ingestion.cli validate-nisar-pair \
  data/derived/nisar_gunw_houston_20251102_20251114_pair_cells.json \
  data/derived/nisar_gunw_houston_20251102_20251114_pair_cells_integrity_report.json
```

### Multi-date NISAR network status

Five checked track-062 Houston pairs now cover six dates from 2025-11-02 through
2026-01-01. The reproducible diagnostic at
`data/derived/nisar_track062_network_diagnostic_20251102_20260101.json` finds a
connected **chain** with zero redundant edges. Accordingly, TerraGauge withholds
a temporal rate. This is a result, not a missing feature: a defensible rate needs
at least two independent loop-closure edges as well as a documented stable
reference region.

Recreate the graph audit with:

```bash
python3 -m backend.ingestion.cli temporal-network-diagnostic data/derived/nisar_track062_network_diagnostic.json \
  data/derived/nisar_gunw_houston_20251102_20251114_pair_cells.json \
  data/derived/nisar_gunw_houston_20251114_20251126_pair_cells.json \
  data/derived/nisar_gunw_houston_20251126_20251208_pair_cells.json \
  data/derived/nisar_gunw_houston_20251208_20251220_pair_cells.json \
  data/derived/nisar_gunw_houston_20251220_20260101_pair_cells.json
```

Only after the diagnostic reports
`eligible_for_reference_review_and_inversion` **and** an independent science
review documents the stable reference may an inversion run. The CLI requires
that review to be stated explicitly; a candidate patch or a repeated copy of a
pair never qualifies.

```bash
python3 -m backend.ingestion.cli temporal-invert data/derived/nisar_rate.json \
  --reference-cell VERIFIED-STABLE-CELL-ID \
  --reference-status reviewed \
  data/derived/nisar_gunw_houston_PAIR_A.json \
  data/derived/nisar_gunw_houston_PAIR_B.json \
  data/derived/nisar_gunw_houston_PAIR_C.json
```

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

When the LC29H(BS) arrives, keep the outdoor antenna fixed and complete three static sessions. Save the raw receiver log, converted RINEX observation file, static-solution height, and CORS overlap for each. Copy `data/groundtruth_session_manifest.template.json`, fill it with real values, then run:

```bash
python3 -m backend.ingestion.cli groundtruth-report data/groundtruth_session_manifest.json data/derived/groundtruth_report.json
```

A passing report proves only stationary receiver repeatability. It never proves Houston land motion.

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
log only proves that bytes were captured; keep the antenna fixed and use the
three-session GroundTruth manifest plus RTKLIB/RINEX conversion before making
any repeatability claim. An empty log is a diagnostic result, not evidence of
ground movement.

## Remaining source work

1. Science-review and document a stable reference region, then rebuild with `--reference-bbox WEST SOUTH EAST NORTH`.
2. Acquire at least two valid redundant same-track pair edges, then run the existing temporal-network inversion.
3. Add the event’s real LC29H(BS) raw-log, RINEX conversion, CORS overlap, and RTKLIB static-solution record.

## Website (provisional build)

A ready-made static website lives in `web/` (React + Vite + TypeScript + MapLibre). It reads precomputed JSON from `web/public/data/`; all science logic runs in Python.

```bash
cd web
npm install
npm run dev        # opens http://localhost:5173
```

One combined map of 1 km squares answers three questions (color the map by each):

- **Movement:** historical OPERA satellite rate converted to vertical. GPS stays a separate point-scale cross-check and monitoring-coverage signal rather than being blended across mismatched time windows.
- **Confidence:** High / Medium / Low from the fit error, a GPS cross-check within 3 km, record jumpiness, and agreement with the squares around it (`backend/insights.py`).
- **Priority:** Urgent / High / Watch / Stable / Check data, plus the top 15 suggested GPS sensor sites (sinking areas with no active station within 2 km, kept 4 km apart).

Future movement projections are deliberately withheld: the held-out back-test does not support them and the historical reference region is still unreviewed. Clicking a square opens a plain-language card with the evidence, sensor coverage, and what TerraGauge can't conclude. Other pages: "How we know" (data sources, GPS check, prediction test, why NISAR can't measure this yet) and "Our $74 sensor". The basemap is OpenFreeMap (no API key); without internet the map falls back to a plain background.

To regenerate the data the site shows:

```bash
python3 scripts/build_provisional.py   # needs numpy; writes data/derived/provisional/
python3 scripts/export_web.py          # writes web/public/data/
```

### What the provisional build does

Everything is flagged `provisional_unreviewed` until the team approves the reference:

1. **Ramp removal.** A best-fit plane is removed from each NISAR pair. The raw pairs have 13–43 mm of frame-wide ionospheric/atmospheric scatter; after removal, 3–10 mm. Raw values are kept.
2. **Re-referencing.** Cells are referenced to the median at half of the long-history HoustonNet stations with |vertical rate| ≤ 1 mm/yr; the other half are held out. (The single-patch candidate in `terragauge_reference_review_candidates_2026-11-07.json` is farmland where OPERA has too few coherent pixels.)
3. **60-day NISAR chain.** The five consecutive pairs are summed (intermediate-date noise cancels). Still not a rate.
4. **OPERA velocity.** The 19 chained OPERA DISP-S1 products (2016-07-12 to 2021-05-05) are re-referenced and fit with a least-squares LOS velocity per cell.
5. **Check against GPS.** OPERA velocity vs. HoustonNet vertical rate projected into LOS at 105 held-out stations: r = 0.66, median |difference| 1.7 mm/yr (approximate: vertical-only projection, overlapping but different time windows). Cells with an incomplete OPERA series are withheld rather than imputed.
6. **NISAR signal check.** NISAR 12-day noise is ~18 mm vs. ~0.2 mm of expected real motion, and NISAR shows no correlation with OPERA (r ≈ 0). The map therefore defaults to OPERA-based priorities (`backend.decision.classify_opera_velocity`, same action order). NISAR views remain as a quality preview.

To switch to a team-reviewed reference, change the reference selection in `scripts/build_provisional.py` and run it with `--reference-status reviewed`.

### Fixes in this build

- **OPERA water mask was inverted.** The DISP-S1 spec defines `water_mask` as 0 = water, 1 = land; the adapter counted `> 0` as water, so almost every Houston cell read as 100% water. Fixed in `backend/ingestion/opera.py`; derived artifacts corrected with `scripts/correct_opera_water_fraction.py` (water = 1 − old value).
- **NISAR displacements were not re-referenced.** The scatter threshold was computed, but the reference median was never subtracted, so a frame-wide offset (~20 mm) would have turned most cells into "signals". `build_houston_evidence` now subtracts the reference median and keeps the raw value in `pair_los_displacement_raw_mm`.

### Extending the record to 2026

The OPERA record in the repo ends in May 2021. `scripts/fetch_opera_extension.py` downloads the 11 OPERA products (about 3.7 GB) that continue the chain to March 2026, ingests them, and rebuilds the site data. With ~10 years of data the backtest compares five years against the next five, which is long enough for a real forecast test.

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

MERRA-2 weather correction is not needed: the NISAR GUNW products already have wet and hydrostatic tropospheric and ionospheric corrections applied (see `source_processing_corrections` in each pair artifact).

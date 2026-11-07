# TerraGauge Houston

TerraGauge is an evidence-first monitoring-priority backend for Houston ground-motion analysis. It combines NASA NISAR/OPERA-derived cell inputs, local GPS comparison, flood exposure, and a stationary GNSS noise-floor experiment to explain **where an analyst should investigate first and why**.

It does **not** forecast flooding, diagnose the cause of motion, or claim that a weekend GNSS receiver measured subsidence.

## Backend scope

This repository currently contains a dependency-free Python API with:

- transparent monitoring-priority rules;
- quality-mask enforcement;
- lower-bound radar detectability calculations;
- stationary GNSS session-noise calculations;
- validated JSON inputs and documented JSON outputs;
- a small demo fixture, visibly labeled as not source-derived; and
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
| `POST` | `/v1/analyze-cell` | Analyze a validated cell without saving it |
| `POST` | `/v1/gnss/noise-floor` | Calculate stationary GNSS session scatter |

Append `?temporal_network=true` only after the science lead confirms that the NISAR temporal network is sufficient for an empirical lower-bound calculation. Without it, detectability is deliberately returned as a scenario lower bound.

### Example requests

```bash
curl http://127.0.0.1:8000/v1/summary
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

Each cell must provide coordinates, LOS rate/quality values, flood exposure, and any available GPS/USGS evidence. The source-specific NISAR/OPERA ingestion pipeline should write this standard contract after processing—not bypass the API logic.

## Science safeguards

- NISAR motion is line-of-sight motion, not automatically vertical subsidence.
- Every detectability calculation is a lower bound under a white-noise assumption.
- GUNW interferograms are not independent raw epochs. A short temporal stack must remain a scenario estimate.
- A GNSS node result represents stationary receiver repeatability, not observed land motion.
- The demo dataset is only for development and cannot appear as a real Houston result.

## Next backend work

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

### OPERA DISP-S1

OPERA context is ingested from the raw displacement layer and recommended mask,
not a portal screenshot or color ramp:

```bash
python3 -m backend.ingestion.cli opera-disp /path/to/OPERA_DISP.h5 data/derived/opera-pair.json \
  --crs EPSG:32615 --reference-date YYYY-MM-DD --secondary-date YYYY-MM-DD
```

Only `recommended_mask == 1` pixels are included. Build an OPERA historic trend
only after ingesting a dated sequence of products and documenting reference
handling.

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

## Remaining source work

1. Download one verified same-track Houston GUNW collection and produce pair artifacts.
2. Implement a temporal-network inversion only after the real pair graph passes the stack gate.
3. Add USGS groundwater/compaction and verified flood-layer joins as separate, dated artifacts.
4. Add the event’s real LC29H(BS) raw-log to RINEX/RTKLIB processing record.
5. Replace demo data with a dated, versioned data ledger and source-derived results.

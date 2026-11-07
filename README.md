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

1. Add the source-derived NISAR GUNW ingestion adapter after product variables are verified.
2. Add OPERA, HoustonNet, USGS, and flood-layer adapters that output the same cell contract.
3. Add the event’s real LC29H(BS) raw-log to RINEX/RTKLIB processing record.
4. Replace demo data with a dated, versioned data ledger and source-derived results.

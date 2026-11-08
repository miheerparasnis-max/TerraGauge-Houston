"""USGS/HGSD extensometer time-series normalization for mechanism context.

Compaction records are never converted into a radar rate or causal conclusion;
they are colocated mechanism evidence for a reviewer to inspect.
"""

from __future__ import annotations

import csv
import json
from datetime import date
from pathlib import Path
from typing import Any

from .common import one_km_cell_id


REQUIRED_FIELDS = {"station_id", "longitude", "latitude", "date", "cumulative_compaction"}


def import_extensometer_csv(input_path: str | Path, column_map: dict[str, str], unit: str = "ft") -> dict[str, Any]:
    """Normalize an explicitly mapped cumulative-compaction CSV.

    The input's column names are never guessed: this keeps different USGS/HGSD
    releases auditable and prevents an elevation field being mistaken for
    cumulative compaction.
    """
    missing = REQUIRED_FIELDS - set(column_map)
    if missing:
        raise ValueError(f"column_map is missing: {', '.join(sorted(missing))}")
    rows_by_station: dict[str, list[dict[str, Any]]] = {}
    with Path(input_path).open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames:
            raise ValueError("CSV requires a header row")
        unknown = set(column_map.values()) - set(reader.fieldnames)
        if unknown:
            raise ValueError(f"mapped columns absent from CSV: {', '.join(sorted(unknown))}")
        for raw in reader:
            try:
                station_id = raw[column_map["station_id"]].strip()
                longitude = float(raw[column_map["longitude"]])
                latitude = float(raw[column_map["latitude"]])
                observed = date.fromisoformat(raw[column_map["date"]][:10]).isoformat()
                cumulative = float(raw[column_map["cumulative_compaction"]])
            except (KeyError, TypeError, ValueError):
                continue
            if not station_id or not (-180 <= longitude <= 180 and -90 <= latitude <= 90):
                continue
            rows_by_station.setdefault(station_id, []).append({"date": observed, "cumulative_compaction": cumulative, "longitude": longitude, "latitude": latitude})
    stations = []
    for station_id, rows in sorted(rows_by_station.items()):
        rows.sort(key=lambda row: row["date"])
        first, last = rows[0], rows[-1]
        stations.append({
            "station_id": station_id,
            "longitude": first["longitude"],
            "latitude": first["latitude"],
            "cell_id": one_km_cell_id(first["longitude"], first["latitude"]),
            "unit": unit,
            "first_observation": {"date": first["date"], "cumulative_compaction": first["cumulative_compaction"]},
            "last_observation": {"date": last["date"], "cumulative_compaction": last["cumulative_compaction"]},
            "cumulative_compaction_change": last["cumulative_compaction"] - first["cumulative_compaction"],
            "observation_count": len(rows),
            "source_status": "source_derived",
        })
    if not stations:
        raise ValueError("no valid extensometer observations remained after parsing")
    return {
        "artifact_type": "usgs_extensometer_compaction_summary",
        "source_file": str(input_path),
        "column_map": column_map,
        "stations": stations,
        "limitations": [
            "Cumulative compaction is station-specific subsurface mechanism context, not a citywide map.",
            "Do not compare values across stations until datum, screened interval, and time span are reviewed.",
            "A compaction change does not prove the cause of a radar observation.",
        ],
    }


def write_extensometer_csv(input_path: str | Path, output_path: str | Path, column_map: dict[str, str], unit: str = "ft") -> None:
    Path(output_path).write_text(json.dumps(import_extensometer_csv(input_path, column_map, unit), indent=2), encoding="utf-8")

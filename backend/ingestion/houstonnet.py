"""HoustonNet station-velocity import with explicit column mapping."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from .common import one_km_cell_id


REQUIRED_COLUMNS = ("station_id", "longitude", "latitude", "east_mm_year", "north_mm_year", "up_mm_year")


def import_velocity_csv(path: str | Path, column_map: dict[str, str]) -> dict[str, Any]:
    """Normalize a checked HoustonNet velocity export.

    The public archive contains several products/reference frames. Requiring an
    explicit map prevents the backend from silently mixing columns or frames.
    """
    missing = [name for name in REQUIRED_COLUMNS if name not in column_map]
    if missing:
        raise ValueError(f"column_map missing: {', '.join(missing)}")
    stations: list[dict[str, Any]] = []
    with Path(path).open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames is None:
            raise ValueError("velocity CSV needs a header row")
        actual = set(reader.fieldnames)
        absent = [source for source in column_map.values() if source not in actual]
        if absent:
            raise ValueError(f"CSV is missing mapped columns: {', '.join(absent)}")
        for row in reader:
            longitude = float(row[column_map["longitude"]])
            latitude = float(row[column_map["latitude"]])
            stations.append({
                "station_id": row[column_map["station_id"]].strip(),
                "longitude": longitude,
                "latitude": latitude,
                "cell_id": one_km_cell_id(longitude, latitude),
                "east_mm_year": float(row[column_map["east_mm_year"]]),
                "north_mm_year": float(row[column_map["north_mm_year"]]),
                "up_mm_year": float(row[column_map["up_mm_year"]]),
                "source_status": "source_derived",
            })
    return {
        "artifact_type": "houstonnet_velocity_stations",
        "source_file": str(path),
        "column_map": column_map,
        "limitations": [
            "Reference frame and velocity time span must be recorded alongside this artifact.",
            "ENU velocities must be projected into the radar line of sight before comparison.",
        ],
        "stations": stations,
    }


def write_velocity_stations(input_path: str | Path, output_path: str | Path, column_map: dict[str, str]) -> None:
    Path(output_path).write_text(json.dumps(import_velocity_csv(input_path, column_map), indent=2), encoding="utf-8")

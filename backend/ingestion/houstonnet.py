"""HoustonNet station-velocity import with explicit column mapping."""

from __future__ import annotations

import csv
import json
import tarfile
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


def import_release_summary(archive_path: str | Path) -> dict[str, Any]:
    """Read the official 2024 HoustonNet summary table directly from its TGZ release."""
    member_name = "./HoustonNet_2024_Data_Release/A_HGSD_Summary_table_1993-2023.txt"
    with tarfile.open(archive_path, "r:gz") as archive:
        stream = archive.extractfile(member_name)
        if stream is None:
            raise ValueError("HoustonNet summary table not found in archive")
        lines = stream.read().decode("utf-8").splitlines()[2:]
    stations = []
    for line in lines:
        fields = line.split()
        if len(fields) != 9:
            continue
        station, longitude, latitude, start, end, years, samples, displacement, rate = fields[0], *fields[1:]
        # 9000.0 is HoustonNet's sentinel for an invalid/undefined rate.
        vertical_rate = float(rate)
        if abs(vertical_rate) >= 8000:
            continue
        stations.append({"station_id": station, "longitude": float(longitude), "latitude": float(latitude), "start_decimal_year": float(start), "end_decimal_year": float(end), "history_years": float(years), "samples": int(samples), "total_up_down_cm": float(displacement), "up_mm_year": vertical_rate, "source_status": "source_derived"})
    return {"artifact_type": "houstonnet_2024_summary", "source_archive": str(archive_path), "reference_frame": "See HoustonNet release summary documentation before radar comparison", "limitations": ["Vertical linear rates span station-specific historical windows.", "Rates must be time-matched and LOS-projected before comparison to NISAR."], "stations": stations}


def write_release_summary(archive_path: str | Path, output_path: str | Path) -> None:
    Path(output_path).write_text(json.dumps(import_release_summary(archive_path), indent=2), encoding="utf-8")

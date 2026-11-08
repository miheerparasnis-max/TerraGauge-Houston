"""USGS/HGSD extensometer time-series normalization for mechanism context.

Compaction records are never converted into a radar rate or causal conclusion;
they are colocated mechanism evidence for a reviewer to inspect.
"""

from __future__ import annotations

import csv
import json
from datetime import date, datetime
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


def _release_name(filename: str) -> str:
    """Map published TABLE filenames to the official TABLE1 GENERAL_NM values."""
    stem = filename.removeprefix("TABLE").split("_", 1)[-1].removesuffix("_2023.txt")
    aliases = {"TexasCity": "Texas City", "LakeHouston": "Lake Houston", "EastEnd": "East End", "JohnsonSpaceCenter_NASA": "Johnson Space Center", "ClearLakeShallow": "Clear Lake Shallow", "ClearLakeDeep": "Clear Lake Deep", "BaytownC1_Shallow": "Baytown Shallow", "BaytownC2_Deep": "Baytown Deep", "FortBend_CincoMUD": "Fort Bend"}
    return aliases.get(stem, stem.replace("_", " "))


def import_usgs_2023_release(directory: str | Path) -> dict[str, Any]:
    """Normalize the official USGS P9YGUE2V TABLE1/TABLE2-15 release layout."""
    root = Path(directory)
    site_path = root / "TABLE1_CompactionSites.txt"
    if not site_path.is_file():
        raise ValueError("official release directory requires TABLE1_CompactionSites.txt")
    with site_path.open(newline="", encoding="utf-8-sig") as stream:
        site_rows = {row["GENERAL_NM"].strip(): row for row in csv.DictReader(stream, delimiter="\t")}
    stations = []
    skipped = []
    for path in sorted(root.glob("TABLE[2-9]*_2023.txt")) + sorted(root.glob("TABLE1[0-5]*_2023.txt")):
        name = _release_name(path.name)
        site = site_rows.get(name)
        if site is None:
            skipped.append({"file": path.name, "reason": "no matching TABLE1 site"})
            continue
        observations = []
        with path.open(newline="", encoding="utf-8-sig") as stream:
            for row in csv.DictReader(stream, delimiter="\t"):
                try:
                    observed = datetime.strptime(row["DATE"].strip(), "%m/%d/%Y").date().isoformat()
                    value = float(row["CUMULATIVE_COMPACTION"])
                except (KeyError, TypeError, ValueError):
                    continue
                observations.append((observed, value))
        if not observations:
            skipped.append({"file": path.name, "reason": "no usable observations"})
            continue
        observations.sort()
        first, last = observations[0], observations[-1]
        longitude, latitude = float(site["DEC_LONG_VA"]), float(site["DEC_LAT_VA"])
        stations.append({
            "station_id": site["SITE_NO"], "station_name": site["STATION_NM"], "general_name": name,
            "compaction_interval": site["COMPACTION_INTERVAL"], "anchor_depth_ft": float(site["ANCHOR_DEPTH"].replace(",", "")),
            "longitude": longitude, "latitude": latitude, "cell_id": one_km_cell_id(longitude, latitude), "unit": "ft",
            "first_observation": {"date": first[0], "cumulative_compaction": first[1]},
            "last_observation": {"date": last[0], "cumulative_compaction": last[1]},
            "cumulative_compaction_change": last[1] - first[1], "observation_count": len(observations), "source_status": "source_derived",
        })
    return {"artifact_type": "usgs_extensometer_compaction_summary", "source_release": "USGS DOI 10.5066/P9YGUE2V, version 6.0 (September 2024), cumulative compaction through 2023", "source_directory": str(root), "station_count": len(stations), "stations": stations, "skipped_files": skipped, "limitations": ["Cumulative compaction is station-specific subsurface mechanism context, not a citywide motion map.", "Do not compare values across stations until datum, monitored interval, and time span are reviewed.", "A compaction change does not prove the cause of a radar observation."]}


def write_usgs_2023_release(directory: str | Path, output_path: str | Path) -> None:
    Path(output_path).write_text(json.dumps(import_usgs_2023_release(directory), indent=2), encoding="utf-8")

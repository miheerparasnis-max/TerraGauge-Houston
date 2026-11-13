"""USGS NWIS groundwater JSON normalization for evidence cards.

The adapter keeps the sign convention explicit: a positive `depth_change_ft`
means the water level became deeper below land surface over the retrieved
window. It does not infer causality or turn a water-level change into motion.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .common import one_km_cell_id


def import_groundwater_daily(path: str | Path) -> dict[str, Any]:
    """Normalize a downloaded USGS NWIS daily-values JSON response."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    series = payload.get("value", {}).get("timeSeries", [])
    records: list[dict[str, Any]] = []
    for ordinal, item in enumerate(series):
        source = item.get("sourceInfo", {})
        location = source.get("geoLocation", {}).get("geogLocation", {})
        codes = source.get("siteCode", [])
        values_groups = item.get("values", [])
        values = values_groups[0].get("value", []) if values_groups else []
        try:
            no_data = float(item.get("variable", {}).get("noDataValue", -999999.0))
        except (TypeError, ValueError):
            no_data = -999999.0
        observations = []
        for value in values:
            try:
                depth = float(value["value"])
            except (KeyError, TypeError, ValueError):
                continue
            # USGS marks missing days with a no-data value (-999999); a real
            # depth is never anywhere near that.
            if depth == no_data or depth <= -9999:
                continue
            observations.append((value["dateTime"], depth))
        if not codes or not observations or "longitude" not in location or "latitude" not in location:
            continue
        observations.sort(key=lambda entry: entry[0])
        start_time, start_depth = observations[0]
        end_time, end_depth = observations[-1]
        longitude, latitude = float(location["longitude"]), float(location["latitude"])
        variable = item.get("variable", {})
        records.append({
            "series_id": f"{codes[0]['value']}:{ordinal}",
            "site_id": codes[0]["value"],
            "site_name": source.get("siteName"),
            "longitude": longitude,
            "latitude": latitude,
            "cell_id": one_km_cell_id(longitude, latitude),
            "parameter_code": variable.get("variableCode", [{}])[0].get("value"),
            "parameter_name": variable.get("variableName"),
            "unit": variable.get("unit", {}).get("unitCode"),
            "first_observation": {"time": start_time, "depth_below_land_surface": start_depth},
            "last_observation": {"time": end_time, "depth_below_land_surface": end_depth},
            "depth_change_ft": end_depth - start_depth,
            "observation_count": len(observations),
            "source_status": "source_derived",
        })
    return {
        "artifact_type": "usgs_groundwater_daily_summary",
        "source_file": str(path),
        "sign_convention": "Positive depth_change_ft means water was deeper below land surface at the end of the retrieved window.",
        "limitations": [
            "This is local groundwater evidence, not a causal subsidence finding.",
            "Multiple series may exist at one site for different monitored intervals; preserve series_id when joining.",
            "Time-match and document aquifer/interval metadata before comparing stations.",
        ],
        "series": records,
    }


def write_groundwater_daily(input_path: str | Path, output_path: str | Path) -> None:
    Path(output_path).write_text(json.dumps(import_groundwater_daily(input_path), indent=2), encoding="utf-8")

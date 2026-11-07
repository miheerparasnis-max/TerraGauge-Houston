"""Normalize FEMA National Flood Hazard Layer point-query evidence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def join_nfhl_point_responses(groundwater_path: str | Path, response_directory: str | Path) -> dict[str, Any]:
    """Join saved FEMA NFHL point queries to unique USGS monitoring locations.

    A point classification is intentionally stored as evidence at that location;
    it must not be extrapolated to an entire radar cell or neighborhood.
    """
    groundwater = json.loads(Path(groundwater_path).read_text(encoding="utf-8"))
    directory = Path(response_directory)
    sites: dict[str, dict[str, Any]] = {}
    for series in groundwater["series"]:
        sites.setdefault(series["site_id"], series)
    results = []
    for site_id, series in sorted(sites.items()):
        response_path = directory / f"fema-{site_id}.json"
        response = json.loads(response_path.read_text(encoding="utf-8"))
        attributes = response.get("features", [{}])[0].get("attributes")
        results.append({
            "site_id": site_id,
            "site_name": series.get("site_name"),
            "longitude": series["longitude"],
            "latitude": series["latitude"],
            "cell_id": series["cell_id"],
            "flood_zone": attributes.get("FLD_ZONE") if attributes else None,
            "zone_subtype": attributes.get("ZONE_SUBTY") if attributes else None,
            "is_special_flood_hazard_area": attributes.get("SFHA_TF") == "T" if attributes else None,
            "query_status": "classified" if attributes else "no_feature_returned",
            "source_status": "source_derived",
        })
    return {
        "artifact_type": "fema_nfhl_usgs_station_join",
        "source_layer": "FEMA National Flood Hazard Layer, MapServer layer 28 (Flood Hazard Zones)",
        "limitations": [
            "A point zone lookup is evidence at the monitoring location only, not flood depth or parcel-level advice.",
            "Use the current FEMA map and local authority for decisions affecting a property or permit.",
        ],
        "stations": results,
    }


def write_nfhl_point_join(groundwater_path: str | Path, response_directory: str | Path, output_path: str | Path) -> None:
    Path(output_path).write_text(json.dumps(join_nfhl_point_responses(groundwater_path, response_directory), indent=2), encoding="utf-8")

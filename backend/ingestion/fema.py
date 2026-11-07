"""Normalize FEMA National Flood Hazard Layer evidence without guessing flood risk."""

from __future__ import annotations

import json
from math import floor
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import urlopen


NFHL_ZONE_QUERY = "https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28/query"
NFHL_SOURCE = "FEMA National Flood Hazard Layer, MapServer layer 28 (Flood Hazard Zones)"


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
        "source_layer": NFHL_SOURCE,
        "limitations": [
            "A point zone lookup is evidence at the monitoring location only, not flood depth or parcel-level advice.",
            "Use the current FEMA map and local authority for decisions affecting a property or permit.",
        ],
        "stations": results,
    }


def write_nfhl_point_join(groundwater_path: str | Path, response_directory: str | Path, output_path: str | Path) -> None:
    Path(output_path).write_text(json.dumps(join_nfhl_point_responses(groundwater_path, response_directory), indent=2), encoding="utf-8")


def _fetch_geojson(params: dict[str, Any]) -> dict[str, Any]:
    url = f"{NFHL_ZONE_QUERY}?{urlencode(params)}"
    with urlopen(url, timeout=90) as response:  # nosec B310 - fixed public FEMA endpoint
        payload = json.loads(response.read().decode("utf-8"))
    if "error" in payload:
        raise RuntimeError(f"FEMA NFHL query failed: {payload['error']}")
    return payload


def download_nfhl_zone_overlay(bounds: tuple[float, float, float, float], tile_degrees: float = 0.10, max_allowable_offset_degrees: float = 0.001) -> dict[str, Any]:
    """Download FEMA flood-zone polygons in small tiles and deduplicate by OBJECTID.

    The tile approach avoids silently truncating a dense citywide ArcGIS query.
    It downloads polygons that intersect the study bounds; the later classifier
    reports a cell-center zone context, not flood depth or parcel advice.
    """
    west, south, east, north = bounds
    if not (west < east and south < north and tile_degrees > 0):
        raise ValueError("bounds must be west, south, east, north and tile_degrees must be positive")
    features: dict[str, dict[str, Any]] = {}
    tiles = 0
    longitude = west
    while longitude < east:
        latitude = south
        right = min(longitude + tile_degrees, east)
        while latitude < north:
            top = min(latitude + tile_degrees, north)
            offset = 0
            tiles += 1
            while True:
                payload = _fetch_geojson({
                    "where": "1=1",
                    "geometry": f"{longitude},{latitude},{right},{top}",
                    "geometryType": "esriGeometryEnvelope",
                    "inSR": 4326,
                    "spatialRel": "esriSpatialRelIntersects",
                    "outFields": "OBJECTID,FLD_ZONE,ZONE_SUBTY,SFHA_TF",
                    "returnGeometry": "true",
                    "resultOffset": offset,
                    "resultRecordCount": 1000,
                    "maxAllowableOffset": max_allowable_offset_degrees,
                    "f": "geojson",
                })
                page = payload.get("features", [])
                for feature in page:
                    object_id = feature.get("properties", {}).get("OBJECTID")
                    if object_id is not None:
                        features[str(object_id)] = feature
                if len(page) < 1000:
                    break
                offset += len(page)
            latitude = top
        longitude = right
    return {
        "artifact_type": "fema_nfhl_houston_zone_overlay",
        "source_layer": NFHL_SOURCE,
        "study_bounds_wgs84": list(bounds),
        "tile_degrees": tile_degrees,
        "max_allowable_offset_degrees": max_allowable_offset_degrees,
        "tile_count": tiles,
        "feature_count": len(features),
        "features": list(features.values()),
        "limitations": [
            "Polygons provide flood-zone context, not flood depth, parcel determination, or a current flood forecast.",
            "Coverage and map amendments must be checked against the current FEMA map for decisions affecting a property or permit.",
        ],
    }


def merge_nfhl_geojson_tiles(tile_directory: str | Path, bounds: tuple[float, float, float, float], tile_degrees: float, max_allowable_offset_degrees: float) -> dict[str, Any]:
    """Merge saved FEMA GeoJSON tiles; this supports fully auditable downloads."""
    features: dict[str, dict[str, Any]] = {}
    paths = sorted(Path(tile_directory).glob("*.json"))
    if not paths:
        raise ValueError("tile directory contains no GeoJSON files")
    for path in paths:
        for feature in json.loads(path.read_text(encoding="utf-8")).get("features", []):
            object_id = feature.get("properties", {}).get("OBJECTID")
            if object_id is not None:
                features[str(object_id)] = feature
    return {
        "artifact_type": "fema_nfhl_houston_zone_overlay",
        "source_layer": NFHL_SOURCE,
        "study_bounds_wgs84": list(bounds),
        "tile_degrees": tile_degrees,
        "tile_count": len(paths),
        "max_allowable_offset_degrees": max_allowable_offset_degrees,
        "feature_count": len(features),
        "features": list(features.values()),
        "limitations": [
            "Polygon vertices were generalized by the documented FEMA service tolerance; this is suitable for 1 km cell-center context, not property-level decisions.",
            "Polygons provide flood-zone context, not flood depth, parcel determination, or a current flood forecast.",
        ],
    }


def write_nfhl_zone_overlay(bounds: tuple[float, float, float, float], output_path: str | Path, tile_degrees: float = 0.10) -> None:
    Path(output_path).write_text(json.dumps(download_nfhl_zone_overlay(bounds, tile_degrees), indent=2), encoding="utf-8")


def write_merged_nfhl_geojson_tiles(tile_directory: str | Path, bounds: tuple[float, float, float, float], tile_degrees: float, max_allowable_offset_degrees: float, output_path: str | Path) -> None:
    Path(output_path).write_text(json.dumps(merge_nfhl_geojson_tiles(tile_directory, bounds, tile_degrees, max_allowable_offset_degrees), indent=2), encoding="utf-8")


def _ring_contains(longitude: float, latitude: float, ring: list[list[float]]) -> bool:
    inside = False
    for index, point in enumerate(ring):
        previous = ring[index - 1]
        x1, y1 = float(previous[0]), float(previous[1])
        x2, y2 = float(point[0]), float(point[1])
        if (y1 > latitude) != (y2 > latitude):
            crossing = (x2 - x1) * (latitude - y1) / (y2 - y1) + x1
            if longitude < crossing:
                inside = not inside
    return inside


def _polygon_contains(longitude: float, latitude: float, rings: list[list[list[float]]]) -> bool:
    return bool(rings) and _ring_contains(longitude, latitude, rings[0]) and not any(_ring_contains(longitude, latitude, hole) for hole in rings[1:])


def _geometry_contains(longitude: float, latitude: float, geometry: dict[str, Any]) -> bool:
    if geometry.get("type") == "Polygon":
        return _polygon_contains(longitude, latitude, geometry.get("coordinates", []))
    if geometry.get("type") == "MultiPolygon":
        return any(_polygon_contains(longitude, latitude, polygon) for polygon in geometry.get("coordinates", []))
    return False


def _geometry_bounds(geometry: dict[str, Any]) -> tuple[float, float, float, float] | None:
    coordinates = []
    if geometry.get("type") == "Polygon":
        coordinates = [point for ring in geometry.get("coordinates", []) for point in ring]
    elif geometry.get("type") == "MultiPolygon":
        coordinates = [point for polygon in geometry.get("coordinates", []) for ring in polygon for point in ring]
    if not coordinates:
        return None
    longitudes, latitudes = zip(*((float(point[0]), float(point[1])) for point in coordinates))
    return min(longitudes), min(latitudes), max(longitudes), max(latitudes)


def classify_cell_centers(nisar_path: str | Path, overlay_path: str | Path, grid_degrees: float = 0.10) -> dict[str, Any]:
    """Assign each radar-cell center its FEMA polygon context, if covered."""
    nisar = json.loads(Path(nisar_path).read_text(encoding="utf-8"))
    overlay = json.loads(Path(overlay_path).read_text(encoding="utf-8"))
    index: dict[tuple[int, int], list[dict[str, Any]]] = {}
    for feature in overlay.get("features", []):
        bounds = _geometry_bounds(feature.get("geometry", {}))
        if bounds is None:
            continue
        west, south, east, north = bounds
        for x in range(floor(west / grid_degrees), floor(east / grid_degrees) + 1):
            for y in range(floor(south / grid_degrees), floor(north / grid_degrees) + 1):
                index.setdefault((x, y), []).append(feature)
    cells = []
    for cell in nisar.get("cells", []):
        longitude, latitude = float(cell["longitude"]), float(cell["latitude"])
        candidates = index.get((floor(longitude / grid_degrees), floor(latitude / grid_degrees)), [])
        matches = [feature for feature in candidates if _geometry_contains(longitude, latitude, feature.get("geometry", {}))]
        ordered = sorted(matches, key=lambda feature: feature.get("properties", {}).get("SFHA_TF") != "T")
        chosen = ordered[0].get("properties", {}) if ordered else {}
        cells.append({
            "cell_id": cell["cell_id"],
            "flood_exposed": any(feature.get("properties", {}).get("SFHA_TF") == "T" for feature in matches) if matches else False,
            "flood_zone": chosen.get("FLD_ZONE"),
            "zone_subtype": chosen.get("ZONE_SUBTY"),
            "matching_polygon_count": len(matches),
        })
    return {
        "artifact_type": "fema_nfhl_nisar_cell_center_context",
        "source_layer": overlay.get("source_layer", NFHL_SOURCE),
        "source_overlay": str(overlay_path),
        "cell_context_method": "NISAR-cell center point-in-polygon classification against downloaded FEMA NFHL polygons.",
        "limitations": [
            "This is flood-zone context sampled at the aggregated radar-cell center; it is not a cell-area percentage, flood depth, parcel determination, or forecast.",
            "A cell with no matching polygon is recorded as not mapped to an SFHA polygon by this layer, not as risk-free.",
        ],
        "cells": cells,
    }


def write_cell_center_flood_context(nisar_path: str | Path, overlay_path: str | Path, output_path: str | Path) -> None:
    Path(output_path).write_text(json.dumps(classify_cell_centers(nisar_path, overlay_path), indent=2), encoding="utf-8")

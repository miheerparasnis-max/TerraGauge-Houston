"""Sample NASA GeoTIFF layers (NASADEM, OPERA DSWx, OPERA DIST) onto TerraGauge 1 km cells.

All three products are distributed as (cloud-optimized) GeoTIFF tiles. Each
TerraGauge cell is a 1 km Web-Mercator square identified by its cell_id; this
module reads the pixels inside that square from every tile that overlaps it
and reduces them to one context value per cell.

Class codes below follow the OPERA product specifications as published; check
them against the spec of the exact product version you download before use:
- DSWx WTR layer: 0 not water, 1 open water, 2 partial surface water (HLS);
  values >= 250 are masked/fill (cloud, snow, ocean mask, layover, no data).
- DIST-ALERT VEG-DIST-STATUS: 0 none; 1/2/3 first/provisional/confirmed <50%
  loss; 4/5/6 the same for >=50% loss; 7/8 finished <50% / >=50%; 255 no data.
  Only confirmed or finished disturbance (3, 6, 7, 8) is counted.
"""

from __future__ import annotations

import json
import re
from math import atan, exp, pi
from pathlib import Path
from typing import Any, Callable, Iterable

R = 6378137.0
DSWX_WATER = {1, 2}
DIST_CONFIRMED = {3, 6, 7, 8}


def cell_bounds_lonlat(cell_id: str) -> tuple[float, float, float, float]:
    match = re.fullmatch(r"epsg3857-1km-(-?\d+)-(-?\d+)", cell_id)
    if not match:
        raise ValueError(f"not a TerraGauge 1 km cell id: {cell_id}")
    ix, iy = int(match.group(1)), int(match.group(2))
    x0, y0 = ix * 1000.0, iy * 1000.0

    def lon(x: float) -> float:
        return x / R * 180.0 / pi

    def lat(y: float) -> float:
        return (2 * atan(exp(y / R)) - pi / 2) * 180.0 / pi

    return lon(x0), lat(y0), lon(x0 + 1000.0), lat(y0 + 1000.0)


def _windows(paths: Iterable[str | Path], cells: list[dict[str, Any]]):
    """Yield (cell, pixel block, nodata) for every tile that overlaps a cell.

    Each tile is read into memory once; only cells whose centre lies inside
    the tile's footprint are visited, so 100+ tiles stay fast.
    """
    import numpy as np
    import rasterio
    from pyproj import Transformer

    for path in paths:
        with rasterio.open(path) as src:
            data = src.read(1)
            nodata = src.nodata
            to_src = Transformer.from_crs("EPSG:4326", src.crs, always_xy=True)
            inverse = ~src.transform
            height, width = data.shape
            for cell in cells:
                west, south, east, north = cell_bounds_lonlat(cell["cell_id"])
                xs, ys = to_src.transform([west, east, west, east], [south, south, north, north])
                cols, rows = zip(*(inverse * (x, y) for x, y in zip(xs, ys)))
                c0, c1 = max(int(min(cols)), 0), min(int(max(cols)) + 1, width)
                r0, r1 = max(int(min(rows)), 0), min(int(max(rows)) + 1, height)
                if c0 >= c1 or r0 >= r1:
                    continue
                yield cell, np.asarray(data[r0:r1, c0:c1]), nodata


def sample_layer(paths: list[str | Path], cells: list[dict[str, Any]], kind: str) -> list[dict[str, Any]]:
    """Return one record per cell that any tile covers."""
    import numpy as np

    acc: dict[str, dict[str, float]] = {}
    for cell, data, nodata in _windows(paths, cells):
        slot = acc.setdefault(cell["cell_id"], {"sum": 0.0, "count": 0.0, "hit": 0.0})
        if kind == "nasadem":
            valid = np.isfinite(data) & (data > -1000)
            if nodata is not None:
                valid &= data != nodata
            slot["sum"] += float(data[valid].sum()); slot["count"] += float(valid.sum())
        elif kind == "dswx":
            valid = data < 250
            slot["hit"] += float(np.isin(data, list(DSWX_WATER)).sum()); slot["count"] += float(valid.sum())
        elif kind == "dist":
            valid = data != 255
            slot["hit"] += float(np.isin(data, list(DIST_CONFIRMED)).sum()); slot["count"] += float(valid.sum())
        else:
            raise ValueError(f"unknown layer kind: {kind}")
    rows = []
    for cell in cells:
        slot = acc.get(cell["cell_id"])
        if not slot or slot["count"] == 0:
            continue
        row: dict[str, Any] = {"cell_id": cell["cell_id"], "valid_pixels": int(slot["count"])}
        if kind == "nasadem":
            row["elevation_m"] = slot["sum"] / slot["count"]
        elif kind == "dswx":
            row["water_fraction"] = slot["hit"] / slot["count"]
        else:
            row["disturbed_fraction"] = slot["hit"] / slot["count"]
        rows.append(row)
    return rows


DESCRIPTIONS: dict[str, dict[str, Any]] = {
    "nasadem": {"source": "NASA NASADEM (SRTM-based) elevation, LP DAAC", "value": "mean elevation in metres", "limitations": ["Elevation is ~2000 epoch SRTM-derived; Houston has subsided since.", "Elevation is context for flood exposure, not a flood estimate."]},
    "dswx": {"source": "NASA JPL OPERA DSWx (Dynamic Surface Water Extent), WTR layer", "value": "fraction of valid observations classified as open or partial surface water", "limitations": ["Water ruins radar phase; high fractions flag unreliable radar cells.", "Cloud/snow/layover pixels are excluded, not counted as dry."]},
    "dist": {"source": "NASA JPL OPERA DIST-ALERT, VEG-DIST-STATUS layer", "value": "fraction of valid pixels with confirmed or finished vegetation disturbance", "limitations": ["Construction and land clearing can change radar phase and mimic ground motion.", "Disturbance is not ground motion and is not a cause of subsidence."]},
}


def write_layer(paths: list[str | Path], cells_path: str | Path, kind: str, output: str | Path, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    cells = json.loads(Path(cells_path).read_text(encoding="utf-8"))["cells"]
    rows = sample_layer(paths, cells, kind)
    artifact = {"artifact_type": f"terragauge_{kind}_cells", "kind": kind, **DESCRIPTIONS[kind], "source_files": [Path(p).name for p in paths], **(extra or {}), "cells": rows}
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    Path(output).write_text(json.dumps(artifact, separators=(",", ":")), encoding="utf-8")
    return artifact

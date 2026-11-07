"""Shared spatial helpers for source adapters.

All output records retain source paths and processing parameters. This makes the
analysis reproducible and avoids treating a portal screenshot as data.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from math import floor
from typing import Iterable

import numpy as np


@dataclass(frozen=True)
class SpatialGrid:
    x: np.ndarray
    y: np.ndarray
    crs: str


def require_geospatial_dependencies():
    try:
        from pyproj import Transformer
    except ImportError as error:
        raise RuntimeError("Real raster ingestion requires pyproj. Run: python3 -m pip install -r requirements.txt") from error
    return Transformer


def coordinates_for_grid(grid: SpatialGrid) -> tuple[np.ndarray, np.ndarray]:
    """Transform projected x/y coordinate vectors to 2D longitude/latitude."""
    Transformer = require_geospatial_dependencies()
    transformer = Transformer.from_crs(grid.crs, "EPSG:4326", always_xy=True)
    xx, yy = np.meshgrid(grid.x, grid.y)
    longitude, latitude = transformer.transform(xx, yy)
    return np.asarray(longitude), np.asarray(latitude)


def one_km_cell_id(longitude: float, latitude: float) -> str:
    """Stable 1 km Web-Mercator index used only for joins and map aggregation."""
    Transformer = require_geospatial_dependencies()
    transformer = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
    x, y = transformer.transform(longitude, latitude)
    return f"epsg3857-1km-{floor(x / 1000)}-{floor(y / 1000)}"


def median_or_none(values: np.ndarray) -> float | None:
    finite = values[np.isfinite(values)]
    return None if finite.size == 0 else float(np.median(finite))


def dominant_component(values: Iterable[int]) -> int | None:
    positive = [int(value) for value in values if int(value) > 0]
    return Counter(positive).most_common(1)[0][0] if positive else None

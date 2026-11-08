"""OPERA DISP-S1 inspection and quality-preserving extraction."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np

from .common import SpatialGrid, coordinates_for_grid, median_or_none, one_km_cell_id, require_geospatial_dependencies
from .nisar import _h5py


@dataclass(frozen=True)
class OperaConfig:
    crs: str
    x_path: str = "/x"
    y_path: str = "/y"
    displacement_path: str = "/displacement"
    recommended_mask_path: str = "/recommended_mask"
    cell_pixels: int = 33
    reference_date: str = "unknown_reference"
    secondary_date: str = "unknown_secondary"
    bounding_box: tuple[float, float, float, float] | None = None


def _window(x: np.ndarray, y: np.ndarray, crs: str, bbox: tuple[float, float, float, float] | None) -> tuple[slice, slice]:
    if bbox is None:
        return slice(0, len(y)), slice(0, len(x))
    Transformer = require_geospatial_dependencies()
    west, south, east, north = bbox
    transformer = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
    corners = [transformer.transform(lon, lat) for lon in (west, east) for lat in (south, north)]
    projected_x, projected_y = zip(*corners)
    columns = np.flatnonzero((x >= min(projected_x)) & (x <= max(projected_x)))
    rows = np.flatnonzero((y >= min(projected_y)) & (y <= max(projected_y)))
    if not len(columns) or not len(rows):
        raise ValueError("bounding box does not overlap the OPERA raster")
    return slice(int(rows.min()), int(rows.max()) + 1), slice(int(columns.min()), int(columns.max()) + 1)


def extract_disp_cells(path: str | Path, config: OperaConfig) -> dict[str, Any]:
    """Emit quality-masked OPERA displacement context, never a portal screenshot."""
    h5py = _h5py()
    with h5py.File(path, "r") as file:
        x = np.asarray(file[config.x_path], dtype=float)
        y = np.asarray(file[config.y_path], dtype=float)
        row_window, column_window = _window(x, y, config.crs, config.bounding_box)
        displacement = np.asarray(file[config.displacement_path][row_window, column_window], dtype=float)
        recommended_mask = np.asarray(file[config.recommended_mask_path][row_window, column_window])
        x, y = x[column_window], y[row_window]
    if displacement.shape != recommended_mask.shape or displacement.shape != (len(y), len(x)):
        raise ValueError("OPERA arrays and x/y vectors must describe the same grid")
    longitude, latitude = coordinates_for_grid(SpatialGrid(x=x, y=y, crs=config.crs))
    records: list[dict[str, Any]] = []
    for row in range(0, displacement.shape[0], config.cell_pixels):
        for column in range(0, displacement.shape[1], config.cell_pixels):
            section = np.s_[row : row + config.cell_pixels, column : column + config.cell_pixels]
            valid = (recommended_mask[section] == 1) & np.isfinite(displacement[section])
            lon = median_or_none(longitude[section])
            lat = median_or_none(latitude[section])
            if lon is None or lat is None:
                continue
            records.append({
                "cell_id": one_km_cell_id(lon, lat),
                "longitude": lon,
                "latitude": lat,
                "opera_pair_displacement_mm": median_or_none(np.where(valid, displacement[section] * 1000.0, np.nan)),
                "opera_valid_fraction": float(np.count_nonzero(valid) / valid.size),
                "source_status": "source_derived",
            })
    return {
        "artifact_type": "opera_disp_pair_cells",
        "source_file": str(path),
        "parameters": asdict(config),
        "limitations": [
            "Displacement is LOS displacement from one OPERA product, not an annual trend.",
            "Only pixels with recommended_mask == 1 are included.",
            "Short-wavelength displacement must not replace the unfiltered product without a stated reason.",
        ],
        "cells": records,
    }


def write_disp_cells(input_path: str | Path, output_path: str | Path, config: OperaConfig) -> None:
    Path(output_path).write_text(json.dumps(extract_disp_cells(input_path, config), indent=2), encoding="utf-8")

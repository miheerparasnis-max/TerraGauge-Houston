"""NISAR L2 GUNW extraction.

The adapter extracts pair displacement and quality statistics. It deliberately
does not convert a single interferogram into a yearly subsidence rate. A later
temporal-network inversion is required before a rate is supplied to TerraGauge.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np

from .common import SpatialGrid, coordinates_for_grid, dominant_component, median_or_none, one_km_cell_id


DEFAULT_ROOT = "/science/LSAR/GUNW/grids/frequencyA/unwrappedInterferogram/HH"


def _h5py():
    try:
        import h5py
    except ImportError as error:
        raise RuntimeError("NISAR ingestion requires h5py. Run: python3 -m pip install -r requirements.txt") from error
    return h5py


def inspect_hdf5(path: str | Path) -> list[dict[str, Any]]:
    """List HDF5 datasets without guessing a product layout."""
    h5py = _h5py()
    items: list[dict[str, Any]] = []
    with h5py.File(path, "r") as file:
        def visitor(name: str, node: Any) -> None:
            if isinstance(node, h5py.Dataset):
                items.append({"path": f"/{name}", "shape": list(node.shape), "dtype": str(node.dtype), "units": _decode(node.attrs.get("units"))})
        file.visititems(visitor)
    return items


def _decode(value: Any) -> Any:
    return value.decode() if isinstance(value, bytes) else value


@dataclass(frozen=True)
class GunwConfig:
    wavelength_m: float
    crs: str
    x_path: str
    y_path: str
    phase_path: str = f"{DEFAULT_ROOT}/unwrappedPhase"
    coherence_path: str = f"{DEFAULT_ROOT}/coherenceMagnitude"
    connected_components_path: str = f"{DEFAULT_ROOT}/connectedComponents"
    cell_pixels: int = 13
    acquisition_dates: tuple[str, str] = ("unknown_reference", "unknown_secondary")
    bounding_box: tuple[float, float, float, float] | None = None


def extract_pair_cells(path: str | Path, config: GunwConfig) -> dict[str, Any]:
    """Aggregate one GUNW pair into auditable ~1 km cell records.

    `cell_pixels` must be chosen from the product's 80 m posting and documented
    in the output ledger. The default 13 pixels is approximately 1.04 km.
    """
    if config.wavelength_m <= 0 or config.cell_pixels < 1:
        raise ValueError("wavelength_m and cell_pixels must be positive")
    h5py = _h5py()
    with h5py.File(path, "r") as file:
        phase = np.asarray(file[config.phase_path], dtype=float)
        coherence = np.asarray(file[config.coherence_path], dtype=float)
        components = np.asarray(file[config.connected_components_path])
        x = np.asarray(file[config.x_path], dtype=float)
        y = np.asarray(file[config.y_path], dtype=float)
    if phase.shape != coherence.shape or phase.shape != components.shape:
        raise ValueError("phase, coherence, and connected-components grids must have identical shape")
    if phase.shape != (len(y), len(x)):
        raise ValueError("x/y vectors do not match raster shape")
    longitude, latitude = coordinates_for_grid(SpatialGrid(x=x, y=y, crs=config.crs))
    displacement_mm = phase * (config.wavelength_m / (4.0 * np.pi)) * 1000.0
    records: list[dict[str, Any]] = []
    for row in range(0, phase.shape[0], config.cell_pixels):
        for column in range(0, phase.shape[1], config.cell_pixels):
            section = np.s_[row : row + config.cell_pixels, column : column + config.cell_pixels]
            section_phase = displacement_mm[section]
            section_coherence = coherence[section]
            section_components = components[section]
            valid = np.isfinite(section_phase) & np.isfinite(section_coherence) & (section_components > 0)
            lon = median_or_none(longitude[section])
            lat = median_or_none(latitude[section])
            if lon is None or lat is None:
                continue
            if config.bounding_box is not None:
                west, south, east, north = config.bounding_box
                if not (west <= lon <= east and south <= lat <= north):
                    continue
            records.append({
                "cell_id": one_km_cell_id(lon, lat),
                "longitude": lon,
                "latitude": lat,
                "pair_los_displacement_mm": median_or_none(np.where(valid, section_phase, np.nan)),
                "coherence_median": median_or_none(np.where(valid, section_coherence, np.nan)),
                "valid_fraction": float(np.count_nonzero(valid) / valid.size),
                "dominant_connected_component": dominant_component(section_components[valid].ravel()),
                "in_main_connected_component": bool(np.any(valid)),
                "source_status": "source_derived",
            })
    return {
        "artifact_type": "nisar_gunw_pair_cells",
        "source_file": str(path),
        "source_paths": {
            "phase": config.phase_path,
            "coherence": config.coherence_path,
            "connected_components": config.connected_components_path,
            "x": config.x_path,
            "y": config.y_path,
        },
        "parameters": asdict(config),
        "limitations": [
            "Each record is a pairwise LOS displacement, not an annual rate.",
            "External phase corrections in GUNW are not silently applied by this adapter.",
            "Temporal inversion and covariance treatment are required before an empirical rate/detectability claim.",
        ],
        "cells": records,
    }


def write_pair_cells(input_path: str | Path, output_path: str | Path, config: GunwConfig) -> None:
    Path(output_path).write_text(json.dumps(extract_pair_cells(input_path, config), indent=2), encoding="utf-8")

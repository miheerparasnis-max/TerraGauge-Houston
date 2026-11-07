"""Application service consumed by HTTP, CLI, and future jobs."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from .decision import classify_cell
from .detection import gnss_session_noise_floor
from .model import Thresholds
from .repository import cell_from_dict, load_cells


class TerraGaugeService:
    def __init__(self, dataset_path: str | Path, thresholds: Thresholds | None = None):
        self.dataset_path = Path(dataset_path)
        self.thresholds = thresholds or Thresholds()

    def cells(self, empirical_temporal_network: bool = False) -> list[dict[str, Any]]:
        return [
            classify_cell(cell, self.thresholds, empirical_temporal_network).to_dict()
            for cell in load_cells(self.dataset_path)
        ]

    def cell(self, cell_id: str, empirical_temporal_network: bool = False) -> dict[str, Any] | None:
        for result in self.cells(empirical_temporal_network):
            if result["cell"]["cell_id"] == cell_id:
                return result
        return None

    def summary(self, empirical_temporal_network: bool = False) -> dict[str, Any]:
        results = self.cells(empirical_temporal_network)
        counts: dict[str, int] = {}
        for result in results:
            counts[result["label"]] = counts.get(result["label"], 0) + 1
        return {
            "cells": len(results),
            "labels": counts,
            "thresholds": asdict(self.thresholds),
            "temporal_network_status": "empirical_lower_bounds" if empirical_temporal_network else "scenario_lower_bounds",
            "disclaimer": "TerraGauge provides monitoring-priority evidence, not a flood forecast or a diagnosis of subsidence cause.",
        }

    def analyze_cell(self, payload: dict[str, Any], empirical_temporal_network: bool = False) -> dict[str, Any]:
        cell = cell_from_dict(payload)
        return classify_cell(cell, self.thresholds, empirical_temporal_network).to_dict()

    def node_noise_floor(self, payload: dict[str, Any]) -> dict[str, Any]:
        heights = payload.get("session_heights_mm")
        hours = payload.get("session_hours", 2.0)
        if not isinstance(heights, list) or any(isinstance(item, bool) or not isinstance(item, (int, float)) for item in heights):
            raise ValueError("session_heights_mm must be a numeric array")
        if isinstance(hours, bool) or not isinstance(hours, (int, float)):
            raise ValueError("session_hours must be a number")
        result = gnss_session_noise_floor([float(value) for value in heights], float(hours))
        result["disclaimer"] = "Stationary receiver repeatability only. This result does not measure subsidence."
        return result

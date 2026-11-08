"""Application service consumed by HTTP, CLI, and future jobs."""

from __future__ import annotations

from dataclasses import asdict
import json
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

    def cells(self) -> list[dict[str, Any]]:
        return [classify_cell(cell, self.thresholds).to_dict() for cell in load_cells(self.dataset_path)]

    def cell(self, cell_id: str) -> dict[str, Any] | None:
        for result in self.cells():
            if result["cell"]["cell_id"] == cell_id:
                return result
        return None

    def summary(self) -> dict[str, Any]:
        results = self.cells()
        counts: dict[str, int] = {}
        for result in results:
            counts[result["label"]] = counts.get(result["label"], 0) + 1
        return {
            "cells": len(results),
            "labels": counts,
            "thresholds": asdict(self.thresholds),
            "disclaimer": "TerraGauge provides pairwise radar-signal triage, not a flood forecast, annual rate, or diagnosis of subsidence cause.",
        }

    def analyze_cell(self, payload: dict[str, Any]) -> dict[str, Any]:
        cell = cell_from_dict(payload)
        return classify_cell(cell, self.thresholds).to_dict()

    def data_ledger(self) -> dict[str, Any]:
        data_root = next((path for path in (self.dataset_path.parent, *self.dataset_path.parents) if path.name == "data"), None)
        manifests = data_root / "manifests" if data_root else self.dataset_path.parent / "manifests"
        entries = []
        if manifests.is_dir():
            for path in sorted(manifests.iterdir()):
                if path.suffix == ".json":
                    entries.append({"manifest": path.name, "record": json.loads(path.read_text(encoding="utf-8"))})
                elif path.suffix == ".sha256":
                    entries.append({"manifest": path.name, "sha256": path.read_text(encoding="utf-8").strip()})
        return {"dataset": str(self.dataset_path), "entries": entries, "disclaimer": "Source records document provenance; they do not upgrade a pairwise observation into an annual rate."}

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

    def review_packet(self, cell_id: str) -> dict[str, Any] | None:
        """Return the human checks required before a map label becomes a claim."""
        result = self.cell(cell_id)
        if result is None:
            return None
        label = result["label"]
        needs_review = label in {"investigate_satellite_signal", "add_ground_monitoring", "review_time_matched_mismatch"}
        return {
            "cell_id": cell_id,
            "classification": result,
            "review_required": needs_review,
            "checklist": [
                "Inspect the original interferogram, coherence, and connected-component raster at this location.",
                "Confirm the GUNW processing/provenance record and do not apply atmospheric corrections a second time.",
                "Check time-matched GNSS and groundwater/compaction context; neither alone establishes causation.",
                "Check construction, standing-water, and land-cover context before describing a radar signal as ground motion.",
                "Report this as a monitoring priority unless a reviewed multi-date, redundantly connected inversion supports a rate.",
            ] if needs_review else [
                "No escalation is implied by this label. Keep the provenance and limitation visible in the interface."
            ],
            "monitoring_definition": "The 2 km coverage test uses permanent GNSS stations. Extensometers are mechanism evidence, not a replacement for a surface-motion station.",
        }

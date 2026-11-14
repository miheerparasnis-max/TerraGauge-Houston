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
        self._loaded_mtime_ns: int | None = None
        self._loaded_cells = []

    def _cells(self):
        """Reload only when the dataset changes, while keeping every request current."""
        mtime_ns = self.dataset_path.stat().st_mtime_ns
        if self._loaded_mtime_ns != mtime_ns:
            self._loaded_cells = load_cells(self.dataset_path)
            self._loaded_mtime_ns = mtime_ns
        return self._loaded_cells

    def cells(self) -> list[dict[str, Any]]:
        return [classify_cell(cell, self.thresholds).to_dict() for cell in self._cells()]

    def cell(self, cell_id: str) -> dict[str, Any] | None:
        cell = next((item for item in self._cells() if item.cell_id == cell_id), None)
        return classify_cell(cell, self.thresholds).to_dict() if cell is not None else None

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
        data_root = self._data_root()
        manifests = data_root / "manifests" if data_root else self.dataset_path.parent / "manifests"
        entries = []
        if manifests.is_dir():
            for path in sorted(manifests.iterdir()):
                if path.suffix == ".json":
                    entries.append({"manifest": path.name, "record": json.loads(path.read_text(encoding="utf-8"))})
                elif path.suffix == ".sha256":
                    entries.append({"manifest": path.name, "sha256": path.read_text(encoding="utf-8").strip()})
        return {"dataset": self.dataset_path.name, "entries": entries, "disclaimer": "Source records document provenance; they do not upgrade a pairwise observation into an annual rate."}

    def opera_temporal_status(self) -> dict[str, Any]:
        """Return the checked historical OPERA rate status for direct UI display.

        This is deliberately a status record rather than a map endpoint: when
        the network is insufficient, the frontend must show why no rate exists.
        """
        data_root = self._data_root()
        path = (data_root / "derived" / "opera_houston_temporal_rate_20160712_20210505.json") if data_root else None
        if path is None or not path.is_file():
            return {
                "available": False,
                "rate_status": "not_loaded",
                "message": "No checked OPERA temporal-status artifact is available in this deployment.",
            }
        record = json.loads(path.read_text(encoding="utf-8"))
        stack = record.get("local_stack", {})
        return {
            "available": True,
            "source_artifact": path.name,
            "rate_status": record.get("rate_status"),
            "span_days": record.get("span_days"),
            "date_count": stack.get("date_count"),
            "product_count": stack.get("product_count"),
            "next_requirement": record.get("next_requirement"),
            "display_message": "Historical LOS rate withheld: the locally processed OPERA subset has not been re-referenced as a full time series to an independently reviewed stable spatial patch.",
            "disclaimer": "This is an evidence-status record, not a subsidence-rate map. OPERA displacement is line of sight, not automatically vertical motion.",
        }

    def _data_root(self) -> Path | None:
        return next((path for path in (self.dataset_path.parent, *self.dataset_path.parents) if path.name == "data"), None)

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

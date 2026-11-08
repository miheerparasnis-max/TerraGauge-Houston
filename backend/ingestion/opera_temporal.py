"""Conservative status assessment for a local OPERA DISP-S1 subset.

DISP-S1 granules are already products of a time-series processing workflow.
They must not be treated as raw NISAR GUNW interferogram edges and subjected to
a synthetic loop-closure requirement. A rate needs a re-referenced full stack
and a reviewed stable spatial reference, neither of which this lightweight
adapter silently invents.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

def _as_generic(artifact: dict[str, Any]) -> dict[str, Any]:
    if artifact.get("artifact_type") != "opera_disp_pair_cells":
        raise ValueError("every input must be an opera_disp_pair_cells artifact")
    params = artifact.get("parameters", {})
    reference, secondary = params.get("reference_date"), params.get("secondary_date")
    if not isinstance(reference, str) or not isinstance(secondary, str) or "unknown" in reference or "unknown" in secondary:
        raise ValueError("OPERA artifact needs verified reference_date and secondary_date")
    return {"parameters": {"acquisition_dates": [reference, secondary]}, "cells": [{
        "cell_id": row["cell_id"], "longitude": row["longitude"], "latitude": row["latitude"],
        "pair_los_displacement_mm": row.get("opera_pair_displacement_mm"),
        "coherence_median": row.get("opera_valid_fraction"), "valid_fraction": row.get("opera_valid_fraction"),
        "in_main_connected_component": (row.get("opera_valid_fraction") or 0) > 0,
    } for row in artifact.get("cells", [])]}


def invert_opera_network(pair_artifacts: list[dict[str, Any]], reference_cell_id: str) -> dict[str, Any]:
    generic = [_as_generic(artifact) for artifact in pair_artifacts]
    dates = sorted({value for item in generic for value in item["parameters"]["acquisition_dates"]})
    span_days = (date.fromisoformat(dates[-1]) - date.fromisoformat(dates[0])).days
    local_stack = {
        "date_count": len(dates),
        "product_count": len(pair_artifacts),
        "acquisition_dates": dates,
        "product_interpretation": "DISP-S1 products are processed displacement time slices, not raw interferogram edges.",
    }
    if len(dates) < 20 or span_days < 730:
        return {
            "artifact_type": "opera_temporal_rate_withheld",
            "local_stack": local_stack,
            "span_days": span_days,
            "rate_status": "withheld_insufficient_long_term_stack",
            "next_requirement": "Provide a longer OPERA DISP-S1 time series, re-reference it to a reviewed stable spatial patch, and validate the fitted LOS rate against co-temporal GNSS.",
        }
    return {
        "artifact_type": "opera_temporal_rate_withheld",
        "local_stack": local_stack,
        "span_days": span_days,
        "reference_cell_id": reference_cell_id,
        "rate_status": "withheld_reformat_and_reference_review_required",
        "next_requirement": "Use the complete OPERA frame-level time series with a documented stable spatial reference (for example via opera-utils DISP-S1 reformat), then fit and validate a LOS rate against co-temporal GNSS.",
        "limitations": [
            "The local files are a sparse subset of an already processed OPERA displacement time series; they are not raw independent interferograms.",
            "A rate must be calculated only after re-referencing the full time series to a scientifically reviewed stable spatial patch.",
            "A fitted OPERA rate is line-of-sight motion, not automatically vertical subsidence.",
        ],
    }


def invert_opera_files(input_paths: list[str], output_path: str, reference_cell_id: str) -> None:
    artifacts = [json.loads(Path(path).read_text(encoding="utf-8")) for path in input_paths]
    Path(output_path).write_text(json.dumps(invert_opera_network(artifacts, reference_cell_id), indent=2), encoding="utf-8")

"""Explainable pairwise-NISAR monitoring-priority rules."""

from __future__ import annotations

from .model import CellInput, CellResult, Label, Thresholds


def classify_cell(cell: CellInput, thresholds: Thresholds) -> CellResult:
    """Classify a single GUNW-pair cell without inventing a yearly rate."""
    quality_reasons = []
    if cell.pair_los_displacement_mm is None:
        quality_reasons.append("No aggregated NISAR pairwise LOS displacement is available.")
    if not cell.in_main_connected_component:
        quality_reasons.append("Cell is outside the accepted connected component.")
    if cell.coherence_median is None or cell.coherence_median < thresholds.coherence_min:
        quality_reasons.append(f"Median coherence is below {thresholds.coherence_min:.2f}.")
    if cell.valid_fraction is None or cell.valid_fraction < thresholds.valid_fraction_min:
        quality_reasons.append(f"Valid-pixel fraction is below {thresholds.valid_fraction_min:.0%}.")
    if quality_reasons:
        return CellResult(cell, Label.INSUFFICIENT_DATA, quality_reasons, None)

    if cell.reference_scatter_mm is None or cell.reference_scatter_mm <= 0:
        return CellResult(cell, Label.CONTEXT_ONLY, ["Radar quality passes, but no documented stable-reference scatter is available for a candidate-signal threshold."], None)

    threshold = thresholds.pair_signal_sigma_multiplier * cell.reference_scatter_mm
    candidate = abs(cell.pair_los_displacement_mm or 0.0) >= threshold
    nearby_gps = cell.evidence.gps_distance_km is not None and cell.evidence.gps_distance_km <= thresholds.gps_nearby_km
    matched_disagreement = (
        cell.evidence.gps_comparison_time_matched
        and cell.evidence.gps_residual_mm is not None
        and cell.evidence.gps_uncertainty_mm is not None
        and abs(cell.evidence.gps_residual_mm) > thresholds.detection_sigma * cell.evidence.gps_uncertainty_mm
    )

    if matched_disagreement:
        return CellResult(cell, Label.REVIEW_MISMATCH, ["Time-matched GPS and radar differ beyond the published comparison tolerance."], threshold)
    if candidate and cell.flood_exposed is True and not nearby_gps:
        return CellResult(cell, Label.ADD_MONITORING, ["Quality-controlled NISAR pair signal and flood context pass; no permanent GPS station is within the monitoring radius."], threshold)
    if candidate and cell.flood_exposed is True:
        return CellResult(cell, Label.INVESTIGATE_SIGNAL, ["Quality-controlled NISAR pair signal exceeds the reference-scatter threshold and flood context is present."], threshold)

    reasons = ["Radar quality passes, but this cell does not meet the full investigation rule."]
    if not candidate:
        reasons.append("Pairwise LOS displacement is below the published reference-scatter threshold.")
    if cell.flood_exposed is None:
        reasons.append("Cell-level flood context is not available; no flood-based priority label is assigned.")
    elif not cell.flood_exposed:
        reasons.append("No flood-context intersection is recorded for this cell.")
    return CellResult(cell, Label.CONTEXT_ONLY, reasons, threshold)

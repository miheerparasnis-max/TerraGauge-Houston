"""Explainable monitoring-priority rules."""

from __future__ import annotations

from .detection import detectability
from .model import CellInput, CellResult, Label, Thresholds


def classify_cell(cell: CellInput, thresholds: Thresholds, empirical_temporal_network: bool) -> CellResult:
    quality_reasons = []
    if cell.los_rate_mm_year is None:
        quality_reasons.append("No aggregated NISAR line-of-sight rate is available.")
    if not cell.in_main_connected_component:
        quality_reasons.append("Pixel is outside the main connected component.")
    if cell.coherence_median is None or cell.coherence_median < thresholds.coherence_min:
        quality_reasons.append(f"Median coherence is below {thresholds.coherence_min:.2f}.")
    if cell.valid_fraction is None or cell.valid_fraction < thresholds.valid_fraction_min:
        quality_reasons.append(f"Valid-pixel fraction is below {thresholds.valid_fraction_min:.0%}.")

    detection = detectability(
        rate_mm_year=cell.los_rate_mm_year,
        epoch_sigma_mm=cell.epoch_sigma_mm,
        interval_days=cell.interval_days,
        observation_count=cell.observation_count,
        thresholds=thresholds,
        empirical_temporal_network=empirical_temporal_network,
    )
    if quality_reasons:
        return CellResult(cell, Label.INSUFFICIENT_DATA, quality_reasons, detection)

    motion = abs(cell.los_rate_mm_year or 0) >= thresholds.motion_rate_min_mm_year
    nearby_gps = (
        cell.evidence.gps_distance_km is not None
        and cell.evidence.gps_distance_km <= thresholds.gps_nearby_km
    )
    agreement_limit = (cell.evidence.gps_uncertainty_mm_year or 0) * thresholds.detection_sigma
    agrees = (
        nearby_gps
        and cell.evidence.gps_residual_mm_year is not None
        and abs(cell.evidence.gps_residual_mm_year) <= agreement_limit
    )
    disagrees = (
        nearby_gps
        and cell.evidence.gps_residual_mm_year is not None
        and cell.evidence.gps_uncertainty_mm_year is not None
        and abs(cell.evidence.gps_residual_mm_year) > agreement_limit
    )

    if disagrees:
        return CellResult(
            cell,
            Label.REVIEW_DISAGREEMENT,
            ["Nearby GPS and radar differ beyond the stated two-sigma comparison tolerance."],
            detection,
        )
    if motion and cell.flood_exposed and agrees:
        return CellResult(
            cell,
            Label.INVESTIGATE_FIRST,
            ["Motion threshold, flood exposure, and nearby GPS agreement all pass."],
            detection,
        )
    if motion and cell.flood_exposed and not nearby_gps:
        return CellResult(
            cell,
            Label.ADD_MONITORING,
            ["Motion threshold and flood exposure pass, but no permanent GPS station is within the monitoring radius."],
            detection,
        )
    reasons = []
    if motion:
        reasons.append("Radar motion threshold passes.")
    if cell.flood_exposed:
        reasons.append("Flood-exposure layer intersects this cell.")
    if not reasons:
        reasons.append("Neither the motion nor flood-exposure rule is met.")
    return CellResult(cell, Label.OBSERVE, reasons, detection)

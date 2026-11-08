"""Typed records shared by TerraGauge's evidence and decision layers."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


class Label(StrEnum):
    INVESTIGATE_SIGNAL = "investigate_satellite_signal"
    ADD_MONITORING = "add_ground_monitoring"
    CONTEXT_ONLY = "context_only"
    REVIEW_MISMATCH = "review_time_matched_mismatch"
    INSUFFICIENT_DATA = "insufficient_radar_evidence"


@dataclass(frozen=True)
class Thresholds:
    """Published design choices; they are not universal physical constants."""

    coherence_min: float = 0.40
    valid_fraction_min: float = 0.50
    pair_signal_sigma_multiplier: float = 2.0
    gps_nearby_km: float = 2.0
    detection_sigma: float = 2.0


@dataclass(frozen=True)
class Evidence:
    nisar_acquisition_dates: list[str] = field(default_factory=list)
    nearest_gps_station: str | None = None
    gps_distance_km: float | None = None
    historic_gps_up_mm_year: float | None = None
    historic_gps_start_year: float | None = None
    historic_gps_end_year: float | None = None
    gps_comparison_time_matched: bool = False
    gps_projected_displacement_mm: float | None = None
    gps_residual_mm: float | None = None
    gps_uncertainty_mm: float | None = None
    usgs_site_id: str | None = None
    usgs_distance_km: float | None = None
    groundwater_depth_change_ft: float | None = None
    nearest_extensometer_station: str | None = None
    extensometer_distance_km: float | None = None
    cumulative_compaction_change_ft: float | None = None
    opera_historic_pair_displacement_mm: float | None = None
    opera_historic_valid_fraction: float | None = None
    flood_source: str | None = None
    flood_zone: str | None = None


@dataclass(frozen=True)
class CellInput:
    """One post-processed approximately 1 km evidence cell.

    `pair_los_displacement_mm` is the safe default for a GUNW pair. The
    optional rate fields are deliberately separate so a single pair cannot
    silently become a yearly motion rate.
    """

    cell_id: str
    longitude: float
    latitude: float
    pair_los_displacement_mm: float | None
    reference_scatter_mm: float | None
    coherence_median: float | None
    valid_fraction: float | None
    in_main_connected_component: bool
    flood_exposed: bool | None
    evidence: Evidence = field(default_factory=Evidence)
    source_status: str = "source_derived"
    temporal_los_rate_mm_year: float | None = None
    temporal_network_adequate: bool = False
    observation_count: int | None = None


@dataclass(frozen=True)
class DetectionResult:
    rate_uncertainty_mm_year: float | None
    minimum_observations: int | None
    minimum_duration_days: float | None
    lower_bound: bool
    status: str
    warnings: list[str]


@dataclass(frozen=True)
class CellResult:
    cell: CellInput
    label: Label
    reasons: list[str]
    pair_signal_threshold_mm: float | None
    detection: DetectionResult | None = None

    def to_dict(self) -> dict[str, Any]:
        return _serialize(asdict(self))


def _serialize(value: Any) -> Any:
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, dict):
        return {key: _serialize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_serialize(item) for item in value]
    return value

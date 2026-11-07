"""Typed records shared by the ingestion, science, and API layers."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


class Label(StrEnum):
    INVESTIGATE_FIRST = "investigate_first"
    ADD_MONITORING = "add_monitoring_here"
    REVIEW_DISAGREEMENT = "review_disagreement"
    OBSERVE = "observe"
    INSUFFICIENT_DATA = "insufficient_data"


@dataclass(frozen=True)
class Thresholds:
    """Published decision choices, not universal physical constants."""

    coherence_min: float = 0.40
    valid_fraction_min: float = 0.50
    motion_rate_min_mm_year: float = 5.0
    gps_nearby_km: float = 2.0
    detection_sigma: float = 2.0


@dataclass(frozen=True)
class Evidence:
    nisar_acquisition_dates: list[str] = field(default_factory=list)
    opera_rate_mm_year: float | None = None
    nearest_gps_station: str | None = None
    gps_distance_km: float | None = None
    gps_projected_rate_mm_year: float | None = None
    gps_residual_mm_year: float | None = None
    gps_uncertainty_mm_year: float | None = None
    usgs_site_id: str | None = None
    flood_source: str | None = None


@dataclass(frozen=True)
class CellInput:
    """One already-aggregated 1 km analysis cell.

    This backend deliberately accepts post-processed science inputs. Raster
    decoding and GUNW-specific variable names stay in a separately auditable
    ingestion adapter rather than being hidden in the decision logic.
    """

    cell_id: str
    longitude: float
    latitude: float
    los_rate_mm_year: float | None
    epoch_sigma_mm: float | None
    interval_days: float | None
    observation_count: int | None
    coherence_median: float | None
    valid_fraction: float | None
    in_main_connected_component: bool
    flood_exposed: bool
    evidence: Evidence = field(default_factory=Evidence)
    source_status: str = "source_derived"


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
    detection: DetectionResult

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

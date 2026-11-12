"""Rate-resolution and GNSS noise-floor calculations.

These functions return lower-bound planning values. They are intentionally not
subsidences forecasts and must never be rendered as such by a client.
"""

from __future__ import annotations

from math import sqrt

from .model import DetectionResult, Thresholds


def rate_uncertainty_mm_year(
    epoch_sigma_mm: float, interval_days: float, observations: int
) -> float:
    """Least-squares slope uncertainty for equally spaced white-noise samples."""
    if epoch_sigma_mm <= 0 or interval_days <= 0 or observations < 3:
        raise ValueError("positive sigma/interval and at least 3 observations are required")
    interval_years = interval_days / 365.25
    return (epoch_sigma_mm / interval_years) * sqrt(
        12.0 / (observations * (observations**2 - 1))
    )


def detectability(
    *,
    rate_mm_year: float | None,
    epoch_sigma_mm: float | None,
    interval_days: float | None,
    observation_count: int | None,
    thresholds: Thresholds,
    empirical_temporal_network: bool,
) -> DetectionResult:
    """Return an explicitly caveated rate-resolution calculation.

    GUNW interferograms have temporal and atmospheric correlation. Even when a
    series passes the caller's temporal-network gate, this remains a lower
    bound until covariance is estimated from the real network.
    """
    missing = [
        name
        for name, value in {
            "rate_mm_year": rate_mm_year,
            "epoch_sigma_mm": epoch_sigma_mm,
            "interval_days": interval_days,
            "observation_count": observation_count,
        }.items()
        if value is None
    ]
    if missing:
        return DetectionResult(None, None, None, True, "not_available", [f"Missing: {', '.join(missing)}."])
    if observation_count < 3 or epoch_sigma_mm <= 0 or interval_days <= 0:
        # Missing values are honest absence (reported above); invalid values are an error (MASTER B8).
        raise ValueError("epoch_sigma_mm and interval_days must be positive and observation_count at least 3")
    if rate_mm_year == 0:
        return DetectionResult(None, None, None, True, "not_detectable", ["A zero assumed rate cannot meet a rate-detection threshold."])

    warnings = [
        "White-noise lower bound only; atmospheric and temporal correlations are not modeled."
    ]
    if not empirical_temporal_network:
        warnings.append(
            "Scenario only: the supplied observations are not a sufficient connected temporal network for an empirical NISAR trend."
        )

    current_uncertainty = rate_uncertainty_mm_year(epoch_sigma_mm, interval_days, observation_count)
    target = abs(rate_mm_year) / thresholds.detection_sigma
    minimum_observations = None
    for count in range(3, 100_001):
        if rate_uncertainty_mm_year(epoch_sigma_mm, interval_days, count) <= target:
            minimum_observations = count
            break
    if minimum_observations is None:
        return DetectionResult(current_uncertainty, None, None, True, "not_resolved_in_search", warnings)

    return DetectionResult(
        rate_uncertainty_mm_year=current_uncertainty,
        minimum_observations=minimum_observations,
        minimum_duration_days=(minimum_observations - 1) * interval_days,
        lower_bound=True,
        status="empirical_lower_bound" if empirical_temporal_network else "scenario_lower_bound",
        warnings=warnings,
    )


def gnss_session_noise_floor(session_heights_mm: list[float], session_hours: float = 2.0) -> dict[str, float | int | str]:
    """Calculate a stationary receiver's session scatter and white-noise daily lower bound."""
    if len(session_heights_mm) < 3:
        raise ValueError("at least three static GNSS sessions are required")
    if session_hours <= 0 or 24 % session_hours != 0:
        raise ValueError("session_hours must divide 24")
    mean = sum(session_heights_mm) / len(session_heights_mm)
    variance = sum((value - mean) ** 2 for value in session_heights_mm) / (len(session_heights_mm) - 1)
    sigma_session = sqrt(variance)
    sessions_per_day = 24.0 / session_hours
    return {
        "sessions": len(session_heights_mm),
        "mean_height_mm": mean,
        "sigma_session_mm": sigma_session,
        "sigma_daily_mm_lower_bound": sigma_session / sqrt(sessions_per_day),
        "status": "lower_bound_white_noise_assumption",
    }

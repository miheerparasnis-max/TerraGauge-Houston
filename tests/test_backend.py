import unittest

from backend.decision import classify_cell
from backend.detection import detectability, gnss_session_noise_floor, rate_uncertainty_mm_year
from backend.model import CellInput, Evidence, Label, Thresholds
from backend.repository import ValidationError, cell_from_dict


def cell(**overrides):
    values = {
        "cell_id": "test-cell",
        "longitude": -95.3,
        "latitude": 29.7,
        "pair_los_displacement_mm": -12.0,
        "reference_scatter_mm": 4.0,
        "coherence_median": 0.6,
        "valid_fraction": 0.8,
        "in_main_connected_component": True,
        "flood_exposed": True,
        "evidence": Evidence(gps_distance_km=1.0),
    }
    values.update(overrides)
    return CellInput(**values)


class DetectionTests(unittest.TestCase):
    def test_rate_uncertainty_shrinks_with_more_observations(self):
        self.assertGreater(rate_uncertainty_mm_year(4, 12, 4), rate_uncertainty_mm_year(4, 12, 8))

    def test_scenario_is_explicitly_caveated(self):
        result = detectability(rate_mm_year=-7, epoch_sigma_mm=4, interval_days=12, observation_count=6, thresholds=Thresholds(), empirical_temporal_network=False)
        self.assertEqual(result.status, "scenario_lower_bound")
        self.assertTrue(result.lower_bound)

    def test_gnss_noise_floor_requires_three_sessions(self):
        with self.assertRaises(ValueError):
            gnss_session_noise_floor([1.0, 2.0])

    def test_gnss_noise_floor_is_calculated(self):
        result = gnss_session_noise_floor([10.0, 12.0, 8.0])
        self.assertEqual(result["sessions"], 3)
        self.assertGreater(result["sigma_session_mm"], 0)


class DecisionTests(unittest.TestCase):
    def test_candidate_with_flood_context_is_investigate_signal(self):
        self.assertEqual(classify_cell(cell(), Thresholds()).label, Label.INVESTIGATE_SIGNAL)

    def test_candidate_without_flood_context_is_still_investigated(self):
        self.assertEqual(classify_cell(cell(flood_exposed=False), Thresholds()).label, Label.INVESTIGATE_SIGNAL)

    def test_candidate_without_nearby_gps_is_add_monitoring(self):
        value = cell(evidence=Evidence(gps_distance_km=3.0))
        self.assertEqual(classify_cell(value, Thresholds()).label, Label.ADD_MONITORING)

    def test_mismatch_requires_time_matched_measurements(self):
        value = cell(evidence=Evidence(gps_distance_km=1.0, gps_comparison_time_matched=True, gps_residual_mm=3.0, gps_uncertainty_mm=1.0))
        self.assertEqual(classify_cell(value, Thresholds()).label, Label.REVIEW_MISMATCH)

    def test_missing_flood_context_does_not_hide_candidate(self):
        self.assertEqual(classify_cell(cell(flood_exposed=None), Thresholds()).label, Label.INVESTIGATE_SIGNAL)

    def test_low_quality_is_insufficient_data(self):
        self.assertEqual(classify_cell(cell(coherence_median=0.2), Thresholds()).label, Label.INSUFFICIENT_DATA)


class InputValidationTests(unittest.TestCase):
    def test_rejects_rate_without_valid_network(self):
        payload = cell().__dict__.copy()
        payload["evidence"] = payload["evidence"].__dict__
        payload.update({"temporal_los_rate_mm_year": -5.0, "temporal_network_adequate": False, "observation_count": 6})
        with self.assertRaises(ValidationError):
            cell_from_dict(payload)

    def test_rejects_non_finite_coordinates(self):
        payload = cell().__dict__.copy()
        payload["evidence"] = payload["evidence"].__dict__
        payload["longitude"] = float("nan")
        with self.assertRaises(ValidationError):
            cell_from_dict(payload)


if __name__ == "__main__":
    unittest.main()

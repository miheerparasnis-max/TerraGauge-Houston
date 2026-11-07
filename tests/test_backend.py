import unittest

from backend.decision import classify_cell
from backend.detection import detectability, gnss_session_noise_floor, rate_uncertainty_mm_year
from backend.model import CellInput, Evidence, Label, Thresholds


def cell(**overrides):
    values = {
        "cell_id": "test-cell",
        "longitude": -95.3,
        "latitude": 29.7,
        "los_rate_mm_year": -7.0,
        "epoch_sigma_mm": 4.0,
        "interval_days": 12.0,
        "observation_count": 6,
        "coherence_median": 0.6,
        "valid_fraction": 0.8,
        "in_main_connected_component": True,
        "flood_exposed": True,
        "evidence": Evidence(gps_distance_km=1.0, gps_residual_mm_year=1.0, gps_uncertainty_mm_year=1.0),
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
        self.assertIsNotNone(result.minimum_observations)

    def test_gnss_noise_floor_requires_three_sessions(self):
        with self.assertRaises(ValueError):
            gnss_session_noise_floor([1.0, 2.0])

    def test_gnss_noise_floor_is_calculated(self):
        result = gnss_session_noise_floor([10.0, 12.0, 8.0])
        self.assertEqual(result["sessions"], 3)
        self.assertGreater(result["sigma_session_mm"], 0)


class DecisionTests(unittest.TestCase):
    def test_agreeing_cell_is_investigate_first(self):
        self.assertEqual(classify_cell(cell(), Thresholds(), True).label, Label.INVESTIGATE_FIRST)

    def test_no_nearby_gps_is_add_monitoring(self):
        value = cell(evidence=Evidence(gps_distance_km=3.0))
        self.assertEqual(classify_cell(value, Thresholds(), True).label, Label.ADD_MONITORING)

    def test_disagreement_is_review(self):
        value = cell(evidence=Evidence(gps_distance_km=1.0, gps_residual_mm_year=3.0, gps_uncertainty_mm_year=1.0))
        self.assertEqual(classify_cell(value, Thresholds(), True).label, Label.REVIEW_DISAGREEMENT)

    def test_low_quality_is_insufficient_data(self):
        value = cell(coherence_median=0.2)
        self.assertEqual(classify_cell(value, Thresholds(), True).label, Label.INSUFFICIENT_DATA)


if __name__ == "__main__":
    unittest.main()

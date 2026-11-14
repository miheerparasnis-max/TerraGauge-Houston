import unittest
import json
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from backend.api import TerraGaugeHandler
from backend.decision import classify_cell
from backend.detection import detectability, gnss_session_noise_floor, rate_uncertainty_mm_year
from backend.model import CellInput, Evidence, Label, Thresholds
from backend.repository import ValidationError, cell_from_dict
from backend.service import TerraGaugeService


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

    def test_rejects_out_of_range_quality_fraction(self):
        payload = cell().__dict__.copy()
        payload["evidence"] = payload["evidence"].__dict__
        payload["coherence_median"] = 1.1
        with self.assertRaisesRegex(ValidationError, "between 0 and 1"):
            cell_from_dict(payload)

    def test_rejects_negative_monitoring_distance(self):
        payload = cell().__dict__.copy()
        payload["evidence"] = {**payload["evidence"].__dict__, "gps_distance_km": -0.1}
        with self.assertRaisesRegex(ValidationError, "non-negative"):
            cell_from_dict(payload)

    def test_rejects_nonchronological_observation_dates(self):
        payload = cell().__dict__.copy()
        payload["evidence"] = {**payload["evidence"].__dict__, "nisar_acquisition_dates": ["2026-01-13", "2026-01-01"]}
        with self.assertRaisesRegex(ValidationError, "unique and chronological"):
            cell_from_dict(payload)


class OperaTemporalStatusTests(unittest.TestCase):
    def test_exposes_withheld_rate_reason_for_frontend(self):
        dataset = Path(__file__).resolve().parents[1] / "data" / "sample_cells.json"
        status = TerraGaugeService(dataset).opera_temporal_status()
        self.assertTrue(status["available"])
        self.assertEqual(status["rate_status"], "withheld_reformat_and_reference_review_required")
        self.assertEqual(status["date_count"], 20)
        self.assertEqual(status["product_count"], 19)
        self.assertIn("withheld", status["display_message"].lower())


class ApiTests(unittest.TestCase):
    """Exercise the public API surface, not just the service functions."""

    def setUp(self):
        dataset = Path(__file__).resolve().parents[1] / "data" / "sample_cells.json"
        self.previous_service = TerraGaugeHandler.service
        TerraGaugeHandler.service = TerraGaugeService(dataset)
        try:
            self.server = ThreadingHTTPServer(("127.0.0.1", 0), TerraGaugeHandler)
        except PermissionError:
            self.skipTest("local TCP sockets are disabled in this execution environment")
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.thread.join(timeout=2)
        self.server.server_close()
        TerraGaugeHandler.service = self.previous_service

    def test_health_and_temporal_status_are_json(self):
        with urlopen(f"{self.base_url}/health") as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
            self.assertEqual(json.load(response)["status"], "ok")
        with urlopen(f"{self.base_url}/v1/opera-temporal-status") as response:
            self.assertEqual(json.load(response)["rate_status"], "withheld_reformat_and_reference_review_required")

    def test_post_requires_json_content_type(self):
        request = Request(
            f"{self.base_url}/v1/gnss/noise-floor",
            data=b'{"session_heights_mm":[1,2,3]}',
            method="POST",
            headers={"Content-Type": "text/plain"},
        )
        with self.assertRaises(HTTPError) as caught:
            urlopen(request)
        self.assertEqual(caught.exception.code, 400)
        self.assertEqual(json.load(caught.exception)["error"], "invalid_request")


if __name__ == "__main__":
    unittest.main()

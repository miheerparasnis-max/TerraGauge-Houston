import unittest
from pathlib import Path

from backend.model import Label
from backend.service import TerraGaugeService


DATASET = Path(__file__).resolve().parents[1] / "data" / "derived" / "terragauge_houston_evidence_pair_20251102_20251114.json"


class RealHoustonCellTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.service = TerraGaugeService(DATASET)

    def test_northeast_houston_pair_cell_is_context_only_without_reference_region(self):
        result = self.service.cell("epsg3857-1km--10588-3508")
        self.assertIsNotNone(result)
        self.assertEqual(result["label"], Label.CONTEXT_ONLY)
        self.assertEqual(result["cell"]["pair_los_displacement_mm"], 0.0)
        self.assertIsNone(result["pair_signal_threshold_mm"])

    def test_west_houston_pair_cell_does_not_become_an_annual_rate(self):
        result = self.service.cell("epsg3857-1km--10648-3471")
        self.assertIsNotNone(result)
        self.assertEqual(result["label"], Label.CONTEXT_ONLY)
        self.assertAlmostEqual(result["cell"]["pair_los_displacement_mm"], -39.282693968228884)
        self.assertIsNone(result["cell"]["temporal_los_rate_mm_year"])

    def test_southwest_houston_pair_cell_has_real_fema_context_but_no_radar_threshold(self):
        result = self.service.cell("epsg3857-1km--10629-3449")
        self.assertIsNotNone(result)
        self.assertEqual(result["label"], Label.CONTEXT_ONLY)
        self.assertAlmostEqual(result["cell"]["pair_los_displacement_mm"], -38.13685465672304)
        self.assertTrue(result["cell"]["flood_exposed"])
        self.assertEqual(result["cell"]["evidence"]["flood_zone"], "AE")
        self.assertIsNone(result["pair_signal_threshold_mm"])


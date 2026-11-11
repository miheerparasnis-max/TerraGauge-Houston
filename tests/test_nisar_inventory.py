import importlib.util
import unittest
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location("nisar_inventory", Path(__file__).resolve().parents[1] / "scripts" / "nisar_inventory.py")
inventory = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(inventory)


class ChainReportTests(unittest.TestCase):
    def test_bridging_pair_over_missed_acquisition_is_still_a_chain(self):
        pairs = [("2026-02-06", "2026-02-18"), ("2026-02-18", "2026-03-14"), ("2026-03-14", "2026-03-26")]
        report = inventory.chain_report(pairs)
        self.assertTrue(report["is_simple_chain"])
        self.assertEqual(report["redundant_edges"], 0)
        self.assertEqual(report["non_nominal_span_pairs"], [["2026-02-18", "2026-03-14"]])
        self.assertEqual(report["gaps_longer_than_nominal"], [{"from": "2026-02-18", "to": "2026-03-14", "days": 24}])

    def test_cross_pair_skipping_an_available_date_is_redundant(self):
        pairs = [("2025-11-02", "2025-11-14"), ("2025-11-14", "2025-11-26"), ("2025-11-02", "2025-11-26")]
        report = inventory.chain_report(pairs)
        self.assertFalse(report["is_simple_chain"])
        self.assertEqual(report["redundant_edges"], 1)
        self.assertEqual(report["pairs_skipping_an_available_date"], [["2025-11-02", "2025-11-26"]])

    def test_empty_input_fails_loudly(self):
        with self.assertRaises(ValueError):
            inventory.chain_report([])

    def test_bbox_coverage_full_and_none(self):
        box = (0.0, 0.0, 1.0, 1.0)
        self.assertEqual(inventory.bbox_coverage([(-1, -1), (2, -1), (2, 2), (-1, 2)], box), 1.0)
        self.assertEqual(inventory.bbox_coverage([(5, 5), (6, 5), (6, 6), (5, 6)], box), 0.0)


if __name__ == "__main__":
    unittest.main()

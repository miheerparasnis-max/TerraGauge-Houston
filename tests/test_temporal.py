import unittest

from backend.ingestion.temporal import diagnose_gunw_network, invert_gunw_network


def pair(start, end, value):
    return {"parameters": {"acquisition_dates": [start, end]}, "cells": [
        {"cell_id": "reference", "longitude": -95.4, "latitude": 29.7, "pair_los_displacement_mm": 0.0, "coherence_median": 0.8, "valid_fraction": 1.0, "in_main_connected_component": True},
        {"cell_id": "target", "longitude": -95.3, "latitude": 29.8, "pair_los_displacement_mm": value, "coherence_median": 0.7, "valid_fraction": 0.9, "in_main_connected_component": True},
    ]}


class TemporalNetworkTests(unittest.TestCase):
    def test_inverts_connected_redundant_network(self):
        artifacts = [pair("2026-01-01", "2026-01-31", 0.99), pair("2026-01-31", "2026-03-02", 0.99), pair("2026-03-02", "2026-04-01", 0.99), pair("2026-04-01", "2026-05-01", 0.99), pair("2026-01-01", "2026-03-02", 1.98), pair("2026-03-02", "2026-05-01", 1.98)]
        target = next(cell for cell in invert_gunw_network(artifacts, "reference", reference_status="reviewed")["cells"] if cell["cell_id"] == "target")
        self.assertTrue(target["temporal_network_adequate"])
        self.assertAlmostEqual(target["los_rate_mm_year"], 12.05, places=1)

    def test_inversion_requires_reviewed_reference(self):
        artifacts = [pair("2026-01-01", "2026-01-31", 0.99), pair("2026-01-31", "2026-03-02", 0.99), pair("2026-03-02", "2026-04-01", 0.99), pair("2026-04-01", "2026-05-01", 0.99), pair("2026-01-01", "2026-03-02", 1.98), pair("2026-03-02", "2026-05-01", 1.98)]
        with self.assertRaisesRegex(ValueError, "reference_status"):
            invert_gunw_network(artifacts, "reference")

    def test_rejects_too_few_dates(self):
        with self.assertRaises(ValueError):
            invert_gunw_network([pair("2026-01-01", "2026-01-31", 1), pair("2026-01-31", "2026-03-02", 1), pair("2026-03-02", "2026-04-01", 1)], "reference")

    def test_chain_is_explicitly_withheld(self):
        artifacts = [pair("2026-01-01", "2026-01-31", 1), pair("2026-01-31", "2026-03-02", 1), pair("2026-03-02", "2026-04-01", 1), pair("2026-04-01", "2026-05-01", 1)]
        result = diagnose_gunw_network(artifacts)
        self.assertEqual(result["redundant_edges"], 0)
        self.assertEqual(result["rate_status"], "withheld_insufficient_redundancy")

    def test_disconnected_network_is_not_eligible(self):
        artifacts = [
            pair("2026-01-01", "2026-01-31", 1),
            pair("2026-01-31", "2026-03-02", 1),
            pair("2026-06-01", "2026-07-01", 1),
            pair("2026-07-01", "2026-07-31", 1),
            pair("2026-06-01", "2026-07-31", 2),
            pair("2026-01-01", "2026-03-02", 2),
        ]
        result = diagnose_gunw_network(artifacts)
        self.assertEqual(result["connected_component_count"], 2)
        self.assertEqual(result["rate_status"], "withheld_disconnected_network")

    def test_duplicate_pair_cannot_count_as_loop_closure(self):
        artifacts = [
            pair("2026-01-01", "2026-01-31", 1),
            pair("2026-01-31", "2026-03-02", 1),
            pair("2026-03-02", "2026-04-01", 1),
            pair("2026-04-01", "2026-05-01", 1),
            pair("2026-01-01", "2026-03-02", 2),
            pair("2026-01-01", "2026-03-02", 2),
        ]
        result = diagnose_gunw_network(artifacts)
        self.assertEqual(result["duplicate_pair_edge_count"], 1)
        self.assertEqual(result["rate_status"], "withheld_duplicate_pair_edges")

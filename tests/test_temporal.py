import unittest

from backend.ingestion.temporal import invert_gunw_network


def pair(start, end, value):
    return {"parameters": {"acquisition_dates": [start, end]}, "cells": [
        {"cell_id": "reference", "longitude": -95.4, "latitude": 29.7, "pair_los_displacement_mm": 0.0, "coherence_median": 0.8, "valid_fraction": 1.0, "in_main_connected_component": True},
        {"cell_id": "target", "longitude": -95.3, "latitude": 29.8, "pair_los_displacement_mm": value, "coherence_median": 0.7, "valid_fraction": 0.9, "in_main_connected_component": True},
    ]}


class TemporalNetworkTests(unittest.TestCase):
    def test_inverts_connected_redundant_network(self):
        artifacts = [pair("2026-01-01", "2026-01-31", 0.99), pair("2026-01-31", "2026-03-02", 0.99), pair("2026-03-02", "2026-04-01", 0.99), pair("2026-04-01", "2026-05-01", 0.99), pair("2026-01-01", "2026-03-02", 1.98), pair("2026-03-02", "2026-05-01", 1.98)]
        target = next(cell for cell in invert_gunw_network(artifacts, "reference")["cells"] if cell["cell_id"] == "target")
        self.assertTrue(target["temporal_network_adequate"])
        self.assertAlmostEqual(target["los_rate_mm_year"], 12.05, places=1)

    def test_rejects_too_few_dates(self):
        with self.assertRaises(ValueError):
            invert_gunw_network([pair("2026-01-01", "2026-01-31", 1), pair("2026-01-31", "2026-03-02", 1), pair("2026-03-02", "2026-04-01", 1)], "reference")

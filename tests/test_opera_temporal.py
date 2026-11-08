import unittest

from backend.ingestion.opera_temporal import invert_opera_network


def pair(start, end, value=1.0):
    return {"artifact_type": "opera_disp_pair_cells", "parameters": {"reference_date": start, "secondary_date": end}, "cells": [
        {"cell_id": "ref", "longitude": -95.4, "latitude": 29.7, "opera_pair_displacement_mm": 0.0, "opera_valid_fraction": 1.0},
        {"cell_id": "target", "longitude": -95.3, "latitude": 29.8, "opera_pair_displacement_mm": value, "opera_valid_fraction": 1.0},
    ]}


class OperaTemporalTests(unittest.TestCase):
    def test_withholds_short_network(self):
        result = invert_opera_network([pair("2016-01-01", "2016-01-13"), pair("2016-01-01", "2016-01-25")], "ref")
        self.assertEqual(result["rate_status"], "withheld_insufficient_long_term_network")

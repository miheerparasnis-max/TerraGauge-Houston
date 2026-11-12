import json
import tempfile
import unittest
from pathlib import Path

from backend.ingestion.corrections import (
    CORRECTIONS,
    empty_correction_record,
    mark_applied,
    require_same_corrections,
    set_product_state,
    validate_correction_record,
)
from backend.ingestion.provisional import chain_sum, deramp_pair
from backend.ingestion.quality import validate_pair_artifact


def pair(start, end, record=None):
    cells = [{"cell_id": f"c{i}", "longitude": -95.3 + 0.01 * i, "latitude": 29.7 + 0.01 * (i % 2), "pair_los_displacement_mm": float(i),
              "coherence_median": 0.8, "valid_fraction": 0.9, "in_main_connected_component": True} for i in range(4)]
    return {"artifact_type": "nisar_gunw_pair_cells", "parameters": {"acquisition_dates": [start, end], "bounding_box": [-96, 29, -94, 31]},
            "source_processing_corrections": {}, "applied_corrections": record or empty_correction_record(), "cells": cells}


class CorrectionRecordTests(unittest.TestCase):
    def test_new_record_marks_every_correction_unverified(self):
        record = empty_correction_record()
        self.assertEqual(validate_correction_record(record), [])
        for name in CORRECTIONS:
            self.assertIsNone(record[f"{name}_applied"])

    def test_applying_requires_a_verified_not_applied_state(self):
        with self.assertRaises(ValueError):
            mark_applied(empty_correction_record(), "ionosphere", "terragauge:ionospherePhaseScreen")

    def test_apply_once_after_verification(self):
        record = set_product_state(empty_correction_record(), "ionosphere", False, "product:/science/.../ionosphereFlag=False")
        record = mark_applied(record, "ionosphere", "terragauge:/science/.../ionospherePhaseScreen")
        self.assertIs(record["ionosphere_applied"], True)
        self.assertIn("ionospherePhaseScreen", record["ionosphere_source"])
        self.assertEqual(validate_correction_record(record), [])

    def test_double_application_is_rejected(self):
        record = set_product_state(empty_correction_record(), "troposphere", False, "product:flag")
        record = mark_applied(record, "troposphere", "terragauge:lookup")
        with self.assertRaises(ValueError):
            mark_applied(record, "troposphere", "terragauge:lookup")

    def test_correction_already_applied_by_the_product_is_never_reapplied(self):
        record = set_product_state(empty_correction_record(), "tide", True, "product:/science/.../tideApplied=True")
        with self.assertRaises(ValueError):
            mark_applied(record, "tide", "terragauge:tide_lut")

    def test_product_state_cannot_be_overwritten(self):
        record = set_product_state(empty_correction_record(), "tide", False, "product:flag")
        with self.assertRaises(ValueError):
            set_product_state(record, "tide", True, "product:flag")

    def test_unknown_correction_name_is_rejected(self):
        with self.assertRaises(ValueError):
            mark_applied(empty_correction_record(), "merra2", "x")

    def test_invalid_records_are_reported(self):
        self.assertTrue(validate_correction_record(None))
        missing = empty_correction_record()
        del missing["tide_applied"]
        self.assertTrue(validate_correction_record(missing))
        no_source = empty_correction_record()
        no_source["ionosphere_applied"] = True
        self.assertTrue(validate_correction_record(no_source))
        not_bool = empty_correction_record()
        not_bool["troposphere_applied"] = "True"
        self.assertTrue(validate_correction_record(not_bool))


class CorrectionPropagationTests(unittest.TestCase):
    def test_integrity_gate_requires_a_valid_correction_record(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "pair.json"
            artifact = pair("2025-11-02", "2025-11-14")
            path.write_text(json.dumps(artifact), encoding="utf-8")
            self.assertTrue(validate_pair_artifact(path)["pass"])
            del artifact["applied_corrections"]
            path.write_text(json.dumps(artifact), encoding="utf-8")
            report = validate_pair_artifact(path)
        self.assertFalse(report["pass"])
        self.assertTrue(any("applied_corrections" in finding for finding in report["findings"]))

    def test_chain_sum_rejects_pairs_with_different_correction_states(self):
        corrected = mark_applied(set_product_state(empty_correction_record(), "ionosphere", False, "product:flag"), "ionosphere", "terragauge:screen")
        with self.assertRaises(ValueError):
            chain_sum([pair("2025-11-02", "2025-11-14"), pair("2025-11-14", "2025-11-26", corrected)])

    def test_chain_sum_and_deramp_carry_the_correction_record(self):
        record = empty_correction_record()
        chained = chain_sum([pair("2025-11-02", "2025-11-14"), pair("2025-11-14", "2025-11-26")])
        self.assertEqual(chained["applied_corrections"], record)
        self.assertEqual(deramp_pair(pair("2025-11-02", "2025-11-14"))["applied_corrections"], record)


if __name__ == "__main__":
    unittest.main()

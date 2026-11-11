import importlib.util
import unittest
from pathlib import Path

from backend.publish_guard import UnpublishableInput, assert_publishable
from backend.service import TerraGaugeService

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "data" / "sample_cells.json"


def _script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PublishGuardTests(unittest.TestCase):
    def test_demo_dataset_status_is_refused(self):
        with self.assertRaises(UnpublishableInput):
            assert_publishable({"dataset_status": "demonstration_only_replace_with_source_derived_outputs", "cells": []}, "payload")

    def test_demo_record_inside_a_dataset_is_refused(self):
        with self.assertRaises(UnpublishableInput):
            assert_publishable({"dataset_status": "source_derived", "cells": [{"cell_id": "a", "source_status": "demo_not_source_derived"}]}, "payload")

    def test_source_derived_payload_passes(self):
        assert_publishable({"dataset_status": "source_derived_pairwise_evidence", "cells": [{"source_status": "source_derived"}], "stations": [{"source_status": "source_derived"}]}, "payload")

    def test_sample_fixture_cannot_reach_the_website_export(self):
        # MASTER section 15: data/sample_cells.json must never reach a published output.
        with self.assertRaises(UnpublishableInput):
            _script("export_web").load(SAMPLE)

    def test_sample_fixture_cannot_reach_the_provisional_build(self):
        with self.assertRaises(UnpublishableInput):
            _script("build_provisional").load(SAMPLE)

    def test_api_summary_exposes_dataset_status(self):
        summary = TerraGaugeService(SAMPLE).summary()
        self.assertTrue(summary["dataset_status"].startswith("demonstration_only"))


if __name__ == "__main__":
    unittest.main()

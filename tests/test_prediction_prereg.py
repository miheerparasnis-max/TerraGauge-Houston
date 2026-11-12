"""The OPERA -> NISAR prediction test stays blind: predictor before target, previewed pairs excluded."""

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "config" / "prediction_test.json").read_text(encoding="utf-8"))


class PredictionPreregistrationTests(unittest.TestCase):
    def test_predictor_ends_before_the_test_window(self):
        self.assertLess(CONFIG["predictor"]["end"], CONFIG["target"]["window_start"])

    def test_previewed_pairs_are_before_the_test_window(self):
        for pair in CONFIG["target"]["previewed_pairs_excluded"]:
            end = pair.split("_")[1]
            self.assertLessEqual(f"{end[:4]}-{end[4:6]}-{end[6:]}", CONFIG["target"]["window_start"])

    def test_frozen_predictor_matches_its_window(self):
        frozen = json.loads((ROOT / CONFIG["predictor"]["frozen_file"]).read_text(encoding="utf-8"))
        self.assertEqual(frozen["window"], [CONFIG["predictor"]["start"], CONFIG["predictor"]["end"]])
        self.assertGreater(len(frozen["cells"]), 1000)

    def test_power_runs_before_scoring_and_sign_is_blocking(self):
        self.assertTrue(CONFIG["power"]["must_run_before_scoring"])
        self.assertTrue(any("sign convention" in c for c in CONFIG["blocking_conditions"]))


if __name__ == "__main__":
    unittest.main()

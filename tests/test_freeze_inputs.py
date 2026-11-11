import importlib.util
import unittest
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location("freeze_inputs", Path(__file__).resolve().parents[1] / "scripts" / "freeze_inputs.py")
freeze = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(freeze)


class FreezeDiffTests(unittest.TestCase):
    def test_unchanged_inputs_pass(self):
        self.assertEqual(freeze.diff_freeze({"a": "1"}, {"a": "1"}), {"changed": [], "missing": [], "added": []})

    def test_changed_missing_and_added_inputs_are_reported(self):
        result = freeze.diff_freeze({"a": "1", "b": "2"}, {"a": "9", "b": None, "c": "3"})
        self.assertEqual(result, {"changed": ["a"], "missing": ["b"], "added": ["c"]})


if __name__ == "__main__":
    unittest.main()

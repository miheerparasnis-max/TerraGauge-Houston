import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from backend.provenance import ProvenanceLog


class ProvenanceTests(unittest.TestCase):
    def test_manifest_records_inputs_and_outputs_with_hashes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / "in.json", root / "out.json"
            source.write_text('{"a": 1}', encoding="utf-8")
            output.write_text('{"b": 2}', encoding="utf-8")
            log = ProvenanceLog(root=root, tracked={"in.json"})
            log.read(source)
            log.wrote(output)
            manifest = log.write(root / "manifest.json", artifact_type="test", command="python3 x.py")
            saved = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(saved, manifest)
        self.assertEqual(saved["inputs"], [{"path": "in.json", "sha256": hashlib.sha256(b'{"a": 1}').hexdigest(), "tracked": True}])
        self.assertEqual(saved["outputs"], [{"path": "out.json", "sha256": hashlib.sha256(b'{"b": 2}').hexdigest(), "tracked": False}])
        self.assertEqual(saved["command"], "python3 x.py")

    def test_untracked_inputs_say_how_to_regenerate(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "gen.json").write_text("{}", encoding="utf-8")
            log = ProvenanceLog(root=root, tracked=set(), regenerate={"gen.json": "python3 scripts/build.py"})
            log.read(root / "gen.json")
            manifest = log.write(root / "m.json", artifact_type="test", command="c")
        self.assertEqual(manifest["inputs"][0]["regenerate_with"], "python3 scripts/build.py")


if __name__ == "__main__":
    unittest.main()

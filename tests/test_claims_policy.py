"""MASTER G2 / section 20 regression: published copy and data stay inside the claims policy."""

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB_DATA = ROOT / "web" / "public" / "data"

# MASTER G2 search list, plus the "NISAR can't" spelling of "NISAR cannot".
FORBIDDEN = [
    r"\bsinking\b", r"\bwill flood\b", r"\bcaused by\b", r"\bcaused the\b", r"\bmeasured subsidence\b",
    r"\bour node measured\b", r"\bpredict\w*", r"\bdefinitely\b", r"\bproves\b", r"\bNISAR (cannot|can['’]t)\b",
    r"\bannual subsidence rate\b", r"\bworks everywhere\b", r"\bfirst ever\b", r"\bAI predicted\b",
]
PUBLISHED = sorted((ROOT / "web" / "src").glob("*.ts*")) + sorted(WEB_DATA.glob("*.json")) + [ROOT / "README.md"]


def hits(text):
    return [m.group(0) for pattern in FORBIDDEN for m in re.finditer(pattern, text, flags=re.IGNORECASE)]


class ClaimsPolicyTests(unittest.TestCase):
    def test_published_copy_has_no_forbidden_phrases(self):
        found = {str(path.relative_to(ROOT)): hits(path.read_text(encoding="utf-8")) for path in PUBLISHED}
        self.assertEqual({k: v for k, v in found.items() if v}, {})

    def test_detector_catches_known_phrases(self):
        self.assertTrue(hits("Sinking about 1 cm a year"))
        self.assertTrue(hits("why NISAR can't measure this"))
        self.assertFalse(hits("until the team approves the reference"))

    def test_site_data_carries_no_projections(self):
        meta = json.loads((WEB_DATA / "meta.json").read_text(encoding="utf-8"))
        self.assertNotIn("forecast", meta)
        self.assertNotIn("detect", meta["nisar"])
        cells = json.loads((WEB_DATA / "cells.json").read_text(encoding="utf-8"))
        self.assertFalse([c["id"] for c in cells if "future" in c])
        self.assertFalse([s["id"] for s in meta["sensors"] if "future2035" in s])

    def test_site_data_is_traceable(self):
        meta = json.loads((WEB_DATA / "meta.json").read_text(encoding="utf-8"))
        manifest = ROOT / meta["provenance"]["manifest"]
        self.assertTrue(manifest.is_file())
        recorded = {row["path"] for row in json.loads(manifest.read_text(encoding="utf-8"))["outputs"]}
        self.assertTrue({"web/public/data/cells.json", "web/public/data/sites.json"} <= recorded)
        self.assertEqual(meta["nisarArchive"]["inventory"], "data/manifests/nisar_track062_inventory_20261110.json")


if __name__ == "__main__":
    unittest.main()

"""MASTER G2 / section 20 regression: published copy and data stay inside the claims policy."""

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB_DATA = ROOT / "web" / "public" / "data"

# MASTER G2 search list, plus the "NISAR can't" spelling of "NISAR cannot".
# Decision D-039 (docs/decisions.md): plain "sinking" and the word "predict"
# are allowed (the site is for the public, and it says plainly what it cannot
# predict); the overclaims below stay forbidden. D-040: the ground-sinking
# forecast stays, but flood depths are never forecast; the flood view shows
# only the measured drop.
FORBIDDEN = [
    r"\bwill flood\b", r"\bcaused by\b", r"\bcaused the\b", r"\bmeasured subsidence\b",
    r"\bour node measured\b", r"\bdefinitely\b", r"\bproves\b", r"\bNISAR (cannot|can['’]t)\b",
    r"\bannual subsidence rate\b", r"\bworks everywhere\b", r"\bfirst ever\b", r"\bAI predicted\b",
]
# D-040: no forecast flood depths ("floods 5 cm deeper by 2031", "the same
# flood would be about ... deeper", ocean-rise add-ons).
FLOOD_FORECAST = [
    r"deeper by (\{year\}|20\d\d)", r"flood would be (about )?\S* ?\S* ?cm deeper",
    r"floods? (will|would) (get|be) deeper", r"forecast (to sink|sinking)[^.]*deeper", r"ocean rise",
]
PUBLISHED = sorted((ROOT / "web" / "src").glob("*.ts*")) + sorted(WEB_DATA.glob("*.json")) + [ROOT / "README.md"]


def hits(text, patterns=FORBIDDEN):
    return [m.group(0) for pattern in patterns for m in re.finditer(pattern, text, flags=re.IGNORECASE)]


class ClaimsPolicyTests(unittest.TestCase):
    def test_published_copy_has_no_forbidden_phrases(self):
        found = {str(path.relative_to(ROOT)): hits(path.read_text(encoding="utf-8")) for path in PUBLISHED}
        self.assertEqual({k: v for k, v in found.items() if v}, {})

    def test_no_forecast_flood_depths(self):
        found = {str(path.relative_to(ROOT)): hits(path.read_text(encoding="utf-8"), FLOOD_FORECAST) for path in PUBLISHED}
        self.assertEqual({k: v for k, v in found.items() if v}, {})
        self.assertTrue(hits("By 2031 the same flood would be about 4 cm deeper", FLOOD_FORECAST))
        self.assertTrue(hits("floods 4 cm deeper by {year}", FLOOD_FORECAST))
        self.assertFalse(hits("the same flood now stands about 4 cm deeper than it would have then", FLOOD_FORECAST))

    def test_detector_catches_known_phrases(self):
        self.assertTrue(hits("This proves the ground will flood"))
        self.assertTrue(hits("why NISAR can't measure this"))
        self.assertFalse(hits("until the team approves the reference"))

    def test_forecast_is_tested_and_bounded(self):
        """D-039: a forecast may appear only as a tested trend with ranges,
        and never beyond the horizon the walk-forward tests covered."""
        meta = json.loads((WEB_DATA / "meta.json").read_text(encoding="utf-8"))
        f = meta.get("forecast")
        if not f:
            return
        self.assertTrue(f["benchmark"]["test_cases"] > 0)
        self.assertEqual(len(f["bands_cm"]), len(f["years"]))
        self.assertLessEqual(len(f["years"]), round(f["tested_horizon_years"]))
        cells = json.loads((WEB_DATA / "cells.json").read_text(encoding="utf-8"))
        years = {str(y) for y in f["years"]}
        for c in cells:
            if "future" in c:
                self.assertEqual(set(c["future"]["by"]), years)

    def test_site_data_is_traceable(self):
        meta = json.loads((WEB_DATA / "meta.json").read_text(encoding="utf-8"))
        manifest = ROOT / meta["provenance"]["manifest"]
        self.assertTrue(manifest.is_file())
        recorded = {row["path"] for row in json.loads(manifest.read_text(encoding="utf-8"))["outputs"]}
        self.assertTrue({"web/public/data/cells.json", "web/public/data/sites.json"} <= recorded)
        self.assertEqual(meta["nisarArchive"]["inventory"], "data/manifests/nisar_track062_inventory_20261110.json")


if __name__ == "__main__":
    unittest.main()

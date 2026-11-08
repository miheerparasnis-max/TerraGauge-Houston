"""One-time correction of opera_water_fraction in already-derived OPERA cell artifacts.

Earlier artifacts counted `water_mask > 0` pixels, which per the DISP-S1
Product Specification ("0 indicates water and 1 indicates land") is the LAND
fraction. Because the mask is binary, water = 1 - stored value. The raw NetCDF
files are local-only, so this corrects the derived JSON without re-download.
Re-running is safe: corrected files are skipped.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

NOTE = "opera_water_fraction corrected on 2026-11-08: earlier value counted water_mask==1 (land); now 1 - previous value (water_mask==0)."


def correct(path: Path) -> bool:
    artifact = json.loads(path.read_text(encoding="utf-8"))
    if artifact.get("artifact_type") != "opera_disp_pair_cells" or artifact.get("water_fraction_correction"):
        return False
    for cell in artifact.get("cells", []):
        value = cell.get("opera_water_fraction")
        if value is not None:
            cell["opera_water_fraction"] = round(1.0 - float(value), 6)
    artifact["water_fraction_correction"] = NOTE
    path.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    return True


if __name__ == "__main__":
    paths = [Path(p) for p in sys.argv[1:]] or sorted(Path("data/derived").glob("opera_disp_houston_*_pair_cells.json"))
    changed = [p.name for p in paths if correct(p)]
    print(f"corrected {len(changed)} artifact(s)")

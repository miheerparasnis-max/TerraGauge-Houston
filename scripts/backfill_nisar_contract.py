"""Backfill the five pre-contract NISAR pair artifacts (2026-11-10, plan F-2/F-3).

The artifacts were extracted before the adapter wrote `applied_corrections` and
`wavelength`. This adds both honestly, without touching any cell value:

- applied_corrections: every correction "unverified" (null). The adapter applied
  none, and the product's own phase-correction state has not been read (audit A1).
- wavelength: the CLI value that was used (0.241962 m), marked `cli_unverified`.
  The pair-1 manifest records a 1.239 GHz center frequency; re-extraction at plan
  step B2 verifies every pair against its own metadata.

Idempotent: an artifact that already has both fields is left as it is.

    python3 scripts/backfill_nisar_contract.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.ingestion.corrections import empty_correction_record  # noqa: E402

PAIRS = ["20251102_20251114", "20251114_20251126", "20251126_20251208", "20251208_20251220", "20251220_20260101"]
NOTE = ("Backfilled 2026-11-10: extracted before the adapter read the wavelength from product metadata. "
        "data/manifests/nisar_gunw_20251102_20251114.json records center_frequency_hz 1.239e9 for pair 1; "
        "re-extraction at plan step B2 verifies every pair.")


def backfill(artifact: dict) -> tuple[dict, bool]:
    changed = False
    if "applied_corrections" not in artifact:
        artifact["applied_corrections"] = empty_correction_record()
        changed = True
    if "wavelength" not in artifact:
        value = float(artifact["parameters"]["wavelength_m"])
        artifact["wavelength"] = {"value_m": value, "source": "cli_unverified", "center_frequency_hz": None, "metadata_paths": [], "cli_value_m": value, "note": NOTE}
        changed = True
    return artifact, changed


def main() -> None:
    for name in PAIRS:
        path = ROOT / "data" / "derived" / f"nisar_gunw_houston_{name}_pair_cells.json"
        artifact, changed = backfill(json.loads(path.read_text(encoding="utf-8")))
        if changed:
            path.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
        print(f"{path.name}: {'backfilled' if changed else 'already current'}")


if __name__ == "__main__":
    main()

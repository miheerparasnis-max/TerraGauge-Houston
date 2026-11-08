"""Extend the Houston OPERA record from May 2021 to the newest available date.

Downloads the 11 OPERA DISP-S1 products (about 3.7 GB) that continue the
existing 2016-2021 chain, shrinks each to compact Houston cells, then rebuilds
the website data. Needs a free NASA Earthdata login.

    python3 -m pip install earthaccess numpy h5py pyproj
    python3 scripts/fetch_opera_extension.py

Raw .nc files go to data/raw/opera/ (git-ignored). Add --delete-raw to remove
each one after it is processed.
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
CATALOG = ROOT / "data/manifests/opera_disp_s1_f38238_full_catalog_20261108.json"
DERIVED = ROOT / "data/derived"
RAW = ROOT / "data/raw/opera"
BBOX = (-95.95, 29.4, -94.8, 30.2)


def iso(stamp: str) -> str:
    return f"{stamp[:4]}-{stamp[4:6]}-{stamp[6:8]}"


def existing_end() -> str:
    ends = []
    for path in DERIVED.glob("opera_disp_houston_*_pair_cells.json"):
        ends.append(path.stem.split("_")[4])
    return max(ends)


def plan(start: str) -> list[dict]:
    """Longest-hop chain of products from `start` (YYYYMMDD) to the newest date."""
    granules = json.loads(CATALOG.read_text(encoding="utf-8"))["granules"]
    by_reference = defaultdict(list)
    for granule in granules:
        by_reference[granule["reference_acquisition_utc"][:8]].append(granule)
    chain, current = [], start
    while current in by_reference:
        nxt = max(by_reference[current], key=lambda g: g["secondary_acquisition_utc"])
        if nxt["secondary_acquisition_utc"][:8] <= current:
            break
        chain.append(nxt)
        current = nxt["secondary_acquisition_utc"][:8]
    return chain


def main() -> None:
    import earthaccess
    from backend.ingestion.opera import OperaConfig, write_disp_cells

    delete_raw = "--delete-raw" in sys.argv
    chain = plan(existing_end())
    if not chain:
        print("Nothing to download: the OPERA record is already up to date.")
        return
    total = sum(g["size_mb"] for g in chain) / 1024
    print(f"{len(chain)} products, about {total:.1f} GB, {iso(chain[0]['reference_acquisition_utc'])} to {iso(chain[-1]['secondary_acquisition_utc'])}")
    earthaccess.login(strategy="interactive", persist=True)
    RAW.mkdir(parents=True, exist_ok=True)
    for index, granule in enumerate(chain, start=1):
        ref, sec = granule["reference_acquisition_utc"][:8], granule["secondary_acquisition_utc"][:8]
        output = DERIVED / f"opera_disp_houston_{ref}_{sec}_pair_cells.json"
        if output.exists():
            print(f"[{index}/{len(chain)}] already processed {output.name}")
            continue
        print(f"[{index}/{len(chain)}] downloading {granule['granule_id']}")
        files = earthaccess.download([granule["download_url"]], str(RAW))
        source = Path(files[0])
        write_disp_cells(source, output, OperaConfig(crs="EPSG:32615", reference_date=iso(ref), secondary_date=iso(sec), bounding_box=BBOX))
        print(f"           wrote {output.name}")
        if delete_raw:
            source.unlink()
    print("Rebuilding TerraGauge data...")
    subprocess.run([sys.executable, str(ROOT / "scripts/build_provisional.py")], check=True, cwd=ROOT)
    subprocess.run([sys.executable, str(ROOT / "scripts/export_web.py")], check=True, cwd=ROOT)
    print("Done. Reload the website.")


if __name__ == "__main__":
    main()

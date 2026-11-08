"""Download NASADEM, OPERA DSWx-S1 and OPERA DIST-ALERT for Houston and sample them onto TerraGauge cells.

Run on a computer that can reach NASA Earthdata (needs a free Earthdata login):

    python3 -m pip install earthaccess rasterio numpy
    python3 scripts/fetch_nasa_layers.py            # all three layers
    python3 scripts/fetch_nasa_layers.py dswx       # just one

Raw downloads go to data/raw/nasa_layers/ (git-ignored). Compact per-cell
results go to data/derived/nasa_layers/. Then run scripts/export_web.py.
"""

from __future__ import annotations

import importlib.util
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BBOX = (-95.95, 29.4, -94.8, 30.2)
NISAR_WINDOW = ("2025-11-01", "2026-01-02")
CELLS = ROOT / "data/derived/nisar_gunw_houston_20251102_20251114_pair_cells.json"
RAW = ROOT / "data/raw/nasa_layers"
OUT = ROOT / "data/derived/nasa_layers"

# Load the sampler without importing the whole backend package (works on Python 3.9+).
_spec = importlib.util.spec_from_file_location("raster_layers", ROOT / "backend/ingestion/raster_layers.py")
raster_layers = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(raster_layers)  # type: ignore[union-attr]


def _links(granules, pattern: str) -> list[str]:
    return [link for g in granules for link in g.data_links() if re.search(pattern, link)]


def nasadem(earthaccess) -> None:
    granules = earthaccess.search_data(short_name="NASADEM_HGT", version="001", bounding_box=BBOX)
    files = earthaccess.download(_links(granules, r"\.zip$"), str(RAW / "nasadem"))
    rasters = []
    for path in map(Path, files):
        with zipfile.ZipFile(path) as archive:
            rasters += [f"/vsizip/{path}/{name}" for name in archive.namelist() if name.endswith(".hgt")]
    raster_layers.write_layer(rasters, CELLS, "nasadem", OUT / "nasadem_houston_cells.json", {"granules": [Path(f).name for f in files]})


def latest_per_tile(granules):
    best = {}
    for g in granules:
        name = g["umm"]["GranuleUR"]
        tile = re.search(r"_T(\w{5})_", name)
        when = g["umm"]["TemporalExtent"]["RangeDateTime"]["BeginningDateTime"]
        key = tile.group(1) if tile else name
        if key not in best or when > best[key][0]:
            best[key] = (when, g)
    return [value[1] for value in best.values()]


def dswx(earthaccess) -> None:
    granules = earthaccess.search_data(short_name="OPERA_L3_DSWX-S1_V1", bounding_box=BBOX, temporal=NISAR_WINDOW)
    files = earthaccess.download(_links(granules, r"_B01_WTR\.tif$"), str(RAW / "dswx"))
    raster_layers.write_layer(files, CELLS, "dswx", OUT / "dswx_houston_cells.json", {"date": f"{NISAR_WINDOW[0]} to {NISAR_WINDOW[1]}", "granule_count": len(files)})


def dist(earthaccess) -> None:
    granules = earthaccess.search_data(short_name="OPERA_L3_DIST-ALERT-HLS_V1", bounding_box=BBOX, temporal=NISAR_WINDOW)
    files = earthaccess.download(_links(latest_per_tile(granules), r"VEG-DIST-STATUS\.tif$"), str(RAW / "dist"))
    raster_layers.write_layer(files, CELLS, "dist", OUT / "dist_houston_cells.json", {"date": f"latest status up to {NISAR_WINDOW[1]}", "granule_count": len(files)})


def main() -> None:
    import earthaccess

    auth = earthaccess.login(strategy="interactive", persist=True)
    if not auth or not getattr(auth, "authenticated", False):
        sys.exit("Earthdata login failed. Check your username and password (the password is hidden while you type), "
                 "make sure you clicked the confirmation link NASA emailed you, then run this again.")
    wanted = sys.argv[1:] or ["nasadem", "dswx", "dist"]
    for name in wanted:
        print(f"== {name}")
        {"nasadem": nasadem, "dswx": dswx, "dist": dist}[name](earthaccess)
        print(f"   wrote {OUT / (name + '_houston_cells.json')}")
    print("Done. Now run: python3 scripts/export_web.py")


if __name__ == "__main__":
    main()

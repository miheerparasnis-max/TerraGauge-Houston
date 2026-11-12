"""Fill south Houston with real satellite data from the neighbouring OPERA frame.

Our record uses OPERA DISP-S1 frame F38238, whose footprint ends on a slanted
line around 29.5-29.6 N (Pearland, Alvin, Rosharon, Needville get no data).
Frame F38239 is the next frame along the same Sentinel-1 track, imaged on the
same dates. This downloads the F38239 products matching our 30-product
chain, keeps only the southern strip (plus an overlap band used to line the
two frames up), deletes each raw file after use, then rebuilds everything.

    python3 -m pip install earthaccess numpy h5py pyproj
    python3 scripts/fetch_opera_south.py            # about 30 downloads
    python3 scripts/fetch_opera_south.py --keep-raw # keep the .nc files

Safe to stop and re-run: finished products are skipped.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "data" / "derived" / "opera_f38239"
RAW = ROOT / "data" / "raw" / "opera_f38239"
VELOCITY = ROOT / "data" / "derived" / "provisional" / "opera_houston_los_velocity.json"
SOUTH_BBOX = (-95.95, 29.38, -94.80, 29.80)   # gap plus an overlap band with F38238


def main() -> None:
    try:
        import earthaccess
        from backend.ingestion.opera import OperaConfig, write_disp_cells
    except ImportError:
        sys.exit("Run first:  python3 -m pip install earthaccess numpy h5py pyproj")
    dates = [d.replace("-", "") for d in json.loads(VELOCITY.read_text(encoding="utf-8"))["dates"]]
    pairs = list(zip(dates[:-1], dates[1:]))
    auth = earthaccess.login(strategy="interactive", persist=True)
    if not auth or not getattr(auth, "authenticated", False):
        sys.exit("Earthdata login failed. Check your username and password, then try again.")
    print("Searching NASA Earthdata for frame F38239...")
    granules = earthaccess.search_data(short_name="OPERA_L3_DISP-S1_V1", granule_name="*F38239*", count=2000)
    best: dict[tuple[str, str], tuple[str, object]] = {}
    for g in granules:
        name = g["umm"]["GranuleUR"]
        m = re.search(r"_F38239_VV_(\d{8})T\d+Z_(\d{8})T\d+Z_v[\d.]+_(\d{8}T\d+Z)", name)
        if m:
            key = (m.group(1), m.group(2))
            if key not in best or m.group(3) > best[key][0]:
                best[key] = (m.group(3), g)
    todo = [(ref, sec) for ref, sec in pairs if (ref, sec) in best]
    missing = [(ref, sec) for ref, sec in pairs if (ref, sec) not in best]
    print(f"{len(todo)} of {len(pairs)} matching products found." + (f" Missing: {', '.join(f'{a}-{b}' for a, b in missing)}" if missing else ""))
    OUT.mkdir(parents=True, exist_ok=True)
    RAW.mkdir(parents=True, exist_ok=True)
    keep = "--keep-raw" in sys.argv
    for i, (ref, sec) in enumerate(todo, start=1):
        output = OUT / f"opera_disp_f38239_{ref}_{sec}_pair_cells.json"
        if output.exists():
            print(f"[{i}/{len(todo)}] already done {output.name}")
            continue
        print(f"[{i}/{len(todo)}] downloading {ref} -> {sec}")
        files = earthaccess.download([best[(ref, sec)][1]], str(RAW))
        nc = [Path(f) for f in files if str(f).endswith(".nc")]
        if not nc:
            sys.exit("Download failed. Sign in once at https://search.asf.alaska.edu with your Earthdata account, accept the data agreement, then run this again.")
        iso = lambda s: f"{s[:4]}-{s[4:6]}-{s[6:]}"  # noqa: E731
        write_disp_cells(nc[0], output, OperaConfig(crs="EPSG:32615", reference_date=iso(ref), secondary_date=iso(sec), bounding_box=SOUTH_BBOX))
        if not keep:
            nc[0].unlink()
    print("Rebuilding TerraGauge data with the southern frame...")
    for script in ("build_provisional.py", "build_hazards.py", "export_web.py"):
        subprocess.run([sys.executable, str(ROOT / "scripts" / script)], check=True, cwd=ROOT)
    print("Done. Reload the website.")


if __name__ == "__main__":
    main()

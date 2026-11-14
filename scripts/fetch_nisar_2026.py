"""Download the 2026 NISAR GUNW pairs one at a time, shrink each to study-area cells, delete the raw file.

The 22 track-062 frame-016 pairs from 2026-01-01 (data/manifests/nisar_track062_inventory_20261110.json)
are about 51 GB, more than most laptops have free, so each file is:
downloaded -> MD5-checked against NASA's catalog -> ingested to
data/derived/nisar_gunw_houston_<ref>_<sec>_pair_cells.json -> deleted.
The first raw file is kept for plan step B1 (sign convention and correction flags).

    python3 -m pip install earthaccess        # plus requirements.txt (numpy, h5py, pyproj)
    python3 scripts/fetch_nisar_2026.py       # all 22, in chain order
    python3 scripts/fetch_nisar_2026.py 6     # only the first 6 (minimum for the prediction test)

Safe to stop and re-run: finished pairs are skipped. Needs an Earthdata login.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
INVENTORY = ROOT / "data" / "manifests" / "nisar_track062_inventory_20261110.json"
RAW = ROOT / "data" / "raw" / "nisar_2026"
DERIVED = ROOT / "data" / "derived"
LOG = ROOT / "data" / "manifests" / "nisar_2026_downloads.json"
BBOX = (-95.95, 29.4, -94.8, 30.2)
GRID = "/science/LSAR/GUNW/grids/frequencyA/unwrappedInterferogram"
MIN_FREE_GB = 6.0


def digest(path: Path, name: str) -> str:
    h = hashlib.new(name)
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 22), b""):
            h.update(block)
    return h.hexdigest()


def product_crs(path: Path) -> str:
    """EPSG code from the product's own projection dataset (never assumed)."""
    import h5py

    with h5py.File(path, "r") as f:
        found = []
        f[GRID].visititems(lambda name, obj: found.append(obj) if name.split("/")[-1] == "projection" and isinstance(obj, h5py.Dataset) else None)
        for obj in found:
            for value in (obj[()] if obj.shape == () else None, obj.attrs.get("epsg_code")):
                try:
                    code = int(value)
                except (TypeError, ValueError):
                    continue
                if 1024 <= code <= 32767:
                    return f"EPSG:{code}"
    sys.exit(f"No EPSG code found under {GRID} in {path.name}. The raw file is kept; report this before continuing.")


def login():
    import earthaccess

    for strategy in ("environment", "netrc", "interactive"):
        try:
            auth = earthaccess.login(strategy=strategy, persist=strategy == "interactive")
        except Exception:  # noqa: BLE001
            continue
        if auth and getattr(auth, "authenticated", False):
            return earthaccess
    sys.exit("Earthdata login failed. Check your username and password, then run this again.")


def main() -> None:
    try:
        import h5py  # noqa: F401
        from backend.ingestion.nisar import GunwConfig, write_pair_cells
    except ImportError:
        sys.exit("Run first:  python3 -m pip install -r requirements.txt earthaccess   (Python 3.14; h5py has no 3.15 wheel)")
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    granules = [g for g in json.loads(INVENTORY.read_text(encoding="utf-8"))["granules"] if g["reference_date"] >= "2026-01-01"]
    granules.sort(key=lambda g: g["reference_date"])
    granules = granules[:limit] if limit else granules
    log = json.loads(LOG.read_text(encoding="utf-8")) if LOG.is_file() else {"artifact_type": "nisar_download_log", "inventory": str(INVENTORY.relative_to(ROOT)), "pairs": {}}
    earthaccess = None
    RAW.mkdir(parents=True, exist_ok=True)
    for n, g in enumerate(granules, start=1):
        ref, sec = g["reference_date"].replace("-", ""), g["secondary_date"].replace("-", "")
        out = DERIVED / f"nisar_gunw_houston_{ref}_{sec}_pair_cells.json"
        tag = f"[{n}/{len(granules)}] {g['reference_date']} -> {g['secondary_date']}"
        if out.is_file():
            print(f"{tag} already done")
            continue
        if shutil.disk_usage(RAW).free / 1e9 < MIN_FREE_GB:
            sys.exit(f"Less than {MIN_FREE_GB:g} GB free; stopping. Free some space and re-run (finished pairs are kept).")
        path = RAW / f"{g['granule_id']}.h5"
        if not path.is_file():
            earthaccess = earthaccess or login()
            print(f"{tag} downloading {g['size_bytes'] / 1e9:.1f} GB")
            files = earthaccess.download([g["download_url"]], str(RAW))
            if not files:
                sys.exit("Download failed. Sign in once at https://search.asf.alaska.edu and accept the NISAR data agreement, then re-run.")
            path = Path(files[0])
        md5 = digest(path, "md5")
        if md5 != g["checksum"]["value"]:
            path.unlink()
            sys.exit(f"{tag} MD5 mismatch ({md5} vs catalog {g['checksum']['value']}); file deleted, re-run to retry.")
        sha = digest(path, "sha256")
        crs = product_crs(path)
        print(f"{tag} MD5 ok, {crs}, ingesting")
        write_pair_cells(path, out, GunwConfig(wavelength_m=None, crs=crs, x_path=f"{GRID}/HH/xCoordinates", y_path=f"{GRID}/HH/yCoordinates", cell_pixels=13,
                                               acquisition_dates=(g["reference_date"], g["secondary_date"]), bounding_box=BBOX))
        log["pairs"][g["granule_id"]] = {"reference_date": g["reference_date"], "secondary_date": g["secondary_date"], "md5": md5, "sha256": sha,
                                         "size_bytes": path.stat().st_size, "crs": crs, "output": str(out.relative_to(ROOT)),
                                         "retrieved_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "raw_kept": n == 1}
        LOG.write_text(json.dumps(log, indent=2) + "\n", encoding="utf-8")
        if n != 1:
            path.unlink()
        print(f"{tag} wrote {out.name}")
    print("Done. The first raw file is kept in data/raw/nisar_2026/ for the sign-convention and correction check (plan B1).")


if __name__ == "__main__":
    main()

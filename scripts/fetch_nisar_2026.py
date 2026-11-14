"""Download the 2026 NISAR track-062 pairs and keep only Houston.

The repo already has the first five pairs (2025-11-02 to 2026-01-01). The
inventory (data/manifests/nisar_track062_inventory_20261110.json) lists 22 more,
2026-01-01 to 2026-10-16, about 2.3 GB each (51 GB in all). For each one this:
downloads it with your NASA Earthdata login, checks the archive's MD5, cuts
out the Houston study box, runs the structural integrity gate, records a
manifest, and deletes the raw .h5 (unless --keep-raw).

It only extracts the pairs. It does not score the pre-registered prediction
test; that is run separately, from the pre-registered rules.

    python3 -m pip install earthaccess numpy h5py pyproj
    python3 scripts/fetch_nisar_2026.py              # all 22, safe to stop and re-run
    python3 scripts/fetch_nisar_2026.py --keep-raw   # keep the .h5 files

First time only: sign in at https://search.asf.alaska.edu with the same
Earthdata account and accept the NISAR data agreement, or downloads fail.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
INVENTORY = ROOT / "data" / "manifests" / "nisar_track062_inventory_20261110.json"
RAW = ROOT / "data" / "raw" / "nisar"
DERIVED = ROOT / "data" / "derived"
MANIFESTS = ROOT / "data" / "manifests"
BBOX = (-95.95, 29.4, -94.8, 30.2)
GRID = "/science/LSAR/GUNW/grids/frequencyA/unwrappedInterferogram/HH"


def md5(path: Path) -> str:
    h = hashlib.md5()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(8 << 20), b""):
            h.update(block)
    return h.hexdigest()


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(8 << 20), b""):
            h.update(block)
    return h.hexdigest()


def main() -> None:
    try:
        import earthaccess
        from backend.ingestion.nisar import GunwConfig, write_pair_cells
        from backend.ingestion.quality import write_pair_integrity_report
    except ImportError:
        sys.exit("Run first:  python3 -m pip install earthaccess numpy h5py pyproj")
    granules = [g for g in json.loads(INVENTORY.read_text(encoding="utf-8"))["granules"] if not g.get("in_repo")]
    print(f"{len(granules)} NISAR pairs to fetch ({sum(g['size_bytes'] for g in granules) / 1e9:.0f} GB in all, one at a time).")
    auth = earthaccess.login(strategy="interactive", persist=True)
    if not auth or not getattr(auth, "authenticated", False):
        sys.exit("Earthdata login failed. Check your username and password, then try again.")
    RAW.mkdir(parents=True, exist_ok=True)
    keep = "--keep-raw" in sys.argv
    done = failed = 0
    for i, g in enumerate(granules, start=1):
        ref, sec = g["reference_date"], g["secondary_date"]
        tag = f"{ref.replace('-', '')}_{sec.replace('-', '')}"
        out = DERIVED / f"nisar_gunw_houston_{tag}_pair_cells.json"
        report = DERIVED / f"nisar_gunw_houston_{tag}_pair_cells_integrity_report.json"
        if out.exists() and report.exists():
            print(f"[{i}/{len(granules)}] already done {ref} -> {sec}")
            done += 1
            continue
        h5 = RAW / f"{g['granule_id']}.h5"
        if not h5.exists():
            print(f"[{i}/{len(granules)}] downloading {ref} -> {sec} ({g['size_bytes'] / 1e9:.1f} GB)")
            files = earthaccess.download([g["download_url"]], str(RAW))
            if not files or not h5.exists():
                sys.exit("Download failed. Sign in once at https://search.asf.alaska.edu with your Earthdata account, accept the NISAR data agreement, then run this again.")
        else:
            print(f"[{i}/{len(granules)}] using downloaded {ref} -> {sec}")
        want = (g.get("checksum") or {}).get("value")
        if want and md5(h5) != want:
            h5.unlink()
            print(f"  checksum mismatch, deleted; re-run to download {ref} -> {sec} again")
            failed += 1
            continue
        try:
            write_pair_cells(h5, out, GunwConfig(wavelength_m=None, crs="EPSG:32615", x_path=f"{GRID}/xCoordinates", y_path=f"{GRID}/yCoordinates", acquisition_dates=(ref, sec), bounding_box=BBOX))
            write_pair_integrity_report(out, report)
        except Exception as error:  # keep going; one bad granule shouldn't stop the rest
            print(f"  extraction failed for {ref} -> {sec}: {error}")
            out.unlink(missing_ok=True)
            failed += 1
            continue
        (MANIFESTS / f"nisar_gunw_{tag}.json").write_text(json.dumps({
            "artifact": h5.name,
            "collection": "NISAR_L2_GUNW_PROVISIONAL_V1",
            "download_endpoint": g["download_url"],
            "md5_archive": want,
            "sha256": sha256(h5),
            "retrieved_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "derived_artifact": str(out.relative_to(ROOT)),
            "integrity_report": str(report.relative_to(ROOT)),
            "study_bounds_wgs84": list(BBOX),
            "scientific_limit": "One 12-day (or 24-day) pairwise line-of-sight displacement observation. Not a velocity or a subsidence diagnosis.",
        }, indent=2) + "\n", encoding="utf-8")
        if not keep:
            h5.unlink()
        done += 1
        print(f"  ok: {out.name}")
    print(f"Finished: {done} of {len(granules)} pairs ready" + (f", {failed} failed (re-run to retry)" if failed else "") + ".")


if __name__ == "__main__":
    main()

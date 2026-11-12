"""Make one TerraGauge square for every 1 km of the Houston study area.

Earlier builds only kept squares that appeared in the NISAR evidence file,
whose footprint has stripes and gaps, so some squares (including ~2,000 with
OPERA satellite measurements) never reached the map. This script:

1. lays a complete 1 km grid (EPSG:3857, same ids as before) over the study
   box (-95.95, 29.4, -94.8, 30.2);
2. gives every square its FEMA flood zone by looking up its centre in the
   FEMA NFHL polygons already saved in data/derived;
3. writes data/derived/provisional/grid_cells.json.

Then `python3 scripts/build_grid.py --layers` re-samples NASADEM, DSWx and DIST
for every square (needs rasterio + pyproj and the raw files from
scripts/fetch_nasa_layers.py).
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
import zipfile
from math import atan, degrees, exp, floor, log, pi, radians, tan
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DERIVED = ROOT / "data" / "derived"
OUT = DERIVED / "provisional" / "grid_cells.json"
BBOX = (-95.95, 29.4, -94.8, 30.2)
R = 6378137.0
OVERLAY = DERIVED / "fema_nfhl_houston_polygon_overlay_2026-11-07.json"
PAIR = DERIVED / "terragauge_houston_evidence_pair_20251102_20251114.json"
OPERA = DERIVED / "provisional" / "opera_houston_los_velocity.json"


def merc(lon: float, lat: float) -> tuple[float, float]:
    return R * radians(lon), R * log(tan(pi / 4 + radians(lat) / 2))


def lonlat(x: float, y: float) -> tuple[float, float]:
    return degrees(x / R), degrees(2 * atan(exp(y / R)) - pi / 2)


def grid_ids(bbox=BBOX) -> list[tuple[int, int]]:
    x0, y0 = merc(bbox[0], bbox[1])
    x1, y1 = merc(bbox[2], bbox[3])
    out = []
    for i in range(floor(x0 / 1000), floor(x1 / 1000) + 1):
        for j in range(floor(y0 / 1000), floor(y1 / 1000) + 1):
            lon, lat = lonlat((i + 0.5) * 1000, (j + 0.5) * 1000)
            if bbox[0] <= lon <= bbox[2] and bbox[1] <= lat <= bbox[3]:
                out.append((i, j))
    return out


def _inside(x: float, y: float, ring: list[list[float]]) -> bool:
    hit = False
    n = len(ring)
    for k in range(n):
        x1, y1 = ring[k][0], ring[k][1]
        x2, y2 = ring[(k + 1) % n][0], ring[(k + 1) % n][1]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            hit = not hit
    return hit


def _polygons(geometry: dict) -> list[list[list[list[float]]]]:
    if geometry["type"] == "Polygon":
        return [geometry["coordinates"]]
    if geometry["type"] == "MultiPolygon":
        return geometry["coordinates"]
    return []


RANK = {"VE": 6, "V": 6, "AE": 5, "A": 5, "AO": 5, "AH": 5}


def zone_rank(zone: str | None, sub: str | None, sfha: bool) -> int:
    if sfha:
        return 4 + RANK.get(zone or "", 0)
    if zone == "X" and sub and ("0.2 PCT" in sub or "1 PCT" in sub):
        return 3
    if zone == "X" and sub and "LEVEE" in sub:
        return 2
    if zone == "OPEN WATER":
        return 1
    return 0


class ZoneLookup:
    def __init__(self, features: list[dict], size: float = 0.05):
        self.size = size
        self.index: dict[tuple[int, int], list[int]] = {}
        self.items = []
        for f in features:
            props = f.get("properties") or {}
            for poly in _polygons(f.get("geometry") or {}):
                xs = [p[0] for p in poly[0]]
                ys = [p[1] for p in poly[0]]
                box = (min(xs), min(ys), max(xs), max(ys))
                n = len(self.items)
                self.items.append((box, poly, props))
                for gx in range(floor(box[0] / size), floor(box[2] / size) + 1):
                    for gy in range(floor(box[1] / size), floor(box[3] / size) + 1):
                        self.index.setdefault((gx, gy), []).append(n)

    def zone(self, lon: float, lat: float) -> tuple[str | None, str | None, bool]:
        best, best_rank = (None, None, False), -1
        for n in self.index.get((floor(lon / self.size), floor(lat / self.size)), []):
            box, poly, props = self.items[n]
            if not (box[0] <= lon <= box[2] and box[1] <= lat <= box[3]):
                continue
            if _inside(lon, lat, poly[0]) and not any(_inside(lon, lat, hole) for hole in poly[1:]):
                z, sub, sfha = props.get("FLD_ZONE"), props.get("ZONE_SUBTY"), props.get("SFHA_TF") == "T"
                rk = zone_rank(z, sub, sfha)
                if rk > best_rank:
                    best, best_rank = (z, sub, sfha), rk
        return best


SFHA_SHARE_MIN = 0.25   # a square counts as high-risk if at least a quarter of it is in FEMA's 1% zone


def build() -> dict:
    known: dict[str, tuple[float, float]] = {}
    for path in (PAIR, OPERA):
        if path.is_file():
            for c in json.loads(path.read_text(encoding="utf-8"))["cells"]:
                known.setdefault(c["cell_id"], (float(c["longitude"]), float(c["latitude"])))
    ids = set(grid_ids())
    for cid in known:   # keep every square an earlier build had, even just outside the box
        m = re.fullmatch(r"epsg3857-1km-(-?\d+)-(-?\d+)", cid)
        if m:
            ids.add((int(m.group(1)), int(m.group(2))))
    lookup = ZoneLookup(json.loads(OVERLAY.read_text(encoding="utf-8"))["features"])
    cells = []
    steps = [0.1, 0.3, 0.5, 0.7, 0.9]
    for i, j in sorted(ids):
        cid = f"epsg3857-1km-{i}-{j}"
        lon, lat = known.get(cid) or lonlat((i + 0.5) * 1000, (j + 0.5) * 1000)
        tally: dict[tuple, int] = {}
        sfha = 0
        for a in steps:
            for b in steps:
                z = lookup.zone(*lonlat((i + a) * 1000, (j + b) * 1000))
                tally[z] = tally.get(z, 0) + 1
                sfha += z[2]
        share = sfha / 25
        if share >= SFHA_SHARE_MIN:
            sub_tally = {k: v for k, v in tally.items() if k[2]}
            zone = max(sub_tally, key=lambda k: (sub_tally[k], zone_rank(*k)))
        else:
            rest = {k: v for k, v in tally.items() if not k[2]}
            zone = max(rest, key=lambda k: (rest[k], zone_rank(*k)))
        cells.append({"cell_id": cid, "longitude": round(lon, 6), "latitude": round(lat, 6), "flood_zone": zone[0], "zone_subtype": zone[1],
                      "flood_exposed": share >= SFHA_SHARE_MIN, "sfha_share": round(share, 2)})
    return {"artifact_type": "terragauge_full_grid", "bbox": BBOX, "cell_km": 1, "sfha_share_min": SFHA_SHARE_MIN,
            "method": "FEMA zone from a 5x5 grid of points in each square; high-risk if at least 25% of the square is in the 1% (SFHA) zone.", "cells": cells}


def layers() -> None:
    spec = importlib.util.spec_from_file_location("raster_layers", ROOT / "backend/ingestion/raster_layers.py")
    rl = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rl)  # type: ignore[union-attr]
    raw = ROOT / "data" / "raw" / "nasa_layers"
    out = DERIVED / "nasa_layers"
    nasadem = []
    for path in sorted((raw / "nasadem").glob("*.zip")):
        with zipfile.ZipFile(path) as archive:
            nasadem += [f"/vsizip/{path}/{name}" for name in archive.namelist() if name.endswith(".hgt")]
    jobs = {"nasadem": nasadem, "dswx": sorted(str(p) for p in (raw / "dswx").glob("*_B01_WTR.tif")), "dist": sorted(str(p) for p in (raw / "dist").glob("*VEG-DIST-STATUS.tif"))}
    for kind, files in jobs.items():
        if not files:
            print(f"{kind}: no raw files, skipped")
            continue
        old = out / f"{kind}_houston_cells.json"
        extra = {k: v for k, v in json.loads(old.read_text(encoding="utf-8")).items() if k in ("granules", "date", "granule_count")} if old.is_file() else {}
        art = rl.write_layer(files, OUT, kind, old, {**extra, "grid": "full 1 km study grid"})
        print(f"{kind}: {len(art['cells'])} squares")


def main() -> None:
    if "--layers" in sys.argv:
        layers()
        return
    grid = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(grid, separators=(",", ":")), encoding="utf-8")
    zoned = sum(1 for c in grid["cells"] if c["flood_zone"])
    print(f"{len(grid['cells'])} squares, {zoned} with a FEMA zone -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

"""Check TerraGauge's flood view against where Hurricane Harvey really flooded.

Uses the USGS data release "Flood inundation geospatial data for the August
and September 2017 flood event in Texas" (Garvin, 2018, doi:10.5066/F7VH5N3N,
ScienceBase item 5a85f30fe4b00f54eb36d3a9). Put any of these basin zips in
data/raw/harvey/ (the depth zips are optional and large):

    San_Jacinto.zip   (+ Depth_San_Jacinto.zip)    north and northeast Houston
    Brazos_upper.zip  (+ Depth_Brazos_upper.zip)   Richmond, Sugar Land, Fort Bend
    Brazos_lower.zip  (+ Depth_Brazos_lower.zip)   near the coast (mostly south of the map)

then run  python3 scripts/build_harvey.py   (needs pyshp, shapely, pyproj;
rasterio + numpy for depth). Writes data/derived/provisional/harvey_check.json:
for every TerraGauge square inside a mapped area, how much of it flooded
(25 sample points) and how deep, compared with its FEMA flood class.
Depth per basin is cached in harvey_depth_<basin>.json, so the multi-GB
rasters only need unzipping once.
"""
from __future__ import annotations

import json
import os
import re
import zipfile
from math import atan, degrees, exp, pi
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "harvey"
PROV = ROOT / "data" / "derived" / "provisional"
CELLS = ROOT / "web" / "public" / "data" / "cells.json"
OUT = PROV / "harvey_check.json"
R = 6378137.0
STEPS = [0.1, 0.3, 0.5, 0.7, 0.9]
# (folder / zip name, shapefile prefix, depth raster inside Depth_<folder>.zip, area name)
BASINS = [
    ("San_Jacinto", "sj", "sj_depth.tif", "north and northeast Houston (San Jacinto River)"),
    ("Brazos_upper", "brazos_upper", "brazos_upper_depth.tif", "Richmond, Sugar Land and Fort Bend County (Brazos River)"),
    ("Brazos_lower", "brazos_lower", "brazos_lower_depth.tif", "the lower Brazos River near the coast"),
]


def flood_class(zone, sub, sfha):
    if sfha:
        return "1pct"
    if zone == "X" and sub and ("0.2 PCT" in sub or "1 PCT" in sub or "LEVEE" in sub):
        return "0.2pct"
    if zone == "X":
        return "minimal"
    return None


def corner_lonlat(cid: str, a: float, b: float) -> tuple[float, float]:
    m = re.search(r"(-?\d+)-(-?\d+)$", cid)
    i, j = int(m.group(1)), int(m.group(2))
    return degrees((i + a) * 1000 / R), degrees(2 * atan(exp((j + b) * 1000 / R)) - pi / 2)


def basin_depth(name: str, raster_name: str, ids: list[str]) -> dict[str, float]:
    """Mean flood depth (ft) over the flooded part of each square, read at 20 m.
    Uses the cache if present; otherwise needs the unzipped raster (set
    TERRAGAUGE_HARVEY_DEPTH_DIR to where Depth_<basin>/ was unzipped)."""
    cache = PROV / f"harvey_depth_{name}.json"
    base = Path(os.environ.get("TERRAGAUGE_HARVEY_DEPTH_DIR", RAW))
    path = base / f"Depth_{name}" / raster_name
    if not path.is_file():
        return json.loads(cache.read_text(encoding="utf-8")) if cache.is_file() else {}
    import numpy as np
    import rasterio
    from pyproj import Transformer

    step = 10
    with rasterio.open(path) as src:
        h, w = src.height // step, src.width // step
        data = src.read(1, out_shape=(h, w))
        t = src.transform * src.transform.scale(src.width / w, src.height / h)
        to_src = Transformer.from_crs("EPSG:4326", src.crs, always_xy=True)
    valid = np.isfinite(data) & (data > 0) & (data < 100)
    inv = ~t
    out = {}
    for cid in ids:
        xs, ys = [], []
        for a in (0, 1):
            for b in (0, 1):
                cx, cy = inv * to_src.transform(*corner_lonlat(cid, a, b))
                xs.append(cx); ys.append(cy)
        c0, c1 = max(int(min(xs)), 0), min(int(max(xs)) + 1, w)
        r0, r1 = max(int(min(ys)), 0), min(int(max(ys)) + 1, h)
        if c0 < c1 and r0 < r1:
            ok = valid[r0:r1, c0:c1]
            if ok.sum() >= 5:
                out[cid] = round(float(data[r0:r1, c0:c1][ok].mean()), 2)
    cache.write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
    return out


def main() -> None:
    import shapefile
    from pyproj import Transformer
    from shapely.geometry import Point, shape
    from shapely.prepared import prep

    cells = json.loads(CELLS.read_text(encoding="utf-8"))
    by_id = {c["id"]: c for c in cells}
    found, results, marks, areas = [], {}, [], []
    for name, prefix, raster, area in BASINS:
        folder = RAW / name
        if not folder.is_dir():
            if not (RAW / f"{name}.zip").is_file():
                continue
            with zipfile.ZipFile(RAW / f"{name}.zip") as z:
                z.extractall(RAW)
        read = lambda n: shapefile.Reader(str(folder / f"{prefix}_{n}"))  # noqa: E731
        flooded = prep(shape(read("final").shape(0).__geo_interface__).buffer(0))
        bound = prep(shape(read("bndy").shape(0).__geo_interface__).buffer(0))
        prj = (folder / f"{prefix}_final.prj").read_text()
        to_albers = Transformer.from_crs("EPSG:4326", prj, always_xy=True)
        bx = read("bndy").bbox
        to_ll = Transformer.from_crs(prj, "EPSG:4326", always_xy=True)
        (w_, s_), (e_, n_) = to_ll.transform(bx[0], bx[1]), to_ll.transform(bx[2], bx[3])
        ids = []
        for c in cells:
            if not (w_ - 0.02 <= c["lon"] <= e_ + 0.02 and s_ - 0.02 <= c["lat"] <= n_ + 0.02):
                continue
            pts = [Point(*to_albers.transform(*corner_lonlat(c["id"], a, b))) for a in STEPS for b in STEPS]
            inside = [p for p in pts if bound.contains(p)]
            if len(inside) < 13:
                continue
            wet = sum(1 for p in inside if flooded.contains(p)) / len(inside)
            prev = results.get(c["id"])
            results[c["id"]] = {"wet": max(wet, prev["wet"]) if prev else wet, "depth": prev["depth"] if prev else None}
            ids.append(c["id"])
        depth = basin_depth(name, raster, ids)
        for cid in ids:
            if cid in depth and (results[cid]["depth"] is None or depth[cid] > results[cid]["depth"]):
                results[cid]["depth"] = depth[cid]
        for rec in read("hwm").records():
            d = rec.as_dict()
            marks.append({"lon": d.get("longitude_"), "lat": d.get("latitude_d"), "ft": d.get("height_abo"), "name": d.get("descriptio")})
        if ids:
            found.append(name)
            areas.append(area)
        print(f"{name}: {len(ids)} squares, depth for {sum(1 for i in ids if i in depth)}")

    rows = []
    for cid, v in results.items():
        c = by_id[cid]
        f = c["flood"]
        rows.append({"id": cid, "wet": round(v["wet"], 2), "depth_ft": v["depth"], "cls": flood_class(f["zone"], f["sub"], f["sfha"]), "rate": c["rate"], "act": c["act"]})

    def summary(sub):
        if not sub:
            return None
        return {"squares": len(sub), "flooded_pct": round(100 * sum(r["wet"] >= 0.1 for r in sub) / len(sub), 1),
                "mean_flooded_share_pct": round(100 * sum(r["wet"] for r in sub) / len(sub), 1)}

    def depth_summary(sub):
        ds = sorted(r["depth_ft"] for r in sub if r["depth_ft"] is not None)
        return {"squares": len(ds), "median_depth_ft": round(ds[len(ds) // 2], 2)} if ds else None

    classes = ("1pct", "0.2pct", "minimal")
    land = [r for r in rows if r["cls"]]
    wet_total = sum(r["wet"] for r in land)
    measured = [r for r in land if r["rate"] is not None and r["act"] != "insufficient_data"]
    out = {
        "source": "USGS, Garvin (2018), Flood inundation geospatial data for the August and September 2017 flood event in Texas. doi:10.5066/F7VH5N3N",
        "basins": found, "areas": areas, "squares": len(rows),
        "by_class": {k: summary([r for r in rows if r["cls"] == k]) for k in classes},
        "depth_by_class": {k: depth_summary([r for r in rows if r["cls"] == k]) for k in classes},
        "flooded_area_outside_high_risk_pct": round(100 * sum(r["wet"] for r in land if r["cls"] != "1pct") / wet_total, 1) if wet_total else None,
        "by_sinking": {
            "fast": summary([r for r in measured if r["rate"] <= -10]),
            "slow": summary([r for r in measured if -10 < r["rate"] <= -3]),
            "stable": summary([r for r in measured if r["rate"] > -3]),
        },
        "high_water_marks": len(marks),
        "cells": {r["id"]: [r["wet"], r["depth_ft"]] for r in rows},
        "marks": marks,
    }
    OUT.write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k not in ("cells", "marks")}, indent=1))


if __name__ == "__main__":
    main()

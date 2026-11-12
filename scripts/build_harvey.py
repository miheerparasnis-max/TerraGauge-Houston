"""Check TerraGauge's flood view against where Hurricane Harvey really flooded.

Uses the USGS data release "Flood inundation geospatial data for the August
and September 2017 flood event in Texas" (Garvin, 2018, doi:10.5066/F7VH5N3N),
San Jacinto River basin: the mapped boundary, the flooded-area polygon and the
surveyed high-water marks. Download San_Jacinto.zip from ScienceBase into
data/raw/harvey/ (see README), then run:

    python3 scripts/build_harvey.py      # needs pyshp, shapely, pyproj

Writes data/derived/provisional/harvey_check.json. For every TerraGauge square
inside the mapped area it records how much of the square flooded (25 sample
points), then compares that with the square's FEMA flood class and sinking.
"""
from __future__ import annotations

import json
import os
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "harvey"
CELLS = ROOT / "web" / "public" / "data" / "cells.json"
OUT = ROOT / "data" / "derived" / "provisional" / "harvey_check.json"
R = 6378137.0
STEPS = [0.1, 0.3, 0.5, 0.7, 0.9]


def flood_class(zone, sub, sfha):
    if sfha:
        return "1pct"
    if zone == "X" and sub and ("0.2 PCT" in sub or "1 PCT" in sub or "LEVEE" in sub):
        return "0.2pct"
    if zone == "X":
        return "minimal"
    return None


def harvey_depth(rows: list[dict]) -> dict[str, float]:
    """Mean flood depth (ft) over the flooded part of each square, from the
    USGS 2 m depth raster (Depth_San_Jacinto.zip, ~7 GB unzipped). Set
    TERRAGAUGE_HARVEY_DEPTH to the unzipped sj_depth.tif; skipped if absent.
    The raster is read at 20 m (every 10th pixel), plenty for 1 km squares."""
    import re
    from math import atan, degrees, exp, pi

    path = Path(os.environ.get("TERRAGAUGE_HARVEY_DEPTH", RAW / "Depth_San_Jacinto" / "sj_depth.tif"))
    if not path.is_file():
        print("No Harvey depth raster; skipping depth.")
        return {}
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
    for r in rows:
        m = re.search(r"(-?\d+)-(-?\d+)$", r["id"])
        i, j = int(m.group(1)), int(m.group(2))
        xs, ys = [], []
        for a in (0, 1):
            for b in (0, 1):
                lon = degrees((i + a) * 1000 / R)
                lat = degrees(2 * atan(exp((j + b) * 1000 / R)) - pi / 2)
                x, y = to_src.transform(lon, lat)
                cx, cy = inv * (x, y)
                xs.append(cx); ys.append(cy)
        c0, c1 = max(int(min(xs)), 0), min(int(max(xs)) + 1, w)
        r0, r1 = max(int(min(ys)), 0), min(int(max(ys)) + 1, h)
        if c0 >= c1 or r0 >= r1:
            continue
        block, ok = data[r0:r1, c0:c1], valid[r0:r1, c0:c1]
        if ok.sum() >= 5:
            out[r["id"]] = round(float(block[ok].mean()), 2)
    return out


def main() -> None:
    import re
    from math import atan, degrees, exp, pi

    import shapefile
    from pyproj import Transformer
    from shapely.geometry import Point, shape
    from shapely.prepared import prep

    folder = RAW / "San_Jacinto"
    if not folder.is_dir():
        with zipfile.ZipFile(RAW / "San_Jacinto.zip") as z:
            z.extractall(RAW)
    read = lambda n: shapefile.Reader(str(folder / n))  # noqa: E731
    flooded = prep(shape(read("sj_final").shape(0).__geo_interface__).buffer(0))
    bound_geom = shape(read("sj_bndy").shape(0).__geo_interface__).buffer(0)
    bound = prep(bound_geom)
    prj = (folder / "sj_final.prj").read_text()
    to_albers = Transformer.from_crs("EPSG:4326", prj, always_xy=True)
    to_ll = Transformer.from_crs(prj, "EPSG:4326", always_xy=True)

    cells = json.loads(CELLS.read_text(encoding="utf-8"))
    rows = []
    for c in cells:
        m = re.search(r"(-?\d+)-(-?\d+)$", c["id"])
        i, j = int(m.group(1)), int(m.group(2))
        pts = []
        for a in STEPS:
            for b in STEPS:
                lon = degrees((i + a) * 1000 / R)
                lat = degrees(2 * atan(exp((j + b) * 1000 / R)) - pi / 2)
                pts.append(Point(*to_albers.transform(lon, lat)))
        inside = [p for p in pts if bound.contains(p)]
        if len(inside) < 13:          # at least half the square inside the mapped area
            continue
        wet = sum(1 for p in inside if flooded.contains(p)) / len(inside)
        f = c["flood"]
        rows.append({"id": c["id"], "wet": round(wet, 2), "cls": flood_class(f["zone"], f["sub"], f["sfha"]),
                     "rate": c["rate"], "act": c["act"], "src": c["src"]})

    def summary(sub):
        if not sub:
            return None
        return {"squares": len(sub), "flooded_pct": round(100 * sum(r["wet"] >= 0.1 for r in sub) / len(sub), 1),
                "mean_flooded_share_pct": round(100 * sum(r["wet"] for r in sub) / len(sub), 1)}

    by_class = {k: summary([r for r in rows if r["cls"] == k]) for k in ("1pct", "0.2pct", "minimal")}
    land = [r for r in rows if r["cls"]]
    wet_total = sum(r["wet"] for r in land)
    outside = sum(r["wet"] for r in land if r["cls"] != "1pct")
    measured = [r for r in land if r["rate"] is not None and r["act"] != "insufficient_data"]
    sinking = {
        "fast": summary([r for r in measured if r["rate"] <= -10]),
        "slow": summary([r for r in measured if -10 < r["rate"] <= -3]),
        "stable": summary([r for r in measured if r["rate"] > -3]),
        "fast_in_1pct": summary([r for r in measured if r["rate"] <= -10 and r["cls"] == "1pct"]),
        "stable_in_1pct": summary([r for r in measured if r["rate"] > -3 and r["cls"] == "1pct"]),
    }
    depth = harvey_depth(rows)
    for r in rows:
        r["depth_ft"] = depth.get(r["id"])
    deep = [r for r in rows if r.get("depth_ft") is not None]

    def depth_summary(sub):
        sub = [r for r in sub if r.get("depth_ft") is not None]
        if not sub:
            return None
        ds = sorted(r["depth_ft"] for r in sub)
        return {"squares": len(sub), "median_depth_ft": round(ds[len(ds) // 2], 2)}

    depth_by_class = {k: depth_summary([r for r in deep if r["cls"] == k]) for k in ("1pct", "0.2pct", "minimal")}
    hwm = []
    for rec, shp in zip(read("sj_hwm").records(), read("sj_hwm").shapes()):
        d = rec.as_dict()
        hwm.append({"lon": d["longitude_"], "lat": d["latitude_d"], "ft": d["height_abo"], "name": d["descriptio"]})
    b = bound_geom.bounds
    corners = [to_ll.transform(x, y) for x, y in ((b[0], b[1]), (b[2], b[3]))]
    out = {
        "source": "USGS, Garvin (2018), Flood inundation geospatial data for the August and September 2017 flood event in Texas, San Jacinto River basin. doi:10.5066/F7VH5N3N",
        "mapped_bbox": [round(corners[0][0], 3), round(corners[0][1], 3), round(corners[1][0], 3), round(corners[1][1], 3)],
        "squares": len(rows), "by_class": by_class,
        "flooded_area_outside_high_risk_pct": round(100 * outside / wet_total, 1) if wet_total else None,
        "by_sinking": sinking, "high_water_marks": len(hwm),
        "depth_by_class": depth_by_class,
        "cells": {r["id"]: [r["wet"], r.get("depth_ft")] for r in rows},
        "marks": hwm,
    }
    OUT.write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k not in ("cells", "marks")}, indent=1))


if __name__ == "__main__":
    main()

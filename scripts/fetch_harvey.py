"""Download USGS high-water marks from Hurricane Harvey (2017) for the Houston area.

These are surveyed flood marks: places that really flooded, and how deep.
scripts/build_hazards.py uses them to check the flood view.
Run from the repo root:  python3 scripts/fetch_harvey.py
"""
from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "raw" / "harvey_usgs_high_water_marks.json"
BASE = "https://stn.wim.usgs.gov/STNServices"
BOX = (-96.2, 29.2, -94.7, 30.4)   # west, south, east, north


def get(url: str):
    with urllib.request.urlopen(urllib.request.Request(url, headers={"Accept": "application/json"}), timeout=120) as r:
        return json.loads(r.read().decode("utf-8"))


def main() -> None:
    try:
        events = get(f"{BASE}/Events.json")
        ids = [e["event_id"] for e in events if "harvey" in (e.get("event_name") or "").lower()]
        if not ids:
            sys.exit("Couldn't find Hurricane Harvey in the USGS event list.")
        marks = []
        for eid in ids:
            marks += get(f"{BASE}/HWMs/FilteredHWMs.json?Event={eid}&States=TX")
    except Exception as exc:  # noqa: BLE001
        sys.exit(f"Download failed ({exc}). Check your internet connection and try again.")
    keep = []
    for m in marks:
        lon, lat = m.get("longitude_dd"), m.get("latitude_dd")
        if lon is None or lat is None or not (BOX[0] <= lon <= BOX[2] and BOX[1] <= lat <= BOX[3]):
            continue
        keep.append({"lon": lon, "lat": lat, "height_above_ground_ft": m.get("height_above_gnd"), "elev_ft": m.get("elev_ft"), "quality": m.get("hwm_quality_id"), "environment": m.get("hwm_environment")})
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"source": f"USGS Flood Event Viewer / STN, events {ids}", "marks": keep}, indent=0), encoding="utf-8")
    print(f"Saved {len(keep)} Harvey high-water marks in the Houston area to {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

"""List the OPERA DISP-S1 frames that cover the part of Houston our frame misses.

Our record uses frame F38238, which stops short of the far south (Pearland,
Alvin, Rosharon, Needville). This only *searches* NASA Earthdata (no big
downloads) and prints each frame that covers that strip, with how many
products it has and their total size, so we can decide whether to add it.

    python3 scripts/find_opera_frames.py
"""
from __future__ import annotations

import re
import sys
from collections import defaultdict

SOUTH = (-95.95, 29.40, -94.80, 29.55)   # the uncovered southern strip


def main() -> None:
    try:
        import earthaccess
    except ImportError:
        sys.exit("Run first:  python3 -m pip install earthaccess")
    auth = earthaccess.login(strategy="interactive", persist=True)
    if not auth or not getattr(auth, "authenticated", False):
        sys.exit("Earthdata login failed. Check your username and password, then try again.")
    granules = earthaccess.search_data(short_name="OPERA_L3_DISP-S1_V1", bounding_box=SOUTH, count=4000)
    frames: dict[str, dict] = defaultdict(lambda: {"n": 0, "mb": 0.0, "first": "9", "last": "0"})
    for g in granules:
        name = g["umm"]["GranuleUR"]
        m = re.search(r"_F(\d+)_VV_(\d{8})T\d+Z_(\d{8})T", name)
        if not m:
            continue
        f = frames[m.group(1)]
        f["n"] += 1
        f["mb"] += sum(float(s.get("Size", 0)) for s in g["umm"].get("DataGranule", {}).get("ArchiveAndDistributionInformation", []) if s.get("SizeUnit", "MB") == "MB")
        f["first"] = min(f["first"], m.group(2))
        f["last"] = max(f["last"], m.group(3))
    if not frames:
        sys.exit("No OPERA frames found for the southern strip.")
    print("Frames covering south Houston (F38238 is the one we already use):")
    for fid, f in sorted(frames.items(), key=lambda kv: -kv[1]["n"]):
        print(f"  F{fid}: {f['n']} products, about {f['mb'] / 1024:.1f} GB, {f['first']} to {f['last']}")


if __name__ == "__main__":
    main()

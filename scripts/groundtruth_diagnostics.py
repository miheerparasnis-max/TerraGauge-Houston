"""Signal and tracking diagnostics for the GroundTruth sessions (what the receiver actually saw).

For each data/raw/groundtruth/sessionN.rtcm3 this converts the log again with signal strength
kept, then measures:
- seconds recorded, satellite systems, satellites tracked;
- carrier-phase continuity: a one-second step of the L1-L5 (BeiDou B1I-B2a) phase difference
  larger than 5 cm is a real loss of lock, independent of the receiver's own lock flags;
- how many satellites were in an unbroken phase arc of at least 10 minutes at once (median over the session);
- GPS L1 signal strength (C/N0) by direction in the sky, from RTKLIB single-point azimuths and
  elevations computed with the GPS broadcast orbits already fetched by process_groundtruth.py.

Writes data/derived/groundtruth/groundtruth_diagnostics.json. Directions and signal strengths
only: no position, height or location leaves this script.

    python3 scripts/groundtruth_diagnostics.py
"""
from __future__ import annotations

import collections
import json
import re
import statistics as st
import subprocess
from datetime import datetime
from pathlib import Path

import process_groundtruth as pg

C = 299792458.0
# (phase A, freq A, phase B, freq B) per system for the continuity check
PAIRS = {"G": ("L1C", 1575.42e6, "L5Q", 1176.45e6), "E": ("L1C", 1575.42e6, "L5Q", 1176.45e6), "C": ("L2I", 1561.098e6, "L5P", 1176.45e6)}
SYSTEMS = {"G": "GPS", "R": "GLONASS", "E": "Galileo", "C": "BeiDou"}
SLIP_M = 0.05
ARC_S = 600  # a satellite is usable for precise positioning only after minutes of unbroken phase
CLEAR_SKY_DBHZ = 40
SECTORS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
OUT_JSON = pg.OUT / "groundtruth_diagnostics.json"


def convert(n: int) -> Path:
    raw = pg.RAW / f"session{n}.rtcm3"
    start = datetime.strptime((pg.RAW / f"session{n}.start.txt").read_text(encoding="utf-8").split()[2], "%Y-%m-%dT%H:%M:%SZ")
    obs = pg.OUT / f"session{n}_snr.obs"
    subprocess.run([str(pg.CONVBIN), "-r", "rtcm3", "-tr", start.strftime("%Y/%m/%d"), start.strftime("%H:%M:%S"), "-v", "3.04", "-os", "-o", str(obs), str(raw)], check=True, capture_output=True)
    return obs


def tracking(obs: Path) -> dict:
    lines = obs.read_text(encoding="ascii", errors="replace").splitlines()
    end = next(i for i, line in enumerate(lines) if "END OF HEADER" in line)
    types = {line[0]: line[7:58].split() for line in lines[:end] if "SYS / # / OBS TYPES" in line}
    prev: dict[str, tuple[int, float]] = {}
    arc_start: dict[str, int] = {}
    arcs: list[tuple[int, int]] = []
    steps, slips = 0, 0
    sats: set[str] = set()
    epoch = -1

    def close(sat: str) -> None:
        if sat in arc_start and sat in prev:
            arcs.append((arc_start.pop(sat), prev[sat][0]))

    for line in lines[end + 1:]:
        if line.startswith(">"):
            epoch += 1
            continue
        sys_ = line[:1]
        if sys_ not in SYSTEMS:
            continue
        sats.add(line[:3])
        if sys_ not in PAIRS:
            continue
        a, fa, b, fb = PAIRS[sys_]
        t = types[sys_]

        def val(name: str) -> float | None:
            if name not in t:
                return None
            j = t.index(name)
            text = line[3 + 16 * j:3 + 16 * j + 14].strip()
            return float(text) if text else None

        la, lb = val(a), val(b)
        sat = line[:3]
        if la is None or lb is None:
            close(sat)
            prev.pop(sat, None)
            continue
        gf = C / fa * la - C / fb * lb
        if sat in prev and prev[sat][0] == epoch - 1:
            steps += 1
            if abs(gf - prev[sat][1]) > SLIP_M:
                slips += 1
                close(sat)
        else:
            close(sat)
        arc_start.setdefault(sat, epoch)
        prev[sat] = (epoch, gf)
    for sat in list(arc_start):
        close(sat)
    usable = [0] * (epoch + 1)
    for a, b in arcs:
        if b - a + 1 >= ARC_S:
            for e in range(a, b + 1):
                usable[e] += 1
    return {"seconds": epoch + 1, "systems": sorted(SYSTEMS[s] for s in {x[0] for x in sats}), "satellites_tracked": len(sats),
            "steady_satellites_median": st.median(usable), "phase_break_share": round(slips / steps, 3) if steps else None}


def sky(obs: Path, n: int) -> dict:
    """GPS L1 C/N0 by direction (elevation 15 deg or more) and for high satellites (60 deg or more)."""
    nav = sorted(pg.CORS_DIR.glob("brdc*.??n"))
    if not nav:
        raise SystemExit("No GPS broadcast orbits cached; run scripts/process_groundtruth.py first.")
    cfg = pg.OUT / f"session{n}_single.conf"
    cfg.write_text("pos1-posmode       =single\npos1-elmask        =0\npos1-navsys        =1\nout-outstat        =residual\n", encoding="ascii")
    pos = pg.OUT / f"session{n}_single.pos"
    subprocess.run([str(pg.RNX2RTKP), "-k", str(cfg), "-o", str(pos), str(obs), *map(str, nav)], check=True, capture_output=True)
    by_dir: dict[str, list[float]] = collections.defaultdict(list)
    high: list[float] = []
    for line in Path(f"{pos}.stat").read_text(encoding="ascii", errors="replace").splitlines():
        if not line.startswith("$SAT"):
            continue
        f = line.split(",")
        if not f[3].startswith("G") or f[4] != "1":
            continue
        az, el, snr = float(f[5]), float(f[6]), float(f[10])
        if snr <= 0 or el < 15:
            continue
        by_dir[SECTORS[int(((az + 22.5) % 360) // 45)]].append(snr)
        if el >= 60:
            high.append(snr)
    return {"gps_l1_cn0_by_direction": {s: round(st.median(by_dir[s])) if by_dir[s] else None for s in SECTORS},
            "gps_l1_cn0_high": round(st.median(high)) if high else None}


def main() -> None:
    sessions = []
    for raw in sorted(pg.RAW.glob("session*.rtcm3")):
        m = re.fullmatch(r"session(\d+)\.rtcm3", raw.name)
        if not m:
            continue
        n = int(m.group(1))
        obs = convert(n)
        sessions.append({"session_id": f"session{n}", **tracking(obs), **sky(obs, n)})
        print(sessions[-1])
    OUT_JSON.write_text(json.dumps({
        "artifact_type": "groundtruth_signal_diagnostics",
        "method": f"Carrier-phase break: one-second step of the dual-frequency phase difference over {SLIP_M * 100:.0f} cm. "
                  f"Steady satellites: GPS, Galileo and BeiDou satellites inside an unbroken phase arc of {ARC_S // 60} minutes or more at that second. "
                  f"Signal strength: median GPS L1 C/N0 per direction at elevation 15 deg or more; about {CLEAR_SKY_DBHZ} dB-Hz or more is typical of open sky.",
        "clear_sky_dbhz": CLEAR_SKY_DBHZ,
        "sessions": sessions,
        "privacy": "Directions and signal strengths only; no position or height.",
    }, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

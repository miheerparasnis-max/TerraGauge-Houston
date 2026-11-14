"""Process GroundTruth Node sessions: RTCM3 log -> RINEX -> static solution against NOAA CORS NETP.

For each data/raw/groundtruth/sessionN.rtcm3 (with sessionN.start.txt from the capture):
1. RTKLIB convbin converts the log to RINEX 3 (data/derived/groundtruth/sessionN.obs);
2. NETP observations covering the session (hourly files, or the daily file) and the GPS
   broadcast orbits are fetched from NOAA's open-data bucket (noaa-cors-pds; no login);
3. RTKLIB rnx2rtkp computes a static GPS L1+L5 solution relative to NETP, whose
   ITRF2020 coordinate is carried from epoch 2020.0 to the session date with NOAA's velocity;
4. the session's ellipsoidal height goes into data/groundtruth_session_manifest.json, and
   backend.ingestion.cli groundtruth-report computes the session-to-session scatter.

Privacy: RINEX headers and solutions contain the antenna's location, so .obs/.pos files stay
out of git (see .gitignore) and the manifest records heights and checksums only, never
latitude or longitude. The result is fixed-antenna repeatability, never land motion.

    python3 scripts/process_groundtruth.py               # every session with a raw log
    python3 scripts/process_groundtruth.py 1 2           # selected sessions
Needs RTKLIB built in ~/tools/RTKLIB (override with RTKLIB=/path).
"""
from __future__ import annotations

import gzip
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "groundtruth"
OUT = ROOT / "data" / "derived" / "groundtruth"
CORS_DIR = RAW / "cors"
MANIFEST = ROOT / "data" / "groundtruth_session_manifest.json"
REPORT = OUT / "groundtruth_report.json"
RTKLIB = Path(os.environ.get("RTKLIB", Path.home() / "tools" / "RTKLIB"))
CONVBIN = RTKLIB / "app/consapp/convbin/gcc/convbin"
RNX2RTKP = RTKLIB / "app/consapp/rnx2rtkp/gcc/rnx2rtkp"
BUCKET = "https://noaa-cors-pds.s3.amazonaws.com"
STATION = "netp"
ELEV_MASK_DEG = 15

# NETP ARP, ITRF2020 epoch 2020.0, and velocity (NOAA coord/coord_20/netp_20.coord.txt, retrieved 2026-11-14).
NETP_XYZ = (-515007.955, -5515795.306, 3150298.442)
NETP_VEL = (-0.0118, 0.0010, -0.0041)
NETP_EPOCH = 2020.0


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def fetch(key: str, dest: Path) -> Path | None:
    """Download one object from NOAA's CORS bucket; gunzip it. None if not posted yet."""
    plain = dest.with_suffix("") if dest.suffix == ".gz" else dest
    if plain.is_file() and plain.stat().st_size:
        return plain
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        with urllib.request.urlopen(urllib.request.Request(f"{BUCKET}/{key}", headers={"User-Agent": "terragauge-groundtruth"}), timeout=120) as r:
            data = r.read()
    except Exception:  # noqa: BLE001 - not posted yet, or offline
        return None
    plain.write_bytes(gzip.decompress(data) if key.endswith(".gz") else data)
    return plain


def decimal_year(t: datetime) -> float:
    start = datetime(t.year, 1, 1, tzinfo=timezone.utc)
    return t.year + (t - start).total_seconds() / (datetime(t.year + 1, 1, 1, tzinfo=timezone.utc) - start).total_seconds()


def netp_at(t: datetime) -> tuple[float, float, float]:
    dt = decimal_year(t) - NETP_EPOCH
    return tuple(p + v * dt for p, v in zip(NETP_XYZ, NETP_VEL))


def ecef_to_height(x: float, y: float, z: float) -> float:
    a, e2 = 6378137.0, 6.69437999014e-3
    p = math.hypot(x, y)
    lat = math.atan2(z, p * (1 - e2))
    h = 0.0
    for _ in range(8):
        n = a / math.sqrt(1 - e2 * math.sin(lat) ** 2)
        h = p / math.cos(lat) - n
        lat = math.atan2(z, p * (1 - e2 * n / (n + h)))
    return h


def merge_rinex2(parts: list[Path], dest: Path) -> Path:
    """Concatenate hourly RINEX 2 observation files: first header, then every file's data."""
    lines: list[str] = []
    for n, part in enumerate(parts):
        text = part.read_text(encoding="ascii", errors="replace").splitlines(keepends=True)
        end = next(i for i, line in enumerate(text) if "END OF HEADER" in line)
        lines.extend(text if n == 0 else text[end + 1:])
    dest.write_text("".join(lines), encoding="ascii")
    return dest


def cors_files(t0: datetime, t1: datetime) -> tuple[Path, list[Path]]:
    """NETP observations covering [t0, t1] and the GPS broadcast navigation for those days."""
    hours, t = [], t0.replace(minute=0, second=0, microsecond=0)
    while t <= t1:
        hours.append(t)
        t += timedelta(hours=1)
    days = sorted({(h.year, h.timetuple().tm_yday) for h in hours})
    nav = []
    for year, doy in days:
        f = fetch(f"rinex/{year}/{doy:03d}/brdc{doy:03d}0.{year % 100:02d}n.gz", CORS_DIR / f"brdc{doy:03d}0.{year % 100:02d}n.gz")
        if f is None:
            sys.exit(f"GPS broadcast orbits for {year}-{doy:03d} are not posted yet; try again later.")
        nav.append(f)
    if len(days) == 1:
        year, doy = days[0]
        daily = fetch(f"rinex/{year}/{doy:03d}/{STATION}/{STATION}{doy:03d}0.{year % 100:02d}o.gz", CORS_DIR / f"{STATION}{doy:03d}0.{year % 100:02d}o.gz")
        if daily:
            return daily, nav
    parts = []
    for h in hours:
        doy, letter = h.timetuple().tm_yday, "abcdefghijklmnopqrstuvwx"[h.hour]
        name = f"{STATION}{doy:03d}{letter}.{h.year % 100:02d}o"
        part = fetch(f"rinex/{h.year}/{doy:03d}/{STATION}/{name}.gz", CORS_DIR / f"{name}.gz")
        if part is None:
            sys.exit(f"NOAA has not posted {name} yet (hourly files arrive in batches, the daily file about 6 h after midnight UTC). Try again later.")
        parts.append(part)
    return merge_rinex2(parts, CORS_DIR / f"{STATION}_{t0:%Y%j%H}_{t1:%H}.obs"), nav


def obs_window(obs: Path) -> tuple[datetime, datetime, int]:
    epochs = [line for line in obs.read_text(encoding="ascii", errors="replace").splitlines() if line.startswith(">")]
    stamp = lambda line: datetime(*(int(float(v)) for v in line[1:].split()[:6]), tzinfo=timezone.utc)  # noqa: E731
    return stamp(epochs[0]), stamp(epochs[-1]), len(epochs)


def config(base: tuple[float, float, float], path: Path) -> Path:
    path.write_text("\n".join([
        "pos1-posmode       =static",
        "pos1-frequency     =l1+l2+l5",   # L2 slot unused by the rover; L1 + L5 are common to both receivers
        f"pos1-elmask        ={ELEV_MASK_DEG}",
        "pos1-navsys        =1",          # GPS: NOAA's broadcast file is GPS-only
        "pos1-ionoopt       =brdc",
        "pos1-tropopt       =saas",
        "pos2-armode        =continuous",
        "pos2-arthres       =3",
        "out-solformat      =xyz",
        "out-outstat        =residual",
        "ant2-postype       =xyz",
        f"ant2-pos1          ={base[0]:.4f}",
        f"ant2-pos2          ={base[1]:.4f}",
        f"ant2-pos3          ={base[2]:.4f}",
        "",
    ]), encoding="ascii")
    return path


def final_solution(pos: Path) -> dict:
    rows = [line.split() for line in pos.read_text(encoding="ascii", errors="replace").splitlines() if line and not line.startswith("%")]
    if not rows:
        raise ValueError(f"{pos.name}: no solution epochs")
    last = rows[-1]
    x, y, z, q = float(last[2]), float(last[3]), float(last[4]), int(last[5])
    fixed = sum(1 for r in rows if r[5] == "1")
    sdx, sdy, sdz = (float(v) for v in last[7:10])
    return {"height_mm": round(ecef_to_height(x, y, z) * 1000, 1), "quality": {1: "fixed", 2: "float"}.get(q, f"q{q}"),
            "fixed_epoch_share": round(fixed / len(rows), 3), "epochs": len(rows), "sigma_3d_mm": round(math.sqrt(sdx ** 2 + sdy ** 2 + sdz ** 2) * 1000, 1)}


def process(n: int) -> dict:
    raw = RAW / f"session{n}.rtcm3"
    start_line = (RAW / f"session{n}.start.txt").read_text(encoding="utf-8").split()
    start = datetime.strptime(start_line[2], "%Y-%m-%dT%H:%M:%SZ")
    OUT.mkdir(parents=True, exist_ok=True)
    obs = OUT / f"session{n}.obs"
    subprocess.run([str(CONVBIN), "-r", "rtcm3", "-tr", start.strftime("%Y/%m/%d"), start.strftime("%H:%M:%S"), "-v", "3.04", "-o", str(obs), str(raw)],
                   check=True, capture_output=True)
    t0, t1, epochs = obs_window(obs)
    base_obs, nav = cors_files(t0, t1)
    cfg = config(netp_at(t0), OUT / f"session{n}.conf")
    pos = OUT / f"session{n}.pos"
    subprocess.run([str(RNX2RTKP), "-k", str(cfg), "-o", str(pos), str(obs), str(base_obs), *map(str, nav)], check=True, capture_output=True)
    sol = final_solution(pos)
    hours = (t1 - t0).total_seconds() / 3600
    print(f"session {n}: {t0:%H:%M}-{t1:%H:%M} UTC ({hours:.2f} h, {epochs} epochs), {sol['quality']}, "
          f"fixed share {sol['fixed_epoch_share']:.0%}, sigma {sol['sigma_3d_mm']} mm")
    return {
        "session_id": f"session{n}",
        "raw_observation_log": str(raw.relative_to(ROOT)),
        "raw_sha256": sha256(raw),
        "rinex_observation_file": str(obs.relative_to(ROOT)),
        "rinex_sha256": sha256(obs),
        "static_solution_height_mm": sol["height_mm"],
        "solution": {k: v for k, v in sol.items() if k != "height_mm"},
        "window_utc": [f"{t0:%Y-%m-%dT%H:%M:%SZ}", f"{t1:%Y-%m-%dT%H:%M:%SZ}"],
        "session_hours": round(hours, 2),
        "antenna_fixed": True,
        "cors_station": STATION.upper(),
        "cors_files": [p.name for p in [base_obs, *nav]],
        "cors_overlap": True,
        "processing": f"RTKLIB rnx2rtkp static, GPS L1+L5, elevation mask {ELEV_MASK_DEG} deg, broadcast orbits, base NETP ITRF2020 propagated to the session date",
    }


def main() -> None:
    for tool in (CONVBIN, RNX2RTKP):
        if not tool.is_file():
            sys.exit(f"Missing {tool}. Build RTKLIB first (see the README).")
    wanted = [int(a) for a in sys.argv[1:]] or sorted(int(m.group(1)) for p in RAW.glob("session*.rtcm3") if (m := re.fullmatch(r"session(\d+)\.rtcm3", p.name)))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.is_file() else {"purpose": "GroundTruth Node stationary-repeatability validation. Heights are ellipsoidal (ITRF2020 via NETP); location is withheld for privacy.", "sessions": []}
    by_id = {s["session_id"]: s for s in manifest["sessions"]}
    for n in wanted:
        by_id[f"session{n}"] = process(n)
    manifest["sessions"] = [by_id[k] for k in sorted(by_id)]
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    subprocess.run([sys.executable, "-m", "backend.ingestion.cli", "groundtruth-report", str(MANIFEST), str(REPORT)], check=True, cwd=ROOT)
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    scatter = report.get("vertical_session_scatter_mm")
    print(f"report: pass={report['pass']} sessions={report['session_count']}" + (f" vertical scatter {scatter:.1f} mm" if scatter is not None else ""))


if __name__ == "__main__":
    main()

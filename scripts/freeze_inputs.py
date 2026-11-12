"""Freeze (or check) the SHA-256 of every git-tracked file under data/derived/.

MASTER section 19 risk "data changes after snapshot": every published number must
be reproducible from frozen inputs. Write a freeze at each checkpoint, then use
--check before building any output.

    python3 scripts/freeze_inputs.py --out data/manifests/input_freeze_YYYY-MM-DD.json
    python3 scripts/freeze_inputs.py --check data/manifests/input_freeze_YYYY-MM-DD.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def tracked_files(prefix: str = "data/derived") -> list[str]:
    output = subprocess.run(["git", "ls-files", prefix], cwd=ROOT, check=True, capture_output=True, text=True).stdout
    return sorted(line for line in output.splitlines() if line)


def current_hashes(paths: list[str]) -> dict[str, str | None]:
    return {path: sha256(ROOT / path) if (ROOT / path).is_file() else None for path in paths}


def diff_freeze(recorded: dict[str, str], current: dict[str, str | None]) -> dict[str, list[str]]:
    """Compare a recorded freeze with current hashes; any non-empty list is a failure."""
    return {
        "changed": sorted(p for p in recorded if p in current and current[p] is not None and current[p] != recorded[p]),
        "missing": sorted(p for p in recorded if current.get(p) is None),
        "added": sorted(p for p in current if p not in recorded and current[p] is not None),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--out")
    group.add_argument("--check")
    args = parser.parse_args()
    paths = tracked_files()
    if args.out:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()
        hashes = current_hashes(paths)
        payload = {
            "artifact_type": "terragauge_input_freeze",
            "created_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "git_head_at_freeze": commit,
            "scope": "git-tracked files under data/derived/",
            "file_count": len(hashes),
            "sha256": hashes,
            "limitations": ["Gitignored regenerable intermediates (data/derived/provisional/*) are not frozen here; outputs must not depend on them without their own manifest (audit A11)."],
        }
        Path(args.out).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print(f"froze {len(hashes)} files at {commit[:7]}")
        return
    recorded = json.loads(Path(args.check).read_text(encoding="utf-8"))["sha256"]
    result = diff_freeze(recorded, current_hashes(sorted(set(paths) | set(recorded))))
    print(json.dumps(result, indent=1))
    sys.exit(1 if any(result.values()) else 0)


if __name__ == "__main__":
    main()

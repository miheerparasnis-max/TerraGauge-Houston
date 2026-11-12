"""Record what a build read and wrote, with SHA-256 hashes (MASTER section 0, rule 3).

Every number in a published output must trace to an artifact with a manifest
entry. A build creates a `ProvenanceLog`, calls `read()` for each input and
`wrote()` for each output, then `write()`s the manifest. Inputs that git does not
track (regenerable intermediates) carry the command that regenerates them.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _git(root: Path, *args: str) -> str | None:
    try:
        return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return None


class ProvenanceLog:
    def __init__(self, root: str | Path, tracked: set[str] | None = None, regenerate: dict[str, str] | None = None):
        self.root = Path(root).resolve()
        if tracked is None:
            listing = _git(self.root, "ls-files")
            tracked = set(listing.splitlines()) if listing else set()
        self.tracked = tracked
        self.regenerate = regenerate or {}
        self._inputs: dict[str, dict[str, Any]] = {}
        self._outputs: dict[str, Path] = {}

    def _relative(self, path: str | Path) -> str:
        resolved = Path(path).resolve()
        try:
            return resolved.relative_to(self.root).as_posix()
        except ValueError:
            return resolved.as_posix()

    def _row(self, relative: str, digest: str) -> dict[str, Any]:
        row: dict[str, Any] = {"path": relative, "sha256": digest, "tracked": relative in self.tracked}
        if not row["tracked"] and relative in self.regenerate:
            row["regenerate_with"] = self.regenerate[relative]
        return row

    def read(self, path: str | Path) -> None:
        """Hash an input at the moment it is read."""
        relative = self._relative(path)
        self._inputs[relative] = self._row(relative, sha256_file(path))

    def wrote(self, path: str | Path) -> None:
        """Register an output; it is hashed when the manifest is written."""
        self._outputs[self._relative(path)] = Path(path)

    def write(self, path: str | Path, *, artifact_type: str, command: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
        head = _git(self.root, "rev-parse", "HEAD")
        status = _git(self.root, "status", "--porcelain", "--untracked-files=no")
        manifest = {
            "artifact_type": artifact_type,
            "created_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "git_head": head.strip() if head else None,
            # False means the build ran with uncommitted changes to tracked files, so git_head alone does not reproduce it.
            "git_worktree_clean": (status.strip() == "") if status is not None else None,
            "command": command,
            "inputs": [self._inputs[key] for key in sorted(self._inputs)],
            "outputs": [self._row(key, sha256_file(self._outputs[key])) for key in sorted(self._outputs)],
            **(extra or {}),
        }
        Path(path).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        return manifest

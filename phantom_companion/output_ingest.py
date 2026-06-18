"""Production writer for developer-output samples from git activity.

This module turns local git history into the ``output-<day>.json`` files that
the existing health/output correlation already knows how to read from the mesh.
It is best-effort by design: missing git, non-git directories, and malformed
numstat rows produce an empty or partial ingest rather than interrupting report
generation.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


def collect_git_output(
    repo: str | os.PathLike[str] | Path,
    days: list[str] | None = None,
) -> dict[str, dict[str, int]]:
    """Collect per-day commit and changed-line counts from ``repo``."""
    cmd = [
        "git",
        "-C",
        str(Path(repo)),
        "log",
        "--no-merges",
        "--numstat",
        "--date=short",
        "--pretty=format:%x01%ad",
    ]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return {}
    if proc.returncode != 0:
        return {}

    wanted = set(days) if days is not None else None
    out: dict[str, dict[str, int]] = {}
    current_day: str | None = None
    for line in proc.stdout.splitlines():
        if line.startswith("\x01"):
            current_day = line[1:].strip()
            if wanted is None or current_day in wanted:
                bucket = out.setdefault(current_day, {"commits": 0, "lines_changed": 0})
                bucket["commits"] += 1
            continue
        if current_day is None or (wanted is not None and current_day not in wanted):
            continue
        parts = line.split("\t", 2)
        if len(parts) < 3:
            continue
        added = _numstat_int(parts[0])
        deleted = _numstat_int(parts[1])
        out.setdefault(current_day, {"commits": 0, "lines_changed": 0})[
            "lines_changed"
        ] += added + deleted
    if wanted is None:
        return out
    return {day: out[day] for day in days or [] if day in out}


def _numstat_int(value: str) -> int:
    if value == "-":
        return 0
    try:
        return int(value)
    except ValueError:
        return 0


def write_output_samples(
    mesh_root: str | os.PathLike[str] | Path,
    samples: dict[str, dict[str, int]],
    overwrite: bool = True,
) -> list[Path]:
    """Write ``output-<day>.json`` files under the phantom companion log dir."""
    out_dir = Path(mesh_root) / "logs" / "phantom-companion"
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for day, counts in sorted(samples.items()):
        path = out_dir / f"output-{day}.json"
        if not overwrite and path.exists():
            continue
        payload = {
            "day": day,
            "commits": int(counts.get("commits", 0)),
            "lines_changed": int(counts.get("lines_changed", 0)),
        }
        path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
        written.append(path)
    return written


def ingest_output(
    repo: str | os.PathLike[str] | Path,
    mesh_root: str | os.PathLike[str] | Path,
    days: list[str] | None = None,
    overwrite: bool = True,
) -> list[Path]:
    """Collect git output from ``repo`` and write mesh output samples."""
    return write_output_samples(mesh_root, collect_git_output(repo, days), overwrite=overwrite)


__all__ = [
    "collect_git_output",
    "write_output_samples",
    "ingest_output",
]

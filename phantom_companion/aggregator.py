"""Unified daily aggregator over phantom-mesh runtime artifacts.

Reads:
- ``~/.phantom-mesh/events/<id>/{meta.json, analysis.json}`` — E002 capture
- ``~/.phantom-mesh/logs/<satellite>/<date>.{md,log}`` — per-satellite daily
- ``~/.phantom-mesh/logs/phantom-*-heartbeat.log`` — satellite liveness

Returns a deterministic ``dict`` keyed by ISO date. No network, no LLM —
this is the data-plane layer Tier 1+ insight modules consume.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass, field, asdict
from datetime import date, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # avoid a runtime import cycle (schema imports aggregator)
    from .schema import HealthSample, OutputSample

DEFAULT_MESH_ROOT = Path(os.environ.get("PHANTOM_MESH_HOME", Path.home() / ".phantom-mesh"))

# Sibling satellites we read heartbeat / daily logs from.
SATELLITES = (
    "phantom-ai-feed",
    "phantom-flow",
    "phantom-enterprise",
    "phantom-secure-connector",
    "phantom-training",
)


@dataclass
class DailyAggregate:
    """One day's worth of phantom-mesh activity, flattened for insight modules."""

    day: str  # ISO YYYY-MM-DD
    events: list[dict[str, Any]] = field(default_factory=list)
    satellite_logs: dict[str, str] = field(default_factory=dict)
    heartbeats: dict[str, bool] = field(default_factory=dict)
    ai_feed_log: str = ""
    flow_log: str = ""
    # P1-M3 — parallel ④ secure-connector health + git-output streams, attached
    # when available so the daily reporter can run the real (gated) correlation
    # instead of the old hard-coded empty inputs. ``None`` means "not ingested".
    health: "HealthSample | None" = None
    output: "OutputSample | None" = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _iso_today() -> str:
    return date.today().isoformat()


def _load_event_dir(event_dir: Path) -> dict[str, Any] | None:
    """Load a single event directory; returns None if neither file exists."""
    meta_path = event_dir / "meta.json"
    analysis_path = event_dir / "analysis.json"
    if not meta_path.exists() and not analysis_path.exists():
        return None
    event: dict[str, Any] = {"id": event_dir.name}
    for key, path in (("meta", meta_path), ("analysis", analysis_path)):
        if path.exists():
            try:
                event[key] = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                event[key] = {"_error": "unreadable"}
    return event


def _events_for_day(events_root: Path, day: str) -> list[dict[str, Any]]:
    if not events_root.is_dir():
        return []
    out: list[dict[str, Any]] = []
    for child in sorted(events_root.iterdir()):
        if not child.is_dir():
            continue
        event = _load_event_dir(child)
        if event is None:
            continue
        ts = event.get("meta", {}).get("timestamp") or event.get("meta", {}).get("ts")
        if isinstance(ts, str) and ts.startswith(day):
            out.append(event)
        elif ts is None:
            # No timestamp → assume it belongs to the day's mtime bucket.
            try:
                mtime = datetime.fromtimestamp(child.stat().st_mtime).date().isoformat()
            except OSError:
                continue
            if mtime == day:
                out.append(event)
    return out


def _events_via_recall(day: str, limit: int = 1000) -> list[dict[str, Any]]:
    """Source the day's events through ``phantom recall --json`` (the supported,
    decrypting read path). The on-disk ``events/<id>/{meta,analysis}.json`` files
    are age-encrypted, so reading them directly yields ciphertext — recall is the
    only way to get decrypted ``{event_id, timestamp, kind, summary}``.

    Mapped back to the aggregator's event shape so insight modules are unaffected.
    Returns ``[]`` if phantom is unavailable (CI / no binary).
    """
    if not shutil.which("phantom"):
        return []
    try:
        proc = subprocess.run(
            ["phantom", "recall", "", "--json", "--since", day, "--limit", str(int(limit))],
            capture_output=True, text=True, timeout=20,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if proc.returncode != 0:
        return []
    try:
        events = json.loads(proc.stdout or "[]")
    except json.JSONDecodeError:
        return []
    out: list[dict[str, Any]] = []
    for e in events:
        ts = e.get("timestamp", "") or ""
        if not ts.startswith(day):  # --since is >=day; keep exactly this day
            continue
        out.append({
            "id": e.get("event_id"),
            "meta": {"timestamp": ts, "kind": e.get("kind")},
            "analysis": {"summary": e.get("summary", "")},
        })
    return out


def _read_satellite_log(logs_root: Path, satellite: str, day: str) -> str:
    sat_dir = logs_root / satellite
    if not sat_dir.is_dir():
        return ""
    # Both .md (ai-feed, companion) and .log (flow) variants exist in the wild.
    for ext in (".md", ".log"):
        candidate = sat_dir / f"{day}{ext}"
        if candidate.exists():
            try:
                return candidate.read_text(encoding="utf-8")
            except OSError:
                return ""
    return ""


def _heartbeat_alive(logs_root: Path, satellite: str) -> bool:
    hb = logs_root / f"{satellite}-heartbeat.log"
    if not hb.exists():
        return False
    try:
        return hb.stat().st_size > 0
    except OSError:
        return False


def aggregate_day(day: str | None = None, mesh_root: Path | None = None) -> DailyAggregate:
    """Return a :class:`DailyAggregate` for ``day`` (default: today)."""
    day = day or _iso_today()
    root = Path(mesh_root) if mesh_root else DEFAULT_MESH_ROOT
    # Real mesh → recall (decrypts); overridden mesh_root (tests) or no phantom →
    # fall back to the raw events/ dir scan.
    if root == DEFAULT_MESH_ROOT and shutil.which("phantom"):
        events = _events_via_recall(day)
    else:
        events = _events_for_day(root / "events", day)
    logs_root = root / "logs"
    satellite_logs = {sat: _read_satellite_log(logs_root, sat, day) for sat in SATELLITES}
    heartbeats = {sat: _heartbeat_alive(logs_root, sat) for sat in SATELLITES}
    return DailyAggregate(
        day=day,
        events=events,
        satellite_logs=satellite_logs,
        heartbeats=heartbeats,
        ai_feed_log=satellite_logs.get("phantom-ai-feed", ""),
        flow_log=satellite_logs.get("phantom-flow", ""),
    )


def aggregate_range(days: list[str], mesh_root: Path | None = None) -> dict[str, DailyAggregate]:
    """Aggregate multiple days (used by the weekly report)."""
    return {d: aggregate_day(d, mesh_root=mesh_root) for d in days}

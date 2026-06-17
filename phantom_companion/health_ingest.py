"""P1-M3 — parse the ④ secure-connector daily health export.

Health vitals reach the companion through ④ phantom-secure-connector, which
runs the consent-gated ingest pipeline (an iOS Shortcut / Garmin Connect export
lands as one JSON object per day). The export is *not* one fixed schema: Apple
HealthKit shortcuts emit camelCase keys and string-formatted numbers, while a
Garmin/native export uses snake_case. This module normalises either shape into
the typed :class:`~phantom_companion.schema.HealthSample` the statistical
correlation consumes.

It deliberately does no network I/O and no decryption — by the time an export
reaches here it has already been decrypted by ④. Parsing is total: any missing
optional field falls back to a documented default, and the only hard error is a
missing ``day`` (a sample with no date cannot be placed in the window).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .schema import HealthSample


class HealthExportError(ValueError):
    """Raised when a secure-connector export cannot be placed in the window."""


# Accepted aliases per field. The first key present (in order) wins. This keeps
# the parser tolerant of both the snake_case native export and the Apple
# HealthKit Shortcut's camelCase output without branching on a "source" guess.
_DAY_KEYS = ("day", "date")
_SLEEP_KEYS = ("sleep_hr", "sleep_hours", "sleepHours", "sleep_h")
_HRV_KEYS = ("hrv_ms", "hrv", "heartRateVariability", "heart_rate_variability")
_RESTING_KEYS = ("resting_hr", "restingHeartRate", "resting_heart_rate")
_ACTIVITY_KEYS = ("activity_min", "activeMinutes", "active_minutes", "activity_minutes")
_SOURCE_KEYS = ("source", "device", "provider")


def _first(raw: dict[str, Any], keys: tuple[str, ...]) -> Any | None:
    for k in keys:
        if k in raw and raw[k] is not None:
            return raw[k]
    return None


def _as_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_int(value: Any, default: int = 0) -> int:
    if value is None:
        return default
    try:
        # tolerate "52" and 52.0
        return int(round(float(value)))
    except (TypeError, ValueError):
        return default


def parse_secure_connector_export(raw: dict[str, Any]) -> HealthSample:
    """Normalise one day's ④ export dict into a :class:`HealthSample`.

    Raises :class:`HealthExportError` if the export carries no ``day``/``date``;
    everything else is best-effort with documented defaults. ``source`` defaults
    to ``"unknown"`` so a sample is never silently mis-attributed.
    """
    if not isinstance(raw, dict):
        raise HealthExportError("export must be a JSON object")
    day = _first(raw, _DAY_KEYS)
    if not day:
        raise HealthExportError("export is missing a 'day'/'date' field")
    source = _first(raw, _SOURCE_KEYS)
    return HealthSample(
        day=str(day),
        sleep_hr=_as_float(_first(raw, _SLEEP_KEYS)),
        hrv_ms=_as_float(_first(raw, _HRV_KEYS)),
        resting_hr=_as_int(_first(raw, _RESTING_KEYS)),
        activity_min=_as_int(_first(raw, _ACTIVITY_KEYS)),
        source=str(source) if source else "unknown",
    )


def parse_export_stream(rows: list[dict[str, Any]]) -> dict[str, HealthSample]:
    """Parse a multi-day export into a ``{day: HealthSample}`` map.

    Rows without a placeable ``day`` are skipped (not fatal) so one malformed
    line cannot drop a whole window — mirrors the aggregator's malformed-JSON
    tolerance.
    """
    out: dict[str, HealthSample] = {}
    for row in rows:
        try:
            sample = parse_secure_connector_export(row)
        except HealthExportError:
            continue
        out[sample.day] = sample
    return out


def read_health_window(
    mesh_root: str | os.PathLike[str] | Path,
    days: list[str],
) -> dict[str, dict[str, Any]]:
    """Read the per-day ④ secure-connector health exports for the given ISO days off disk.

    Production location: <mesh_root>/logs/phantom-secure-connector/health-<day>.json
    Each file is one day's export dict (the shape parse_secure_connector_export consumes).
    Returns {day: {sleep_hr, hrv_ms, resting_hr, activity_min, source}} suitable for
    aggregate_window(health_by_day=...). Days with no file (or unreadable/unparseable
    JSON) are skipped (best-effort, never raises). mesh_root may be a str or Path.
    """
    out: dict[str, dict[str, Any]] = {}
    for day in days:
        path = (
            Path(mesh_root)
            / "logs"
            / "phantom-secure-connector"
            / f"health-{day}.json"
        )
        if not path.exists():
            continue
        try:
            # OSError = unreadable; ValueError covers json.JSONDecodeError AND a
            # UnicodeDecodeError from a corrupt byte — keep this total.
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(raw, dict):
            continue
        raw.setdefault("day", day)
        try:
            sample = parse_secure_connector_export(raw)
        except HealthExportError:
            continue
        sample_dict = sample.to_dict()
        sample_dict.pop("day", None)
        out[day] = sample_dict
    return out


def read_output_window(
    mesh_root: str | os.PathLike[str] | Path,
    days: list[str],
) -> dict[str, dict[str, int]]:
    """Read per-day developer-output samples (commit/line counts) off disk.

    Production location: <mesh_root>/logs/phantom-companion/output-<day>.json
    Each file is a dict like {"commits": int, "lines_changed": int}.
    Returns {day: {commits, lines_changed}} suitable for aggregate_window(output_by_day=...).
    Missing/unreadable/unparseable files are skipped (never raises).
    """
    out: dict[str, dict[str, int]] = {}
    for day in days:
        path = Path(mesh_root) / "logs" / "phantom-companion" / f"output-{day}.json"
        if not path.exists():
            continue
        try:
            # ValueError also catches a UnicodeDecodeError from a corrupt byte.
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(raw, dict):
            continue
        try:
            commits = int(raw.get("commits", 0))
        except (TypeError, ValueError):
            commits = 0
        try:
            lines_changed = int(raw.get("lines_changed", 0))
        except (TypeError, ValueError):
            lines_changed = 0
        out[day] = {"commits": commits, "lines_changed": lines_changed}
    return out


__all__ = [
    "HealthExportError",
    "parse_secure_connector_export",
    "parse_export_stream",
    "read_health_window",
    "read_output_window",
]

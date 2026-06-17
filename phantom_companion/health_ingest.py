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


__all__ = [
    "HealthExportError",
    "parse_secure_connector_export",
    "parse_export_stream",
]

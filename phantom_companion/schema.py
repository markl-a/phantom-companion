"""P1-M2 — typed normalized records + a stable AggregateWindow.

The Tier-1 aggregator returns loose ``dict`` blobs; insight modules then poke
at nested keys (``event["analysis"]["provider"]`` etc.). That is fine for a
stub but brittle as the surface grows. This module introduces the typed layer:

- :class:`NormalizedEvent` — one mesh event, flattened to the fields the
  insight modules actually use.
- :class:`SatelliteDailyLog` — one satellite's text log for one day.
- :class:`HealthSample` — one day's health vitals (④ secure-connector shape).
- :class:`OutputSample` — one day's developer output (commits / lines).
- :class:`DayAggregate` — all of the above for a single day.
- :class:`AggregateWindow` — a contiguous, **day-ordered** span of
  ``DayAggregate``s, the unit the weekly report + statistical modules consume.

:func:`aggregate_window` builds a window from the existing day aggregator, so
it stays offline/deterministic and reuses the malformed-JSON-tolerant reader.
Every record round-trips through ``to_dict`` / ``from_dict`` losslessly, which
is what the SQLite cache relies on.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .aggregator import SATELLITES, aggregate_day

# Bumped to 2 in P1-M3: HealthSample gained ``activity_min`` + ``source``, which
# changes the serialized record shape. The cache key embeds SCHEMA_VERSION, so
# the bump cleanly invalidates any window cached under the v1 shape.
SCHEMA_VERSION = 2


# ---------------------------------------------------------------------------
# Leaf records
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class NormalizedEvent:
    """A single mesh event flattened to the fields insight modules consume."""

    event_id: str
    day: str
    timestamp: str = ""
    kind: str = ""
    provider: str = ""
    company: str = ""
    tags: tuple[str, ...] = ()
    applied: bool = False
    summary: str = ""
    error: str = ""  # non-empty if the source blob was unreadable

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "day": self.day,
            "timestamp": self.timestamp,
            "kind": self.kind,
            "provider": self.provider,
            "company": self.company,
            "tags": list(self.tags),
            "applied": self.applied,
            "summary": self.summary,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "NormalizedEvent":
        return cls(
            event_id=str(d.get("event_id", "")),
            day=str(d.get("day", "")),
            timestamp=str(d.get("timestamp", "")),
            kind=str(d.get("kind", "")),
            provider=str(d.get("provider", "")),
            company=str(d.get("company", "")),
            tags=tuple(d.get("tags", []) or []),
            applied=bool(d.get("applied", False)),
            summary=str(d.get("summary", "")),
            error=str(d.get("error", "")),
        )

    @classmethod
    def from_raw(cls, raw: dict[str, Any], day: str) -> "NormalizedEvent":
        """Normalize the aggregator's raw ``{id, meta, analysis}`` event shape."""
        meta = raw.get("meta") or {}
        analysis = raw.get("analysis") or {}
        error = ""
        if meta.get("_error") or analysis.get("_error"):
            error = "unreadable"
        tags = meta.get("tags") or []
        if isinstance(tags, str):
            tags = [tags]
        kind = analysis.get("task_kind") or analysis.get("kind") or meta.get("kind") or ""
        return cls(
            event_id=str(raw.get("id", "")),
            day=day,
            timestamp=str(meta.get("timestamp") or meta.get("ts") or ""),
            kind=str(kind),
            provider=str(analysis.get("provider") or ""),
            company=str(meta.get("company") or ""),
            tags=tuple(str(t) for t in tags),
            applied=bool(meta.get("applied", False)),
            summary=str(analysis.get("summary") or ""),
            error=error,
        )

    def to_raw(self) -> dict[str, Any]:
        """Re-expand to the loose dict shape the existing insight modules accept."""
        meta: dict[str, Any] = {
            "timestamp": self.timestamp,
            "tags": list(self.tags),
        }
        if self.company:
            meta["company"] = self.company
        if self.applied:
            meta["applied"] = True
        analysis: dict[str, Any] = {}
        if self.provider:
            analysis["provider"] = self.provider
        if self.kind:
            analysis["task_kind"] = self.kind
        if self.summary:
            analysis["summary"] = self.summary
        return {"id": self.event_id, "meta": meta, "analysis": analysis}


@dataclass(frozen=True)
class SatelliteDailyLog:
    day: str
    satellite: str
    text: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"day": self.day, "satellite": self.satellite, "text": self.text}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "SatelliteDailyLog":
        return cls(
            day=str(d.get("day", "")),
            satellite=str(d.get("satellite", "")),
            text=str(d.get("text", "")),
        )


@dataclass(frozen=True)
class HealthSample:
    """One day's health vitals (④ secure-connector export shape).

    ``activity_min`` (active minutes) and ``source`` (which device/app the
    export came from, e.g. ``garmin`` / ``apple_health``) are carried so the
    reporter can attribute the data and the consent-gated relay can decide what
    is safe to send off-device.
    """

    day: str
    sleep_hr: float = 0.0
    hrv_ms: float = 0.0
    resting_hr: int = 0
    activity_min: int = 0
    source: str = "unknown"

    def to_dict(self) -> dict[str, Any]:
        return {
            "day": self.day,
            "sleep_hr": self.sleep_hr,
            "hrv_ms": self.hrv_ms,
            "resting_hr": self.resting_hr,
            "activity_min": self.activity_min,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "HealthSample":
        return cls(
            day=str(d.get("day", "")),
            sleep_hr=float(d.get("sleep_hr", 0.0)),
            hrv_ms=float(d.get("hrv_ms", 0.0)),
            resting_hr=int(d.get("resting_hr", 0)),
            activity_min=int(d.get("activity_min", 0)),
            source=str(d.get("source", "unknown")),
        )


@dataclass(frozen=True)
class OutputSample:
    day: str
    commits: int = 0
    lines_changed: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "day": self.day,
            "commits": self.commits,
            "lines_changed": self.lines_changed,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "OutputSample":
        return cls(
            day=str(d.get("day", "")),
            commits=int(d.get("commits", 0)),
            lines_changed=int(d.get("lines_changed", 0)),
        )


# ---------------------------------------------------------------------------
# Composite records
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DayAggregate:
    day: str
    events: list[NormalizedEvent] = field(default_factory=list)
    satellite_logs: dict[str, SatelliteDailyLog] = field(default_factory=dict)
    heartbeats: dict[str, bool] = field(default_factory=dict)
    health: HealthSample | None = None
    output: OutputSample | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "day": self.day,
            "events": [e.to_dict() for e in self.events],
            "satellite_logs": {
                k: v.to_dict() for k, v in sorted(self.satellite_logs.items())
            },
            "heartbeats": dict(sorted(self.heartbeats.items())),
            "health": self.health.to_dict() if self.health else None,
            "output": self.output.to_dict() if self.output else None,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "DayAggregate":
        return cls(
            day=str(d.get("day", "")),
            events=[NormalizedEvent.from_dict(e) for e in d.get("events", [])],
            satellite_logs={
                k: SatelliteDailyLog.from_dict(v)
                for k, v in (d.get("satellite_logs") or {}).items()
            },
            heartbeats={k: bool(v) for k, v in (d.get("heartbeats") or {}).items()},
            health=HealthSample.from_dict(d["health"]) if d.get("health") else None,
            output=OutputSample.from_dict(d["output"]) if d.get("output") else None,
        )


@dataclass(frozen=True)
class AggregateWindow:
    """A contiguous, day-ordered span of :class:`DayAggregate`s."""

    days: list[DayAggregate] = field(default_factory=list)
    schema_version: int = SCHEMA_VERSION

    @property
    def start(self) -> str | None:
        return self.days[0].day if self.days else None

    @property
    def end(self) -> str | None:
        return self.days[-1].day if self.days else None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "days": [d.to_dict() for d in self.days],
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "AggregateWindow":
        return cls(
            days=[DayAggregate.from_dict(x) for x in d.get("days", [])],
            schema_version=int(d.get("schema_version", SCHEMA_VERSION)),
        )


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------

def aggregate_window(
    days: list[str],
    mesh_root: Path | None = None,
    health_by_day: dict[str, dict[str, Any]] | None = None,
    output_by_day: dict[str, dict[str, Any]] | None = None,
) -> AggregateWindow:
    """Build a day-ordered :class:`AggregateWindow` over ``days``.

    Days are sorted and de-duplicated so the window is always stable regardless
    of caller order. Reads go through the existing :func:`aggregate_day`, which
    already tolerates a missing mesh root and malformed JSON. ``health_by_day``
    / ``output_by_day`` optionally attach the parallel streams (the fixture
    harness or ④ ingest provides these).
    """
    ordered = sorted(set(days))
    health_by_day = health_by_day or {}
    output_by_day = output_by_day or {}

    day_aggs: list[DayAggregate] = []
    for day in ordered:
        raw = aggregate_day(day, mesh_root=mesh_root)
        events = [NormalizedEvent.from_raw(e, day) for e in raw.events]
        sat_logs = {
            sat: SatelliteDailyLog(day=day, satellite=sat, text=raw.satellite_logs.get(sat, ""))
            for sat in SATELLITES
        }
        health = (
            HealthSample.from_dict({"day": day, **health_by_day[day]})
            if day in health_by_day
            else raw.health
        )
        output = (
            OutputSample.from_dict({"day": day, **output_by_day[day]})
            if day in output_by_day
            else raw.output
        )
        day_aggs.append(
            DayAggregate(
                day=day,
                events=events,
                satellite_logs=sat_logs,
                heartbeats=dict(raw.heartbeats),
                health=health,
                output=output,
            )
        )
    return AggregateWindow(days=day_aggs)


__all__ = [
    "SCHEMA_VERSION",
    "NormalizedEvent",
    "SatelliteDailyLog",
    "HealthSample",
    "OutputSample",
    "DayAggregate",
    "AggregateWindow",
    "aggregate_window",
]

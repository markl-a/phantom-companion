"""P1-M2 — typed normalized schemas + AggregateWindow + SQLite cache.

These records are the stable typed layer the insight + statistical modules
should consume instead of poking at raw dicts. ``aggregate_range`` builds an
``AggregateWindow`` over a contiguous day span; a SQLite cache makes a warm
rebuild return byte-identical content to a cold build.
"""

from __future__ import annotations

import json
from pathlib import Path

from phantom_companion.fixtures import build_mesh_fixture, fixture_days
from phantom_companion.schema import (
    AggregateWindow,
    DayAggregate,
    HealthSample,
    NormalizedEvent,
    OutputSample,
    SatelliteDailyLog,
    aggregate_window,
)
from phantom_companion.cache import WindowCache


# ---------------------------------------------------------------------------
# Serialization round-trips
# ---------------------------------------------------------------------------

def test_normalized_event_roundtrip() -> None:
    ev = NormalizedEvent(
        event_id="2026-05-22-00",
        day="2026-05-22",
        timestamp="2026-05-22T10:15:00Z",
        kind="code_review",
        provider="claude",
        company="Garmin",
        tags=("jobseek", "applied"),
        applied=True,
        summary="did a thing",
    )
    blob = ev.to_dict()
    assert json.loads(json.dumps(blob))  # JSON-serializable
    ev2 = NormalizedEvent.from_dict(blob)
    assert ev2 == ev


def test_health_sample_roundtrip() -> None:
    hs = HealthSample(day="2026-05-22", sleep_hr=7.5, hrv_ms=55.0, resting_hr=58)
    assert HealthSample.from_dict(hs.to_dict()) == hs


def test_output_sample_roundtrip() -> None:
    os_ = OutputSample(day="2026-05-22", commits=4, lines_changed=120)
    assert OutputSample.from_dict(os_.to_dict()) == os_


def test_satellite_daily_log_roundtrip() -> None:
    log = SatelliteDailyLog(
        day="2026-05-22", satellite="phantom-ai-feed", text="## Item\nQ: ?\n"
    )
    assert SatelliteDailyLog.from_dict(log.to_dict()) == log


def test_window_roundtrip(tmp_path: Path) -> None:
    root = tmp_path / "m"
    build_mesh_fixture(root, end_day="2026-05-22", n_days=14, seed=3)
    win = aggregate_window(
        fixture_days("2026-05-22", 14), mesh_root=root
    )
    win2 = AggregateWindow.from_dict(win.to_dict())
    assert win2 == win


# ---------------------------------------------------------------------------
# Day ordering
# ---------------------------------------------------------------------------

def test_window_days_are_sorted_even_if_input_unordered(tmp_path: Path) -> None:
    root = tmp_path / "m"
    build_mesh_fixture(root, end_day="2026-05-22", n_days=5, seed=4)
    shuffled = ["2026-05-22", "2026-05-19", "2026-05-21", "2026-05-18", "2026-05-20"]
    win = aggregate_window(shuffled, mesh_root=root)
    assert [d.day for d in win.days] == sorted(shuffled)
    assert win.start == "2026-05-18"
    assert win.end == "2026-05-22"


def test_window_events_are_day_scoped(tmp_path: Path) -> None:
    root = tmp_path / "m"
    build_mesh_fixture(root, end_day="2026-05-22", n_days=7, seed=6)
    win = aggregate_window(fixture_days("2026-05-22", 7), mesh_root=root)
    for da in win.days:
        assert isinstance(da, DayAggregate)
        for ev in da.events:
            assert isinstance(ev, NormalizedEvent)
            assert ev.day == da.day
            assert ev.timestamp.startswith(da.day)


# ---------------------------------------------------------------------------
# SQLite cache: hit vs cold-build equivalence
# ---------------------------------------------------------------------------

def test_cache_hit_equals_cold_build(tmp_path: Path) -> None:
    root = tmp_path / "m"
    build_mesh_fixture(root, end_day="2026-05-22", n_days=14, seed=8)
    days = fixture_days("2026-05-22", 14)
    db = tmp_path / "cache.sqlite"

    cache = WindowCache(db)
    cold = cache.get_or_build(days, mesh_root=root)
    # Second call must be served from the DB, not rebuilt — but identical.
    warm = cache.get_or_build(days, mesh_root=root)
    assert warm.to_dict() == cold.to_dict()
    # Sanity: equivalence to a fresh, un-cached build.
    fresh = aggregate_window(days, mesh_root=root)
    assert cold.to_dict() == fresh.to_dict()


def test_cache_reports_hit_vs_miss(tmp_path: Path) -> None:
    root = tmp_path / "m"
    build_mesh_fixture(root, end_day="2026-05-22", n_days=7, seed=10)
    days = fixture_days("2026-05-22", 7)
    db = tmp_path / "cache.sqlite"
    cache = WindowCache(db)

    assert cache.has(days) is False
    cache.get_or_build(days, mesh_root=root)
    assert cache.has(days) is True


def test_cache_survives_reopen(tmp_path: Path) -> None:
    root = tmp_path / "m"
    build_mesh_fixture(root, end_day="2026-05-22", n_days=7, seed=12)
    days = fixture_days("2026-05-22", 7)
    db = tmp_path / "cache.sqlite"

    built = WindowCache(db).get_or_build(days, mesh_root=root)
    # A brand-new cache object over the same file must hit.
    reopened = WindowCache(db)
    assert reopened.has(days) is True
    assert reopened.get_or_build(days, mesh_root=root).to_dict() == built.to_dict()


# ---------------------------------------------------------------------------
# Robustness: missing satellite dir + malformed JSON
# ---------------------------------------------------------------------------

def test_missing_mesh_root_falls_back_to_empty_window(tmp_path: Path) -> None:
    # Nonexistent root: window builds, every day empty, no exception.
    days = fixture_days("2026-05-22", 7)
    win = aggregate_window(days, mesh_root=tmp_path / "nope")
    assert [d.day for d in win.days] == days
    assert all(d.events == [] for d in win.days)
    assert all(
        sl.text == "" for d in win.days for sl in d.satellite_logs.values()
    )


def test_missing_satellite_dir_does_not_crash(tmp_path: Path) -> None:
    root = tmp_path / "m"
    build_mesh_fixture(root, end_day="2026-05-22", n_days=3, seed=14)
    # Delete one satellite's log dir entirely.
    import shutil as _sh

    _sh.rmtree(root / "logs" / "phantom-ai-feed")
    win = aggregate_window(fixture_days("2026-05-22", 3), mesh_root=root)
    for d in win.days:
        assert "phantom-ai-feed" in d.satellite_logs
        assert d.satellite_logs["phantom-ai-feed"].text == ""


def test_malformed_event_json_is_tolerated(tmp_path: Path) -> None:
    root = tmp_path / "m"
    build_mesh_fixture(root, end_day="2026-05-22", n_days=3, seed=16)
    # Corrupt one event's meta.json with non-JSON bytes.
    events_root = root / "events"
    target = sorted(p for p in events_root.iterdir() if p.is_dir())[0]
    (target / "meta.json").write_text("{ this is not valid json :: ", encoding="utf-8")

    # Must not raise; the corrupt event is dropped or carried with an error
    # marker, but the rest of the window is intact.
    win = aggregate_window(fixture_days("2026-05-22", 3), mesh_root=root)
    assert [d.day for d in win.days] == fixture_days("2026-05-22", 3)
    # Other days still have events.
    total = sum(len(d.events) for d in win.days)
    assert total >= 1

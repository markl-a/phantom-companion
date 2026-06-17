"""P1-M1 — deterministic fixture harness + offline end-to-end report render.

The harness builds a fake ``~/.phantom-mesh`` tree containing multi-day
event / satellite-log / heartbeat streams plus parallel health-sample and
commit streams, so insight + report code can be exercised fully offline with
zero network and zero real phantom binary.

Determinism is a hard requirement: two builds with the same seed must produce
byte-identical trees, otherwise end-to-end report snapshots are untrustworthy.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from phantom_companion.fixtures import (
    MeshFixture,
    build_mesh_fixture,
    fixture_days,
)
from phantom_companion.reporter import (
    render_daily_report,
    render_weekly_report,
    shame_free_check,
    write_weekly_report,
)
from phantom_companion.aggregator import aggregate_day, aggregate_range


def _file_digest(root: Path) -> list[tuple[str, str]]:
    """A sorted (relative-path, content) snapshot of every file under ``root``."""
    out: list[tuple[str, str]] = []
    for p in sorted(root.rglob("*")):
        if p.is_file():
            rel = p.relative_to(root).as_posix()
            out.append((rel, p.read_text(encoding="utf-8")))
    return out


def test_fixture_days_are_contiguous_and_ordered() -> None:
    days = fixture_days(end_day="2026-05-22", n_days=14)
    assert len(days) == 14
    assert days[0] == "2026-05-09"
    assert days[-1] == "2026-05-22"
    # strictly increasing ISO order
    assert days == sorted(days)


def test_build_is_deterministic_same_seed(tmp_path: Path) -> None:
    a = tmp_path / "a"
    b = tmp_path / "b"
    build_mesh_fixture(a, end_day="2026-05-22", n_days=14, seed=7)
    build_mesh_fixture(b, end_day="2026-05-22", n_days=14, seed=7)
    assert _file_digest(a) == _file_digest(b)


def test_build_differs_on_seed(tmp_path: Path) -> None:
    a = tmp_path / "a"
    b = tmp_path / "b"
    build_mesh_fixture(a, end_day="2026-05-22", n_days=14, seed=1)
    build_mesh_fixture(b, end_day="2026-05-22", n_days=14, seed=2)
    assert _file_digest(a) != _file_digest(b)


def test_build_returns_typed_fixture_with_parallel_streams(tmp_path: Path) -> None:
    fx = build_mesh_fixture(tmp_path / "m", end_day="2026-05-22", n_days=14, seed=3)
    assert isinstance(fx, MeshFixture)
    assert fx.days == fixture_days(end_day="2026-05-22", n_days=14)
    # parallel streams: one health sample + one commit list per day
    assert set(fx.health_by_day) == set(fx.days)
    assert set(fx.commits_by_day) == set(fx.days)
    # health samples carry the documented keys
    sample = fx.health_by_day[fx.days[0]]
    assert {"sleep_hr", "hrv_ms", "resting_hr"}.issubset(sample.keys())


def test_fixture_events_land_in_the_right_day(tmp_path: Path) -> None:
    root = tmp_path / "m"
    build_mesh_fixture(root, end_day="2026-05-22", n_days=14, seed=5)
    # Every fixture day must aggregate at least one event from the events/ tree.
    for day in fixture_days(end_day="2026-05-22", n_days=14):
        agg = aggregate_day(day, mesh_root=root)
        assert agg.events, f"no events aggregated for {day}"
        # and none leak from neighbouring days
        for ev in agg.events:
            ts = ev.get("meta", {}).get("timestamp", "")
            assert ts.startswith(day), f"event {ev['id']} ts={ts} leaked into {day}"


def test_offline_end_to_end_daily_report_is_shame_free(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from phantom_companion import reporter as rep

    # No real coach: keep the path deterministic + offline.
    monkeypatch.setattr(rep, "_invoke_coach", lambda _day: None)
    root = tmp_path / "m"
    build_mesh_fixture(root, end_day="2026-05-22", n_days=14, seed=9)

    agg = aggregate_day("2026-05-22", mesh_root=root)
    text = render_daily_report(agg)
    assert text.startswith("# phantom-companion")
    # With real fixture events present, at least some insight modules fire.
    assert "## Insights" in text
    ok, reason = shame_free_check(text)
    assert ok, reason


def test_offline_end_to_end_weekly_report_renders_and_is_shame_free(
    tmp_path: Path,
) -> None:
    root = tmp_path / "m"
    build_mesh_fixture(root, end_day="2026-05-22", n_days=14, seed=11)
    days = fixture_days(end_day="2026-05-22", n_days=7)
    aggs = list(aggregate_range(days, mesh_root=root).values())
    text = render_weekly_report(aggs)
    total = sum(len(a.events) for a in aggs)
    assert total > 0, "weekly window should contain fixture events"
    assert f"Total events: **{total}**" in text
    ok, reason = shame_free_check(text)
    assert ok, reason


def test_write_weekly_report_offline_against_fixture(tmp_path: Path) -> None:
    root = tmp_path / "m"
    build_mesh_fixture(root, end_day="2026-05-22", n_days=7, seed=13)
    out = tmp_path / "out"
    path = write_weekly_report(
        end_day="2026-05-22", out_root=out, mesh_root=root
    )
    assert path.exists()
    body = path.read_text(encoding="utf-8")
    assert body.startswith("# phantom-companion")
    ok, reason = shame_free_check(body)
    assert ok, reason


def test_fixture_event_payload_is_valid_json(tmp_path: Path) -> None:
    root = tmp_path / "m"
    build_mesh_fixture(root, end_day="2026-05-22", n_days=14, seed=17)
    events_root = root / "events"
    any_meta = False
    for child in events_root.iterdir():
        meta = child / "meta.json"
        if meta.exists():
            any_meta = True
            json.loads(meta.read_text(encoding="utf-8"))  # must not raise
    assert any_meta, "fixture produced no event meta.json files"

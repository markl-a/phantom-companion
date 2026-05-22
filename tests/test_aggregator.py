"""Aggregator integration: synthetic ~/.phantom-mesh layout."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from phantom_companion.aggregator import (
    SATELLITES,
    aggregate_day,
    aggregate_range,
)


@pytest.fixture()
def synthetic_mesh(tmp_path: Path) -> Path:
    """Build a fake ~/.phantom-mesh with 2 events + 1 ai-feed digest."""
    events = tmp_path / "events"
    events.mkdir()
    # Event 1 — today, full meta + analysis.
    e1 = events / "evt-001"
    e1.mkdir()
    (e1 / "meta.json").write_text(
        json.dumps({"timestamp": "2026-05-22T10:15:00Z", "tags": ["jobseek"], "company": "Garmin"}),
        encoding="utf-8",
    )
    (e1 / "analysis.json").write_text(
        json.dumps({"provider": "claude", "task_kind": "code_review"}),
        encoding="utf-8",
    )
    # Event 2 — today, applied.
    e2 = events / "evt-002"
    e2.mkdir()
    (e2 / "meta.json").write_text(
        json.dumps(
            {
                "timestamp": "2026-05-22T14:02:00Z",
                "tags": ["jobseek", "applied"],
                "company": "Anthropic",
            }
        ),
        encoding="utf-8",
    )
    # Event 3 — yesterday, must NOT appear in today's aggregate.
    e3 = events / "evt-003"
    e3.mkdir()
    (e3 / "meta.json").write_text(
        json.dumps({"timestamp": "2026-05-21T11:00:00Z"}), encoding="utf-8"
    )

    logs = tmp_path / "logs"
    (logs / "phantom-ai-feed").mkdir(parents=True)
    (logs / "phantom-ai-feed" / "2026-05-22.md").write_text(
        "## Item A\nQ: what about X?\n## Item B\n",
        encoding="utf-8",
    )
    (logs / "phantom-flow").mkdir()
    (logs / "phantom-flow" / "2026-05-22.log").write_text("flow ran\n", encoding="utf-8")

    # heartbeats
    (logs / "phantom-enterprise-heartbeat.log").write_text("alive\n", encoding="utf-8")
    (logs / "phantom-secure-connector-heartbeat.log").write_text("", encoding="utf-8")
    return tmp_path


def test_aggregate_day_event_count_correct(synthetic_mesh: Path) -> None:
    agg = aggregate_day("2026-05-22", mesh_root=synthetic_mesh)
    assert agg.day == "2026-05-22"
    assert len(agg.events) == 2
    ids = sorted(ev["id"] for ev in agg.events)
    assert ids == ["evt-001", "evt-002"]


def test_aggregate_day_picks_up_satellite_logs(synthetic_mesh: Path) -> None:
    agg = aggregate_day("2026-05-22", mesh_root=synthetic_mesh)
    assert "Item A" in agg.ai_feed_log
    assert "flow ran" in agg.flow_log
    # All satellites should be present in the dict, even if empty.
    assert set(agg.satellite_logs.keys()) == set(SATELLITES)


def test_aggregate_day_heartbeats(synthetic_mesh: Path) -> None:
    agg = aggregate_day("2026-05-22", mesh_root=synthetic_mesh)
    assert agg.heartbeats["phantom-enterprise"] is True
    # Empty file → not alive.
    assert agg.heartbeats["phantom-secure-connector"] is False
    # Never-existed file → not alive.
    assert agg.heartbeats["phantom-training"] is False


def test_aggregate_day_handles_missing_root(tmp_path: Path) -> None:
    # Pointing at a brand-new empty dir must not raise.
    agg = aggregate_day("2026-05-22", mesh_root=tmp_path)
    assert agg.events == []
    assert all(v == "" for v in agg.satellite_logs.values())


def test_aggregate_range_returns_dict_per_day(synthetic_mesh: Path) -> None:
    days = ["2026-05-21", "2026-05-22"]
    out = aggregate_range(days, mesh_root=synthetic_mesh)
    assert set(out.keys()) == set(days)
    assert len(out["2026-05-22"].events) == 2
    assert len(out["2026-05-21"].events) == 1

"""companion_goal_status MCP tool — mirrors the CLI `companion goals` subcommand."""
from __future__ import annotations

import json

from phantom_companion.goals import Goal, save_goals
from phantom_companion.mcp_server import companion_goal_status


def test_goal_status_empty_when_no_goals_declared(tmp_path):
    assert companion_goal_status(tmp_path) == []


def test_goal_status_returns_per_goal_dict_for_temp_goals_json(tmp_path):
    save_goals(tmp_path / "goals.json", [
        Goal(id="mood", label="Mood check", metric="mood", direction="at_least",
             target=4.0, window_days=1),
    ])
    checkin = {"day": "2026-06-27", "gut": 3, "mood": 5, "sleep_hr": 7.0}
    (tmp_path / "checkins.jsonl").write_text(json.dumps(checkin) + "\n", encoding="utf-8")

    result = companion_goal_status(tmp_path, end="2026-06-27", mesh_root=tmp_path)

    assert result == [{"id": "mood", "status": "on_track", "actual": 5.0, "target": 4.0}]


def test_goal_status_insufficient_data_without_checkins(tmp_path):
    save_goals(tmp_path / "goals.json", [
        Goal(id="mood", label="Mood check", metric="mood", direction="at_least",
             target=4.0, window_days=7),
    ])

    result = companion_goal_status(tmp_path, end="2026-06-27", mesh_root=tmp_path)

    assert result == [{"id": "mood", "status": "insufficient_data", "actual": 0.0, "target": 4.0}]


def test_goal_status_multiple_goals_preserve_declaration_order(tmp_path):
    save_goals(tmp_path / "goals.json", [
        Goal(id="mood", label="Mood", metric="mood", direction="at_least",
             target=4.0, window_days=1),
        Goal(id="calm-ai", label="AI calls", metric="llm_calls", direction="at_most",
             target=100.0, window_days=1),
    ])
    checkin = {"day": "2026-06-27", "gut": 3, "mood": 2, "sleep_hr": 6.0}
    (tmp_path / "checkins.jsonl").write_text(json.dumps(checkin) + "\n", encoding="utf-8")

    result = companion_goal_status(tmp_path, end="2026-06-27", mesh_root=tmp_path)

    assert [r["id"] for r in result] == ["mood", "calm-ai"]
    assert result[0]["status"] == "violated"  # mood 2 well below target 4

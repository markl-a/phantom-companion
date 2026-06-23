from phantom_companion.goals import Goal
from phantom_companion.goal_eval import GoalStatus
from phantom_companion.reporter import render_goal_section, shame_free_check


def _st(status, label="Move daily", metric="activity_min"):
    g = Goal(id="m", label=label, metric=metric, direction="at_least",
             target=30, window_days=1)
    return GoalStatus(g, status, actual=5, target=30, observed_days=1)


def test_section_lists_each_goal_with_status_marker():
    lines = render_goal_section([_st("on_track"), _st("violated", label="Sleep 7h")])
    text = "\n".join(lines)
    assert "## 🎯 Goal tracking" in text
    assert "Move daily" in text and "Sleep 7h" in text


def test_section_is_shame_free():
    lines = render_goal_section([_st("violated"), _st("drifting")])
    ok, _ = shame_free_check("\n".join(lines))
    assert ok


def test_empty_goals_returns_no_section():
    assert render_goal_section([]) == []

import pytest
from phantom_companion.goals import (
    Goal, METRICS, DEFAULT_WINDOWS, load_goals, save_goals, add_goal, remove_goal,
)


def test_goal_roundtrips():
    g = Goal(id="move", label="Move daily", metric="activity_min",
             direction="at_least", target=30.0, window_days=1)
    assert Goal.from_dict(g.to_dict()) == g


def test_metric_vocabulary_is_fixed():
    assert set(METRICS) == {
        "commits", "activity_min", "sleep_hr", "mood", "jobs_applied", "llm_calls",
    }


def test_add_uses_default_window_and_slug(tmp_path):
    p = tmp_path / "goals.json"
    g = add_goal(p, metric="jobs_applied", direction="at_least", target=3, label="Apply weekly")
    assert g.window_days == DEFAULT_WINDOWS["jobs_applied"] == 7
    assert g.id and g.id == g.id.lower()
    assert load_goals(p) == [g]


def test_add_rejects_unknown_metric(tmp_path):
    with pytest.raises(ValueError):
        add_goal(tmp_path / "goals.json", metric="vibes", direction="at_least", target=1)


def test_remove_goal(tmp_path):
    p = tmp_path / "goals.json"
    add_goal(p, metric="commits", direction="at_least", target=1, label="Ship")
    g2 = add_goal(p, metric="sleep_hr", direction="at_least", target=7, label="Sleep")
    assert remove_goal(p, g2.id) is True
    assert [g.metric for g in load_goals(p)] == ["commits"]
    assert remove_goal(p, "nope") is False


def test_load_missing_file_is_empty(tmp_path):
    assert load_goals(tmp_path / "absent.json") == []

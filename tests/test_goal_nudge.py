from phantom_companion.goals import Goal
from phantom_companion.goal_eval import GoalStatus
from phantom_companion.goal_nudge import build_goal_nudges, should_nudge, emit_goal_nudges
from phantom_companion.reporter import shame_free_check


def _status(status):
    g = Goal(id="move", label="Move daily", metric="activity_min",
             direction="at_least", target=30, window_days=1)
    return GoalStatus(g, status, actual=5, target=30, observed_days=1)


def test_only_violated_become_nudges():
    statuses = [_status("violated"), _status("on_track"), _status("drifting"),
                _status("insufficient_data")]
    nudges = build_goal_nudges(statuses, window_key="2026-06-01")
    assert len(nudges) == 1 and nudges[0].kind == "goal_nudge"


def test_nudge_body_is_shame_free():
    n = build_goal_nudges([_status("violated")], window_key="2026-06-01")[0]
    ok, _ = shame_free_check(n.body)
    assert ok, f"nudge body tripped shame lint: {n.body!r}"


def test_throttle_one_per_goal_per_window(tmp_path):
    state = tmp_path / "nudge_state.jsonl"
    assert should_nudge("move", "2026-06-01", state) is True
    emit_goal_nudges([_status("violated")], window_key="2026-06-01",
                     outbox=tmp_path / "outbox", state_path=state)
    assert should_nudge("move", "2026-06-01", state) is False
    assert should_nudge("move", "2026-06-02", state) is True


def test_emit_writes_local_outbox(tmp_path):
    outbox = tmp_path / "outbox"
    emitted = emit_goal_nudges([_status("violated")], window_key="2026-06-01",
                               outbox=outbox, state_path=tmp_path / "s.jsonl")
    assert emitted == 1
    assert list(outbox.glob("goal_nudge-*.json"))


def test_nudge_shame_free_with_adversarial_label():
    from phantom_companion.reporter import shame_free_check
    g = Goal(id="x", label="you failed to move", metric="activity_min",
             direction="at_least", target=30, window_days=1)
    st = GoalStatus(g, "violated", actual=5, target=30, observed_days=1)
    n = build_goal_nudges([st], window_key="2026-06-01")[0]
    assert shame_free_check(n.body)[0], f"body: {n.body!r}"
    assert shame_free_check(n.title)[0], f"title: {n.title!r}"

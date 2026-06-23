import math
from phantom_companion.schema import (
    AggregateWindow, DayAggregate, HealthSample, OutputSample, NormalizedEvent,
)
from phantom_companion.checkin import SubjectiveCheckin
from phantom_companion.goals import Goal
from phantom_companion.goal_eval import evaluate_goals, has_goal_density


def _day(day, commits=None, activity=None, sleep=None, applied=0, providers=0):
    events = []
    for i in range(applied):
        events.append(NormalizedEvent(event_id=f"a{i}", day=day, applied=True))
    for i in range(providers):
        events.append(NormalizedEvent(event_id=f"p{i}", day=day, provider="codex"))
    return DayAggregate(
        day=day, events=events,
        health=HealthSample(day=day, activity_min=activity or 0, sleep_hr=sleep or 0.0)
        if (activity is not None or sleep is not None) else None,
        output=OutputSample(day=day, commits=commits) if commits is not None else None,
    )


def test_density_gate_is_window_proportional():
    assert has_goal_density(observed=1, window_days=1) is True
    assert has_goal_density(observed=3, window_days=7) is False
    assert has_goal_density(observed=4, window_days=7) is True


def test_at_least_violation_when_well_below():
    win = AggregateWindow(days=[_day("2026-06-01", activity=5)])
    g = Goal(id="move", label="Move", metric="activity_min",
             direction="at_least", target=30, window_days=1)
    [st] = evaluate_goals(win, {}, [g])
    assert st.status == "violated" and st.actual == 5 and st.target == 30


def test_at_least_drifting_within_margin():
    win = AggregateWindow(days=[_day("2026-06-01", activity=27)])
    g = Goal(id="m", label="", metric="activity_min", direction="at_least", target=30, window_days=1)
    assert evaluate_goals(win, {}, [g])[0].status == "drifting"


def test_at_least_on_track():
    win = AggregateWindow(days=[_day("2026-06-01", commits=3)])
    g = Goal(id="ship", label="", metric="commits", direction="at_least", target=1, window_days=1)
    assert evaluate_goals(win, {}, [g])[0].status == "on_track"


def test_sum_metric_jobs_applied_over_week():
    days = [_day(f"2026-06-0{i}", applied=1) for i in range(1, 6)]
    win = AggregateWindow(days=days)
    g = Goal(id="apply", label="", metric="jobs_applied", direction="at_least",
             target=3, window_days=7)
    [st] = evaluate_goals(win, {}, [g])
    assert st.actual == 5 and st.status == "on_track"


def test_at_most_llm_calls_violation():
    days = [_day(f"2026-06-{i:02d}", providers=10) for i in range(1, 21)]
    win = AggregateWindow(days=days)
    g = Goal(id="ai", label="", metric="llm_calls", direction="at_most",
             target=100, window_days=30)
    [st] = evaluate_goals(win, {}, [g])
    assert st.actual == 200 and st.status == "violated"


def test_mood_uses_checkins_and_insufficient_data():
    win = AggregateWindow(days=[_day(f"2026-06-0{i}") for i in range(1, 8)])
    checkins = {"2026-06-01": SubjectiveCheckin(day="2026-06-01", mood=4)}
    g = Goal(id="mood", label="", metric="mood", direction="at_least",
             target=4, window_days=7)
    [st] = evaluate_goals(win, checkins, [g])
    assert st.status == "insufficient_data"

"""Deterministic, density-gated evaluation of goals against an AggregateWindow.

NEVER uses an LLM: whether a goal is violated is pure arithmetic. A goal is only
judged when enough of its window has observed data (window-proportional gate),
otherwise it is `insufficient_data` and raises no nudge."""
from __future__ import annotations

import math
from dataclasses import dataclass

from .goals import Goal
from .schema import AggregateWindow

_SUM_METRICS = {"jobs_applied", "llm_calls"}


@dataclass(frozen=True)
class GoalStatus:
    goal: Goal
    status: str
    actual: float
    target: float
    observed_days: int

    @property
    def gap(self) -> float:
        return self.actual - self.target


def has_goal_density(observed: int, window_days: int) -> bool:
    """Window-proportional density gate: need data for at least half the window."""
    return observed >= max(1, math.ceil(window_days / 2))


def _per_day(days, metric: str, checkins_by_day: dict):
    for d in days:
        if metric == "commits":
            if d.output is not None:
                yield d.output.commits
        elif metric == "activity_min":
            if d.health is not None:
                yield d.health.activity_min
        elif metric == "sleep_hr":
            if d.health is not None:
                yield d.health.sleep_hr
        elif metric == "mood":
            c = checkins_by_day.get(d.day)
            if c is not None:
                yield c.mood
        elif metric == "jobs_applied":
            yield sum(1 for e in d.events if e.applied)
        elif metric == "llm_calls":
            yield sum(1 for e in d.events if e.provider)


def _status_for(direction: str, actual: float, target: float) -> str:
    if direction == "at_least":
        if actual >= target:
            return "on_track"
        return "drifting" if actual >= 0.8 * target else "violated"
    if actual <= target:
        return "on_track"
    return "drifting" if actual <= 1.2 * target else "violated"


def evaluate_goals(window: AggregateWindow, checkins_by_day: dict,
                   goals: list[Goal]) -> list[GoalStatus]:
    out: list[GoalStatus] = []
    for g in goals:
        # Clip each goal to only the last `g.window_days` of the shared window
        # BEFORE measuring. Multi-goal callers pass ONE window sized to
        # max(window_days); without this a 1-day goal would be judged over the
        # whole span. No-op when the window already equals the goal's window.
        clipped = window.days[-g.window_days:]
        values = list(_per_day(clipped, g.metric, checkins_by_day))
        observed = len(values)
        if not has_goal_density(observed, g.window_days):
            out.append(GoalStatus(g, "insufficient_data", 0.0, g.target, observed))
            continue
        actual = float(sum(values)) if g.metric in _SUM_METRICS else (sum(values) / observed)
        out.append(GoalStatus(g, _status_for(g.direction, actual, g.target),
                              round(actual, 3), g.target, observed))
    return out


__all__ = ["GoalStatus", "has_goal_density", "evaluate_goals"]

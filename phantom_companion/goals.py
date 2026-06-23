"""User-declared goals: a metric, a direction, a target, a window. Stored as a
human-readable goals.json. Pure data — evaluation lives in goal_eval.py."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

DEFAULT_WINDOWS: dict[str, int] = {
    "commits": 1, "activity_min": 1, "sleep_hr": 1,
    "mood": 7, "jobs_applied": 7, "llm_calls": 30,
}
METRICS = tuple(DEFAULT_WINDOWS)
_DIRECTIONS = ("at_least", "at_most")


@dataclass(frozen=True)
class Goal:
    id: str
    label: str
    metric: str
    direction: str
    target: float
    window_days: int

    def to_dict(self) -> dict:
        return {
            "id": self.id, "label": self.label, "metric": self.metric,
            "direction": self.direction, "target": self.target,
            "window_days": self.window_days,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Goal":
        return cls(
            id=str(d["id"]), label=str(d.get("label", "")),
            metric=str(d["metric"]), direction=str(d["direction"]),
            target=float(d["target"]), window_days=int(d["window_days"]),
        )


def _slug(metric: str, label: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-") or metric
    return base[:40]


def load_goals(path: Path) -> list[Goal]:
    p = Path(path)
    if not p.exists():
        return []
    data = json.loads(p.read_text(encoding="utf-8"))
    return [Goal.from_dict(d) for d in data]


def save_goals(path: Path, goals: list[Goal]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps([g.to_dict() for g in goals], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def add_goal(path: Path, metric: str, direction: str, target: float,
             label: str = "", window_days: int | None = None) -> Goal:
    if metric not in METRICS:
        raise ValueError(f"unknown metric {metric!r}; known: {', '.join(METRICS)}")
    if direction not in _DIRECTIONS:
        raise ValueError(f"direction must be one of {_DIRECTIONS}")
    goals = load_goals(path)
    label = label or f"{metric} {direction} {target}"
    gid = _slug(metric, label)
    existing = {g.id for g in goals}
    suffix = 2
    base = gid
    while gid in existing:
        gid = f"{base}-{suffix}"
        suffix += 1
    goal = Goal(
        id=gid, label=label, metric=metric, direction=direction,
        target=float(target),
        window_days=window_days if window_days is not None else DEFAULT_WINDOWS[metric],
    )
    goals.append(goal)
    save_goals(path, goals)
    return goal


def remove_goal(path: Path, goal_id: str) -> bool:
    goals = load_goals(path)
    kept = [g for g in goals if g.id != goal_id]
    if len(kept) == len(goals):
        return False
    save_goals(path, kept)
    return True


__all__ = [
    "Goal", "METRICS", "DEFAULT_WINDOWS",
    "load_goals", "save_goals", "add_goal", "remove_goal",
]

"""MCP tool surface for phantom-companion.

Plain Python callables a host MCP server registers as tools. Today this
mirrors the CLI's ``companion goals`` subcommand as ``companion_goal_status``,
returning structured data instead of printed lines.
"""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from .checkin import read_checkins
from .goal_eval import evaluate_goals
from .goals import load_goals
from .schema import aggregate_window


def companion_goal_status(
    report_dir: str | Path,
    *,
    end: str | None = None,
    mesh_root: str | Path | None = None,
) -> list[dict]:
    """Per-goal ``{id, status, actual, target}`` for the goals declared in
    ``report_dir/goals.json`` — the same evaluation the ``companion goals``
    CLI subcommand prints, returned as data. ``end`` defaults to today;
    ``mesh_root`` overrides the mesh root scanned for commits/health/output
    (tests pass an isolated temp dir)."""
    report_dir = Path(report_dir)
    goals = load_goals(report_dir / "goals.json")
    if not goals:
        return []
    span = max(g.window_days for g in goals)
    end_date = date.fromisoformat(end) if end else date.today()
    days = [(end_date - timedelta(days=i)).isoformat() for i in range(span - 1, -1, -1)]
    window = aggregate_window(days, mesh_root=Path(mesh_root) if mesh_root else None)
    checkins = read_checkins(report_dir)
    return [
        {"id": st.goal.id, "status": st.status, "actual": st.actual, "target": st.target}
        for st in evaluate_goals(window, checkins, goals)
    ]


__all__ = ["companion_goal_status"]

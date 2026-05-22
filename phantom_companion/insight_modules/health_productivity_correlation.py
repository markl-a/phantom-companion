"""Health (sleep / HRV) vs output (commits, PR-review quality).

Tier 1 stub: ④ secure-connector HealthKit ingest is not yet writing data,
so this module's job today is just to declare the shape and confirm it
sees no health input. Real Pearson r ships once a 14-day window exists.
"""

from __future__ import annotations

from typing import Any


def analyze_health_vs_output(
    health_data: dict[str, Any] | None = None,
    commits: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Compute a placeholder correlation summary.

    ``health_data`` is the daily aggregate that ④ will provide
    (sleep_hr, hrv_ms, resting_hr). ``commits`` is a git-log slice.
    """
    health_data = health_data or {}
    commits = commits or []
    have_health = bool(health_data)
    have_output = bool(commits)
    baseline_ready = have_health and have_output and len(commits) >= 1

    if baseline_ready:
        sleep_hr = float(health_data.get("sleep_hr", 0.0))
        commit_count = len(commits)
        # Toy directional signal — replace with real Pearson r once N≥14.
        signal = "↑" if (sleep_hr >= 7.0 and commit_count >= 3) else "·"
        summary = (
            f"sleep={sleep_hr:.1f}h, commits={commit_count}: directional={signal}"
        )
    else:
        missing = []
        if not have_health:
            missing.append("health (④ secure-connector ingest)")
        if not have_output:
            missing.append("commits (git activity feed)")
        summary = "Waiting on: " + ", ".join(missing) if missing else "No data yet."
    return {
        "module": "health_productivity_correlation",
        "summary": summary,
        "details": {
            "health_keys": sorted(health_data.keys()),
            "commit_count": len(commits),
        },
        "baseline_ready": baseline_ready,
    }

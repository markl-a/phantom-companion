"""Health (sleep / HRV) vs output (commits, PR-review quality).

Two code paths:

- :func:`analyze_health_vs_output` — single-day directional stub used by the
  daily reporter. It just declares the shape and confirms whether ④
  secure-connector health ingest produced anything today.
- :func:`correlate_health_output` — the multi-day *statistical* gate. It
  computes a real Pearson r over a window of paired (health, output) days,
  but only once at least :data:`phantom_companion.thresholds.MIN_SAMPLES`
  days exist. The threshold is imported (never re-hard-coded) so the gate
  cannot be bypassed.
"""

from __future__ import annotations

import math
from typing import Any

from ..thresholds import MIN_SAMPLES

MODULE = "health_productivity_correlation"


def analyze_health_vs_output(
    health_data: dict[str, Any] | None = None,
    commits: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Compute a placeholder single-day correlation summary.

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
        # Toy directional signal — a sound Pearson r over a multi-day window
        # ships via ``correlate_health_output`` once MIN_SAMPLES days exist.
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
        "module": MODULE,
        "summary": summary,
        "details": {
            "health_keys": sorted(health_data.keys()),
            "commit_count": len(commits),
        },
        "baseline_ready": baseline_ready,
    }


def _pearson_r(xs: list[float], ys: list[float]) -> float | None:
    """Pearson correlation coefficient; ``None`` if undefined (flat series)."""
    n = len(xs)
    if n < 2 or len(ys) != n:
        return None
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    num = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    den_x = math.sqrt(sum((x - mean_x) ** 2 for x in xs))
    den_y = math.sqrt(sum((y - mean_y) ** 2 for y in ys))
    if den_x == 0.0 or den_y == 0.0:
        return None
    return num / (den_x * den_y)


def correlate_health_output(samples: list[dict[str, Any]]) -> dict[str, Any]:
    """Multi-day Pearson correlation between sleep and commit output.

    ``samples`` is a list of per-day dicts, each carrying at least
    ``sleep_hr`` (float) and ``commits`` (int count). The statistical gate is
    :data:`MIN_SAMPLES`: with fewer paired days the correlation is suppressed
    and the module reports baseline-not-ready. This is the gate the M1 task
    pins to a single imported constant.
    """
    n = len(samples)
    baseline_ready = n >= MIN_SAMPLES

    details: dict[str, Any] = {"n_samples": n, "min_samples": MIN_SAMPLES}

    if not baseline_ready:
        summary = (
            f"{n}/{MIN_SAMPLES} days of paired health+output data — the "
            "correlation stays in baseline mode until the window fills."
        )
        return {
            "module": MODULE,
            "summary": summary,
            "details": details,
            "baseline_ready": False,
        }

    sleep = [float(s.get("sleep_hr", 0.0)) for s in samples]
    commits = [float(s.get("commits", 0)) for s in samples]
    r = _pearson_r(sleep, commits)
    details["pearson_r"] = round(r, 4) if r is not None else None
    if r is None:
        summary = (
            f"{n} days observed, but sleep or output had no variance — "
            "correlation is undefined for now."
        )
    else:
        direction = "positive" if r > 0 else ("negative" if r < 0 else "flat")
        summary = (
            f"{n} days observed — sleep↔output correlation r={r:.2f} "
            f"({direction}). This is a description, not a verdict."
        )
    return {
        "module": MODULE,
        "summary": summary,
        "details": details,
        "baseline_ready": True,
    }

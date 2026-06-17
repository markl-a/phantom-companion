"""P3-M2 — monthly / quarterly long-window trend descriptions.

The daily / weekly views describe a moment; the monthly and quarterly views
describe a *direction*. :func:`trend_over` fits a least-squares slope over a
metric's daily series and reports only its direction — increasing, decreasing,
or steady — behind the same density gate the rest of the companion uses
(:data:`~phantom_companion.thresholds.MIN_SAMPLES`, imported, never re-defined).

The output is strictly descriptive: a trend is a description of what the numbers
did, never a verdict, never a cause, and never an instruction. That keeps the
long-window views inside the shame-free invariant just like the daily report.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .thresholds import MIN_SAMPLES

# A |slope-per-day| below this reads as "steady" rather than a direction — small
# enough to ignore day-to-day drift, big enough that a real monthly change shows.
_STEADY_EPS: float = 0.01

# Neutral, human metric labels for the rendered prose.
_LABELS: dict[str, str] = {
    "sleep_hr": "sleep hours",
    "hrv_ms": "heart-rate variability",
    "resting_hr": "resting heart rate",
    "mood": "subjective mood",
    "gut": "subjective gut feeling",
    "llm_cost": "model usage",
    "attention": "activity density",
}


@dataclass(frozen=True)
class TrendResult:
    metric: str
    n: int
    slope: float
    direction: str  # "increasing" | "decreasing" | "steady" | "insufficient-data"
    baseline_ready: bool
    summary: str

    @property
    def label(self) -> str:
        return _LABELS.get(self.metric, self.metric)


def _least_squares_slope(ys: list[float]) -> float:
    """Slope of y vs index (days). 0.0 if degenerate."""
    n = len(ys)
    if n < 2:
        return 0.0
    xs = list(range(n))
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    num = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    den = sum((x - mean_x) ** 2 for x in xs)
    if den == 0.0:
        return 0.0
    return num / den


def trend_over(series: list[tuple[Any, float]], metric: str) -> TrendResult:
    """Describe the direction of ``metric`` over ``series`` (a long window).

    Below :data:`MIN_SAMPLES` points the trend is suppressed (``direction =
    "insufficient-data"``) — a slope fit on a handful of days is noise, and
    presenting it would be a false signal.
    """
    label = _LABELS.get(metric, metric)
    n = len(series)
    if n < MIN_SAMPLES:
        return TrendResult(
            metric=metric,
            n=n,
            slope=0.0,
            direction="insufficient-data",
            baseline_ready=False,
            summary=(
                f"{n}/{MIN_SAMPLES} days of {label} so far — the trend stays in "
                "baseline mode until the window fills."
            ),
        )

    ys = [float(v) for (_, v) in series]
    slope = _least_squares_slope(ys)
    if abs(slope) < _STEADY_EPS:
        direction = "steady"
        summary = (
            f"Over {n} days, {label} held roughly steady. This is a description "
            "of the trend, not a verdict."
        )
    else:
        direction = "increasing" if slope > 0 else "decreasing"
        summary = (
            f"Over {n} days, {label} trended {direction} "
            f"(~{slope:+.3f}/day). This is a description of the trend, not a "
            "verdict and not a cause."
        )
    return TrendResult(
        metric=metric,
        n=n,
        slope=round(slope, 4),
        direction=direction,
        baseline_ready=True,
        summary=summary,
    )


def render_trend_report(trends: list[TrendResult], period: str = "monthly") -> str:
    """Render a monthly / quarterly trend digest. Always shame-free."""
    from .reporter import shame_free_check  # local import avoids a cycle

    title_period = "quarterly" if period == "quarterly" else "monthly"
    lines: list[str] = []
    lines.append(f"# phantom-companion — {title_period} trends")
    lines.append("")
    lines.append("> Long-window pattern pass. Tone: descriptive, never blame.")
    lines.append("")

    ready = [t for t in trends if t.baseline_ready]
    lines.append("## Trends")
    if ready:
        for t in ready:
            lines.append(f"- **{t.label}**: {t.summary}")
    else:
        lines.append(
            "- Not enough history yet for any long-window trend — still in "
            "baseline mode. Trends unlock once a few weeks of each metric exist."
        )
    lines.append("")

    waiting = [t for t in trends if not t.baseline_ready]
    if waiting:
        lines.append("## Still gathering baseline")
        for t in waiting:
            lines.append(f"- {t.label}: {t.n}/{MIN_SAMPLES} days.")
        lines.append("")

    text = "\n".join(lines).rstrip() + "\n"
    ok, reason = shame_free_check(text)
    if not ok:
        raise RuntimeError(f"refused to emit shame-leaking report: {reason}")
    return text


__all__ = ["TrendResult", "trend_over", "render_trend_report"]

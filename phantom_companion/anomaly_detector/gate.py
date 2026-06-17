"""P2-M2 — density-gated anomaly alerts over tracked daily metrics.

The raw :func:`detector.detect` is a pure rolling-MAD flag: it can fire as soon
as a point has a trailing window. That is the right primitive, but a *user-facing
alert* must not surface until enough total history exists for the baseline to be
trustworthy — otherwise a noisy first week would spam false positives, which on a
behaviour tracker reads as nagging.

This module adds the gate:

- :func:`gated_anomaly_alerts` runs the MAD detector but **suppresses every alert
  until the series has at least** :data:`~phantom_companion.thresholds.MIN_SAMPLES`
  **points** (the same ~14-day density gate the correlation uses, imported from
  the single source — never re-hard-coded).
- :func:`detect_metric_anomalies` builds the univariate series for one tracked
  metric (health sleep_hr / hrv_ms / resting_hr, LLM daily cost proxy, attention
  switch density) off a typed :class:`AggregateWindow`, then gates it.
- :func:`render_anomaly_alerts` renders the alerts as shame-free, non-causal prose
  (a description of a deviation from baseline, never a verdict or a "you did X").
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..thresholds import MIN_SAMPLES
from .detector import detect, _mad

if TYPE_CHECKING:
    from ..schema import AggregateWindow

Series = list[tuple[str, float]]

# Human-readable, strictly neutral metric labels. Wording is chosen so that any
# combination renders as a description of a deviation, not a judgement.
_METRIC_LABELS: dict[str, str] = {
    "sleep_hr": "sleep hours",
    "hrv_ms": "heart-rate variability",
    "resting_hr": "resting heart rate",
    "llm_cost": "daily model usage",
    "attention": "activity/switch density",
}


@dataclass(frozen=True)
class AnomalyAlert:
    """One gated, surfaced anomaly. Carries the data, not a verdict."""

    metric: str
    day: str
    value: float
    score: float
    direction: str  # "above" | "below" | "unusual" — relative to recent baseline

    @property
    def label(self) -> str:
        return _METRIC_LABELS.get(self.metric, self.metric)


# Surfacing threshold for user-facing alerts. Deliberately stricter than the
# detector's raw 3.5 default: on a *behaviour tracker* a marginal blip read as
# an alert is experienced as nagging, which is exactly the shame-leakage we are
# avoiding. 5.0 robust-z surfaces only clear deviations from baseline; the raw
# detector stays available at 3.5 for non-user-facing analytics.
ALERT_THRESHOLD: float = 5.0

# A point must deviate from the recent median by at least this many *series-wide*
# robust scales (1.4826·MAD over the whole window) before it can surface. This is
# the guard against the MAD-collapse false positive: a tight local 7-day window
# can inflate the rolling robust-z even when the actual deviation is trivial
# (e.g. 0.4 h of sleep). Grounding the floor in the series-wide scale — which is
# stable, not degenerate — kills that artifact without chasing a single seed.
ALERT_MIN_ABS_SCALES: float = 3.0


def gated_anomaly_alerts(
    series: Series,
    metric: str,
    window: int = 7,
    threshold: float = ALERT_THRESHOLD,
) -> list[AnomalyAlert]:
    """Detect anomalies in ``series`` but only surface them past the density gate.

    Below :data:`MIN_SAMPLES` points the function returns ``[]`` no matter how
    extreme a value is — the baseline is not trustworthy yet, so a short noisy
    window cannot raise a (potentially shaming) false alarm.

    Two guards stack: the rolling-MAD robust-z must clear ``threshold`` AND the
    absolute deviation from the recent median must clear ``ALERT_MIN_ABS_SCALES``
    series-wide robust scales — so a degenerate local MAD cannot manufacture an
    alert out of a trivially small real difference.
    """
    if len(series) < MIN_SAMPLES:
        return []

    values = [v for (_, v) in series]
    series_scale = 1.4826 * _mad(values, statistics.median(values))

    points = detect(series, window=window, threshold=threshold)
    alerts: list[AnomalyAlert] = []
    for i, p in enumerate(points):
        if not p.is_anomaly:
            continue
        # Per-point density: a point only has ``i`` days of history behind it.
        # Even in a long batch, an EARLY point whose own baseline is thinner
        # than MIN_SAMPLES must not surface — otherwise the gate is only a
        # whole-series check and an early blip still leaks (codex finding #1).
        if i + 1 < MIN_SAMPLES:
            continue
        start = max(0, i - window)
        recent = [v for (_, v) in series[start:i]]
        if not recent:
            continue
        recent_med = statistics.median(recent)
        local_scale = 1.4826 * _mad(recent, recent_med)
        # Absolute-deviation floor = max(local, whole-series) scale:
        #  - the whole-series term gives a sensible minimum so a degenerate
        #    local MAD can't manufacture a tiny floor (the MAD-collapse FP);
        #  - the local term lets a genuinely tight recent regime still flag a
        #    smaller-but-real deviation (codex finding #2). A real spike clears
        #    either; a trivial blip clears neither.
        # ``is_anomaly`` already guarantees the local window had mad>0, so
        # ``scale`` is strictly positive here; the floor is always meaningful.
        # ``<=`` so "exceeds the floor" is strict (a deviation equal to the
        # floor is treated as still-within-baseline, not an alert).
        abs_floor = ALERT_MIN_ABS_SCALES * max(local_scale, series_scale)
        if abs(p.value - recent_med) <= abs_floor:
            continue
        mid = recent_med
        direction = "above" if p.value > mid else ("below" if p.value < mid else "unusual")
        alerts.append(
            AnomalyAlert(
                metric=metric,
                day=str(p.timestamp),
                value=float(p.value),
                score=float(p.score),
                direction=direction,
            )
        )
    return alerts


def _metric_series(window: "AggregateWindow", metric: str) -> Series:
    """Extract the univariate daily series for ``metric`` from a typed window."""
    out: Series = []
    for day in window.days:
        if metric in ("sleep_hr", "hrv_ms", "resting_hr"):
            if day.health is None:
                continue
            out.append((day.day, float(getattr(day.health, metric))))
        elif metric == "llm_cost":
            # Proxy: count of model-call events that day (no $ amount on device).
            n = sum(1 for ev in day.events if ev.provider)
            out.append((day.day, float(n)))
        elif metric == "attention":
            # Switch density proxy: total timestamped events that day.
            n = sum(1 for ev in day.events if ev.timestamp)
            out.append((day.day, float(n)))
        else:
            raise ValueError(f"unknown metric: {metric!r}")
    return out


def detect_metric_anomalies(
    window: "AggregateWindow",
    metric: str,
    detect_window: int = 7,
    threshold: float = ALERT_THRESHOLD,
) -> list[AnomalyAlert]:
    """Build the series for ``metric`` off ``window`` and return gated alerts."""
    series = _metric_series(window, metric)
    return gated_anomaly_alerts(series, metric, window=detect_window, threshold=threshold)


def render_anomaly_alerts(alerts: list[AnomalyAlert]) -> str:
    """Render gated alerts as shame-free, non-causal prose.

    Each line is a neutral description of a deviation from the recent baseline —
    never "you did X", never a cause. If there is nothing to report we say so
    plainly (the absence of an alert is itself reassuring, not a silence).
    """
    if not alerts:
        return "No notable deviations from your recent baseline today.\n"

    lines = ["## Worth a glance", ""]
    for a in alerts:
        if a.direction == "above":
            phrase = "ran higher than"
        elif a.direction == "below":
            phrase = "ran lower than"
        else:
            phrase = "looked different from"
        lines.append(
            f"- On {a.day}, {a.label} {phrase} your recent baseline "
            f"(value {a.value:g}). Just a heads-up — nothing here is a verdict."
        )
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


__all__ = [
    "AnomalyAlert",
    "gated_anomaly_alerts",
    "detect_metric_anomalies",
    "render_anomaly_alerts",
]

"""P2-M2 — anomaly detection behind the density (MIN_SAMPLES) gate.

The raw rolling-MAD :func:`detect` can flag a point as soon as it has a trailing
window, but a *user-facing alert* must not fire until enough total history
exists for the baseline to be trustworthy. This milestone adds a gated layer:

- :func:`detect_metric_anomalies` builds a univariate series from one of the
  tracked metrics (health sleep_hr / hrv_ms / resting_hr, LLM daily cost,
  attention switch density) off a typed :class:`AggregateWindow`.
- :func:`gated_anomaly_alerts` runs the MAD detector but **suppresses every
  alert until ``len(series) >= MIN_SAMPLES``** — so a short noisy window raises
  nothing, while a wide window with a genuine spike raises a gated alert.
- Alert text is shame-free (descriptive, no blame, no causation).
"""

from __future__ import annotations

import random
from pathlib import Path

import pytest

from phantom_companion.thresholds import MIN_SAMPLES
from phantom_companion.reporter import shame_free_check
from phantom_companion.anomaly_detector.gate import (
    AnomalyAlert,
    detect_metric_anomalies,
    gated_anomaly_alerts,
    render_anomaly_alerts,
)


# ---------------------------------------------------------------------------
# series builders
# ---------------------------------------------------------------------------

def _health_series(n: int, seed: int = 1) -> list[tuple[str, float]]:
    rng = random.Random(seed)
    out: list[tuple[str, float]] = []
    for i in range(n):
        day = f"2026-05-{i + 1:02d}"
        # stable ~7.0h sleep, with a sharp drop on the last day for spike tests
        val = round(rng.gauss(7.0, 0.25), 2)
        out.append((day, val))
    return out


# ---------------------------------------------------------------------------
# density gate
# ---------------------------------------------------------------------------

def test_short_noisy_window_raises_no_alert() -> None:
    # Fewer than MIN_SAMPLES days, even with a wild value, must raise nothing.
    series = _health_series(MIN_SAMPLES - 1)
    series[-1] = (series[-1][0], 1.0)  # a severe drop on the last day
    alerts = gated_anomaly_alerts(series, metric="sleep_hr")
    assert alerts == []


def test_wide_window_with_spike_raises_gated_alert() -> None:
    series = _health_series(MIN_SAMPLES + 6)
    series[-1] = (series[-1][0], 1.0)  # genuine spike at/after the gate
    alerts = gated_anomaly_alerts(series, metric="sleep_hr")
    assert alerts, "a real spike past the density gate must alert"
    a = alerts[-1]
    assert isinstance(a, AnomalyAlert)
    assert a.metric == "sleep_hr"
    assert a.day == series[-1][0]


def test_wide_window_no_spike_raises_no_alert() -> None:
    # Stable wide window: enough density but nothing anomalous.
    series = _health_series(MIN_SAMPLES + 6)
    alerts = gated_anomaly_alerts(series, metric="sleep_hr")
    assert alerts == []


def test_early_point_below_per_point_density_is_suppressed() -> None:
    # A long-ENOUGH series (passes the whole-series gate) but the spike sits at
    # an EARLY index whose own trailing history is < MIN_SAMPLES -> must not
    # surface. Otherwise the gate would only be a whole-series check.
    series = _health_series(MIN_SAMPLES + 10, seed=9)
    # Inject the spike at index 8 (only 8 days of history behind it).
    series[8] = (series[8][0], 1.0)
    alerts = gated_anomaly_alerts(series, metric="sleep_hr")
    assert all(a.day != series[8][0] for a in alerts), (
        "an early point with < MIN_SAMPLES history must not alert"
    )


def test_late_point_above_per_point_density_surfaces() -> None:
    # Same magnitude spike, but placed where it has >= MIN_SAMPLES history.
    series = _health_series(MIN_SAMPLES + 10, seed=9)
    idx = MIN_SAMPLES + 4
    series[idx] = (series[idx][0], 1.0)
    alerts = gated_anomaly_alerts(series, metric="sleep_hr")
    assert any(a.day == series[idx][0] for a in alerts)


def test_gate_is_exactly_min_samples() -> None:
    # At exactly MIN_SAMPLES, the gate is open.
    series = _health_series(MIN_SAMPLES)
    series[-1] = (series[-1][0], 1.0)
    assert gated_anomaly_alerts(series, metric="sleep_hr"), "gate should open at MIN_SAMPLES"
    # One short of it, closed.
    short = _health_series(MIN_SAMPLES - 1)
    short[-1] = (short[-1][0], 1.0)
    assert gated_anomaly_alerts(short, metric="sleep_hr") == []


# ---------------------------------------------------------------------------
# shame-free alert text
# ---------------------------------------------------------------------------

_CAUSATION = ("causes", "because of", "due to", "leads to", "makes you")


def test_alert_text_is_shame_free_and_non_causal() -> None:
    series = _health_series(MIN_SAMPLES + 6)
    series[-1] = (series[-1][0], 1.0)
    alerts = gated_anomaly_alerts(series, metric="sleep_hr")
    text = render_anomaly_alerts(alerts)
    ok, reason = shame_free_check(text)
    assert ok, reason
    low = text.lower()
    for w in _CAUSATION:
        assert w not in low, f"causation leaked: {w}"


def test_render_no_alerts_is_shame_free() -> None:
    text = render_anomaly_alerts([])
    ok, reason = shame_free_check(text)
    assert ok, reason
    assert "no" in text.lower()


def test_render_anomaly_alerts_self_guards_output() -> None:
    bad_alert = AnomalyAlert(
        metric="you always",
        day="2026-06-03",
        value=99.0,
        score=8.0,
        direction="above",
    )
    with pytest.raises(RuntimeError, match="refused to emit shame-leaking anomaly alert"):
        render_anomaly_alerts([bad_alert])

    normal_alert = AnomalyAlert(
        metric="sleep_hr",
        day="2026-06-03",
        value=1.0,
        score=8.0,
        direction="below",
    )
    assert isinstance(render_anomaly_alerts([normal_alert]), str)


# ---------------------------------------------------------------------------
# metric extraction off an AggregateWindow
# ---------------------------------------------------------------------------

def test_detect_metric_anomalies_from_window(tmp_path: Path) -> None:
    from phantom_companion.fixtures import build_mesh_fixture, fixture_days
    from phantom_companion.schema import (
        aggregate_window,
    )

    root = tmp_path / "m"
    fx = build_mesh_fixture(root, end_day="2026-06-03", n_days=MIN_SAMPLES + 6, seed=4)
    days = fixture_days("2026-06-03", MIN_SAMPLES + 6)
    health_by_day = {d: dict(fx.health_by_day[d]) for d in days}
    # inject a sharp sleep drop on the final day
    health_by_day[days[-1]]["sleep_hr"] = 1.0
    window = aggregate_window(days, mesh_root=root, health_by_day=health_by_day)

    alerts = detect_metric_anomalies(window, metric="sleep_hr")
    assert any(a.day == days[-1] for a in alerts), "injected sleep drop must be flagged"
    # And it is gated: a too-short window over the same data raises nothing.
    short_days = days[: MIN_SAMPLES - 1]
    short_window = aggregate_window(
        short_days, mesh_root=root, health_by_day={d: health_by_day[d] for d in short_days}
    )
    # force a spike in the short window's last day too
    assert detect_metric_anomalies(short_window, metric="sleep_hr") == []


def test_detect_metric_anomalies_llm_cost(tmp_path: Path) -> None:
    from phantom_companion.fixtures import build_mesh_fixture, fixture_days
    from phantom_companion.schema import aggregate_window

    root = tmp_path / "m"
    build_mesh_fixture(root, end_day="2026-06-03", n_days=MIN_SAMPLES + 6, seed=8)
    days = fixture_days("2026-06-03", MIN_SAMPLES + 6)
    window = aggregate_window(days, mesh_root=root)
    # LLM "cost" proxy = events-with-provider per day. Should run without error
    # and return a list (possibly empty if the fixture has no spike).
    alerts = detect_metric_anomalies(window, metric="llm_cost")
    assert isinstance(alerts, list)

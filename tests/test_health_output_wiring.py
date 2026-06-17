"""P1-M3 — wire real ④ secure-connector health + git output into the daily
report, behind the MIN_SAMPLES statistical gate.

The Tier-1 reporter hard-coded ``analyze_health_vs_output(health_data={},
commits=[])`` so the health/output insight could never fire. This milestone:

1. parses a ④ secure-connector daily export (sleep_hr, hrv_ms, resting_hr,
   activity, source) into a typed :class:`HealthSample`;
2. fills :class:`DayAggregate.health` / ``.output`` from the export streams;
3. removes the hard-code in :func:`reporter._run_insights`, sourcing health +
   commits from the aggregate;
4. below MIN_SAMPLES → directional single-day summary only; at/above → a real
   Pearson AND Spearman correlation with NO causation language;
5. below/above-threshold/missing-source fixtures all stay shame-free.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from phantom_companion.aggregator import DailyAggregate
from phantom_companion.health_ingest import (
    HealthExportError,
    parse_secure_connector_export,
)
from phantom_companion.schema import HealthSample, OutputSample
from phantom_companion.insight_modules.health_productivity_correlation import (
    correlate_health_output,
)
from phantom_companion.reporter import (
    render_daily_report,
    shame_free_check,
)
from phantom_companion.fixtures import build_mesh_fixture, fixture_days


# ---------------------------------------------------------------------------
# 1. secure-connector export parser
# ---------------------------------------------------------------------------

def test_parse_export_reads_documented_fields() -> None:
    raw = {
        "day": "2026-05-22",
        "sleep_hr": 7.4,
        "hrv_ms": 56.0,
        "resting_hr": 54,
        "activity_min": 41,
        "source": "garmin",
    }
    sample = parse_secure_connector_export(raw)
    assert isinstance(sample, HealthSample)
    assert sample.day == "2026-05-22"
    assert sample.sleep_hr == 7.4
    assert sample.hrv_ms == 56.0
    assert sample.resting_hr == 54
    assert sample.activity_min == 41
    assert sample.source == "garmin"


def test_parse_export_tolerates_apple_healthkit_keys() -> None:
    # Apple HealthKit Shortcut export uses camelCase / minute units.
    raw = {
        "date": "2026-05-22",
        "sleepHours": "7.10",
        "heartRateVariability": 60,
        "restingHeartRate": "52",
        "activeMinutes": "55",
        "source": "apple_health",
    }
    sample = parse_secure_connector_export(raw)
    assert sample.day == "2026-05-22"
    assert sample.sleep_hr == pytest.approx(7.10)
    assert sample.hrv_ms == pytest.approx(60.0)
    assert sample.resting_hr == 52
    assert sample.activity_min == 55
    assert sample.source == "apple_health"


def test_parse_export_missing_source_defaults_to_unknown() -> None:
    sample = parse_secure_connector_export({"day": "2026-05-22", "sleep_hr": 6.0})
    assert sample.source == "unknown"


def test_parse_export_rejects_missing_day() -> None:
    with pytest.raises(HealthExportError):
        parse_secure_connector_export({"sleep_hr": 6.0})


# ---------------------------------------------------------------------------
# 2. correlation gate: directional below, statistical above, no causation
# ---------------------------------------------------------------------------

_CAUSATION_WORDS = (
    "causes",
    "caused",
    "because of",
    "due to",
    "leads to",
    "results in",
    "makes you",
)


def _assert_no_causation(text: str) -> None:
    low = text.lower()
    for word in _CAUSATION_WORDS:
        assert word not in low, f"causation claim leaked: {word!r} in {text!r}"


def test_below_threshold_is_directional_only() -> None:
    short = [
        {"sleep_hr": 7.0 + (i % 2), "commits": 1 + (i % 3)}
        for i in range(5)
    ]
    out = correlate_health_output(short)
    assert out["baseline_ready"] is False
    # No pearson/spearman number is exposed below the gate.
    assert "pearson_r" not in out["details"]
    assert "spearman_r" not in out["details"]
    _assert_no_causation(out["summary"])


def test_above_threshold_reports_pearson_and_spearman_no_causation() -> None:
    from phantom_companion.thresholds import MIN_SAMPLES

    samples = [
        {"sleep_hr": 5.0 + 0.2 * i, "commits": i}
        for i in range(MIN_SAMPLES)
    ]
    out = correlate_health_output(samples)
    assert out["baseline_ready"] is True
    assert "pearson_r" in out["details"]
    assert "spearman_r" in out["details"]
    # Monotone construction → both strongly positive.
    assert out["details"]["pearson_r"] > 0.9
    assert out["details"]["spearman_r"] > 0.9
    # Descriptive, never causal.
    _assert_no_causation(out["summary"])
    assert "not a verdict" in out["summary"].lower() or "description" in out["summary"].lower()
    ok, reason = shame_free_check(out["summary"])
    assert ok, reason


# ---------------------------------------------------------------------------
# 3. reporter wiring: health/output sourced from the aggregate, not hard-coded
# ---------------------------------------------------------------------------

def _agg_with_health(monkeypatch: pytest.MonkeyPatch) -> DailyAggregate:
    return DailyAggregate(
        day="2026-05-22",
        health=HealthSample(
            day="2026-05-22", sleep_hr=7.5, hrv_ms=58.0, resting_hr=52, source="garmin"
        ),
        output=OutputSample(day="2026-05-22", commits=4, lines_changed=120),
    )


def test_daily_report_uses_real_health_output(monkeypatch: pytest.MonkeyPatch) -> None:
    from phantom_companion import reporter as rep

    monkeypatch.setattr(rep, "_invoke_coach", lambda _day: None)
    agg = _agg_with_health(monkeypatch)
    text = render_daily_report(agg)
    # The health insight must now FIRE (it had real data), not say "Waiting on".
    assert "health_productivity_correlation" in text
    assert "Waiting on: health" not in text
    _assert_no_causation(text)
    ok, reason = shame_free_check(text)
    assert ok, reason


def test_daily_report_missing_health_is_directional_and_shame_free(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from phantom_companion import reporter as rep

    monkeypatch.setattr(rep, "_invoke_coach", lambda _day: None)
    # No health/output attached → directional "waiting on" summary, still clean.
    agg = DailyAggregate(day="2026-05-22")
    text = render_daily_report(agg)
    assert "health_productivity_correlation" in text
    _assert_no_causation(text)
    ok, reason = shame_free_check(text)
    assert ok, reason


def test_daily_report_below_threshold_offline_fixture_is_shame_free(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from phantom_companion import reporter as rep

    monkeypatch.setattr(rep, "_invoke_coach", lambda _day: None)
    root = tmp_path / "m"
    fx = build_mesh_fixture(root, end_day="2026-05-22", n_days=3, seed=21)
    # A single below-threshold day with health attached.
    from phantom_companion.aggregator import aggregate_day

    base = aggregate_day("2026-05-22", mesh_root=root)
    h = fx.health_by_day["2026-05-22"]
    agg = DailyAggregate(
        day=base.day,
        events=base.events,
        satellite_logs=base.satellite_logs,
        heartbeats=base.heartbeats,
        ai_feed_log=base.ai_feed_log,
        flow_log=base.flow_log,
        health=HealthSample(day="2026-05-22", source="garmin", **h),
        output=OutputSample(day="2026-05-22", commits=len(fx.commits_by_day["2026-05-22"])),
    )
    text = render_daily_report(agg)
    _assert_no_causation(text)
    ok, reason = shame_free_check(text)
    assert ok, reason

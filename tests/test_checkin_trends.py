"""P3-M2 — nightly subjective check-in + monthly/quarterly trend rollups.

The spec's nightly "1 line" (gut 1-5, mood 1-5, sleep hr) is a structured,
local-only subjective record. Monthly/quarterly views lift the daily + check-in
streams into long-window *trend* descriptions — direction only, behind the same
density gate, and strictly shame-free (a trend is a description, never a verdict).
"""

from __future__ import annotations

import random
from pathlib import Path

import pytest

from phantom_companion.thresholds import MIN_SAMPLES
from phantom_companion.reporter import shame_free_check
from phantom_companion.checkin import (
    SubjectiveCheckin,
    CheckinParseError,
    parse_checkin_line,
)
from phantom_companion.trends import (
    TrendResult,
    trend_over,
    render_trend_report,
)


# ---------------------------------------------------------------------------
# nightly subjective check-in
# ---------------------------------------------------------------------------

def test_parse_structured_checkin_line() -> None:
    c = parse_checkin_line("2026-05-22 gut=4 mood=3 sleep=7.2")
    assert isinstance(c, SubjectiveCheckin)
    assert c.day == "2026-05-22"
    assert c.gut == 4
    assert c.mood == 3
    assert c.sleep_hr == pytest.approx(7.2)


def test_parse_checkin_shorthand_csv() -> None:
    # The terse "1 line" form: date, gut, mood, sleep.
    c = parse_checkin_line("2026-05-22, 5, 4, 6.8")
    assert c.day == "2026-05-22"
    assert c.gut == 5
    assert c.mood == 4
    assert c.sleep_hr == pytest.approx(6.8)


def test_parse_checkin_clamps_scale() -> None:
    # 1-5 scales are clamped, never rejected (no shame for "wrong" input).
    c = parse_checkin_line("2026-05-22 gut=9 mood=0 sleep=8")
    assert c.gut == 5
    assert c.mood == 1


def test_parse_checkin_requires_a_date() -> None:
    with pytest.raises(CheckinParseError):
        parse_checkin_line("gut=4 mood=3 sleep=7")


def test_checkin_roundtrips() -> None:
    c = SubjectiveCheckin(day="2026-05-22", gut=4, mood=3, sleep_hr=7.2)
    assert SubjectiveCheckin.from_dict(c.to_dict()) == c


# ---------------------------------------------------------------------------
# monthly / quarterly trends
# ---------------------------------------------------------------------------

def _rising(n: int) -> list[tuple[str, float]]:
    return [(f"d{i:03d}", 5.0 + 0.1 * i) for i in range(n)]


def _flat_noisy(n: int, seed: int = 2) -> list[tuple[str, float]]:
    rng = random.Random(seed)
    return [(f"d{i:03d}", round(rng.gauss(7.0, 0.2), 2)) for i in range(n)]


def test_trend_below_density_gate_is_directionless() -> None:
    out = trend_over(_rising(MIN_SAMPLES - 1), metric="sleep_hr")
    assert out.baseline_ready is False
    assert out.direction == "insufficient-data"
    # No slope number is asserted as meaningful below the gate.
    ok, reason = shame_free_check(out.summary)
    assert ok, reason


def test_trend_rising_series_is_increasing() -> None:
    out = trend_over(_rising(30), metric="sleep_hr")
    assert out.baseline_ready is True
    assert out.direction == "increasing"
    assert out.slope > 0
    ok, reason = shame_free_check(out.summary)
    assert ok, reason


def test_trend_flat_series_is_steady() -> None:
    out = trend_over(_flat_noisy(90), metric="sleep_hr")
    assert out.baseline_ready is True
    assert out.direction in {"steady", "increasing", "decreasing"}
    # A near-zero slope must read as "steady".
    assert abs(out.slope) < 0.05
    assert out.direction == "steady"


def test_trend_summary_has_no_causation_or_shame() -> None:
    out = trend_over(_rising(90), metric="resting_hr")
    low = out.summary.lower()
    for w in ("causes", "because of", "due to", "leads to", "you should", "you must"):
        assert w not in low, f"leaked: {w}"
    ok, reason = shame_free_check(out.summary)
    assert ok, reason


def test_render_trend_report_monthly_is_shame_free() -> None:
    trends = [
        trend_over(_rising(30), metric="sleep_hr"),
        trend_over(_flat_noisy(30), metric="mood"),
    ]
    text = render_trend_report(trends, period="monthly")
    assert text.startswith("# phantom-companion — monthly trends")
    ok, reason = shame_free_check(text)
    assert ok, reason


def test_render_trend_report_quarterly_handles_baseline() -> None:
    # All series too short -> the report still renders, in baseline language.
    trends = [trend_over(_rising(5), metric="sleep_hr")]
    text = render_trend_report(trends, period="quarterly")
    assert text.startswith("# phantom-companion — quarterly trends")
    assert "baseline" in text.lower()
    ok, reason = shame_free_check(text)
    assert ok, reason


def test_trend_from_checkins_end_to_end() -> None:
    # A month of nightly check-ins -> a mood trend.
    lines = [f"2026-05-{(i % 28) + 1:02d} gut=4 mood={1 + (i % 5)} sleep=7" for i in range(30)]
    checkins = [parse_checkin_line(s) for s in lines]
    series = [(c.day, float(c.mood)) for c in checkins]
    out = trend_over(series, metric="mood")
    assert out.baseline_ready is True
    ok, reason = shame_free_check(out.summary)
    assert ok, reason

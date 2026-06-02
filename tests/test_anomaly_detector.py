"""Tests for the time-series anomaly detector.

Fixture: 30 days of synthetic sleep_score data ~ N(80, 5) with two injected
anomalies on day 12 (sleep_score=20, severe drop) and day 25 (sleep_score=10).
Both must be flagged; normal days must not be flagged (FP <= 1 allowance).
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from phantom_companion.anomaly_detector.detector import detect, calibrate_threshold  # noqa: E402


def _make_series(seed: int = 42):
    rng = random.Random(seed)
    series = []
    labels = []
    for day in range(30):
        if day == 12:
            val = 20.0
            lbl = True
        elif day == 25:
            val = 10.0
            lbl = True
        else:
            val = rng.gauss(80, 5)
            lbl = False
        series.append((f"2026-05-{day+1:02d}", val))
        labels.append(lbl)
    return series, labels


def test_both_injected_anomalies_flagged():
    series, labels = _make_series()
    out = detect(series, window=7, threshold=3.5)
    flagged_idx = {i for i, p in enumerate(out) if p.is_anomaly}
    assert 12 in flagged_idx, f"day 12 missed; flagged={flagged_idx}"
    assert 25 in flagged_idx, f"day 25 missed; flagged={flagged_idx}"


def test_false_positive_rate_low():
    series, labels = _make_series()
    out = detect(series, window=7, threshold=3.5)
    false_positives = sum(
        1 for i, p in enumerate(out)
        if p.is_anomaly and not labels[i]
    )
    # Allow at most 1 FP across 28 normal days — robust z with MAD should be
    # very tight on N(80,5) data.
    assert false_positives <= 1, f"too many FPs: {false_positives}"


def test_score_monotone_with_severity():
    # A more extreme drop should produce a strictly higher score than a mild
    # one, ceteris paribus.
    base = [(i, 80.0) for i in range(10)]
    mild = base + [(10, 70.0)]
    severe = base + [(10, 20.0)]
    s_mild = detect(mild, window=7)[-1].score
    s_severe = detect(severe, window=7)[-1].score
    assert s_severe > s_mild


def test_empty_and_short_series_safe():
    assert detect([]) == []
    out = detect([("t0", 1.0)])
    assert len(out) == 1
    assert out[0].is_anomaly is False


def test_calibrate_threshold_returns_valid_candidate():
    series, labels = _make_series()
    thr = calibrate_threshold(series, labels, window=7)
    assert thr in {2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0}
    # And running detect with the calibrated threshold still catches both
    # injected anomalies (the calibration objective is F1, so this should hold
    # unless the threshold sweep degenerates).
    out = detect(series, window=7, threshold=thr)
    flagged = {i for i, p in enumerate(out) if p.is_anomaly}
    assert 12 in flagged and 25 in flagged

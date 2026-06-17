"""Cross-cutting SHAME-FREE invariant: EVERY text the companion can emit — daily,
weekly rollup, anomaly alerts, monthly/quarterly trends, and the relay payload —
must pass the shame-free lint. This is the BIG-GOAL operational invariant; if any
new emitter is added it should be exercised here.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

import pytest

from phantom_companion.thresholds import MIN_SAMPLES
from phantom_companion.reporter import (
    render_daily_report,
    render_weekly_report,
    render_weekly_report_from_window,
    shame_free_check,
)
from phantom_companion.anomaly_detector.gate import (
    gated_anomaly_alerts,
    render_anomaly_alerts,
)
from phantom_companion.trends import trend_over, render_trend_report
from phantom_companion.notify import Notification, minimize_payload
from phantom_companion.fixtures import build_mesh_fixture, fixture_days
from phantom_companion.schema import aggregate_window
from phantom_companion.aggregator import aggregate_day, aggregate_range


# ---------------------------------------------------------------------------
# the lint now also catches English blame/shame
# ---------------------------------------------------------------------------

def test_lint_rejects_english_shame() -> None:
    for bad in (
        "You always skip your workout.",
        "You never finish what you start.",
        "You failed to apply to 5 companies.",
        "You keep staying up late.",
        "You should have slept earlier.",
        "Late yet again.",
    ):
        ok, reason = shame_free_check(bad)
        assert ok is False, f"expected rejection: {bad}"
        assert "shame" in reason


def test_lint_allows_descriptive_english() -> None:
    for clean in (
        "Your weekly review is ready on your device.",
        "Activity ran higher than your recent baseline.",
        "Over 30 days, sleep hours trended increasing.",
        "Your sleep hours held roughly steady.",
    ):
        ok, reason = shame_free_check(clean)
        assert ok is True, f"unexpected rejection ({reason}): {clean}"


# ---------------------------------------------------------------------------
# every emitter, against a multi-source fixture
# ---------------------------------------------------------------------------

def _series(n: int, spike: bool = False, seed: int = 1):
    rng = random.Random(seed)
    out = [(f"2026-05-{i + 1:02d}", round(rng.gauss(7.0, 0.25), 2)) for i in range(n)]
    if spike:
        out[-1] = (out[-1][0], 1.0)
    return out


def test_all_emitters_are_shame_free(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from phantom_companion import reporter as rep

    monkeypatch.setattr(rep, "_invoke_coach", lambda _day: None)

    root = tmp_path / "m"
    build_mesh_fixture(root, end_day="2026-05-22", n_days=MIN_SAMPLES, seed=20)
    days = fixture_days("2026-05-22", MIN_SAMPLES)

    emitted: list[str] = []

    # daily
    emitted.append(render_daily_report(aggregate_day("2026-05-22", mesh_root=root)))
    # weekly (legacy + rollup)
    aggs = list(aggregate_range(fixture_days("2026-05-22", 7), mesh_root=root).values())
    emitted.append(render_weekly_report(aggs))
    window = aggregate_window(days, mesh_root=root)
    emitted.append(render_weekly_report_from_window(window))
    # anomaly alerts (gated, with a spike)
    alerts = gated_anomaly_alerts(_series(MIN_SAMPLES + 6, spike=True), metric="sleep_hr")
    emitted.append(render_anomaly_alerts(alerts))
    emitted.append(render_anomaly_alerts([]))
    # trends (monthly + quarterly, ready + baseline)
    emitted.append(
        render_trend_report(
            [trend_over([(f"d{i}", 5.0 + 0.1 * i) for i in range(30)], "sleep_hr")],
            period="monthly",
        )
    )
    emitted.append(
        render_trend_report(
            [trend_over([("d0", 7.0), ("d1", 7.1)], "mood")], period="quarterly"
        )
    )
    # relay payload
    emitted.append(
        json.dumps(
            minimize_payload(Notification(kind="weekly_digest", title="t", body="b")),
            ensure_ascii=False,
        )
    )

    for text in emitted:
        ok, reason = shame_free_check(text)
        assert ok, f"emitter leaked shame: {reason}\n---\n{text[:400]}"

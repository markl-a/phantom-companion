"""Reporter MUST always emit shame-free text. This is a BIG-GOAL invariant."""

from __future__ import annotations

from pathlib import Path

import pytest

from phantom_companion.aggregator import DailyAggregate, aggregate_day
from phantom_companion.reporter import (
    render_daily_report,
    render_weekly_report,
    shame_free_check,
    write_daily_report,
)


def test_lint_rejects_known_shame_patterns() -> None:
    for bad in ("你又吃垃圾食物", "你終於做了", "你居然會", "你怎麼又熬夜", "還不去運動"):
        ok, reason = shame_free_check(bad)
        assert ok is False, f"expected rejection for: {bad}"
        assert "shame" in reason


def test_lint_accepts_clean_text() -> None:
    for clean in (
        "今天三餐熱量在目標範圍內",
        "明天可以試試早上 10 分鐘散步",
        "",
        "Mark, today's report is mostly a baseline snapshot.",
    ):
        ok, reason = shame_free_check(clean)
        assert ok is True, f"unexpected rejection ({reason}): {clean}"


def test_daily_report_on_empty_mesh_is_shame_free(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Disable the real LLM coach so this stays deterministic/offline.
    from phantom_companion import reporter as rep

    monkeypatch.setattr(rep, "_invoke_coach", lambda _day: None)
    # Use an empty fake mesh root.
    agg = aggregate_day("2026-05-22", mesh_root=tmp_path)
    text = render_daily_report(agg)
    assert text.startswith("# phantom-companion")
    assert "baseline" in text.lower()
    # Even with no coach, a data-driven next-step must be present.
    assert "## Next-step suggestion" in text
    ok, reason = shame_free_check(text)
    assert ok, reason


def test_weekly_report_on_empty_mesh_is_shame_free(tmp_path: Path) -> None:
    aggs = [DailyAggregate(day=f"2026-05-{16+i:02d}") for i in range(7)]
    text = render_weekly_report(aggs)
    assert text.startswith("# phantom-companion")
    ok, reason = shame_free_check(text)
    assert ok, reason


def test_write_daily_report_creates_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from phantom_companion import reporter as rep

    monkeypatch.setattr(rep, "_invoke_coach", lambda _day: None)
    out = tmp_path / "out"
    path = write_daily_report(
        day="2026-05-22",
        out_root=out,
        mesh_root=tmp_path / "mesh",  # nonexistent → empty aggregate
    )
    assert path.exists()
    assert path.read_text(encoding="utf-8").startswith("# phantom-companion")


def test_reporter_refuses_to_emit_shame(monkeypatch: pytest.MonkeyPatch) -> None:
    """If the coach output is dirty, reporter must drop it, not merge it."""
    from phantom_companion import reporter as rep

    monkeypatch.setattr(rep, "_invoke_coach", lambda _day: "# Daily review —\n你又遲到了!")
    agg = DailyAggregate(day="2026-05-22")
    text = rep.render_daily_report(agg)
    # The dirty coach block must NOT be merged into the report.
    assert "你又" not in text


def test_reporter_merges_clean_coach_block(monkeypatch: pytest.MonkeyPatch) -> None:
    """A clean coach review must be merged in and drive the next-step line."""
    from phantom_companion import reporter as rep

    coach = (
        "# Daily review — 2026-05-22\n\n"
        "You stayed focused on AI research today.\n\n"
        "## Tomorrow's one action\n\n"
        "Read the PEEL framework paper."
    )
    monkeypatch.setattr(rep, "_invoke_coach", lambda _day: coach)
    agg = DailyAggregate(day="2026-05-22")
    text = rep.render_daily_report(agg)
    # The real coach narrative must appear (demoted to H2).
    assert "## Daily review — 2026-05-22" in text
    assert "You stayed focused on AI research today." in text
    # Next-step must be driven by the coach's "Tomorrow's one action".
    assert "## Next-step suggestion" in text
    assert "Read the PEEL framework paper." in text
    ok, reason = shame_free_check(text)
    assert ok, reason

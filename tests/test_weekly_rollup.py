"""P2-M1 — weekly cross-satellite pattern summaries.

The Tier-1 weekly report only listed per-day event counts. This milestone lifts
the per-day signal into week-level rollups across the four behavioural lenses —
LLM usage, attention, learning ROI, jobseek follow-up — sourced from a typed
:class:`AggregateWindow` (so it can read straight from the SQLite window cache),
and renders a human-readable, shame-free weekly digest.
"""

from __future__ import annotations

from pathlib import Path

from phantom_companion.fixtures import build_mesh_fixture, fixture_days
from phantom_companion.schema import aggregate_window
from phantom_companion.cache import WindowCache
from phantom_companion.reporter import (
    render_weekly_report,
    render_weekly_report_from_window,
    shame_free_check,
    weekly_rollup,
)


def _window(tmp_path: Path, *, n_days: int = 7, seed: int = 31):
    root = tmp_path / "m"
    build_mesh_fixture(root, end_day="2026-05-22", n_days=n_days, seed=seed)
    days = fixture_days("2026-05-22", n_days)
    return aggregate_window(days, mesh_root=root), days, root


def test_weekly_rollup_aggregates_all_four_lenses(tmp_path: Path) -> None:
    window, _days, _root = _window(tmp_path)
    rollup = weekly_rollup(window)
    # All four behavioural lenses present.
    for lens in ("llm_usage", "attention", "learning_roi", "jobseek"):
        assert lens in rollup, f"missing lens: {lens}"
    # LLM usage rolled up across the week: provider totals + a top provider.
    llm = rollup["llm_usage"]
    assert llm["total_calls"] > 0
    assert llm["by_provider"]  # non-empty Counter-like map
    assert llm["top_provider"] in llm["by_provider"]
    # Jobseek: investigated vs applied vs still-pending across the week.
    job = rollup["jobseek"]
    assert job["investigated"] >= job["applied"]
    assert job["pending"] == job["investigated"] - job["applied"]
    # Learning ROI: items read + engaged summed across the week.
    learn = rollup["learning_roi"]
    assert learn["items_read"] > 0
    # Attention: a busiest hour-of-day across the week (or None if too sparse).
    assert "busiest_hour" in rollup["attention"]


def test_weekly_rollup_counts_match_per_day_sum(tmp_path: Path) -> None:
    window, _days, _root = _window(tmp_path, seed=33)
    rollup = weekly_rollup(window)
    # The week's total LLM calls must equal the per-day provider counts summed.
    per_day_total = 0
    for day in window.days:
        for ev in day.events:
            if ev.provider:
                per_day_total += 1
    assert rollup["llm_usage"]["total_calls"] == per_day_total


def test_render_weekly_from_window_is_human_readable_and_shame_free(
    tmp_path: Path,
) -> None:
    window, _days, _root = _window(tmp_path, seed=35)
    text = render_weekly_report_from_window(window)
    assert text.startswith("# phantom-companion — weekly report")
    # Human-readable rollup sections (not just a per-day count list).
    assert "## LLM usage" in text
    assert "## Attention" in text
    assert "## Learning ROI" in text
    assert "## Jobseek follow-up" in text
    ok, reason = shame_free_check(text)
    assert ok, reason


def test_render_weekly_from_window_reads_from_sqlite_cache(tmp_path: Path) -> None:
    window, days, root = _window(tmp_path, seed=37)
    db = tmp_path / "cache.sqlite"
    cache = WindowCache(db)
    cached = cache.get_or_build(days, mesh_root=root)
    # Rendering off the cached window must equal rendering off the cold build.
    assert render_weekly_report_from_window(cached) == render_weekly_report_from_window(window)


def test_render_weekly_from_empty_window_is_baseline_and_shame_free() -> None:
    from phantom_companion.schema import AggregateWindow

    text = render_weekly_report_from_window(AggregateWindow(days=[]))
    assert text.startswith("# phantom-companion — weekly report")
    assert "baseline" in text.lower()
    ok, reason = shame_free_check(text)
    assert ok, reason


def test_legacy_render_weekly_report_still_works(tmp_path: Path) -> None:
    """The old DailyAggregate-list entry point must keep rendering shame-free."""
    from phantom_companion.aggregator import aggregate_range

    root = tmp_path / "m"
    build_mesh_fixture(root, end_day="2026-05-22", n_days=7, seed=39)
    days = fixture_days("2026-05-22", 7)
    aggs = list(aggregate_range(days, mesh_root=root).values())
    text = render_weekly_report(aggs)
    ok, reason = shame_free_check(text)
    assert ok, reason

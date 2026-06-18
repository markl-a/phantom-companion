"""sat/companion-jobseek-aging — stale jobseek leads surface in the weekly report.

A STILL-PENDING lead (jobseek-tagged, never `applied`) whose most-recent activity
day is >= JOBSEEK_STALE_DAYS before the window's end ("now") is surfaced as a
ranked, shame-free "Worth a nudge" line, oldest first. This drives the REAL weekly
report (render_weekly_report_from_window) over a hand-built 14-day mesh fixture —
not the aging helper in isolation.
"""

from __future__ import annotations

import json
from pathlib import Path

from phantom_companion.fixtures import fixture_days
from phantom_companion.schema import aggregate_window
from phantom_companion.reporter import (
    render_weekly_report_from_window,
    shame_free_check,
    weekly_rollup,
)


def _write_event(
    root: Path, ev_id: str, *, ts: str, company: str, applied: bool
) -> None:
    """Write one events/<id>/meta.json the aggregator reads (timestamp -> day)."""
    ev_dir = root / "events" / ev_id
    ev_dir.mkdir(parents=True, exist_ok=True)
    tags = ["jobseek"] + (["applied"] if applied else [])
    meta = {"timestamp": ts, "tags": tags, "company": company, "applied": applied}
    (ev_dir / "meta.json").write_text(json.dumps(meta, sort_keys=True), encoding="utf-8")
    (ev_dir / "analysis.json").write_text(
        json.dumps({"provider": "claude", "summary": f"event {ev_id}"}, sort_keys=True),
        encoding="utf-8",
    )


def _build(tmp_path: Path):
    root = tmp_path / "m"
    days = fixture_days("2026-05-22", 14)  # 2026-05-09 .. 2026-05-22 inclusive
    # StaleA — investigated on the FIRST day, never applied -> days_open = 13 (stale).
    _write_event(root, "a-old", ts="2026-05-09T09:00:00Z", company="StaleA", applied=False)
    # StaleB — investigated on 2026-05-12, never applied -> days_open = 10 (stale, newer).
    _write_event(root, "b-mid", ts="2026-05-12T10:00:00Z", company="StaleB", applied=False)
    # CONTROL AppliedCo — investigated early but APPLIED -> not pending -> not stale.
    _write_event(root, "c-applied", ts="2026-05-09T11:00:00Z", company="AppliedCo", applied=True)
    # CONTROL FreshCo — investigated 2 days before end, never applied -> days_open = 2 (<7).
    _write_event(root, "d-fresh", ts="2026-05-20T12:00:00Z", company="FreshCo", applied=False)
    return aggregate_window(days, mesh_root=root)


def test_stale_jobseek_leads_surface_in_weekly_report(tmp_path: Path) -> None:
    window = _build(tmp_path)

    # --- data layer: ranked stale-leads, oldest first, days_open >= 7 ---
    job = weekly_rollup(window)["jobseek"]
    assert job["investigated"] == 4
    assert job["applied"] == 1
    assert job["pending"] == 3
    stale = job["stale_leads"]
    companies = [s["company"] for s in stale]
    assert companies == ["StaleA", "StaleB"], stale  # oldest (13d) ranked first
    assert stale[0]["days_open"] == 13
    assert stale[1]["days_open"] == 10
    assert all(s["days_open"] >= 7 for s in stale)
    # CONTROLS are not stale (non-vacuous).
    assert "AppliedCo" not in companies
    assert "FreshCo" not in companies

    # --- real report layer: a shame-free "Worth a nudge" line per stale lead ---
    text = render_weekly_report_from_window(window)
    assert "Worth a nudge" in text
    assert "StaleA" in text and "13 days" in text
    assert "StaleB" in text and "10 days" in text
    # The applied control is never named anywhere in the report.
    assert "AppliedCo" not in text
    # FreshCo is pending<7d: it may appear under "Open to revisit" but NEVER as stale.
    for line in text.splitlines():
        if "Worth a nudge" in line:
            assert "FreshCo" not in line
    ok, reason = shame_free_check(text)
    assert ok, reason

"""End-to-end: the ④ health × developer-output correlation on the REAL CLI path.

These tests deliberately do NOT inject a ``DailyAggregate`` or hand-build a
sample list (that is what ``test_health_output_wiring.py`` does and why the bug
hid — the unit tests passed while production was dead). Instead they write the
on-disk ④ secure-connector health export + the developer-output sample to the
exact locations the production readers look at, then drive the actual
``phantom-companion`` CLI (``daily-report`` / ``weekly-report``) and assert the
correlation runs on the real data instead of forever rendering "Waiting on:
health…".

Production locations exercised here (the wiring under test):
- ``<mesh-root>/logs/phantom-secure-connector/health-<day>.json``
- ``<mesh-root>/logs/phantom-companion/output-<day>.json``
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import pytest

from phantom_companion.cli import main
from phantom_companion.reporter import shame_free_check


def _write_health_export(mesh_root: Path, day: str, sleep_hr: float, source: str = "garmin") -> None:
    """Drop one day's ④ secure-connector health export where production reads it."""
    d = mesh_root / "logs" / "phantom-secure-connector"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"health-{day}.json").write_text(
        json.dumps(
            {
                "day": day,
                "sleep_hr": sleep_hr,
                "hrv_ms": 55.0,
                "resting_hr": 53,
                "activity_min": 40,
                "source": source,
            }
        ),
        encoding="utf-8",
    )


def _write_output_sample(mesh_root: Path, day: str, commits: int) -> None:
    """Drop one day's developer-output sample where production reads it."""
    d = mesh_root / "logs" / "phantom-companion"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"output-{day}.json").write_text(
        json.dumps({"commits": commits, "lines_changed": commits * 30}),
        encoding="utf-8",
    )


def _days_ending(end: str, n: int) -> list[str]:
    e = date.fromisoformat(end)
    return [(e - timedelta(days=i)).isoformat() for i in range(n - 1, -1, -1)]


def test_daily_report_cli_fires_health_insight_from_disk_export(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A health+output export on disk → the daily report's correlation insight
    FIRES (no "Waiting on: health"), driven through the real CLI, not injection."""
    # Keep the deterministic template path: don't let a stray real ``phantom``
    # binary on PATH inject a coach narrative into the assertion.
    from phantom_companion import reporter as rep

    monkeypatch.setattr(rep, "_invoke_coach", lambda _day: None)

    mesh = tmp_path / "mesh"
    out = tmp_path / "out"
    day = "2026-05-22"
    _write_health_export(mesh, day, sleep_hr=7.6)
    _write_output_sample(mesh, day, commits=4)

    rc = main(["--mesh-root", str(mesh), "daily-report", "--day", day, "--out", str(out)])
    assert rc == 0
    body = Path(capsys.readouterr().out.strip()).read_text(encoding="utf-8")

    # The whole point: the insight is no longer waiting on the ④ health stream.
    assert "Waiting on: health" not in body
    assert "Waiting on" not in body  # neither health nor commits is missing now
    # It rendered a real single-day directional summary off the export values.
    assert "health_productivity_correlation" in body
    assert "sleep=7.6h" in body
    assert "commits=4" in body
    ok, reason = shame_free_check(body)
    assert ok, reason


def test_daily_report_cli_without_export_still_waits(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Control: with NO export on disk the same CLI path honestly reports
    "Waiting on" — proving the positive test above measures the real wiring."""
    from phantom_companion import reporter as rep

    monkeypatch.setattr(rep, "_invoke_coach", lambda _day: None)

    mesh = tmp_path / "mesh"
    out = tmp_path / "out"
    rc = main(["--mesh-root", str(mesh), "daily-report", "--day", "2026-05-22", "--out", str(out)])
    assert rc == 0
    body = Path(capsys.readouterr().out.strip()).read_text(encoding="utf-8")
    assert "Waiting on: health" in body
    ok, reason = shame_free_check(body)
    assert ok, reason


def test_weekly_report_cli_correlation_consumes_real_paired_days(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A week of health+output exports on disk → the weekly "Health × output"
    section runs the real multi-day correlation over the REAL paired days
    (7/14), proving the on-disk streams flow through aggregate_window into the
    rollup — vs the empty 0/14 when nothing is ingested."""
    mesh = tmp_path / "mesh"
    out = tmp_path / "out"
    end = "2026-05-22"
    days = _days_ending(end, 7)
    for i, day in enumerate(days):
        _write_health_export(mesh, day, sleep_hr=6.0 + 0.2 * i)
        _write_output_sample(mesh, day, commits=i)

    rc = main(["--mesh-root", str(mesh), "weekly-report", "--end", end, "--out", str(out)])
    assert rc == 0
    body = Path(capsys.readouterr().out.strip()).read_text(encoding="utf-8")

    assert "## Health × output" in body
    # The correlation saw all 7 paired days from disk (below the 14-day gate it
    # stays in honest baseline mode, but the paired-day COUNT proves real data
    # flowed end-to-end rather than the dead 0/14 empty path).
    assert "7/14 days of paired health+output data" in body
    assert "0/14" not in body
    ok, reason = shame_free_check(body)
    assert ok, reason


def test_weekly_report_cli_without_exports_is_empty_baseline(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Control: no exports → the correlation honestly sees 0 paired days."""
    mesh = tmp_path / "mesh"
    out = tmp_path / "out"
    rc = main(["--mesh-root", str(mesh), "weekly-report", "--end", "2026-05-22", "--out", str(out)])
    assert rc == 0
    body = Path(capsys.readouterr().out.strip()).read_text(encoding="utf-8")
    assert "## Health × output" in body
    assert "0/14 days of paired health+output data" in body
    ok, reason = shame_free_check(body)
    assert ok, reason


def test_trend_report_cli_emits_real_pearson_spearman_over_long_window(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The whole point of the statistical gate: over a 30-day window (>= the
    14-day MIN_SAMPLES) the monthly trend report emits the REAL Pearson +
    Spearman coefficient — the branch the 7-day weekly report can never reach.
    Driven through the actual ``trends`` CLI off on-disk exports, not injection."""
    mesh = tmp_path / "mesh"
    out = tmp_path / "out"
    end = "2026-05-30"
    days = _days_ending(end, 30)
    # Monotone sleep↔commits construction → a strong, well-defined correlation.
    for i, day in enumerate(days):
        _write_health_export(mesh, day, sleep_hr=5.0 + 0.1 * i)
        _write_output_sample(mesh, day, commits=i)

    rc = main(["--mesh-root", str(mesh), "trends", "--period", "monthly",
               "--end", end, "--out", str(out)])
    assert rc == 0
    body = Path(capsys.readouterr().out.strip()).read_text(encoding="utf-8")

    # The real statistical correlation actually fired (not the < gate baseline).
    assert "## Health × output" in body
    assert "30 days observed" in body
    assert "association r=" in body
    assert "Spearman" in body
    # And it never claims causation, and stays shame-free.
    low = body.lower()
    for word in ("causes", "because of", "due to", "leads to"):
        assert word not in low, f"causation leaked: {word!r}"
    ok, reason = shame_free_check(body)
    assert ok, reason


def test_trend_report_cli_without_exports_stays_baseline(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Control: no exports over the long window → correlation stays in honest
    baseline mode (no fabricated coefficient)."""
    mesh = tmp_path / "mesh"
    out = tmp_path / "out"
    rc = main(["--mesh-root", str(mesh), "trends", "--period", "monthly",
               "--end", "2026-05-30", "--out", str(out)])
    assert rc == 0
    body = Path(capsys.readouterr().out.strip()).read_text(encoding="utf-8")
    assert "## Health × output" in body
    assert "association r=" not in body  # no coefficient without real paired data
    assert "0/14 days of paired health+output data" in body
    ok, reason = shame_free_check(body)
    assert ok, reason

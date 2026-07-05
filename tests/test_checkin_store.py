"""Real, accumulating check-in store + honest report (no synthetic seed).

Covers ``phantom_companion.checkin_store`` and its CLI wiring:

- ``append_checkin`` is a real accumulating write path (append, not overwrite).
- ``load_checkins`` reads it back with last-write-wins per day.
- ``companion_demo_report`` reads the REAL store and, when empty, returns an
  honest ``no_data_yet`` payload — never fabricated seed numbers.
- The ``checkin-report`` CLI surfaces the same, and stays shame-free.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from phantom_companion.checkin import SubjectiveCheckin
from phantom_companion.checkin_store import (
    CHECKIN_FILENAME,
    append_checkin,
    companion_demo_report,
    default_store_dir,
    load_checkins,
)
from phantom_companion.cli import main
from phantom_companion.reporter import shame_free_check


def test_append_is_real_accumulating_store(tmp_path: Path) -> None:
    store = tmp_path / "data"
    p1 = append_checkin(SubjectiveCheckin("2026-05-22", gut=4, mood=3, sleep_hr=7.2), path=store)
    p2 = append_checkin(SubjectiveCheckin("2026-05-23", gut=5, mood=4, sleep_hr=6.8), path=store)

    assert p1 == p2 == store / CHECKIN_FILENAME
    lines = p1.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2  # appended, not overwritten
    assert json.loads(lines[0])["day"] == "2026-05-22"

    loaded = load_checkins(path=store)
    assert set(loaded) == {"2026-05-22", "2026-05-23"}
    assert loaded["2026-05-23"].gut == 5


def test_load_last_write_wins_per_day(tmp_path: Path) -> None:
    store = tmp_path / "data"
    append_checkin(SubjectiveCheckin("2026-05-22", gut=2, mood=2, sleep_hr=5.0), path=store)
    append_checkin(SubjectiveCheckin("2026-05-22", gut=5, mood=4, sleep_hr=8.0), path=store)
    loaded = load_checkins(path=store)
    assert len(loaded) == 1
    assert loaded["2026-05-22"].gut == 5  # later nightly correction wins


def test_report_empty_is_honest_not_synthetic(tmp_path: Path) -> None:
    report = companion_demo_report(path=tmp_path / "empty")
    assert report["status"] == "no_data_yet"
    assert report["source"] == "real_checkin_store"
    assert report["count"] == 0
    assert report["days"] == []
    assert report["first_day"] is None
    assert report["averages"] is None
    # Honest emptiness: no fabricated numbers leak into the summary.
    assert "0" not in report["summary"].replace("YYYY", "")
    ok, reason = shame_free_check(report["summary"])
    assert ok, reason


def test_report_reads_real_accumulated_data(tmp_path: Path) -> None:
    store = tmp_path / "data"
    append_checkin(SubjectiveCheckin("2026-05-20", gut=4, mood=2, sleep_hr=6.0), path=store)
    append_checkin(SubjectiveCheckin("2026-05-21", gut=2, mood=4, sleep_hr=8.0), path=store)

    report = companion_demo_report(path=store)
    assert report["status"] == "ok"
    assert report["source"] == "real_checkin_store"
    assert report["count"] == 2
    assert report["days"] == ["2026-05-20", "2026-05-21"]
    assert report["first_day"] == "2026-05-20"
    assert report["last_day"] == "2026-05-21"
    assert report["averages"] == {"gut": 3.0, "mood": 3.0, "sleep_hr": 7.0}
    ok, reason = shame_free_check(report["summary"])
    assert ok, reason


def test_default_store_dir_uses_data_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake_root = tmp_path / "phantom-companion"
    monkeypatch.setattr("phantom_companion.reporter.DEFAULT_REPORT_ROOT", fake_root)
    assert default_store_dir() == fake_root
    append_checkin(SubjectiveCheckin("2026-05-22", gut=3, mood=3, sleep_hr=7.0), path=None)
    assert (fake_root / CHECKIN_FILENAME).exists()
    assert companion_demo_report(path=None)["count"] == 1


def test_cli_checkin_report_empty(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["checkin-report", "--out", str(tmp_path / "empty")])
    assert rc == 0
    out = capsys.readouterr().out
    assert "No check-ins recorded yet" in out


def test_cli_checkin_then_report_roundtrip(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    store = tmp_path / "data"
    assert main(["checkin", "2026-05-22 gut=4 mood=3 sleep=7.2", "--out", str(store)]) == 0
    capsys.readouterr()
    assert main(["checkin-report", "--out", str(store), "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "ok"
    assert report["count"] == 1
    assert report["last_day"] == "2026-05-22"

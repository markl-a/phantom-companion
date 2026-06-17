"""CLI wiring for the new subcommands: trends + checkin (both local-only)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from phantom_companion.cli import main
from phantom_companion.reporter import shame_free_check


def test_trends_subcommand_writes_shame_free_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "out"
    rc = main(
        [
            "--mesh-root", str(tmp_path / "mesh"),  # empty -> baseline
            "trends", "--period", "monthly", "--end", "2026-05-22", "--out", str(out),
        ]
    )
    assert rc == 0
    printed = capsys.readouterr().out.strip()
    path = Path(printed)
    assert path.exists()
    body = path.read_text(encoding="utf-8")
    assert body.startswith("# phantom-companion — monthly trends")
    ok, reason = shame_free_check(body)
    assert ok, reason


def test_quarterly_trends_subcommand(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = tmp_path / "out"
    rc = main(
        [
            "--mesh-root", str(tmp_path / "mesh"),
            "trends", "--period", "quarterly", "--end", "2026-05-22", "--out", str(out),
        ]
    )
    assert rc == 0
    path = Path(capsys.readouterr().out.strip())
    assert "quarterly trends" in path.read_text(encoding="utf-8")


def test_checkin_subcommand_appends_local_jsonl(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "out"
    rc = main(["checkin", "2026-05-22 gut=4 mood=3 sleep=7.2", "--out", str(out)])
    assert rc == 0
    path = Path(capsys.readouterr().out.strip())
    assert path.name == "checkins.jsonl"
    rec = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    assert rec["day"] == "2026-05-22"
    assert rec["gut"] == 4 and rec["mood"] == 3 and rec["sleep_hr"] == 7.2

    # A second check-in appends, not overwrites.
    main(["checkin", "2026-05-23, 5, 4, 6.8", "--out", str(out)])
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2


def test_checkin_rejects_dateless_line(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["checkin", "gut=4 mood=3 sleep=7", "--out", str(tmp_path)])
    assert rc == 1
    err = capsys.readouterr().err
    assert "phantom-companion:" in err

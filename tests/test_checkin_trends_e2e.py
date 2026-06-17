"""End-to-end: nightly check-ins flow into the trend report via the REAL CLI.

``test_checkin_trends.py`` parses check-in lines and feeds ``trend_over``
directly — it never writes ``checkins.jsonl`` nor reads it back, which is why
the "check-in not wired to trends" bug passed unit tests while production was
dead. These tests instead:

1. record check-ins through the actual ``phantom-companion checkin`` CLI (which
   appends to ``checkins.jsonl`` in the output dir), then
2. run the actual ``phantom-companion trends`` CLI against the SAME dir, and
3. assert the rendered trend report reflects those check-ins (subjective mood /
   gut / sleep trends), proving the file written in step 1 is read in step 2.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from phantom_companion.cli import main
from phantom_companion.reporter import shame_free_check


def _checkin(out: Path, line: str) -> None:
    rc = main(["checkin", line, "--out", str(out)])
    assert rc == 0


def test_trends_cli_reflects_checkins_written_via_cli(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "out"
    mesh = tmp_path / "mesh"  # empty mesh → only the check-ins carry signal

    # A month of nightly check-ins recorded through the real CLI. Mood rises so
    # the (gated) trend has a clear direction once >= MIN_SAMPLES days exist.
    for i in range(30):
        day = f"2026-05-{i + 1:02d}"
        mood = 1 + (i // 6)  # 1..5, monotone non-decreasing
        _checkin(out, f"{day} gut=4 mood={mood} sleep=7.{i % 10}")
        capsys.readouterr()  # drain the per-checkin path print

    # checkins.jsonl really landed where the trend reader will look.
    store = out / "checkins.jsonl"
    assert store.exists()
    assert len(store.read_text(encoding="utf-8").splitlines()) == 30

    rc = main(
        ["--mesh-root", str(mesh), "trends", "--period", "monthly",
         "--end", "2026-05-30", "--out", str(out)]
    )
    assert rc == 0
    body = Path(capsys.readouterr().out.strip()).read_text(encoding="utf-8")

    # The trend report must now reflect the subjective check-in series. With 30
    # days >= MIN_SAMPLES the mood trend is baseline-ready and rendered with a
    # direction — this is data that ONLY exists because the CLI check-ins were
    # read back in. Without the wiring these labels never appear.
    assert "subjective mood" in body
    assert "subjective gut feeling" in body
    # Mood was constructed to rise, so its trend reads as increasing.
    assert "subjective mood" in body and "increasing" in body
    ok, reason = shame_free_check(body)
    assert ok, reason


def test_trends_cli_without_checkins_omits_subjective_metrics(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Control: no check-ins recorded → no subjective mood/gut metrics appear,
    proving the positive test measures the real read-back path."""
    out = tmp_path / "out"
    mesh = tmp_path / "mesh"
    rc = main(
        ["--mesh-root", str(mesh), "trends", "--period", "monthly",
         "--end", "2026-05-30", "--out", str(out)]
    )
    assert rc == 0
    body = Path(capsys.readouterr().out.strip()).read_text(encoding="utf-8")
    assert "subjective mood" not in body
    assert "subjective gut feeling" not in body
    ok, reason = shame_free_check(body)
    assert ok, reason

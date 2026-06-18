"""End-to-end: the new `ingest-health` CLI flips the live health x output correlation.

Unlike test_health_output_e2e.py (which drops a pre-normalized health-<day>.json on
disk directly), these tests drive the REAL `ingest-health` subcommand: an export file
goes through the actual parser + the new writer, lands at the production path the
aggregator reads, and the daily report's "Waiting on: health" then flips to a real
metric. A no-ingest control proves the wiring is what flipped it.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from phantom_companion.cli import main


def _write_export_file(path: Path, day: str) -> None:
    """One day's export using Apple-HealthKit camelCase + string numbers, so the
    REAL parser (not a hand-normalized dict) is what produces the on-disk sample."""
    path.write_text(
        json.dumps(
            {
                "date": day,
                "sleepHours": "7.6",
                "heartRateVariability": 55,
                "restingHeartRate": 53,
                "activeMinutes": 40,
                "device": "apple_health",
            }
        ),
        encoding="utf-8",
    )


def _write_output_sample(mesh_root: Path, day: str, commits: int) -> None:
    d = mesh_root / "logs" / "phantom-companion"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"output-{day}.json").write_text(
        json.dumps({"commits": commits, "lines_changed": commits * 30}),
        encoding="utf-8",
    )


def test_ingest_health_cli_writes_normalized_health_file(tmp_path: Path) -> None:
    """`ingest-health <export>` parses + writes health-<day>.json at the exact path
    read_health_window/aggregator reads, in the normalized shape."""
    mesh = tmp_path / "mesh"
    day = "2026-05-22"
    export = tmp_path / "export.json"
    _write_export_file(export, day)

    rc = main(["--mesh-root", str(mesh), "ingest-health", str(export)])
    assert rc == 0

    written = mesh / "logs" / "phantom-secure-connector" / f"health-{day}.json"
    assert written.exists()
    data = json.loads(written.read_text(encoding="utf-8"))
    # camelCase string "7.6" normalized to a float; restingHeartRate -> resting_hr int.
    assert data["sleep_hr"] == 7.6
    assert data["resting_hr"] == 53
    assert data["source"] == "apple_health"


def test_ingest_health_cli_flips_live_correlation_in_daily_report(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Drive the REAL CLI: ingest-health then daily-report -> the report carries the
    real health metric and "Waiting on: health" is gone (correlation now fires)."""
    from phantom_companion import reporter as rep

    monkeypatch.setattr(rep, "_invoke_coach", lambda _day: None)

    mesh = tmp_path / "mesh"
    out = tmp_path / "out"
    day = "2026-05-22"
    export = tmp_path / "export.json"
    _write_export_file(export, day)
    _write_output_sample(mesh, day, commits=4)

    rc = main(["--mesh-root", str(mesh), "ingest-health", str(export)])
    assert rc == 0
    capsys.readouterr()  # drop the ingest stdout

    rc = main(["--mesh-root", str(mesh), "daily-report", "--day", day, "--out", str(out)])
    assert rc == 0
    body = Path(capsys.readouterr().out.strip()).read_text(encoding="utf-8")

    assert "Waiting on: health" not in body
    assert "health_productivity_correlation" in body
    assert "sleep=7.6h" in body


def test_daily_report_without_ingest_health_still_waits(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Control: no ingest-health -> the same CLI path still says "Waiting on: health",
    proving the ingest wiring (not something else) is what flipped the correlation."""
    from phantom_companion import reporter as rep

    monkeypatch.setattr(rep, "_invoke_coach", lambda _day: None)

    mesh = tmp_path / "mesh"
    out = tmp_path / "out"
    day = "2026-05-22"
    _write_output_sample(mesh, day, commits=4)

    rc = main(["--mesh-root", str(mesh), "daily-report", "--day", day, "--out", str(out)])
    assert rc == 0
    body = Path(capsys.readouterr().out.strip()).read_text(encoding="utf-8")
    assert "Waiting on: health" in body


def test_ingest_health_cli_multi_day_stream(tmp_path: Path) -> None:
    """A JSON list export (multi-day stream) writes one health-<day>.json per row
    via parse_export_stream."""
    mesh = tmp_path / "mesh"
    export = tmp_path / "stream.json"
    days = ["2026-05-20", "2026-05-21", "2026-05-22"]
    export.write_text(
        json.dumps([{"day": d, "sleep_hr": 6.0 + i, "resting_hr": 50 + i} for i, d in enumerate(days)]),
        encoding="utf-8",
    )

    rc = main(["--mesh-root", str(mesh), "ingest-health", str(export)])
    assert rc == 0
    for d in days:
        assert (mesh / "logs" / "phantom-secure-connector" / f"health-{d}.json").exists()

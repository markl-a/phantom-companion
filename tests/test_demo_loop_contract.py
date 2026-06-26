from __future__ import annotations

import json
from pathlib import Path

from phantom_companion.cli import main
from phantom_companion.reporter import shame_free_check


def test_demo_loop_cli_writes_reproducible_synthetic_reporting_artifacts(
    tmp_path: Path,
    capsys,
) -> None:
    out = tmp_path / "demo"

    rc = main(
        [
            "demo-loop",
            "--out",
            str(out),
            "--end",
            "2026-05-30",
            "--days",
            "30",
            "--seed",
            "42",
        ]
    )

    assert rc == 0
    printed = capsys.readouterr().out.strip()
    manifest_path = Path(printed)
    assert manifest_path == out / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["schema_version"] == 1
    assert manifest["mode"] == "synthetic_demo_loop"
    assert manifest["end_day"] == "2026-05-30"
    assert manifest["days"] == 30
    assert manifest["seed"] == 42
    assert manifest["data_policy"] == "synthetic_only"
    assert manifest["private_data_included"] is False
    assert manifest["external_network"] is False
    assert manifest["llm_coach"] == "disabled"

    report_paths = [out / rel for rel in manifest["reports"].values()]
    assert {p.name for p in report_paths} == {
        "2026-05-30-report.md",
        "2026-05-30-weekly-report.md",
        "2026-05-30-monthly-trends.md",
    }
    for path in report_paths:
        assert path.exists()
        body = path.read_text(encoding="utf-8")
        ok, reason = shame_free_check(body)
        assert ok, reason
        assert "synthetic event" not in body
        assert "real health" not in body.lower()
        assert "browser history" not in body.lower()

    assert (out / "reports" / "checkins.jsonl").exists()
    assert (out / "mesh" / "logs" / "phantom-secure-connector").is_dir()
    assert (out / "mesh" / "logs" / "phantom-companion").is_dir()


def test_demo_loop_is_byte_stable_for_same_inputs(tmp_path: Path, capsys) -> None:
    a = tmp_path / "a"
    b = tmp_path / "b"
    args = ["demo-loop", "--end", "2026-05-30", "--days", "30", "--seed", "7"]

    assert main([*args, "--out", str(a)]) == 0
    capsys.readouterr()
    assert main([*args, "--out", str(b)]) == 0
    capsys.readouterr()

    rels = (
        "manifest.json",
        "reports/2026-05-30-report.md",
        "reports/2026-05-30-weekly-report.md",
        "reports/2026-05-30-monthly-trends.md",
        "reports/checkins.jsonl",
    )
    for rel in rels:
        assert (a / rel).read_text(encoding="utf-8") == (b / rel).read_text(
            encoding="utf-8"
        )


def test_demo_loop_rejects_too_short_windows(tmp_path: Path, capsys) -> None:
    rc = main(
        [
            "demo-loop",
            "--out",
            str(tmp_path / "short"),
            "--end",
            "2026-05-30",
            "--days",
            "6",
        ]
    )

    assert rc == 1
    assert "requires at least 7 days" in capsys.readouterr().err

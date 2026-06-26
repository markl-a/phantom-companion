from __future__ import annotations

import json
from pathlib import Path

from phantom_companion.cli import main


def test_review_scenario_writes_usefulness_artifacts(tmp_path: Path, capsys) -> None:
    source = tmp_path / "source"
    scenario = tmp_path / "scenario"

    assert main(
        [
            "demo-loop",
            "--out",
            str(source),
            "--end",
            "2026-05-30",
            "--days",
            "30",
            "--seed",
            "42",
        ]
    ) == 0
    capsys.readouterr()

    assert main(["review-scenario", "--source", str(source), "--out", str(scenario)]) == 0
    printed = capsys.readouterr().out.strip()
    manifest_path = Path(printed)
    assert manifest_path == scenario / "scenario-manifest.json"

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    review = json.loads((scenario / "review-scenario.json").read_text(encoding="utf-8"))
    summary = (scenario / "summary.md").read_text(encoding="utf-8")

    assert manifest["schema_version"] == 1
    assert manifest["mode"] == "thirty_day_review_scenario"
    assert manifest["source_mode"] == "synthetic_demo_loop"
    assert manifest["data_policy"] == "synthetic_only"
    assert manifest["private_data_included"] is False
    assert manifest["raw_payloads_included"] is False
    assert manifest["external_network"] is False
    assert manifest["llm_coach"] == "disabled"
    assert manifest["files"] == {
        "readme": "README.md",
        "review": "review-scenario.json",
        "summary": "summary.md",
    }

    assert review["mode"] == "thirty_day_review_usefulness"
    assert review["coverage"] == {
        "days": 30,
        "event_days": 30,
        "health_source_days": 30,
        "output_source_days": 30,
        "nightly_checkins": 30,
    }
    assert review["readiness"]["coverage_complete"] is True
    assert review["readiness"]["long_window_trends_ready"] is True
    assert review["readiness"]["wellness_output_association_ready"] is True
    assert review["readiness"]["mood_output_association_ready"] is True
    assert review["review_tasks"]
    assert review["review_prompts"]
    assert review["boundaries"]["medical_advice"] == "not_supported"
    assert review["boundaries"]["causal_claims"] == "not_supported"
    assert "30-day review scenario" in summary
    assert "wellness and output moved together" in summary


def test_review_scenario_rejects_short_windows(tmp_path: Path, capsys) -> None:
    source = tmp_path / "source"

    assert main(["demo-loop", "--out", str(source), "--days", "14", "--seed", "3"]) == 0
    capsys.readouterr()

    rc = main(["review-scenario", "--source", str(source), "--out", str(tmp_path / "out")])

    assert rc == 1
    assert "requires at least 30 days" in capsys.readouterr().err


def test_review_scenario_rejects_manifest_paths_outside_bundle(
    tmp_path: Path,
    capsys,
) -> None:
    source = tmp_path / "source"

    assert main(["demo-loop", "--out", str(source), "--seed", "5"]) == 0
    capsys.readouterr()
    manifest_path = source / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["reports_root"] = ".."
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    rc = main(["review-scenario", "--source", str(source), "--out", str(tmp_path / "out")])

    assert rc == 1
    assert "manifest paths must stay inside the bundle" in capsys.readouterr().err


def test_review_scenario_is_byte_stable_and_does_not_copy_raw_payloads(
    tmp_path: Path,
    capsys,
) -> None:
    source = tmp_path / "source"
    a = tmp_path / "a"
    b = tmp_path / "b"

    assert main(["demo-loop", "--out", str(source), "--seed", "7"]) == 0
    capsys.readouterr()

    private_note = "PRIVATE_NOTE_DO_NOT_EXPORT_91b7c"
    (source / "mesh" / "events" / "private-event").mkdir(parents=True)
    (source / "mesh" / "events" / "private-event" / "analysis.json").write_text(
        json.dumps({"summary": private_note, "sleep_hr": 9.91}),
        encoding="utf-8",
    )

    assert main(["review-scenario", "--source", str(source), "--out", str(a)]) == 0
    capsys.readouterr()
    assert main(["review-scenario", "--source", str(source), "--out", str(b)]) == 0
    capsys.readouterr()

    for rel in (
        "scenario-manifest.json",
        "review-scenario.json",
        "summary.md",
        "README.md",
    ):
        assert (a / rel).read_text(encoding="utf-8") == (b / rel).read_text(
            encoding="utf-8"
        )

    exported_text = "\n".join(
        path.read_text(encoding="utf-8") for path in a.iterdir() if path.is_file()
    )
    assert private_note not in exported_text
    assert "9.91" not in exported_text
    assert "private-event" not in exported_text
    assert "health-2026-05-30.json" not in exported_text
    assert "checkins.jsonl" not in exported_text

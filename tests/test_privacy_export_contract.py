from __future__ import annotations

import json
from pathlib import Path

from phantom_companion.cli import main


def test_privacy_export_writes_redacted_shareable_bundle(tmp_path: Path, capsys) -> None:
    source = tmp_path / "source"
    export = tmp_path / "export"

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

    private_note = "PRIVATE_NOTE_DO_NOT_EXPORT_6f5d2"
    (source / "mesh" / "events").mkdir(parents=True, exist_ok=True)
    (source / "mesh" / "events" / "private.json").write_text(
        json.dumps({"summary": private_note, "sleep_hr": 9.91}),
        encoding="utf-8",
    )

    assert main(["privacy-export", "--source", str(source), "--out", str(export)]) == 0
    printed = capsys.readouterr().out.strip()
    manifest_path = Path(printed)
    assert manifest_path == export / "export-manifest.json"

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    context = json.loads((export / "shareable-context.json").read_text(encoding="utf-8"))
    template = (export / "report-template.md").read_text(encoding="utf-8")
    readme = (export / "README.md").read_text(encoding="utf-8")

    assert manifest["schema_version"] == 1
    assert manifest["mode"] == "privacy_export_bundle"
    assert manifest["data_policy"] == "redacted_aggregate_only"
    assert manifest["private_data_included"] is False
    assert manifest["raw_payloads_included"] is False
    assert manifest["external_network"] is False
    assert manifest["llm_coach"] == "disabled"
    assert manifest["files"] == {
        "context": "shareable-context.json",
        "readme": "README.md",
        "template": "report-template.md",
    }

    assert context["mode"] == "privacy_preserving_report_export"
    assert context["coverage"]["days"] == 30
    assert context["coverage"]["health_files"] == 30
    assert context["coverage"]["output_files"] == 30
    assert context["coverage"]["checkins"] == 30
    assert context["redaction"]["raw_payloads_included"] is False
    assert context["redaction"]["exact_metric_values_included"] is False
    assert "daily" in context["report_headings"]
    assert "weekly" in context["report_headings"]
    assert "trends" in context["report_headings"]

    exported_text = "\n".join(
        path.read_text(encoding="utf-8") for path in export.iterdir() if path.is_file()
    )
    assert private_note not in exported_text
    assert "9.91" not in exported_text
    assert "sleep_hr" not in exported_text
    assert "checkins.jsonl" not in exported_text
    assert "health-2026-05-30.json" not in exported_text
    assert "raw health" not in exported_text.lower()
    assert "browser history" not in exported_text.lower()

    assert "redacted aggregate metadata only" in template
    assert "shareable-context.json" in readme


def test_privacy_export_rejects_private_or_network_source_manifest(
    tmp_path: Path,
    capsys,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "manifest.json").write_text(
        json.dumps(
            {
                "mode": "synthetic_demo_loop",
                "data_policy": "synthetic_only",
                "private_data_included": True,
                "external_network": False,
                "llm_coach": "disabled",
                "inputs": {},
                "reports": {},
            }
        ),
        encoding="utf-8",
    )

    rc = main(["privacy-export", "--source", str(source), "--out", str(tmp_path / "export")])

    assert rc == 1
    assert "only accepts synthetic demo bundles" in capsys.readouterr().err


def test_privacy_export_rejects_report_paths_outside_bundle(
    tmp_path: Path,
    capsys,
) -> None:
    source = tmp_path / "source"
    export = tmp_path / "export"
    source.mkdir()
    secret = tmp_path / "secret.md"
    secret.write_text("# PRIVATE_HEADING_DO_NOT_EXPORT\n", encoding="utf-8")
    (source / "manifest.json").write_text(
        json.dumps(
            {
                "mode": "synthetic_demo_loop",
                "data_policy": "synthetic_only",
                "private_data_included": False,
                "external_network": False,
                "llm_coach": "disabled",
                "days": 30,
                "inputs": {},
                "reports": {"daily": "../secret.md"},
            }
        ),
        encoding="utf-8",
    )

    rc = main(["privacy-export", "--source", str(source), "--out", str(export)])

    assert rc == 1
    err = capsys.readouterr().err
    assert "manifest paths must stay inside the bundle" in err
    assert not (export / "shareable-context.json").exists()


def test_privacy_export_is_byte_stable_for_same_inputs(tmp_path: Path, capsys) -> None:
    source = tmp_path / "source"
    a = tmp_path / "a"
    b = tmp_path / "b"

    assert main(["demo-loop", "--out", str(source), "--seed", "7"]) == 0
    capsys.readouterr()

    assert main(["privacy-export", "--source", str(source), "--out", str(a)]) == 0
    capsys.readouterr()
    assert main(["privacy-export", "--source", str(source), "--out", str(b)]) == 0
    capsys.readouterr()

    for rel in ("export-manifest.json", "shareable-context.json", "report-template.md", "README.md"):
        assert (a / rel).read_text(encoding="utf-8") == (b / rel).read_text(
            encoding="utf-8"
        )

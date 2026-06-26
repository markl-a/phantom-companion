"""Privacy-preserving export bundle for public review templates.

The exporter intentionally avoids reading raw mesh payload files. It accepts a
synthetic demo-loop bundle, copies only aggregate coverage metadata and report
headings, and writes a shareable template package for review/import workflows.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
DEFAULT_TEMPLATE = "weekly-review"
SUPPORTED_TEMPLATES = ("weekly-review", "monthly-review")


def write_privacy_export_bundle(
    *,
    source_bundle: str | Path,
    out_root: str | Path,
    template: str = DEFAULT_TEMPLATE,
) -> Path:
    """Write a deterministic redacted export bundle and return its manifest path."""
    if template not in SUPPORTED_TEMPLATES:
        raise ValueError(f"unsupported template: {template}")

    source = Path(source_bundle)
    out = Path(out_root)
    source_root, source_manifest = _load_source_manifest(source)
    _validate_source_manifest(source_manifest)

    out.mkdir(parents=True, exist_ok=True)
    context = _build_context(source=source_root, manifest=source_manifest, template=template)
    context_path = out / "shareable-context.json"
    template_path = out / "report-template.md"
    readme_path = out / "README.md"

    context_path.write_text(
        json.dumps(context, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    template_path.write_text(_render_template(context), encoding="utf-8")
    readme_path.write_text(_render_readme(context), encoding="utf-8")

    export_manifest = {
        "schema_version": SCHEMA_VERSION,
        "mode": "privacy_export_bundle",
        "source_mode": source_manifest.get("mode", ""),
        "template": template,
        "data_policy": "redacted_aggregate_only",
        "private_data_included": False,
        "raw_payloads_included": False,
        "external_network": False,
        "llm_coach": "disabled",
        "files": {
            "context": _rel(out, context_path),
            "readme": _rel(out, readme_path),
            "template": _rel(out, template_path),
        },
    }
    manifest_path = out / "export-manifest.json"
    manifest_path.write_text(
        json.dumps(export_manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest_path


def _load_source_manifest(source: Path) -> tuple[Path, dict[str, Any]]:
    manifest_path = source if source.is_file() else source / "manifest.json"
    if not manifest_path.exists():
        raise RuntimeError("privacy-export requires a demo-loop manifest.json")
    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise RuntimeError("privacy-export manifest must be a JSON object")
    return manifest_path.parent, raw


def _validate_source_manifest(manifest: dict[str, Any]) -> None:
    if (
        manifest.get("mode") != "synthetic_demo_loop"
        or manifest.get("data_policy") != "synthetic_only"
        or manifest.get("private_data_included") is not False
        or manifest.get("external_network") is not False
        or manifest.get("llm_coach") != "disabled"
    ):
        raise RuntimeError(
            "privacy-export only accepts synthetic demo bundles with private data, "
            "network access, and LLM coaching disabled"
        )


def _build_context(
    *,
    source: Path,
    manifest: dict[str, Any],
    template: str,
) -> dict[str, Any]:
    inputs = manifest.get("inputs") or {}
    reports = manifest.get("reports") or {}
    report_headings = {
        name: _extract_headings(_bundle_path(source, rel))
        for name, rel in sorted(reports.items())
        if isinstance(rel, str)
    }

    return {
        "schema_version": SCHEMA_VERSION,
        "mode": "privacy_preserving_report_export",
        "source_mode": manifest.get("mode", ""),
        "source_end_day": manifest.get("end_day", ""),
        "template": template,
        "data_policy": "redacted_aggregate_only",
        "private_data_included": False,
        "external_network": False,
        "llm_coach": "disabled",
        "coverage": {
            "days": int(manifest.get("days") or inputs.get("event_days") or 0),
            "event_days": int(inputs.get("event_days") or 0),
            "health_files": int(inputs.get("health_files") or 0),
            "output_files": int(inputs.get("output_files") or 0),
            "checkins": int(inputs.get("checkins") or 0),
            "reports": len(report_headings),
        },
        "redaction": {
            "raw_payloads_included": False,
            "exact_metric_values_included": False,
            "exact_timestamps_included": False,
            "account_identifiers_included": False,
            "included": [
                "window metadata",
                "coverage counts",
                "report heading names",
                "review template prompts",
            ],
            "excluded": [
                "event payload content",
                "per-day wellness measurements",
                "subjective check-in values",
                "work log content",
                "account identifiers",
                "external service exports",
            ],
        },
        "report_headings": report_headings,
    }


def _extract_headings(path: Path) -> list[str]:
    if not path.exists() or not path.is_file():
        return []
    headings: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped.startswith("#"):
            continue
        title = stripped.lstrip("#").strip()
        if title:
            headings.append(title)
    return headings


def _bundle_path(root: Path, rel: str) -> Path:
    candidate = Path(rel)
    if candidate.is_absolute():
        raise RuntimeError("privacy-export manifest paths must be bundle-relative")
    root_resolved = root.resolve()
    path = (root / candidate).resolve()
    try:
        path.relative_to(root_resolved)
    except ValueError as exc:
        raise RuntimeError("privacy-export manifest paths must stay inside the bundle") from exc
    return path


def _render_template(context: dict[str, Any]) -> str:
    coverage = context["coverage"]
    heading_lines: list[str] = []
    for report_name, headings in sorted(context["report_headings"].items()):
        heading_lines.append(f"- {report_name}: {', '.join(headings) if headings else 'no headings'}")
    if not heading_lines:
        heading_lines.append("- no report headings available")

    return "\n".join(
        [
            "# phantom-companion shareable review template",
            "",
            "> This template is generated from redacted aggregate metadata only.",
            "",
            "## Window",
            f"- End day: {context['source_end_day']}",
            f"- Days represented: {coverage['days']}",
            "",
            "## Coverage",
            f"- Event days: {coverage['event_days']}",
            f"- Wellness source files counted: {coverage['health_files']}",
            f"- Output source files counted: {coverage['output_files']}",
            f"- Subjective check-ins counted: {coverage['checkins']}",
            "",
            "## Available Sections",
            *heading_lines,
            "",
            "## Review Prompts",
            "- What pattern is visible from the coverage and section list?",
            "- What question should the next local report answer?",
            "- What data source would need explicit consent before deeper review?",
            "",
        ]
    )


def _render_readme(context: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Privacy Export Bundle",
            "",
            "This folder is safe to share for public issue discussion or template review.",
            "It contains `shareable-context.json` and `report-template.md` only.",
            "",
            "The context file carries coverage counts and report heading names. It does",
            "not contain event payload content, exact wellness measurements, check-in",
            "values, work log content, account identifiers, network output, or LLM text.",
            "",
            f"Template: `{context['template']}`",
            f"Data policy: `{context['data_policy']}`",
            "",
        ]
    )


def _rel(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


__all__ = [
    "DEFAULT_TEMPLATE",
    "SCHEMA_VERSION",
    "SUPPORTED_TEMPLATES",
    "write_privacy_export_bundle",
]

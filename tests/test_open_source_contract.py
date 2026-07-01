from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_readme_contains_isolated_public_demo_and_privacy_pointer():
    text = _read("README.md")

    assert "Quickstart" in text
    assert "--mesh-root" in text
    assert "ingest-health" in text
    assert "demo-loop" in text
    assert "daily-report" in text
    assert "trends" in text
    assert "docs/PRIVACY_AND_DEMO.md" in text
    assert "docs/SYNTHETIC_REPORTING_LOOP.md" in text
    assert "privacy-export" in text
    assert "docs/PRIVACY_EXPORT_BUNDLE.md" in text
    assert "review-scenario" in text
    assert "docs/THIRTY_DAY_REVIEW_SCENARIO.md" in text


def test_privacy_contract_documents_storage_deletion_and_synthetic_policy():
    text = _read("docs/PRIVACY_AND_DEMO.md")
    low = text.lower()

    assert "synthetic" in low
    assert "~/.phantom-mesh/logs/phantom-companion" in text
    assert "Deletion is ordinary filesystem deletion" in text
    assert "Do not commit real health records" in text
    assert "LLM-backed analysis must remain optional" in text


def test_synthetic_reporting_loop_contract_documents_manifest_and_boundaries():
    text = _read("docs/SYNTHETIC_REPORTING_LOOP.md")

    assert "demo-loop" in text
    assert "manifest.json" in text
    assert "synthetic_only" in text
    assert "private_data_included" in text
    assert "external_network" in text
    assert "llm_coach" in text
    assert "2026-05-30-report.md" in text
    assert "2026-05-30-weekly-report.md" in text
    assert "2026-05-30-monthly-trends.md" in text


def test_privacy_export_contract_documents_redacted_bundle_schema():
    text = _read("docs/PRIVACY_EXPORT_BUNDLE.md")

    assert "privacy-export" in text
    assert "export-manifest.json" in text
    assert "shareable-context.json" in text
    assert "report-template.md" in text
    assert "redacted_aggregate_only" in text
    assert "raw_payloads_included" in text
    assert "external_network" in text
    assert "llm_coach" in text
    assert "byte-stable" in text


def test_review_scenario_contract_documents_p3_usefulness_schema():
    text = _read("docs/THIRTY_DAY_REVIEW_SCENARIO.md")

    assert "review-scenario" in text
    assert "scenario-manifest.json" in text
    assert "review-scenario.json" in text
    assert "summary.md" in text
    assert "synthetic_only" in text
    assert "raw_payloads_included" in text
    assert "external_network" in text
    assert "llm_coach" in text
    assert "30 days" in text
    assert "medical advice" in text

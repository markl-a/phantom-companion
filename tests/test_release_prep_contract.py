from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_release_prep_documents_exist_and_define_safe_contribution_flow() -> None:
    contributing = _read("CONTRIBUTING.md")
    security = _read("SECURITY.md")
    combined = f"{contributing}\n{security}".lower()

    assert "python -m pytest -q" in contributing
    assert "docs/open_source_readiness.md" in combined
    assert "no private data" in combined
    assert "no credentials" in combined
    assert "synthetic" in combined
    assert "security advisory" in security.lower()
    assert "do not open a public issue" in security.lower()
    assert "7 days" in security


def test_release_checklist_documents_final_gate_without_claiming_release_ready() -> None:
    changelog = _read("CHANGELOG.md")
    checklist = _read("docs/RELEASE_CHECKLIST.md")
    combined = f"{changelog}\n{checklist}".lower()

    assert "remote publication pending" in combined
    assert "python -m pytest -q" in checklist
    assert "docs/open_source_readiness.md" in combined
    assert "dependency/license review" in combined
    assert "secret" in combined
    assert "private data" in combined
    assert "manual maintainer approval" in combined
    assert "contributing.md" in combined
    assert "security.md" in combined


def test_final_release_audit_records_scan_dependency_review_and_blockers() -> None:
    audit = _read("docs/FINAL_RELEASE_AUDIT.md")
    low = audit.lower()

    assert "high_conf_secret_hits=0" in audit
    assert "dependency/license review" in low
    assert "direct default release-scope dependency/license review result: pass" in low
    assert "remote publication pending" in low
    assert "manual maintainer approval is recorded" in low
    assert "Apache-2.0" in audit


def test_release_notes_tag_plan_and_approval_gate_are_documented() -> None:
    notes = _read("docs/RELEASE_NOTES.md")
    tag_plan = _read("docs/TAG_PLAN.md")
    approval = _read("docs/PUBLIC_RELEASE_APPROVAL.md")
    combined = f"{notes}\n{tag_plan}\n{approval}".lower()

    assert "release candidate approved and tagged locally" in combined
    assert "remote publication pending" in combined
    assert "proposed tag" in combined
    assert "v0.1.0-alpha.0" in combined
    assert "manual maintainer approval" in combined
    assert "status: approved" in approval.lower()
    assert "approval decision: approved" in approval.lower()
    assert "approver: mark" in approval.lower()
    assert "approval date: 2026-06-27" in approval.lower()
    assert "approved tag: v0.1.0-alpha.0" in approval.lower()
    assert "local annotated tag creation" in approval.lower()
    assert "remote tag push" in approval.lower()
    assert "release scope: public source release candidate" in approval.lower()
    assert "no tag creation before approval" in approval.lower()


def test_ci_runs_release_prep_gate() -> None:
    workflow = _read(".github/workflows/ci.yml")

    assert "release-prep gate" in workflow
    assert "python -m pytest tests/test_release_prep_contract.py -q" in workflow

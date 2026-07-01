"""Unit tests for jobseek_followup._has_tag's scalar-string tags branch and
analyze_jobseek's meta.applied True path — otherwise exercised only
indirectly via the aggregate summary.
"""
from __future__ import annotations

from phantom_companion.insight_modules.jobseek_followup import _has_tag, analyze_jobseek


# ---------------------------------------------------------------------------
# _has_tag — meta.tags as a scalar string, not a list
# ---------------------------------------------------------------------------
def test_has_tag_wraps_scalar_string_tag_as_single_element():
    ev = {"meta": {"tags": "jobseek"}}
    assert _has_tag(ev, "jobseek") is True


def test_has_tag_scalar_string_does_not_substring_match():
    ev = {"meta": {"tags": "jobseek"}}
    assert _has_tag(ev, "seek") is False
    assert _has_tag(ev, "job") is False


def test_has_tag_missing_tags_returns_false():
    assert _has_tag({}, "jobseek") is False
    assert _has_tag({"meta": {}}, "jobseek") is False


def test_has_tag_list_tags_still_works():
    ev = {"meta": {"tags": ["jobseek", "company_research"]}}
    assert _has_tag(ev, "company_research") is True
    assert _has_tag(ev, "applied") is False


# ---------------------------------------------------------------------------
# analyze_jobseek — meta.applied is True vs the "applied" tag path
# ---------------------------------------------------------------------------
def test_analyze_jobseek_meta_applied_true_marks_applied_without_tag():
    events = [
        {"meta": {"company": "Acme", "tags": "jobseek"}},
        {"meta": {"company": "Acme", "applied": True}},
    ]
    result = analyze_jobseek(events)
    assert result["details"]["applied"] == ["Acme"]
    assert result["details"]["pending_followup"] == []


def test_analyze_jobseek_applied_tag_marks_applied_without_meta_flag():
    events = [
        {"meta": {"company": "Beta", "tags": "jobseek"}},
        {"meta": {"company": "Beta", "tags": ["applied"]}},
    ]
    result = analyze_jobseek(events)
    assert result["details"]["applied"] == ["Beta"]
    assert result["details"]["pending_followup"] == []


def test_analyze_jobseek_truthy_non_true_applied_value_does_not_count():
    events = [
        {"meta": {"company": "Gamma", "tags": "jobseek"}},
        {"meta": {"company": "Gamma", "applied": "yes"}},  # truthy but not `is True`
    ]
    result = analyze_jobseek(events)
    assert result["details"]["applied"] == []
    assert result["details"]["pending_followup"] == ["Gamma"]

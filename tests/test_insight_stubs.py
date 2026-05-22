"""Each insight module must return a well-shaped dict."""

from __future__ import annotations

from phantom_companion.insight_modules import (
    analyze_attention,
    analyze_health_vs_output,
    analyze_jobseek,
    analyze_learning_roi,
    analyze_llm_usage,
)

REQUIRED_KEYS = {"module", "summary", "details", "baseline_ready"}


def _check(result: dict, expected_module: str) -> None:
    assert REQUIRED_KEYS.issubset(result.keys()), f"missing keys: {REQUIRED_KEYS - result.keys()}"
    assert result["module"] == expected_module
    assert isinstance(result["summary"], str) and result["summary"]
    assert isinstance(result["details"], dict)
    assert isinstance(result["baseline_ready"], bool)


def test_llm_usage_empty_is_baseline() -> None:
    out = analyze_llm_usage([])
    _check(out, "llm_usage")
    assert out["baseline_ready"] is False


def test_llm_usage_counts_provider() -> None:
    events = [
        {"analysis": {"provider": "claude", "task_kind": "code"}},
        {"analysis": {"provider": "claude", "task_kind": "doc"}},
        {"analysis": {"provider": "mlx", "task_kind": "code"}},
    ]
    out = analyze_llm_usage(events)
    _check(out, "llm_usage")
    assert out["baseline_ready"] is True
    assert out["details"]["by_provider"]["claude"] == 2
    assert out["details"]["by_task_kind"]["code"] == 2


def test_attention_empty_is_baseline() -> None:
    out = analyze_attention([])
    _check(out, "attention_switches")
    assert out["baseline_ready"] is False


def test_attention_finds_peak_focus_hour() -> None:
    events = [
        {"meta": {"timestamp": "2026-05-22T10:00:00Z"}},
        {"meta": {"timestamp": "2026-05-22T10:30:00Z"}},
        {"meta": {"timestamp": "2026-05-22T10:45:00Z"}},
        {"meta": {"timestamp": "2026-05-22T14:00:00Z"}},
        {"meta": {"timestamp": "2026-05-22T18:00:00Z"}},
    ]
    out = analyze_attention(events)
    _check(out, "attention_switches")
    assert out["baseline_ready"] is True
    # 14:00 and 18:00 both have 1 event → either is a valid "calmest".
    assert out["details"]["peak_focus_hour"] in {14, 18}


def test_health_correlation_no_data_is_baseline() -> None:
    out = analyze_health_vs_output(health_data={}, commits=[])
    _check(out, "health_productivity_correlation")
    assert out["baseline_ready"] is False
    assert "Waiting on" in out["summary"]


def test_health_correlation_with_data() -> None:
    out = analyze_health_vs_output(
        health_data={"sleep_hr": 7.5}, commits=[{"sha": "a"}, {"sha": "b"}, {"sha": "c"}]
    )
    _check(out, "health_productivity_correlation")
    assert out["baseline_ready"] is True


def test_learning_roi_empty_log_is_baseline() -> None:
    out = analyze_learning_roi("")
    _check(out, "learning_roi")
    assert out["baseline_ready"] is False


def test_learning_roi_parses_digest() -> None:
    digest = "## A\nQ: hmm?\n## B\n### sub\nQ: hi\n"
    out = analyze_learning_roi(digest)
    _check(out, "learning_roi")
    assert out["baseline_ready"] is True
    assert out["details"]["items_read"] == 3
    assert out["details"]["items_engaged"] == 2


def test_jobseek_empty_is_baseline() -> None:
    out = analyze_jobseek([])
    _check(out, "jobseek_followup")
    assert out["baseline_ready"] is False


def test_jobseek_pending_followup() -> None:
    events = [
        {"meta": {"tags": ["jobseek"], "company": "Garmin"}},
        {"meta": {"tags": ["jobseek", "applied"], "company": "Anthropic"}},
        {"meta": {"tags": ["jobseek"], "company": "南亞科"}},
    ]
    out = analyze_jobseek(events)
    _check(out, "jobseek_followup")
    assert out["baseline_ready"] is True
    assert "Garmin" in out["details"]["pending_followup"]
    assert "Anthropic" not in out["details"]["pending_followup"]

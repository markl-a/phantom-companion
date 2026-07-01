"""Edge cases for insight_modules.attention_switches, otherwise untested:
``_hour_of``'s meta.ts alias + malformed-timestamp handling, and the
all-night event path through ``analyze_attention``.
"""

from __future__ import annotations

from phantom_companion.insight_modules.attention_switches import (
    _hour_of,
    analyze_attention,
)


# ---------------------------------------------------------------------------
# _hour_of — meta.ts alias
# ---------------------------------------------------------------------------
def test_hour_of_ts_alias_matches_timestamp():
    ev_timestamp = {"meta": {"timestamp": "2026-06-27T14:30:00Z"}}
    ev_ts_alias = {"meta": {"ts": "2026-06-27T14:30:00Z"}}
    assert _hour_of(ev_timestamp) == _hour_of(ev_ts_alias) == 14


def test_hour_of_prefers_timestamp_over_ts_when_both_present():
    ev = {"meta": {"timestamp": "2026-06-27T09:00:00Z", "ts": "2026-06-27T20:00:00Z"}}
    assert _hour_of(ev) == 9


# ---------------------------------------------------------------------------
# _hour_of — malformed / missing timestamp is swallowed, never raises
# ---------------------------------------------------------------------------
def test_hour_of_missing_meta_returns_none():
    assert _hour_of({}) is None


def test_hour_of_non_str_timestamp_returns_none():
    assert _hour_of({"meta": {"timestamp": 12345}}) is None
    assert _hour_of({"meta": {"timestamp": None}}) is None
    assert _hour_of({"meta": {"ts": ["not", "a", "string"]}}) is None


def test_hour_of_malformed_timestamp_string_returns_none():
    assert _hour_of({"meta": {"timestamp": "not-a-timestamp"}}) is None


# ---------------------------------------------------------------------------
# analyze_attention — all-night events
# ---------------------------------------------------------------------------
def test_analyze_attention_all_night_events_baseline_ready_but_no_peak():
    events = [
        {"meta": {"timestamp": f"2026-06-27T{h:02d}:00:00Z"}} for h in range(5)
    ]  # hours 0-4 — every event falls outside the 08-22 working window
    result = analyze_attention(events)
    assert result["baseline_ready"] is True
    assert result["details"]["peak_focus_hour"] is None


def test_analyze_attention_ignores_malformed_events_without_crash():
    events = [
        {"meta": {"timestamp": "not-a-timestamp"}},
        {"meta": {"timestamp": 123}},
        {},
        {"meta": {"timestamp": "2026-06-27T10:00:00Z"}},
        {"meta": {"timestamp": "2026-06-27T10:00:00Z"}},
        {"meta": {"timestamp": "2026-06-27T10:00:00Z"}},
        {"meta": {"timestamp": "2026-06-27T10:00:00Z"}},
        {"meta": {"timestamp": "2026-06-27T10:00:00Z"}},
    ]
    result = analyze_attention(events)
    assert result["baseline_ready"] is True
    assert result["details"]["peak_focus_hour"] == 10

"""Attention / context-switch density per hour, peak focus window."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Any


def _hour_of(ev: dict[str, Any]) -> int | None:
    ts = (ev.get("meta") or {}).get("timestamp") or (ev.get("meta") or {}).get("ts")
    if not isinstance(ts, str):
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).hour
    except ValueError:
        return None


def analyze_attention(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Count events per hour as a proxy for context-switch density.

    Peak focus = the hour with the **fewest** non-zero switches in the
    working window (08-22). With <5 events, returns baseline-not-ready.
    """
    per_hour: Counter[int] = Counter()
    for ev in events:
        h = _hour_of(ev)
        if h is not None:
            per_hour[h] += 1
    baseline_ready = sum(per_hour.values()) >= 5
    peak_focus_hour: int | None = None
    if baseline_ready:
        working = {h: c for h, c in per_hour.items() if 8 <= h <= 22 and c > 0}
        if working:
            peak_focus_hour = min(working, key=lambda h: working[h])
        summary = f"{sum(per_hour.values())} events across {len(per_hour)} hour-buckets"
        if peak_focus_hour is not None:
            summary += f"; calmest working hour ≈ {peak_focus_hour:02d}:00"
    else:
        summary = "Fewer than 5 timestamped events — peak-focus detection idle."
    return {
        "module": "attention_switches",
        "summary": summary,
        "details": {
            "events_per_hour": dict(per_hour),
            "peak_focus_hour": peak_focus_hour,
        },
        "baseline_ready": baseline_ready,
    }

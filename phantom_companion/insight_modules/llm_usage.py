"""LLM usage ROI per task type / provider."""

from __future__ import annotations

from collections import Counter
from typing import Any


def analyze_llm_usage(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Tally provider × task-type from event analysis blobs.

    Looks for ``event["analysis"]["provider"]`` and ``event["analysis"]["task_kind"]``.
    Returns deterministic stub if no events carry that shape.
    """
    by_provider: Counter[str] = Counter()
    by_task: Counter[str] = Counter()
    for ev in events:
        analysis = ev.get("analysis") or {}
        provider = analysis.get("provider")
        task = analysis.get("task_kind") or analysis.get("kind")
        if provider:
            by_provider[str(provider)] += 1
        if task:
            by_task[str(task)] += 1
    baseline_ready = bool(by_provider) or bool(by_task)
    if baseline_ready:
        top_provider, top_count = by_provider.most_common(1)[0] if by_provider else ("n/a", 0)
        summary = f"{sum(by_provider.values())} LLM calls; top provider: {top_provider} ({top_count})"
    else:
        summary = "No LLM call events captured yet — gathering baseline."
    return {
        "module": "llm_usage",
        "summary": summary,
        "details": {
            "by_provider": dict(by_provider),
            "by_task_kind": dict(by_task),
            "event_sample": len(events),
        },
        "baseline_ready": baseline_ready,
    }

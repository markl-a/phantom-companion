"""Learning ROI — RSS subscribed vs read vs actually used.

Reads ③ phantom-ai-feed's per-day digest log. The digest format (as of
2026-05-22) is markdown with sections; we count headings as "items read"
and Q&A blocks as "items engaged with".
"""

from __future__ import annotations

import re
from typing import Any

_HEADING = re.compile(r"^#{2,4}\s+(.+)$", re.MULTILINE)
_QA = re.compile(r"(?im)^(?:Q:|問:|Question:)")


def analyze_learning_roi(ai_feed_log: str | None = None) -> dict[str, Any]:
    """Parse ai-feed digest text → read vs engaged ratio.

    Empty log → baseline-not-ready stub.
    """
    text = ai_feed_log or ""
    headings = _HEADING.findall(text)
    qa_count = len(_QA.findall(text))
    items_read = len(headings)
    baseline_ready = items_read > 0
    ratio = (qa_count / items_read) if items_read else 0.0
    if baseline_ready:
        summary = (
            f"{items_read} items in today's digest, {qa_count} engaged "
            f"({ratio * 100:.0f}% engagement)"
        )
    else:
        summary = "No ai-feed digest for today — learning ROI idle."
    return {
        "module": "learning_roi",
        "summary": summary,
        "details": {
            "items_read": items_read,
            "items_engaged": qa_count,
            "engagement_ratio": round(ratio, 3),
            "sample_headings": headings[:3],
        },
        "baseline_ready": baseline_ready,
    }

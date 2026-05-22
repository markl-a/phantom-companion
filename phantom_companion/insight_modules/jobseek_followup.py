"""Jobseek follow-up — investigated-but-not-applied companies.

Looks for events tagged ``jobseek`` or ``company_research`` whose meta
carries a ``company`` field, and intersects with ``applied=True`` events
to surface the *gap*.
"""

from __future__ import annotations

from typing import Any


def _has_tag(ev: dict[str, Any], tag: str) -> bool:
    tags = (ev.get("meta") or {}).get("tags") or []
    if isinstance(tags, str):
        tags = [tags]
    return tag in tags


def analyze_jobseek(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Return companies seen vs companies applied to."""
    investigated: set[str] = set()
    applied: set[str] = set()
    for ev in events:
        meta = ev.get("meta") or {}
        company = meta.get("company")
        if not company:
            continue
        if _has_tag(ev, "jobseek") or _has_tag(ev, "company_research"):
            investigated.add(str(company))
        if meta.get("applied") is True or _has_tag(ev, "applied"):
            applied.add(str(company))
    pending = sorted(investigated - applied)
    baseline_ready = bool(investigated)
    if baseline_ready:
        summary = (
            f"{len(investigated)} companies investigated, {len(applied)} applied, "
            f"{len(pending)} pending follow-up"
        )
    else:
        summary = "No jobseek-tagged events today — follow-up tracker idle."
    return {
        "module": "jobseek_followup",
        "summary": summary,
        "details": {
            "investigated": sorted(investigated),
            "applied": sorted(applied),
            "pending_followup": pending,
        },
        "baseline_ready": baseline_ready,
    }

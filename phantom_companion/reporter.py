"""Compose daily / weekly companion reports.

Tone constraint (HARD): all generated text passes a shame-free lint that
mirrors phantom-mesh ``core/src/life_node/coach_prompts/lint.rs``. If a
template ever produces a shame-leaking line, the reporter refuses to write
the file. This is a BIG-GOAL operational invariant, not a nice-to-have.

LLM swap: ``invoke_coach`` will try ``phantom coach review`` as a
subprocess; if missing or non-zero, the deterministic template wins.
This keeps the daily-cron path deterministic.
"""

from __future__ import annotations

import shutil
import subprocess
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Iterable

from .aggregator import DailyAggregate, aggregate_day, aggregate_range
from .insight_modules import (
    analyze_attention,
    analyze_health_vs_output,
    analyze_jobseek,
    analyze_learning_roi,
    analyze_llm_usage,
)

# Shame patterns — mirror of core/src/life_node/coach_prompts/lint.rs.
# Keep in sync; integration test should verify equivalence once the
# Python <-> Rust bridge is available.
_SHAME_PATTERNS: tuple[tuple[str, str], ...] = (
    ("你又", "blame: '你又...' implies recurring failure"),
    ("你終於", "sarcasm: '你終於...' implies prior repeated failure"),
    ("你居然", "judgment: '你居然...' implies disbelief at user's choice"),
    ("你怎麼又", "compound-blame: '你怎麼又...'"),
    ("還不", "imperative-shame: '還不...' (commanding tone)"),
)


def shame_free_check(text: str) -> tuple[bool, str]:
    """Return ``(ok, reason)``. ``ok=True`` means clean."""
    for pat, why in _SHAME_PATTERNS:
        idx = text.find(pat)
        if idx >= 0:
            return False, f"shame leakage at byte offset {idx}: {why}"
    return True, ""


DEFAULT_REPORT_ROOT = Path.home() / ".phantom-mesh" / "logs" / "phantom-companion"


def _run_insights(agg: DailyAggregate) -> list[dict[str, Any]]:
    return [
        analyze_llm_usage(agg.events),
        analyze_attention(agg.events),
        analyze_health_vs_output(health_data={}, commits=[]),
        analyze_learning_roi(agg.ai_feed_log),
        analyze_jobseek(agg.events),
    ]


def _heartbeat_line(heartbeats: dict[str, bool]) -> str:
    if not heartbeats:
        return "(no sibling satellites detected)"
    parts = [f"{name}={'on' if alive else 'off'}" for name, alive in heartbeats.items()]
    return ", ".join(parts)


def _invoke_coach(day: str) -> str | None:
    """Best-effort: ask the real ``phantom coach review`` LLM for ``day``.

    The real CLI signature is ``phantom coach review --date YYYY-MM-DD``;
    it re-aggregates internally and emits an LLM coaching review whose
    body starts with ``# Daily review —``. Returns ``None`` if the binary
    is missing, times out, exits non-zero, or yields empty output — in
    which case the caller keeps the deterministic template only.
    """
    if not shutil.which("phantom"):
        return None
    try:
        result = subprocess.run(
            ["phantom", "coach", "review", "--date", day],
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def _next_step_from_coach(coach_text: str) -> str | None:
    """Pull the coach's "Tomorrow's one action" line as a next-step.

    The real coach output ends with a ``## Tomorrow's one action`` heading
    followed by the suggested action. Returns the action text, or ``None``
    if that section is absent.
    """
    lines = coach_text.splitlines()
    for i, line in enumerate(lines):
        if line.strip().lower().startswith("## tomorrow's one action"):
            for follow in lines[i + 1 :]:
                if follow.strip():
                    return follow.strip().lstrip("-* ").strip()
            return None
    return None


def _next_step_from_insights(insights: list[dict[str, Any]]) -> str:
    """Derive a next-step from whichever insight modules fired (real data)."""
    fired = [i for i in insights if i.get("baseline_ready")]
    if fired:
        names = ", ".join(i["module"] for i in fired)
        return (
            f"Signal is live in: {names}. Review the insights above and pick "
            "the one that matters most to you tomorrow."
        )
    return (
        "Keep letting phantom-mesh capture your real activity — once a few "
        "weeks of data exist the companion can suggest concrete next steps."
    )


def render_daily_report(agg: DailyAggregate) -> str:
    """Build the daily markdown report. Always shame-free."""
    insights = _run_insights(agg)
    ready = sum(1 for i in insights if i.get("baseline_ready"))

    lines: list[str] = []
    lines.append(f"# phantom-companion — daily report ({agg.day})")
    lines.append("")
    lines.append("> Proactive observation pass. Tone: supportive, never blame.")
    lines.append("")
    lines.append("## Overview")
    lines.append(f"- Events captured today: **{len(agg.events)}**")
    lines.append(f"- Insight modules with usable signal: **{ready} / {len(insights)}**")
    lines.append(f"- Sibling satellites: {_heartbeat_line(agg.heartbeats)}")
    lines.append("")
    lines.append("## Insights")
    for ins in insights:
        marker = "ready" if ins.get("baseline_ready") else "baseline"
        lines.append(f"### {ins['module']} ({marker})")
        lines.append(ins["summary"])
        lines.append("")
    if ready == 0:
        lines.append("## Today's note")
        lines.append(
            "Today's report is mostly a baseline snapshot — that's expected "
            "while phantom-mesh accumulates events. A trustworthy proactive "
            "agent needs weeks of your real activity before it has anything "
            "useful to surface."
        )
        lines.append("")
    # Ask the real LLM coach for ``agg.day`` and MERGE its narrative in as a
    # first-class section (the deterministic insights above stay as structured
    # context). The coach body starts with ``# Daily review —``; we demote that
    # H1 to an H2 so the report keeps a single top-level heading.
    coach_text = _invoke_coach(agg.day)
    next_step: str | None = None
    if coach_text:
        ok, _ = shame_free_check(coach_text)
        if ok:
            next_step = _next_step_from_coach(coach_text)
            coach_block = coach_text
            if coach_block.startswith("# "):
                coach_block = "#" + coach_block  # # Daily review -> ## Daily review
            lines.append("## Coach review (phantom coach review LLM)")
            lines.append("")
            lines.append(coach_block.rstrip())
            lines.append("")

    if next_step is None:
        next_step = _next_step_from_insights(insights)
    lines.append("## Next-step suggestion")
    lines.append(f"➡️ {next_step}")
    lines.append("")

    text = "\n".join(lines).rstrip() + "\n"
    ok, reason = shame_free_check(text)
    if not ok:
        raise RuntimeError(f"refused to emit shame-leaking report: {reason}")
    return text


def render_weekly_report(aggs: Iterable[DailyAggregate]) -> str:
    aggs = list(aggs)
    lines: list[str] = []
    span = f"{aggs[0].day} → {aggs[-1].day}" if aggs else "(empty window)"
    lines.append(f"# phantom-companion — weekly report ({span})")
    lines.append("")
    lines.append("## Rollup")
    total_events = sum(len(a.events) for a in aggs)
    lines.append(f"- Days observed: **{len(aggs)}**")
    lines.append(f"- Total events: **{total_events}**")
    lines.append("")
    lines.append("## Per-day event counts")
    for a in aggs:
        lines.append(f"- {a.day}: {len(a.events)} events")
    lines.append("")
    lines.append("## This week's note")
    if total_events == 0:
        lines.append(
            "No events captured this week. The companion is in baseline mode "
            "and will become genuinely useful once 30+ days of activity exist."
        )
    else:
        lines.append(
            f"Captured {total_events} events across {len(aggs)} days — keep "
            "the baseline growing; cross-day correlation unlocks at ~30 days."
        )
    lines.append("")
    text = "\n".join(lines).rstrip() + "\n"
    ok, reason = shame_free_check(text)
    if not ok:
        raise RuntimeError(f"refused to emit shame-leaking report: {reason}")
    return text


def write_daily_report(
    day: str | None = None,
    out_root: Path | None = None,
    mesh_root: Path | None = None,
) -> Path:
    agg = aggregate_day(day, mesh_root=mesh_root)
    text = render_daily_report(agg)
    out_dir = Path(out_root) if out_root else DEFAULT_REPORT_ROOT
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{agg.day}-report.md"
    path.write_text(text, encoding="utf-8")
    return path


def write_weekly_report(
    end_day: str | None = None,
    out_root: Path | None = None,
    mesh_root: Path | None = None,
) -> Path:
    end = date.fromisoformat(end_day) if end_day else date.today()
    days = [(end - timedelta(days=i)).isoformat() for i in range(6, -1, -1)]
    aggs = list(aggregate_range(days, mesh_root=mesh_root).values())
    text = render_weekly_report(aggs)
    out_dir = Path(out_root) if out_root else DEFAULT_REPORT_ROOT
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{end.isoformat()}-weekly-report.md"
    path.write_text(text, encoding="utf-8")
    return path

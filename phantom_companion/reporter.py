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
from collections import Counter
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
from .insight_modules.health_productivity_correlation import (
    correlate_health_output,
    correlate_subjective_output,
)
from .notify import deliver, LocalSink, Notification, NotifyConfig
from .schema import AggregateWindow, aggregate_window

import re as _re

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

# English shame/blame patterns. The companion now emits English digests (weekly
# rollups, anomaly alerts, trends), so the lint must guard those too — judgmental
# 2nd-person constructs ("you always...", "you failed to...") and shaming
# imperatives. Matched case-insensitively, word-bounded so e.g. "your" never
# trips "you ... ". These are deliberately narrow: descriptive prose ("activity
# ran higher than baseline") must pass untouched.
_SHAME_PATTERNS_EN: tuple[tuple[str, str], ...] = (
    (r"\byou always\b", "blame: 'you always...' implies recurring failure"),
    (r"\byou never\b", "blame: 'you never...' implies recurring failure"),
    (r"\byou failed\b", "judgment: 'you failed...'"),
    (r"\byou keep\b", "blame: 'you keep...' implies repeated failure"),
    (r"\byou should have\b", "regret-shame: 'you should have...'"),
    (r"\byou wasted\b", "judgment: 'you wasted...'"),
    (r"\byou can'?t even\b", "contempt: \"you can't even...\""),
    (r"\byet again\b", "sarcasm: 'yet again' implies repeated failure"),
)
_SHAME_RE_EN = tuple(
    (_re.compile(pat, _re.IGNORECASE), why) for pat, why in _SHAME_PATTERNS_EN
)


def shame_free_check(text: str) -> tuple[bool, str]:
    """Return ``(ok, reason)``. ``ok=True`` means clean."""
    for pat, why in _SHAME_PATTERNS:
        idx = text.find(pat)
        if idx >= 0:
            return False, f"shame leakage at byte offset {idx}: {why}"
    for rx, why in _SHAME_RE_EN:
        m = rx.search(text)
        if m is not None:
            return False, f"shame leakage at byte offset {m.start()}: {why}"
    return True, ""


DEFAULT_REPORT_ROOT = Path.home() / ".phantom-mesh" / "logs" / "phantom-companion"


def _emit_notification(
    *,
    kind,
    title,
    body,
    details,
    out_dir,
    notify_config=None,
    local_sink=None,
    relay_sink=None,
):
    """Deliver a report notification local-first. Local sink always; relay only if opted-in/consented (NotifyConfig). Notification text is shame-free linted before delivery."""
    check_text = f"{title}\n{body}"
    ok, reason = shame_free_check(check_text)
    if not ok:
        raise RuntimeError(f"refused to emit shame-leaking notification: {reason}")
    sink = local_sink if local_sink is not None else LocalSink(Path(out_dir) / "notifications")
    return deliver(
        Notification(kind=kind, title=title, body=body, details=details),
        config=notify_config or NotifyConfig(),
        local_sink=sink,
        relay_sink=relay_sink,
    )


def _health_inputs(agg: DailyAggregate) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Lift the ④ health sample + git output off the aggregate into the shape
    :func:`analyze_health_vs_output` consumes.

    P1-M3: this REPLACES the old ``health_data={}, commits=[]`` hard-code at the
    callsite. When ④ ingest has attached nothing the inputs stay empty and the
    insight reports a directional "waiting on" summary — never a fabricated
    correlation.
    """
    health_data: dict[str, Any] = {}
    if agg.health is not None:
        health_data = {
            "sleep_hr": agg.health.sleep_hr,
            "hrv_ms": agg.health.hrv_ms,
            "resting_hr": agg.health.resting_hr,
            "activity_min": agg.health.activity_min,
            "source": agg.health.source,
        }
    commits: list[dict[str, Any]] = []
    if agg.output is not None and agg.output.commits > 0:
        # We only need the count for the single-day directional summary; emit
        # placeholder rows so no commit message / SHA / content leaves device.
        commits = [{"n": i} for i in range(agg.output.commits)]
    return health_data, commits


def _run_insights(agg: DailyAggregate) -> list[dict[str, Any]]:
    health_data, commits = _health_inputs(agg)
    return [
        analyze_llm_usage(agg.events),
        analyze_attention(agg.events),
        analyze_health_vs_output(health_data=health_data, commits=commits),
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


# --- goal tracking section ---
_GOAL_MARKERS = {
    "on_track": "✅ on track",
    "drifting": "➰ drifting",
    "violated": "🌱 worth a nudge",
    "insufficient_data": "… still gathering data",
}


def render_goal_section(statuses) -> list:
    """Render a shame-free '🎯 Goal tracking' section from a GoalStatus list.

    Empty list -> no section (returns []). A missed goal reads as 'worth a
    nudge', never as failure."""
    if not statuses:
        return []
    lines = ["## 🎯 Goal tracking", ""]
    for st in statuses:
        label = st.goal.label or st.goal.metric
        marker = _GOAL_MARKERS.get(st.status, st.status)
        if st.status == "insufficient_data":
            lines.append(f"- **{label}** — {marker}.")
        else:
            lines.append(f"- **{label}** — {marker} ({st.actual} vs target {st.target}).")
    lines.append("")
    return lines


# ---------------------------------------------------------------------------
# P2-M1 — weekly cross-satellite pattern rollups (typed AggregateWindow)
# ---------------------------------------------------------------------------

# A still-pending jobseek lead whose most-recent activity day is at least this
# many days before the window's end ("now") is surfaced as a gentle, ranked
# "worth a nudge" — never as a failure.
JOBSEEK_STALE_DAYS = 7


def weekly_rollup(window: AggregateWindow) -> dict[str, Any]:
    """Lift a week of per-day signal into four behavioural-lens rollups.

    Consumes a typed :class:`AggregateWindow` (so it reads straight from the
    SQLite window cache), summing the per-day insight signal across the span:

    - ``llm_usage`` — provider call totals + the week's top provider.
    - ``attention`` — busiest hour-of-day across the week.
    - ``learning_roi`` — items read vs engaged, summed over ai-feed digests.
    - ``jobseek`` — companies investigated vs applied vs still-pending.

    Pure data — no judgemental wording is produced here; the renderer turns this
    into shame-free prose.
    """
    by_provider: Counter[str] = Counter()
    by_task: Counter[str] = Counter()
    by_hour: Counter[int] = Counter()
    investigated: set[str] = set()
    applied: set[str] = set()
    last_seen: dict[str, str] = {}  # company -> most-recent ISO day (first 10 of ts)
    items_read = 0
    items_engaged = 0

    for day in window.days:
        for ev in day.events:
            if ev.provider:
                by_provider[ev.provider] += 1
            if ev.kind:
                by_task[ev.kind] += 1
            # hour-of-day from the ISO timestamp, if present.
            ts = ev.timestamp
            if len(ts) >= 13 and ts[10] == "T":
                try:
                    by_hour[int(ts[11:13])] += 1
                except ValueError:
                    pass
            if ev.company:
                tags = set(ev.tags)
                if "jobseek" in tags or "company_research" in tags:
                    investigated.add(ev.company)
                    day10 = ev.timestamp[:10]
                    if day10 and day10 > last_seen.get(ev.company, ""):
                        last_seen[ev.company] = day10
                if ev.applied or "applied" in tags:
                    applied.add(ev.company)
        # learning ROI from the ai-feed digest log for the day.
        feed = day.satellite_logs.get("phantom-ai-feed")
        if feed is not None and feed.text:
            roi = analyze_learning_roi(feed.text)["details"]
            items_read += int(roi.get("items_read", 0))
            items_engaged += int(roi.get("items_engaged", 0))

    top_provider = by_provider.most_common(1)[0][0] if by_provider else None
    busiest_hour = by_hour.most_common(1)[0][0] if by_hour else None
    pending = sorted(investigated - applied)
    # Aging — a STILL-PENDING lead untouched for >= JOBSEEK_STALE_DAYS (measured
    # from its most-recent activity day to the window's end) is surfaced as a
    # ranked stale lead, oldest first. Reuses the scan above; no re-scan.
    stale_leads: list[dict[str, Any]] = []
    window_end = window.end
    if window_end is not None:
        end_date = date.fromisoformat(window_end)
        for company in pending:
            seen = last_seen.get(company)
            if not seen:
                continue
            days_open = (end_date - date.fromisoformat(seen)).days
            if days_open >= JOBSEEK_STALE_DAYS:
                stale_leads.append({"company": company, "days_open": days_open})
        stale_leads.sort(key=lambda s: (-s["days_open"], s["company"]))

    # P1-M3 — pair each day's ④ health sample with that day's developer output
    # and run the multi-day statistical correlation (gated on MIN_SAMPLES inside
    # correlate_health_output). Days missing either stream are dropped so the
    # Pearson/Spearman fit only sees complete pairs.
    health_output_samples = [
        {
            "day": d.day,
            "sleep_hr": d.health.sleep_hr,
            "commits": d.output.commits,
        }
        for d in window.days
        if d.health is not None and d.output is not None
    ]
    health_correlation = correlate_health_output(health_output_samples)

    return {
        "days_observed": len(window.days),
        "llm_usage": {
            "total_calls": sum(by_provider.values()),
            "by_provider": dict(by_provider),
            "by_task_kind": dict(by_task),
            "top_provider": top_provider,
        },
        "attention": {
            "busiest_hour": busiest_hour,
            "by_hour": dict(by_hour),
        },
        "learning_roi": {
            "items_read": items_read,
            "items_engaged": items_engaged,
            "engagement_ratio": round(items_engaged / items_read, 3) if items_read else 0.0,
        },
        "jobseek": {
            "investigated": len(investigated),
            "applied": len(applied),
            "pending": len(pending),
            "pending_companies": pending,
            "stale_leads": stale_leads,
        },
        "health_output": health_correlation,
    }


def render_weekly_report_from_window(window: AggregateWindow) -> str:
    """Render the cross-satellite weekly digest from a typed window. Shame-free."""
    roll = weekly_rollup(window)
    span = f"{window.start} → {window.end}" if window.days else "(empty window)"
    total_events = sum(len(d.events) for d in window.days)

    lines: list[str] = []
    lines.append(f"# phantom-companion — weekly report ({span})")
    lines.append("")
    lines.append("> Cross-satellite pattern pass. Tone: descriptive, never blame.")
    lines.append("")
    lines.append("## Rollup")
    lines.append(f"- Days observed: **{roll['days_observed']}**")
    lines.append(f"- Total events: **{total_events}**")
    lines.append("")

    llm = roll["llm_usage"]
    lines.append("## LLM usage")
    if llm["total_calls"] > 0:
        prov = ", ".join(f"{p}×{n}" for p, n in sorted(llm["by_provider"].items()))
        lines.append(f"- {llm['total_calls']} model calls this week ({prov}).")
        if llm["top_provider"]:
            lines.append(f"- Most-used provider: **{llm['top_provider']}**.")
    else:
        lines.append("- No model-call events captured this week — gathering baseline.")
    lines.append("")

    att = roll["attention"]
    lines.append("## Attention")
    if att["busiest_hour"] is not None:
        lines.append(
            f"- Busiest activity hour this week was around "
            f"**{att['busiest_hour']:02d}:00**."
        )
    else:
        lines.append("- Not enough timestamped events yet to spot a busy hour.")
    lines.append("")

    learn = roll["learning_roi"]
    lines.append("## Learning ROI")
    if learn["items_read"] > 0:
        pct = learn["engagement_ratio"] * 100
        lines.append(
            f"- {learn['items_read']} digest items surfaced, "
            f"{learn['items_engaged']} engaged with ({pct:.0f}%)."
        )
    else:
        lines.append("- No ai-feed digests this week — learning ROI idle.")
    lines.append("")

    job = roll["jobseek"]
    lines.append("## Jobseek follow-up")
    if job["investigated"] > 0:
        lines.append(
            f"- {job['investigated']} companies looked into, "
            f"{job['applied']} applied to, {job['pending']} still open."
        )
        if job["pending_companies"]:
            shown = ", ".join(job["pending_companies"][:5])
            lines.append(f"- Open to revisit when you have time: {shown}.")
        for lead in job.get("stale_leads") or []:
            lines.append(
                f"- Worth a nudge: **{lead['company']}** — open "
                f"{lead['days_open']} days, worth another look when you have time."
            )
    else:
        lines.append("- No jobseek-tagged activity this week — tracker idle.")
    lines.append("")

    hc = roll["health_output"]
    lines.append("## Health × output")
    lines.append(f"- {hc['summary']}")
    lines.append("")

    lines.append("## This week's note")
    if total_events == 0:
        lines.append(
            "No events captured this week. The companion is in baseline mode "
            "and becomes genuinely useful once a few weeks of activity exist."
        )
    else:
        lines.append(
            f"Captured {total_events} events across {roll['days_observed']} days "
            "— the rollups above are descriptions of what happened, for you to "
            "act on as you see fit."
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
    notify_config=None,
    local_sink=None,
    relay_sink=None,
) -> Path:
    requested_day = day or date.today().isoformat()
    effective_mesh_root = Path(mesh_root) if mesh_root else DEFAULT_REPORT_ROOT.parent.parent
    try:
        from .output_ingest import ingest_output

        ingest_output(
            repo=Path.cwd(),
            mesh_root=effective_mesh_root,
            days=[requested_day],
            overwrite=False,
        )
    except Exception:
        pass
    agg = aggregate_day(requested_day, mesh_root=mesh_root)
    text = render_daily_report(agg)
    # goal tracking (deterministic; no-op when no goals declared)
    from .goals import load_goals
    from .goal_eval import evaluate_goals
    from .checkin import read_checkins
    _goal_out = DEFAULT_REPORT_ROOT if out_root is None else Path(out_root)
    _goals = load_goals(_goal_out / "goals.json")
    if _goals:
        _checkins = read_checkins(_goal_out)
        _window = aggregate_window([agg.day], mesh_root=mesh_root)
        _section = render_goal_section(evaluate_goals(_window, _checkins, _goals))
        if _section:
            text = text.rstrip("\n") + "\n\n" + "\n".join(_section).rstrip("\n") + "\n"
    out_dir = Path(out_root) if out_root else DEFAULT_REPORT_ROOT
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{agg.day}-report.md"
    path.write_text(text, encoding="utf-8")
    _emit_notification(
        kind="daily_report",
        title="Your daily report is ready on your device.",
        body="Today's report has been written locally.",
        details={"report_path": str(path), "events": len(agg.events), "day": agg.day},
        out_dir=out_dir,
        notify_config=notify_config,
        local_sink=local_sink,
        relay_sink=relay_sink,
    )
    return path


def write_weekly_report(
    end_day: str | None = None,
    out_root: Path | None = None,
    mesh_root: Path | None = None,
    rollup: bool = True,
    notify_config=None,
    local_sink=None,
    relay_sink=None,
) -> Path:
    """Write the 7-day weekly report.

    ``rollup=True`` (default, P2-M1) renders the cross-satellite pattern digest
    off a typed :class:`AggregateWindow`; ``rollup=False`` keeps the legacy
    per-day-count renderer for callers that want the lighter view.
    """
    end = date.fromisoformat(end_day) if end_day else date.today()
    days = [(end - timedelta(days=i)).isoformat() for i in range(6, -1, -1)]
    window = None
    if rollup:
        # aggregate_window → aggregate_day loads the ④ health + developer-output
        # exports off disk per day, so the health×output correlation runs on real
        # data when present (and stays in honest baseline mode when absent).
        window = aggregate_window(days, mesh_root=mesh_root)
        text = render_weekly_report_from_window(window)
    else:
        aggs = list(aggregate_range(days, mesh_root=mesh_root).values())
        text = render_weekly_report(aggs)
    # goal tracking (deterministic; no-op when no goals declared)
    from .goals import load_goals
    from .goal_eval import evaluate_goals
    from .checkin import read_checkins
    _goal_out = DEFAULT_REPORT_ROOT if out_root is None else Path(out_root)
    _goals = load_goals(_goal_out / "goals.json")
    if _goals:
        _checkins = read_checkins(_goal_out)
        if window is None:
            window = aggregate_window(days, mesh_root=mesh_root)
        _section = render_goal_section(evaluate_goals(window, _checkins, _goals))
        if _section:
            text = text.rstrip("\n") + "\n\n" + "\n".join(_section).rstrip("\n") + "\n"
    out_dir = Path(out_root) if out_root else DEFAULT_REPORT_ROOT
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{end.isoformat()}-weekly-report.md"
    path.write_text(text, encoding="utf-8")
    _emit_notification(
        kind="weekly_digest",
        title="Your weekly review is ready on your device.",
        body="This week's digest has been written locally.",
        details={"report_path": str(path)},
        out_dir=out_dir,
        notify_config=notify_config,
        local_sink=local_sink,
        relay_sink=relay_sink,
    )
    return path


def write_anomaly_alerts(
    window,
    *,
    metric="attention",
    out_root=None,
    notify_config=None,
    local_sink=None,
    relay_sink=None,
):
    """Detect gated anomalies over a typed AggregateWindow for one metric, render the shame-free alert text, write it to <out>/<window.end>-anomaly-alerts.md, AND deliver a kind='anomaly' notification (local-first, relay gated). Returns the written Path."""
    from .anomaly_detector import detect_metric_anomalies, render_anomaly_alerts

    alerts = detect_metric_anomalies(window, metric)
    text = render_anomaly_alerts(alerts)
    out_dir = Path(out_root) if out_root else DEFAULT_REPORT_ROOT
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{window.end}-anomaly-alerts.md"
    path.write_text(text, encoding="utf-8")
    _emit_notification(
        kind="anomaly",
        title="Something in your recent data is worth a glance on your device.",
        body="An anomaly-alert summary has been written locally.",
        details={"report_path": str(path), "alert_count": len(alerts), "metric": metric},
        out_dir=out_dir,
        notify_config=notify_config,
        local_sink=local_sink,
        relay_sink=relay_sink,
    )
    return path


def write_trend_report(
    period: str = "monthly",
    end_day: str | None = None,
    out_root: Path | None = None,
    mesh_root: Path | None = None,
) -> Path:
    """Write a monthly (30d) / quarterly (90d) long-window trend digest (P3-M2)."""
    from .trends import build_trends_from_window, render_trend_report
    from .checkin import read_checkins

    n_days = 90 if period == "quarterly" else 30
    end = date.fromisoformat(end_day) if end_day else date.today()
    days = [(end - timedelta(days=i)).isoformat() for i in range(n_days - 1, -1, -1)]
    out_dir = Path(out_root) if out_root else DEFAULT_REPORT_ROOT
    # aggregate_window → aggregate_day loads the ④ health + developer-output
    # exports off disk per day; the nightly check-ins come from the report dir.
    window = aggregate_window(days, mesh_root=mesh_root)
    checkins_by_day = read_checkins(out_dir)
    # The 30/90-day trend window is long enough to clear the MIN_SAMPLES gate, so
    # this is where the REAL multi-day health×output Pearson/Spearman correlation
    # can actually fire in production (the 7-day weekly report never can). Pair
    # each day's ④ health sample with that day's output; days missing either are
    # dropped so the coefficient only sees complete pairs.
    paired = [
        {"day": d.day, "sleep_hr": d.health.sleep_hr, "commits": d.output.commits}
        for d in window.days
        if d.health is not None and d.output is not None
    ]
    health_correlation = correlate_health_output(paired)
    # P3-M2 keystone — the cross-domain (subjective × objective) correlation:
    # pair each day's nightly check-in mood with that day's commit output,
    # dropping days missing either stream, then run the SAME gated Pearson /
    # Spearman the health×output section uses (never reinvented).
    paired_subjective = [
        {"day": d.day, "mood": checkins_by_day[d.day].mood, "commits": d.output.commits}
        for d in window.days
        if d.output is not None and d.day in checkins_by_day
    ]
    subjective_correlation = correlate_subjective_output(paired_subjective)
    text = render_trend_report(
        build_trends_from_window(window, checkins_by_day),
        period=period,
        health_correlation=health_correlation,
        subjective_correlation=subjective_correlation,
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{end.isoformat()}-{period}-trends.md"
    path.write_text(text, encoding="utf-8")
    return path

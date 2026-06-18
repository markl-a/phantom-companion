> ARCHIVED 2026-06-19 — frozen historical snapshot; current status lives in /ROADMAP.md

# Tier 1 Initial Dev — 2026-05-22

## What's in

- `aggregator.py` — reads `~/.phantom-mesh/events/` + 5 sibling satellite
  logs + heartbeats into a single `DailyAggregate` dataclass. Pure-Python,
  no LLM, no network. The data plane.
- 5 insight modules (`insight_modules/`) — each exposes one
  `analyze_*(...) -> dict` with a uniform `{module, summary, details,
  baseline_ready}` contract. Each has real signal-extraction logic
  (`Counter`, regex, dataclass walk) but falls back to a "gathering
  baseline" stub when input is empty.
- `reporter.py` — composes daily + weekly markdown. **Every emitted line
  passes the shame-free lint** (mirror of phantom-mesh's
  `core/src/life_node/coach_prompts/lint.rs`). Best-effort
  `phantom coach review` subprocess for polish; deterministic template
  wins if the binary is missing or the polished output fails lint.
- `cli.py` — `phantom-companion daily-report` / `weekly-report`. Writes
  to `~/.phantom-mesh/logs/phantom-companion/<date>-report.md` by default.
- Tests:
  - `test_aggregator.py` — 5 cases, synthetic mesh layout
  - `test_insight_stubs.py` — 10 cases, structural contract + 1 real input
    each module
  - `test_reporter_shame_free.py` — 6 cases, including a regression test
    that proves a dirty `_invoke_coach` return is dropped, not propagated

## Why insights are stubs today

The five insight modules each have working extraction code, but the
*data they need* is not yet flowing in volume:

| Module | Needs | ETA |
|---|---|---|
| `llm_usage` | E002 events with `analysis.provider` populated | growing |
| `attention_switches` | 5+ timestamped events/day | growing |
| `health_productivity_correlation` | ④ secure-connector HealthKit ingest | not yet |
| `learning_roi` | ③ ai-feed daily digest in markdown | partial |
| `jobseek_followup` | events tagged `jobseek` with `company` meta | ad-hoc |

A useful proactive agent requires **~30 days of accumulated activity**
plus at least one of {③ ai-feed digest, ⑥ flow jobseek log} writing
on a real cadence. Until then, daily reports are honest:
"baseline mode; nothing useful to surface yet."

## What real LLM-driven insight needs

1. **Persistence layer** — events accumulating to `~/.phantom-mesh/events/`
   at a steady rate (the launchd job exists; needs validation that meta
   schemas are stable).
2. **Cross-day windows** — Tier 2 should add `aggregator.aggregate_window(N)`
   returning a `pandas.DataFrame` for correlation work.
3. **LLM call path** — `_invoke_coach` currently shells out to
   `phantom coach review`. Tier 2 should switch to phantom-mesh's MCP
   broker so cost routing (Gemini Flash for compression, Claude for the
   final delivery pass) goes through the existing meter.
4. **Shame-free at LLM layer** — the lint must run on LLM output too.
   `reporter.render_daily_report` already does this; keep the invariant
   when the call path changes.
5. **Push delivery** — file → Telegram → email later, all gated through
   the same `shame_free_check`.

## Out of scope today

- Modifying `~/Documents/GitHub/hailmary/phantom-companion/` (launchd uses
  the existing scaffold; do not touch).
- Modifying phantom-mesh itself.
- GitHub push.
- Real LLM invocation (deterministic template only).

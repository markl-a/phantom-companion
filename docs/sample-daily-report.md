# Sample daily report (synthetic data)

This is a **real run** of the `daily-report` CLI, captured verbatim. The input
is the synthetic mesh fixture used by `tests/test_aggregator.py` (no real
events, no personal data, no secrets). It exists so you can see what the
companion actually emits today without first accumulating weeks of activity.

Reproduce it yourself:

```bash
# 1. Lay down a synthetic ~/.phantom-mesh tree (5 events + 1 digest)
mkdir -p /tmp/synth-mesh/events/evt-{001,002,003,004,005} \
         /tmp/synth-mesh/logs/phantom-ai-feed

printf '{"timestamp":"2026-05-22T10:15:00Z","tags":["jobseek"],"company":"Garmin"}' \
  > /tmp/synth-mesh/events/evt-001/meta.json
printf '{"provider":"claude","task_kind":"code_review"}' \
  > /tmp/synth-mesh/events/evt-001/analysis.json
printf '{"timestamp":"2026-05-22T14:02:00Z","tags":["jobseek","applied"],"company":"Anthropic"}' \
  > /tmp/synth-mesh/events/evt-002/meta.json
printf '{"provider":"claude","task_kind":"doc"}' \
  > /tmp/synth-mesh/events/evt-002/analysis.json
printf '{"timestamp":"2026-05-21T11:00:00Z"}' \
  > /tmp/synth-mesh/events/evt-003/meta.json   # yesterday -> excluded
printf '{"timestamp":"2026-05-22T10:30:00Z","tags":["jobseek","company_research"],"company":"Micron"}' \
  > /tmp/synth-mesh/events/evt-004/meta.json
printf '{"provider":"mlx","task_kind":"code"}' \
  > /tmp/synth-mesh/events/evt-004/analysis.json
printf '{"timestamp":"2026-05-22T10:45:00Z"}' \
  > /tmp/synth-mesh/events/evt-005/meta.json
printf '{"provider":"claude","task_kind":"code"}' \
  > /tmp/synth-mesh/events/evt-005/analysis.json
printf '## Robust statistics for anomaly detection\nQ: When is MAD preferable to standard deviation?\n## On-device privacy patterns\n## Spaced repetition (SM-2)\nQ: How does the easiness factor evolve?\n' \
  > /tmp/synth-mesh/logs/phantom-ai-feed/2026-05-22.md
printf 'alive\n' > /tmp/synth-mesh/logs/phantom-enterprise-heartbeat.log  # -> enterprise=on

# 2. Run the CLI against it (offline; no phantom binary required)
python -m phantom_companion.cli --mesh-root /tmp/synth-mesh \
  daily-report --day 2026-05-22 --out /tmp/synth-out
cat /tmp/synth-out/2026-05-22-report.md
```

Note how `health_productivity_correlation` correctly reports `baseline`
("Waiting on: health ... commits ...") — there is no HealthKit / health
ingest behind it yet, and the report says so rather than inventing a number.
The "yesterday" event (`evt-003`) is correctly excluded from today's count.

---

# phantom-companion — daily report (2026-05-22)

> Proactive observation pass. Tone: supportive, never blame.

## Overview
- Events captured today: **4**
- Insight modules with usable signal: **3 / 5**
- Sibling satellites: phantom-ai-feed=off, phantom-flow=off, phantom-enterprise=on, phantom-secure-connector=off, phantom-training=off

## Insights
### llm_usage (ready)
4 LLM calls; top provider: claude (3)

### attention_switches (baseline)
Fewer than 5 timestamped events — peak-focus detection idle.

### health_productivity_correlation (baseline)
Waiting on: health (④ secure-connector ingest), commits (git activity feed)

### learning_roi (ready)
3 items in today's digest, 2 engaged (67% engagement)

### jobseek_followup (ready)
3 companies investigated, 1 applied, 2 pending follow-up

## Next-step suggestion
➡️ Signal is live in: llm_usage, learning_roi, jobseek_followup. Review the insights above and pick the one that matters most to you tomorrow.

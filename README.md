# ⑦ phantom-companion

> **Proactive behavior observer + LLM insight, running on phantom-mesh.**
> Life Track keystone — the project that turns the other six satellites into a coherent personal-improvement loop.

Status: **alpha — gathering baseline** (needs 2-3 months of accumulated
phantom-mesh events before insights become non-trivial).

## Pitch (1 line)

> Companion doesn't just answer when you ask — it watches how you actually
> live (LLM usage, commits, RSS reads, calendar, health, jobseek leads),
> finds patterns across the whole phantom-mesh, and writes you a daily +
> weekly report that is **shame-free by construction**.

## What it covers (8 痛點)

1. **LLM usage ROI** — which provider for which task, $/insight
2. **Attention switches** — context-switch density, peak focus windows
3. **Health × productivity** — sleep/HRV vs commit/PR quality
4. **Learning ROI** — RSS subscribed vs actually read vs actually used
5. **Jobseek follow-up** — investigated but not applied companies
6. **Daily review (shame-free)** — what worked, no blame language
7. **Weekly pattern surfacing** — cross-domain correlations
8. **Proactive suggestion delivery** — push to file → Telegram → email later

## How it composes

```
~/.phantom-mesh/events/        <- E002 event capture (meta.json + analysis.json)
~/.phantom-mesh/logs/
  phantom-ai-feed/             <- ③ digest + answered questions
  phantom-flow/                <- ⑥ jobseek triggers
  phantom-*-heartbeat.log      <- satellite liveness
                          │
                          ▼
              phantom_companion.aggregator
                          │
                          ▼
       5 insight_modules/* (LLM, attention, health, learning, jobseek)
                          │
                          ▼
                 reporter (shame-free lint)
                          │
                          ▼
   ~/.phantom-mesh/logs/phantom-companion/<date>-report.md
```

## Why this is the keystone

Companion is the **only** project that consumes output from all other six
satellites. It is also the project that makes phantom-mesh a *daily-life
product* rather than a developer toolbox.

The flip side: **it has nothing useful to say with no data**. Today's reports
are honest stubs that say so out loud.

## Hiring signal (招聘 alignment)

- **Garmin / wearable teams** — multi-source health × behavior correlation
- **Anthropic / LLM-tooling teams** — proactive agent, on-device privacy, cost-aware routing
- **Medical AI / digital-therapeutics** — shame-free coaching (a real, hard constraint), longitudinal personal data without cloud lock-in

## When this becomes valuable

After **30+ days of accumulated phantom-mesh events** AND at least one of
{③ ai-feed digest log, ⑥ flow jobseek log} being actively written. Until
then, insights are stub-shaped but structurally correct.

## License

Apache-2.0 — see [LICENSE](LICENSE).

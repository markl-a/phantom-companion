# Roadmap — phantom-companion

_Last updated 2026-06-19._

This file is the **single source of truth for project status**. README links here for
status; do not duplicate a status list elsewhere. Each "Shipped" bullet is grounded in a
real merge commit on `master` or in the design spec
([`docs/07-phantom-companion.md`](docs/07-phantom-companion.md)).

> **Honest caveat (by design, not a bug):** the engine is built and tested, but useful
> insight needs **~30+ days of accumulated phantom-mesh events** plus at least one of
> {③ ai-feed digest log, ⑥ flow jobseek log} writing on a real cadence. Run today and the
> reports are structurally correct but signal-thin — they degrade to honest
> "gathering baseline" stubs rather than inventing insight.

## Shipped

### Tier 1 — data plane + reporting foundation
- **Aggregator data plane** — `aggregator.py` reads `~/.phantom-mesh/events/` plus 6 sibling
  satellite logs/heartbeats into a single typed `DailyAggregate`; pure-Python, no LLM, no
  network. Sources events via `phantom recall` (decrypts) rather than the raw `events/` dir.
- **5 insight modules** — `llm_usage`, `attention_switches`, `health_productivity_correlation`,
  `learning_roi`, `jobseek_followup`; each exposes a uniform
  `{module, summary, details, baseline_ready}` contract with real extraction logic and an
  honest baseline-stub fallback when input is empty.
- **Shame-free reporter** — `reporter.py` composes daily/weekly markdown; every emitted line
  passes the shame-free lint (mirror of phantom-mesh `coach_prompts/lint.rs`). Deterministic
  template wins if the `phantom coach review` polish path is missing or fails the lint.
- **Real LLM coach pass** — `phantom coach review` wiring fixed (utf-8 decode), coach block
  merged into the report with a next-step line.
- **CLI** — `python -m phantom_companion.cli daily-report` / `weekly-report`, writing to
  `~/.phantom-mesh/logs/phantom-companion/<date>-report.md`.
- **Anomaly data plane absorbed** — `anomaly_detector` (health data plane) folded in.
- **Packaging hygiene** — Apache-2.0 LICENSE, CI workflow + badge, asciinema demo
  (`docs/demo.cast`), `.env`/`agents.toml`/`.venv*` gitignored.

### Tier 2 / Tier 3 — statistical layer (all behind the single-source `MIN_SAMPLES` ≈ 14-day density gate)
- **Foundation** — deterministic mock-mesh fixtures + single-source `MIN_SAMPLES` gate; typed
  `AggregateWindow` + normalized records + SQLite window cache.
- **P1-M3 health × output correlation** — real ④ secure-connector health (sleep / HRV /
  resting-HR / activity / source) and git output wired into a gated Pearson **and** Spearman
  correlation, with strictly no-causation wording; below the gate it falls back to
  directional-only.
- **P2-M1 weekly cross-satellite rollups** — LLM usage / attention / learning ROI / jobseek,
  off the typed `AggregateWindow` + SQLite cache.
- **P2-M2 density-gated anomaly alerts** — rolling-MAD over health / LLM-cost / attention;
  short noisy windows raise nothing; alerts are shame-free (with per-point density floor,
  local floor, and kind allowlist hardening).
- **P3-M1 notification delivery** — local-first sink always; off-device relay is opt-in,
  consent-gated, and payload-minimised (no PII crosses the device boundary). `deliver()` is
  wired into the real daily / weekly / anomaly report paths (was previously never called),
  plus a reachable anomaly-alerts CLI.
- **P3-M2 subjective trends** — nightly subjective check-in (`checkin`) + monthly / quarterly
  trend digests (`trends --period monthly|quarterly`), shame-free lint hardened for English.

### Production wiring (turning claimed-but-unreachable green into real green)
- **Output writer** — `ingest-output` writes `output-{day}.json` from real `git log`
  activity at the exact path the readers/aggregator consume; feeds the health × output
  correlation real data instead of a permanent baseline-empty.
- **Health ingest** — `ingest-health <export>` reuses `parse_secure_connector_export` +
  `write_health_samples` to write `health-<day>.json` at the path `read_health_window`
  reads; flips "Waiting on: health" to a real metric (real decryption / iOS / Garmin / Relay
  paths remain env-blocked).
- **Mood × output cross-domain correlation** — `correlate_subjective_output` pairs nightly
  check-in mood with daily commit output through the same `_pearson_r` / `_spearman_r` +
  `MIN_SAMPLES` gate; a Mood × output section is rendered in the trends report behind the
  n-gate. This is the spec keystone "跨領域相關性 (心情)".
- **Stale jobseek leads (aging)** — weekly rollup computes `days_open` for still-pending
  jobseek-tagged leads (never applied), emits a ranked stale-leads list (≥7 days, oldest
  first), and renders a shame-free "Worth a nudge" line per lead — adding the missing time
  dimension to jobseek follow-up.

## In progress

- None tracked as actively in-flight in this repo. The shipped engine is awaiting real
  longitudinal data volume (see the honest caveat above) rather than further code to become
  useful.

## Planned / next

From the design spec ([`docs/07-phantom-companion.md`](docs/07-phantom-companion.md)) — the
"Nice to have (M4+)" and post-M4 horizon:

- **Push fan-out** — extend delivery beyond the local sink: Telegram → email, all gated
  through the same shame-free check.
- **MCP broker LLM path** — switch `_invoke_coach` from shelling out to `phantom coach review`
  over to phantom-mesh's MCP broker so cost routing (e.g. Gemini Flash for compression,
  Claude for final delivery) goes through the existing meter.
- **Statistically-sound long windows** — health vs productivity over ≥60–90 days of data.
- **Multimodal demos (P2)** — food-photo recognition + calorie estimate; focus-session audio
  summary.
- **Family-shared dashboard** — parents' health view (⑦ + ④ integration).
- **Personal-model integration (②)** — use accumulated personal pattern to fine-tune a small
  "knows-you" model via phantom-training.
- **Post-M4** — automatic intervention suggestions; behavioral A/B testing framework.

### Explicitly NOT doing (from the spec)
- Clinical diagnosis (ruled out by BIG-GOAL).
- Surveillance-style monitoring (violates consent-gating).
- Shame-based interfaces ("you stayed up late again") — replaced by "better/worse than
  yesterday's choice, and why".

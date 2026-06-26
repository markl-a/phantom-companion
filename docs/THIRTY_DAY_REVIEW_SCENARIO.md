# 30-Day Review Scenario Contract

`phantom-companion review-scenario` turns a synthetic `demo-loop` bundle into a
P3 usefulness evidence package. It is intended to show what the companion can
support after 30 local days without using private data, network access, cloud
LLMs, or live sensors.

## Command

```powershell
python -m phantom_companion.cli demo-loop --out <source-bundle> --end 2026-05-30 --days 30 --seed 42
python -m phantom_companion.cli review-scenario --source <source-bundle> --out <scenario-bundle>
```

The command prints `<scenario-bundle>\scenario-manifest.json`.

## Accepted Source

`review-scenario` accepts only a `demo-loop` bundle whose manifest declares:

- `mode=synthetic_demo_loop`
- `data_policy=synthetic_only`
- `private_data_included=false`
- `external_network=false`
- `llm_coach=disabled`

The command rejects windows shorter than 30 days.

## Bundle Layout

```text
<scenario-bundle>/
  scenario-manifest.json
  review-scenario.json
  summary.md
  README.md
```

## Scenario Manifest

`scenario-manifest.json` is stable JSON with sorted keys and schema version `1`.

Required fields:

- `mode`: `thirty_day_review_scenario`
- `source_mode`: `synthetic_demo_loop`
- `data_policy`: `synthetic_only`
- `private_data_included`: always `false`
- `raw_payloads_included`: always `false`
- `external_network`: always `false`
- `llm_coach`: `disabled`
- `files`: bundle-relative paths to the README, scenario JSON, and summary

## Review Scenario JSON

`review-scenario.json` contains:

- 30-day coverage counts for event days, wellness source days, output source
  days, and nightly check-ins
- readiness booleans for long-window trends, wellness/output association,
  mood/output association, and weekly rollup availability
- aggregate signal summaries such as trend metric names and association
  direction
- supported review tasks and prompts
- explicit boundaries: no medical advice, causal claims, cloud LLM default, live
  sensor default, or raw private export

The scenario re-aggregates the source bundle locally. It does not copy event
payload content, per-day measurements, check-in rows, source filenames, account
identifiers, external service exports, network output, or LLM text.

## Determinism

Two scenario bundles from the same source bundle must produce byte-stable
`scenario-manifest.json`, `review-scenario.json`, `summary.md`, and `README.md`.

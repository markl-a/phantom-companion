# Open Source Readiness

Project: `phantom-companion`
Current phase: P3 30-day review usefulness scenario slice verified
Master plan: `../../PHANTOM-SATELLITES-OPEN-SOURCE-MASTER-PLAN.md`

## Shipped Features

- Local-first companion/reporting CLI.
- CLI entrypoint: `phantom-companion = phantom_companion.cli:main`.
- Help surface verified with `python -m phantom_companion.cli --help`.
- Subcommands include `daily-report`, `weekly-report`, `trends`, `anomaly-alerts`, `checkin`, `ingest-output`, `ingest-health`, `demo-loop`, `privacy-export`, `goal`, and `goals`.
- Root README points to `docs/phantom-companion.md`.
- Root README now includes a synthetic isolated quickstart using `--mesh-root` and `--out`.
- Privacy, storage, deletion, and synthetic public data policy are documented in `docs/PRIVACY_AND_DEMO.md`.
- P2 synthetic reporting loop contract is documented in `docs/SYNTHETIC_REPORTING_LOOP.md`.
- `demo-loop` writes a deterministic synthetic mesh, check-ins, daily/weekly/monthly reports, and `manifest.json`.
- P2 privacy-preserving report export contract is documented in `docs/PRIVACY_EXPORT_BUNDLE.md`.
- `privacy-export` accepts only safe synthetic demo bundles and writes a deterministic redacted shareable bundle with `export-manifest.json`, `shareable-context.json`, `report-template.md`, and `README.md`.
- P3 30-day review usefulness scenario contract is documented in `docs/THIRTY_DAY_REVIEW_SCENARIO.md`.
- `review-scenario` accepts only safe synthetic demo bundles of at least 30 days and writes `scenario-manifest.json`, `review-scenario.json`, `summary.md`, and `README.md`.
- The scenario bundle proves which review tasks are ready from synthetic local data: long-window trends, wellness/output co-movement, mood/output co-movement, weekly activity review, and consent prompts for deeper local imports.
- Test suite baseline after P2 synthetic reporting loop additions: `python -m pytest -q` passed with 165 tests.
- Test suite baseline after P2 privacy export additions: `python -m pytest -q` passed with 169 tests.
- Test suite baseline after P3 30-day review scenario additions and manifest-path hardening: `python -m pytest -q` passed with 175 tests.

## Planned Or Deferred Features

- Broader personal context and reflection layer: adapter contract, goal/routine mapping, richer local data sources.
- ActivityWatch wrapper hardening, sensor integrations, and cloud LLM reflection are out of initial release scope unless explicitly gated.

## Install And Test Commands

```powershell
python -m pip install -e .
python -m pytest -q
python -m phantom_companion.cli --help
python -m phantom_companion.cli --mesh-root <temp>\mesh ingest-health <synthetic-health.json>
python -m phantom_companion.cli checkin "2026-06-26 gut=4 mood=4 sleep=7.4" --out <temp>\out
python -m phantom_companion.cli --mesh-root <temp>\mesh daily-report --day 2026-06-26 --out <temp>\out
python -m phantom_companion.cli --mesh-root <temp>\mesh trends --period monthly --end 2026-06-26 --out <temp>\out
python -m phantom_companion.cli demo-loop --out <temp>\bundle --end 2026-05-30 --days 30 --seed 42
python -m phantom_companion.cli privacy-export --source <temp>\bundle --out <temp>\safe-export
python -m phantom_companion.cli review-scenario --source <temp>\bundle --out <temp>\scenario
```

Observed P2 synthetic reporting result on 2026-06-26:

```text
165 passed in 87.31s
```

Observed P2 privacy export targeted result on 2026-06-26:

```text
3 passed in 1.92s
```

Observed P2 privacy export full-suite result on 2026-06-26:

```text
169 passed in 89.24s
```

Observed P3 30-day review scenario targeted result on 2026-06-26:

```text
3 passed in 5.35s
```

Observed P3 30-day review scenario full-suite result on 2026-06-26:

```text
175 passed in 99.95s
```

## Fixture And Data Policy

- Public examples must use synthetic timelines and synthetic health/output data.
- No private personal events, health records, work logs, or real user timeline exports may be committed.
- Any adapter stub must be clearly marked as stub/prototype.
- Shareable exports must include only redacted aggregate metadata, report headings, and templates; raw payloads and exact metric values remain excluded.
- Review scenario bundles must include only coverage/readiness summaries, aggregate signal labels, review tasks, review prompts, and explicit unsupported boundaries; raw payloads and per-day private rows remain excluded.

## Safety And Privacy Risks

- Reports can reveal sensitive lifestyle and health patterns.
- LLM-backed analysis must remain optional and must not upload private local data by default.
- Trend claims need enough history; docs must state data-history limits.

## Blockers To Next Phase

- None for the current P3 30-day review scenario slice. Next phase should harden consent-gated adapters or import ergonomics without enabling live sensors by default.

## Evidence

- `pyproject.toml` declares package `phantom-companion` and script `phantom-companion`.
- `README.md` points to `docs/phantom-companion.md`.
- `README.md` includes isolated synthetic quickstart.
- `README.md` includes `demo-loop` as the deterministic reporting artifact bundle.
- `README.md` includes `privacy-export` as the redacted shareable report-template bundle.
- `README.md` includes `review-scenario` as the 30-day usefulness evidence bundle.
- `docs/PRIVACY_AND_DEMO.md` documents storage under `~/.phantom-mesh/logs/phantom-companion`, deletion, and synthetic-only public data policy.
- `docs/SYNTHETIC_REPORTING_LOOP.md` documents `manifest.json`, report paths, `synthetic_only`, `private_data_included=false`, `external_network=false`, and `llm_coach=disabled`.
- `docs/PRIVACY_EXPORT_BUNDLE.md` documents `export-manifest.json`, `shareable-context.json`, `report-template.md`, `redacted_aggregate_only`, `raw_payloads_included=false`, `external_network=false`, and `llm_coach=disabled`.
- `docs/THIRTY_DAY_REVIEW_SCENARIO.md` documents `scenario-manifest.json`, `review-scenario.json`, `summary.md`, `synthetic_only`, `raw_payloads_included=false`, `external_network=false`, and `llm_coach=disabled`.
- `python -m pytest tests/test_thirty_day_review_scenario_contract.py -q`: 3 passed.
- `python -m pytest tests/test_thirty_day_review_scenario_contract.py tests/test_open_source_contract.py tests/test_privacy_export_contract.py -q`: 13 passed.
- `python -m pytest tests/test_privacy_export_contract.py -q`: 3 passed.
- `python -m pytest tests/test_privacy_export_contract.py tests/test_open_source_contract.py -q`: 7 passed.
- `python -m pytest tests/test_demo_loop_contract.py tests/test_open_source_contract.py tests/test_fixtures.py tests/test_weekly_rollup.py tests/test_checkin_trends_e2e.py -q`: 23 passed.
- `python -m pytest -q`: 169 passed.
- `python -m pytest --collect-only -q`: 169 tests collected.
- `python -m phantom_companion.cli --help`: help OK.
- Isolated smoke:
  - `ingest-health` wrote normalized `health-2026-06-26.json` under temp mesh.
  - `checkin` wrote temp `checkins.jsonl`.
  - `daily-report` and `trends` wrote local Markdown reports under temp output.
- P2 synthetic reporting smoke:
  - `demo-loop --out <temp> --end 2026-05-30 --days 30 --seed 42` wrote `manifest.json`.
  - Manifest recorded `mode=synthetic_demo_loop`, 30 health files, 30 output files, 30 check-ins, `private_data_included=false`, `external_network=false`, and `llm_coach=disabled`.
  - Manifest report paths existed for `2026-05-30-report.md`, `2026-05-30-weekly-report.md`, and `2026-05-30-monthly-trends.md`.
- P2 privacy export smoke:
  - `privacy-export --source <temp>\bundle --out <temp>\safe-export` wrote `export-manifest.json`.
  - Manifest recorded `mode=privacy_export_bundle`, `data_policy=redacted_aggregate_only`, `private_data_included=false`, `raw_payloads_included=false`, `external_network=false`, and `llm_coach=disabled`.
  - `shareable-context.json` included only coverage counts, report heading names, selected template, and explicit redaction flags.
  - Contract tests verify private note strings, exact wellness values, source-file names, and raw field names do not appear in exported files.
  - Manifest report paths are validated as bundle-relative and must stay inside the source bundle before headings are read.
- P3 30-day review scenario smoke:
  - `review-scenario --source <temp>\bundle --out <temp>\scenario` wrote `scenario-manifest.json`.
  - Manifest recorded `mode=thirty_day_review_scenario`, `data_policy=synthetic_only`, `private_data_included=false`, `raw_payloads_included=false`, `external_network=false`, and `llm_coach=disabled`.
  - `review-scenario.json` recorded 30 days of event, wellness source, output source, and nightly check-in coverage.
  - Readiness flags showed long-window trends, wellness/output association, mood/output association, and weekly rollup availability.
  - Scenario artifacts explicitly mark medical advice, causal claims, cloud LLM default, live sensor default, and raw private export as unsupported.
  - Contract tests verify private note strings, exact wellness values, private event ids, source-file names, and check-in filenames do not appear in scenario files.
  - Manifest `mesh_root` and `reports_root` paths are validated as bundle-relative and must stay inside the source bundle before aggregation.
- `agy` reviewer result: no medium/high blockers. Low-severity follow-ups were fixed by adding a `--days < 7` error-path test and clarifying `stores.health_dir` / `stores.output_dir` in `docs/SYNTHETIC_REPORTING_LOOP.md`.
- `agy` P2 privacy export reviewer result: `NO BLOCKERS` for live sensor default, raw private event/note/health metric/source filename leak, cloud LLM/network implication, nondeterminism, docs/tests mismatch, missing synthetic/no-live flags, missing redaction contract, or health/medical advice drift.
- `agy` P3 review scenario reviewer result: initial blocker found for manifest path traversal / absolute path acceptance in `privacy-export` report paths and `review-scenario` roots. Fixed with bundle containment validation and regression tests. Re-review result: `NO BLOCKERS`.

## P4 Release-Prep Slice 1

Status: governance baseline added; this does not mark the project release-ready.

Evidence:
- `CONTRIBUTING.md` defines the contribution workflow, required test command, readiness-doc update rule, and no-private-data/no-credentials boundary.
- `SECURITY.md` defines private vulnerability reporting, supported version scope, 7-day acknowledgement target, and safe report contents.
- `python -m pytest tests/test_release_prep_contract.py -q`: 1 passed.
- `python -m pytest -q`: 176 passed.

Remaining P4 work: full release gate, final docs audit, package metadata audit, release notes, tag plan, and maintainer sign-off.

## P4 Release-Prep Slice 2

Status: final release gate checklist added; this does not mark the project release-ready.

Evidence:
- `CHANGELOG.md` records the unreleased governance/release-checklist work and points back to readiness evidence.
- `docs/RELEASE_CHECKLIST.md` documents final tests, dependency/license review, secret/private-data scan, known limitations, and manual maintainer approval.
- `python -m pytest tests/test_release_prep_contract.py -q`: 2 passed.
- `python -m pytest -q`: 177 passed.

Remaining P4 work: execute final scans, complete dependency/license review, finalize release notes, and record manual maintainer approval.

## P4 Release-Prep Slice 3

Status: final scan and direct dependency/license audit recorded; not release-ready.

Evidence:
- `docs/FINAL_RELEASE_AUDIT.md` records scan scope, `high_conf_secret_hits=0`, direct dependency/license review, and remaining release blockers.
- Direct release-scope dependency review: no runtime dependencies beyond Python stdlib.
- `python -m pytest tests/test_release_prep_contract.py -q`: 3 passed.
- `python -m pytest -q`: 178 passed.

Remaining P4 work: release notes finalization, tag plan, final maintainer approval, and separate review for any future live sensor/private-health adapter.

## P4 Release-Prep Slice 4

Status: maintainer approval recorded, conductor sign-off complete, and release-candidate tag created.

Evidence:
- `docs/RELEASE_NOTES.md` records public release-candidate notes, known limitations, and verification pointers.
- `docs/TAG_PLAN.md` records proposed tag `v0.1.0-alpha.0`, required approval-before-tag sequence, and rollback steps.
- `docs/PUBLIC_RELEASE_APPROVAL.md` records `Status: approved` with approver, approval date, and approved tag.
- Conductor root approval packet `PHANTOM-SATELLITES-PUBLIC-RELEASE-APPROVAL.md` records all ten candidate tags as approved.
- `.github/workflows/ci.yml` runs an explicit `release-prep gate` against `tests/test_release_prep_contract.py`.
- `python -m pytest tests/test_release_prep_contract.py -q`: 5 passed.
- `python -m pytest -q`: 180 passed.

Remaining P4 work: none for the approved release-candidate tag.

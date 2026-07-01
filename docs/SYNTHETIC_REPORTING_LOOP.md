# Synthetic Reporting Loop Contract

`phantom-companion demo-loop` is the P2 public alpha artifact loop. It lets a
new contributor exercise the core companion value without real personal data,
network access, cloud LLMs, external sensors, or a live `phantom` binary.

## Command

```powershell
python -m phantom_companion.cli demo-loop --out <bundle> --end 2026-05-30 --days 30 --seed 42
```

The command prints `<bundle>\manifest.json`.

## Bundle Layout

```text
<bundle>/
  manifest.json
  mesh/
    events/
    logs/
      phantom-secure-connector/health-YYYY-MM-DD.json
      phantom-companion/output-YYYY-MM-DD.json
      phantom-ai-feed/YYYY-MM-DD.md
      phantom-flow/YYYY-MM-DD.log
  reports/
    checkins.jsonl
    2026-05-30-report.md
    2026-05-30-weekly-report.md
    2026-05-30-monthly-trends.md
```

## Manifest Schema

`manifest.json` is stable JSON with sorted keys and schema version `1`.

Required top-level fields:

- `schema_version`: currently `1`.
- `mode`: `synthetic_demo_loop`.
- `end_day`, `days`, `seed`: the reproducibility inputs.
- `data_policy`: `synthetic_only`.
- `private_data_included`: always `false`.
- `external_network`: always `false`.
- `llm_coach`: `disabled`.
- `mesh_root`, `reports_root`: bundle-relative directories.
- `inputs`: event day count, health file count, output file count, check-in count.
- `reports`: bundle-relative paths for `daily`, `weekly`, and `trends`.
- `stores`: bundle-relative paths for `checkins`, `health_dir`, and `output_dir`.
  `health_dir` and `output_dir` are directories containing per-day sample files.

## Report Contract

For `--end 2026-05-30 --days 30`, the reports are:

- `reports/2026-05-30-report.md`
- `reports/2026-05-30-weekly-report.md`
- `reports/2026-05-30-monthly-trends.md`

All generated reports must pass `phantom_companion.reporter.shame_free_check`.
Reports summarize aggregate signals and must not expose raw synthetic event
summaries, private health records, browser history, real work logs, or any
external-account data.

## Determinism

Two runs with the same `--end`, `--days`, and `--seed` must produce byte-stable
manifest, check-in, and report files. The loop disables the optional LLM coach
path by construction, so output does not depend on local model availability.

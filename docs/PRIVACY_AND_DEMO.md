# Privacy And Public Demo Contract

`phantom-companion` reports over personal timelines, health exports, work output,
goals, and subjective check-ins. Public demos must therefore use synthetic data
only and must run against isolated local directories.

## Isolated Smoke Demo

```powershell
$root = Join-Path $env:TEMP ("phantom-companion-demo-" + [guid]::NewGuid().ToString("N"))
$mesh = Join-Path $root "mesh"
$out = Join-Path $root "out"
$export = Join-Path $root "health.json"

@'
{"date":"2026-06-26","sleepHours":"7.4","heartRateVariability":52,"restingHeartRate":54,"activeMinutes":35,"device":"synthetic_health"}
'@ | Set-Content -LiteralPath $export -Encoding UTF8

python -m phantom_companion.cli --mesh-root $mesh ingest-health $export
python -m phantom_companion.cli checkin "2026-06-26 gut=4 mood=4 sleep=7.4" --out $out
python -m phantom_companion.cli --mesh-root $mesh daily-report --day 2026-06-26 --out $out
python -m phantom_companion.cli --mesh-root $mesh trends --period monthly --end 2026-06-26 --out $out

Remove-Item -LiteralPath $root -Recurse -Force
```

Expected shape:

- `ingest-health` writes normalized `health-2026-06-26.json` under the isolated
  mesh root.
- `checkin` appends to isolated `checkins.jsonl`.
- `daily-report` and `trends` write local Markdown reports under the isolated
  output directory.
- No private health export, work log, browser history, or real timeline is
  required.

## Shareable Privacy Export

After `demo-loop` writes a synthetic bundle, `privacy-export` can derive a safe
template-review bundle:

```powershell
python -m phantom_companion.cli privacy-export --source <source-bundle> --out <export-bundle>
```

The export is accepted only from a synthetic demo bundle with private data,
network access, and LLM coaching disabled. The output contains
`export-manifest.json`, `shareable-context.json`, `report-template.md`, and a
bundle README. It carries coverage counts and report heading names, not event
payload content, exact wellness measurements, check-in values, work log content,
account identifiers, network output, or LLM text.

See `docs/PRIVACY_EXPORT_BUNDLE.md` for the schema contract.

## Storage And Deletion

- Default report/check-in storage is local under
  `~/.phantom-mesh/logs/phantom-companion`.
- `--mesh-root` and `--out` allow tests and demos to isolate all generated data.
- Deletion is ordinary filesystem deletion of the chosen mesh/output directory.

## Public Data Policy

- Public fixtures must be synthetic and small enough to inspect in review.
- Do not commit real health records, location traces, personal calendar entries,
  browser/activity exports, work logs, goals, or check-ins.
- LLM-backed analysis must remain optional and must not upload private local
  data by default.
- Trend claims need enough history. Reports should stay in baseline mode when
  the history window is too short.

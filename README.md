# phantom-companion

[![CI](https://github.com/markl-a/phantom-companion/actions/workflows/ci.yml/badge.svg)](https://github.com/markl-a/phantom-companion/actions/workflows/ci.yml)
![license: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue)
[![phantom-mesh ecosystem](https://img.shields.io/badge/ecosystem-phantom--mesh-purple)](https://github.com/markl-a/phantom-mesh)

> **跨裝置 + 自動 + LLM-insight + shame-free 的個人改善迴圈** — phantom-mesh 七專案的 keystone(唯一消費其他六個輸出),看你怎麼活、跨整個 mesh 找 pattern、寫日/週/月/季報,語言結構上保證不羞辱。

## Quickstart

```powershell
python -m pip install -e .
python -m pytest -q
python -m phantom_companion.cli --help
```

Synthetic, isolated demo:

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

Deterministic reporting artifact bundle:

```powershell
$bundle = Join-Path $env:TEMP ("phantom-companion-loop-" + [guid]::NewGuid().ToString("N"))
python -m phantom_companion.cli demo-loop --out $bundle --end 2026-05-30 --days 30 --seed 42
Get-Content (Join-Path $bundle "manifest.json")
```

The bundle writes a synthetic mesh tree, nightly check-ins, daily/weekly/monthly
reports, and a machine-readable manifest. The artifact contract is documented in
[docs/SYNTHETIC_REPORTING_LOOP.md](docs/SYNTHETIC_REPORTING_LOOP.md).

Privacy-preserving shareable export:

```powershell
$safe = Join-Path $env:TEMP ("phantom-companion-safe-export-" + [guid]::NewGuid().ToString("N"))
python -m phantom_companion.cli privacy-export --source $bundle --out $safe
Get-Content (Join-Path $safe "shareable-context.json")
```

The export contains only redacted aggregate metadata, report headings, and a
review template. It does not include raw event payloads, exact wellness
measurements, check-in values, work log content, network output, or LLM text.
The contract is documented in
[docs/PRIVACY_EXPORT_BUNDLE.md](docs/PRIVACY_EXPORT_BUNDLE.md).

30-day review usefulness scenario:

```powershell
$scenario = Join-Path $env:TEMP ("phantom-companion-review-" + [guid]::NewGuid().ToString("N"))
python -m phantom_companion.cli review-scenario --source $bundle --out $scenario
Get-Content (Join-Path $scenario "scenario-manifest.json")
```

The scenario bundle proves which 30-day review tasks are ready from synthetic
local data: long-window trends, wellness/output co-movement, mood/output
co-movement, weekly activity review, and consent prompts for deeper imports.
The contract is documented in
[docs/THIRTY_DAY_REVIEW_SCENARIO.md](docs/THIRTY_DAY_REVIEW_SCENARIO.md).

Public demos use synthetic local data only. Privacy, storage, and deletion rules
are documented in [docs/PRIVACY_AND_DEMO.md](docs/PRIVACY_AND_DEMO.md).

📄 完整文件(狀態/路線圖/方向):見 [docs/phantom-companion.md](docs/phantom-companion.md)

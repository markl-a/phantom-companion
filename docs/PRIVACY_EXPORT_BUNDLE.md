# Privacy Export Bundle Contract

`phantom-companion privacy-export` turns a synthetic `demo-loop` bundle into a
shareable report-template package. It is intended for public issue discussion,
template review, and import/export ergonomics testing without exposing local
personal context.

## Command

```powershell
python -m phantom_companion.cli demo-loop --out <source-bundle> --end 2026-05-30 --days 30 --seed 42
python -m phantom_companion.cli privacy-export --source <source-bundle> --out <export-bundle>
```

The command prints `<export-bundle>\export-manifest.json`.

## Accepted Source

`privacy-export` accepts only a `demo-loop` bundle whose manifest declares:

- `mode=synthetic_demo_loop`
- `data_policy=synthetic_only`
- `private_data_included=false`
- `external_network=false`
- `llm_coach=disabled`

Bundles that declare private data, network access, or LLM coaching are rejected.

## Bundle Layout

```text
<export-bundle>/
  export-manifest.json
  shareable-context.json
  report-template.md
  README.md
```

## Export Manifest

`export-manifest.json` is stable JSON with sorted keys and schema version `1`.

Required fields:

- `mode`: `privacy_export_bundle`
- `source_mode`: `synthetic_demo_loop`
- `template`: `weekly-review` or `monthly-review`
- `data_policy`: `redacted_aggregate_only`
- `private_data_included`: always `false`
- `raw_payloads_included`: always `false`
- `external_network`: always `false`
- `llm_coach`: `disabled`
- `files`: bundle-relative paths to the context, template, and README files

## Shareable Context

`shareable-context.json` contains only:

- window metadata such as end day and day count
- coverage counts for event days, source-file counts, check-in count, and report count
- report heading names extracted from generated reports
- the selected review template name
- explicit redaction flags

It does not include event payload content, exact wellness measurements,
subjective check-in values, work log content, account identifiers, external
service exports, network output, or LLM text.

Any report path declared by the source manifest must be bundle-relative and
must resolve inside the source bundle before headings are read.

## Determinism

Two exports from the same source bundle and template must produce byte-stable
`export-manifest.json`, `shareable-context.json`, `report-template.md`, and
`README.md`.

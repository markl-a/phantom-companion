# Final Release Audit

Status: release candidate approved and tagged.

Date: 2026-06-27

## Scope

- Default release surface: `phantom_companion` package and synthetic/local public commands.
- Excluded scan noise: `.git`, `.ensemble`, `.venv`, `venv`, `__pycache__`, `.pytest_cache`, `reports`, `dist`, and `build`.

## Secret And Private-Data Scan

Command class: `rg` high-confidence patterns for private keys, AWS access keys, GitHub tokens, OpenAI-shaped keys, Slack tokens, and Google API keys.

Result: `high_conf_secret_hits=0`.

## Dependency/License Review

- Project license: Apache-2.0.
- Default runtime dependencies: none beyond Python stdlib.
- Dev dependencies: `pytest>=7` and `ruff>=0.6`, used for local/CI verification only.

Direct default release-scope dependency/license review result: pass.

## Current Verification

- `python -m pytest tests\test_packaging.py tests\test_release_prep_contract.py -q`: 8 passed.
- `python -m pip install -e . --dry-run --no-deps`: editable metadata OK; would install `phantom-companion-0.1.0a0`.
- `python -m pip wheel . --no-deps -w <temp>`: built `phantom_companion-0.1.0a0-py3-none-any.whl`.
- `python -m phantom_companion.cli --help`: help OK.
- `python -m phantom_companion.cli demo-loop --out <bundle> --end 2026-05-30 --days 30 --seed 42`: wrote synthetic demo manifest with `private_data_included=false`, `external_network=false`, and `llm_coach=disabled`.
- `python -m phantom_companion.cli privacy-export --source <bundle> --out <export>`: wrote privacy export manifest with `private_data_included=false`, `raw_payloads_included=false`, `external_network=false`, and `llm_coach=disabled`.
- `python -m phantom_companion.cli review-scenario --source <bundle> --out <scenario>`: wrote review scenario manifest with `private_data_included=false`, `raw_payloads_included=false`, `external_network=false`, and `llm_coach=disabled`.
- `python -m ruff check .`: all checks passed.
- `python -m pytest -q`: 183 passed.
- High-confidence secret scan: `high_conf_secret_hits=0`.

## Remaining Publication Gates

- Manual maintainer approval is recorded in `docs/PUBLIC_RELEASE_APPROVAL.md`.
- Local annotated tag `v0.1.0-alpha.0` was created after the root strict approval verifier and conductor sign-off passed.
- Any future live sensor or private health-data adapter requires separate dependency/license and privacy review.

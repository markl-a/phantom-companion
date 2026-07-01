# Contributing

This repository is in pre-release open-source preparation. Contributions are welcome when they keep the public path deterministic, documented, and safe by default.

## Development Workflow

1. Start from the documented quickstart in `README.md`.
2. Keep demos synthetic, fixture-based, offline, mock, dry-run, or read-only unless the README explicitly documents an opt-in live path.
3. Run `python -m pytest -q` before opening a pull request.
4. Update public contracts, examples, and `docs/OPEN_SOURCE_READINESS.md` when behavior, schemas, commands, or safety boundaries change.
5. Keep changes scoped to one feature or fix. Avoid unrelated rewrites in the same pull request.

## Data And Secrets

- Commit no private data, no credentials, no access tokens, no customer data, and no local machine paths that reveal private environments.
- Use synthetic fixtures for examples and tests.
- Do not add network, cloud, broker, connector, scanning, training, or live-data behavior as a default path.
- If a change needs an opt-in live path, document the gate, required environment variables, expected artifacts, and rollback behavior before implementation.

## Security Reports

Do not report vulnerabilities through a public issue. Follow `SECURITY.md` so reports can be handled privately.

# Changelog

All notable public-release changes should be recorded here.

## Unreleased

No unreleased changes after the approved `v0.1.0-alpha.0` release candidate.

## 0.1.0-alpha.0 - 2026-06-27

### Added

- P4 release-prep governance baseline with `CONTRIBUTING.md` and `SECURITY.md`.
- Release checklist covering final tests, secret/private-data scan, dependency/license review, release notes, and manual approval.
- CI release gate now installs the package, builds a wheel, runs ruff, runs the full test suite, and runs a deterministic demo-loop smoke.
- Public package metadata now includes PyPI classifiers, project URLs, and a `dev` extra for release verification tooling.

### Verification

- Current verification evidence is recorded in `docs/OPEN_SOURCE_READINESS.md`.

### Release Status

- Release candidate approved by maintainer `mark` on 2026-06-27.
- Approved release-candidate tag: `v0.1.0-alpha.0`.

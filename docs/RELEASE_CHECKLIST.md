# Release Checklist

Status: release-prep complete for approved public source release candidate.

Completed before local release-candidate tag creation:

- Run `python -m pytest -q` and record the result in `docs/OPEN_SOURCE_READINESS.md`.
- Confirm `CONTRIBUTING.md`, `SECURITY.md`, `LICENSE`, and `CHANGELOG.md` are present.
- Complete a dependency/license review and document any incompatible license risk.
- Run a final secret and private data scan; public artifacts must contain no credentials, no private data, and no raw production logs.
- Recheck high-risk behavior remains opt-in, synthetic, fixture-based, offline, mock, dry-run, or read-only by default.
- Update release notes with known limitations and deferred live integrations.
- Record manual maintainer approval before publishing a public release.

Current gate result: final scans, dependency/license review, release notes, manual maintainer approval, conductor sign-off, and release-candidate tag creation are complete.

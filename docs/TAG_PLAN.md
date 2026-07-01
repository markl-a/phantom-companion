# Tag Plan

Status: annotated release-candidate tag created.

## Candidate Tag

- Proposed tag: `v0.1.0-alpha.0`
- Tag type: annotated git tag after approval
- Release branch: current prepared branch

## Required Steps

1. Confirm `docs/OPEN_SOURCE_READINESS.md` has current full-test evidence.
2. Confirm `docs/FINAL_RELEASE_AUDIT.md` has current scan and dependency/license evidence.
3. Confirm `docs/RELEASE_NOTES.md` is accurate for the release candidate.
4. Record manual maintainer approval in `docs/PUBLIC_RELEASE_APPROVAL.md`.
5. Create the tag only after approval. Completed for `v0.1.0-alpha.0`.

## Rollback

If a tag is created incorrectly, delete the remote tag, delete the local tag, update release notes, and rerun the release gate before creating a replacement tag.

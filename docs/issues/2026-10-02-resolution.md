# GitHub issue audit, 2026-10-02

Pulled main to c26a016. Snapshot includes all nine issues and their comments;
seven are closed and require no new change. Open issues are #16 and #17.

## #16 — journaled relocation

Added `cw layout --relocate --set ROLE=FOLDER`, preview by default, apply through
the existing exact-byte transaction engine. Scope is schema-v1 authoring role
folders. Assets/sidecars remain opaque; Markdown and binder path references,
layout selections, generated indexes and directories participate in undo.
The CLI rejects unsafe or overlapping moves instead of merging content.
No changes to legacy migration semantics or schema-v2 translation migration.

## #17 — component routing

Audited canonical project-feedback and Hieronymus integration resources,
generated Claude/ZCode instructions, and installed Hieronymus 0.10.1 skills.
The CWS feedback entry point already selects ownership correctly. No competing
tracker default was found in these sources. The public report does not include
the effective prompt or the historical agent routing trace, so the original
misrouting and its source cannot be deterministically reproduced from available
evidence. Do not claim a discovered root cause.

Added the ownership boundary at the CWS integration entry point and workflow,
with regression checks for a CWS layout defect in a Hieronymus-enabled project
and an actual Hieronymus service defect in canonical and generated runtimes.
This hardens the instruction path; it does not prove model routing behavior.

## Validation

Full unittest suite: 903 tests passed. Focused relocation/routing suite after
adding the explicit SHA-256 file map: 21 tests passed. Relocation tests cover
read-only preview, exact apply/undo, binary assets and opaque review sidecars,
draft status/target preservation, relative/encoded/external links, occupied
paths, overlap, symlinks, nested projects, stale content, and injected failure
rollback. Distribution validation, generation synchronization, `git diff
--check`, and generation of all 36 deterministic archives passed.

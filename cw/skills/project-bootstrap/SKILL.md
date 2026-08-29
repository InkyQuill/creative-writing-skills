---
name: project-bootstrap
description: "Locate, create, migrate, or reconcile portable project instruction entrypoints across supported agent harnesses."
---

# Project Bootstrap

Use this skill whenever project instructions must be located, created, migrated,
or reconciled. It owns entrypoint filenames and compatibility only. Load
`/qi-layer` for the quality and structure of instruction content.

`AGENTS.md` is the canonical project-instruction source. Codex, Pi, OpenCode
v2, current ZCode, and OpenCode-derived MiMo Code read it directly. Claude Code
uses a regular sibling `CLAUDE.md` whose first line is exactly `@AGENTS.md`.
That file is a portable import shim, not a second generic instruction source.
ZCode does not expand the Claude import at runtime.

Do not create filesystem symlinks by default. They are unreliable on Windows
without Developer Mode or administrator access and may be flattened or rejected
by packaging and sync tools. An existing correct `CLAUDE.md -> AGENTS.md`
symlink may remain when it is safe.

Before changing anything, inspect every applicable instruction entrypoint at
the relevant directory level. Nested local guidance follows the same pair
contract. Then follow [entrypoint reconciliation](resources/entrypoint-reconciliation.md).
Preview material migrations or semantic differences. The approved contract is
already authority for unambiguous shim creation and exact consolidation, so do
not ask for redundant confirmation.

Return the resolved project-instruction path to the calling skill. Other skills
must work with that resolution and must not independently guess a filename.

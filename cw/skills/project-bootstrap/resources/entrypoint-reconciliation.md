# Entrypoint Reconciliation

Resolve instruction entrypoints independently at each directory that carries
local guidance.

Classify safety before applying the existence rows below. An unsafe or
unreadable entry, broken symlink, or broken import always takes precedence and
uses the blocking row. In particular, a lone regular `CLAUDE.md` beginning
`@AGENTS.md` is a broken import when its sibling target is absent; preserve it
instead of treating it as ordinary only-Claude migration input.

## Resolution Matrix

| Observed state | Action |
|---|---|
| Neither entrypoint exists | Resolve `AGENTS.md` as canonical. The calling setup or qi workflow writes substantive content; create a regular sibling `CLAUDE.md` containing exactly `@AGENTS.md` plus a trailing newline in the same change. |
| Only regular `AGENTS.md` exists | Create the regular `CLAUDE.md` shim automatically. This safe mechanical compatibility needs no additional confirmation. |
| Only non-broken regular `CLAUDE.md` exists | Inspect it. Move directly and unambiguously shared guidance into `AGENTS.md`; retain only the import plus a clearly labeled Claude-specific tail. Ask once only when shared versus Claude-specific intent is materially ambiguous. Never discard content. |
| Both regular files exist | Accept a shim beginning `@AGENTS.md`, optionally followed by a clearly labeled Claude-specific tail. Consolidate exact duplicated generic content mechanically. For contradictory or ambiguously divergent instructions, show the difference and ask only for the semantic choice. |
| Correct existing symlink | A safe `CLAUDE.md -> AGENTS.md` symlink may remain unchanged. Do not create a new symlink. |
| Broken import or symlink, unsafe path, or unreadable file | Preserve bytes, report the exact path, and block only this reconciliation. |

For a material migration, show a preview or diff before writing. Never silently
overwrite divergent instructions, never maintain two generic copies, and never
claim `CLAUDE.md` is ZCode's live instruction source.

After reconciliation, verify that the regular shim starts with the literal
line `@AGENTS.md`, that its import resolves to the sibling canonical file, and
that any remaining tail is explicitly Claude-specific. Repeat this check for
each nested directory where local project instructions exist.

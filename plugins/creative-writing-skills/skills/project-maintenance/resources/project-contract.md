# Project Contract

The nearest ancestor containing `project.md` is the project root. Nested
projects are independent boundaries. The managed roots are `project.md`,
`story/`, `work/`, `kb/`, and `.creative-writing/`.

Other root entries are allowed. Leave unknown files untouched: initialization,
migration, repair, and reindexing must preserve them. Markdown outside managed
roots may produce an informational finding, but Git is optional and the CLI
does not require a repository to provide transaction history or undo.

## Manifest language and prose profile

Schema v1 requires a non-empty `language` tag and accepts any project language.
Bundled resources and checks resolve the normalized primary tag, so `ru-RU`
uses `ru` support and `en-GB` uses `en` support without constraining future
languages.

`prose-profile` is optional and defaults to `general`, which adds no profile
overlay. When present it is a lower-case slug with letters, numbers, and
internal hyphens. Bundled selectors are `general`, `light-novel`,
`classical-literary`, and `literary-fiction`; preserve valid custom selectors.
Existing schema-v1 projects need no migration only to add the default.

## Protected paths and metadata

Generic edits must not modify:

- generated `_index.md` files;
- `.creative-writing/`, including its transaction journal and context cache;
- CLI-managed draft lifecycle metadata such as `base-revision` and status.

Use domain commands such as `reindex`, `draft set-status`, `draft rebase`,
`draft accept`, and `recover` for those changes. Paths outside the nearest
project, paths inside another nested project, and linked mutation targets are
also protected from automatic writes.

Direct author prose edits remain valid input. The agent owns mechanical
maintenance: hashes, tags, indexes, base revisions, repair-command selection
and execution, and runtime setup. The CLI performs only the deterministic
mechanics requested by the agent. Never ask a nontechnical author to edit an
index, calculate a hash, copy a tag, or maintain a base revision.

Contract drift that can be repaired without guessing is an agent task. An
unknown schema, unsafe path, changed precondition, ambiguous anchor, or
unrecoverable journal requires a conflict finding and no write. These
mechanical constraints do not decide literary meaning.

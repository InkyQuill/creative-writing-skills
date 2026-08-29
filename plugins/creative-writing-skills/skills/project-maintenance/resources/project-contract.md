# Project Contract

The nearest ancestor containing `project.md` is the project root. Nested
projects are independent boundaries. The managed roots are `project.md`,
`story/`, `work/`, `kb/`, and `.creative-writing/`.

Other root entries are allowed. Leave unknown files untouched: initialization,
migration, repair, and reindexing must preserve them. Markdown outside managed
roots may produce an informational finding, but Git is optional and the CLI
does not require a repository to provide transaction history or undo.

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
maintenance: calculate and carry hashes, preserve source tags, update generated
indexes, choose domain commands for lifecycle fields, and execute previewed
repair commands. Never ask a nontechnical author to edit an index, calculate a
hash, copy a tag, or maintain a base revision.

Contract drift that can be repaired without guessing is an agent task. An
unknown schema, unsafe path, changed precondition, ambiguous anchor, or
unrecoverable journal requires a conflict finding and no write. These
mechanical constraints do not decide literary meaning.

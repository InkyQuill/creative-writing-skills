---
name: project-maintenance
description: "Optional deterministic maintenance for author-owned creative-writing workspaces. Use when an agent needs to inspect project structure, preview initialization, or run the bundled cw CLI."
---

# Project Maintenance

Keep mechanical maintenance out of the author's writing flow. If a safe,
deterministic, recoverable repair is needed to finish the requested work,
preview and apply it within the authorized scope, then summarize the repair
briefly. Do not hand the author a list of routine lint findings or ask them to
perform CLI steps. Working-draft typography is opt-in; accepted-prose spacing
can be normalized with `fix-prose-typography` after inspecting its preview.

Use the bundled CLI when its capability fits the requested work. Resolve the
explicit workspace or nearest `project.md`/`.cws-layout.json` marker; without
markers use the supplied directory or a standalone file's parent. No manifest,
tags or scaffold are required for ordinary checks. Resolve this installed skill
directory and run its entrypoint directly before optional launcher setup:

```bash
python3 <project-maintenance-skill>/resources/cli/cw.py --version
python3 <project-maintenance-skill>/resources/cli/cw.py check links <file-or-directory>
```

Keep the command's working path inside the user's requested project. Preview
every journaled mutation first; add `--apply` only after its complete diff is
understood and remains within the request. Derived cache is separate:
`context --snapshot` writes a restricted snapshot immediately without
`--apply`, and `clean-context` never enters transaction history. The CLI
performs the deterministic mechanics the agent requests. The agent owns hashes,
tags, indexes, base revisions, repair-command selection and execution, and
runtime setup.

Use actual author filenames first. Optional `cw layout inspect` exposes
inherited purpose tags; `cw get-folder <role>` is a compatibility convenience,
not a prerequisite. `cw layout tag PATH --kind directory|file --add TAG`
previews tags; repeated `--remove TAG` excludes inherited tags. Use `.` for flat
folders. Tags do not establish authority or opt files into lifecycle metadata.
An explicit output path works without tags; configure `layout destination`
only when useful. Never invent default folders for an unconfigured workspace.

Check `coverage` in reports. Metadata, language-specific rules, managed drafts,
continuity schemas or translation may be unassessed/inapplicable. Continue the
creative work using the actual sources; do not repair an author's layout into a
scaffold. Use safe ordinary file tools for authorized named edits when a CLI
feature does not apply, and do not promise CLI undo for those edits.

Interpret results agent-first: exit 0 continues; exit 1 means inspect the
findings, repair what is safe, and continue unrelated creative work; exit 2
means follow `/cli-doctor`. Mechanical warnings never block prose review or
unrelated creative work.

Read only the resource needed for the current operation:

- [Command reference](resources/command-reference.md) for command shapes and
  preview/apply behavior.
- [Project contract](resources/project-contract.md) for managed roots,
  protected paths, and preservation boundaries.
- [External project contract](resources/external-project-contract.md) for the
  versioned structural roles and portable compatibility examples exposed to
  independent tools.
- [Agent workflows](resources/agent-workflows.md) for checks, drafts,
  migration, history, undo, recovery, and failure handling.

## Literary translation mechanics

For translation work, use the opt-in schema-v2 contract and `cw translation`
commands in the command reference. Keep schema-v1 author projects unchanged
until translation is enabled. Source originals are opaque and immutable to
agent edits; refreshed extraction is a separately journaled working revision.

Run `cw check translation` for coverage, references and stale drafts; reindex
through `cw reindex`. A finding about changed inputs requests literary review,
not automatic retranslation or replacement. Direction language controls checks
of its output. Build context with relevant entities and relationships and keep
its exact snapshot with the draft. The CLI never performs literary translation
or decides whether a proposed rule is true; /literary-translation,
/translation-memory and /translation-review supply that judgment.

For an existing authoring project whose role folders need to move, preview
`cw layout --relocate --set ROLE=FOLDER --format json`. Review the concrete
semantic file map with the author before `--apply`; use the transaction ID for
undo. See [command reference](resources/command-reference.md) for supported
references, opaque sidecars and relocation boundaries.

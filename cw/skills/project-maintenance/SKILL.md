---
name: project-maintenance
description: "Deterministic maintenance for canonical creative-writing projects. Use when an agent needs to inspect project structure, preview initialization, or run the bundled cw CLI."
---

# Project Maintenance

Keep mechanical maintenance out of the author's writing flow. If a safe,
deterministic, recoverable repair is needed to finish the requested work,
preview and apply it within the authorized scope, then summarize the repair
briefly. Do not hand the author a list of routine lint findings or ask them to
perform CLI steps. Working-draft typography is opt-in; accepted-prose spacing
can be normalized with `fix-prose-typography` after inspecting its preview.

Use the bundled CLI for mechanical story-project work. Resolve the nearest
ancestor containing `project.md`, resolve this installed skill directory, and
run its entrypoint directly before considering optional launcher setup:

```bash
python3 <project-maintenance-skill>/resources/cli/cw.py --version
python3 <project-maintenance-skill>/resources/cli/cw.py check all <project>
```

Keep the command's working path inside the user's requested project. Preview
every journaled mutation first; add `--apply` only after its complete diff is
understood and remains within the request. Derived cache is separate:
`context --snapshot` writes a restricted snapshot immediately without
`--apply`, and `clean-context` never enters transaction history. The CLI
performs the deterministic mechanics the agent requests. The agent owns hashes,
tags, indexes, base revisions, repair-command selection and execution, and
runtime setup.

Before reading or writing a role folder, resolve it with `cw get-folder
<role>` from the project root. Roles are `chapters`, `side-stories`, `drafts`,
`characters`, `world`, `plans`, `brainstorm`, `reviews`, and `archive`. The command returns
a project-relative path without creating it. Never assume a default folder
when a project selected another one. If the role is ambiguous, inspect
`cw layout` and save the actual choice with `cw layout --set ROLE=FOLDER
--apply` only when the author's intent or existing evidence settles it.

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

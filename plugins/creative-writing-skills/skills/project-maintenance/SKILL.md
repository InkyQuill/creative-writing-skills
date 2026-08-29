---
name: project-maintenance
description: Deterministic maintenance for canonical creative-writing projects. Use when an agent needs to inspect project structure, preview initialization, or run the bundled cw CLI.
---

# Project Maintenance

Use the bundled CLI for mechanical story-project work. Resolve the nearest
ancestor containing `project.md`, resolve this installed skill directory, and
run its entrypoint directly before considering optional launcher setup:

```bash
python3 <project-maintenance-skill>/resources/cli/cw.py --version
python3 <project-maintenance-skill>/resources/cli/cw.py check all <project>
```

Keep the command's working path inside the user's requested project. Preview
every mutation first; add `--apply` only after its complete diff is understood
and remains within the request. The CLI owns discovery, validation, hashes,
tags, indexes, base revisions, transactions, and repair commands.

Interpret results agent-first: exit 0 continues; exit 1 means inspect the
findings, repair what is safe, and continue unrelated creative work; exit 2
means follow the `cli-doctor` workflow. Mechanical warnings never block prose review or
unrelated creative work.

Read only the resource needed for the current operation:

- [Command reference](resources/command-reference.md) for command shapes and
  preview/apply behavior.
- [Project contract](resources/project-contract.md) for managed roots,
  protected paths, and preservation boundaries.
- [Agent workflows](resources/agent-workflows.md) for checks, drafts,
  migration, history, undo, recovery, and failure handling.

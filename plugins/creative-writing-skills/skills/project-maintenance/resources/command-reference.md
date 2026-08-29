# Command Reference

Resolve the installed `project-maintenance` skill and invoke
`resources/cli/cw.py` directly with Python. Run from the relevant project path
or pass the project path where the command accepts one. A user-scoped `cw`
launcher is optional convenience, never a prerequisite.

Use `--format json` when structured output helps. Read-only commands and
previews do not modify the project. Mutating commands preview by default and
write only when repeated with `--apply`.

## Inspect and prepare context

```text
check structure|links|kb|continuity|drafts|prose|journal|all [project]
doctor
context draft|chapter|kb <path> [--as trusted|reader|character:<id>] [--snapshot]
clean-context
reindex
```

Use `check all` for the mechanical floor, or a focused checker while working
in one domain. A restricted context snapshot is agent preparation; trusted
context can use the selected source paths directly. Preview `clean-context`
and `reindex`, then add `--apply` only for the reviewed change.

## Project and draft lifecycle

```text
init [path] --title <title> --language <language>
draft create <target> [--draft-path <path>]
draft set-status <draft> working|review|ready
draft rebase <draft>
draft accept <draft>
draft abandon <draft>
migrate --plan
migrate --preview <plan.json>
migrate --apply <plan.json> --expect-plan-hash <hash>
```

Preview every lifecycle mutation. Draft acceptance changes the story target;
it does not promote material into the KB. Acceptance and KB promotion remain
separate author-confirmed decisions. The agent carries plan hashes and
`base-revision` values between commands without asking the author to maintain
them.

## Exact edits and transaction history

```text
edit replace|insert-before|insert-after|delete ...
edit apply <operations.json>
history
history show <transaction-id>
undo <transaction-id>
recover <transaction-id>
```

Put large anchors and replacement bodies in files. Preview edit, undo, and
recover operations before `--apply`. `history` is append-only evidence: undo
creates a new inverse transaction and refuses diverged targets. Recovery rolls
an interrupted transaction back only when journal evidence still proves the
safe before-state.

## Exit status

- Exit 0: the command completed; continue the requested workflow.
- Exit 1: findings or a safe conflict need agent inspection. Continue any
  unrelated creative work while planning a bounded repair.
- Exit 2: the CLI could not execute. Follow the `cli-doctor` workflow; keep
  runtime setup away from the author.

# Agent Workflows

## Establish the mechanical floor

1. Resolve the nearest `project.md` from the material the user placed in scope.
2. Run the bundled `resources/cli/cw.py` directly with Python; do not make
   launcher installation a prerequisite.
3. Run `check all` or the checker relevant to the task and inspect its
   structured findings.
4. Preview each unambiguous repair, confirm the diff stays in scope, then use
   `--apply`. Run the affected check again.

Exit 0 continues. Exit 1 means inspect findings and continue unrelated
creative work; repairable mechanical warnings never block prose review or
unrelated creative work. Exit 2 routes to the `cli-doctor` workflow for
agent-owned runtime setup.

## Prepare review context

Use `context draft`, `context chapter`, or `context kb` with the appropriate
trusted, reader, or character role. Treat unresolved references as warnings to
inspect, not permission to invent context. Restricted snapshots are derived
cache; clean stale snapshots through a previewed `clean-context` transaction.

## Manage a draft

Create the working copy with `draft create`, change lifecycle state through
`draft set-status`, and run checks before requesting author acceptance. If the
target changed, preview `draft rebase`; do not overwrite it. Preview
`draft accept` only after the author confirms acceptance. KB promotion is a
different confirmation and transaction. Use `draft abandon` for a rejected
draft so it moves to archive without becoming canon.

## Migrate an older layout

Run `migrate --plan`, review classifications with the author where literary
meaning is ambiguous, then run `migrate --preview <plan.json>`. Apply only that
reviewed plan with its expected plan hash. Preserve unknown files and never
reinterpret ambiguous material as canon automatically.

## Correct a mistake or interrupted write

Use `history` and `history show <transaction-id>` to inspect exact recorded
changes. Preview `undo <transaction-id>` and apply it only while its after-state
still matches; never rewrite history or overwrite newer work. For an
interrupted prepared/applying transaction, inspect `doctor`, preview
`recover <transaction-id>`, and apply rollback only when the CLI reports it as
recoverable. Preserve conflicted bytes and journal evidence for manual agent
diagnosis.

All hashes, tags, indexes, base revisions, repair commands, and optional
launcher setup are agent responsibilities. Ask the author for semantic choices
and approval boundaries, not mechanical maintenance.

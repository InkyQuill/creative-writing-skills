# Repair Policy

Use the JSON result from `cw doctor --format json` as diagnosis, not as
authorization to mutate the project. Keep the diagnosis read-only before any
repair and never perform a hidden repair while collecting findings.

## Priority

The first priority is an incomplete transaction or recovery blocker. Report
its consequence and exact next action. For recovery, use the repair group's
ordered `"commands"` list and execute `commands[*].argv` as described below;
do not derive a command from the finding text. Do not interleave a new mutation
with unresolved recovery.

After recovery is clear, classify the remaining material findings:

- **Safe mechanical:** deterministic scaffold, index, metadata, or journal
  repair whose intended content is already established. The agent performs it
  through `/project-maintenance` using the structured command procedure below.
- **Cosmetic or repairable drift:** record the exact mechanical next action,
  but continue unrelated creative work. It is not an author blocker, and the
  agent must retain ownership of the project mechanics.
- **Semantic contradiction or retcon:** never autofix it. Route the finding to
  the owning domain skill, such as `/story-memory`, `/kb-management`, or
  `/story-planning`. Ask a content question only if different answers would
  change canon.

## Structured Commands

Read the JSON `"groups"` array in order. For each repair group, preserve its
ordered `"commands"` list and execute each `commands[*].argv` directly as an
argument vector, without shell interpolation. Never rebuild or split an
argument vector from rendered text.

Run the preview command for each repair group first. Inspect its complete diff,
scope, and current applicability before executing the matching apply
`"argv"`; stop when the preview is unsafe, stale, or outside the request. This
preview-before-apply rule also governs incomplete-transaction recovery: execute
the recovery `commands[*].argv` entries in order, inspect the preview, and only
then execute the corresponding apply vector.

The command `"display"` field and each finding `"next_action"` are reporting
text only. Never execute or pass `display` or `next_action` to a shell. They may
explain the consequence and next step, but executable input comes exclusively
from a structured `"argv"` array.

## Reporting

Summarize only material findings. Give each one its impact and an exact next
action: a preview/apply command pair for safe mechanics, the owning domain
skill for semantic analysis, or the single canon-changing question that needs
the author's answer. Keep nonblocking cosmetic drift out of the critical path.

# Repair Policy

Use the JSON result from `cw doctor --format json` as diagnosis, not as
authorization to mutate the project. Keep the diagnosis read-only before any
repair and never perform a hidden repair while collecting findings.

## Priority

The first priority is an incomplete transaction or recovery blocker. Report
its consequence and exact next action, then use the recovery command exposed
by the finding. Do not interleave a new mutation with unresolved recovery.

After recovery is clear, classify the remaining material findings:

- **Safe mechanical:** deterministic scaffold, index, metadata, or journal
  repair whose intended content is already established. The agent performs it
  through `$project-maintenance`: preview the exact command, inspect its full
  diff and boundaries, then run the matching `--apply` command.
- **Cosmetic or repairable drift:** record the exact mechanical next action,
  but continue unrelated creative work. It is not an author blocker, and the
  agent must retain ownership of the project mechanics.
- **Semantic contradiction or retcon:** never autofix it. Route the finding to
  the owning domain skill, such as `$story-memory`, `$kb-management`, or
  `$story-planning`. Ask a content question only if different answers would
  change canon.

## Reporting

Summarize only material findings. Give each one its impact and an exact next
action: a preview/apply command pair for safe mechanics, the owning domain
skill for semantic analysis, or the single canon-changing question that needs
the author's answer. Keep nonblocking cosmetic drift out of the critical path.

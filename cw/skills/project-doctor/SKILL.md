---
name: project-doctor
description: "Diagnose a canonical creative-writing project and plan safe repairs when its structure, transactions, indexes, or canon checks report problems."
---

# Project Doctor

Diagnose before changing anything. Run `cw doctor --format json` as a read-only
first step and retain its structured findings. Diagnosis performs no hidden or
implicit repair. If the CLI itself cannot run, route to `/cli-doctor`; do not
guess at project changes.

Treat incomplete transactions and recovery blockers as the highest priority.
Until they have an exact recovery action, do not start another journaled
mutation. Then separate the remaining findings into safe mechanical drift and
semantic questions.

Summarize only material findings to the author. For each material finding,
report an exact next action: the command the agent will preview, the skill that
owns the decision, or the content question that must be answered. Do not dump
the raw JSON when a short consequence-and-action summary is sufficient.

The agent handles safe mechanical repairs through `/project-maintenance`.
Always run and inspect the command's preview before the corresponding
`--apply`. Execute only the structured argument vectors supplied by the doctor,
without shell interpolation; keep project mechanics with the agent rather than
the author. Cosmetic or repairable drift does not block unrelated creative
work: continue that work while keeping the repair action explicit.

Semantic contradictions or retcons are never autofixed. Route them to the
owning domain skill. Ask a content or canon question only when different
answers would change canon; otherwise resolve the mechanics without handing
project maintenance back to the author.

Read [the repair policy](resources/repair-policy.md) when classifying findings
or planning a repair.

---
name: project-feedback
description: Report a suspected bug, regression, confusing behavior, broken script, invalid generated Claude or ZCode output, or incorrect or contradictory instruction owned by this repository's Creative Writing Skills plugin, bundled cw CLI, or project docs and contracts.
---

# Project Feedback

Continue safe diagnosis and the user's primary task while handling feedback.
Feedback must never replace or unnecessarily block the actual work. A report is
useful only for a problem owned by this repository: its canonical Creative
Writing Skills plugin skills, bundled `cw` CLI, generated Claude or ZCode
distribution, or project docs and contracts.

Every canonical skill shipped by this repository is in scope. That includes
authored and internal skills such as `story-memory`, plus defects in this
repository's pinned or adapted vendored copy of a skill such as `llm-writing`
and in the packaging or distribution of that local copy. Ownership follows the
local implementation or adaptation, not whether the skill originated here.

Do not file feedback for ordinary story-content ambiguity, author preference,
an unrelated harness bug, a local configuration mistake, or a problem already
durably tracked by the active task or plan. An upstream issue may still be
useful when the durable task record does not cover the reusable project defect.
Do not activate or file here for Superpowers, Codex, Claude, or ZCode harness
bugs, GitHub CLI (`gh`), or any skill or plugin not shipped by this repository.
An upstream defect in the original project from which a skill was vendored is
also out of scope when this repository's pinned copy, adaptation, packaging,
and distribution are working as intended. If ownership is unclear, diagnose it
first and do not file in this repository until local ownership is established.

Use the fixed [Creative Writing Skills issue tracker](https://github.com/InkyQuill/creative-writing-skills/issues).
Search both open and closed issues before proposing or creating a report. Use
an available read-only GitHub or web route even when `gh` or authentication is
unavailable. Inspect the body and discussion of plausible matching issues; do
not deduplicate on title alone. Reuse an existing issue when it covers the same
root problem. For a genuine regression, reference and link the prior issue in
the new draft.

Verify the problem from local evidence, prose, or instructions before
creation. Reproduce it, inspect the relevant source, compare generated output,
and resolve obvious facts without delegating diagnosis to the author. Ask only
when ambiguity, conflicting intent, sensitive disclosure, or a choice would
materially change the report.

Treat a new issue as high-confidence only when all of these are true:

- project ownership is clear;
- the problem is reproducible or directly evidenced;
- it is not misuse, an unsupported local setup, or a transient external
  failure;
- no existing issue covers the root problem;
- a concise redacted title and actionable body are ready.

Capability-check immediately before creation: `gh` is available, an
authenticated account is usable, the repository is reachable, and issues are
enabled. Maintainer or repository write access is not required and does not
determine public issue-creation capability; an ordinary authenticated GitHub
user may be able to file an issue.

When confidence and capability are both present, read
[issue reporting](resources/issue-reporting.md) and create the issue without a
redundant confirmation or additional approval. The approved workflow already
authorizes this high-confidence external creation. Report the created URL.

If `gh`, authentication, network, or permission is unavailable, or creation
fails, apply the one-pass fallback in the reporting resource. Never request a
login, enter a retry loop, or block the primary task. Preserve a complete draft
in an existing safe task/report area or return it inline.

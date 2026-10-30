---
name: world-creation
description: >
  Explore, develop, or settle story-world ideas using existing lore and character
  context. Use for cultures, powers, history, geography, institutions, or other
  setting material; keep manuscript prose read-only in this workflow.
---

# World Creation

Match the author's desired kind of help. A request for possibilities is not an
invitation to interrogate every dependency or build a complete taxonomy.

## Choose the Conversation

- **Explore:** offer distinct possibilities, associations, or concrete scenarios.
  Keep alternatives provisional and let ambiguity remain creative space.
- **Develop:** follow a selected idea's consequences for people and the world.
  Test relevant limits and interactions without demanding encyclopedic coverage.
- **Settle:** resolve a consequential choice and record the author's decision
  within the authorized documentation scope.

Infer the mode from the request; do not demand a mode selection. Ask one focused
question when a decision blocks progress. Recommend an answer when the evidence
supports one; several artistically viable choices need no artificial winner.
A sustained one-question-at-a-time interview is appropriate when the author
asks to work that way, not the default for all worldbuilding.

## Read Relevant Context

Use existing author files for lore, characters, plans, and prose evidence.
Optional folder/file tags and indexes can help; flat files and missing configuration need no setup.
Start from the named topic, discover relevant files, and read actual sources
before asserting a conflict. Indexes are maps, not substitutes for evidence.
Expand discovery when a proposed change affects other records or story events.

Treat accepted chapter and side-story prose, and draft prose, as read-only
evidence. Never rewrite, patch, or insert scene text in this workflow. A small
hypothetical scenario can illustrate a consequence in discussion; it is not
manuscript output or a canon decision.

Distinguish what the world establishes, what a group believes, what a character
reports, and what remains uncertain. Preserve `<AI>` proposals and `<hidden>`
author-only material. A future truth must not leak into earlier character or
reader knowledge. Different names for one concept can be meaningful; use
`$shared-dao` without forcing every culture to share one term.

## Develop Useful Consequences

Choose questions that bear on this story: who benefits, what everyday practice
changes, what the limits allow, or where a character's choices become difficult.
Not every idea needs an economic, legal, religious, and military analysis.
Use concrete scenarios to reveal an important ambiguity, not to force a fully
specified system. Preserve mystery when it is part of the intended experience.

When evidence conflicts, cite the passages and explain the consequence. Offer
possibilities such as narrowing the idea, keeping an in-world disagreement, or
proposing a retcon. The author decides material changes to established canon.
Generator resources under `resources/generators/` are optional prompts when
useful for exploration; their output remains provisional.

## Record Settled Decisions

`$kb-management` owns the shared promotion procedure. When documentation is in
scope and a direct author answer settles durable lore, persist it before the
next dependent question using a reviewed named edit or a previewed, recoverable
`$project-maintenance` transaction where managed mechanics apply.
Do not ask for redundant confirmation. Unless the author marks an answer
provisional or asks not to save it, record settled decisions within that scope.
A discussion-only request returns decisions without changing files.

Ask only about material ambiguity, inference, conflict, retcon, source tags,
or knowledge boundaries. Keep unresolved options in working notes when notes
are requested; do not ask permission for each open question or put speculation
in canon. Reuse the smallest appropriate author record; create a file only
when the task needs one and its destination is clear.

Use [world-file-format.md](references/world-file-format.md) as a format guide
for new world records while preserving compatible author formatting. Update
affected existing indexes with the same edit or transaction; use managed reindexing
only where applicable. No new folder or index is required for a single fact.

## Return Useful Work

Give the ideas, consequences, or decision record the author requested. Separate
evidence, proposals, decisions, and remaining uncertainty without requiring the
same labels before every question. If a settled change affects prose, name the
relevant passages for a separate revision; keep this workflow's prose read-only.

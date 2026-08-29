---
name: story-memory
description: >
  Where writing artifacts live: kb for durable knowledge, work directory for scratch. Use when deciding where to read from or write to.
---

# Writing Artifacts

- Durable project knowledge lives in canonical `kb/`. Continuity records —
  timeline, promises, questions, state snapshot, and scene records — live only
  under `kb/continuity/`; see `resources/continuity-records.md` for formats.
- Work scratch lives in canonical `work/`, scoped to the current task and
  archived on completion.
- Project-specific semantic conventions live in the body of `project.md`, but
  they do not replace or customize the schema-v1 managed roots.

## Work Layout

```text
work/plans/              # outlines and current plans
work/drafts/             # draft iterations
work/reviews/            # critique and review reports
work/brainstorm/         # brainstorm captures and synthesis
work/archive/            # completed or abandoned work artifacts
```

## Shared Workspace

The working tree is shared between the author, the orchestrators, and worker
agents. Any file may have been edited by someone else since you last saw it.

Read the current state before acting on it; a draft may have author edits
between critique rounds, a KB entry may have been updated by another agent,
an outline may have been restructured. Treat what's on disk as the authority,
not your memory of what was there.

When your edits would conflict with changes someone else made, surface the
conflict rather than silently overwriting. The author's direct edits are
always authoritative.

## Promotion

Completing or accepting a work item only makes durable facts eligible for a
promotion proposal; it never performs a KB write. Propose the knowledge rather
than raw artifacts, with exact destinations and source evidence. Brainstorm
captures and draft iterations stay in work storage.

Preserve provenance during promotion. Untagged author-stated text remains untagged.
Preserve `<AI>...</AI>` markers around AI suggestions; promotion does
not turn a suggestion into author-stated canon. Exclude `<hidden>...</hidden>`
content unless the author explicitly confirms both the fact and its destination
in durable knowledge. Even after that confirmation, preserve any knowledge
boundary the author assigns.

KB promotion requires separate author confirmation. After confirmation, perform
it as a previewed, recoverable `$project-maintenance` transaction, then apply
only that reviewed transaction. If it was mistaken, inspect history and preview
`cw undo <transaction-id>`; never reconstruct earlier bytes from memory.

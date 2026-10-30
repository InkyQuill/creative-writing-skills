---
name: story-review
description: "Review work after prose exists: editorial review, craft critique, continuity/voice review, copyediting, proofreading, and synthesis of reader-sim signal. Load when diagnosing a draft rather than rewriting it.\n"
---

# Story Review

Analytical review of existing prose. This skill is for diagnosis, not
rewriting. Keep `/reader-sim` separate when the task needs a felt first-time
reader experience rather than analytical critique.
Resolve project preferences through
`../project-bootstrap/resources/author-workflow-contract.md` before reviewing.
If the author requests in-place edits, route the agreed depth and exact file
scope to the editing workflow; this review skill still returns findings.

When the task includes dialogue, load `/creative-writing-craft` and its
`resources/dialogue-rules.md` before proceeding. Consult the persistent Character
Voice Roster, preserve each speaker's knowledge and relationship context, and
apply the rules' final dialogue review. Keep proposed roster changes separate
from established traits and respect the task's file-edit scope.

## Prepare the Review

Read the author's named files directly, including flat and untagged projects.
Use `/project-maintenance` checks and `cw context draft` or chapter context
when useful; inspect coverage and do not create a scaffold to enable them. Inspect the
draft, intent or outline, relevant style and vocab, neighboring prose, and
continuity state selected by that context plan before beginning the review.
Use `/creative-writing-craft`'s shared prose-context procedure for surface
judgment, reusing applicable context already resolved. For a short requested
review, the passage and immediate context may suffice; do not demand an outline,
full manuscript, or project checks. Never substitute English for a missing or
unsupported language.

Interpret repairable warnings internally and continue the review with the
readable evidence, naming any limitation in the report. A required target that
cannot be read safely is the only mechanical reason to stop the requested
review. The agent owns hashes, indexes, base revisions, migration mechanics,
and repair commands; never ask the author to maintain SHA values.

Include relevant saved human-praise evidence in review context, even when
Pocket Editor sidecars are gone. Preserve the valued effects in recommendations;
record conflicts with the current brief instead of treating praise as a lock.

Choose the review level before reading. Start big before small unless the
caller explicitly asks for a late-stage pass. The edit levels move from
structural to surface, and each assumes the levels above it are stable:

- **Editorial review** — holistic third-party book-editor pass. What kind of
  revision does this draft need, and in what order?
- **Developmental edit** — structure, promise, causality, pacing, character
  arc. Is the draft the right shape?
- **Line edit** — voice, rhythm, clarity, texture. Does the prose move well?
- **Copyedit** — grammar, usage, punctuation, consistency. Is it correct?
- **Proofreading** — final surface pass. What slipped through?

Each level has a dedicated resource with method and checklist:

- `resources/editorial-review.md`
- `resources/developmental-edit.md`
- `resources/line-edit.md`
- `resources/copyedit.md`
- `resources/proofreading.md`

For focused craft diagnosis (or adversarial stress-testing when requested), load:

- `resources/prose-critique.md` — methodology and focus-area routing.
- `resources/prose-critique/` — deep resources per focus area (structure,
  character, voice, prose, continuity).

When review incorporates reader-sim data:

- `resources/reader-sim-signal.md` — how to interpret and synthesize
  reader-sim output alongside analytical critique.

## Acceptance Boundary

A review returns findings; it does not itself accept or alter prose. For
requested revision, route the authorized scope to the editing workflow.
`/kb-management` owns the shared promotion procedure for facts established by
accepted prose, including source/status boundaries and separate durable updates.
Do not treat review approval, model agreement, or a successful checker as author
acceptance or proof of literary quality.

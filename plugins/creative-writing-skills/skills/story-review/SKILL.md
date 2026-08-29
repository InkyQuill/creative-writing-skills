---
name: story-review
description: >
  Review work after prose exists: editorial review, craft critique, continuity/voice review, copyediting, proofreading, and synthesis of reader-sim signal. Load when diagnosing a draft rather than rewriting it.
---

# Story Review

Analytical review of existing prose. This skill is for diagnosis, not
rewriting. Keep `$reader-sim` separate when the task needs a felt first-time
reader experience rather than analytical critique.

## Prepare the Review

Use `$project-maintenance` before reading: run the checks relevant to the
requested review and prepare focused context with `cw context draft` for an
active draft (or the matching chapter context for accepted prose). Inspect the
draft, intent or outline, relevant style and vocab, neighboring prose, and
continuity state selected by that context plan before beginning the review.
For every prose or surface judgment, resolve the same base,
manuscript-language, prose-profile, and applicable project style/sample stack
defined by `$creative-writing-craft`. Never substitute English when the
language is missing or unsupported.

Interpret repairable warnings internally and continue the review with the
readable evidence, naming any limitation in the report. A required target that
cannot be read safely is the only mechanical reason to stop the requested
review. The agent owns hashes, indexes, base revisions, migration mechanics,
and repair commands; never ask the author to maintain SHA values.

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

For adversarial craft critique (as opposed to editorial review), load:

- `resources/prose-critique.md` — methodology and focus-area routing.
- `resources/prose-critique/` — deep resources per focus area (structure,
  character, voice, prose, continuity).

When review incorporates reader-sim data:

- `resources/reader-sim-signal.md` — how to interpret and synthesize
  reader-sim output alongside analytical critique.

## Acceptance Boundary

A review may recommend draft acceptance, but it never applies acceptance
without author confirmation and a reviewed `$project-maintenance` preview.
The acceptance transaction does not update the KB or knowledge base. After
acceptance, `$kb-management` re-reads the prose and synchronizes directly and
unambiguously established facts through a separate previewed, recoverable
transaction without re-approval. Separate transaction does not mean separate
confirmation. Ask only about ambiguity, inference, conflict, retcon, uncertain
source tags, or uncertain character and reader knowledge boundaries.

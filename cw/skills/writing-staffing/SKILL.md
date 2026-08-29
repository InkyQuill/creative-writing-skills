---
name: writing-staffing
description: "Internal capability-based dispatch reference for composing writing teams. Use when explicitly staffing a workflow to choose skills, context, and parallel lanes without relying on named agents or a specific runtime.\n"
---

# Writing Staffing

When delegation is available, the muse assigns bounded work by capability,
names the relevant skills and resources, and provides the files each lane
needs. When delegation is unavailable, the muse loads the same skills and
performs the lane directly. Keep the author-facing thread coherent in either
case.

## Model Selection

Use the default model unless the work needs a different capability. Prefer
strong creative judgment for generation and high-stakes critique, structured
reasoning for outlining and cross-document synthesis, and fast economical
execution for mechanical gathering whose misses will be caught in synthesis.

**Fan-out** means giving the same question and files to different model
families for independent judgment. Reserve it for high-stakes calls where
model diversity can reveal different blind spots. **Parallel lanes** use
different prompts or focus areas; use each lane's default model unless it
needs a capability it lacks.

## Dispatch Reference

### Prose drafting

Load `/creative-writing-modes` and `/creative-writing-craft`. Add
`/character-sim` for voice fidelity and `/shared-dao` for project vocabulary.

Name the production mode from `/creative-writing-modes` →
`resources/prose-modes.md` (fresh draft, revision, bridge, alternate take,
line polish). Point to `/creative-writing-craft` →
the resolved `resources/prose/` stack or `resources/scene-construction.md` when relevant.
Provide style files, character state, and continuity anchors.

One writer per scene — voice consistency degrades when multiple writers
handle adjacent content.

### Focused critique

Load `/story-review`. Add `/creative-writing-craft` for prose or voice focus
and `/shared-dao` for vocabulary checks.

Assign one focus area: structure, character, voice, prose, or continuity.
Provide style files for voice critique.

Run different focus areas as parallel lanes. Scale to stakes:
1–2 for low-stakes, 3 for standard chapters, 4–5 for pivotal scenes with
duplicated coverage on the critical dimension.

For a pivotal scene or disputed judgment, fan out the same critical dimension
across two meaningfully different reasoning approaches, then synthesize the
disagreement.

### Holistic editing

Load `/story-review` and name the edit level (editorial review, developmental,
line edit, copyedit, proofreading). Point to `/story-review` →
`resources/editorial-review.md` for holistic pass, or the specific
edit-level resource.

Use when the draft needs a priority order across concerns. For depth on
one dimension, use a focused critique lane.

### Cross-project continuity

Provide the draft plus canon files, timeline, character state, and vocab. This
lane reads broadly across the project, so reserve it for deep validation; use
a focused critique lane for routine continuity checks.

### Brainstorming

Load `/story-planning`. Add `/character-sim` for character arcs and
`/creative-research` for real-world grounding.

Run parallel lanes on different *angles*, not the same angle. Three perspectives
beats five instances of one.

### Outlining

Load `/story-planning` after direction is chosen. Brainstorm first; the outline
then feeds the prose-drafting pass.

### Style analysis

Load `/creative-writing-craft`, provide sample chapters or existing style
files, and use `resources/style-analysis.md`.

### Reader simulation

Load `/reader-sim`. Add `/character-sim` when the reader persona is a specific
character type.

Specify the reader persona and knowledge boundary: what has this reader already
read? Provide the draft.

Run after the write/critique loop converges, before presenting to the
author. A scene can be technically clean and leave a reader cold.

### Character simulation

Load `/character-sim`, provide character state and voice/style files, and
specify the scenario or relationship to explore. Use one parallel lane per
character or perspective for independent exploration; use one shared
simulation when testing their interaction.

### Research

Load `/creative-research`. Provide the specific question, story context, and
what the story currently assumes so contradictions can be flagged.

### Story memory

After the triggering event settles — a chapter is finalized, a brainstorm
concludes, or the author makes a decision — have the muse apply `/story-memory`
directly for fact extraction, fiction-specific categories, and artifact layout.

## Effort Scaling

Scale critic coverage to stakes. Knowledge maintenance waits until direction
or chapters settle. Reader-sim runs after the write/critique loop converges.

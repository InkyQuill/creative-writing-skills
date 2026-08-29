---
name: targeted-editing
description: "Discipline for editing existing prose in place. Use before any revision, bridge, insertion, reorder, or cut: locate the exact target on the outline and timeline, choose the smallest effective change level, and check ripple effects on story flow before touching text.\n"
---

# Targeted Editing

Every edit lands somewhere in the story. Before changing existing prose,
establish what is being edited, where it sits, and what the change touches.
Then edit at the level the problem actually lives at, and verify the joins
afterward.

Use `/project-maintenance` for mechanical checks, exact edit operations,
preview/apply, and transaction recovery. Interpret repairable warnings
internally and continue the literary edit when its required text is readable.
A required target that cannot be read safely is the only mechanical reason to
stop. The agent owns hashes, indexes, base revisions, migration mechanics, and
repair commands; never ask the author to maintain SHA values.

## Locate Before Editing

- Name the target precisely: which chapter, which scene, which beat or
  passage. "Tighten the middle" is not a target; "Chapter 4: Scene where the
  rivals negotiate in the warehouse, middle beats" is.
- Find the target's position in the outline and on the story timeline: where
  it falls in main-storyline order, and which character sub-timelines pass
  through it.
- Read the current text from disk immediately before editing — the working
  tree is shared and may have changed. Then read what the edit joins to: the
  scene before, the scene after, and any earlier passage the target sets up
  or pays off.

## Choose the Change Level

Pick the smallest level that achieves the intent, and escalate deliberately:

- **Line or phrase** — voice, rhythm, clarity. Structure and causality stay
  put.
- **Beat** — add, reorder, or cut a beat inside the existing scene.
- **Scene** — rework the scene's conflict, turn, entry point, or exit.
- **New scene or bridge** — the change needs room no existing scene gives.
- **Structure** — reorder scenes, move a reveal, or cut a thread.

A pacing problem is rarely fixed at line level; a clarity problem is rarely
fixed with a new scene. When critique or direction implies a bigger level
than requested, name the mismatch and let the author or orchestrator confirm
before restructuring.

When adding a scene or beat, place it explicitly: after which existing scene,
before which, and where its events fall on the timeline relative to
neighboring events, durations, and anything happening in parallel.

## Check Ripple Effects Before Writing

Trace what the edit touches:

- **Flow** — does the passage still join its neighbors? Causality entering
  and leaving, emotional register entering and leaving.
- **Setup and payoff** — does anything downstream depend on a line, beat, or
  fact this edit changes or removes?
- **Timeline** — does the edit shift event order, duration, or simultaneity?
  Check the main storyline and every character sub-timeline that intersects
  the passage. Watch time-of-day and season language, and whether travel
  time between locations still works.
- **Character state** — who knows what at this story time? Does the edit
  change knowledge, location, injury, or relationship state that later scenes
  rely on? Check for abilities the character has not yet demonstrated at this
  point in the story.
- **Canon and vocab** — does the edit contradict established canon or settled
  terminology? Flag the contradiction; the author decides canon.

## Form an Exact Operation Plan

Choose the literary scope first: target and change level, intended reader
effect, and ripple boundaries. Only then translate the approved change into an
exact-anchor operation or a batch of exact operations. Read current bytes just
before planning. Each repeated match needs an explicit expected-count assertion;
never let a common phrase silently select the first occurrence.

Preview the exact operation or complete batch before apply. Inspect every
changed passage and precondition, then use `--apply` only while the preview
still represents the requested edit. If an applied edit was a mistake, inspect
history, preview `cw undo <transaction-id>`, and apply that inverse transaction
instead of hand-restoring remembered text.

## Edit, Then Verify

Make the edit, then re-read the edited passage together with the scene before
and after. Confirm the joins hold, and follow each ripple flagged above to
where it lands. Identify the corresponding continuity-record changes
(`/story-memory` continuity records): scene record when POV, location, cast,
or state changed; timeline rows when events, order, or duration moved; promise
and question statuses when the edit plants, pays off, raises, or answers
anything; the state snapshot when knowledge, location, injuries, or
relationships moved. After the edited prose is accepted, re-read it and apply
record changes it directly and unambiguously establishes through a separate
previewed, recoverable transaction without asking for re-approval. Then run the
deterministic checker and report its findings rather than silently repairing
them. Keep ambiguity, inference or implication, canon conflict, retcon, uncertain
source tag, and uncertain character or reader knowledge boundary as a proposal;
ask only when different answers would materially change canon or knowledge.

Report the placement decision — what level, where, why — along with any
ripple that could not be fully verified and any contradiction found. Keep only
unresolved or inferred `/story-memory` updates provisional; accepted prose is
evidence for facts it establishes explicitly.

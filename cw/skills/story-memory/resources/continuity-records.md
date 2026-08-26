---
name: story-memory
description: >
  Machine-checkable continuity records: timeline, promises, questions, state snapshot, and scene records. Use when creating or updating these artifacts and when running the deterministic continuity check.
---

# Continuity Records

Free-form kb pages carry judgment; these five record types carry facts a
script can check. They record what established prose and author-confirmed
decisions made true — never speculation. Anything unresolved stays in the
issue log or brainstorm notes instead.

## Where They Live

Follow the project layout: under `plot/` in Layout A projects and `kb/` in
Layout B projects. Record the exact paths in the project instructions. The
checker discovers the records by name, so keep the file names below. If both
roots contain continuity records, stop and resolve the selected root in the
project instructions; the checker treats the layout as ambiguous rather than
silently choosing one.

## Timeline

`timeline.md` — the master chronology. One row per event, one line per row.

```markdown
# Timeline

## Backstory

| When | Event | Threads | Anchor | Evidence |
|---|---|---|---|---|
| ~12 years ago | Ember Rite: Sera's magic manifests | sera-arc | ember-rite | `sera.md` |

## Story

| When | Event | Threads | Anchor | Chapter |
|---|---|---|---|---|
| Day 3, morning | The crew crosses the strait | main | strait-crossing | Chapter 7: Scene where the crew crosses the strait |
| Day 3, morning | Kell signals the harbor | kell-thread | strait-crossing | Chapter 7: Scene where Kell signals the harbor |
```

Rules: backstory events cite project documents; story events cite chapters.
Events that happen at the same time share one anchor and are noted explicitly.
`Threads` names the main storyline or the character/subplot sub-timeline the
event belongs to. Character sub-timelines live in the character's entry as a
section with the same columns; every row that coincides with a master event
carries that event's anchor.

## Promises

`promises.md` — what the prose promised the reader, tracked to payoff.

```markdown
# Promises

| Promise | Status | Planted | Payoff | POV knows | Evidence |
|---|---|---|---|---|---|
| The mentor's sealed letter gets opened | planted | Chapter 3: Scene where the mentor seals the letter | — | reader only | Chapter 3: Scene where the mentor seals the letter |
| The harbor signal is answered | paid-off | Chapter 5: Scene where Kell sends the signal | Chapter 9: Scene where the answer arrives | Kell | Chapter 9: Scene where the answer arrives |
```

Status is `planned`, `planted`, `paid-off`, or `dropped`. `planned` means the
author intends the promise but prose has not planted it yet. A dropped promise
stays in the table with a one-line reason appended to its evidence — dropped
is a decision, not a deletion. Once prose exists, use the full `Chapter N:
Scene where X discovers Y` citation in `Planted` and `Payoff`, never bare
`Ch N` shorthand.

## Questions

`questions.md` — story-logic questions the reader is owed an answer to.

```markdown
# Questions

| Question | Status | Introduced | Answered | Evidence |
|---|---|---|---|---|
| Who paid the smugglers? | open | Chapter 4: Scene where the payment surfaces | — | Chapter 4: Scene where the payment surfaces |
```

Status is `open`, `answered`, `partially-answered`, or `dropped`. Questions are
distinct from promises: a promise is a payoff the reader anticipates; a
question is an inconsistency or mystery the story raised. Once prose exists,
use the full chapter-scene citation in `Introduced` and `Answered`.

## State Snapshot

`state.md` — the mutable present at the writing front. Rewritten as the story
advances; the other records in the selected continuity root keep durable
chronology and lifecycle history, while this file keeps only current state.

```markdown
# State at the Writing Front

current-chapter: 9
story-status: draft

## Characters

| Character | Location | Status | Injuries | Relationships |
|---|---|---|---|---|
| Sera | harbor | alive | healing ribs | trusts Kell again |
| Mentor | capital | deceased (Ch 6) | — | — |

## Knowledge

| Character | Fact | Learned in |
|---|---|---|
| Kell | the signal was a trap | Ch 8 |

## Objects

| Object | Holder | Location | Status | Since |
|---|---|---|---|---|
| Sealed letter | Sera | satchel | unopened | Ch 3 |

## Open Threads

- The harbor blockade is unresolved.
```

## Scene Records

`scenes/` — one file per chapter, `ch-07.md`, with a row per scene. Scene
records make continuity queryable without rereading prose.

```markdown
# Chapter 7 Scenes

| Scene | POV | Location | Present | Mentions | Anchor | State changes |
|---|---|---|---|---|---|---|
| 1 | Sera | strait | Sera, Kell | mentor | strait-crossing | Kell learns the crossing route |
| 2 | Kell | harbor | Kell | Sera | strait-crossing | signal sent |
```

`Present` lists characters on stage; `Mentions` lists characters who appear
only in flashback, memory, recording, or reference — a deceased character may
appear in `Mentions` after their death, never in `Present`.

## Updating the Records

Records update when decisions settle, not during exploration: after the author
accepts prose, confirms a decision, or an edit lands. Fact extraction writes
scene records and timeline rows from the accepted chapter, moves promises and
questions to their new statuses, and refreshes `state.md` to the new writing
front. An edit that changes events, knowledge, or deaths ripples into the same
records before the pass reports done. When a record and the prose disagree,
the record is flagged to the author — the author decides canon; agents never
quietly re-time, re-cast, or resolve.

## Deterministic Check First

Run the checker before judging continuity by reading. Set the working directory
to the installed `story-memory` skill directory, then pass the story project
root as the argument:

```bash
STORY_PROJECT_ROOT="$(cd "<project-root>" && pwd -P)"
cd "<story-memory-skill-directory>"
python3 resources/continuity_check.py "$STORY_PROJECT_ROOT"
```

It reports ordering violations (payoff before plant, answer before question,
appearance after death), lifecycle mismatches, stale state, anchor conflicts,
and Chekhov gaps — promises planted three or more chapters back with no
payoff. Once any continuity record exists, the full five-record set is
required; a missing file or `scenes/` directory is an error. The checker also
compares anchored timeline tables embedded in character and subplot entries
with the master timeline. Exit is nonzero when it finds errors. Treat its
output as the fixed floor: resolve or flag every finding, then apply reader
judgment for what a script cannot see. Deterministic findings are reported,
not auto-repaired; record updates that change canon wait for the author.

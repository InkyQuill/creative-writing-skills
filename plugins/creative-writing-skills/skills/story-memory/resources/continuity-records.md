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

The canonical continuity root is `kb/continuity/`:

- `kb/continuity/timeline.md`
- `kb/continuity/promises.md`
- `kb/continuity/questions.md`
- `kb/continuity/state.md`
- `kb/continuity/scenes/`

These paths are consumed by `cw check continuity`. Use `$project-maintenance`
for the check and migration mechanics. Direct author edits are valid input:
re-read current bytes, tolerate author formatting and prose changes that still
meet the record contract, and report semantic conflicts without overwriting
them. Repairable warnings do not block the continuity reading; only a required
target that cannot be read safely stops that part of the audit.

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
advances; the other records in the canonical continuity root keep durable
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

Acceptance does not itself write continuity records. After acceptance, fact
extraction re-reads the prose and synchronizes scene records, timeline rows,
promise and question status changes, and `state.md` facts that the text directly
and unambiguously establishes. Use `$project-maintenance` to preview and apply
that separate recoverable transaction without asking for reconfirmation.

Keep ambiguity, inference or implication, canon conflict, retcon, uncertain
source tag, and uncertain character or reader knowledge boundary as a proposal.
Ask only when different answers would materially change canon or knowledge
boundaries. If an applied update was mistaken, preview
`cw undo <transaction-id>`. When a record and prose disagree, flag it to the
author — the author decides canon; agents never quietly re-time, re-cast,
resolve, or write around the conflict.

## Deterministic Check First

Run `cw check continuity` through `$project-maintenance` before judging
continuity by reading. It reports ordering violations (payoff before plant, answer before question,
appearance after death), lifecycle mismatches, stale state, anchor conflicts,
and Chekhov gaps — promises planted three or more chapters back with no
payoff. Once any continuity record exists, the full five-record set is
required; a missing file or `scenes/` directory is an error. The checker also
compares anchored timeline tables embedded in character and subplot entries
with the master timeline. Exit is nonzero when it finds errors. Treat its
output as the fixed floor: resolve or flag every finding, then apply reader
judgment for what a script cannot see. Deterministic findings are reported,
not auto-repaired; record updates that change canon wait for the author.

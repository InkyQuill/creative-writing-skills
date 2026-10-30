---
name: story-memory
description: >
  Context scoping for writing handoffs. Use when deciding what story context to pass, whether to materialize decisions before handoff, and how much is enough.
---

# Story Context

Use the author's actual paths. Folder names below are optional legacy examples;
flat and mixed layouts are valid. Tags aid routing but do not establish canon.
Use named outputs and safe edits without requiring a scaffold or CLI lifecycle.

Every handoff starts with a context decision. Get it wrong and a drafting pass invents facts that contradict established canon, a critique misses a continuity issue because it never saw the relevant chapter, or a brainstorming lane explores territory the author already rejected.

This skill teaches the judgment: what story context to pass, when to materialize decisions before handoff, and how much is enough.

## Choose the Right Mechanism

Three options, each for a different situation:

**Attach files**: when context already exists as files — chapters, outlines,
wiki pages, style files, character state. Default choice because files are
stable, inspectable, and survive compaction. Scope tightly: pass the files
that matter, not everything.

**Pass conversation history**: when the agent needs decisions, reasoning, or
brainstorm context that hasn't been written down yet. History captures
the *why* behind choices: why the author picked this angle, what they rejected.

**Materialize first**: when context is too important to be ephemeral. If
critical story decisions only live in conversation, write them to the kb or
work directory *before* handoff. If a worker could accidentally contradict
this context, materialize it. If it's supplementary background, conversation
history is fine.

## What Each Agent Needs

### Writers

Provide the requested passage or brief, relevant current character state, and
only the continuity or vocabulary evidence the work touches. No outline or file
target is required for an inline task. For revision, include immediate joins;
expand to chronology and downstream dependencies only when those can change.

Use the shared prose-context procedure in `/creative-writing-craft`: manuscript
language, prose profile, applicable voice guidance and samples from actual
paths (`kb/styles/` and `kb/samples/` are optional examples), and a language
adapter when the profile provides one. Pass resolved resources instead of
requiring another discovery pass. Optional evidence may be absent.

### Critics

Critics need the draft plus enough context to judge it against:

- **The draft being reviewed**: always as attached files
- **The scene brief or outline**: so the critic can check whether the draft achieved what it was supposed to
- **Resolved prose stack**: the exact manuscript-language and prose-profile
  resources plus only the `kb/styles/` and `kb/samples/` evidence applicable to
  the review's narrator, character, scene, and language scope
- **Prior chapters for continuity**: so continuity critics can cross-reference facts
- **Author intent**: via conversation history if the orchestrator discussed direction with the author, or via materialized decision notes
- **Known issues**: tracked issues if the critic should watch for specific recurring problems
- **Vocab**: relevant `vocab.md` files when consistency of naming, aliases, deprecated terms, or invented language matters

### Brainstormers

Brainstormers need constraints, not answers:

- **The question being explored**: scoped tightly in the prompt
- **Established context that constrains the answer**: character profiles, timeline, prior decisions that limit the design space
- **What's been rejected**: so they don't re-propose dead ends
- **Existing vocabulary**: enough vocab context to avoid minting new names for concepts the project has already named

Don't pass too much: brainstormers that receive the full project history tend to produce conservative ideas that fit neatly into existing patterns instead of exploring fresh territory.

### Knowledge Maintenance

- **Fact extraction**: the chapter(s) to extract from as attached files, plus existing canon files, timeline entries, and vocab files for deduplication, plus the continuity records being updated
- **Continuity-checker**: the draft plus canon, timeline, character state, and vocab files for any domains the draft touches, plus the continuity records when they exist — the deterministic checker runs first, reader judgment covers what it cannot see
- **KB restructuring**: the full kb directory structure — needs to see everything to rebuild connections
- **Session mining**: conversation history from the session to mine, plus kb paths for where to write findings

## Cross-Phase Context

Carry forward what a previous phase learned. The writer benefits from seeing
what the prior draft pass discovered when revising. The critic benefits from
seeing prior critique rounds.

Combine mechanisms when phases produce artifacts: conversation history for
reasoning context, attached files for the artifacts the prior phase created.

## Voice and Knowledge Scope

`/creative-writing-craft` owns prose-context selection; reuse the applicable
resolved resources. Preserve source tags and author-only, character, and reader
knowledge boundaries. Filter reader-simulation inputs before dispatch: text,
reading history, and persona only for the initial pass, without desired outcomes,
prior diagnoses, or secrets to ignore. Do not claim blindness if already exposed.

For story-state handoffs, distinguish facts, reported claims, beliefs, and
inferences. A character's confident assertion does not establish world truth.
No role should receive a future revelation as knowledge it has at an earlier time.

## Vocab Handoffs

Treat vocabulary as operational story context. If a writer, critic, or
brainstormer could choose the wrong name for a concept, pass the relevant
`vocab.md` file or materialize the decision before delegating. This matters most
for magic systems, factions, recurring in-world phrases, titles, relationship
labels, and terms the author corrected during conversation.

When a session settles terminology, record it before handoff: canonical name,
meaning, aliases still in circulation, and boundaries that prevent likely
confusion.

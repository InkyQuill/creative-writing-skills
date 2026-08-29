---
name: story-memory
description: >
  Context scoping for writing handoffs. Use when deciding what story context to pass, whether to materialize decisions before handoff, and how much is enough.
---

# Story Context

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

Writers need enough to stay in voice and on-canon, not everything ever written. The essential context:

- **Scene brief or outline**: what happens in this scene, the beats to hit
- **Resolved prose stack**: universal base, exact manuscript language,
  prose-profile base and matching language adapter when the profile provides
  one, then only applicable
  `kb/styles/` guidance and supporting `kb/samples/` evidence. Name why every
  narrower narrator, POV, character, or scene style applies.
- **Continuity anchors**: the immediately preceding chapter or scene (for flow), plus any chapters that establish facts this scene references. Two to four files, not the entire manuscript. For revisions and insertions, also the scene's timeline position — where its events fall relative to neighboring events and which character sub-timelines intersect — so the edit lands without breaking order, duration, or simultaneity.
- **Character state**: character files for characters who appear in the scene, especially if their emotional state or knowledge has changed recently
- **Vocab**: relevant `vocab.md` files when the scene uses invented terms, magic/faction names, titles, relationship labels, or genre terms with project-specific meanings

Tell the writer where to find more if it needs to explore, for example: "the full arc outline is in the work directory; focus on the Route 1 section." Avoid attaching everything preemptively.

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

Select style and sample evidence by manuscript language, prose profile, and
declared applicability. Project-wide guidance comes before narrower narrator,
POV, character, or scene guidance; the current brief is last. Pass only
relevant evidence, and state why a narrow style applies. Never merge
cross-language samples into a single baseline. Preserve source tags and
author-only, character, and reader knowledge boundaries when quoting evidence.
Missing optional evidence leaves the resolved defaults in force and does not
itself require a question.

## Vocab Handoffs

Treat vocabulary as operational story context. If a writer, critic, or
brainstormer could choose the wrong name for a concept, pass the relevant
`vocab.md` file or materialize the decision before delegating. This matters most
for magic systems, factions, recurring in-world phrases, titles, relationship
labels, and terms the author corrected during conversation.

When a session settles terminology, record it before handoff: canonical name,
meaning, aliases still in circulation, and boundaries that prevent likely
confusion.

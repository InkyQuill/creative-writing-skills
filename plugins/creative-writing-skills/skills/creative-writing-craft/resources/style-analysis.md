---
name: creative-writing-craft
description: >
  How to analyze prose and produce style reference files. Use when creating, updating, or evaluating the style files that capture a project's voice patterns.
---

# Style Analysis

How to analyze prose evidence within one language and prose-profile scope and
produce style references that drafting and critique passes can use. Examples
are evidence for principles, not a mechanical imitation corpus.

## Style Has Dimensions

Style varies independently along multiple axes: some bound to a character,
some to a scene type, some to both, some that cross everything. The first job
is identifying what dimensions exist in *this* project, not arriving with a
predetermined taxonomy.

Look at the text: what varies independently? If a character's narration voice
changes by scene type, that's two dimensions interacting. If action pacing
stays consistent regardless of narrator, that's scene-bound. The text tells
you where the boundaries are.

## File Splitting

Style files are the unit of context selection: an orchestrator passes
individual files to writers via `-f`. Every file boundary is a context
decision: would an agent ever need this chunk without that chunk?

Split where a caller would plausibly want one part without the other. A
character with distinct dialogue and narration modes might need separate files.
A character with a simple, consistent voice needs one. A scene type that works
the same regardless of POV is its own file.

Keep schema-v1 paths flat. Evidence lives at
`kb/samples/<descriptive-name>.md`; durable derived guidance lives at
`kb/styles/<descriptive-name>.md`. Do not nest language, profile, character, or
scene directories beneath those roots. Encode applicability in each file.

## Evidence Sample Template

An approved sample states:

- **Language/tag**: the manuscript language represented;
- **Scope/applicability**: project, narrator, character dialogue, scene type,
  or another precise scope;
- **Evidence role**: `authoritative`, `aspirational`, or `negative`;
- **Source/citation and source-tag boundary**: exact chapter pointer, excerpt
  origin, and whether text is author-stated, `<AI>`, or `<hidden>`;
- **Evidence**: the selected excerpt or exact chapter citation;
- **Why it matters**: what tendency or boundary the sample demonstrates.

Do not promote an attractive excerpt merely because it resembles the desired
voice. Its role and source boundary must be known.

## Style Reference Template

A derived style reference states:

- **Language and prose-profile applicability**;
- **Scope**: project, narrator, POV, character dialogue, scene type, or a
  documented intersection;
- **Evidence links**: approved sample paths and accepted chapter citations;
- **Status of guidance**: observed versus author-specified, with inference
  labeled;
- **Actionable tendencies**: diction, syntax, rhythm, distance, imagery,
  dialogue, and other dimensions the evidence actually supports;
- **Allowed variation** and **anti-patterns**.

Derive each principle from cited evidence and explain the reader or voice
effect. Sparse evidence leaves the selected language/profile defaults in force;
it does not justify filling gaps or repeatedly questioning the author.

## What to Analyze

Dimensions worth investigating: the text determines which matter:

- **Sentence patterns**: length distribution, rhythm, how it shifts with
  emotional intensity. Fragment usage, compound tendencies.
- **Interiority**: depth of internal monologue. Direct thought, indirect
  thought, stream of consciousness: when each activates.
- **Vocabulary and register**: recurring word choices, domain language,
  register shifts.
- **Dialogue patterns**: how characters sound distinct. Tag frequency, action
  beats, subtext delivery.
- **Humor mechanics**: techniques, timing, what's played for laughs vs what's
  sacred.
- **Emotional approach**: physical manifestation vs named emotions, how much
  space emotional moments get.
- **Sensory detail**: privileged senses, how density shifts by scene type.
- **Pacing and paragraph rhythm**: how paragraph length and whitespace shift
  between scene types.

## File Structure

Each style file teaches a voice through principles, not catalogs:

- **Principle**: the core insight in a few sentences. What's the pattern? Why
  does it work?
- **Representative examples**: one or two with chapter citations showing the
  principle in action.
- **Chapter pointers**: where to see more of the pattern in context.

A writer who internalizes the principle produces natural variation. A writer
following an exhaustive checklist produces something mechanical.

Each file should be self-describing: a caller reading it should understand
what it covers and when to load it.

## Patterns vs Problems

Intentional patterns go in style files: the voice a writer should reproduce.
Unconscious tics and inconsistencies go in the issues directory: problems for
the critic to watch for and the author to address in revision.

The test: would the author want a writer agent to reproduce this? If "for a
moment" appears 29 times across 17 chapters, that's a tic. If an emotional
technique works in chapters 2 and 15 but is absent from chapter 11, that's an
inconsistency to log as an issue.

Analyze one declared language/profile scope at a time. Never merge
cross-language samples into one baseline: a repeated surface pattern can have a
different function or grammatical status in another language.

The style-creator writes only a proposal as a direct file under
`work/reviews/`. Muse or the orchestrator promotes approved sample and style
artifacts into the flat KB paths through a previewed, recoverable transaction.
An explicit author choice or directly settled answer needs no redundant second
confirmation; ambiguity, conflicting evidence, source-boundary uncertainty,
and material inference remain provisional until resolved.

## Quality Tests

1. **Voice test**: could a writer, reading only this file and a scene brief,
   produce prose the author recognizes as their voice?
2. **Brevity test**: could a writer internalize this file in one read? If
   they need to keep it open as reference while drafting, it's over-prescribed.

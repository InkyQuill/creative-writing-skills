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

Style files are units of context selection: pass only the relevant references
or excerpts to a writing pass. Every file boundary is a context
decision: would an agent ever need this chunk without that chunk?

Split where a caller would plausibly want one part without the other. A
character with distinct dialogue and narration modes might need separate files.
A character with a simple, consistent voice needs one. A scene type that works
the same regardless of POV is its own file.

Use the author's actual sample and style locations, flat or nested.
`kb/samples/<descriptive-name>.md` and `kb/styles/<descriptive-name>.md` are
optional legacy examples, not required homes. Encode applicability in each
record and avoid duplicating existing voice guidance.

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

Separate an observed tendency, an author-desired practice, and a supported
problem. Compare passages with similar speakers, narrative distance, purpose,
and pressure. A raw count does not establish a tic; absence of a technique
from another chapter does not establish inconsistency.

Describe the effect before prescribing a rule. Repetition may create a motif;
a voice may change under stress. Label a defect only when evidence shows an
unwanted effect in context. Do not turn an isolated choice into a standing rule.
The current brief and new prose can establish intentional experimentation;
prior approved samples are helpful, not a prerequisite for a new voice.

Analyze one language/profile scope at a time; do not merge cross-language
surface tendencies into one baseline. Produce the requested reference in chat
or at the assigned output path. The style-creator writes only a proposal;
`/kb-management` owns promotion of approved sample/style guidance and its
shared evidence/status rules. Do not invent a reviews folder or flatten the
author's existing structure.

## Quality Tests

1. **Voice test**: could a writer, reading only this file and a scene brief,
   produce prose the author recognizes as their voice?
2. **Brevity test**: could a writer internalize this file in one read? If
   they need to keep it open as reference while drafting, it's over-prescribed.

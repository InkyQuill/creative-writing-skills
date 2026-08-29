---
name: writing-principles
description: >
  What fiction readers want (reader reward channels) and the specific ways LLM training damages them. Load when drafting prose, critiquing, or diagnosing why a passage feels flat.
---

# Writing Principles

Load `$llm-writing` if it isn't already loaded. This skill adds the
fiction-specific layer.

## Trust the Reader

The reader is an active collaborator. They reconstruct emotions from behavior,
infer motives from action, hold tension across scenes, fill gaps the text
leaves open, and make assumptions about what's coming next. That work is where
the reward lives: reconstruction, inference, anticipation.

Your training pulls in the opposite direction. The helpfulness instinct wants
to explain, resolve, clarify, and complete. In fiction, every one of those
impulses can damage the reading experience by doing work the reader wanted to
do themselves. The specific failure modes below are all forms of this: not
trusting the reader to interpret an emotion, hold an ambiguity, follow
subtext, or tolerate unresolved tension.

Trust doesn't mean obscurity. Readers also need coherent narrative, stable
geography, and enough access to model characters. The discipline is knowing
when to leave space and when to orient.

## Economy

Every element does more than one thing. A line of dialogue advances plot
AND reveals character. A sensory detail grounds the scene AND shows who the
POV character is. A transition compresses time AND carries an emotional
beat. Single-purpose prose makes fiction go flat: description that only
describes, dialogue that only informs, interiority that only labels.

Economy isn't minimalism. Dense, lyrical prose can be economical when every
phrase carries weight. Sparse prose can be wasteful when it takes ten short
sentences to do what one image could do. The measure is whether removing
the element would cost the reader something.

The LLM pull is toward completeness: covering every beat, naming every
emotion, resolving every ambiguity. Economy is the counter-discipline:
what can you leave out and still have the scene work? What's the reader
already doing for you?

## Reader Reward Channels

Readers enjoy fiction through overlapping reward channels. Good prose protects
the relevant channels at once; damaging one damages the reading experience.

- **Transportation**: entering the story world. Protected by coherent
  narrative progression, consistent POV, concrete sensory grounding. Consistent
  POV means writing from inside the character's knowledge state: what have
  they experienced, what do they actually know right now, what would they
  notice and miss? The full story is in your context window; the character
  only has what they've lived through. Separate those.
- **Aesthetic**: sentence-level pleasure. Protected by variety in rhythm,
  word choice, sentence shape, and punctuation. Style is a reward channel, not decoration.
- **Social simulation**: modeling characters as minds. Protected by access
  through behavior and interiority, distinct voices, emotion the reader
  interprets rather than being told.
- **Flow**: challenge-skill fit and smooth processing. Protected by pacing that
  matches the scene's work and sentences that support comprehension without
  making the reading trivial.
- **Curiosity / prediction reward**: wanting to know what happens, what a clue
  means, what a character will choose, or whether an expectation will be
  confirmed. Protected by information gaps, uncertainty, setup/payoff, suspense,
  and withheld implications that the reader can actively model.

The channels compose: optimizing one at the expense of others fails.
Over-explaining breaks social simulation. Under-explaining breaks
transportation. Generic style breaks aesthetic pleasure. Impenetrable style
breaks flow.

## Punctuation Fit

Choose punctuation from the meaning and relationship of the clauses, the
line's readability and rhythm, and the manuscript's documented voice. Use a
sentence break for separation, a comma for continuity, a colon for
development, a semicolon for balanced independence, parentheses for an aside,
and a dash when interruption or suspension is the intended effect. Rewrite a
sentence when its clause structure is unclear instead of mechanically swapping
one mark for another.

The author's documented punctuation habits and the language's grammar outrank
generic defaults. Do not normalize punctuation from frequency alone. When a
line needs interruption, use the project's established interruption pattern
and keep it consistent.

## Language Register

Apply every surface judgment through the resolved prose stack from
`$creative-writing-craft`: manuscript-language grammar and orthography first,
then prose profile, then evidenced project and narrow voice. Punctuation,
sentence movement, dialogue formatting, lexical variation, and mechanical
metrics do not have language-neutral defaults.

When generic advice and the selected language resource disagree, the language
resource wins. When the resource does not support a language, never substitute
another language's habits. Use accepted same-language project evidence when it
settles the choice; ask only when a missing norm would materially change the
work.

## Applying the Principles

This skill is the diagnostic layer: it names what readers want and how
training damages it. When a passage feels off and you can't name why, check
the reward channels — which one broke? — then see `resources/failure-modes.md`
for common patterns and fix heuristics.

The craft skills carry the execution. `$creative-writing-craft` resolves the
universal, language, profile, and author-voice prose stack, then routes scene
mechanics and style analysis. `$creative-writing-modes` has the production
modes for putting prose on the page.

## Resources

- [`resources/failure-modes.md`](resources/failure-modes.md): per-pattern
  deep dives with examples and fix heuristics.
- [`resources/citations.md`](resources/citations.md): research backing for
  the reader-reward model and documented failure modes.

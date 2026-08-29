---
name: story-planning
description: >
  Story story-planning capture: minimal notes that preserve creative freedom. Use when exploring narrative ideas, discussing characters, planning chapters, or thinking through story possibilities.
---

# Brainstorming Capture

Capture story brainstorming as minimal working notes that preserve creative freedom. The core principle: record what was stated, mark what was suggested, and don't fill gaps the author left open.

## Report Structure

When producing a standalone brainstorm document, preserve the source of each
part. Tag only new AI suggestions. Author statements remain untagged, and
hidden content stays wrapped in `<hidden>...</hidden>`.

```markdown
# [Topic]: [Angle]

## Approach
What the author stated about the direction and constraints.

## Ideas
<AI>Concrete possibilities, organized logically.</AI>

## Tradeoffs
<AI>What each option gains and gives up.</AI>

## Connections
Author-stated connections remain untagged.
<AI>New possible connections suggested during this pass.</AI>

## Open Questions
<AI>Questions the author should consider before committing.</AI>

## Author-Only Context
<hidden>Any author-only information stays hidden.</hidden>
```

## Source Tagging

**Default: untagged text = the author said it.** Most story-planning content comes from the author, so untagged is the common case.

Three tags for special context:

**`<AI>...</AI>`**: AI suggestions and possibilities. Use when offering ideas the author didn't state. Keep brief: 2-3 options, not exhaustive lists.

**`<hidden>...</hidden>`**: Author-only information for planned reveals. Secret motivations, future twists, behind-the-scenes reasoning that readers and characters don't know yet.

**`<rejected>...</rejected>`**: Ideas explicitly considered and discarded. Recording why something was rejected prevents re-suggesting it and preserves the reasoning for later reconsideration.

## Minimal Capture

Record what the author stated. Don't elaborate, don't fill gaps, don't invent details they didn't mention.

AI suggestions are valuable: wrap them in `<AI>` tags and keep them brief.

- "Character A competes with B" → capture as stated. Optionally: `<AI>Tournament? Political? Trial?</AI>`
- "Maybe creates tension" → record as uncertain. Don't resolve the maybe.
- "Three kingdoms" → note three kingdoms. Don't name them.

## Preserve Vagueness

If the author left it vague, the notes stay vague. "Might," "maybe," "thinking about," "something like": all preserved as-is. Vagueness isn't a problem to solve; it's creative space the author is keeping open.

Multiple contradictory options coexist until the author chooses. Don't resolve them. Don't pick the "best" one.

## Output Format

Use whatever structure fits the discussion: bullet lists, topic sections, timeline format, question-driven, freeform. The goal is clarity, not template compliance.

Essential elements:
- Minimal capture of author's words
- Vagueness preserved
- AI suggestions wrapped in `<AI>` tags
- Author-only info wrapped in `<hidden>` tags
- Rejected ideas wrapped in `<rejected>` tags when relevant

## Brainstorming Types

All story-planning types share the core principles above. See resources for specialized guidance:

- [`resources/brainstorming/chapter-planning.md`](brainstorming/chapter-planning.md): beat and scene exploration, pacing thoughts, chapter structure
- [`resources/brainstorming/character-development.md`](brainstorming/character-development.md): motivations, arcs, relationships, voice
- [`resources/brainstorming/worldbuilding.md`](brainstorming/worldbuilding.md): systems, cultures, geography, lore
- [`resources/brainstorming/continuity-timeline.md`](brainstorming/continuity-timeline.md): chronology, contradictions, knowledge propagation

Read the relevant resource when the story-planning focuses on that area.

## Calibration

The success check: the author says "yes, that's what I said." Capture stated
facts, preserve uncertainty, add brief tagged options when useful, keep notes
minimal.

## File Placement

See the `story-memory` skill for canonical directory conventions and naming.
During interactive brainstorming, every direct author answer that settles a
durable fact or decision is already confirmation: persist it immediately
through a previewed, recoverable `/project-maintenance` transaction before
asking the next question. Never delay settled decisions until the brainstorm
completes. Preserve the answer's source tag and author/character/reader
knowledge boundaries. Do not persist an answer the author marks provisional or
asks not to save, and do not promote unresolved options or AI suggestions.

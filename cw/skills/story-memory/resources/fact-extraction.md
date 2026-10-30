---
name: story-memory
description: >
  Extract factual state changes from accepted prose for previewed KB synchronization. Use when a chapter needs its canon, timeline, character state, and terminology captured or an ambiguous change needs author review.
---

# Fact Extraction

Read written chapters and extract the *factual state diff*: anything the
chapter made true that wasn't before, and anything it changed about what was
already true.

## Truth, Reports, and Beliefs

A statement appearing in accepted prose is not automatically world truth.
Separate an event the text establishes from what a character says, believes,
remembers, infers, or hears. Account for unreliable narration and POV limits.
“She says the king died” establishes that she made the claim; record the death
as confirmed only when the author or reliable story evidence establishes it.
Preserve who knows what and when; do not make a hidden truth available to an
earlier character or reader context.

## What to Extract

Common categories to look for, but don't treat as exhaustive:

- Character state changes: physical, emotional, locational, what they now know, what they can now do
- Timeline events: what happened and when, anchored to the main chronology and to any character sub-timeline the event touches, with one shared anchor on both
- Canon facts: worldbuilding details now established by appearing in prose, which will constrain future writing
- Relationship shifts: alliances, trust, power dynamics
- Reveals: what readers now know vs. what characters now know (often different)
- Terminology evidence: new or changed usage for magic, factions, places, customs, relationships, titles, invented words, or recurring in-world phrases
- Anything else the chapter establishes that future agents would need to know to stay consistent

If something the chapter establishes doesn't fit the common categories but still feels load-bearing, capture it anyway. Closed taxonomies lose information.

## Prepare the Promotion Proposal

Extract once, compare with existing records, and propose updates rather than
creating parallel accounts. Include sources, applicable story time, and which
claims remain uncertain. Maintain shared anchors across main and character
timelines when those records exist; do not retime silently to erase a conflict.

Use `/kb-management`'s promotion procedure for authorization, source status,
and durable updates after prose acceptance. Accepted prose supports only what
it directly and unambiguously establishes. Keep inferred implications and
conflicting claims provisional. This resource extracts evidence; it does not
independently authorize file changes.

Use `resources/continuity-records.md` only when the existing project needs those
formats. Run `cw check continuity` through `/project-maintenance` when supported
records are present and useful; inspect coverage and do not invent records to
satisfy a checker.

## Quality Bar

Entries are compressed, annotated, factual. "The protagonist learned that the
mentor's secret project started three years before her arrival — Chapter 7: Scene where the protagonist learns when the mentor's secret project began" is
specific, sourced, factual. Cite prose evidence as `Chapter N: Scene where X
discovers Y` and project-document evidence by path, such as `magic-system.md`.
Treat vocab cautiously: propose an existing vocab entry update only when the
canonical term is already settled. Otherwise report
candidate terms, aliases actually used, and chapter sources for the author or
orchestrator to ratify. Future agents read these to maintain continuity; vague
entries create vague continuity.

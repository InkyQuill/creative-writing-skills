---
name: story-memory
description: >
  Extracting factual state changes from written chapters into the kb. Use when a chapter needs its canon, timeline, character state, and terminology captured.
---

# Fact Extraction

Read written chapters and extract the *factual state diff*: anything the
chapter made true that wasn't before, and anything it changed about what was
already true.

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

## Writing to the KB

Update existing entries rather than creating duplicates. A character entry should grow chapter by chapter as their state evolves: each chapter adds to their entry rather than creating a new file.

Cross-link between entries. If a chapter establishes a relationship change between two characters, both character entries should reflect it, and the timeline entry should reference the event. When an event lands on a character sub-timeline as well as the main timeline, record it once with its shared anchor on both, and keep the two synchronized on every later update. If updating one side would desynchronize the other — shifted order, stretched duration, knowledge arriving too early — flag it as a conflict rather than re-timing silently.

Maintain the continuity records (`resources/continuity-records.md`) as part of extraction: write the chapter's scene record and timeline rows, move promises and questions to their new statuses with their chapter references, and refresh the state snapshot to the new writing front. Run the deterministic checker when extraction finishes; report its findings alongside the extraction report rather than silently repairing records.

Check for conflicts between what the chapter establishes and what's already in the kb. If the chapter contradicts existing canon or uses a term differently from the relevant vocab file, flag it in your report; preserve the existing record until the author or orchestrator resolves the conflict. The contradiction may be an error in the chapter, an intentional retcon, or a vocabulary decision that needs recording.

## Quality Bar

Entries are compressed, annotated, factual. "The protagonist learned that the
mentor's secret project started three years before her arrival — Chapter 7: Scene where the protagonist learns when the mentor's secret project began" is
specific, sourced, factual. Cite prose evidence as `Chapter N: Scene where X
discovers Y` and project-document evidence by path, such as `magic-system.md`.
Treat vocab cautiously: update existing vocab
entries only when the canonical term is already settled. Otherwise report
candidate terms, aliases actually used, and chapter sources for the author or
orchestrator to ratify. Future agents read these to maintain continuity; vague
entries create vague continuity.

---
name: qi-layer
description: 'Use when writing or maintaining harness instruction files and .context/CONTEXT.md: keep intent docs minimal and load-bearing.'
---

# qi-layer

When colocated knowledge changes, keep its project instructions and .context
documentation synchronized with the source in the same change.
This skill owns how to write and structure that knowledge.

Load `$project-bootstrap` first to resolve instruction entrypoints.
Load `$knowledge-layers` for where each layer lives and what it holds.
Load `$llm-writing` if it isn't already loaded.

This skill is about **how to write and maintain** the directory-local pair:
resolved project instructions and `.context/CONTEXT.md`. The pair governs any
tree agents work in — code, the KB, docs, work directories. Project instructions load into an agent's
bounded context as standing instructions: write it like a prompt, minimal,
every line load-bearing.

## The Four Principles

1. **Fractal Compression**: leaf project instructions summarize their directory's
   content; parent project instructions summarize their children. Each level is a
   compression of the level below.
2. **Hierarchical Summarization**: root provides broad architectural
   frame. Leaves provide local working knowledge. Agents accumulate
   understanding as they descend.
3. **LCA Deduplication**: shared knowledge appears once at the shallowest
   node covering all relevant paths. Never duplicate between siblings.
4. **Progressive Disclosure**: give just enough to work correctly at this
   level. Link to `.context/CONTEXT.md` for depth.

## Writing Project Instructions

Agents read applicable project instructions before opening anything else in the tree — write for
that moment. Ask: **what must someone understand before working here?**
That's what project instructions capture.

Keep project instructions as short as the directory allows, rarely past 200 lines.
Include only what has substance:

- **Purpose**: what this area IS and what it ISN'T (1–3 sentences)
- **Mental model**: how to think about this area, key abstractions
- **Key rules**: constraints, what breaks if you get it wrong
- **Anti-patterns**: what NOT to do here
- **Downlinks**: to `.context/` for depth, to related areas

An agent that only reads project instructions should be able to work correctly here.
An agent that also reads .context/ should be able to change things safely.

## Writing .context/CONTEXT.md

Reference depth, co-located with the code it describes. Where an agent
goes when it needs contracts, architecture, or rationale in detail.

Sections (use only those with substance):

- **Contracts**: interfaces, invariants, what breaks if violated
- **Architecture**: component relationships, data flow, dependency direction
- **Rationale**: why X over Y, rejected alternatives
- **Patterns**: how to work here, concrete pitfalls

The `.context/` directory is extensible: additional files alongside
CONTEXT.md for specialized concerns.

## What Does NOT Belong in Project Instructions

Apply the **every-session test**: root project instructions load on every session.
If knowledge is only relevant when working in a specific domain, it belongs
in that domain's project instructions or .context/, not root.

Apply the **think-vs-lookup test**: text whose removal would cause a
*wrong decision* belongs in project instructions. Text an agent would merely have to
*look up* belongs in .context/. Text that changes no behavior gets
deleted — agents already know how to code and follow common conventions.

Specific failure modes:

- **Session bleed**: LLM working notes that calcified into the instruction
  file. Tells: status-update language ("**deleted**", "shipped", "deferred"),
  implementation terms packed without framing, history narration.
- **Reference material posing as intent**: tables, command blocks, full
  scheme vocabularies, implementation specifics.
- **Redundant guards**: prose warnings for invariants already enforced by
  tests or types. The code is the real guard; prose rots faster.
- **Duplicated knowledge**: restating what lives in a skill, a domain
  .context/, or a KB page. Point, don't duplicate.
- **Domain-specific detail at root**: URI scheme tables, gateway pricing
  internals, auth implementation details. These belong in their domain's
  project instructions, not root.

## Structural Rules

- Relative paths for all links
- Project instructions and .context/ at the same directory level (siblings)
- Link to files, not headings (headings change more often)
- Lateral links between `.context/` directories with contracts between them
- LCA deduplication: if two siblings share context, put it in the parent

## Entrypoint Compatibility

`$project-bootstrap` owns filenames, imports, compatibility, migration, and
conflict handling. This skill writes substantive shared instructions only to
the canonical path it resolves. Do not duplicate entrypoint logic here.

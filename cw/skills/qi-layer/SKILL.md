---
name: qi-layer
description: "'Use when writing or maintaining CLAUDE.md, .context/CONTEXT.md, or CLAUDE.md mirrors: keep intent docs minimal and load-bearing.'"
---

# qi-layer

When colocated knowledge changes, keep its CLAUDE.md and .context documentation synchronized with the source in the same change.
This skill owns how to write and structure that knowledge.

Load `/knowledge-layers` for where each layer lives and what it holds.
Load `/llm-writing` if it isn't already loaded.

This skill is about **how to write and maintain** the directory-local pair:
CLAUDE.md and `.context/CONTEXT.md`. The pair governs any tree agents work
in — code, the KB, docs, work directories. CLAUDE.md loads into an agent's
bounded context as standing instructions: write it like a prompt, minimal,
every line load-bearing.

## The Four Principles

1. **Fractal Compression**: leaf CLAUDE.md summarizes its directory's
   content; parent CLAUDE.md summarizes its children. Each level is a
   compression of the level below.
2. **Hierarchical Summarization**: root provides broad architectural
   frame. Leaves provide local working knowledge. Agents accumulate
   understanding as they descend.
3. **LCA Deduplication**: shared knowledge appears once at the shallowest
   node covering all relevant paths. Never duplicate between siblings.
4. **Progressive Disclosure**: give just enough to work correctly at this
   level. Link to `.context/CONTEXT.md` for depth.

## Writing CLAUDE.md

Agents read CLAUDE.md before opening anything else in the tree — write for
that moment. Ask: **what must someone understand before working here?**
That's what CLAUDE.md captures.

Keep CLAUDE.md as short as the directory allows, rarely past 200 lines.
Include only what has substance:

- **Purpose**: what this area IS and what it ISN'T (1–3 sentences)
- **Mental model**: how to think about this area, key abstractions
- **Key rules**: constraints, what breaks if you get it wrong
- **Anti-patterns**: what NOT to do here
- **Downlinks**: to `.context/` for depth, to related areas

An agent that only reads CLAUDE.md should be able to work correctly here.
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

## What Does NOT Belong in CLAUDE.md

Apply the **every-session test**: root CLAUDE.md loads on every session.
If knowledge is only relevant when working in a specific domain, it belongs
in that domain's CLAUDE.md or .context/, not root.

Apply the **think-vs-lookup test**: text whose removal would cause a
*wrong decision* belongs in CLAUDE.md. Text an agent would merely have to
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
  CLAUDE.md, not root.

## Structural Rules

- Relative paths for all links
- CLAUDE.md and .context/ at the same directory level (siblings)
- Link to files, not headings (headings change more often)
- Lateral links between `.context/` directories with contracts between them
- LCA deduplication: if two siblings share context, put it in the parent

## CLAUDE.md Mirrors

Claude harnesses read CLAUDE.md, not CLAUDE.md. Give every CLAUDE.md a
sibling CLAUDE.md whose first line is `@CLAUDE.md` — normally the whole
file. After creating or moving CLAUDE.md files, inspect the containing tree: create missing mirrors, leave exact mirrors unchanged, and report divergent files as conflicts.

Never write shared instructions into CLAUDE.md. Claude-only knowledge is rare; when it exists, put it below the `@CLAUDE.md` import and expect manual mirror verification to keep flagging the file, so the divergence stays visible.

Loading differs by level. At the root, each harness auto-loads its own
file every session: Claude reads CLAUDE.md, others read CLAUDE.md. In
subdirectories, Claude auto-injects CLAUDE.md when it touches files there;
other agents see nested CLAUDE.md only by reading it on entry. Don't lean
on Claude's auto-injection: a nested CLAUDE.md carries the local additions
an agent needs on entry, with everything else inherited from ancestors.

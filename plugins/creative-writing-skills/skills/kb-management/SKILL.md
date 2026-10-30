---
name: kb-management
description: >
  Maintaining the story knowledge base: creating, updating, and organizing
  reference pages in the author's chosen layout. Use when capturing finalized story
  knowledge, updating character profiles, documenting world mechanics, or
  restructuring the kb.
---

# KB Management

The knowledge base is the project's durable knowledge, wherever the author stores it. Drafting, critique,
planning, and research passes read from it for context. This skill covers how
to maintain it well.

## Establish the Mechanical Floor

Use `cw check kb` through `$project-maintenance` when knowledge tags or legacy
metadata identify the relevant records. Otherwise audit the named author files
directly. Read coverage as well as findings; an unassessed record is not verified. Repairable mechanical warnings do not
block the requested knowledge work: continue wherever the required sources and
target page are readable, and schedule bounded repairs separately. A required
target that cannot be read safely is the only mechanical reason to stop that
semantic work.

The agent owns hashes, indexes, base revisions, migration mechanics, and repair
commands. Author edits are valid project input; never ask the author to maintain
SHA values or generated indexes.

## Layers

**Canon**: established facts the story has committed to. Once a chapter is
published/finalized, the facts it establishes are canon. Contradicting canon
breaks reader trust.

**Wiki**: synthesized reference pages. How the magic system works, character
relationships, faction politics. Living documents that evolve as the story
develops.

**Styles**: voice reference files derived from prose samples. Drafting and
critique passes depend on these for voice consistency.

**Samples**: approved, scoped evidence for author voice. A sample is not an
instruction to imitate every surface feature.

**Vocab**: canonical story terms, aliases, and exclusions live in the author's
vocabulary notes; `kb/vocab.md` is one optional legacy example.

**Issues**: tracked writing problems that span multiple chapters (recurring
tics, pacing patterns, continuity errors). See the story-memory skill.

## Page Conventions

### One Concept Per Document

Each doc covers one coherent topic: one character, one location, one system.
When a doc covers two unrelated topics, split it. When two docs explain the
same thing from different angles, merge or cross-reference.

Name files by what they describe (`fire-magic.md`, `protagonist.md`), not
when they were written (`session-3-notes.md`).

### Organization

Use existing files, optional inherited `kb`/`characters`/`world` tags, and the
author's instructions. Flat files and nested/shared folders are valid. The
following paths are optional legacy scaffold examples, never required homes:

```text
kb/vocab.md                              # canonical terms
kb/characters/<name>.md                  # character pages
kb/world/<topic>.md                      # locations, factions, systems
kb/canon/<chapter-or-arc>.md             # hard facts
kb/styles/<style-name>.md                # voice references
kb/samples/<sample-name>.md              # approved prose samples
kb/issues/<issue-name>.md                # persistent writing problems
kb/continuity/timeline.md                # master chronology
kb/continuity/promises.md
kb/continuity/questions.md
kb/continuity/state.md
kb/continuity/scenes/<chapter>.md
```

Legacy schema validation applies only to opted-in managed records. Do not move
or reshape author knowledge to satisfy it. Folder/file tags describe purpose;
acceptance and provenance must come from explicit evidence.

### Voice Evidence and Guidance

Use the author's sample and style locations or a named output path. Descriptive
filenames help discovery without imposing a directory structure.

Every sample records manuscript **language/tag**, **scope/applicability**,
evidence role (`authoritative`, `aspirational`, or `negative`), exact
**source/citation and source-tag boundary**, the excerpt or chapter pointer,
and **why this sample is evidence**. Every style reference records language and
prose-profile applicability, scope, linked sample and accepted-chapter
evidence, observed versus author-specified guidance, actionable tendencies,
allowed variation, and anti-patterns.

Examples are evidence, not a mechanical imitation corpus. Missing or sparse
samples leave the resolved language and prose-profile defaults in force.
Label inference instead of inventing a rule or repeatedly asking the author.

### Character Voice Roster

Maintain persistent speech traits in the author's existing character or voice
records. Use `$creative-writing-craft`'s `resources/dialogue-rules.md` for the
roster template, evidence/status rules, and contextual variation. Update
established traits from author decisions or accepted prose; keep draft and
simulation discoveries provisional. Read-only work returns proposed updates.

### Linking

Link to related pages with relative paths. Cross-reference instead of
duplicating: one source of truth per concept. A character page links to
the location page for their home, the timeline entry for their arc, etc.

### Readability

Write pages that work in isolation:

- **Self-contained**: enough context that a reader doesn't need three
  other pages first
- **Scannable**: headers, bullets, tables. Bold key terms on first use.
- **Concrete**: specific quotes, chapter references, scene citations
- **Current**: update when the story invalidates or extends what's here

## Vocab Pages

Use vocab pages when terms matter across agents: magic names, faction labels,
place names, titles, relationship labels, invented words, recurring in-world
phrases, and genre terms with project-specific meanings.

Each entry should include:

- **Canonical name**: the form agents should use
- **Definition**: one to three sentences, including what the term is not when ambiguity is likely
- **Aliases**: names the author, characters, drafts, or older kb pages actually use
- **Source**: where the usage was established or decided

Resolve conflicts early. If two terms seem to name the same thing, pick the
canonical form with the author or flag it in the report instead of carrying
both forward silently.

## When to Create vs Update

**Create** a new page when a concept is finalized enough to be referenced
by other agents. Don't create pages for things still in story-planning.

**Update** an existing page when new chapters establish facts about it,
when the author makes decisions that change it, or when a page has become
stale.

**Split** when a page grows past ~200 lines or covers multiple unrelated
concepts.

## What Belongs in KB vs Work

- Finalized knowledge → the author's chosen knowledge records
- Draft iterations, brainstorm captures, critique reports → the selected
  drafts, brainstorm, and reviews folders (`cw get-folder <role>`); `work/`
  is the full-scaffold default
- Promoted facts after a draft completes → the relevant author-approved record

Use `$story-memory` for routine fact extraction from completed chapters.
Author direct edits are valid and authoritative input; always re-read them.
For applicable managed operations, use `$project-maintenance`: form the exact
edit or batch, preview the transaction, and apply within the confirmed scope.
For ordinary files, use safe named edits with a reviewable diff, preserving
concurrent changes and source tags; do not promise journal undo for those edits. If a journaled result was mistaken, inspect history and preview
`cw undo <transaction-id>` using its recorded transaction ID. For unjournaled
named edits, inspect the current bytes and available history, then prepare a
reviewed corrective edit; do not claim transaction undo.

## Promotion Uses a Separate Reviewed Update

Draft or manuscript acceptance does not itself write anything into the KB.
After acceptance, re-read the prose and split extraction into settled evidence
and material questions. Synchronize facts directly and unambiguously established
by the text through a separate previewed, recoverable `$project-maintenance`
transaction when managed mechanics apply, or a separate reviewed named edit
otherwise, without asking for re-approval. Separate update does not mean
separate confirmation. Include exact destination pages and provenance back to
the accepted passage or prior direct author answer.

This promotion boundary also applies to voice artifacts. The style-creator
writes only a proposal under the selected reviews folder (`cw get-folder reviews`);
muse or the orchestrator promotes
an approved sample or style through a separate previewed, recoverable
transaction when applicable, or a separate reviewed named edit otherwise. A direct author designation of a sample's role or an explicit
approval of a style proposal is already confirmation.

Ask only when ambiguity, inference or implication, a canon conflict, a retcon,
an uncertain source tag, or an uncertain character or reader knowledge boundary
means different answers would materially change canon or knowledge boundaries.
Keep those items as promotion proposals until resolved. Preserve source tags
and knowledge boundaries; acceptance never turns an AI suggestion into
author-stated canon. Do not ask redundant confirmation for every promotion.

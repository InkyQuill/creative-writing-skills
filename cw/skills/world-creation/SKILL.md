---
name: world-creation
description: "Grilling session for story worldbuilding that challenges a lore idea against the existing setting, characters, notes, and other project Markdown, sharpens terminology and consequences, and updates concise non-story lore/supporting files as decisions crystallize. Use when the user wants to brainstorm, change, reconcile, expand, or sanity-check species, cultures, powers, characters, history, geography, institutions, economy, religion, factions, or other setting material. Do not use for rewriting story prose or challenging finished scenes against lore."
---

<what-to-do>

Run a structured worldbuilding interrogation. First map the relevant existing project context, then interview me about the idea one decision at a time until we reach a shared understanding. Walk down each branch of the lore tree, resolving dependencies between decisions before moving outward. For each question, provide your recommended answer.

Ask the questions one at a time, waiting for feedback on each question before continuing.

If a question can be answered by exploring project files, explore them instead.

Direct author answers that settle durable lore are confirmation; persist them
incrementally without asking for redundant confirmation. Suggestions, inferred
implications, and unresolved options remain provisional and are not canonized.

Treat canonical prose under `story/chapters/` and draft prose under
`work/drafts/` as read-only evidence. Never rewrite, patch, or directly edit
prose or scene text in this workflow, regardless of location.

</what-to-do>

<supporting-info>

## Project awareness

Use the canonical schema-v1 roots: `kb/world/` for setting lore,
`kb/characters/` for character facts, `work/plans/` for planning artifacts,
`story/chapters/` for accepted prose, and `work/drafts/` for draft prose. Use
`/project-maintenance` for schema checks, previewed recoverable mutations,
indexes, and reindexing. If a project needs scaffold or migration before these
roots are writable, route that preparation through `/project-maintenance`;
never establish an alternate writable layout from local folder names.

Use folder index files first when they exist, then search filenames and file
contents, then read the relevant files faithfully before asking substantive
questions. Files under `story/chapters/` and `work/drafts/` may be read to
understand on-page evidence but remain read-only. This skill may point out that
lore decisions require later prose edits, but it must not perform those edits.

### Discovery order

Before asking substantive lore questions:

1. Identify the likely project root from the user's working directory and nearby folders.
2. Inspect existing indexes and the canonical schema-v1 directories. Look for:
   - `_index.md`
   - `index.md`
   - `INDEX.md`
   - `README.md`
3. If required canonical roots are missing, use `/project-maintenance` to
   prepare or diagnose them rather than selecting a local alternative.
4. Read the most relevant indexes in this order when present:
   - project-level index or README
   - `kb/world/` index
   - `kb/characters/` index
   - indexes in relevant subfolders such as systems, locations, or factions, or equivalent local categories
5. Use the indexes to choose targeted files to read. Do not treat an index summary as a substitute for the linked source file when the exact canon matters.
6. If no index exists, fall back to filename discovery and content search
   within the canonical roots. The agent handles reindexing when a durable
   transaction changes discoverability.
7. If the topic touches story events, search `story/chapters/` and
   `work/drafts/` for evidence only after reading lore and character files.
   Keep all prose read-only.

Index files are maps, not canon by themselves unless they explicitly contain canon facts. Prefer source topic files for final wording and conflict checks.

### File structure

Keep durable world and character facts in their canonical KB roots. Put
planning proposals in `work/plans/`. Use other schema-v1 KB destinations only
when their declared document kind matches the fact. If the current topic
crosses several files or directories, read all relevant material before
challenging the idea.

If a folder has an index file, preserve its role:

- Use it to understand folder scope, canonical file homes, and existing taxonomy.
- Follow Markdown links from the index when they appear relevant.
- When adding a new durable lore or character file, update the nearest relevant
  index in the same transaction.
- When changing a file's title, topic, or scope in a way that makes an index
  stale, update the index in the same transaction.
- The agent owns reindexing. Create an index only when several durable files
  make it useful; ask only when its scope or taxonomy is materially ambiguous.

Create files lazily—only when a direct settled answer has no existing canonical
home. The settled answer authorizes the smallest unambiguous canonical
destination; preview the creation through `/project-maintenance` without a
second confirmation. Ask when competing destinations would materially change
canon, provenance, or a knowledge boundary.

### Editable vs read-only areas

Editable through previewed, recoverable `/project-maintenance` transactions:

- `kb/world/` for durable setting facts
- `kb/characters/` for settled character facts, relationships, constraints, or backstory
- `work/plans/` for planning context that is not durable canon
- another schema-v1 KB path only when its document kind is the unambiguous home

Read-only in this workflow:

- `story/chapters/` canonical prose
- `work/drafts/` draft prose
- any other prose or scene text, regardless of location

If a confirmed worldbuilding change affects existing prose, record the lore decision in the smallest appropriate non-story file and tell the user which prose files may need a separate revision pass. Do not rewrite prose here.

## During the session

### Operating loop

For each worldbuilding branch:

1. State the existing context briefly:
   - `Existing lore`
   - `Existing character/story evidence`
   - `Gaps or conflicts`
2. Ask one decision question.
3. Include your recommended answer and why it fits.
4. Wait for the user's answer.
5. When a direct author answer settles a durable fact or decision, persist it
   immediately through a previewed, recoverable transaction via
   `/project-maintenance` before asking the next question.
6. Update the smallest canonical non-story file and any affected index in that
   transaction; the agent performs reindexing.
7. Continue to the next dependent question.

Do not ask for redundant confirmation. Unless the author marks an answer
provisional or asks not to save it, persist every settled direct answer. Ask
only when ambiguity, inference, conflict, retcon, source-tag uncertainty, or
character/reader
knowledge-boundary uncertainty means different answers materially change canon
or knowledge boundaries. Do not jump straight to a large taxonomy,
encyclopedia entry, or multi-file rewrite. Build from settled decisions.

### Challenge against existing lore

When the user proposes something that conflicts with existing files, call it out immediately. "The current `Elves.md` says X, but this idea implies Y — should we revise X, narrow Y, or make this an in-world contradiction?"

Also challenge against character files and story evidence. "The story has
already shown X in `story/chapters/chapter-01.md`, but this lore change implies
Y. Should the lore be narrowed, or should that scene be flagged for a later
rewrite?"

### Sharpen fuzzy setting language

When the user uses vague or overloaded terms, propose a precise canonical term. "You're saying 'magic' — do you mean Talents, Skills, divine intervention, or something else?"

### Discuss concrete scenarios

Stress-test lore with specific situations. Invent small scenarios that probe boundaries: edge cases, social consequences, power abuse, mixed ancestry, institutional response, everyday life, taboos, trade, law, inheritance, or war.

### Trace consequences

Do not let a cool idea remain isolated. Ask who gains power, who loses status, what becomes illegal, what becomes normal, what institutions adapt, and what limits keep the element from dominating the entire setting.

### Cross-reference across project files

When the user states how something works, check whether related lore, character, note, and story files agree. If a contradiction appears, surface it before continuing. Prefer targeted reads over relying on memory.

Use indexes to find adjacent files that might contradict or depend on the decision. For example, a new slavery-law detail may require checking the regional location file, the relevant social-system file, the faction enforcing it, and any character whose backstory depends on it.

### Update non-story files inline

When a fact is resolved by a direct author answer, update the relevant
canonical non-story file right there through `/project-maintenance`. Do not
batch settled lore until the end unless the user asks you to wait. Use the
format in [world-file-format.md](./references/world-file-format.md) for
worldbuilding files, and preserve compatible author formatting in character or
other Markdown files unless normalization is explicitly requested.

Worldbuilding files should contain durable setting facts, not transcripts, discarded alternatives, or long reasoning. Keep them concise but complete enough that future sessions can reconstruct the canon.

Character files should contain durable character facts and constraints, not scene rewrites. If a decision changes how a character should behave in prose, record the constraint in the character file and flag the affected story material for a future prose-level review.

Index updates should be concise:

- Add or adjust one table row or bullet per changed file.
- Keep links relative to the index file.
- Keep descriptions short enough to scan.
- Do not duplicate full lore from topic files into the index.

### Record open questions only with permission

If a question remains unresolved, ask whether to record it as an open question in the relevant file. Do not add speculative possibilities to canon sections.

### Preserve user's ownership

Your role is to pressure-test and recommend, not to decide. Always distinguish:

- `Existing lore`: what files already say
- `Existing character/story evidence`: what character files or read-only story prose already show
- `Recommendation`: what you think fits best
- `User decision`: what should be written

## Boundary with prose-level review

This skill develops and records lore. It may identify that existing story or draft prose conflicts with lore or would benefit from revision, but it must not suggest full rewrites or patch prose text. Handle prose-level changes in a separate revision workflow.

</supporting-info>

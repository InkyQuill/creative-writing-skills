---
name: world-creation
description: "Grilling session for story worldbuilding that challenges a lore idea against the existing setting, characters, notes, and other project Markdown, sharpens terminology and consequences, and updates concise non-story lore/supporting files as decisions crystallize. Use when the user wants to brainstorm, change, reconcile, expand, or sanity-check species, cultures, powers, characters, history, geography, institutions, economy, religion, factions, or other setting material. Do not use for rewriting story prose or challenging finished scenes against lore."
---

<what-to-do>

Run a structured worldbuilding interrogation. First map the relevant existing project context, then interview me about the idea one decision at a time until we reach a shared understanding. Walk down each branch of the lore tree, resolving dependencies between decisions before moving outward. For each question, provide your recommended answer.

Ask the questions one at a time, waiting for feedback on each question before continuing.

If a question can be answered by exploring project files, explore them instead.

Do not write new canon, revise existing canon, or create lore/supporting files without my confirmation. Suggestions are allowed; canonization is not.

Treat canonical prose and draft prose as read-only evidence. Never rewrite, patch, or directly edit files under `chapters/`, `story/`, `drafts/`, or `work/drafts/` during this workflow. Treat prose or scene text found anywhere else as read-only too.

</what-to-do>

<supporting-info>

## Project awareness

Projects may keep lore in `worldbuilding/` with characters in `characters/`, or in `kb/world/` with characters in `kb/characters/`. Canonical prose may live in `chapters/` or `story/`; draft prose may live in `drafts/` or `work/drafts/`; and planning may live in `plot/` or `work/outline/`. Treat both layouts as equal conventions and follow the structure already established by the project.

Use folder index files first when they exist, then search filenames and file contents, then read the relevant files faithfully before asking substantive questions. Files under `chapters/` and `story/` may be read to understand what has already appeared on-page, but both are read-only. Files under `drafts/` and `work/drafts/` are also read-only. This skill may point out that lore decisions would require later prose edits, but it must not perform those edits.

### Discovery order

Before asking substantive lore questions:

1. Identify the likely project root from the user's working directory and nearby folders.
2. Inspect existing indexes, directories, and their contents for both layout conventions before choosing paths. Look for:
   - `_index.md`
   - `index.md`
   - `INDEX.md`
   - `README.md`
3. Select the locally established layout from the indexes and populated directories already present. If both layouts exist, use the one with more relevant established content. Ask one layout question only when both layouts are absent or equally populated; do not invent or migrate a layout silently.
4. Read the most relevant indexes in this order when present:
   - project-level index or README
   - `worldbuilding/` or `kb/world/` index
   - `characters/` or `kb/characters/` index
   - indexes in relevant subfolders such as systems, locations, or factions, or equivalent local categories
5. Use the indexes to choose targeted files to read. Do not treat an index summary as a substitute for the linked source file when the exact canon matters.
6. If no index exists, fall back to filename discovery and content search within the selected local structure.
7. If the topic touches story events, search both canonical and draft prose locations that exist for evidence only after reading lore and character files. Keep all prose read-only.

Index files are maps, not canon by themselves unless they explicitly contain canon facts. Prefer source topic files for final wording and conflict checks.

### File structure

Support these equivalent path roles:

| Concern | Layout A | Layout B |
|---|---|---|
| World lore | `worldbuilding/` | `kb/world/` |
| Characters | `characters/` | `kb/characters/` |
| Canonical prose | `chapters/` | `story/` |
| Draft prose | `drafts/` | `work/drafts/` |
| Planning | `plot/` | `work/outline/` |

Projects can contain other supporting areas such as `explorations/`, `continuity/`, `style/`, or `glossary/`. Infer each folder's scope from its name, index, and contents. If the current topic crosses several files or directories, read all relevant material before challenging the idea.

If a folder has an index file, preserve its role:

- Use it to understand folder scope, canonical file homes, and existing taxonomy.
- Follow Markdown links from the index when they appear relevant.
- When adding a new durable lore or character file after confirmation, update the nearest relevant index in the same session.
- When changing a file's title, topic, or scope in a way that makes an index stale, update the index after confirmation.
- Do not create an index unless the folder has multiple durable files and the user confirms the structure. If creating one, keep it short and navigational.

Create files lazily — only when the discussion produces confirmed information that has no natural home. If no relevant file exists, propose the file path in the selected local layout and wait for confirmation before creating it.

### Editable vs read-only areas

Editable after confirmation:

- `worldbuilding/` or `kb/world/` for durable setting facts
- `characters/` or `kb/characters/` for confirmed character facts, relationships, constraints, or backstory
- `plot/` or `work/outline/` for confirmed planning context when it is clearly the best home
- `continuity/`, `style/`, `glossary/`, or other non-prose Markdown when it is clearly the best home for confirmed project context

Read-only in this workflow:

- `chapters/` and `story/` canonical prose
- `drafts/` and `work/drafts/` draft prose
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
5. After confirmation, update the smallest appropriate non-story file immediately.
6. If the update changes discoverability, update the relevant index file too.
7. Continue to the next dependent question.

Do not jump straight to a large taxonomy, encyclopedia entry, or multi-file rewrite. Build from confirmed decisions.

### Challenge against existing lore

When the user proposes something that conflicts with existing files, call it out immediately. "The current `Elves.md` says X, but this idea implies Y — should we revise X, narrow Y, or make this an in-world contradiction?"

Also challenge against character files and story evidence. "The story has already shown X in `chapters/chapter-01.md`, but this lore change implies Y. Should the lore be narrowed, or should that scene be flagged for a later rewrite?"

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

When a fact is resolved, update the relevant non-story file right there. Do not batch all confirmed lore until the end unless the user asks you to wait. Use the format in [world-file-format.md](./references/world-file-format.md) for worldbuilding files, and preserve existing local structure for character or other Markdown files unless the user asks to normalize them.

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

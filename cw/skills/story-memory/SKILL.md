---
name: story-memory
description: "Creative-writing domain knowledge for durable story state. Load when preserving or retrieving project memory — fact extraction, context scoping, reference writing, artifact layout, and issue tracking. Apply it directly for fiction-specific categories and conventions during knowledge work.\n"
---

# Story Memory

Knowledge that must survive the current pass: canon facts, context handoffs,
vocab/reference material, project layout, and persistent issues.

Use `/project-maintenance` for deterministic project mechanics. Run the check
relevant to the memory artifact before semantic reconciliation and interpret
repairable warnings internally. Continue semantic work when the required
sources are readable; a required target that cannot be read safely is the only
mechanical reason to stop. Direct author edits remain valid input and must be
re-read rather than overwritten from remembered state.

When the current user or project agreement refers to Hieronymus, load
`/hieronymus-integration` before selecting, retrieving, or delivering durable
memory. Keep file and Hieronymus provenance distinct. Trust assigned by the
agreement does not authorize a write, and replacement memory does not require a
file mirror.

Load the resource needed:

- `resources/story-context.md` — what context to pass into handoffs for writers, critics, brainstormers, and knowledge agents.
- `resources/fact-extraction.md` — extract durable facts from chapters: character state, timeline, reveals, terminology.
- `resources/continuity-records.md` — canonical `kb/continuity/` records consumed by `cw check continuity`: timeline, promises, questions, state snapshot, and scene records.
- `resources/story-reference-writing.md` — wiki pages, vocab, decisions, summaries, issue logs.
- `resources/writing-artifacts.md` — where work and kb artifacts live.
- `resources/writing-issues.md` — persistent writing issue tracking across chapters.

The agent owns hashes, indexes, base revisions, migration mechanics, and repair
commands. Never delegate SHA or generated-index maintenance to the author.

## Translation boundary

For translation-specific terms, voices and inheritance use /translation-memory.
Shared entity identity belongs to the project KB, while target expressions and
voice adaptations belong to the selected direction. Do not promote observations
from an auxiliary edition into original canon or another language's rules.

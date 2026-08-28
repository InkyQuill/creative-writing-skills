# Story Project Contract and CLI Design

**Status:** Revised after design review on 2026-08-28

## Summary

Creative Writing Skills will replace its two interchangeable story-project
layouts with one versioned Markdown project contract based on the existing
Layout B roles: accepted manuscript in `story/`, provisional artifacts in
`work/`, and durable story knowledge in `kb/`.

A bundled, standard-library-only Python CLI named `cw` will provide
deterministic project maintenance. It will validate the contract, prepare
context for agent reviews, manage working drafts, migrate older projects, and
apply reversible exact-anchor edits through one transaction engine. Skills
will retain literary judgment, author dialogue, and confirmation boundaries;
the CLI will not call a model or make semantic story decisions.

The project language used by this design is defined in [`CONTEXT.md`](../../../CONTEXT.md).

## Goals

- Give every creative-writing agent one project shape and one vocabulary.
- Make malformed structure, stale drafts, broken links, and structured
  continuity errors deterministic and reproducible.
- Preserve the distinction between accepted manuscript, provisional work, and
  durable story knowledge.
- Let agents edit files precisely with preview, conflict detection, history,
  and undo even when Git is unavailable.
- Work in ordinary folders synchronized by services such as Dropbox or
  Yandex Disk.
- Package the same CLI implementation with the canonical Codex plugin and its
  generated Claude and ZCode distributions.

## Author Experience

The author works with ordinary Markdown and may edit any story, work, or KB
file directly. The agent, not the author, is responsible for initialization,
frontmatter, indexes, tags, hashes, migrations, and repair commands. A malformed
index, missing optional field, stale context snapshot, or manually changed file
must not prevent the agent from reading the prose, discussing it, researching,
or offering a repair.

The CLI blocks a write only when continuing could lose or overwrite content:
an unknown newer schema, a path outside the project, a changed write
precondition, an ambiguous edit anchor, an unrecoverable transaction, or an
invalid migration plan. Contract drift that can be repaired without guessing
is a warning with an agent-facing next action. The default workflow lets the
agent repair such drift in a previewed transaction without asking the author
to understand the underlying metadata.

## Non-goals

- The CLI will not judge prose quality, infer story facts, resolve canon
  contradictions, or call an LLM.
- The first version will not attempt semantic spoiler detection or prose
  redaction beyond explicit project metadata and tags.
- The CLI will not require Git, a daemon, a database, a package manager, or
  network access.
- The project contract will not forbid unrelated files outside its managed
  roots.
- The first version will not provide a general-purpose merge engine. Draft
  rebasing stops when a deterministic patch cannot be applied unambiguously.
- The first version assumes one active writer process. It uses optimistic
  preconditions and recovery records, not a cross-machine or advisory lock.

## Canonical Project Shape

`cw init` creates the complete authored scaffold at once. Every authored
content directory has a generated `_index.md`, including empty directories, so the
shape survives version control and agents never need to choose a location.

```text
project/
├── project.md
├── story/
│   ├── _index.md
│   └── chapters/
│       └── _index.md
├── work/
│   ├── _index.md
│   ├── drafts/
│   │   └── _index.md
│   ├── plans/
│   │   └── _index.md
│   ├── reviews/
│   │   └── _index.md
│   ├── brainstorm/
│   │   └── _index.md
│   └── archive/
│       └── _index.md
├── kb/
│   ├── _index.md
│   ├── vocab.md
│   ├── characters/
│   │   └── _index.md
│   ├── world/
│   │   └── _index.md
│   ├── canon/
│   │   └── _index.md
│   ├── continuity/
│   │   ├── _index.md
│   │   ├── timeline.md
│   │   ├── state.md
│   │   ├── promises.md
│   │   ├── questions.md
│   │   └── scenes/
│   │       └── _index.md
│   ├── styles/
│   │   └── _index.md
│   ├── samples/
│   │   └── _index.md
│   └── issues/
│       └── _index.md
└── .creative-writing/
    ├── transactions/
    └── context/
```

The contract governs `project.md`, `story/`, `work/`, `kb/`, and
`.creative-writing/`. `project.md` contains both the versioned manifest and
the project-specific writing instructions that every supported agent reads.
Platform-specific instruction files may coexist as unmanaged files but are
not required by the story contract. Other root entries are allowed. Markdown outside the
managed roots produces an informational finding because it is not validated
or selected as context; non-Markdown files are ignored unless a managed file
references them.

Schema v1 has this explicit allowed-location map for Markdown:

- `project.md` is the single root manifest;
- generated `_index.md` files exist only at the authored directories shown in
  the canonical tree;
- chapter files are direct children of `story/chapters/`;
- work artifacts are direct children of `work/drafts/`, `work/plans/`,
  `work/reviews/`, `work/brainstorm/`, or `work/archive/`;
- KB entity and content files are direct children of `kb/characters/`,
  `kb/world/`, `kb/canon/`, `kb/styles/`, `kb/samples/`, or `kb/issues/`, with
  the fixed vocabulary file at `kb/vocab.md`; and
- continuity content consists of the fixed `timeline.md`, `state.md`,
  `promises.md`, and `questions.md` records plus direct scene entries below
  `kb/continuity/scenes/`.

Other Markdown inside a managed root is illegal placement and produces a
repairable structure finding. Every canonical file and directory must have its
expected filesystem kind. Kind checks use the directory entry itself and do
not follow symlinks.

The nearest ancestor containing `project.md` is the project root. Nested
projects are allowed. Managed links may not escape the nearest root or descend
into another nested project. A filesystem link outside the boundary is
reported as external and omitted from automatic context; it does not make the
project unusable. Mutating commands never follow it.

## Manifest and Document Identity

`project.md` is the machine-readable project manifest and human-readable
overview. Its required frontmatter is:

```yaml
---
schema-version: 1
title: Story title
language: ru
status: drafting
---
```

Project status is one of `planning`, `drafting`, `revising`, `complete`, or
`archived`. The Markdown body carries the synopsis, style rules, naming and
language conventions, knowledge boundaries, and other project-specific
instructions. This single cross-platform file avoids maintaining different
Codex and Claude instruction filenames for the same story.

Every Markdown file below `story/`, `work/`, and `kb/` has frontmatter. The
document type is inferred from its directory and its stable identifier is its
project-relative path. Frontmatter does not repeat `type` or `id`. Character
identity is the file stem below `kb/characters/`; continuity rows and
`character:<id>` context requests use that identifier, while aliases are
resolved through `kb/vocab.md`.

The supported YAML subset contains strings, integers, booleans, empty values,
flat lists of strings, and ISO dates represented as strings. Nested mappings,
anchors, tags, and multiline YAML blocks are invalid. Complex structured
records use prescribed Markdown tables instead. Because YAML is not in the
Python standard library, this is deliberately a small custom parser rather
than an incomplete claim of general YAML support; parser properties and
round-trips are tested directly.

Schema v1 deliberately does not define type-specific semantic frontmatter
contracts or required Markdown table columns. It structurally enforces the
manifest fields above, path-inferred identity and placement, supported
frontmatter syntax, `generated: true` on derived indexes, and a positive
non-boolean integer chapter `number` used only for deterministic ordering and
duplicate detection. Missing or invalid repairable metadata is a warning with
an agent-facing next action.

Fields such as chapter title or lifecycle status, draft `target` and
`base-revision`, work-artifact subject, KB entity class and `sources`, explicit
related paths, and the columns of vocab, style, issue, canon, and continuity
tables remain semantically unconstrained in schema v1. The CLI preserves
representable unknown values rather than guessing a contract. The provenance
and lifecycle descriptions later in this design express intended future
services, not additional schema-v1 validation. Any command that tightens these
field or table contracts must introduce a new schema version and migration;
it cannot silently reinterpret schema v1.

`_index.md` files are fully derived registries. They contain no unique author
knowledge. `cw reindex` reports drift, shows a diff, and rebuilds them only
with explicit application.

Managed Markdown is decoded as UTF-8; an existing UTF-8 BOM is accepted.
Logical revision hashes and exact-anchor matching normalize CRLF and CR to LF,
while recovery snapshots preserve exact bytes and writes preserve the file's
existing newline style. Mixed newline styles and Unicode/case-colliding paths
are warnings for the agent, not reasons to stop reading the project. New paths
use NFC-normalized names, forward-slash project identifiers, and avoid Windows
reserved names so the same cloud folder remains usable on Windows, macOS, and
Linux.

An older CLI encountering a newer `schema-version` performs no mutations and
asks the agent to update the bundled tool. A newer CLI may read an older schema
only through a versioned migration plan.

## Manuscript and Knowledge Lifecycles

`story/` contains the latest author-accepted manuscript. New prose and
revisions remain under `work/drafts/` until accepted. Active draft status is
one of `working`, `review`, or `ready`. `cw draft abandon` archives a rejected
draft with status `abandoned`; it does not leave inactive material among the
working drafts.

Chapter prose, including its scene breaks, lives inside the chapter file.
`kb/continuity/scenes/` contains machine-checkable scene records rather than a
second copy of scene prose. Chapter numbers are unique; duplicate numbers are
errors for ordering-dependent commands, while gaps are informational.

Draft acceptance is a transaction that:

1. verifies the target and `base-revision`;
2. creates or replaces the target manuscript file;
3. moves the working artifact into `work/archive/` with CLI-managed status
   `accepted`, the accepting transaction reference, and a collision-proof name
   containing that transaction ID; and
4. refreshes affected derived indexes.

Acceptance does not update the KB. Knowledge promotion is a separate,
author-confirmed transaction that writes settled facts to `kb/`. A manuscript
claim does not silently override KB canon, and KB canon does not silently
rewrite manuscript evidence. A disagreement remains a contradiction until
the author chooses a prose correction, a KB correction, or an explicit
retcon.

Undo remains transaction-local. Undoing draft acceptance does not cascade into
a later knowledge-promotion transaction. The resulting manuscript/KB
disagreement is surfaced through the normal contradiction workflow so the
author can decide whether the knowledge should also be reversed.

When an accepted target changes after a draft starts, the draft is stale.
`cw draft accept` refuses to overwrite the target. `cw draft rebase` previews
the patch from the recorded base to the draft and applies it to the current
target only when every hunk is unambiguous. It updates `base-revision` only
after a successful, explicitly applied rebase. Conflicts leave all files
unchanged and identify the competing fragments.

## Source Tag Policy

Source tagging applies by layer:

- in `work/brainstorm/`, skills wrap new agent suggestions in
  `<AI>...</AI>` and preserve `<hidden>...</hidden>` author-only information;
- `work/plans/` and `work/reviews/` may contain balanced source tags;
- prose bodies in `work/drafts/` do not use `<AI>` wrappers; the draft layer
  and explicit acceptance transaction provide the confirmation boundary;
- prose bodies in `story/` contain neither `<AI>` nor `<hidden>`;
- KB documents cannot contain unresolved `<AI>` suggestions, while
  `<hidden>` is allowed for confirmed knowledge with an explicit visibility
  boundary.

All managed text is checked for balanced, properly nested tags and tags that
are forbidden in the destination layer. A mechanical checker cannot infer
that untagged prose was an agent suggestion; enforcing tags on newly generated
brainstorm material remains a skill responsibility. Draft acceptance fails if
the draft contains unresolved `<hidden>` material because choosing where that
content belongs is semantic. Balanced `<AI>` wrappers are removed around their
content in the acceptance preview, so source markup alone does not make the
author repair a file manually.

## Runtime Architecture

The implementation is a modular CLI owned by the new `project-maintenance`
skill. It supports Python 3.10 or newer on Windows, macOS, and Linux and uses
the standard library only. One entrypoint named
`cw` delegates to focused internal modules:

```text
command parsing
    → project discovery and model loading
        → schema and check registry
        → draft lifecycle
        → context planning
        → migration planning
        → transaction engine
```

Skills communicate with the CLI through commands, previews, and structured
findings. They do not duplicate frontmatter parsing, project discovery,
hashing, or file mutation logic.

The current `story-memory/resources/continuity_check.py` and
`story-review/resources/prose-critique/analyze.py` behavior is absorbed into
`cw check continuity` and `cw check prose`, including the existing Russian and
English prose analysis. After parity tests pass, the standalone entrypoints
are retired so two implementations cannot drift.

Read-only services inspect the project directly. Every mutating service,
including initialization, reindexing, migration, draft operations, exact
edits, and undo, routes through the same transaction engine.

Initialization is the bootstrap case. For an absent target it builds the
complete project in a temporary sibling directory, writes the initial
committed transaction record inside that tree, and renames the tree into
place. For an existing ordinary folder it creates only missing scaffold paths
and leaves every unknown file untouched; if managed paths already contain
content, it switches to migration planning rather than overwriting. The
bootstrap transaction is marked non-undoable so `cw undo` cannot delete the
project that contains its own journal.

## Command Surface

The initial command surface is:

```text
cw init
cw check [structure|links|kb|continuity|drafts|prose|journal|all]
cw doctor
cw context [draft|chapter|kb] <path> [--as trusted|reader|character:<id>]
cw reindex

cw migrate --plan
cw migrate --apply <plan.json>

cw draft create
cw draft set-status
cw draft rebase
cw draft accept
cw draft abandon

cw edit replace
cw edit insert-before
cw edit insert-after
cw edit delete
cw edit apply <operations.json>

cw history
cw history show <transaction-id>
cw undo <transaction-id>

cw cli-doctor
cw clean-context
```

`cw draft set-status <draft> <working|review|ready>` is the safe journaled
way for an agent to advance or return an active draft. The author may still
edit a draft file directly; the command exists so agent workflows do not need
to rewrite lifecycle frontmatter through a generic text primitive.

Mutating commands produce a preview by default. Non-interactive application
requires an explicit `--apply`; no workflow depends on an interactive prompt.
Large anchors and replacement text are passed through files rather than shell
arguments so punctuation and line breaks remain exact.

Read-only commands, previews, conflicts, and mutation results all support
`--format json`; skills never need to parse human prose. Mutation conflicts
return exit status `1`, while inability to execute returns `2`, matching the
check-command distinction.

Simple edit commands create one-file transactions. `cw edit apply` consumes a
JSON operations plan for an all-or-nothing multi-file change. Supported
operations use exact old text or exact before/after anchors. Zero matches or
multiple matches are conflicts by default. An operations plan may state an
explicit `expect-count` or `all: true` for a deliberate repeated replacement;
the observed count must still match before anything changes. Line numbers and
injected block identifiers are not editing primitives.

Generic edit primitives operate on document bodies. They refuse generated
`_index.md`, `.creative-writing/`, and CLI-managed lifecycle frontmatter such
as `base-revision` and status transitions. Domain commands own those changes.
A batch plan may use a typed `frontmatter-set` operation for ordinary
user-editable fields, subject to the artifact schema. Direct author edits
remain allowed; the next check or lifecycle command reads the current file and
repairs metadata only when doing so is unambiguous.

## Transaction and Recovery Model

The transaction engine follows this protocol:

1. read every target and validate paths, hashes, and exact anchors;
2. calculate the complete change set and preview;
3. write an append-only transaction manifest with state `prepared`;
4. persist exact before and after bytes in content-addressed snapshots;
5. write each new target to a temporary sibling;
6. recheck target hashes, mark the manifest `applying`, and record each
   completed replacement;
7. replace targets and mark the manifest `committed`; and
8. restore already replaced targets if an in-process failure interrupts the
   commit sequence.

Multiple filesystem replacements cannot be physically atomic. The protocol
provides logical atomicity and crash recovery. `cw doctor` detects a manifest
left in `prepared` or `applying`. Version 1 has one recovery policy: restore
all targets from before-snapshots and mark the transaction `rolled-back`.
Doctor reports which replacements had occurred; it never attempts a competing
roll-forward path.

Cloud synchronization is not treated as a distributed lock. Unique
transaction IDs avoid journal-name collisions, and optimistic hash checks
detect external edits immediately before replacement. The author or another
agent's direct changes always win over an unsafe automated overwrite. A narrow
time-of-check/time-of-use race remains between the last hash check and file
replacement; the single-writer assumption and exact recovery journal make it
detectable, but version 1 does not claim distributed concurrency safety.

Mutating commands resolve every target without following symlinks and refuse
paths outside the nearest project, paths inside another nested project, and
targets under `.creative-writing/`. Read-only checks may inspect a symlink
enough to report it, but never use it as a mutation or automatic-context path.

Each transaction stores its command, timestamp, paths, preconditions, before
and after hashes, content-addressed snapshots, and a unified diff for review.
The journal is append-only under `.creative-writing/transactions/` and works
without Git. Git may additionally version or ignore it.

`cw undo` verifies that every current target matches the selected
transaction's after-state, then creates and applies a new inverse transaction.
It never deletes or rewrites history. Diverged targets produce a conflict and
remain untouched. Journal pruning is never automatic; a future explicit
maintenance command may be designed separately if storage becomes material.

## Check Registry and Findings

`cw check all` runs independent checkers:

- `structure`: scaffold, schema version, frontmatter, document placement, and
  valid statuses;
- `links`: relative target existence, target class, orphan pages, and derived
  registry drift;
- `kb`: required sources, vocabulary collisions, live references to archived
  records, and source-tag policy;
- `continuity`: timeline anchors, character state, knowledge order, deaths,
  promises, questions, and scene records;
- `drafts`: target validity, base revisions, lifecycle status, staleness, and
  source-tag policy;
- `prose`: Markdown integrity, word counts, and the existing deterministic
  prose metrics without literary conclusions; and
- `journal`: manifests, snapshot hashes, and incomplete transactions.

Context snapshot staleness is included in doctor output and
`cw clean-context`; it does not fail ordinary project checks.

Deterministic checks report only conclusions supported by explicit structure.
A death recorded in structured state can conflict mechanically with a later
scene cast. A metaphor that may conflict with a magic rule requires semantic
review by an agent.

Every finding has a stable code, severity, path, optional line, explanation,
and safe next action. Human-readable text is the default and `--format json`
emits the same data for skills and CI.

Exit status is `0` when no errors are found, `1` when the project was checked
and errors were found, and `2` when the CLI could not execute the check.
Warnings do not fail a command unless `--strict` is supplied. Strict mode
returns `1`, does not rewrite warning severities in JSON, and adds a summary
flag showing that warnings caused the nonzero result.

Most structure and metadata drift is a warning because the primary consumer
is an agent that can repair it. Errors are reserved for cases where a specific
operation cannot be interpreted safely, such as duplicate chapter numbers for
neighbor selection or a corrupt transaction required for undo. Check failures
never prevent unrelated reading, research, or semantic review.

`cw doctor` is read-only. It runs all checks and groups findings into a
prioritized repair plan with exact follow-up commands. Automatic repairs are
separate previewed, journaled commands; semantic contradictions never receive
automatic fixes.

## Context Planning and Redaction

`cw context` returns `required`, `suggested`, and `unresolved` paths based on
explicit document references, neighboring chapters, plans, continuity state,
vocabulary, and active issues. It reduces missed dependencies without
pretending to infer every semantically relevant document. Its kinds are
`draft`, `chapter`, and `kb`; `--as trusted` is the default, with `reader` and
`character:<id>` available for restricted snapshots. Text and JSON formats are
both supported.

Trusted roles receive source paths. Restricted roles may request a derived
snapshot under `.creative-writing/context/`:

- `reader` removes explicit `<hidden>...</hidden>` blocks;
- `character:<id>` also filters structured knowledge rows belonging to other
  characters.

Each snapshot has a manifest containing its source paths and hashes. It is
read-only derived data, becomes stale when a source hash changes, never enters
the transaction journal or KB, and can be removed with `cw clean-context`.
The first version performs no semantic spoiler detection. When ordinary
unmarked prose may exceed a requested knowledge boundary, the CLI reports
that the boundary cannot be guaranteed.

## Migration

Migration is always planned before it is applied.

`cw migrate --plan` recognizes the previous Layout A and Layout B roles and
emits a versioned JSON mapping. The fixed role mappings are:

| Previous source | Canonical destination |
|---|---|
| Layout A `chapters/` | `story/chapters/` |
| Layout A `drafts/` | `work/drafts/` |
| Layout A `characters/` | `kb/characters/` |
| Layout A `worldbuilding/` | `kb/world/` |
| Layout A samples and style references | `kb/samples/` and `kb/styles/` |
| Layout A named continuity records under `plot/` | `kb/continuity/` |
| Other Layout A `plot/` material | `work/plans/` |
| Layout B prose directly under `story/` | `story/chapters/` |
| Layout B `work/outline/` | `work/plans/` |
| Layout B `work/critique-reports/` | `work/reviews/` |
| Layout B `kb/samples/` and `kb/styles/` | same canonical roles |
| Layout B named continuity records directly under `kb/` | `kb/continuity/` |
| Layout B `kb/timeline/` with multiple files | agent-reviewed merge into `kb/continuity/timeline.md` |
| Domain `vocab.md` files | agent-reviewed merge into `kb/vocab.md` |

Named continuity records include `timeline.md`, `state.md`, `promises.md`,
`questions.md`, and `scenes/`. Multiple competing timelines, mixed layouts,
and files whose role cannot be inferred remain unresolved. The CLI never
decides whether ambiguous material is canon, a draft, or brainstorm output.
Existing creative-writing instructions in platform-specific files are read by
the migration skill and proposed for the body of `project.md`; they are never
deleted or merged mechanically.

The plan contains `plan-version`, source and target schema versions, operations,
unresolved entries, and a hash of its canonical content. Editing a plan
invalidates that hash and requires a new preview. `cw migrate --apply` schema-
validates the plan, requires no unresolved entries, and accepts only the exact
hash last previewed by the caller. This proves plan integrity, not human
approval: the muse still obtains author confirmation in dialogue and then runs
the apply command. No approval token or technical ceremony is exposed to the
author.

Application previews the full diff and applies it as one recoverable
transaction. Original paths remain recoverable until the transaction commits;
undo restores the old structure. All mechanical checks run afterward, with
repairable drift reported to the agent rather than treated as migration
failure.

## Skill Integration

Three authored skills are added:

- `project-maintenance` owns the project contract, bundled CLI, command
  reference, and deterministic maintenance workflows;
- `project-doctor` converts raw findings into a prioritized agent repair
  workflow without mutating the project; and
- `cli-doctor` verifies Python, locates the bundled entrypoint, tests direct
  execution, and helps configure an optional `cw` launcher.

Existing authored skills change as follows:

- `project-setup` creates only the canonical scaffold and guides approved
  migrations;
- `kb-management` runs mechanical KB checks before semantic KB audits and
  confirmed fixes;
- `story-review` checks working drafts against prepared context;
- `story-memory` owns the continuity semantics consumed by the checker;
- `targeted-editing` selects the literary change level and uses exact-anchor
  or batch transactions;
- `creative-writing-muse` owns confirmation boundaries for draft acceptance,
  knowledge promotion, and retcons.

`cli-doctor` does not edit `.zshrc`, `.bashrc`, or `PATH` without separate
explicit approval. The agent first uses direct invocation without surfacing
setup work to the author, then offers a
user-scoped launcher such as `~/.local/bin/cw` with a preview. It never copies
the CLI into a story project. Because the runtime has no third-party
dependencies, its environment checks are limited to Python 3.10 or newer,
entrypoint discovery, permissions, version agreement, and a smoke test.

## Testing

The implementation requires:

- unit tests for the frontmatter subset, project discovery, path containment,
  normalized logical hashes, exact-byte snapshots, anchors, diff generation,
  and schemas;
- valid-minimal, populated, and intentionally broken fixture projects;
- golden text and JSON output for every finding code;
- injected failures at every transaction phase and recovery verification;
- conflicts caused by manual edits, stale drafts, ambiguous anchors, and
  cloud-style duplicate files;
- Windows-reserved names, case and Unicode-normalization collisions, newline
  preservation, symlinks, and nested-project boundaries;
- apply/undo round trips, including multi-file batches;
- migration fixtures for Layout A, Layout B, mixed projects, plan hash changes,
  and continuity-root relocation;
- context tests proving explicit hidden-block removal and character knowledge
  filtering;
- behavioral tests proving that doctor does not repair, review starts from
  the mechanical floor, and draft acceptance does not update KB; and
- KB provenance tests proving that work artifacts alone cannot become durable
  sources without author confirmation; and
- the repository's complete distribution, generation, archive, and release
  checks.

## Distribution and Rollout

The canonical implementation lives under
`plugins/creative-writing-skills/skills/project-maintenance/`. The Python
entrypoint, modules, and schema resources are copied into generated `cw/` by
the existing distribution generator. Here, **the `cw` CLI** means the command;
**the `cw/` tree** means the committed Claude/ZCode distribution. The
`project-maintenance` Claude.ai archive contains the complete fallback CLI.

The story contract deliberately uses platform-neutral `project.md` rather
than requiring a runtime `AGENTS.md`. This avoids the existing generator's
Codex-to-Claude filename transformation and vocabulary ban while giving every
platform one file to read. The repository's contributor `AGENTS.md` remains
unchanged and outside the story-project contract.

The canonical skill inventory grows from 26 to 29. Distribution configuration,
validators, plugin metadata, README documentation, generated Claude and ZCode
trees, and deterministic archives must change through the canonical generation
flow; generated output is never hand-edited. The implementation plan must
update both configured inventories and existing hard-coded inventory/count
assertions in distribution tests.

Implementation proceeds in dependency order:

1. schema v1, scaffold, parser, project model, and read-only checks;
2. transaction engine, exact-anchor edits, history, and undo;
3. draft creation, rebase, acceptance, and migration;
4. context planner, doctor commands, and the three new skills; and
5. integration of existing skills, fixtures, documentation, and generated
   distributions.

Each stage leaves a runnable, tested CLI. Commands are documented as available
only after their implementation and distribution tests pass.

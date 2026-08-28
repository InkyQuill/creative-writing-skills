# Story Project Contract and CLI Design

**Status:** Approved in design review on 2026-08-28

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

## Canonical Project Shape

`cw init` creates the complete authored scaffold at once. Every managed
directory has a generated `_index.md`, including empty directories, so the
shape survives version control and agents never need to choose a location.

```text
project/
├── project.md
├── AGENTS.md
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
│   └── issues/
│       └── _index.md
└── .creative-writing/
    ├── transactions/
    └── context/
```

The contract governs `project.md`, `AGENTS.md`, `story/`, `work/`, `kb/`, and
`.creative-writing/`. Other root entries are allowed. Markdown outside the
managed roots produces an informational finding because it is not validated
or selected as context; non-Markdown files are ignored unless a managed file
references them.

The nearest ancestor containing `project.md` is the project root. Nested
projects are allowed, and a command never crosses from the nearest project
into its parent project.

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
`archived`. `AGENTS.md` contains project-specific instructions, style rules,
and confirmation boundaries; it is not a second manifest.

Every Markdown file below `story/`, `work/`, and `kb/` has frontmatter. The
document type is inferred from its directory and its stable identifier is its
project-relative path. Frontmatter does not repeat `type` or `id`.

The supported YAML subset contains strings, integers, booleans, empty values,
flat lists of strings, and ISO dates represented as strings. Nested mappings,
anchors, tags, and multiline YAML blocks are invalid. Complex structured
records use prescribed Markdown tables instead.

Required fields vary by artifact type:

- manuscript chapters have `number`, `title`, and `status`, with optional
  explicit references for POV, characters, locations, and arcs;
- working drafts have `target`, `base-revision`, and `status`;
- plans, reviews, and brainstorm artifacts have `subject`, `status`, and
  explicit related paths where applicable;
- KB entity pages use the fields for their entity class and a flat `sources`
  list;
- vocab, styles, issues, canon summaries, and continuity records each have a
  small type-specific schema.

`base-revision` is absent when a draft creates a new target. Otherwise it is a
CLI-managed SHA-256 identifier for the accepted target on which the draft is
based. Authors may edit Markdown bodies freely and never need to update a
hash by hand.

`_index.md` files are fully derived registries. They contain no unique author
knowledge. `cw reindex` reports drift, shows a diff, and rebuilds them only
with explicit application.

## Manuscript and Knowledge Lifecycles

`story/` contains the latest author-accepted manuscript. New prose and
revisions remain under `work/drafts/` until accepted. Active draft status is
one of `working`, `review`, `ready`, or `abandoned`.

Draft acceptance is a transaction that:

1. verifies the target and `base-revision`;
2. creates or replaces the target manuscript file;
3. moves the working artifact into `work/archive/` with CLI-managed status
   `accepted` and the accepting transaction reference; and
4. refreshes affected derived indexes.

Acceptance does not update the KB. Knowledge promotion is a separate,
author-confirmed transaction that writes settled facts to `kb/`. A manuscript
claim does not silently override KB canon, and KB canon does not silently
rewrite manuscript evidence. A disagreement remains a contradiction until
the author chooses a prose correction, a KB correction, or an explicit
retcon.

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
the resulting manuscript would violate the manuscript policy.

## Runtime Architecture

The implementation is a modular CLI owned by the new `project-maintenance`
skill. It uses Python 3 and the standard library only. One entrypoint named
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

Read-only services inspect the project directly. Every mutating service,
including initialization, reindexing, migration, draft operations, exact
edits, and undo, routes through the same transaction engine.

Initialization is the bootstrap case: it builds the complete project in a
temporary sibling directory, writes the initial committed transaction record
inside that tree, and renames the tree to the requested absent target. It
refuses to initialize over an existing nonempty target; existing projects use
the migration workflow.

## Command Surface

The initial command surface is:

```text
cw init
cw check [structure|links|kb|continuity|drafts|prose|journal|all]
cw doctor
cw context <kind> <path>
cw reindex

cw migrate --plan
cw migrate --apply <plan.json>

cw draft create
cw draft rebase
cw draft accept

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

Mutating commands produce a preview by default. Non-interactive application
requires an explicit `--apply`; no workflow depends on an interactive prompt.
Large anchors and replacement text are passed through files rather than shell
arguments so punctuation and line breaks remain exact.

Simple edit commands create one-file transactions. `cw edit apply` consumes a
JSON operations plan for an all-or-nothing multi-file change. Supported
operations use exact old text or exact before/after anchors. Zero matches or
multiple matches are conflicts, not guesses. Line numbers and injected block
identifiers are not editing primitives.

## Transaction and Recovery Model

The transaction engine follows this protocol:

1. read every target and validate paths, hashes, and exact anchors;
2. calculate the complete change set and preview;
3. write an append-only transaction manifest with state `prepared`;
4. persist exact before and after bytes in content-addressed snapshots;
5. write each new target to a temporary sibling;
6. recheck target hashes immediately before replacement;
7. replace targets and mark the manifest `committed`; and
8. restore already replaced targets if an in-process failure interrupts the
   commit sequence.

Multiple filesystem replacements cannot be physically atomic. The protocol
provides logical atomicity and crash recovery. `cw doctor` detects a manifest
left in `prepared` or applying state and gives a deterministic recovery action.

Cloud synchronization is not treated as a distributed lock. Unique
transaction IDs avoid journal-name collisions, and optimistic hash checks
detect external edits immediately before replacement. The author or another
agent's direct changes always win over an unsafe automated overwrite.

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

Deterministic checks report only conclusions supported by explicit structure.
A death recorded in structured state can conflict mechanically with a later
scene cast. A metaphor that may conflict with a magic rule requires semantic
review by an agent.

Every finding has a stable code, severity, path, optional line, explanation,
and safe next action. Human-readable text is the default and `--format json`
emits the same data for skills and CI.

Exit status is `0` when no errors are found, `1` when the project was checked
and errors were found, and `2` when the CLI could not execute the check.
Warnings do not fail a command unless `--strict` is supplied.

`cw doctor` is read-only. It runs all checks and groups findings into a
prioritized repair plan with exact follow-up commands. Automatic repairs are
separate previewed, journaled commands; semantic contradictions never receive
automatic fixes.

## Context Planning and Redaction

`cw context` returns `required`, `suggested`, and `unresolved` paths based on
explicit document references, neighboring chapters, plans, continuity state,
vocabulary, and active issues. It reduces missed dependencies without
pretending to infer every semantically relevant document.

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
emits a JSON mapping. Mechanical matches such as `chapters/` to
`story/chapters/` may be proposed automatically. The CLI never decides whether
ambiguous material is canon, a draft, or brainstorm output.

An agent resolves every ambiguous entry with the author. `cw migrate --apply`
accepts only a complete approved plan, previews the full diff, and applies it
as one recoverable transaction. Original paths remain recoverable until the
transaction commits; undo restores the old structure. All mechanical checks
run after application.

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
explicit approval. It prefers direct invocation first, then offers a
user-scoped launcher such as `~/.local/bin/cw` with a preview. It never copies
the CLI into a story project. Because the runtime has no third-party
dependencies, its environment checks are limited to a compatible Python 3,
entrypoint discovery, permissions, version agreement, and a smoke test.

## Testing

The implementation requires:

- unit tests for the frontmatter subset, project discovery, path containment,
  hashes, anchors, diff generation, and schemas;
- valid-minimal, populated, and intentionally broken fixture projects;
- golden text and JSON output for every finding code;
- injected failures at every transaction phase and recovery verification;
- conflicts caused by manual edits, stale drafts, ambiguous anchors, and
  cloud-style duplicate files;
- apply/undo round trips, including multi-file batches;
- migration fixtures for Layout A, Layout B, and mixed projects;
- context tests proving explicit hidden-block removal and character knowledge
  filtering;
- behavioral tests proving that doctor does not repair, review starts from
  the mechanical floor, and draft acceptance does not update KB; and
- the repository's complete distribution, generation, archive, and release
  checks.

## Distribution and Rollout

The canonical implementation lives under
`plugins/creative-writing-skills/skills/project-maintenance/`. The Python
entrypoint, modules, and schema resources are copied into generated `cw/` by
the existing distribution generator. The `project-maintenance` Claude.ai
archive contains the complete fallback CLI.

The canonical skill inventory grows from 26 to 29. Distribution configuration,
validators, plugin metadata, README documentation, generated Claude and ZCode
trees, and deterministic archives must change through the canonical generation
flow; generated output is never hand-edited.

Implementation proceeds in dependency order:

1. schema v1, scaffold, parser, project model, and read-only checks;
2. transaction engine, exact-anchor edits, history, and undo;
3. draft creation, rebase, acceptance, and migration;
4. context planner, doctor commands, and the three new skills; and
5. integration of existing skills, fixtures, documentation, and generated
   distributions.

Each stage leaves a runnable, tested CLI. Commands are documented as available
only after their implementation and distribution tests pass.

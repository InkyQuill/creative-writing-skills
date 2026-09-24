# Project Contract

For independent tools that need a stable, versioned description of discovery
and document roles, use the [external project contract](external-project-contract.md)
and its executable compatibility examples. Those structural roles do not decide
authority or permission.
For author control over agent assistance, edit scope, and canon promotion, use
`$project-bootstrap`'s `author-workflow-contract.md`. Its optional
`cws.md` is human-readable guidance, not a CLI discovery or schema requirement.

The nearest ancestor containing `project.md` is the project root. Nested
projects are independent boundaries. The default managed roots are
`project.md`, `story/`, `work/`, `kb/`, and `.creative-writing/`. Role folders
selected in `.cws-layout.json` or discovered from populated folders are also
managed for applicable checks and existing generated indexes, even when they
sit outside those default roots.

Other root entries are allowed. Leave unknown files untouched: initialization,
migration, repair, and reindexing must preserve them. Markdown outside managed
roots may produce an informational finding, but Git is optional and the CLI
does not require a repository to provide transaction history or undo.

Legacy `inspiration/` is a recognized author-owned migration corpus, not a
managed Markdown root. Migration inventories every regular file below it and
preserves the complete relative tree and exact bytes in place. This includes
Pocket Editor `.pocket-editor.json` binders and `*.review.json` sidecars,
images, office documents, RTF, hidden metadata, and unknown service files. The
CLI does not parse, reindex, rename, or infer meaning from this material.
Links, special filesystem entries, and nested project boundaries are reported
for review and never followed.

## Manifest language and prose profile

Schema v1 requires a non-empty `language` tag and accepts any project language.
Bundled resources and checks resolve the normalized primary tag, so `ru-RU`
uses `ru` support and `en-GB` uses `en` support without constraining future
languages.

`prose-profile` is optional and defaults to `general`, which adds no profile
overlay. When present it is a lower-case slug with letters, numbers, and
internal hyphens. Bundled selectors are `general`, `light-novel`,
`classical-literary`, and `literary-fiction`; preserve valid custom selectors.
Existing schema-v1 projects need no migration only to add the default.

## Protected paths and metadata

Generic edits must not modify:

- generated `_index.md` files;
- `.creative-writing/`, including its transaction journal and context cache;
- CLI-managed draft lifecycle metadata such as `base-revision` and status.

Use domain commands such as `reindex`, `draft set-status`, `draft rebase`,
`draft accept`, and `recover` for those changes. Paths outside the nearest
project, paths inside another nested project, and linked mutation targets are
also protected from automatic writes.

Direct author prose edits remain valid input. The agent owns mechanical
maintenance: hashes, tags, indexes, base revisions, repair-command selection
and execution, and runtime setup. The CLI performs only the deterministic
mechanics requested by the agent. Never ask a nontechnical author to edit an
index, calculate a hash, copy a tag, or maintain a base revision.

## Manuscript roles and reading order

`.cws-layout.json` stores the selected project-relative folder for each role.
Read it before choosing chapter, side-story, draft, plan, review, archive, or
knowledge folders. Existing projects without this file are discovered from
populated folders; record unambiguous choices without moving author files.
The paths below are defaults for the full scaffold, not required author paths.

Numbered main chapters are direct Markdown children of the selected chapters
folder (`cw get-folder chapters`) and
use unique positive integer `number` metadata. Accepted bonus prose is a direct
Markdown child of the selected side-stories folder (`cw get-folder
side-stories`); it uses required `after` metadata that
names an accepted chapter or side story, plus an optional lower-case `subtype`
such as `omake` or `interlude`. Side stories do not take chapter numbers.

The aggregate reading order starts with chapters ordered by `number`, then
places each side story after its durable `after` anchor. Multiple
side stories sharing an anchor are ordered by portable path identity. Missing
or cyclic anchors are structural errors. Both manuscript roles are valid draft
targets, accepted prose inputs, prose-check inputs, and `context chapter`
subjects. Their separate generated indexes remain derived state.

Contract drift that can be repaired without guessing is an agent task. An
unknown schema, unsafe path, changed precondition, ambiguous anchor, or
unrecoverable journal requires a conflict finding and no write. These
mechanical constraints do not decide literary meaning.


## Schema v2: literary translation

Schema v1 remains supported unchanged. Enabling translation uses schema v2 with
`project-kind: authoring` or `translation`, `work-kind: book` or `series`, and
`translation-enabled: true`. Unknown schema versions are not mutation targets.
A v2 author project keeps `story/`, `work/`, `kb/` and its manuscript-language
meaning. In a standalone translation project `language` describes working
communication/documentation, not all text; no author manuscript scaffold is
required. Each edition and direction declares its own language.

Additional managed roots are `sources/` and `translations/`. Shared identities
live in `kb/entities/`; explicit comparisons in `kb/source-comparisons/`. Opaque
original files, including Markdown, are excluded from managed text walking and
generic edits. All mutations preserve nested boundaries, unknown files and
recoverability. Per-direction indexes and the source index are derived.

An edition at `sources/<edition>/edition.md` declares `edition-id`, `language`,
`edition-role` (original or translation), `revision-label` and `coverage` (volume
IDs). Supplied files live in `originals/` and working source units in `text/`.
For a series, both directories live under `volumes/<volume>/`; for a book they
are directly under the edition. Do not mix these layouts. A unit has `unit-id`, positive `order` within its volume,
optional `volume-id`, and `original-path` plus `original-sha256`, or a
`manuscript-path` reference to existing author prose. Unit identities are unique
within an edition and survive file renames. A different supplied original
revision uses a new edition; extraction corrections retain the unit identity.

A direction at `translations/<direction>/translation.md` declares
`direction-id`, target `language`, `primary-edition`, `auxiliary-editions`,
`coverage` and optional `inheritance` categories. Its body contains literary
strategy. Several directions/editions may share a language. A series permits
`volumes/<volume>/settings.md` to override explicit source/inheritance fields;
missing fields inherit, empty fields clear lists. Do not fall back from a
missing primary or silently use an unavailable auxiliary. A translation edition
may be primary, but preserve indirect provenance.

Direction memory uses `memory/terms/`, `memory/voices/`, `memory/decisions/` and
`memory/style.md`. Each record has `record-id`, `subject`, `status`, `evidence`
and optional `scope-volumes`, `scope-units`, `scope-entities`,
`scope-relationships`, `supersedes`. Scope dimensions combine with AND; list
entries within a dimension combine with OR. Empty scope is unrestricted.
Unit references use `edition:unit`. Statuses are `observed`, `proposed`,
`accepted`, `superseded`. Actual instructions and examples remain in the body.
An explicit narrower exception leaves the general rule active elsewhere;
same-scope replacement supersedes the predecessor. Conflicts and cycles are
findings, not permission to choose a rule silently.

Alignment records carry `alignment-id`, `source-units`, `reference-units`,
`status` (observed/accepted), and `relation` (equivalent/split/merge/reordered/
omitted). Omission needs a body explanation and no target units. No equal
paragraph or chapter count is required. Shared entities use `entity-id` and
evidence; they do not impose a rendering on all directions.

A direction's `drafts/`, `reviews/`, `accepted/` directories are direct children
for a book, or under `volumes/<volume>/` for a series. A draft stores
`direction-id`, `draft-id`, `source-units`, `packet-transaction`, `base-revision`
and lifecycle status (`draft`, `reviewed`, `accepted`). The journal transaction
retains its exact context packet, source provenance and dependency hashes.
Review records a prose hash; later prose edits require a new review. Acceptance
checks the input snapshot and existing accepted base. It never changes another
direction or automatically accepts memory proposals.

Acceptance and freshness are separate: an accepted text can need review after a
source or memory change. Adding a new rule also invalidates prior contexts.
Rebuild and review a draft to revise accepted prose. Do not manually maintain
snapshots, hashes, protected identifiers or generated indexes. Direct user edits
remain inputs and must be preserved. Technical checks cannot certify semantic
completeness or literary quality.

Source import assigns the next order within a volume unless the request provides
an explicit unique positive order. Import units in reading order or supply it;
context neighbors use this order, never alphabetic identity.

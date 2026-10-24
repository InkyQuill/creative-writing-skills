# Layout-independent story projects

Status: implemented; see the implementation plan completion record for validation limits.

Baseline: `origin/main` at `a489953`, plugin 0.12.0, fetched 2026-10-24.

## Requirement

The skills must adapt to any author layout. No required `kb/`, `story/`,
`work/`, manifest, generated index, or migration before useful writing work.
Flat files, shared folders, nested volumes, custom names and existing metadata
are valid. The CLI currently processes Markdown; other author formats remain
valid source material for suitable readers, without claiming CLI coverage.

The author suggested tagging folders with purposes such as `kb` and `drafts`.
Adopt this as the organizing model, with optional file overrides for mixed or
fully flat projects. Tags describe purpose, never approval or truth.

## Verified problems in 0.12.0

Paths below are relative to
`plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/`.

| Component | Current restriction | Required correction |
| --- | --- | --- |
| `checks/kb.py` | Only selected literal `kb/` and `story/` paths resolve; even side stories fail | Resolve references independently of tags and folder names |
| `layout.py` | One directory per role; rejects `.` and shared directories | Inherited tags, file exceptions, multiple matches |
| `project.py` | Requires `project.md`; inventory skips root-level files | Explicit workspace roots and scope-aware discovery |
| `schema.py`, `checks/structure.py` | Path implies document type; recommends relocating files | Optional legacy schema adapter; no layout repair demands |
| `context.py`, `indexes.py`, `checks/*`, `drafts.py` | Separate, inconsistent role/path inference | One shared classification service |
| `documents.py`, `edits.py` | Small YAML subset can block reading/editing otherwise valid author files | Preserve opaque metadata; constrain only operations needing its interpretation |
| Setup, maintenance, KB, story-memory skills | Mandatory scaffold/CLI assumptions despite adaptation promises | Layout-independent author workflow, optional managed features |

## Tag contract

Extend the existing optional `.cws-layout.json` to version 2. Do not introduce
another required project file. Existing version-1 configuration loads through
a compatibility adapter and is never rewritten by reading it.

```json
{
  "version": 2,
  "bindings": [
    {"path": ".", "kind": "directory", "tags": ["drafts"]},
    {"path": "notes", "kind": "directory", "tags": ["kb"], "remove": ["drafts"]},
    {"path": "world.md", "kind": "file", "tags": ["kb", "world"], "remove": ["drafts"]},
    {"path": "chapter-01.md", "kind": "file", "tags": ["chapters"], "remove": ["drafts"]}
  ],
  "destinations": {"reviews": "."}
}
```

Store one binding per `(kind, path)` and reject duplicate bindings on input.

- Directory bindings inherit recursively, shallowest first; exact file bindings
  apply last. Within a binding, remove inherited tags, then add tags. Reject a
  tag appearing in both sets. Canonicalize paths before checking duplicates.
- Multiple folders can share tags; one folder/file can have several tags.
  Root `.` is legal for directory bindings. No globs in version 2: exact paths
  plus recursive inheritance cover the initial requirement without a new DSL.
- Built-in tags: `kb`, `chapters`, `side-stories`, `drafts`, `characters`,
  `world`, `canon`, `styles`, `samples`, `issues`, `continuity`, `vocabulary`,
  `plans`, `brainstorm`, `reviews`, `archive`. Custom nonempty tags are retained;
  unknown tags do not trigger a checker or become an error.
- `characters`, `world`, `canon`, `styles`, `samples`, `issues`, `continuity`
  and `vocabulary` select knowledge operations even without a separate `kb`
  tag. They do not imply accepted canon. An `archive` tag excludes a document
  from current-context defaults but does not make its path unresolvable.
- Explicit tags supersede legacy inference. Conflicting purposes are reported
  to operations that need a single purpose; iteration order never selects a
  winner. Read/link checks can still proceed on those files.
- Legacy folder inference applies only to existing schema-v1/v2 managed
  projects or version-1 layout configuration. A manifestless ordinary folder
  is not opted into legacy rules because it happens to be named `story` or
  `work`. Version-2 bindings are authoritative: removed tags must not reappear
  through a legacy fallback. Upgrading a v1 layout explicitly materializes
  existing role choices as bindings in the reviewed configuration diff.
- `destinations` optionally selects an output folder for a purpose. It does
  not classify its contents. An explicit command output path wins. Otherwise
  use a configured destination or a unique compatible directory binding;
  if neither exists, request a concrete output path only when writing needs it.
- No tag file is needed for reading a named document or ordinary creative work.
  Tags give scripts durable routing information; they are not an admission test.

Proposed commands: `cw layout tag PATH --kind directory|file --add TAG`
and repeatable `--add`/`--remove`; `cw layout destination TAG PATH`;
`cw layout inspect [PATH] --format json`. Mutations retain preview/`--apply`
and undo. `--remove` records inheritance exclusions, not source-file deletion.
The old `layout --set ROLE=FOLDER` and `get-folder` remain compatibility APIs;
unresolved/multiple folders return an actionable result, not an invented path.

## Workspace and content boundaries

Resolve an explicit CLI `--root` first, otherwise the nearest supported
`project.md` or `.cws-layout.json` marker; a command's explicit directory is
the fallback root. For a standalone file use its parent. Commands without a
path use the current directory. Never walk up to a repository/home directory
merely to broaden the search. Existing managed-project discovery remains
available to commands explicitly needing that contract.

Read-only commands create no scaffold, layout, indexes, journal or cache.
Directory checks inventory Markdown inside that root; file checks inventory
only that file and resolve referenced targets as needed. Exclude hidden/service
directories and nested marked projects by default, and do not follow symlinks.
Explicit read selection may include an ordinary hidden author file inside the
root, but never silently include journal/cache internals. Keep scope visible in
JSON and text reports. Unsupported formats/metadata are reported as unassessed.

Inventory, semantic tags and automation lifecycle are separate. A `drafts` tag
does not opt every document into the CLI's target/base-revision state machine.
Legacy managed drafts remain recognizable through their existing lifecycle
metadata; ordinary draft files remain readable without adding it.

Keep the strict managed frontmatter parser for managed lifecycle operations.
Add a read envelope that preserves raw bytes and exposes unavailable metadata
without rewriting it. Body checks may continue when the body boundary is known;
unterminated frontmatter makes that boundary unknown. Exact text edits can use
explicit byte-preserving anchors; metadata-dependent mutations fail specifically
when they cannot safely interpret the requested field.

## Provenance and author authority

Replace the single durable/invalid decision with separate facts:

- Reference kind: local file, URL, transaction receipt, or descriptive citation.
- Resolution: resolved, missing, unsafe, unverified, or malformed.
- Author authority: unknown, provisional, accepted, or archived, using explicit
  applicable evidence; never infer acceptance from a folder/tag/URL/receipt.

Any safe existing project-relative file can be a reference, including drafts,
flat files, and non-Markdown source material. A binary reference can resolve
while its content remains unassessed. A known archived source resolves but is
flagged when relied upon as current evidence. Missing explicit file references
still produce findings. No network requests are needed to recognize a URL;
report it as unverified rather than declaring the remote page exists.

Keep existing project-relative `sources` paths and `decision:<id>` syntax.
Add unambiguous `file:<project-relative-path>` and `note:<description>` forms
within the existing list-of-strings model. Recognize old path-like values
(`.md`/other extension, `/`, `./`) as files even when missing; other free text
is an unverified descriptive citation. Existing-file lookup precedes this
heuristic. Normal Markdown links remain relative to their containing document.
Normalize contained `..` segments for relative body links, rejecting escapes;
do not relax boundary checks on project-relative source fields.

A `note:` or free-text author citation is allowed without claiming machine
verification. The agent checks it against the conversation/source and records
the actual statement only when persistence is useful and authorized. Do not
manufacture a transaction to satisfy provenance. Existing receipts prove a
recorded transaction, not author confirmation; their retention remains intact.

## Optional capabilities and compatibility

- Generic reading, links, provenance resolution and explicitly selected prose
  checks work without a manifest or tags. Missing title/language/schema fields
  are not defects in ordinary author documents. Language-specific checks need
  available language evidence or an explicit option; do not invent it.
- Reports add coverage: checked paths plus skipped checks with reasons.
  `--strict` still fails actual warnings/errors, not an inapplicable optional
  capability. No-op coverage must never be presented as full verification.
- Reindex only explicitly owned/generated indexes. Do not overwrite an author's
  `_index.md` or create one per tag in a shared folder. Version-1 generated
  indexes remain supported; new indexes need an explicit destination.
- Exact edits, transaction history, conflict detection, undo, recovery and
  context redaction retain existing safeguards. Tags never grant write access.
- Managed draft create/rebase/accept works at arbitrary named Markdown paths;
  creating a managed draft is explicit opt-in. Preserve lifecycle metadata and
  hashes. No manuscript promotion based on a tag alone.
- Existing schema-v1/v2 projects, translation originals, receipts and snapshots
  remain readable. No automatic project-schema bump or database migration.
  Translation's existing managed pipeline stays an opt-in capability; arbitrary
  layouts still support literary translation through skills. Do not claim its
  specialized CLI pipeline supports arbitrary layouts until separately adapted.
- Relocation remains explicitly requested, never a response to check findings.
  Keep v1 relocation working; reject ambiguous v2 relocation plans before writes
  rather than guessing which shared/tagged files should move.

## Skill behavior and completion criteria

Update the shared author workflow contract and every active canonical caller:
setup/bootstrap/maintenance/doctor, muse and worker prompts, KB management,
story-memory resources, planning, world creation, review, targeted editing,
translation and Hieronymus integration where they assume managed paths.
Examples may show conventional folders, clearly labeled optional examples.
Read project instructions and actual files first. Do not initialize/migrate just
to review, brainstorm, draft or capture an author's statement. Use existing
safe editor tools when the CLI is inapplicable; maintain named write scope and
reviewable changes. Do not promise CLI undo for changes made outside its journal.

Completion requires behavioral tests for flat, nested, shared, untagged, tagged,
legacy and translation projects; checks and ordinary skill workflows must not
move content or create scaffolds. All canonical consumer classifications must
agree. Regenerate compatibility output and run the repository validation chain.

Out of scope: new databases, arbitrary file-format parsers, automatic semantic
tagging of prose, a tag-management UI, automatic migration or a release now.

# External CWS Project Contract v1

This resource publishes the structural parts of a Creative Writing Skills (CWS)
project that another tool may recognize without installing or importing CWS.
Contract version 1 describes both existing project schema versions 1 and 2.
The contract version and the manifest's `schema-version` are independent.

The portable executable examples are
[`compatibility/cws-project-v1.json`](compatibility/cws-project-v1.json). Paths
in that file use `/`, are relative to the fixture directory, and map to complete
UTF-8 file contents. `expect.root` is relative to the fixture directory, while
the keys in `expect.roles` are relative to that discovered project root.

## Discovery boundary

Starting at a file or directory, walk ancestors toward the filesystem root. The
nearest directory containing a regular, non-symbolic-link `project.md` is the
project root. Resolve the root before reporting it. A `project.md` below that
root starts an independent nested project; do not cross either project boundary
while walking project content. If no such manifest exists, the path is not a CWS
project.

The optional root project-instruction file has this portable filename:

```text
AGENTS.md
```

Read it as free-text instructions in the context of the user's current request.
Its presence and the structural roles below do not create permission to write,
copy, synchronize, or trust data.

## Manifest parser subset

Managed documents are UTF-8, with an optional UTF-8 BOM. Frontmatter exists only
when the first line is exactly `---` and ends at a later line exactly equal to
`---`. CWS accepts a deliberately small, flat subset:

- unique, unindented string keys;
- scalar strings, base-ten integers, and lowercase `true` or `false`;
- JSON double-quoted strings and YAML-style single-quoted strings;
- string lists whose items are indented by exactly two spaces and begin with
  `-` under an otherwise empty key;
- blank lines and full-line comments.

An empty key parses as an empty string; translation list readers treat that as
an empty list. Nested mappings, indented content, flow collections, block
scalars, anchors, aliases, tags, duplicate keys, unterminated frontmatter, and
invalid UTF-8 are technical failures. A consumer that cannot safely implement
this subset must leave the document opaque. CWS preserves original bytes when
parsed content is unchanged.

Schema 1 requires `schema-version: 1`, a non-empty `title` and `language`, and a
status of `planning`, `drafting`, `revising`, `complete`, or `archived`.
Schema 2 additionally requires `project-kind` (`authoring` or `translation`),
`work-kind` (`book` or `series`), and `translation-enabled: true`. An unsupported
schema maps to the public technical failure `unsupported_schema`; the fixture
also records CWS's current producer diagnostic for executable compatibility
testing.

## Public structural roles

A role identifies structure, not authority. Consumers may expose these role
names:

| Public role | Current CWS structure |
| --- | --- |
| `instructions` | Root project-instruction file named in the discovery section |
| `manifest` | Root `project.md` |
| `accepted_prose` | Chapter or side story in either supported schema; schema-2 translation `accepted/` document |
| `draft` | Schema-2 translation `drafts/` document |
| `work` | Direct work artifact in either supported schema |
| `knowledge` | Vocabulary, continuity, or managed knowledge content in either supported schema |
| `derived` | An exact generated-index path listed below |
| `private_state` | Content below `.creative-writing/` |
| `opaque` | Unknown files, legacy originals, and schema-2 supplied originals |
| `source_edition` | Schema-2 `sources/<edition>/edition.md` |
| `source_unit` | Schema-2 working source text in the book or series layout |
| `translation_direction` | Schema-2 `translations/<direction>/translation.md` |
| `direction_settings` | Schema-2 series volume `settings.md` |
| `translation_memory` | Schema-2 direction memory record or `memory/style.md` |
| `alignment` | Schema-2 direct Markdown child of `kb/source-comparisons/` |
| `entity` | Schema-2 direct Markdown child of `kb/entities/` |
| `review` | Schema-2 translation `reviews/` document |

Neither `accepted_prose` nor `knowledge` decides trust. A direct author edit,
an AI suggestion, a provisional observation, and a generated or imported fact
can occupy a structurally recognized file. Interpret authority from the user's
free-text agreement, source tags, provenance, lifecycle metadata, and current
task. Merely detecting CWS, another installed tool, or a technical binding does
not change that agreement.

## Exact retained authoring paths

Schema 2 first recognizes its translation-specific paths, then deliberately
falls through to the same authoring path rules as schema 1. In particular, a
schema-2 `project-kind: authoring` project keeps its chapters, side stories,
work artifacts, knowledge files, continuity files, and base generated indexes
in their existing roles. For the patterns below, `<name>.md` is one direct
Markdown filename, cannot be `_index.md`, and cannot contain another path
separator.

`accepted_prose` recognizes these direct paths in either supported schema:

- `story/chapters/<name>.md`
- `story/side-stories/<name>.md`

`work` recognizes a direct `<name>.md` child of exactly these directories in
either supported schema:

- `work/archive/`
- `work/brainstorm/`
- `work/drafts/`
- `work/plans/`
- `work/reviews/`

`knowledge` recognizes exactly these fixed files and direct-child patterns in
either supported schema:

- `kb/vocab.md`
- `kb/continuity/promises.md`
- `kb/continuity/questions.md`
- `kb/continuity/state.md`
- `kb/continuity/timeline.md`
- `kb/continuity/scenes/<name>.md`
- `kb/canon/<name>.md`
- `kb/characters/<name>.md`
- `kb/issues/<name>.md`
- `kb/samples/<name>.md`
- `kb/styles/<name>.md`
- `kb/world/<name>.md`

`derived` recognizes exactly these base files in either supported schema:

- `kb/_index.md`
- `kb/canon/_index.md`
- `kb/characters/_index.md`
- `kb/continuity/_index.md`
- `kb/continuity/scenes/_index.md`
- `kb/issues/_index.md`
- `kb/samples/_index.md`
- `kb/styles/_index.md`
- `kb/world/_index.md`
- `story/_index.md`
- `story/chapters/_index.md`
- `story/side-stories/_index.md`
- `work/_index.md`
- `work/archive/_index.md`
- `work/brainstorm/_index.md`
- `work/drafts/_index.md`
- `work/plans/_index.md`
- `work/reviews/_index.md`

Schema 2 additionally recognizes exactly these generated-index paths, where
`<direction>` is one path component and is not `originals`:

- `sources/_index.md`
- `translations/_index.md`
- `kb/entities/_index.md`
- `kb/source-comparisons/_index.md`
- `translations/<direction>/_index.md`

No other `_index.md` receives the `derived` role under contract version 1.

## Authoring structure in both schemas

Numbered main chapters are direct Markdown children of `story/chapters/` with a
unique positive integer `number`. Accepted side stories are direct Markdown
children of `story/side-stories/`. Each has an `after` value naming an accepted
chapter or side story and may have a lowercase `subtype` slug. Chapters sort by
`number`; side stories are inserted after their durable anchor, with portable
path identity breaking ties between siblings. Missing anchors and cycles are
technical structural errors.

Other files remain opaque. Root entries outside managed roots are allowed and
must remain untouched.

## Schema-2 translation structure

A source edition lives at `sources/<edition>/edition.md`. Its supplied files in
`originals/` are opaque even when their extension is `.md`; working source units
live in `text/`. Books put those directories directly below the edition. Series
put them below `volumes/<volume>/`. Do not mix layouts. Unit IDs are stable only
within an edition, so references use `edition:unit`, such as `ja:u001`.

A direction lives at `translations/<direction>/translation.md`. Its own
`language` is the target language; several directions may share a language.
`primary-edition`, `auxiliary-editions`, and `coverage` select source evidence.
A series may override source and inheritance fields at
`volumes/<volume>/settings.md`. Missing override fields inherit; present empty
lists clear the inherited values. Never silently fall back from a missing or
uncovered edition.

`translation_memory` recognizes exactly
`translations/<direction>/memory/style.md` and a direct Markdown child of
`translations/<direction>/memory/terms/`, `voices/`, or `decisions/`. No deeper
path and no other memory subdirectory has that role; `<direction>` has the same
component restriction stated for generated indexes. Alignments and shared
entities are direct Markdown children of `kb/source-comparisons/` and
`kb/entities/`. Shared entities identify the same subject across editions or
directions but do not impose one rendering. Draft, review, and accepted paths
are direct children of their direction for a book and of its volume directory
for a series. Lifecycle metadata, source-unit lists, packet transaction, base
revision, and review hash remain CLI-owned.

## Preservation and authority boundaries

Treat generated `_index.md` files, `.creative-writing/`, and CLI-managed
lifecycle metadata as protected. Use CWS domain commands for authorized changes
to those paths. Paths outside the discovered root, paths inside a nested project,
symbolic-link mutation targets, supplied originals, and legacy `inspiration/`
material are not generic edit targets. Legacy originals include every regular
file and sidecar beneath `inspiration/`; preserve their relative tree and exact
bytes.

Preserve direct author edits and the source tags that qualify content. Untagged
text is author-stated, `<AI>...</AI>` is an AI suggestion, and
`<hidden>...</hidden>` is author-only information. Structural discovery never
removes tags, promotes an observation to canon, discloses hidden text, or grants
permission to mutate either CWS or an external system.

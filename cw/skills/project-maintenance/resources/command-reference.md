# Command Reference

Resolve the installed `project-maintenance` skill and invoke
`resources/cli/cw.py` directly with Python. Run from the relevant project path
or pass the project path where the command accepts one. A user-scoped `cw`
launcher is convenience, never a runtime prerequisite. `cw cli-doctor` tries
to install or refresh its managed wrapper in a safe user-owned PATH directory.

Use `--format json` when structured output helps. Transactional previews do
not modify the project. Transactional mutations preview by default and write
only when repeated with `--apply`; the derived context cache has the narrower
exceptions described below.

## Inspect and prepare context

```text
check structure|links|kb|continuity|drafts|prose|journal|translation|all [project]
check prose|all [project] --draft-typography
doctor
layout
get-folder chapters|side-stories|drafts|characters|world|plans|brainstorm|reviews|archive
layout --capture [--apply]
layout --set chapters=<folder> [--set drafts=<folder>] [--apply]
context draft|chapter|kb <path> [--as trusted|reader|character:<id>] [--snapshot]
clean-context
reindex
```

Use `check all` for the mechanical floor, or a focused checker while working
in one domain. `layout` inventories populated common Markdown folders without
creating paths or selecting between ambiguous locations. `.cws-layout.json`
stores folder choices for this project, separate from `project.md`.
`layout --capture` saves only unambiguous populated folders; `--set` records
an explicit role path. Both preview changes before `--apply` and can be undone.
`get-folder <role>` prints the selected project-relative path (or returns it
as `path` with `--format json`) without creating a folder. Resolve roles this
way before constructing artifact paths in skills and worker tasks. Use these
as internal setup aids; do not make the author run them or treat a
missing candidate as a setup failure. Context planning without `--snapshot` is read-only. A restricted
`context --snapshot` writes derived cache without `--apply`; trusted context
can use the selected source paths directly. `clean-context` previews and
applies derived-cache deletion with `--apply`, but it stays outside transaction
history. `reindex` is transactional: preview it, then apply the reviewed diff.

`check prose` always reports universal Unicode counts and integrity signals.
Routine checks omit typography findings for working drafts; use
`--draft-typography` only when that draft is ready for a surface pass. Draft
source-tag and Markdown integrity findings remain visible in ordinary checks.
Russian and English capabilities additionally measure their own pronoun,
opener, quote, punctuation, and dialogue conventions. For an unsupported
language, the check explicitly omits those language-sensitive metrics, reports their
structured `skipped_metrics`, and continues without a failing status or an
English fallback.

Russian-language projects additionally receive deterministic typography
findings (`CW-PROSE-100`…`CW-PROSE-103` warnings for straight quotes,
spaced hyphens, three-dot ellipses, and breakable spaces after
single-letter words; `CW-PROSE-110`…`CW-PROSE-114` info findings for digit
grouping, decimal points, `№`, ordinals, and abbreviation spacing). They
report typographic norms as warnings the project's `project.md`
conventions may override; they never fail `check all` without `--strict`.
For safe Russian spacing fixes on one manuscript file, use
`fix-prose-typography <path>` to inspect the transaction diff and repeat with
`--apply` to write it. The command repairs single-letter-word spaces and a
breakable space before an existing em dash. It skips fenced code, inline code,
and lines with Markdown link targets; it does not rewrite words or punctuation.
The transaction can be undone with `undo <transaction-id> --apply`.

## Project and draft lifecycle

```text
init [path] --title <title> --language <language>
draft create <target> [--draft-path <path>]
draft set-status <draft> working|review|ready
draft rebase <draft>
draft accept <draft>
draft abandon <draft>
migrate --plan
migrate --preview <plan.json> --expect-plan-hash <hash>
migrate --apply <plan.json> --expect-plan-hash <hash>
```

Migration inventories the entire legacy `inspiration/` tree, not only
Markdown. Every regular file is represented by an in-place `preserve`
operation and remains byte-for-byte unchanged: Pocket Editor binders and
review sidecars, images, DOC/DOCX/RTF and other documents, hidden metadata, and
unknown service files are all opaque author material. Symlinks, special files,
and nested projects are not followed and appear as unresolved safety entries.

New projects receive `prose-profile: general`. Existing schema-v1 projects
without the optional field behave the same way, and valid custom profile slugs
are preserved by migration, rebase, and exact document edits.

Draft targets may be numbered chapters in the selected chapters folder or
ordered side stories in the selected side-stories folder. Resolve those paths
with `cw get-folder` first. A side story requires an `after` path to an
accepted manuscript document and may declare a lower-case `subtype`. Use
`context chapter` for either accepted manuscript role; it follows their
aggregate reading order when selecting neighbors.

Preview every lifecycle mutation. Draft acceptance changes the story target;
it does not itself write material into the KB. After acceptance, re-read the
accepted text and synchronize direct and unambiguous facts from that accepted
text through a separate previewed, recoverable KB transaction without
reapproval.

A separate KB transaction does not mean separate approval. Ask the author only
when ambiguity, inference, conflict, retcon, source-tag uncertainty, or
character/reader knowledge-boundary uncertainty would materially change canon
or knowledge boundaries. The agent carries plan hashes and `base-revision`
values between commands without asking the author to maintain them.

## Guarded edits and transaction history

```text
edit replace|insert-before|insert-after|delete|append ...
edit apply <operations.json>
history
history show <transaction-id>
undo <transaction-id>
recover <transaction-id>
```

Put large anchors and replacement bodies in files. Text anchors match only the
Markdown body, never YAML frontmatter. Do not use a copy of the entire
physical file as `--old-file`; use a `frontmatter-set` operation in `edit apply` for ordinary metadata
or the relevant lifecycle command for protected metadata. In `edit apply`,
match counts are checked independently for each operation's `path`; conflicts
identify the operation number and path. Preview edit, undo, and
recover operations before `--apply`. `history` is append-only evidence: undo
creates a new inverse transaction and refuses diverged targets. Recovery rolls
an interrupted transaction back only when journal evidence still proves the
safe before-state.

`edit replace` treats every non-empty whitespace run in `--old-file` as
equivalent to any other non-empty whitespace run in the target. This includes
ordinary spaces, indentation, tabs, non-breaking spaces, and line breaks.
Match-count guards apply to all whitespace-equivalent matches.
At the end of an anchor, whitespace matches the shortest non-empty run, so a
trailing newline from `--old-file` does not consume a following blank line.

`edit append <path> --new-file <file>` adds a block after the existing Markdown
body without an anchor. It leaves frontmatter untouched and inserts a blank
line when needed to separate the block. It previews by default and is useful
for an explicitly requested addition to one known file; use a targeted edit
when placement within the file matters.

## Exit status

- Exit 0: the command completed; continue the requested workflow.
- Exit 1: findings or a safe conflict need agent inspection. Continue any
  unrelated creative work while planning a bounded repair.
- Exit 2: the CLI could not execute. Follow the `cli-doctor` workflow; keep
  runtime setup away from the author.


## Literary translation (schema v2)

All mutations preview by default and execute only with `--apply`. All commands
support `--format json`; the agent prepares files and runs mechanics.
Transaction writes hold a project-wide OS lock through validation, installation
and rollback (`flock` on POSIX, a named mutex on Windows).
Context scope is limited to 4096 combinations of units, entities and
relationships per volume; split larger requests into smaller packets.

```bash
cw init book --title "Book" --language ru --kind translation --work-kind series
cw translation enable --work-kind series
cw translation source --request source.json
cw translation direction --file direction.md
cw translation alignment --file alignment.md
cw translation memory --direction ru --kind voices --file voice.md
cw translation memory --kind entity --file entity.md
cw translation context --direction ru --units ja:u001 --scope scope.json
cw translation draft --direction ru --draft-id first --packet packet.json --file prose.md
cw translation set-status translations/ru/volumes/v001/drafts/first.md reviewed
cw translation accept translations/ru/volumes/v001/drafts/first.md
cw translation status translations/ru/volumes/v001/drafts/first.md
cw check translation
cw reindex
```

For operation-local external memory, add `--memory-input memory-input.json` to
`translation context`. Omitting it preserves packet version 1. A supplied JSON
object creates packet version 2; `{}` keeps the same file-memory selection.
Only these three keys are permitted (each is optional):

```json
{
  "external-memory-refs": [],
  "excluded-file-memory": ["translations/ru/memory/voices/"],
  "external-entities": {}
}
```

Exclusions are project-relative files or directories inside the selected
direction's `memory/`, including the whole memory directory. Directory selectors
also exclude future records. Exclusion occurs before parsing and graph validation;
it never removes source, original bytes, alignment, direction strategy, manifest,
or accepted-base guards. If a retained rule supersedes an excluded record, the
context request is rejected and produces no packet; exclude the dependent rule
too or keep the parent. Ordinary project diagnostics still inspect all file memory.

Each `external-memory-refs` item is an object containing exactly the nonempty
string fields `provider`, `namespace`, `record_kind`, `record_id`, and `revision`.
For Hieronymus, form `namespace` from the actual public `status.instance_id` and
actual series slug. `hiero status --json` exposes the daemon payload under
`status`; process identity may change on restart. Capture each used record's
public revision and the series authority revision when available. Do not invent
a persistent service UUID, use a database path as identity, or manufacture a
revision from a backend digest.

If a used advisory item has no public revision or service identity, include
`{"unverified":"Public evidence response has no revision"}` as a separate item.
The reason describes the missing technical evidence, never source text or the
user's agreement. This marker can coexist with strict references and always
remains unverified; replacing it with verifiable evidence requires a new packet.
`external-entities` maps IDs in this task's `scope-entities` to nonempty arrays of
the same references or markers. These selected entities need no `kb/entities/`
mirror and their references participate in freshness checks.

Keep passing the captured packet to `translation draft --packet packet.json`.
Packet version 2 stores validated selections under `memory-input`; draft planning,
status, and validation under the local transaction lock rebuild the packet from
those selections and compare all captured context and dependency data. The local
snapshot records task inputs; it does not fetch or mirror external record text.

```bash
cw translation status translations/ru/volumes/v001/drafts/first.md --external-memory-observed observed.json
cw translation accept translations/ru/volumes/v001/drafts/first.md --external-memory-observed observed.json
cw translation accept translations/ru/volumes/v001/drafts/first.md --external-fallback-note fallback.txt
```

`observed.json` must be a JSON array of strict reference objects, without
unverified markers. An omitted observation file means verification is unavailable;
an empty array means no captured references were found. Known changed or missing
references yield `needs-review`; unavailable verification or a captured marker
yields `unknown`. A plain offline check reports `CW-TRANS-012` for unknown external
freshness and never claims to have queried a service.

For an expressly authorized fallback, `--external-fallback-note` reads nonempty
UTF-8 text recording the task-specific limitation. It may accompany observations
when some used dependencies remain unverified. Acceptance records the note and
supplied observations in its transaction. Its `external-memory-freshness` field
records `unknown` as the historical acceptance limitation. Without observations, freshness
stays unknown. Later matching observations for all captured strict references can
report current freshness while preserving that historical limitation; captured
unverified markers still keep freshness unknown. A note never permits known changed
references, stale local inputs, edited unreviewed prose, changed accepted bases,
duplicate coverage, or unsafe paths. The CLI cannot authenticate the agent's
observations or interpret the user's free-text agreement; the skill must obtain
fresh public evidence and apply that agreement. These fields are bookkeeping,
not a trust setting, atomic remote check, or trusted correction receipt. No network
call runs under the local lock, and recovery only restores the frozen local
transaction; it never replays external writes.

`source.json` is one request object. An edition request contains `action: edition`
and `content`, a Markdown string with edition frontmatter and provenance body.
Other requests use these shapes (paths are resolved from command working directory):

```json
{"action":"unit","edition":"ja","unit":"u001","volume":"v001","original-file":"input.pdf","text-file":"extracted.md"}
```

```json
{"action":"refresh-unit","edition":"ja","unit":"u001","text-file":"corrected.md"}
```

```json
{"action":"manuscript-unit","edition":"ja","unit":"u001","volume":"v001","manuscript-path":"story/chapters/one.md"}
```

Omit `volume` for a book. Unit requests optionally accept a positive integer
`order`; otherwise they append in import order. Duplicate orders are rejected. Original imports are regular, explicitly selected files;
no automatic converter is run. Existing original destinations cannot be replaced.
Example edition content and direction file:

```markdown
---
edition-id: ja
language: ja
edition-role: original
revision-label: first
coverage:
  - v001
---
# Japanese edition
Record supplied edition provenance here.
```

```markdown
---
direction-id: ru
language: ru
primary-edition: ja
auxiliary-editions:
coverage:
  - v001
inheritance:
---
# Russian translation
Follow the Japanese source for meaning; preserve deliberate ambiguity.
```

An empty list is written as a bare field with no list items. This is the existing
restricted frontmatter format, not nested YAML or inline `[]`.

A voice record uses this structure; replace its body with actual evidence-based
instructions. Accepted status must represent a settled decision.

```markdown
---
record-id: host-voice
subject: host-voice
status: proposed
scope-volumes:
  - v001
scope-entities:
  - host
evidence:
  - "ja:u001 — Chapter 3: Scene where the host threatens the guest"
---
Observation: the host remains formally courteous.
Proposal: preserve formal address and composed syntax even in threats.
```

Register the corresponding entity before including its identity in context
scope. Example `scope.json`: `{"scope-entities":["host"]}`. Volume and unit
scope are derived from selected units; contradictory overrides are rejected.
The context command emits a read-only JSON packet. Save that output to a
temporary file for `--packet`; do not edit its source text or dependency fields.
Packets include trusted hidden context and must not be treated as publication
artifacts or character/reader simulation contexts.

Directions, alignments and memory are registered/updated from their Markdown
files. Volume settings include `direction-id` and `volume-id` and only override
source/inheritance fields. For `memory`, kinds are terms, voices, decisions,
style, and shared entity. Use generic exact edits for draft prose; use domain
commands for protected lifecycle metadata. `history`, `undo`, and `recover`
apply to translation transactions too. A changed base or input requires a
fresh reviewed draft, never a forced accept.

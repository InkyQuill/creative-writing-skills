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
check structure|links|kb|continuity|drafts|prose|journal|all [project]
doctor
context draft|chapter|kb <path> [--as trusted|reader|character:<id>] [--snapshot]
clean-context
reindex
```

Use `check all` for the mechanical floor, or a focused checker while working
in one domain. Context planning without `--snapshot` is read-only. A restricted
`context --snapshot` writes derived cache without `--apply`; trusted context
can use the selected source paths directly. `clean-context` previews and
applies derived-cache deletion with `--apply`, but it stays outside transaction
history. `reindex` is transactional: preview it, then apply the reviewed diff.

`check prose` always reports universal Unicode counts and integrity signals.
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

Draft targets may be numbered chapters under `story/chapters/` or ordered side
stories under `story/side-stories/`. A side story requires an `after` path to an
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
edit replace|insert-before|insert-after|delete ...
edit apply <operations.json>
history
history show <transaction-id>
undo <transaction-id>
recover <transaction-id>
```

Put large anchors and replacement bodies in files. Preview edit, undo, and
recover operations before `--apply`. `history` is append-only evidence: undo
creates a new inverse transaction and refuses diverged targets. Recovery rolls
an interrupted transaction back only when journal evidence still proves the
safe before-state.

`edit replace` treats every non-empty whitespace run in `--old-file` as
equivalent to any other non-empty whitespace run in the target. This includes
ordinary spaces, indentation, tabs, non-breaking spaces, and line breaks.
Match-count guards apply to all whitespace-equivalent matches.

## Exit status

- Exit 0: the command completed; continue the requested workflow.
- Exit 1: findings or a safe conflict need agent inspection. Continue any
  unrelated creative work while planning a bounded repair.
- Exit 2: the CLI could not execute. Follow the `cli-doctor` workflow; keep
  runtime setup away from the author.


## Literary translation (schema v2)

All mutations preview by default and execute only with `--apply`. All commands
support `--format json`; the agent prepares files and runs mechanics.

```bash
cw init book --title "Book" --language ru --kind translation --work-kind book
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

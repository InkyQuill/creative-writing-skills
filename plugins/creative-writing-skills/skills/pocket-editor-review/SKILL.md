---
name: pocket-editor-review
description: >
  Consume Pocket Editor review sidecars during planning and prose revision.
  Load when a writing folder contains .pocket-editor.json or sibling
  *.review.json files: resolve accepted, rejected, or obsolete review items,
  remove handled records, delete empty sidecars, and register new chapters in
  the binder. Do nothing when the author does not use Pocket Editor.
---

# Pocket Editor Review

Treat Pocket Editor files as the current editorial overlay, not as review
history. Apply this skill alongside the writing, review, planning, or editing
workflow that decides the substance of the feedback. It owns only Pocket
Editor bookkeeping.

The durable format belongs to
[Pocket Editor](https://github.com/InkyQuill/pocket-editor). Inspect the files
that actually exist in the book folder before acting; do not create Pocket
Editor artifacts for a project that has neither a binder nor review sidecars.

## Read the Overlay Safely

Scan the relevant chapter folder for `.pocket-editor.json` and sibling
`<chapter>.review.json` files. Re-read the source, binder, and sidecar
immediately before deciding or mutating anything.

For a v1 review sidecar, distinguish all six review surfaces:

- `signals[]` records with type `note`, `change_required`, `warning`, or
  `review`; each has a stable `id`, selected text, an anchor, and an optional
  or empty comment.
- `edits[]` records; each stable `id` proposes replacing `before` with `after`.
- The singleton `chapter_note` string; an empty string means that no chapter
  comment remains.

Before using feedback, validate that the JSON parses, the supported
`schema_version` matches the observed shape, `source_path` names the sibling
chapter, and `chapter_id` matches that path in the binder when a binder exists.
Use the record ID as identity. Hashes, byte ranges, selected text, and
prefix/suffix context are evidence for locating the intended passage, not a
license to delete a merely similar record. A stale source hash means the
anchor needs adjudication against the current text; it does not by itself make
the feedback irrelevant.

Do not rewrite anchors for unresolved records merely because the source
changed. Preserve every field and record not explicitly handled.

## Resolve One Item at a Time

Classify each item the author or current workflow has decided:

- **Accepted and applied:** first verify the intended source change is present,
  then remove that signal or edit record. For an accepted chapter comment,
  verify the requested chapter-level work is complete, then set
  `chapter_note` to an empty string.
- **Rejected:** make no prose change and remove the corresponding record, or
  clear the rejected chapter comment.
- **No longer relevant:** verify that the current text or settled direction
  truly supersedes it, then remove or clear it.
- **Planned but not yet applied:** keep it in the sidecar. Add an explicit
  post-edit requirement to the action plan: after applying and verifying the
  prose change, re-open the current sidecar and use `$pocket-editor-review` to
  remove the named processed record IDs or clear `chapter_note`. This cleanup
  is part of the planned edit because source changes may invalidate the
  processed anchors.
- **Unresolved:** preserve it. Do not interpret silence, an empty comment, a
  stale anchor, or nearby edits as acceptance or rejection.

When one prose change resolves several review records, name every affected ID
before editing and delete only those records after verification. When an
`edits[]` proposal is adapted rather than applied literally, remove it only if
the resulting prose satisfies the accepted editorial intent.

## Write and Verify the Sidecar

Re-read the sidecar just before cleanup and confirm each target ID still names
the record that was adjudicated. Make the smallest JSON change:

- filter handled signal IDs only from `signals`;
- filter handled edit IDs only from `edits`;
- clear `chapter_note` only when that singleton comment was handled;
- retain schema, chapter identity, source path, ordering, anchors, comments,
  and all unresolved records exactly.

After the mutation, parse the JSON again and confirm the intended IDs are gone
and all other IDs remain. If `chapter_note` is empty and both `signals` and
`edits` are empty, delete the sidecar instead of retaining an empty overlay.
Report which IDs or chapter comment were consumed and whether the sidecar was
deleted.

## Keep the Binder Current

When `.pocket-editor.json` exists, compare its `chapters[].path` values with
the book folder's direct-child Markdown chapter files. Register confirmed new
chapters that are not already present:

- preserve `schema_version`, `book_id`, title, ignored paths, every existing
  chapter ID, and the established reading order;
- assign each new chapter a fresh UUID and use its direct-child relative path;
- place it where the established filename/TOC sequence clearly requires it,
  including before a trailing index or other established end matter; if the
  reading position is genuinely ambiguous, ask the author rather than inventing
  story order;
- never duplicate a path or ID, never reuse an ID from another chapter, and do
  not create an empty review sidecar for the new chapter.

Parse the updated binder and verify unique chapter paths and IDs. When a new
chapter already has a sidecar, also verify that its `chapter_id` and
`source_path` match the new binder entry.

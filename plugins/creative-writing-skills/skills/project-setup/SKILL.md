---
name: project-setup
description: >
  One-time project setup for creative writing. Interviews the author about the project, discovers or confirms its file layout, collects provisional writing samples and voice goals, and creates or updates project instructions after the workspace plan is approved.
---

# Project Setup

Establish only the conventions needed for the author's requested work. Load
`$project-bootstrap` to resolve applicable instructions and read its
`resources/author-workflow-contract.md`. Existing files and the current request
come first; no setup questionnaire, manifest, or scaffold is required.

## Discover Before Changing

Read the relevant author files and any existing instructions, layout tags,
project metadata, or indexes. Preserve flat, shared and nested layouts. An
ordinary folder is already usable: do not run `cw init` or `cw migrate` merely
because `project.md`, `kb/`, or `story/` is absent. Missing optional tooling is
not broken project state.

Use optional `.cws-layout.json` tags only when durable routing would help.
Preview `cw layout tag notes --kind directory --add kb` or tag `.` for a flat
project; exact file overrides handle mixed contents. Multiple folders can share
tags. `cw layout inspect` reads them without writing. Inspect existing evidence
before choosing tags; tags never mark prose accepted or proposals canonical.
Use `cw layout destination reviews .` only when an output destination is needed.
An explicit output filename works without saving configuration.

Offer `cw init` only for an author-requested new managed scaffold. Offer
migration or relocation only for a requested reorganization; preview every
semantic move/merge and obtain the author's approval before applying it.
Preserve the complete opaque `inspiration/` corpus, Pocket Editor sidecars,
images, unknown files, and existing author metadata in place.

## Propose the Writing Contract

Record requested conventions in the author's chosen existing instructions or
notes. A managed `project.md` body can hold the durable writing contract, but
its filename is not a prerequisite. Cover only relevant language, POV, voice,
naming, spoiler/source-tag boundaries and allowed assistance. If no convention
is known, use the current request; ask about material literary ambiguity only.

The optional `prose-profile` defaults to `general`. Preserve custom selectors;
missing language is not English. Language resources use primary-tag fallback,
such as `ru-RU` to `ru`, without restricting author languages.

Keep writing samples and derived style guidance provisional until their role
and destination are approved. Record language, applicability, evidence role
(`authoritative`, `aspirational`, or `negative`), source/citation and source-tag
boundary. Distinguish observed from author-specified guidance. Use existing
sample/style files or explicitly named outputs anywhere in the workspace;
`kb/samples/` and `kb/styles/` are optional legacy examples. A direct author
statement settling role and destination needs no redundant confirmation.

## Apply Safely

Use `$project-maintenance` for applicable previewed CLI transactions. Ordinary
named edits can use safe file tools; preserve current bytes outside the change,
check concurrent edits, and report what changed. Do not claim journal recovery
for edits made outside it. The agent owns hashes, indexes and runtime setup
when managed tools are chosen; never ask the author to maintain CLI metadata.

If the author requests Hieronymus or an existing agreement refers to it, load
`$hieronymus-integration`. Keep any memory agreement as free-text and any
technical binding separate. Neither is required for setup; do not install,
bind, or migrate memory automatically.

## Translation projects

For a literary translation request, establish an independent translation project
or extend an existing author project. Use the v2 translation contract in
$project-maintenance and load $literary-translation. Do not require an author
manuscript, world bible, or character biographies before beginning translation.
The managed translation layout is an explicit opt-in capability. Literary
translation skills also work with the author's existing files without enabling
that pipeline; do not reorganize them as a prerequisite.

Collect only the selected original/reference editions, target direction, work
kind (book or series), actual source coverage and material strategy choices.
Use `cw init --title "<title>" --language <language> --kind translation --work-kind book` or the series variant for a
new project; use `cw translation enable --work-kind book` or
`cw translation enable --work-kind series`, matching the selected work kind,
to extend an author project without moving its manuscript. Preview the concrete setup, then apply within the user's
authorized scope. Keep unknown files and supplied originals untouched.

One language can have multiple editions and directions. The standalone project
language describes working documentation; each edition/direction declares its
own text language. Establish source priority per direction, including explicit
volume overrides. Register existing literary translations as sources rather
than claiming them as newly produced output. Use provisional memory until an
explicit decision or approved inheritance strategy settles a rule.

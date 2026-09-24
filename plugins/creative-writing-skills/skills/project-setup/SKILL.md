---
name: project-setup
description: >
  One-time project setup for creative writing. Interviews the author about the project, discovers or confirms its file layout, collects provisional writing samples and voice goals, and creates or updates project instructions after the workspace plan is approved.
---

# Project Setup

Establish the project-specific writing conventions and one canonical on-disk
contract. Use `$project-maintenance` for all scaffold and migration mechanics;
do not duplicate its command reference or construct managed files by hand.
Load `$project-bootstrap` to resolve or reconcile project instruction
entrypoints. Those instructions are harness guidance; `project.md` remains the
durable story-writing contract.
Read `../project-bootstrap/resources/author-workflow-contract.md` before
proposing the agent's role or any prose edits. Offer ordinary-language examples
of allowed assistance, scope, initiative, and output form; do not require an
agent-role profile or a `cws.md` file.

If the author wants Hieronymus or existing project evidence refers to it, load
`$hieronymus-integration`. Keep any memory agreement as narrow free-text in the
project instructions; do not turn it into required project fields or a trust
flag. An optional technical binding is separate from that agreement. Do not
require Hieronymus installation, create a binding during ordinary setup, or
migrate existing memory automatically.

## Discover Before Changing

Read canonical `project.md`, generated indexes, and populated content before
proposing anything. Resolved project instructions may constrain the current
agent, but they remain unmanaged, optional migration inputs rather
than the durable story-project contract. Ask only for creative information the
managed files do not answer: project kind and stage, language, POV and timeline
shape, an explicitly desired prose profile, voice goals, naming and spoiler
conventions, and the intended role of genuinely ambiguous legacy material.

Classify the folder without moving anything:

- An ordinary folder without recognized story-project content is initialized
  with `cw init` after its title and language are known.
- A folder with recognized legacy content uses `cw migrate --plan`. The agent
  resolves mechanical fields, reviews every proposed destination, and preserves
  unknown files or intentionally unmanaged material untouched. Preview the
  completed migration plan, show the meaningful moves and merges to the author,
  and apply it only after the author confirms the semantic mapping and approves
  the reviewed preview.
- An existing canonical project is extended in place. Do not reinitialize or
  reorganize it merely because optional material is absent.

Treat a legacy `inspiration/` directory as an opaque author-owned corpus. The
migration plan must account for every regular file in it, including Pocket
Editor `.pocket-editor.json` and `*.review.json`, images, documents, hidden
metadata, and unknown service files. Preserve its relative tree and exact bytes
in place; do not classify those files by extension or promote them into the KB.

`project.md` identifies the project. Folder roles are saved separately in
`.cws-layout.json`; `cw layout` detects existing folders and `cw layout
--set chapters=<folder> --apply` records a chosen path. Use the author's
existing folders without moving prose or demanding a canonical tree. The
agent can capture unambiguous existing choices with `cw layout --capture
--apply`; ask only when two populated folders have the same role and the
choice affects the requested work.

The optional `prose-profile` frontmatter selector is independent of manuscript
language. A missing selector means `general`; do not ask the author merely to
confirm that default. Bundled profiles are `light-novel`,
`classical-literary`, and `literary-fiction`, while a project may preserve a
custom lower-case slug for its own profile. Language tags remain open-ended;
bundled language resources use primary-tag fallback such as `ru-RU` to `ru`.

## Propose the Writing Contract

Draft the project-specific writing contract in the body of `project.md` for the
author to review. That authored body is the durable writing contract; preserve
the CLI-owned frontmatter and do not move the contract into project
instructions. Cover:

- project overview, current stage, language, prose profile, and punctuation
  conventions;
- voice, POV, timeline, naming, chapter, spoiler, and source-tagging rules;
- established vocabulary and terms to distinguish or avoid;
- any sample, style, research, or work-support material that would help; and
- how existing legacy paths map to the canonical roles when migrating.

For proposed author-voice evidence, use flat
`kb/samples/<descriptive-name>.md` and derived
`kb/styles/<descriptive-name>.md` paths. Record each sample's manuscript
language/tag, applicability scope, role (`authoritative`, `aspirational`, or
`negative`), source/citation and source-tag boundary, excerpt or chapter
pointer, and why it is evidence. A derived style records language and
prose-profile scope, evidence links, observed versus author-specified guidance,
actionable tendencies, allowed variation, and anti-patterns.

Keep writing samples and voice analysis provisional until their exact role and
destination are approved. A direct author statement that supplies those fields
settles them without a second confirmation; ask only about material ambiguity
or conflicting evidence. Preserve unrelated instructions and unknown files.
Approval of the core project does not imply approval for optional samples,
style files, vocabulary pages, or other auxiliary artifacts. Style analysis is
first proposed as a direct file under the selected reviews folder (`cw
get-folder reviews`), then promoted through a
separate previewed, recoverable transaction after it is approved.

## Apply Safely

Follow `$project-maintenance` preview/apply boundaries. For a new scaffold,
preview and apply `cw init`, then use a previewed exact edit transaction for the
approved `project.md` body. For an existing canonical project or an approved
migration, update that body through the same recoverable transaction path. The
agent owns hashes, indexes, base revisions, migration mechanics, and repair
commands; never ask the author to maintain SHA values or other CLI metadata.
Ask the author only for literary meaning and approval.

Interpret repairable mechanical warnings internally and continue the requested
semantic setup work. The only mechanical reason to stop that work is when a
required target cannot be read safely; report the exact target and preserve all
bytes until it can be inspected.

## Translation projects

For a literary translation request, establish an independent translation project
or extend an existing author project. Use the v2 translation contract in
$project-maintenance and load $literary-translation. Do not require an author
manuscript, world bible, or character biographies before beginning translation.
The canonical authoring layout above remains valid for author projects; the
translation layout is a separate explicit project kind, not an ad hoc relocation.

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

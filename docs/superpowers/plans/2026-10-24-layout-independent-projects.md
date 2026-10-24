# Layout-independent Projects Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make creative-writing skills useful in any author layout, with optional inherited folder/file tags for CLI routing.

**Architecture:** Keep the current CLI, transaction engine and distribution generator. Introduce a shared tag/catalog service and optional workspace discovery, then replace consumer-specific path inference. Keep reference resolution separate from author authority and managed lifecycle state.

**Tech Stack:** Python standard library, unittest, Markdown skills, existing JSON layout and SQLite transaction/context storage.

**Spec:** [Layout-independent story projects](../specs/2026-10-24-layout-independent-projects.md).

## Global Constraints

- The skills must adapt to any author layout.
- Tags describe purpose, never approval or truth.
- Read-only commands create no scaffold, layout, indexes, journal or cache.
- No automatic project-schema bump or database migration.
- Tags never grant write access.
- Edit only canonical runtime sources; regenerate `cw/`.
- Preserve unrelated files, source tags, author approval boundaries, immutable translation originals and transaction recovery.
- Baseline: `a489953` on `origin/main` (0.12.0); implementation has not begun.

## Review Focus

- Root/shared-folder inheritance must not silently classify every file as accepted prose (Tasks 1, 3).
- Opaque metadata and hand-written `_index.md` must survive read/edit/index operations (Tasks 2, 5).
- Missing paths, archived sources and author statements must remain distinguishable (Task 4).
- Explicit-file checks must not scan sibling manuscripts or hidden author-only material (Tasks 2, 3).
- Existing translation, relocation, context redaction and undo flows must remain usable (Tasks 5, 7).

## File map and delivery order

All CLI paths below are relative to
`plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/`.
All skill paths are relative to `plugins/creative-writing-skills/skills/`.
Test paths are repository-relative. New files below are deliberate boundaries,
not a replacement CLI framework.

1. `catalog.py`: tag bindings, effective document purposes and legacy adapter;
   `layout.py`: configuration/CLI compatibility, no separate classification.
2. `project.py`, `documents.py`: workspace and reading boundaries.
3. Existing check/context consumers: use the catalog; `findings.py`: coverage.
4. `provenance.py`: reference resolution independent of document purpose.
5. Existing mutation services: tag-aware destinations and managed feature opt-in.
6. Canonical skills/resources: optional tooling and layout-neutral workflow.
7. Behavioral cross-layout validation and generated distribution.

Each task is a reviewable commit. Do not ship the catalog alone as full layout
support; Tasks 1–7 form the release acceptance boundary. No release/version
changes belong in this implementation branch.

### Task 1: Optional inherited tags and version-1 compatibility

**Files:** Create `catalog.py`, `tests/cw_cli/test_catalog.py`; modify
`layout.py`, `app.py`, `tests/cw_cli/test_layout_discovery.py`.

**Interfaces:** Define immutable `TagBinding(path: str, kind: Literal['file',
'directory'], tags: frozenset[str], remove: frozenset[str])` and
`LayoutConfig(version: int, bindings: tuple[TagBinding, ...], destinations:
Mapping[str, str])`. Expose `read_layout(project: Project) -> LayoutConfig`,
`effective_tags(config: LayoutConfig, relative: str) -> frozenset[str]`, and
`resolve_destination(project: Project, tag: str, explicit: str | None = None)
-> str`; unresolved/ambiguous destinations raise `LayoutAmbiguity`.

- [ ] Add `test_root_tag_inherits_into_nested_files`,
  `test_file_override_removes_inherited_draft_tag`,
  `test_multiple_folders_and_tags_are_valid`,
  `test_custom_tag_round_trips`, and
  `test_v1_read_preserves_bytes_and_role_results`. Assert exact tag sets and
  unchanged filesystem snapshots. Duplicate bindings and add/remove overlap fail.
- [ ] Run `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.cw_cli.test_catalog tests.cw_cli.test_layout_discovery -v`; confirm new cases fail for the current limitations.
- [ ] Implement the spec's version-2 binding semantics and v1 adapter; preserve
  v1 `--set`, add `layout tag`, `layout destination`, and `layout inspect`.
  Use the existing transaction engine for preview/apply/undo. Tags are metadata,
  never mkdir/move instructions. Replace the current shared-folder rejection test.
- [ ] Add CLI preview/apply/undo tests and tests for `.` destinations,
  two competing destinations, contained Unicode paths, symlink/traversal refusal.
- [ ] Rerun both modules; require passing tests and no read/preview side effects.
- [ ] Commit: `feat: add inherited project layout tags`.

### Task 2: Workspace access without mandatory project metadata

**Files:** Modify `project.py`, `documents.py`, `app.py`,
`tests/cw_cli/test_project.py`, `tests/cw_cli/test_documents.py`,
`tests/cw_cli/test_app.py`; create `tests/cw_cli/test_workspace_scope.py`.

**Interfaces:** Add `open_workspace(start: Path, *, root: Path | None = None)
-> Project`; allow `Project.manifest: Document | None` and expose
`Project.metadata: Mapping[str, object]` as an empty mapping when absent.
Keep `discover_project` strict for callers that request legacy discovery.
Add `iter_documents(project: Project, *, target: str | None = None)
-> Iterator[Path]` in `catalog.py`. Add `read_document(data: bytes)
-> DocumentRead` in `documents.py`, carrying raw bytes, optional parsed
`Document`, optional body and an optional metadata error.

- [ ] Add cases for manifestless root-level Markdown, a tag-only workspace,
  explicit `--root`, nearest-marker discovery, nested-project exclusion,
  standalone-file scope, hidden-file explicit selection and read-only snapshots.
- [ ] Run `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.cw_cli.test_workspace_scope tests.cw_cli.test_project tests.cw_cli.test_documents tests.cw_cli.test_app -v`; confirm new cases fail.
- [ ] Implement root precedence and scoped inventory from the spec. Audit every
  `project.manifest` access and adapt it to explicit managed requirements or
  `Project.metadata`; do not synthesize schema/version/language defaults.
- [ ] Implement the read envelope without replacing the strict lifecycle parser.
  Add cases for ordinary Markdown, valid unsupported YAML, unterminated
  frontmatter, BOM/CRLF and invalid UTF-8. Assert preserved raw bytes and honest
  metadata/body availability; no rewriting to satisfy parser restrictions.
- [ ] Rerun the four modules, then existing transaction and translation setup
  tests because they consume `Project`. Require old managed behavior unchanged.
- [ ] Commit: `feat: support explicitly scoped unstructured workspaces`.

### Task 3: One document catalog and honest checker coverage

**Files:** Modify `catalog.py`, `schema.py`, `findings.py`, `checks/__init__.py`,
`checks/structure.py`, `checks/links.py`, `checks/prose.py`,
`checks/continuity.py`, `checks/drafts.py`, `context.py`, `doctor.py`, `app.py`;
tests: existing corresponding `tests/cw_cli/test_*` modules plus
`tests/cw_cli/test_catalog.py` and `tests/cw_cli/test_workspace_scope.py`.

**Interfaces:** `classify_document(project: Project, relative: str)
-> DocumentClassification`, with `tags: frozenset[str]`,
`origin: Literal['explicit', 'legacy', 'unknown']`,
`managed_kind: str | None`, `conflicts: tuple[str, ...]`.
Add `CheckCoverage(check: str, paths: tuple[str, ...], skipped_reason:
str | None)` and additive `Report.coverage`. Purpose is not lifecycle state.

- [ ] Add fixtures exercising the same prose and notes in canonical, tagged
  flat, nested and mixed folders. Assert matching applicable check/context
  results; no `ILLEGAL_LOCATION` or missing-scaffold finding for author layouts.
- [ ] Run focused catalog, structure, links, prose, continuity, context-plan and
  check-command tests; confirm new behavioral cases fail before implementation.
- [ ] Route consumers through `classify_document`/`iter_documents`. Retain
  `allowed_document_kind` only inside legacy schema/translation/migration
  adapters. Tag inference never claims `accepted` status or lifecycle metadata.
- [ ] Add coverage serialization/text rendering. Untagged explicit prose checks
  run generic checks; missing language prevents only language-specific checks.
  No lifecycle data means drafts checks are inapplicable, not broken. Strict
  mode does not turn capability absence into a failure.
- [ ] Test ambiguous tags, unknown tags, one-file scope, opaque metadata,
  no-applicable-check reports, and existing hidden/source-tag context redaction.
- [ ] Run affected modules; search all runtime `allowed_document_kind`,
  `role_directories`, and literal `kb/`, `story/`, `work/` decisions. Document
  remaining legacy/translation adapters; remove active duplicate classifiers.
- [ ] Commit: `refactor: share document classification across story checks`.

### Task 4: Layout-neutral provenance

**Files:** Create `provenance.py`, `tests/cw_cli/test_provenance.py`; modify
`checks/kb.py`, `checks/links.py`, `tests/cw_cli/test_kb_check.py`,
`tests/cw_cli/test_links_check.py`; retain receipt storage/checking code.

**Interfaces:** `resolve_source(project: Project, source: str)
-> SourceReference`, with `kind`, `resolution`, `path: str | None`,
`authority`, and `reason: str | None`, using the spec's enumerated values.
The function resolves evidence; it does not promote knowledge or make requests.

- [ ] Add `test_identical_sources_resolve_in_every_layout`, including root,
  custom chapters, drafts, side stories, KB and binary attachments. Assert
  resolved paths without implied acceptance.
- [ ] Add explicit missing file, free text, `note:`, malformed URL, unverified
  HTTP URL, archived file, unavailable metadata, existing/expired valid receipt,
  invalid receipt, encoded traversal, nested-project and symlink cases.
- [ ] Run `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.cw_cli.test_provenance tests.cw_cli.test_kb_check tests.cw_cli.test_links_check -v`; confirm new cases fail.
- [ ] Implement syntax/disambiguation and independent authority/resolution.
  KB checks select by catalog, report genuine broken/unsafe references, and
  show descriptive citations as unverified rather than invalid. Do not treat
  all provisional evidence as invalid; warn about promotion only when an
  explicit accepted claim depends solely on explicitly provisional evidence.
- [ ] Rerun tests; assert no URL fetches, journal writes or manufactured receipts.
- [ ] Commit: `fix: resolve provenance independently of story layout`.

### Task 5: Preserve safe mutations across tagged layouts

**Files:** Modify `edits.py`, `indexes.py`, `drafts.py`, `prose_fixes.py`,
`context.py`, `relocation.py`, `app.py`, `translation/sources.py` and affected
transaction callers. Tests: `test_edits.py`, `test_indexes.py`,
`test_draft_create.py`, `test_draft_lifecycle.py`, `test_draft_rebase.py`,
`test_relocation.py`, `test_context_redaction.py`, translation boundaries and
transaction apply/history/recovery modules under `tests/cw_cli/`.

**Interfaces:** Consume `resolve_destination` and `classify_document`.
Keep existing transaction/draft plan signatures and optional explicit paths;
do not replace SQLite stores or alter retained receipt identities.

- [ ] Add end-to-end cases: flat target + explicitly named managed draft,
  preview/create/rebase/accept/undo; shared tagged notes + one explicit generated
  index; exact text edit with opaque metadata + undo. Assert untouched siblings,
  exact restored bytes, no implicit scaffold or index creation.
- [ ] Run affected tests and confirm the new layout cases fail.
- [ ] Replace destination guesses and path-based ownership checks. Generated
  ownership comes from supported managed metadata/configuration, never merely
  the `_index.md` name. Preserve hand-written indexes. Exact text operations
  remain guarded by unique anchors and transaction conflicts even with opaque
  metadata; frontmatter updates still require safely parsed fields.
- [ ] Preserve v1 relocation; explicitly reject unsupported ambiguous v2
  relocation before writes. Read-only translation reference registration uses
  the shared catalog for author manuscripts; original-file protection remains.
- [ ] Run mutation, recovery, context redaction and translation boundary tests;
  verify acceptance is explicit and stale revisions still conflict.
- [ ] Commit: `feat: support tagged layouts in managed writing operations`.

### Task 6: Rewrite skill contracts around author layouts

**Files:** Modify `project-bootstrap/resources/author-workflow-contract.md`,
`project-setup/SKILL.md`, `project-maintenance/SKILL.md` and its four contract/
workflow/reference resources, `project-doctor/SKILL.md`,
`kb-management/SKILL.md`, `story-memory/SKILL.md` and its resources,
`creative-writing-muse/SKILL.md` and affected worker prompts; audit callers in
planning/world-creation/review/targeted-editing/translation/Hieronymus skills.
Update `docs/architecture.md`, `docs/behavioral-release-checklist.md` and
relevant README examples. Modify existing `tests/test_author_workflow_contract.py`,
`test_project_maintenance_skill.py`, `test_muse_project_workflows.py`,
`test_external_project_contract.py`, `test_translation_skills.py`.

**Interfaces:** Skills consume resolved workspace/tags, actual author instructions,
named source/output paths, and coverage results. No new skill or worker is added.

- [ ] Update contract tests to reject mandatory scaffold/receipt language while
  retaining source tagging, named write scope and confirmation boundaries.
- [ ] Replace prescriptions with optional tagged-layout examples; show root,
  nested and mixed-folder cases. Explain that CLI lifecycle/index/translation
  features have separate prerequisites and are not prerequisites for writing.
- [ ] Remove unconditional `check all`, initialization, migration and CLI-only
  write requirements from ordinary creative workflows. Explain safe direct-edit
  fallback without promising transaction undo. No automatic canon promotion.
- [ ] Walk through: critique a flat chapter without configuration; capture a
  cited author answer in an existing note; use tagged `notes/` and `drafts/`;
  draft with a named output; preserve a foreign-format source. Record concrete
  expected tool choices and filesystem changes in the behavioral checklist.
- [ ] Run the listed skill contract tests; regenerate `cw/` and check sync.
- [ ] Commit: `docs: make story tooling optional and layout adaptive`.

### Task 7: Cross-layout acceptance and distribution verification

**Files:** Create `tests/cw_cli/test_layout_independence.py`; update the
behavioral checklist and only the generated distribution/archive outputs
required by repository conventions.

**Interfaces:** Exercise public `app.run` and installed CLI entrypoint, not
only helper functions. Compare JSON coverage and exact filesystem snapshots.

- [ ] Add public-command scenarios for no-config flat files, root tags with
  file exceptions, shared multi-tag folders, recursive volumes, v1 configuration,
  full scaffold and schema-v2 translation. Verify reads/checks are nonmutating;
  tagged and explicit-file sources are actually checked, not silently skipped.
- [ ] Include reported regression: a KB-tagged note cites `drafts/chapter.md`
  and an author statement; paths resolve and descriptive evidence remains
  unverified without asking for a decision receipt or promoting the draft.
- [ ] Run `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v`.
- [ ] Run `python3 scripts/sync_claude_distribution.py --apply` followed by
  `python3 scripts/validate_distribution.py`,
  `python3 scripts/sync_claude_distribution.py --check`, and
  `python3 scripts/create_skill_zips.py`. Require the configured 36 archives.
- [ ] Inspect canonical diff, generated sync, fixture bytes and `git diff --check`.
  Record exact tested commit and distinguish automated CLI tests from manual
  agent workflow walkthroughs. No version bump, tag or release action.
- [ ] Commit: `test: verify writing workflows across author layouts`.

## Self-review and handoff

All five review-focus cases have explicit task coverage. The hard requirement
is addressed at both skill and CLI layers; removing only the provenance prefix
check is not sufficient. Translation-managed format adaptation is explicitly
outside this redesign, while translation skills remain usable with author files.

Plan-only deliverable. Review the tag model and compatibility behavior before
implementation; execution should follow Tasks 1–7 in order.

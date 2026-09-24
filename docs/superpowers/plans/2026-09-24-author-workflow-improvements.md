# Author Workflow Improvements Implementation Plan

> **For agentic workers:** Implement one task at a time. Read this plan and the current project contract before changing code. Each task has its own review and test gate.

**Goal:** Make Creative Writing Skills adapt to an author's chosen agent role and Markdown layout while keeping everyday writing simple and multi-file changes reviewable.

**Experience rule:** The author can start writing without configuring roles, folders, or checks. Agents quietly resolve applicable rules, repair deterministic recoverable mechanical blockers, and surface only decisions that change prose, meaning, or canon. Reports summarize useful results instead of dumping routine warnings.

**Architecture:** The canonical runtime is `plugins/creative-writing-skills/`; `cw/` is generated distribution output. Keep project authority rules in skill guidance, structural roles in the project contract and CLI, and author content in ordinary Markdown. Reuse the existing transaction engine for preview, apply, and undo.

**Tech Stack:** Markdown skills and contracts; Python `cw` CLI; `unittest`; distribution sync scripts.

**Inputs:** `CWS-CHANGES.md` (author proposal dated 2026-09-23), [GitHub issue #10](https://github.com/InkyQuill/creative-writing-skills/issues/10), and the v0.9.0 repository. Issues #4, #6, and #7 are closed; current side-story support must remain intact.

## Global constraints

- Timeline Helper integration is **deferred**. Do not add its adapter, event model, shared IDs, sync, or acceptance tests in this work.
- Existing projects are not migrated automatically. Preserve unknown author files, nested project boundaries, source tags, author decisions, and explicit uncertainty.
- `AGENTS.md` is the shared harness instruction source. A task-specific direct author request can narrow or extend project defaults for that task, without silently changing project files.
- `project.md` remains the CLI's project-discovery manifest. An optional `cws.md` must not become a required second manifest.
- Do not hand-edit `cw/`; regenerate it after canonical source changes.
- No mandatory setup interview, new role switch, or warning inventory before routine writing. Safe repairs should be automatic within the requested scope; an ambiguous or semantic change needs a focused author decision.
- Treat proposals, assistant inferences, drafts, and approved facts as distinct. Checks report evidence and uncertainty rather than inventing a resolution.

## Priority and dependencies

| Order | Task | Priority | Depends on | Deliverable |
| --- | --- | --- | --- | --- |
| 1 | Project authority contract | P0 | — | Skills obey the author's chosen role |
| 2 | Quiet draft typography and safe fixes | P0 | — | Close issue #10 |
| 3 | Layout roles and discovery | P1 | 1 | Flat and nested projects work without duplicate trees |
| 4 | Stable chapter path and reading order | P1 | 3 | Status changes preserve chapter location |
| 5 | Minimal scaffold and lazy indexes | P1 | 3 | A new project is ready for its first chapter |
| 6 | Evidence and continuity guidance | P1 | 1 | Provisional information stays provisional |
| 7 | Extract a character safely | P2 | 3, 6 | Previewable, undoable extraction |
| 8 | Optional migration and release gate | P2 | 2–7 | Explicit migration with regression coverage |

Tasks 1 and 2 can ship independently. Tasks 3–5 change the structural contract and should be released together. Task 7 is useful without any Timeline Helper connection.

## Review focus

1. Conflicting project instructions: identify each source and stop before an ambiguous write (Task 1).
2. A working draft with malformed source tags: suppress typography noise, but keep integrity findings (Task 2).
3. A flat project with an author-owned `story/` directory: never create a competing manuscript tree (Task 3).
4. A changed chapter status with links from notes: keep its path and reading position (Task 4).
5. A character extraction after the source note changes: reject the stale plan without a partial write (Task 7).

---

### Task 1: Define and test the project authority contract (P0)

**Files:** Modify `plugins/creative-writing-skills/skills/project-bootstrap/SKILL.md`, `project-setup/SKILL.md`, `creative-writing-muse/SKILL.md`, `story-review/SKILL.md`, and `project-maintenance/resources/project-contract.md`. Add a focused authority-contract resource beside `project-contract.md` and behavioral examples under `tests/`.

**Contract:** `AGENTS.md` provides harness instructions; `project.md` may describe author workflow; `cws.md` is an optional human-readable workflow file. Define source precedence and conflict reporting explicitly without letting a lower-priority file override harness rules. Current direct author requests apply only to their stated scope. No role profile requires a particular folder layout.

- [ ] Write three fixture contracts: analysis-only, requested drafting, and editing with separate rules for accepted chapters. Add a conflict case and a one-task override case.
- [ ] Run their behavioral checks and record the current failures.
- [ ] Add one concise guidance resource with allowed actions, material scope, initiative, output form, canon policy, and source precedence. Link it from the owning skills instead of duplicating prose.
- [ ] Re-run behavioral checks; verify a requested dialogue does not authorize other chapter edits, and the conflict case names both sources before a write.
- [ ] Review the guidance against the source-tag rules in repository `AGENTS.md`; commit this independent change.

### Task 2: Resolve issue #10 without weakening draft integrity (P0)

**Files:** Modify `plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/checks/prose.py`, `checks/prose_typography.py`, `app.py`, and `resources/command-reference.md`. Add a small typography-fix planner beside the prose checks. Extend `tests/cw_cli/test_prose_typography.py`, `test_prose_check.py`, and CLI command tests.

**Contract:** Ordinary `cw check all` and `cw check prose` run result-stage typography on accepted chapters and side stories. Working drafts retain tag, fence, and other integrity checks. An explicit draft-typography mode reports draft typography when requested. A fix command changes only rules that have deterministic, meaning-preserving replacements; it previews by default and applies through the transaction engine, with undo available.

- [ ] Add tests for: draft `CW-PROSE-103` absent by default; accepted chapter and side story still warned; explicit draft mode warned; malformed draft tags still warned; English/unsupported-language behavior unchanged.
- [ ] Run the focused tests and confirm the new expectations fail.
- [ ] Separate document eligibility for typography from eligibility for integrity and metrics; expose the explicit draft option in the CLI and command reference.
- [ ] Add fix tests for single-letter-word spaces and the specifically safe dash-spacing rule, including code fences, inline code, frontmatter, existing NBSP, mixed newlines, no-op input, stale preview, and undo. If a dash case is ambiguous, report it without fixing it.
- [ ] Implement the fixer as a transaction plan and run focused tests, followed by the full CLI suite. Commit when the report and diff are stable.

### Task 3: Introduce configurable layout roles (P1)

**Files:** Modify canonical `resources/project-contract.md`, `external-project-contract.md`, `cli/cwcli/schema.py`, `project.py`, `drafts.py`, `context.py`, `indexes.py`, `migration.py`, and `checks/structure.py` under `project-maintenance`. Add one layout-resolution module instead of repeating path interpretation. Extend `tests/cw_cli/test_schema.py`, `test_context_plan.py`, `test_indexes.py`, `test_draft_lifecycle.py`, `test_migration_plan.py`, and `tests/test_external_project_contract.py`.

**Contract:** Resolve semantic roles for manuscript chapters, side stories, plans, drafts, characters, world notes, reviews, and archive from project configuration. Defaults preserve schema-v1 behavior. A project may use `chapters/` directly or nested folders. Unknown paths remain author-owned. Discovering an existing layout is read-only and reports ambiguous matches for author choice; it does not infer a migration destination.

- [ ] Write a layout matrix for existing v1, flat, nested, missing role, duplicate role, unknown folder, and nested project boundary. Run tests to show fixed-path failures.
- [ ] Add versioned role configuration and a single resolver used by validation and commands. Preserve schema-v1 projects without requiring a config edit.
- [ ] Update command paths in small reviewed slices: schema/project discovery; draft lifecycle; indexes and context; migration and structure checks. Run the owning tests after each slice.
- [ ] Add a read-only layout inventory that displays detected folders and unresolved role choices. Test that inventory and normal commands never create `work/drafts/` or `story/chapters/` in a flat project.
- [ ] Update both contract documents and command reference; run the full suite and commit.

### Task 4: Keep chapter files in place across statuses (P1)

**Files:** Modify canonical `cli/cwcli/drafts.py`, `schema.py`, `context.py`, `indexes.py`, and `resources/project-contract.md`. Extend `tests/cw_cli/test_draft_lifecycle.py`, `test_context_plan.py`, and `test_indexes.py`.

**Contract:** A chapter can stay at one path while moving through working, revised, and accepted states. An explicit chapter order determines manuscript order. The existing separate-draft lifecycle remains a supported configuration. Side stories retain deterministic placement without taking a chapter number.

- [ ] Test an in-place chapter through status changes, context selection, indexing, and links from a plan; confirm its path remains constant.
- [ ] Test duplicate or missing order and an invalid status as reported conflicts rather than guessed fixes.
- [ ] Add status-aware operations and selection to the resolved manuscript role. Preserve the existing draft-create/accept path for projects that choose separate drafts.
- [ ] Update generated indexes to reflect the chosen organization while keeping them derived state. Run lifecycle and context tests, then commit.

### Task 5: Make new projects small and usable immediately (P1)

**Files:** Modify canonical `cli/cwcli/scaffold.py`, `schema.py`, `indexes.py`, `project-setup/SKILL.md`, and `project-bootstrap/SKILL.md`. Extend `tests/cw_cli/test_schema.py` and `test_indexes.py`.

**Contract:** Default initialization creates only project instructions, manifest, and the minimum manuscript area needed to start writing. Optional `canon/`, `issues/`, `samples/`, `scenes/`, reviews, and their indexes appear on first use or via an explicitly chosen template. Empty indexes do not dominate Obsidian navigation.

- [ ] Add a snapshot test for the initial tree and a first-minute scenario: create a chapter, character, and plan without manually building folders.
- [ ] Make required paths depend on enabled roles and actual content. Keep existing v1 scaffolds readable and avoid deleting their empty folders.
- [ ] Verify first-use creation, repeat initialization, and generated-index stability; update setup instructions and commit.

### Task 6: Preserve evidence status in skills and continuity checks (P1)

**Files:** Modify canonical `story-memory/SKILL.md`, `kb-management/SKILL.md`, `story-review/SKILL.md`, `project-maintenance/resources/project-contract.md`, and relevant continuity-check guidance/tests under `tests/cw_cli/`.

**Contract:** Keep author decision, approved KB fact, draft occurrence, agent proposal, and agent inference distinct. A continuity report cites the conflicting passages and indicates uncertainty. Unknown time, motive, or other attributes stay unknown. The result is a warning the author may accept or dismiss.

- [ ] Add cases for a draft contradicting approved KB, two ambiguous sources, an agent proposal, and an event described without a date.
- [ ] Update skill guidance and check output so each finding carries source paths and an uncertainty level where evidence allows it.
- [ ] Test that moving or indexing a note leaves its source status intact. Run focused checks, review author-facing wording, and commit.

### Task 7: Extract a character with a transaction preview (P2)

**Files:** Add a focused character-extraction planner under canonical `cli/cwcli/`; wire it through `app.py`. Modify `kb-management/SKILL.md` and `resources/command-reference.md`. Add `tests/cw_cli/test_character_extraction.py`.

**Contract:** Extract a selected heading from a shared character note into a new Markdown card. Preview the new card, the pointer left in the original note, affected Markdown links, and preserved source/status metadata. Do not fill missing attributes or create a second canon entry. Apply uses existing transaction preconditions and supports undo. A section-size threshold may suggest extraction but never triggers it automatically.

- [ ] Test extraction from a shared note, unresolved or duplicate headings, existing destination, author-owned links, mixed newline style, nested project boundary, and changed source after preview.
- [ ] Implement selection and link inventory as read-only planning. Require explicit destination choice where links or names are ambiguous.
- [ ] Build one transaction plan for source, destination, and resolvable links. Verify preview has no writes; apply and undo restore exact bytes.
- [ ] Update guidance and command reference; run focused and full CLI tests, then commit.

### Task 8: Optional migration and release gate (P2)

**Files:** Modify canonical `cli/cwcli/migration.py`, `resources/agent-workflows.md`, and migration tests only as needed for Tasks 3–7. Regenerate `cw/` using the repository script.

**Contract:** Existing projects keep their paths until the author explicitly chooses a migration. Migration inventories every affected file and link, shows a full preview, applies only to a reviewed plan, and can be undone. The current Lilith-style structure and a small flat project are acceptance fixtures.

- [ ] Test migration planning for both fixtures, including no-op selection, unknown files, stale plans, and exact undo.
- [ ] Document the optional operation and its scope; do not perform a migration as part of project discovery or initialization.
- [ ] Run `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v` and `python3 scripts/validate_distribution.py`.
- [ ] Run `python3 scripts/sync_claude_distribution.py --apply`, then `--check`, `python3 scripts/vendor_generic_skills.py --check`, and `python3 scripts/create_skill_zips.py`.
- [ ] Review the generated diff only for synchronization, confirm no Timeline Helper runtime or event schema was added, and commit.

## Deferred: Timeline Helper

The proposal's shared identities, scene/event links, event ordering, knowledge-state exchange, and rename behavior across both products need a separate design once Timeline Helper is ready. This plan neither reserves a specific ID format nor implements an integration. Existing free-form chronology notes continue to work.

## Completion criteria

The three agent-role fixtures pass; issue #10 is resolved; flat and nested projects pass the same core commands; chapter status changes preserve the path; a new project opens with a small useful tree; character extraction has preview and undo; migration is opt-in; all repository validation gates pass.

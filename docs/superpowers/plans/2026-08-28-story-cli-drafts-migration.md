# Story CLI Drafts and Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the staged draft lifecycle, conservative rebase, acceptance/abandonment, versioned migration plans, and lifecycle checks.

**Architecture:** Draft commands build transaction plans on top of the existing engine. Draft creation captures a recoverable normalized base, rebase performs a conservative non-overlapping three-way merge, acceptance changes only manuscript/archive/index paths, and migration converts known legacy roles while leaving semantic ambiguity to the agent.

**Tech Stack:** Python 3.10+ standard library (`difflib`, `hashlib`, `json`, `pathlib`), existing `cwcli` project/document/transaction interfaces, `unittest` fixtures for Layout A and Layout B.

**Spec:** `docs/superpowers/specs/2026-08-28-story-project-contract-cli-design.md`

## Global Constraints

- Complete the foundation and transactions/editing plans first.
- Authors never edit `base-revision`, migration hashes, or archive names by hand.
- Draft targets are only `story/chapters/*.md`; new targets omit `base-revision`.
- Acceptance does not update KB; knowledge promotion remains a separate later integration workflow.
- Rebase never guesses across overlapping edits and never mutates on conflict.
- Migration requires a schema-valid, unresolved-free, hash-matching preview plan.

---

### Task 1: Capture working drafts and recoverable base revisions

**Files:**
- Create: `plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/drafts.py`
- Modify: `plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/transactions.py`
- Create: `tests/cw_cli/test_draft_create.py`
- Test: `tests/cw_cli/test_draft_create.py`

**Interfaces:**
- Produces: `Draft(metadata, path, target, base_revision, status)`
- Produces: `load_draft(project: Project, path: str) -> Draft`
- Produces: `plan_create_draft(project, target: str, draft_path: str | None, store: TransactionStore) -> TransactionPlan`
- Produces: `TransactionStore.remember_revision(logical_hash: str, data: bytes) -> str`
- Produces: `TransactionStore.load_revision(logical_hash: str) -> bytes`

- [ ] **Step 1: Write failing existing-target and new-target tests**

```python
def test_create_draft_records_base_without_author_hash_work(self):
    root, project_model, store = self.make_project_with_chapter("ch-004.md", b"---\nnumber: 4\ntitle: Harbor\n---\nOld\n")
    plan = drafts.plan_create_draft(project_model, "story/chapters/ch-004.md", None, store=store)
    created = next(change for change in plan.changes if change.path.startswith("work/drafts/"))
    document = documents.parse_document(created.after)
    self.assertEqual(document.metadata["target"], "story/chapters/ch-004.md")
    self.assertEqual(document.metadata["base-revision"], documents.logical_hash((root / "story/chapters/ch-004.md").read_bytes()))
    self.assertEqual(store.load_revision(document.metadata["base-revision"]), (root / "story/chapters/ch-004.md").read_bytes())
```

Add a new `story/chapters/ch-005.md` target case asserting no `base-revision`, a target-outside-manuscript rejection, a duplicate active-draft rejection, and deterministic default path `work/drafts/ch-004.md`.

- [ ] **Step 2: Run focused tests and verify RED**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.cw_cli.test_draft_create -v`

Expected: FAIL because `cwcli.drafts` and revision storage are missing.

- [ ] **Step 3: Implement draft parsing and revision storage**

Store base bytes under the content store keyed by logical hash with an adjacent exact-byte hash in its small JSON descriptor. If a logical hash already exists with different exact bytes caused only by newline/BOM normalization, keep the first exact snapshot and verify its logical hash; never overwrite it.

`plan_create_draft()` copies the accepted chapter body and author-editable metadata into a new draft, then adds `target`, `base-revision` when present, and `status: working`. It does not change the manuscript.

- [ ] **Step 4: Run draft creation and transaction-store tests**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.cw_cli.test_draft_create tests.cw_cli.test_transactions_store -v`

Expected: PASS, including manually created manuscript targets.

- [ ] **Step 5: Commit draft creation**

```bash
git add plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/drafts.py plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/transactions.py tests/cw_cli/test_draft_create.py
git commit -m "feat: create recoverable working drafts"
```

### Task 2: Implement conservative three-way draft rebase

**Files:**
- Create: `plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/rebase.py`
- Modify: `plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/drafts.py`
- Create: `tests/cw_cli/test_draft_rebase.py`
- Test: `tests/cw_cli/test_draft_rebase.py`

**Interfaces:**
- Produces: `TextEdit(start: int, end: int, replacement: tuple[str, ...])`
- Produces: `RebaseResult(text: str | None, conflicts: tuple[RebaseConflict, ...])`
- Produces: `three_way_rebase(base: str, draft: str, current: str) -> RebaseResult`
- Produces: `plan_rebase_draft(project, draft_path, store) -> TransactionPlan`

- [ ] **Step 1: Write failing disjoint-edit and overlapping-conflict tests**

```python
def test_disjoint_manual_and_draft_edits_merge(self):
    base = "one\ntwo\nthree\n"
    draft = "one\nTWO\nthree\n"
    current = "one\ntwo\nTHREE\n"
    result = rebase.three_way_rebase(base, draft, current)
    self.assertEqual(result.conflicts, ())
    self.assertEqual(result.text, "one\nTWO\nTHREE\n")

def test_same_span_edits_conflict_without_output(self):
    result = rebase.three_way_rebase("one\ntwo\n", "one\nDRAFT\n", "one\nAUTHOR\n")
    self.assertIsNone(result.text)
    self.assertEqual(len(result.conflicts), 1)
```

Add insertion-at-same-boundary conflict, current-equals-base fast path, draft-equals-base fast path, Russian lines, and missing-base-snapshot cases.

- [ ] **Step 2: Run focused tests and verify RED**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.cw_cli.test_draft_rebase -v`

Expected: FAIL because `cwcli.rebase` is missing.

- [ ] **Step 3: Implement non-overlapping edit extraction**

Use `difflib.SequenceMatcher(a=base.splitlines(keepends=True), b=variant.splitlines(keepends=True), autojunk=False)` to convert non-`equal` opcodes into `TextEdit` ranges. Two edits conflict when their base ranges overlap or both insert different text at the same base boundary. After the full conflict scan passes, merge the two edit lists by `(start, end)`, emit untouched base slices between them, and emit each edit's replacement. This avoids applying offsets from one variant to the other.

- [ ] **Step 4: Build rebase transaction plans**

Load the base snapshot by `base-revision`, compare current target logical hash, and return a no-op when it still equals the base. On a clean merge, change only the draft body and its CLI-managed `base-revision` to the current target hash, remembering current target bytes first. On conflict, raise `DraftConflict` containing base/draft/current fragments and no `TransactionPlan`.

- [ ] **Step 5: Run rebase tests**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.cw_cli.test_draft_rebase -v`

Expected: PASS; every conflict leaves draft and manuscript bytes unchanged.

- [ ] **Step 6: Commit conservative rebase**

```bash
git add plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/rebase.py plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/drafts.py tests/cw_cli/test_draft_rebase.py
git commit -m "feat: rebase drafts without guessing"
```

### Task 3: Accept and abandon drafts without touching KB

**Files:**
- Modify: `plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/drafts.py`
- Modify: `plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/indexes.py`
- Create: `tests/cw_cli/test_draft_lifecycle.py`
- Test: `tests/cw_cli/test_draft_lifecycle.py`

**Interfaces:**
- Produces: `plan_accept_draft(project, draft_path, store, transaction_id) -> TransactionPlan`
- Produces: `plan_abandon_draft(project, draft_path, transaction_id) -> TransactionPlan`

- [ ] **Step 1: Write failing acceptance-boundary tests**

```python
def test_accept_changes_story_archive_and_indexes_but_not_kb(self):
    root, project_model, store = self.make_ready_draft()
    kb_before = {p: p.read_bytes() for p in (root / "kb").rglob("*") if p.is_file()}
    plan = drafts.plan_accept_draft(project_model, "work/drafts/ch-004.md", store, "tx-accept")
    changed = {change.path for change in plan.changes}
    self.assertIn("story/chapters/ch-004.md", changed)
    self.assertIn("work/archive/ch-004--tx-accept.md", changed)
    self.assertFalse(any(path.startswith("kb/") and not path.endswith("_index.md") for path in changed))
    self.assertEqual(kb_before, {p: p.read_bytes() for p in (root / "kb").rglob("*") if p.is_file()})
```

Add stale-base refusal, status-not-ready refusal, balanced `<AI>` wrapper removal in preview, unresolved `<hidden>` refusal, archive collision-proof naming, and abandoned archive status.

- [ ] **Step 2: Run focused tests and verify RED**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.cw_cli.test_draft_lifecycle -v`

Expected: FAIL because lifecycle planners are missing.

- [ ] **Step 3: Implement acceptance and archive rendering**

Validate the current target logical hash before planning. Strip only the literal balanced `<AI>`/`</AI>` wrappers while preserving their content. Reject any `<hidden>` block. Remove draft-only frontmatter keys from the manuscript result, render archive metadata with `status: accepted` and `accepted-transaction: tx-id`, delete the active draft, and include regenerated story/work indexes in the same plan.

- [ ] **Step 4: Implement abandonment**

Move the draft to `work/archive/<stem>--<transaction-id>.md`, set `status: abandoned` and `abandoned-transaction`, update work indexes, and never create or alter a story target.

- [ ] **Step 5: Run lifecycle and transaction tests**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.cw_cli.test_draft_lifecycle tests.cw_cli.test_transactions_apply -v`

Expected: PASS with no KB content changes.

- [ ] **Step 6: Commit draft lifecycle**

```bash
git add plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/drafts.py plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/indexes.py tests/cw_cli/test_draft_lifecycle.py
git commit -m "feat: accept and archive story drafts"
```

### Task 4: Generate and validate versioned migration plans

**Files:**
- Create: `plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/migration.py`
- Create: `tests/cw_cli/test_migration_plan.py`
- Create: `tests/fixtures/cw-layout-a/README.md`
- Create: `tests/fixtures/cw-layout-b/README.md`
- Test: `tests/cw_cli/test_migration_plan.py`

**Interfaces:**
- Produces: `MigrationOperation(source: str, destination: str, action: str)`
- Produces: `MigrationPlan(plan_version, source_schema, target_schema, operations, unresolved, plan_hash)`
- Produces: `plan_migration(root: Path) -> MigrationPlan`
- Produces: `load_migration_plan(path: Path) -> MigrationPlan`
- Produces: `canonical_plan_hash(payload: dict[str, object]) -> str`

- [ ] **Step 1: Write failing fixed-mapping and ambiguity tests**

```python
def test_layout_b_known_roles_map_without_guessing(self):
    root = self.materialize_layout_b()
    plan = migration.plan_migration(root)
    pairs = {(op.source, op.destination) for op in plan.operations}
    self.assertIn(("work/outline/arc.md", "work/plans/arc.md"), pairs)
    self.assertIn(("kb/timeline.md", "kb/continuity/timeline.md"), pairs)
    self.assertIn(("kb/samples/voice.md", "kb/samples/voice.md"), pairs)

def test_multiple_timeline_files_remain_unresolved(self):
    root = self.materialize_layout_b(extra={"kb/timeline/arc-two.md": "# Two\n"})
    plan = migration.plan_migration(root)
    self.assertTrue(any(item["reason"] == "timeline-merge" for item in plan.unresolved))
```

Cover every mapping row from the spec, mixed Layout A/B evidence, domain vocab merges, platform-specific instruction files proposed for `project.md`, and unknown files preserved as unmanaged.

- [ ] **Step 2: Run focused tests and verify RED**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.cw_cli.test_migration_plan -v`

Expected: FAIL because `cwcli.migration` is missing.

- [ ] **Step 3: Implement role discovery and canonical JSON hashing**

Serialize the plan payload without `plan_hash` using `json.dumps(..., sort_keys=True, separators=(",", ":"), ensure_ascii=False)`, hash UTF-8 bytes with SHA-256, and store the result. Reject unknown plan keys, `plan-version != 1`, target schema other than `1`, duplicate destinations, path escapes, and operations crossing a nested project.

- [ ] **Step 4: Generate fixture contents from test helpers**

Keep README files in fixture directories and create legacy structures in temporary directories from explicit dictionaries in `tests/cw_cli/test_migration_plan.py`. This keeps every legacy role visible in the test without committing empty directories.

- [ ] **Step 5: Run migration-plan tests**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.cw_cli.test_migration_plan -v`

Expected: PASS with stable plan hashes across repeated runs.

- [ ] **Step 6: Commit migration planning**

```bash
git add plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/migration.py tests/cw_cli/test_migration_plan.py tests/fixtures/cw-layout-a tests/fixtures/cw-layout-b
git commit -m "feat: plan canonical story migrations"
```

### Task 5: Apply migrations and expose draft/migration commands

**Files:**
- Modify: `plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/migration.py`
- Modify: `plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/app.py`
- Create: `plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/checks/drafts.py`
- Create: `tests/cw_cli/test_draft_commands.py`
- Create: `tests/cw_cli/test_migration_apply.py`
- Test: `tests/cw_cli/test_draft_commands.py`
- Test: `tests/cw_cli/test_migration_apply.py`

**Interfaces:**
- Produces: `plan_apply_migration(root, plan, expected_hash) -> TransactionPlan`
- Produces: `plan_set_draft_status(project, draft_path, status) -> TransactionPlan`
- Produces: `check_drafts(project: Project, store: TransactionStore) -> list[Finding]`
- Produces: CLI `cw draft create|set-status|rebase|accept|abandon`
- Produces: CLI `cw migrate --plan` and `cw migrate --apply plan.json --expect-plan-hash HASH`

- [ ] **Step 1: Write failing plan-integrity and lifecycle-command tests**

```python
def test_apply_rejects_changed_or_unresolved_plan(self):
    root, plan_path, shown_hash = self.preview_migration()
    payload = json.loads(plan_path.read_text())
    payload["operations"][0]["destination"] = "story/chapters/changed.md"
    plan_path.write_text(json.dumps(payload), encoding="utf-8")
    result = self.run_cli(root, ["migrate", "--apply", str(plan_path), "--expect-plan-hash", shown_hash])
    self.assertEqual(result.status, 1)
    self.assertFalse((root / "story/chapters/changed.md").exists())
```

Add draft command preview/apply tests, allowed `working|review|ready` status transitions, invalid-status refusal, JSON conflict output, migration undo round trip, post-migration structure check, and check findings for stale/unresolvable drafts.

- [ ] **Step 2: Run focused tests and verify RED**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.cw_cli.test_draft_commands tests.cw_cli.test_migration_apply -v`

Expected: FAIL because command handlers and migration application are missing.

- [ ] **Step 3: Convert migration operations into one transaction plan**

Recompute and compare the plan hash before resolving any source path. Require `unresolved == []`. Convert moves into paired delete/create changes, preserve exact bytes, add the canonical scaffold, and regenerate indexes. Validate every destination before constructing the plan.

- [ ] **Step 4: Wire command handlers through the shared preview/apply path**

Allocate transaction IDs before archive-name planning. Route `set-status` through `plan_set_draft_status()` so generic edits remain unable to change lifecycle metadata. Use status `1` for stale draft, rebase conflict, incomplete plan, invalid transition, or hash mismatch; status `2` only for runtime failure. Emit complete conflict fragments and plan hashes in JSON.

- [ ] **Step 5: Implement draft checker severity policy**

Report missing optional metadata and abandoned files left active as warnings; report an invalid target, duplicate active target, or unrecoverable base as errors only for commands that require that draft. `cw check drafts` still completes and does not prevent unrelated review.

- [ ] **Step 6: Run draft/migration and full CLI tests**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.cw_cli.test_draft_commands tests.cw_cli.test_migration_apply tests.cw_cli.test_draft_rebase tests.cw_cli.test_draft_lifecycle -v`

Expected: PASS.

- [ ] **Step 7: Commit command integration**

```bash
git add plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/app.py plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/migration.py plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/checks/drafts.py tests/cw_cli/test_draft_commands.py tests/cw_cli/test_migration_apply.py
git commit -m "feat: manage drafts and story migrations"
```

### Task 6: Verify draft and migration milestone

**Files:**
- Modify only files from Tasks 1–5 if verification exposes a defect.

**Interfaces:**
- Produces: an agent-operable staged manuscript lifecycle and reversible legacy migration.

- [ ] **Step 1: Run all CLI tests**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/cw_cli -t . -v`

Expected: all CLI tests pass.

- [ ] **Step 2: Run a manual temporary-folder lifecycle smoke test**

Use `mktemp -d`, apply `cw init`, create `ch-001` as a new draft, edit it manually, set its status with `cw draft set-status ... ready --apply`, preview and apply acceptance, then inspect `history` and `work/archive/`.

Expected: accepted prose is under `story/chapters/`, the draft archive name contains its transaction ID, and no KB content file changed.

- [ ] **Step 3: Run both legacy migration fixtures through preview/apply/undo**

Materialize the Layout A and Layout B fixture dictionaries in temporary directories, resolve only the explicitly expected merge entries in the plan JSON, preview the new plan hash, apply, run `check structure`, and undo.

Expected: canonical structure after apply; exact legacy bytes and paths after undo.

- [ ] **Step 4: Run repository distribution checks**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v && python3 scripts/validate_distribution.py && python3 scripts/sync_claude_distribution.py --check`

Expected: all commands exit `0`.

- [ ] **Step 5: Commit only verification fixes, if any**

Stage the exact files changed by a verified fix and commit:

```bash
git commit -m "fix: stabilize draft and migration workflows"
```

Skip when the working tree has no milestone fixes.

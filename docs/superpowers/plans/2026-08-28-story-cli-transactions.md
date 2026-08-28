# Story CLI Transactions and Editing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add crash-recoverable transactions, exact-anchor and batch editing, history/undo, reindexing, and safe scaffold application to the foundation CLI.

**Architecture:** Every mutation becomes an immutable `TransactionPlan` of byte-level changes. `TransactionStore` persists manifests and content-addressed blobs before `TransactionEngine` performs guarded sibling-file replacements; editing, indexes, initialization, and undo all reuse this path.

**Tech Stack:** Python 3.10+ standard library (`dataclasses`, `hashlib`, `json`, `os`, `pathlib`, `tempfile`, `uuid`, `difflib`), `unittest` with injected filesystem failures.

**Spec:** `docs/superpowers/specs/2026-08-28-story-project-contract-cli-design.md`

## Global Constraints

- Complete `2026-08-28-story-cli-foundation.md` first.
- No mutation may follow symlinks, leave the nearest project, enter a nested project, or target `.creative-writing/`.
- Previews are the default; non-interactive mutation requires `--apply`.
- Recovery snapshots preserve exact bytes; logical text matching normalizes line endings and preserves the target's newline convention on write.
- Generic text edits cannot modify generated `_index.md` or CLI-managed lifecycle frontmatter.
- No Git dependency, daemon, advisory lock, or automatic journal pruning.

---

### Task 1: Define transaction plans, manifests, and content-addressed storage

**Files:**
- Create: `plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/transactions.py`
- Create: `tests/cw_cli/test_transactions_store.py`
- Test: `tests/cw_cli/test_transactions_store.py`

**Interfaces:**
- Produces: `Change(path: str, before: bytes | None, after: bytes | None)`
- Produces: `TransactionPlan(command: list[str], changes: tuple[Change, ...], metadata: dict[str, object])`
- Produces: `TransactionRecord(id: str, state: str, completed: tuple[str, ...])`
- Produces: `TransactionStore(project).prepare(plan) -> TransactionRecord`
- Produces: `TransactionStore.load(id)`, `.write_state(id, state, completed=())`, `.blob(data) -> str`

- [ ] **Step 1: Write failing immutable-manifest and blob-deduplication tests**

```python
class TransactionStoreTests(unittest.TestCase):
    def test_prepare_persists_before_after_blobs_once(self):
        store = self.make_store()
        plan = transactions.TransactionPlan(
            command=("edit", "replace"),
            changes=(transactions.Change("story/chapters/ch-001.md", b"old\n", b"new\n"),),
            metadata={},
        )
        record = store.prepare(plan, transaction_id="tx-test")
        self.assertEqual(record.state, "prepared")
        manifest = json.loads((store.root / "tx-test/manifest.json").read_text())
        self.assertEqual(manifest["state"], "prepared")
        self.assertEqual(len(list((store.root / "blobs").iterdir())), 2)
        with self.assertRaises(FileExistsError):
            store.prepare(plan, transaction_id="tx-test")
```

Add a second change reusing `b"old\n"` and assert the blob count remains two. Assert manifests contain command, timestamps, relative paths, byte hashes, logical hashes, blob IDs, and unified diff text.

- [ ] **Step 2: Run the focused test and verify RED**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.cw_cli.test_transactions_store -v`

Expected: FAIL because `cwcli.transactions` is missing.

- [ ] **Step 3: Implement atomic manifest writes and deduplicated blobs**

```python
@dataclass(frozen=True)
class Change:
    path: str
    before: bytes | None
    after: bytes | None

@dataclass(frozen=True)
class TransactionPlan:
    command: tuple[str, ...]
    changes: tuple[Change, ...]
    metadata: dict[str, object]
```

Store blobs as `.creative-writing/transactions/blobs/<sha256>`. Write JSON to a sibling temporary file, `flush()`, `os.fsync()`, then `os.replace()` it. Reject an existing transaction ID rather than merging records.

- [ ] **Step 4: Run store tests**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.cw_cli.test_transactions_store -v`

Expected: PASS with deterministic manifest ordering and no duplicate blobs.

- [ ] **Step 5: Commit transaction persistence**

```bash
git add plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/transactions.py tests/cw_cli/test_transactions_store.py
git commit -m "feat: persist cw transaction plans"
```

### Task 2: Apply transactions and roll back interrupted commits

**Files:**
- Modify: `plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/transactions.py`
- Create: `tests/cw_cli/test_transactions_apply.py`
- Test: `tests/cw_cli/test_transactions_apply.py`

**Interfaces:**
- Consumes: `TransactionStore.prepare()` and `Project.resolve()`
- Produces: `TransactionEngine.preview(plan) -> dict[str, object]`
- Produces: `TransactionEngine.apply(plan, *, transaction_id=None) -> TransactionRecord`
- Produces: `TransactionEngine.recover(transaction_id) -> TransactionRecord`

- [ ] **Step 1: Write failing success, stale-precondition, and injected-crash tests**

```python
def test_failure_after_first_replace_restores_every_target(self):
    root, engine = self.make_engine({"story/a.md": b"A\n", "story/b.md": b"B\n"})
    plan = TransactionPlan(("edit", "apply"), (
        Change("story/a.md", b"A\n", b"A2\n"),
        Change("story/b.md", b"B\n", b"B2\n"),
    ), {})
    calls = 0
    def fail_on_second_replace(source, destination):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("injected")
        os.replace(source, destination)
    engine.replace_hook = fail_on_second_replace
    with self.assertRaisesRegex(TransactionError, "rolled back"):
        engine.apply(plan, transaction_id="tx-fail")
    self.assertEqual((root / "story/a.md").read_bytes(), b"A\n")
    self.assertEqual((root / "story/b.md").read_bytes(), b"B\n")
    self.assertEqual(engine.store.load("tx-fail").state, "rolled-back")
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.cw_cli.test_transactions_apply -v`

Expected: FAIL because `TransactionEngine` is missing.

- [ ] **Step 3: Implement `prepared → applying → committed|rolled-back`**

For every target, validate current exact bytes against `before`, write `after` to a temporary sibling, and revalidate all targets before the first replacement. Mark `applying`, append each completed relative path to the manifest, and mark `committed` only after every replacement. On any exception, restore completed paths from before-blobs in reverse order and mark `rolled-back`.

- [ ] **Step 4: Implement deterministic restart recovery**

`recover()` accepts only `prepared` or `applying`, restores every target whose path appears in `completed`, removes uninstalled temporary siblings, and marks `rolled-back`. It never rolls forward.

- [ ] **Step 5: Run apply and store tests**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.cw_cli.test_transactions_store tests.cw_cli.test_transactions_apply -v`

Expected: PASS, including stale manual edits remaining untouched.

- [ ] **Step 6: Commit the transaction engine**

```bash
git add plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/transactions.py tests/cw_cli/test_transactions_apply.py
git commit -m "feat: apply recoverable file transactions"
```

### Task 3: Add exact-anchor editing and JSON batch plans

**Files:**
- Create: `plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/edits.py`
- Create: `tests/cw_cli/test_edits.py`
- Test: `tests/cw_cli/test_edits.py`

**Interfaces:**
- Produces: `load_operations(path: Path) -> tuple[EditOperation, ...]`
- Produces: `plan_edits(project: Project, operations: Iterable[EditOperation]) -> TransactionPlan`
- Supports operation kinds: `replace`, `insert-before`, `insert-after`, `delete`, `frontmatter-set`

- [ ] **Step 1: Write failing unique-anchor and deliberate-repeat tests**

```python
def test_repeated_text_requires_explicit_count(self):
    root = self.make_project_file("story/chapters/ch-001.md", "Rain.\nRain.\n")
    with self.assertRaisesRegex(edits.EditConflict, "found 2"):
        edits.plan_edits(root.project, [{"op": "replace", "path": "story/chapters/ch-001.md", "old": "Rain.", "new": "Snow."}])
    plan = edits.plan_edits(root.project, [{
        "op": "replace", "path": "story/chapters/ch-001.md", "old": "Rain.", "new": "Snow.", "expect-count": 2,
    }])
    self.assertIn(b"Snow.\nSnow.\n", plan.changes[0].after)
```

Add tests for zero matches, before/after insertion, deletion, `all: true`, CRLF preservation, Russian anchors, generated-index refusal, `.creative-writing/` refusal, and protected `base-revision` refusal.

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.cw_cli.test_edits -v`

Expected: FAIL because `cwcli.edits` is missing.

- [ ] **Step 3: Implement normalized matching with original newline rendering**

```python
def _match_count(text: str, needle: str) -> int:
    return text.count(needle)

def _require_count(actual: int, operation: dict[str, object]) -> None:
    if operation.get("all") is True:
        if actual == 0:
            raise EditConflict("expected at least one match, found 0")
        return
    expected = int(operation.get("expect-count", 1))
    if actual != expected:
        raise EditConflict(f"expected {expected} match(es), found {actual}")
```

Convert normalized LF output back to the document's original newline before constructing `Change.after`.

- [ ] **Step 4: Add strict JSON operation schema validation**

Reject unknown keys, unknown operation kinds, absolute paths, missing content files, simultaneous `expect-count` and `all`, and non-integer counts before reading or changing any target. `frontmatter-set` must reject `schema-version`, `base-revision`, and lifecycle statuses owned by domain commands.

- [ ] **Step 5: Run edit tests**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.cw_cli.test_edits -v`

Expected: PASS with no filesystem changes during planning.

- [ ] **Step 6: Commit exact editing**

```bash
git add plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/edits.py tests/cw_cli/test_edits.py
git commit -m "feat: plan exact story file edits"
```

### Task 4: Expose edit preview/apply, history, and undo commands

**Files:**
- Modify: `plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/app.py`
- Modify: `plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/transactions.py`
- Create: `tests/cw_cli/test_edit_commands.py`
- Create: `tests/cw_cli/test_history.py`
- Test: `tests/cw_cli/test_edit_commands.py`
- Test: `tests/cw_cli/test_history.py`

**Interfaces:**
- Produces: CLI `cw edit replace|insert-before|insert-after|delete`
- Produces: CLI `cw edit apply operations.json [--apply] [--format text|json]`
- Produces: CLI `cw history`, `cw history show ID`, `cw undo ID [--apply]`
- Produces: `TransactionEngine.inverse(id) -> TransactionPlan`

- [ ] **Step 1: Write failing preview-does-not-write and apply-does-write tests**

```python
def test_edit_preview_is_read_only_and_apply_is_journaled(self):
    root = self.make_project()
    target = root / "story/chapters/ch-001.md"
    before = target.read_bytes()
    argv = ["edit", "replace", str(target), "--old-file", "old.txt", "--new-file", "new.txt", "--format", "json"]
    preview = self.run_cli(root, argv)
    self.assertEqual(preview.status, 0)
    self.assertEqual(target.read_bytes(), before)
    applied = self.run_cli(root, argv + ["--apply"])
    self.assertEqual(applied.status, 0)
    self.assertNotEqual(target.read_bytes(), before)
    self.assertEqual(len(list((root / ".creative-writing/transactions").glob("*/manifest.json"))), 1)
```

The test helper must write `old.txt` and `new.txt` inside a temporary caller directory and pass their absolute paths as content inputs, not mutation targets.

- [ ] **Step 2: Run command tests and verify RED**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.cw_cli.test_edit_commands tests.cw_cli.test_history -v`

Expected: FAIL because the command handlers and inverse plans are missing.

- [ ] **Step 3: Implement shared preview/apply command handling**

Add one helper in `app.py` that renders `TransactionEngine.preview(plan)` and calls `apply()` only with `--apply`. Return `1` for edit conflicts and stale preconditions, `2` for execution/runtime failures, and provide the same structured fields in text and JSON modes.

- [ ] **Step 4: Implement history and inverse transactions**

List transaction manifests newest first without reading blobs. `history show` includes the stored unified diff. `inverse()` requires a committed, undoable transaction and exact current after-bytes, then swaps before/after for every change. Applying the inverse creates a new transaction with `metadata["undo-of"] = original_id`.

- [ ] **Step 5: Run command tests and apply/undo round trips**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.cw_cli.test_edit_commands tests.cw_cli.test_history -v`

Expected: PASS; undo after a manual edit returns `1` and preserves that edit.

- [ ] **Step 6: Commit command integration**

```bash
git add plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/app.py plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/transactions.py tests/cw_cli/test_edit_commands.py tests/cw_cli/test_history.py
git commit -m "feat: expose journaled cw editing"
```

### Task 5: Add derived indexes and transactional initialization

**Files:**
- Create: `plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/indexes.py`
- Modify: `plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/app.py`
- Modify: `plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/scaffold.py`
- Create: `tests/cw_cli/test_indexes.py`
- Create: `tests/cw_cli/test_init_command.py`
- Test: `tests/cw_cli/test_indexes.py`
- Test: `tests/cw_cli/test_init_command.py`

**Interfaces:**
- Produces: `plan_reindex(project: Project) -> TransactionPlan`
- Produces: `plan_init(target: Path, title: str, language: str) -> TransactionPlan`
- Produces: CLI `cw reindex [--apply]`
- Replaces: foundation's preview-only `cw init` guard with transactional `cw init [--apply]`

- [ ] **Step 1: Write failing generated-index and nonempty-folder tests**

```python
def test_init_existing_folder_preserves_unknown_files(self):
    root = self.temporary_root()
    (root / "notes.txt").write_text("mine\n", encoding="utf-8")
    result = self.run_cli(root.parent, ["init", str(root), "--title", "Mine", "--language", "ru", "--apply"])
    self.assertEqual(result.status, 0)
    self.assertEqual((root / "notes.txt").read_text(), "mine\n")
    self.assertTrue((root / "project.md").is_file())
```

Add tests that populated managed paths switch to migration guidance, init records `undoable: false`, `cw undo` refuses bootstrap, and reindex never includes archived or unmanaged documents.

- [ ] **Step 2: Run focused tests and verify RED**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.cw_cli.test_indexes tests.cw_cli.test_init_command -v`

Expected: FAIL because index planning and transactional init are missing.

- [ ] **Step 3: Implement deterministic index renderers**

Render registries from sorted project-relative IDs and type-specific frontmatter. Preserve no manual index body because indexes are fully derived. Produce no `Change` when bytes already match.

- [ ] **Step 4: Implement init for absent and existing ordinary folders**

For an absent target, create a temporary sibling project, write the committed non-undoable bootstrap manifest inside it, fsync, then rename it into place. For an existing directory with no managed content, create only missing scaffold files through a bootstrap plan and preserve all unknown entries. Refuse existing `project.md` with an incompatible schema and return migration guidance for populated managed roots.

- [ ] **Step 5: Run index/init and transaction tests**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.cw_cli.test_indexes tests.cw_cli.test_init_command tests.cw_cli.test_transactions_apply -v`

Expected: PASS, including preview-only default behavior.

- [ ] **Step 6: Commit transactional scaffold maintenance**

```bash
git add plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/indexes.py plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/app.py plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/scaffold.py tests/cw_cli/test_indexes.py tests/cw_cli/test_init_command.py
git commit -m "feat: initialize story projects transactionally"
```

### Task 6: Verify transaction and editing milestone

**Files:**
- Modify only files from Tasks 1–5 if verification exposes a defect.

**Interfaces:**
- Produces: safe init, reindex, edit, history, recovery, and undo commands.

- [ ] **Step 1: Run all CLI tests**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/cw_cli -t . -v`

Expected: all CLI tests pass.

- [ ] **Step 2: Run packaged CLI smoke scenarios**

Run the packaged `cw.py` against a temporary project: preview init, apply init, exact replace, history show, undo, reindex, and `check structure`. Use `mktemp -d` for the explicit target and do not remove any workspace path.

Expected: every command exits `0`; the final chapter bytes equal the pre-edit bytes; history contains the edit and inverse transactions.

- [ ] **Step 3: Run repository and distribution checks**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v && python3 scripts/validate_distribution.py && python3 scripts/sync_claude_distribution.py --check`

Expected: all commands exit `0` and canonical/generated CLI files remain identical.

- [ ] **Step 4: Commit only verification fixes, if any**

Stage the exact files changed to fix failing milestone tests and commit:

```bash
git commit -m "fix: stabilize cw transaction workflows"
```

Skip this step when verification leaves the working tree unchanged.

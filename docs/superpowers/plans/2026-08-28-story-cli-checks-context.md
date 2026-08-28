# Story CLI Checks, Context, and Doctor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the deterministic check registry, context planner and restricted snapshots, project doctor, context cleanup, and CLI environment doctor without turning repairable author edits into workflow blockers.

**Architecture:** Independent checker modules return the shared `Finding` model and never mutate. A context planner consumes explicit paths and checker output, while a separate snapshot renderer applies only mechanical redaction rules. Doctor groups the same findings into an agent-oriented repair plan; repairs remain explicit transaction commands.

**Tech Stack:** Python 3.10+ standard library (`argparse`, `dataclasses`, `hashlib`, `html`, `json`, `pathlib`, `re`, `shutil`, `subprocess`, `sys`), existing `cwcli` project/document/transaction interfaces, `unittest` golden fixtures.

**Spec:** `docs/superpowers/specs/2026-08-28-story-project-contract-cli-design.md`

## Global Constraints

- Complete the foundation, transactions, and drafts/migration plans first.
- Every checker completes as far as possible and returns stable findings; malformed one-file input must not abort unrelated checks.
- Warnings and informational findings never block reading, context preparation, research, or unrelated mutations.
- `doctor` and `context` planning are read-only. Restricted snapshots are derived cache files, not canon and not journal transactions.
- Redaction removes only explicit structured material. It must report when an ordinary prose knowledge boundary cannot be guaranteed.
- Port existing continuity and prose behavior before retiring either standalone checker.

---

### Task 1: Add shared Markdown tables and port continuity checks with parity tests

**Files:**
- Create: `plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/markdown_tables.py`
- Create: `plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/checks/continuity.py`
- Create: `tests/cw_cli/test_markdown_tables.py`
- Create: `tests/cw_cli/test_continuity_check.py`
- Test: `plugins/creative-writing-skills/skills/story-memory/resources/continuity_check.py`
- Test: `tests/cw_cli/test_markdown_tables.py`
- Test: `tests/cw_cli/test_continuity_check.py`

**Interfaces:**
- Produces: `MarkdownTable(headers: tuple[str, ...], rows: tuple[TableRow, ...])`
- Produces: `parse_tables(text: str) -> tuple[MarkdownTable, ...]`
- Produces: `check_continuity(project: Project) -> list[Finding]`
- Preserves: deaths, promises, questions, knowledge order, scene cast, and timeline-anchor checks from the existing checker

- [ ] **Step 1: Write failing table-parser and legacy-parity tests**

```python
class ContinuityParityTests(unittest.TestCase):
    def test_deceased_character_in_later_scene_keeps_legacy_detection(self):
        root = self.make_project(
            state="| character | state | since |\n|---|---|---|\n| mara | dead | ch-002 |\n",
            scene="| chapter | cast |\n|---|---|\n| ch-004 | mara, ivo |\n",
        )
        findings = continuity.check_continuity(project.discover_project(root))
        self.assertIn("CW-CONT-020", {item.code for item in findings})
```

Add table tests for escaped pipes, surrounding whitespace, missing delimiter rows, Russian cells, source line numbers, and non-table prose. Add parity fixtures for every rule currently implemented in `story-memory/resources/continuity_check.py` and assert equivalent detection, not identical wording.

- [ ] **Step 2: Run focused tests and verify RED**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.cw_cli.test_markdown_tables tests.cw_cli.test_continuity_check -v`

Expected: FAIL because the shared parser and new checker do not exist.

- [ ] **Step 3: Implement a conservative table parser**

Split only unescaped `|`, preserve cell text, record the one-based source line, and recognize a table only when a delimiter row follows its header. Return partial parse warnings from the checker rather than guessing column meaning.

- [ ] **Step 4: Port continuity rules into stable finding codes**

Use explicit structured records under `kb/continuity/`. Resolve character IDs through `kb/characters/<id>.md`; unknown IDs produce warnings. Keep the current checker available and run both implementations over parity fixtures until the new result covers every legacy rule.

- [ ] **Step 5: Run parity and project tests**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.cw_cli.test_markdown_tables tests.cw_cli.test_continuity_check tests.cw_cli.test_structure_check -v`

Expected: PASS; unstructured literary implications do not create continuity findings.

- [ ] **Step 6: Commit the continuity port**

```bash
git add plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/markdown_tables.py plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/checks/continuity.py tests/cw_cli/test_markdown_tables.py tests/cw_cli/test_continuity_check.py
git commit -m "feat: check structured story continuity"
```

### Task 2: Port bilingual prose metrics and Markdown integrity checks

**Files:**
- Create: `plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/checks/prose.py`
- Create: `tests/cw_cli/test_prose_check.py`
- Test: `plugins/creative-writing-skills/skills/story-review/resources/prose-critique/analyze.py`
- Test: `tests/cw_cli/test_prose_check.py`

**Interfaces:**
- Produces: `ProseMetrics(word_count, paragraph_count, sentence_count, dialogue_ratio, repeated_openings, language)`
- Produces: `analyze_prose(text: str, *, language: str) -> ProseMetrics`
- Produces: `check_prose(project: Project) -> list[Finding]`

- [ ] **Step 1: Write failing Russian/English parity and integrity tests**

```python
class ProseCheckTests(unittest.TestCase):
    def test_russian_words_are_counted_without_splitting_cyrillic(self):
        metrics = prose.analyze_prose("Она вошла. Он молчал.\n", language="ru")
        self.assertEqual(metrics.word_count, 5)
        self.assertEqual(metrics.sentence_count, 2)

    def test_unbalanced_source_tag_is_a_mechanical_warning(self):
        root = self.make_chapter("<AI>Текст без закрывающего тега\n")
        result = prose.check_prose(project.discover_project(root))
        self.assertIn("CW-PROSE-010", {item.code for item in result})
```

Port representative RU/EN fixtures from the current `analyze.py` behavior. Add tests for balanced `<AI>` and `<hidden>` tags, Markdown fences, empty documents, repeated paragraph openings, and language inherited from `project.md`.

- [ ] **Step 2: Run focused tests and verify RED**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.cw_cli.test_prose_check -v`

Expected: FAIL because `cwcli.checks.prose` is missing.

- [ ] **Step 3: Implement deterministic bilingual tokenization**

Use Unicode-aware regular expressions for Latin and Cyrillic words, retaining the existing Russian pronoun handling and metrics. Findings describe counts and structural signals only; they never label prose as good, bad, publishable, or stylistically wrong.

- [ ] **Step 4: Run parity tests against the standalone analyzer**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.cw_cli.test_prose_check -v`

Expected: PASS for RU/EN fixtures and Markdown integrity cases.

- [ ] **Step 5: Commit the prose port**

```bash
git add plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/checks/prose.py tests/cw_cli/test_prose_check.py
git commit -m "feat: add bilingual prose checks"
```

### Task 3: Implement links, KB provenance, journal, and complete check registry

**Files:**
- Modify: `plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/checks/__init__.py`
- Create: `plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/checks/links.py`
- Create: `plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/checks/kb.py`
- Create: `plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/checks/journal.py`
- Modify: `plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/app.py`
- Create: `tests/cw_cli/test_links_check.py`
- Create: `tests/cw_cli/test_kb_check.py`
- Create: `tests/cw_cli/test_journal_check.py`
- Create: `tests/cw_cli/test_check_commands.py`
- Test: `tests/cw_cli/test_check_commands.py`

**Interfaces:**
- Produces: `CHECKERS: dict[str, Callable[[Project], list[Finding]]]`
- Produces: `run_checks(project, names: Iterable[str]) -> Report`
- Produces: CLI `cw check structure|links|kb|continuity|drafts|prose|journal|all`
- Produces: JSON `{"checks": [...], "findings": [...], "execution_errors": [...], "strict_failure": bool}`

- [ ] **Step 1: Write failing independent-check and provenance tests**

```python
def test_work_file_cannot_be_the_only_durable_kb_source(self):
    root = self.make_kb_page(sources=["work/brainstorm/idea.md"])
    report = kb.check_kb(project.discover_project(root))
    finding = next(item for item in report if item.code == "CW-KB-020")
    self.assertEqual(finding.severity, "warning")
    self.assertIn("confirm", finding.next_action)

def test_check_all_continues_after_one_malformed_document(self):
    root = self.make_project_with_malformed_kb()
    result = self.run_cli(root, ["check", "all", "--format", "json"])
    payload = json.loads(result.stdout)
    self.assertEqual(payload["checks"], sorted(checks.CHECKERS))
    self.assertGreater(len(payload["findings"]), 1)
```

Add links tests for missing local targets, valid external URLs, parent/sibling/nested-project references as informational external links, target-class mismatch, orphan pages, and index drift. Add journal tests for corrupt blobs, logical/exact hash mismatches, and recoverable `prepared`/`applying` transactions.

- [ ] **Step 2: Run focused tests and verify RED**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.cw_cli.test_links_check tests.cw_cli.test_kb_check tests.cw_cli.test_journal_check tests.cw_cli.test_check_commands -v`

Expected: FAIL because the checker modules and registry are incomplete.

- [ ] **Step 3: Implement links and KB checks without semantic guesses**

Parse explicit Markdown links and `sources` metadata. Durable KB sources may be accepted `story/` files, live `kb/` pages, external URLs, or `decision:<transaction-id>`. A `work/` source is allowed as supporting material but warns when it is the only durable provenance. Unknown files remain allowed and unclassified.

- [ ] **Step 4: Implement journal checks and aggregate command output**

Read manifests and blobs without recovery or cleanup. An incomplete transaction includes the exact `cw recover ID --apply` next action. `check all` catches each checker exception, records that checker in `execution_errors`, and continues collecting independent results. Any nonempty `execution_errors` list returns exit `2`; ordinary findings retain the `0|1` contract.

- [ ] **Step 5: Run the complete checker suite**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.cw_cli.test_links_check tests.cw_cli.test_kb_check tests.cw_cli.test_journal_check tests.cw_cli.test_check_commands tests.cw_cli.test_continuity_check tests.cw_cli.test_prose_check -v`

Expected: PASS; warnings exit `0` by default and `1` only under `--strict`.

- [ ] **Step 6: Commit the complete registry**

```bash
git add plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/checks plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/app.py tests/cw_cli/test_links_check.py tests/cw_cli/test_kb_check.py tests/cw_cli/test_journal_check.py tests/cw_cli/test_check_commands.py
git commit -m "feat: complete story project checks"
```

### Task 4: Build deterministic context plans

**Files:**
- Create: `plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/context.py`
- Modify: `plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/app.py`
- Create: `tests/cw_cli/test_context_plan.py`
- Test: `tests/cw_cli/test_context_plan.py`

**Interfaces:**
- Produces: `ContextPlan(kind, subject, role, required, suggested, unresolved, warnings)`
- Produces: `plan_context(project, kind: str, path: str, role: str) -> ContextPlan`
- Produces: CLI `cw context draft|chapter|kb PATH [--as trusted|reader|character:ID] [--format text|json]`

- [ ] **Step 1: Write failing explicit-dependency and neighbor tests**

```python
def test_draft_context_prioritizes_target_and_explicit_kb_links(self):
    root = self.make_draft_with_links("work/drafts/ch-004.md", ["kb/characters/mara.md"])
    plan = context.plan_context(
        project.discover_project(root), "draft", "work/drafts/ch-004.md", "trusted"
    )
    self.assertEqual(plan.required[0], "work/drafts/ch-004.md")
    self.assertIn("story/chapters/ch-004.md", plan.required)
    self.assertIn("kb/characters/mara.md", plan.required)
    self.assertIn("story/chapters/ch-003.md", plan.suggested)
```

Add tests for first/last chapter neighbors, duplicate chapter numbers becoming `unresolved`, KB backlinks, active continuity issues, explicit plans, unknown character IDs, and no semantically inferred dependencies.

- [ ] **Step 2: Run focused tests and verify RED**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.cw_cli.test_context_plan -v`

Expected: FAIL because the context planner is missing.

- [ ] **Step 3: Implement stable context ordering**

Order required paths as subject, target, direct links, continuity/vocabulary; order suggested paths as neighboring chapters, active plans, backlinks, then active issues. Deduplicate by normalized project-relative identity. Missing or ambiguous dependencies go to `unresolved` and do not abort the plan.

- [ ] **Step 4: Wire text and JSON output**

Trusted output contains source paths only and does not copy content. Invalid kind or role returns status `2`; a valid plan with unresolved paths returns status `0` plus findings for the agent.

- [ ] **Step 5: Run context-plan tests**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.cw_cli.test_context_plan tests.cw_cli.test_check_commands -v`

Expected: PASS with deterministic path order.

- [ ] **Step 6: Commit context planning**

```bash
git add plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/context.py plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/app.py tests/cw_cli/test_context_plan.py
git commit -m "feat: plan focused story context"
```

### Task 5: Add restricted snapshots and context cleanup

**Files:**
- Modify: `plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/context.py`
- Modify: `plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/app.py`
- Create: `tests/cw_cli/test_context_redaction.py`
- Test: `tests/cw_cli/test_context_redaction.py`

**Interfaces:**
- Produces: `render_snapshot(project, plan: ContextPlan) -> SnapshotResult`
- Produces: `snapshot_status(project) -> list[Finding]`
- Produces: CLI `cw context ... --snapshot`
- Produces: CLI `cw clean-context [--apply]`

- [ ] **Step 1: Write failing hidden and character-knowledge redaction tests**

```python
def test_character_snapshot_removes_hidden_and_other_character_rows(self):
    root = self.make_character_context()
    plan = context.plan_context(project.discover_project(root), "chapter", "story/chapters/ch-004.md", "character:mara")
    result = context.render_snapshot(project.discover_project(root), plan)
    text = result.files["kb/continuity/state.md"].decode("utf-8")
    self.assertNotIn("author-only", text)
    self.assertIn("| mara |", text)
    self.assertNotIn("| ivo |", text)
    self.assertTrue(result.boundary_warning)
```

Add reader tests, nested/broken hidden tags, trusted-role snapshot refusal as unnecessary, stable manifest source hashes, stale-source findings, and cleanup preview/apply behavior.

- [ ] **Step 2: Run focused tests and verify RED**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.cw_cli.test_context_redaction -v`

Expected: FAIL because restricted rendering is missing.

- [ ] **Step 3: Implement explicit-only redaction**

Remove balanced `<hidden>...</hidden>` blocks including tags. For `character:<id>`, filter only tables with a recognized `character` or `knower` column, retaining rows whose normalized ID matches. Preserve headings and table headers. Set `boundary_warning` whenever included ordinary prose has no mechanical knowledge annotation.

- [ ] **Step 4: Store derived snapshots outside the journal**

Write snapshots beneath `.creative-writing/context/<snapshot-id>/` with a manifest of source paths, logical hashes, role, and creation time. Use sibling temporary writes but no transaction record. `clean-context` previews directories and removes only resolved descendants of this exact cache root with `--apply`.

- [ ] **Step 5: Run redaction and path-safety tests**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.cw_cli.test_context_redaction tests.cw_cli.test_project -v`

Expected: PASS; stale snapshots never fail ordinary `cw check all`.

- [ ] **Step 6: Commit context snapshots**

```bash
git add plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/context.py plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/app.py tests/cw_cli/test_context_redaction.py
git commit -m "feat: create restricted context snapshots"
```

### Task 6: Add project doctor and CLI environment doctor commands

**Files:**
- Create: `plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/doctor.py`
- Create: `plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/cli_doctor.py`
- Modify: `plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/app.py`
- Create: `tests/cw_cli/test_doctor.py`
- Create: `tests/cw_cli/test_cli_doctor.py`
- Test: `tests/cw_cli/test_doctor.py`
- Test: `tests/cw_cli/test_cli_doctor.py`

**Interfaces:**
- Produces: `RepairGroup(priority, title, findings, commands)`
- Produces: `diagnose_project(project) -> DoctorReport`
- Produces: `diagnose_cli(entrypoint: Path, python: Path) -> CliDoctorReport`
- Produces: CLI `cw doctor [--format text|json]`
- Produces: CLI `cw cli-doctor [--format text|json]`

- [ ] **Step 1: Write failing read-only and friendly-guidance tests**

```python
def test_doctor_groups_repairs_without_mutating(self):
    root = self.make_repairable_project()
    before = snapshot_tree(root)
    result = self.run_cli(root, ["doctor", "--format", "json"])
    payload = json.loads(result.stdout)
    self.assertEqual(snapshot_tree(root), before)
    self.assertEqual(payload["audience"], "agent")
    self.assertTrue(any(group["commands"] for group in payload["groups"]))

def test_cli_doctor_accepts_direct_invocation_without_launcher(self):
    result = cli_doctor.diagnose_cli(self.entrypoint, Path(sys.executable))
    self.assertTrue(result.direct_invocation.ok)
    self.assertFalse(result.launcher.required)
```

Add tests for Python 3.9 vs 3.10+, missing entrypoint, version mismatch, non-executable script that still works through Python, stale context, incomplete transactions, and no shell-profile writes.

- [ ] **Step 2: Run focused tests and verify RED**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.cw_cli.test_doctor tests.cw_cli.test_cli_doctor -v`

Expected: FAIL because doctor services are missing.

- [ ] **Step 3: Implement project repair grouping**

Group findings in this order: protect recoverability, restore safe interpretation, refresh derived files, improve provenance, optional cleanup. Include exact preview commands first and `--apply` commands second where available. Semantic findings contain questions for the agent, never fabricated repair commands.

- [ ] **Step 4: Implement CLI diagnostics without setup side effects**

Check Python version, entrypoint readability, direct `python cw.py --version --format json`, package/entrypoint version agreement, and optional launcher discovery with `shutil.which("cw")`. Report the exact direct invocation as the default solution. A launcher is optional and its setup remains the responsibility of the later `cli-doctor` skill after explicit approval.

- [ ] **Step 5: Run doctor, check, and complete CLI suites**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.cw_cli.test_doctor tests.cw_cli.test_cli_doctor tests.cw_cli.test_check_commands tests.cw_cli.test_context_redaction -v`

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/cw_cli -t . -v`

Expected: PASS; doctor leaves the project byte-for-byte unchanged.

- [ ] **Step 6: Commit doctor commands**

```bash
git add plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/doctor.py plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/cli_doctor.py plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/app.py tests/cw_cli/test_doctor.py tests/cw_cli/test_cli_doctor.py
git commit -m "feat: diagnose story projects and cw runtime"
```

### Task 7: Verify checks and context milestone

**Files:**
- Modify only files from Tasks 1–6 if verification exposes a defect.

**Interfaces:**
- Produces: a complete read-only mechanical floor for agent review and focused context preparation.

- [ ] **Step 1: Run all CLI tests**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/cw_cli -t . -v`

Expected: all CLI tests pass.

- [ ] **Step 2: Run complete repository and distribution checks**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v`

Run: `python3 scripts/validate_distribution.py && python3 scripts/vendor_generic_skills.py --check && python3 scripts/sync_claude_distribution.py --check`

Expected: all commands exit `0` and the generated CLI remains byte-identical to canonical source.

- [ ] **Step 3: Inspect a populated Russian fixture through the agent path**

Run `cw check all --format json`, `cw doctor --format json`, trusted draft context, reader snapshot context, and `cw clean-context` preview against the populated temporary fixture created by `tests.cw_cli.helpers`.

Expected: the author-facing files are unchanged; the agent receives stable codes, concrete next actions, and an explicit redaction-boundary warning.

- [ ] **Step 4: Commit only exact verification fixes, if any**

Stage only files changed to fix a reproduced failure, then commit:

```bash
git commit -m "fix: stabilize story checks and context"
```

Skip when verification leaves the working tree unchanged.

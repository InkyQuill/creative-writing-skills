# Story CLI Skill and Distribution Integration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Teach the authored creative-writing skills to use the canonical project contract and bundled CLI, add project and CLI doctor skills, retire duplicate checker entrypoints after parity, and ship the complete 29-skill distribution.

**Architecture:** `project-maintenance` owns mechanics and command reference; `project-doctor` interprets findings into repairs; `cli-doctor` hides runtime setup from the author. Existing domain skills remain responsible for literary judgment, confirmation, KB semantics, continuity semantics, and author-facing orchestration.

**Tech Stack:** Markdown skills/resources, JSON distribution manifests and worker registry, existing Python generation/validation scripts, `unittest` behavioral and distribution tests.

**Spec:** `docs/superpowers/specs/2026-08-28-story-project-contract-cli-design.md`

## Global Constraints

- Complete all four CLI plans before this integration plan.
- Edit canonical `plugins/creative-writing-skills/` sources only; regenerate `cw/` through the existing script.
- The agent handles setup, hashes, tags, indexes, and repair commands. Instructions must not send a nontechnical author to edit them.
- Mechanical warnings are preparation for agent review, not permission to refuse creative work.
- Draft acceptance and KB promotion are separate author-confirmed decisions.
- Do not remove standalone continuity/prose resources until parity tests from Plan 4 pass.

---

### Task 1: Expand `project-maintenance` into the complete mechanical contract

**Files:**
- Modify: `plugins/creative-writing-skills/skills/project-maintenance/SKILL.md`
- Create: `plugins/creative-writing-skills/skills/project-maintenance/resources/command-reference.md`
- Create: `plugins/creative-writing-skills/skills/project-maintenance/resources/project-contract.md`
- Create: `plugins/creative-writing-skills/skills/project-maintenance/resources/agent-workflows.md`
- Create: `tests/test_project_maintenance_skill.py`
- Test: `tests/test_project_maintenance_skill.py`

**Interfaces:**
- Produces: `$project-maintenance`
- Documents: direct CLI resolution, preview/apply, checks, context, drafts, migration, history/undo, and recovery
- Preserves: CLI package under `resources/cli/`

- [ ] **Step 1: Write failing contract and author-experience tests**

```python
class ProjectMaintenanceSkillTests(unittest.TestCase):
    def test_skill_uses_direct_entrypoint_and_preview_before_apply(self):
        text = SKILL.read_text(encoding="utf-8")
        self.assertIn("resources/cli/cw.py", text)
        self.assertIn("preview", text.lower())
        self.assertIn("--apply", text)

    def test_skill_does_not_delegate_hash_or_index_work_to_author(self):
        text = all_runtime_markdown("project-maintenance")
        self.assertNotRegex(text, r"(?i)ask the author to (edit|update).*(hash|index|base-revision)")
```

Add assertions that the skill allows unknown files, treats Git as optional, recommends direct Python invocation before launcher setup, and names the protected paths.

- [ ] **Step 2: Run focused tests and verify RED**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_project_maintenance_skill -v`

Expected: FAIL because the current initial skill lacks the complete resources.

- [ ] **Step 3: Write the compact orchestration skill**

Keep `SKILL.md` task-oriented: discover the nearest project, invoke the bundled entrypoint, preview mutations, apply only within the user's request, and use history/undo on mistakes. Route command detail to the three resources rather than duplicating it.

- [ ] **Step 4: Document agent-first failure handling**

For exit `0`, continue; for exit `1`, inspect findings and continue any unrelated creative work; for exit `2`, invoke `$cli-doctor`. Never tell the author that prose cannot be reviewed merely because an index, optional field, or context cache is stale.

- [ ] **Step 5: Run skill tests and Markdown validation**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_project_maintenance_skill -v`

Run: `python3 scripts/validate_distribution.py`

Expected: skill tests pass and canonical validation accepts all resource links.

- [ ] **Step 6: Commit the complete maintenance skill**

```bash
git add plugins/creative-writing-skills/skills/project-maintenance/SKILL.md plugins/creative-writing-skills/skills/project-maintenance/resources/command-reference.md plugins/creative-writing-skills/skills/project-maintenance/resources/project-contract.md plugins/creative-writing-skills/skills/project-maintenance/resources/agent-workflows.md tests/test_project_maintenance_skill.py
git commit -m "docs: teach agents the story project CLI"
```

### Task 2: Add `project-doctor` as a read-only repair planner

**Files:**
- Create: `plugins/creative-writing-skills/skills/project-doctor/SKILL.md`
- Create: `plugins/creative-writing-skills/skills/project-doctor/resources/repair-policy.md`
- Create: `tests/test_project_doctor_skill.py`
- Test: `tests/test_project_doctor_skill.py`

**Interfaces:**
- Produces: `$project-doctor`
- Consumes: `cw doctor --format json`
- Routes: mechanical repair to `$project-maintenance`, semantic contradictions to the owning domain skill

- [ ] **Step 1: Write failing no-mutation and prioritization tests**

```python
class ProjectDoctorSkillTests(unittest.TestCase):
    def test_doctor_skill_requires_diagnosis_before_repairs(self):
        text = all_runtime_markdown("project-doctor")
        self.assertIn("cw doctor", text)
        self.assertIn("read-only", text.lower())
        self.assertRegex(text, r"(?is)preview.*--apply")

    def test_cosmetic_drift_is_not_an_author_blocker(self):
        text = all_runtime_markdown("project-doctor")
        self.assertIn("continue", text.lower())
        self.assertNotIn("ask the author to fix the project", text.lower())
```

Add behavioral assertions for incomplete-transaction priority, semantic non-autofix, and exact next-action reporting.

- [ ] **Step 2: Run focused tests and verify RED**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_project_doctor_skill -v`

Expected: FAIL because `project-doctor` does not exist.

- [ ] **Step 3: Write the doctor workflow**

The skill runs diagnosis, summarizes only material findings to the author, repairs safe mechanical issues itself after preview, and asks a content question only when different answers would change canon. It never performs hidden repairs during diagnosis.

- [ ] **Step 4: Run focused tests**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_project_doctor_skill -v`

Expected: PASS.

- [ ] **Step 5: Commit the project doctor skill**

```bash
git add plugins/creative-writing-skills/skills/project-doctor tests/test_project_doctor_skill.py
git commit -m "feat: add story project doctor skill"
```

### Task 3: Add `cli-doctor` and optional launcher setup workflow

**Files:**
- Create: `plugins/creative-writing-skills/skills/cli-doctor/SKILL.md`
- Create: `plugins/creative-writing-skills/skills/cli-doctor/resources/launcher-setup.md`
- Create: `tests/test_cli_doctor_skill.py`
- Test: `tests/test_cli_doctor_skill.py`

**Interfaces:**
- Produces: `$cli-doctor`
- Consumes: bundled `cw cli-doctor --format json`
- Produces: direct invocation guidance and optional user-scoped launcher preview

- [ ] **Step 1: Write failing zero-configuration and approval tests**

```python
class CliDoctorSkillTests(unittest.TestCase):
    def test_direct_python_invocation_is_the_default_solution(self):
        text = all_runtime_markdown("cli-doctor")
        self.assertRegex(text, r"python3 .*resources/cli/cw\.py")
        self.assertIn("Python 3.10", text)

    def test_shell_profiles_are_never_changed_without_approval(self):
        text = all_runtime_markdown("cli-doctor")
        self.assertRegex(text, r"(?is)(approval|permission).*(PATH|profile|launcher)")
```

Add assertions that no third-party dependency installation is suggested, the CLI is not copied into story projects, and Windows/macOS/Linux direct invocations are covered without a large setup guide in the main skill.

- [ ] **Step 2: Run focused tests and verify RED**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_cli_doctor_skill -v`

Expected: FAIL because `cli-doctor` does not exist.

- [ ] **Step 3: Write diagnosis-first instructions**

Resolve the current installed skill path, test the exact bundled entrypoint, use that path for the active task, and only then offer an optional launcher. Keep platform-specific launcher examples in `resources/launcher-setup.md`; every persistent change must have a shown preview and explicit approval.

- [ ] **Step 4: Run focused tests**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_cli_doctor_skill -v`

Expected: PASS.

- [ ] **Step 5: Commit the CLI doctor skill**

```bash
git add plugins/creative-writing-skills/skills/cli-doctor tests/test_cli_doctor_skill.py
git commit -m "feat: add cw CLI doctor skill"
```

### Task 4: Update project, KB, memory, review, and editing domain skills

**Files:**
- Modify: `plugins/creative-writing-skills/skills/project-setup/SKILL.md`
- Modify: `plugins/creative-writing-skills/skills/kb-management/SKILL.md`
- Modify: `plugins/creative-writing-skills/skills/story-memory/SKILL.md`
- Modify: `plugins/creative-writing-skills/skills/story-memory/resources/continuity-records.md`
- Modify: `plugins/creative-writing-skills/skills/story-review/SKILL.md`
- Modify: `plugins/creative-writing-skills/skills/targeted-editing/SKILL.md`
- Create: `tests/test_story_project_integration.py`
- Test: `tests/test_story_project_integration.py`

**Interfaces:**
- `project-setup` produces only canonical scaffold or an approved migration plan
- `kb-management` runs mechanical floor before semantic audit and preserves promotion confirmation
- `story-memory` owns `kb/continuity/` semantics used by `cw check continuity`
- `story-review` reviews active drafts with prepared context even when repairable warnings exist
- `targeted-editing` emits exact-anchor or batch operations with preview and recoverable apply

- [ ] **Step 1: Write failing cross-skill behavior tests**

```python
class StoryProjectIntegrationTests(unittest.TestCase):
    def test_setup_has_one_canonical_layout(self):
        text = all_runtime_markdown("project-setup")
        self.assertNotIn("Layout A", text)
        self.assertNotIn("Layout B", text)
        self.assertIn("cw init", text)

    def test_acceptance_and_kb_promotion_remain_separate(self):
        text = all_runtime_markdown("kb-management") + all_runtime_markdown("story-review")
        self.assertRegex(text, r"(?is)accept.*does not.*(KB|knowledge base)")
```

Add tests for continuity paths, context-before-review, author-edit tolerance, exact-anchor edits, migration preview, and no skill telling the author to maintain SHA values.

- [ ] **Step 2: Run integration tests and verify RED**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_story_project_integration -v`

Expected: FAIL because existing skills still describe multiple layouts and standalone mechanics.

- [ ] **Step 3: Rewrite setup and domain routing**

Replace layout selection with `cw init` for an ordinary folder and `cw migrate --plan` for recognized legacy content. Preserve unknown files. In every domain skill, run only the relevant mechanical check, interpret warnings internally, and proceed to the requested semantic work unless a required target cannot be read safely.

- [ ] **Step 4: Teach editing and lifecycle boundaries**

`targeted-editing` chooses literary scope first, then creates an exact operation plan; it uses explicit repeated-match assertions and `cw undo` after a mistaken apply. `story-review` may recommend acceptance but does not apply it without author confirmation. `kb-management` creates a separate promotion transaction with durable provenance.

- [ ] **Step 5: Run integration and existing skill tests**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_story_project_integration tests.test_distribution -v`

Expected: PASS with no obsolete layout instructions in the five updated skill trees.

- [ ] **Step 6: Commit domain skill integration**

```bash
git add plugins/creative-writing-skills/skills/project-setup plugins/creative-writing-skills/skills/kb-management plugins/creative-writing-skills/skills/story-memory plugins/creative-writing-skills/skills/story-review plugins/creative-writing-skills/skills/targeted-editing tests/test_story_project_integration.py
git commit -m "docs: align writing skills with canonical projects"
```

### Task 5: Update muse orchestration and worker contracts

**Files:**
- Modify: `plugins/creative-writing-skills/skills/creative-writing-muse/SKILL.md`
- Modify: `plugins/creative-writing-skills/skills/creative-writing-muse/resources/workers/registry.json`
- Modify: matching worker prompt files under `plugins/creative-writing-skills/skills/creative-writing-muse/resources/workers/`
- Create: `tests/test_muse_project_workflows.py`
- Test: `tests/test_muse_project_workflows.py`

**Interfaces:**
- Muse initializes/repairs transparently before creative orchestration
- Muse obtains explicit confirmation for draft acceptance, KB promotion, migration apply, and retcons
- Workers receive prepared context and return proposals, not direct unjournaled mutations

- [ ] **Step 1: Enumerate affected workers and write failing registry tests**

Run: `rg -n "(project-setup|kb-management|story-memory|story-review|targeted-editing|chapters/|drafts/|continuity_check|analyze.py)" plugins/creative-writing-skills/skills/creative-writing-muse/resources/workers`

Record the exact matching worker files in this task before editing. Add tests asserting each matching registry entry references canonical paths and that prose-writing/review workers receive a context plan plus draft target.

- [ ] **Step 2: Run focused tests and verify RED**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_muse_project_workflows -v`

Expected: FAIL on obsolete worker contracts.

- [ ] **Step 3: Update orchestration without exposing maintenance ceremony**

Muse calls `$cli-doctor` only after an execution failure and `$project-doctor` when the folder needs repair. It handles safe scaffold/index/tag work itself. It summarizes material conflicts to the author in content language, not CLI terminology.

- [ ] **Step 4: Enforce proposal and confirmation boundaries**

Research, scene options, KB proposals, and drafted prose remain proposals. Acceptance changes manuscript only; KB promotion is a separate confirmed transaction. Worker prompts must never write accepted manuscript or KB directly.

- [ ] **Step 5: Run muse and worker registry tests**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_muse_project_workflows tests.test_distribution -v`

Expected: PASS and every registry path resolves.

- [ ] **Step 6: Commit muse integration**

```bash
git add plugins/creative-writing-skills/skills/creative-writing-muse tests/test_muse_project_workflows.py
git commit -m "docs: orchestrate canonical story workflows"
```

### Task 6: Retire duplicate checker entrypoints after parity

**Files:**
- Delete: `plugins/creative-writing-skills/skills/story-memory/resources/continuity_check.py`
- Delete: `plugins/creative-writing-skills/skills/story-review/resources/prose-critique/analyze.py`
- Modify: references found by repository search in canonical skill Markdown and tests
- Modify: `tests/cw_cli/test_continuity_check.py`
- Modify: `tests/cw_cli/test_prose_check.py`
- Test: `tests/cw_cli/test_continuity_check.py`
- Test: `tests/cw_cli/test_prose_check.py`

**Interfaces:**
- Preserves: all legacy deterministic behavior through `cw check continuity|prose`
- Removes: drifting standalone execution paths

- [ ] **Step 1: Verify parity before deletion**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.cw_cli.test_continuity_check tests.cw_cli.test_prose_check -v`

Expected: PASS for every legacy parity fixture.

- [ ] **Step 2: Find every standalone-script reference**

Run: `rg -n "continuity_check\.py|prose-critique/analyze\.py|resources/prose-critique" plugins tests scripts README.md docs --glob '!docs/superpowers/plans/**' --glob '!docs/superpowers/specs/**'`

Expected: a finite list of canonical skill/test references to replace with bundled `cw check continuity` or `cw check prose`.

- [ ] **Step 3: Delete only after the reference replacement is covered**

Use `apply_patch` to remove the two files and update the exact references reported in Step 2. Keep the parity fixture expectations in the new CLI tests so deletion does not weaken coverage.

- [ ] **Step 4: Run CLI and skill tests**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/cw_cli -t . -v`

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_story_project_integration tests.test_muse_project_workflows -v`

Expected: PASS and repository search finds no runtime reference to either deleted entrypoint.

- [ ] **Step 5: Commit checker consolidation**

Stage the two deletions, the exact references reported in Step 2, and the two parity test files. Then commit with `git commit -m "refactor: consolidate deterministic story checks"`.

### Task 7: Register 29 skills and regenerate every distribution

**Files:**
- Modify: `plugins/creative-writing-skills/.codex-plugin/plugin.json`
- Modify: `config/distribution.json`
- Modify: `scripts/validate_distribution.py`
- Modify: `tests/test_distribution.py`
- Modify: `tests/test_sync_claude_distribution.py`
- Modify: `README.md`
- Generate: `cw/**`
- Generate: `.claude-plugin/marketplace.json`
- Generate: `marketplace.json`
- Generate: `zips/**`
- Test: `tests/test_distribution.py`
- Test: `tests/test_sync_claude_distribution.py`

**Interfaces:**
- Produces: exact total inventory 29
- Produces: exact authored inventory 19
- Produces: byte-identical bundled CLI in canonical, generated, and archive forms

- [ ] **Step 1: Write failing inventory and bundled-runtime assertions**

Add `project-doctor` and `cli-doctor` to sorted configured/expected/authored sets. Change the intermediate counts from 27/17 to 29/19 and sync assertion from 27 to 29. Extend archive tests to assert the `project-maintenance` zip contains `resources/cli/cw.py`, `cwcli/app.py`, and checker modules.

- [ ] **Step 2: Run distribution tests and verify RED**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_distribution tests.test_sync_claude_distribution -v`

Expected: FAIL until configuration and generated output include all three new authored skills.

- [ ] **Step 3: Update canonical inventory and user documentation**

Register the two remaining skills in sorted order. Update README with the single canonical project model and explain that `cw` is agent infrastructure; ordinary authors may continue editing Markdown directly and Git is optional.

- [ ] **Step 4: Regenerate, validate, and build archives**

Run: `python3 scripts/sync_claude_distribution.py --apply`

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_distribution tests.test_sync_claude_distribution -v`

Run: `python3 scripts/validate_distribution.py && python3 scripts/vendor_generic_skills.py --check && python3 scripts/sync_claude_distribution.py --check && python3 scripts/create_skill_zips.py`

Expected: every command exits `0`, reports exactly 29 skills, and generated runtime Markdown contains no forbidden platform token.

- [ ] **Step 5: Commit canonical and generated distribution output**

```bash
git add plugins/creative-writing-skills/.codex-plugin/plugin.json plugins/creative-writing-skills/skills/cli-doctor plugins/creative-writing-skills/skills/project-doctor config/distribution.json scripts/validate_distribution.py tests/test_distribution.py tests/test_sync_claude_distribution.py README.md cw .claude-plugin/marketplace.json marketplace.json zips
git commit -m "feat: distribute canonical story project workflows"
```

### Task 8: Run final behavioral, repository, and archive verification

**Files:**
- Modify only exact files implicated by a reproduced verification failure.

**Interfaces:**
- Produces: a complete 29-skill release candidate with one project layout and an agent-operated recoverable CLI.

- [ ] **Step 1: Run the full test suite**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v`

Expected: all tests pass.

- [ ] **Step 2: Run all repository validation**

Run: `python3 scripts/validate_distribution.py`

Run: `python3 scripts/vendor_generic_skills.py --check`

Run: `python3 scripts/sync_claude_distribution.py --check`

Run: `python3 scripts/create_skill_zips.py`

Expected: all commands exit `0`; archives match the exact configured inventory.

- [ ] **Step 3: Run an end-to-end author workflow in a temporary folder**

Exercise: initialize an existing folder containing unrelated files; manually edit a chapter; run doctor; create and edit a draft; prepare review context; apply a safe batch edit; undo it; accept the draft; propose but do not apply KB promotion; inspect history; and verify unrelated files remain byte-identical.

Expected: the author never supplies a hash, manages an index, installs a dependency, or loses a manual edit. Warnings remain visible to the agent without stopping the workflow.

- [ ] **Step 4: Search for obsolete contract language**

Run: `rg -n "Layout A|Layout B|continuity_check\.py|prose-critique/analyze\.py|ask the author to .*hash|ask the author to .*index" plugins/creative-writing-skills/skills README.md tests`

Expected: no runtime instruction retains the obsolete dual-layout or standalone-checker contract; historical tests may mention legacy layouts only as migration fixtures.

- [ ] **Step 5: Commit only exact verification fixes, if any**

Stage only files changed to fix a reproduced failure, then commit:

```bash
git commit -m "fix: stabilize canonical story workflows"
```

Skip when final verification leaves the working tree unchanged.

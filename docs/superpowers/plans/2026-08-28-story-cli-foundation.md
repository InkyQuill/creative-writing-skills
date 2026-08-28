# Story CLI Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the first runnable `cw` CLI with the canonical schema, strict Markdown/frontmatter reader, project discovery, scaffold rendering, and read-only structure checks.

**Architecture:** The new authored `project-maintenance` skill owns a standard-library Python package under `resources/cli/`. This plan exposes only `cw --version`, scaffold preview, and `cw check structure`; later plans add mutation, draft, context, and doctor services without changing these interfaces.

**Tech Stack:** Python 3.10+ standard library, `unittest`, Markdown files with a deliberately limited YAML subset, existing canonical-to-`cw/` distribution generator.

**Spec:** `docs/superpowers/specs/2026-08-28-story-project-contract-cli-design.md`

## Global Constraints

- Python 3.10 or newer; no third-party runtime dependencies or network access.
- Canonical runtime changes begin under `plugins/creative-writing-skills/`; never hand-edit `cw/`.
- Project text is UTF-8; logical hashes normalize BOM and CRLF/CR to LF, while byte snapshots are outside this plan.
- Manual author edits and repairable metadata drift remain readable; only unsafe interpretation produces an error.
- The story contract uses platform-neutral `project.md`, never a required runtime `AGENTS.md`.
- Use `PYTHONDONTWRITEBYTECODE=1` for repository test commands.

---

### Task 1: Create the CLI package and stable finding model

**Files:**
- Create: `plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cw.py`
- Create: `plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/__init__.py`
- Create: `plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/app.py`
- Create: `plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/findings.py`
- Create: `tests/cw_cli/__init__.py`
- Create: `tests/cw_cli/helpers.py`
- Create: `tests/cw_cli/test_app.py`
- Test: `tests/cw_cli/test_app.py`

**Interfaces:**
- Produces: `cwcli.__version__: str`
- Produces: `Finding(code, severity, message, path=None, line=None, next_action=None)`
- Produces: `Report(findings).exit_status(strict=False)`, `.as_json(strict=False)`, and `.as_text()`
- Produces: `app.run(argv: list[str], *, cwd: Path, stdout: TextIO, stderr: TextIO) -> int`

- [ ] **Step 1: Write failing tests for version output and finding exit semantics**

```python
# tests/cw_cli/test_app.py
import io
import unittest
from pathlib import Path

from .helpers import app, findings


class AppTests(unittest.TestCase):
    def test_version_is_machine_readable(self):
        stdout = io.StringIO()
        status = app.run(["--version", "--format", "json"], cwd=Path.cwd(), stdout=stdout, stderr=io.StringIO())
        self.assertEqual(status, 0)
        self.assertEqual({"name": "cw", "version": "0.1.0"}, __import__("json").loads(stdout.getvalue()))

    def test_strict_warning_returns_one_without_changing_severity(self):
        report = findings.Report([findings.Finding("CW-DEMO-001", "warning", "demo")])
        self.assertEqual(report.exit_status(strict=False), 0)
        self.assertEqual(report.exit_status(strict=True), 1)
        self.assertEqual(report.as_json(strict=True)["findings"][0]["severity"], "warning")
        self.assertTrue(report.as_json(strict=True)["strict_failure"])
```

- [ ] **Step 2: Add the test import helper**

```python
# tests/cw_cli/helpers.py
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CLI_ROOT = REPO_ROOT / "plugins/creative-writing-skills/skills/project-maintenance/resources/cli"
sys.path.insert(0, str(CLI_ROOT))

from cwcli import app, findings  # noqa: E402
```

- [ ] **Step 3: Run the focused test and verify RED**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.cw_cli.test_app -v`

Expected: FAIL because `project-maintenance/resources/cli` and `cwcli` do not exist.

- [ ] **Step 4: Implement the package entrypoint and finding model**

```python
# cwcli/findings.py
from dataclasses import asdict, dataclass
from typing import Literal

Severity = Literal["info", "warning", "error"]

@dataclass(frozen=True)
class Finding:
    code: str
    severity: Severity
    message: str
    path: str | None = None
    line: int | None = None
    next_action: str | None = None

@dataclass(frozen=True)
class Report:
    findings: list[Finding]

    def exit_status(self, *, strict: bool = False) -> int:
        return int(any(item.severity == "error" for item in self.findings) or
                   (strict and any(item.severity == "warning" for item in self.findings)))

    def as_json(self, *, strict: bool = False) -> dict[str, object]:
        return {
            "findings": [asdict(item) for item in self.findings],
            "strict_failure": strict and self.exit_status(strict=True) == 1 and
                not any(item.severity == "error" for item in self.findings),
        }
```

Implement `Report.as_text()` with one stable line per finding and implement `app.run()` with `argparse`, `--version`, and `--format text|json`. `cw.py` must call `sys.exit(app.main())` without importing repository-local modules.

- [ ] **Step 5: Run the focused tests and entrypoint smoke test**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.cw_cli.test_app -v`

Expected: PASS.

Run: `python3 plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cw.py --version --format json`

Expected: `{"name": "cw", "version": "0.1.0"}` followed by a newline.

- [ ] **Step 6: Commit the package foundation**

```bash
git add plugins/creative-writing-skills/skills/project-maintenance/resources/cli tests/cw_cli
git commit -m "feat: add cw CLI foundation"
```

### Task 2: Implement the limited frontmatter and text-normalization contract

**Files:**
- Create: `plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/documents.py`
- Create: `tests/cw_cli/test_documents.py`
- Test: `tests/cw_cli/test_documents.py`

**Interfaces:**
- Produces: `Document(metadata: dict[str, Scalar | list[str]], body: str, newline: str, bom: bool)`
- Produces: `parse_document(data: bytes) -> Document`
- Produces: `render_document(document: Document) -> bytes`
- Produces: `canonical_text(data: bytes) -> str`
- Produces: `logical_hash(data: bytes) -> str`

- [ ] **Step 1: Write failing parser, round-trip, and normalized-hash tests**

```python
from .helpers import documents

def test_supported_frontmatter_round_trips_crlf_and_bom():
    raw = b"\xef\xbb\xbf---\r\ntitle: Story\r\nnumber: 3\r\nhidden: false\r\ntags:\r\n  - sea\r\n  - memory\r\n---\r\n\r\nText\r\n"
    parsed = documents.parse_document(raw)
    assert parsed.metadata == {"title": "Story", "number": 3, "hidden": False, "tags": ["sea", "memory"]}
    assert parsed.newline == "\r\n"
    assert parsed.bom is True
    assert documents.render_document(parsed) == raw

def test_logical_hash_ignores_bom_and_line_endings():
    left = b"\xef\xbb\xbf---\r\ntitle: Story\r\n---\r\nBody\r\n"
    right = b"---\ntitle: Story\n---\nBody\n"
    assert documents.logical_hash(left) == documents.logical_hash(right)
```

Add cases rejecting nested mappings, block scalars, duplicate keys, invalid UTF-8, and unterminated frontmatter with `DocumentError` messages containing the line number.

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.cw_cli.test_documents -v`

Expected: FAIL because `cwcli.documents` is missing.

- [ ] **Step 3: Implement a line-oriented subset parser**

```python
# cwcli/documents.py
@dataclass(frozen=True)
class Document:
    metadata: dict[str, Scalar | list[str]]
    body: str
    newline: str
    bom: bool

def canonical_text(data: bytes) -> str:
    text = data.decode("utf-8-sig")
    return text.replace("\r\n", "\n").replace("\r", "\n")

def logical_hash(data: bytes) -> str:
    return hashlib.sha256(canonical_text(data).encode("utf-8")).hexdigest()
```

Parse only unindented `key: scalar` and two-space-indented `- scalar` list items. Accept quoted JSON strings, single-quoted strings with doubled quotes, integers, booleans, and empty values. Preserve original bytes when the parsed document is rendered without metadata/body changes.

- [ ] **Step 4: Run parser tests and property-style fixture loops**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.cw_cli.test_documents -v`

Expected: PASS for LF, CRLF, BOM, Russian text, and every rejected YAML feature.

- [ ] **Step 5: Commit the document contract**

```bash
git add plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/documents.py tests/cw_cli/test_documents.py
git commit -m "feat: parse story project documents"
```

### Task 3: Add project discovery and safe path identity

**Files:**
- Create: `plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/project.py`
- Create: `tests/cw_cli/test_project.py`
- Test: `tests/cw_cli/test_project.py`

**Interfaces:**
- Produces: `Project(root: Path, manifest: Document)`
- Produces: `discover_project(start: Path) -> Project`
- Produces: `Project.resolve(relative: str, *, for_write: bool = False) -> Path`
- Produces: `Project.iter_managed_markdown() -> Iterator[Path]`
- Produces: `Project.relative_id(path: Path) -> str`

- [ ] **Step 1: Write failing nearest-root, nested-boundary, and symlink tests**

```python
class ProjectDiscoveryTests(unittest.TestCase):
    def test_nearest_project_wins(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_manifest(root)
            child = root / "nested"
            write_manifest(child)
            self.assertEqual(project.discover_project(child / "story").root, child.resolve())

    def test_write_refuses_parent_and_nested_project(self):
        with tempfile.TemporaryDirectory() as directory:
            outer = make_project(Path(directory) / "outer")
            make_project(outer.root / "story" / "nested")
            with self.assertRaisesRegex(project.ProjectPathError, "nested project"):
                outer.resolve("story/nested/project.md", for_write=True)
            with self.assertRaisesRegex(project.ProjectPathError, "outside project"):
                outer.resolve("../escape.md", for_write=True)
```

Add cases for `.creative-writing/`, absolute paths, case-colliding managed paths, Windows reserved names, and a symlink target.

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.cw_cli.test_project -v`

Expected: FAIL because `cwcli.project` is missing.

- [ ] **Step 3: Implement nearest-manifest discovery and lexical plus resolved containment**

```python
MANAGED_ROOTS = ("story", "work", "kb")
PROTECTED_ROOT = ".creative-writing"

@dataclass(frozen=True)
class Project:
    root: Path
    manifest: Document

    def relative_id(self, path: Path) -> str:
        return path.relative_to(self.root).as_posix()
```

`resolve()` must reject `..`, absolute inputs, path escapes after resolution, nested descendants containing another `project.md`, and symlinks when `for_write=True`. Read-only discovery returns external links as findings later rather than traversing them.

- [ ] **Step 4: Run path tests on the current platform**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.cw_cli.test_project -v`

Expected: PASS; symlink tests may use `unittest.skipUnless(hasattr(os, "symlink"), ...)` only when the platform lacks symlink support.

- [ ] **Step 5: Commit project discovery**

```bash
git add plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/project.py tests/cw_cli/test_project.py
git commit -m "feat: discover story project boundaries"
```

### Task 4: Define schema v1 and render the full scaffold

**Files:**
- Create: `plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/schema.py`
- Create: `plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/scaffold.py`
- Create: `tests/cw_cli/test_schema.py`
- Create: `tests/fixtures/cw-project-minimal/README.md`
- Test: `tests/cw_cli/test_schema.py`

**Interfaces:**
- Produces: `SCHEMA_VERSION = 1`
- Produces: `SCAFFOLD_FILES: tuple[str, ...]`
- Produces: `render_scaffold(title: str, language: str) -> dict[str, bytes]`
- Produces: `validate_metadata(relative_id: str, document: Document) -> list[Finding]`

- [ ] **Step 1: Write a failing exact-scaffold test**

```python
def test_scaffold_contains_every_canonical_file():
    rendered = scaffold.render_scaffold("Second Light", "ru")
    self.assertEqual(set(rendered), set(schema.SCAFFOLD_FILES))
    manifest = documents.parse_document(rendered["project.md"])
    self.assertEqual(manifest.metadata["schema-version"], 1)
    self.assertEqual(manifest.metadata["title"], "Second Light")
    self.assertIn("kb/samples/_index.md", rendered)
    self.assertNotIn("AGENTS.md", rendered)
```

Add exact assertions for continuity files, every authored `_index.md`, and default project instructions in the `project.md` body.

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.cw_cli.test_schema -v`

Expected: FAIL because `schema` and `scaffold` do not exist.

- [ ] **Step 3: Implement constants and deterministic renderers**

```python
# cwcli/schema.py
SCHEMA_VERSION = 1
PROJECT_STATUSES = frozenset({"planning", "drafting", "revising", "complete", "archived"})
WORLD_CLASSES = frozenset({"location", "faction", "system", "artifact", "concept"})
```

Render files in sorted path order with LF endings and trailing newlines. `_index.md` files contain only frontmatter, a heading, and an empty generated registry marker; they must not contain author instructions.

- [ ] **Step 4: Materialize the minimal fixture using the renderer**

Add a test helper that writes `render_scaffold()` into a temporary directory. Keep `tests/fixtures/cw-project-minimal/README.md` as a human note explaining that runtime tests materialize the fixture to avoid duplicating generated scaffold content.

- [ ] **Step 5: Run schema tests**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.cw_cli.test_schema -v`

Expected: PASS with stable ordering and exact canonical paths.

- [ ] **Step 6: Commit schema and scaffold rendering**

```bash
git add plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/schema.py plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/scaffold.py tests/cw_cli/test_schema.py tests/fixtures/cw-project-minimal
git commit -m "feat: define story project schema v1"
```

### Task 5: Implement `check structure` and scaffold preview

**Files:**
- Create: `plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/checks/__init__.py`
- Create: `plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/checks/structure.py`
- Modify: `plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/app.py`
- Create: `tests/cw_cli/test_structure_check.py`
- Test: `tests/cw_cli/test_structure_check.py`

**Interfaces:**
- Consumes: `Project`, `SCAFFOLD_FILES`, `validate_metadata`, `Finding`, `Report`
- Produces: `check_structure(project: Project) -> list[Finding]`
- Produces: CLI `cw check structure [path] [--strict] [--format text|json]`
- Produces: CLI `cw init [path] --title TITLE --language LANG` preview JSON only; `--apply` remains unavailable until the transaction plan.

- [ ] **Step 1: Write failing leniency and blocker tests**

```python
def test_missing_index_is_warning_but_newer_schema_is_error(self):
    root = self.make_project()
    (root / "kb/_index.md").unlink()
    report = structure.check_structure(project.discover_project(root))
    self.assertIn(("CW-STRUCT-010", "warning"), {(f.code, f.severity) for f in report})
    rewrite_manifest(root, schema_version=99)
    report = structure.check_structure(project.discover_project(root))
    self.assertIn(("CW-STRUCT-001", "error"), {(f.code, f.severity) for f in report})
```

Add cases for missing optional chapter status, duplicate chapter numbers, malformed frontmatter that still reports the file path, unmanaged Markdown as `info`, mixed newlines as `warning`, and case collisions as `warning`.

- [ ] **Step 2: Run tests and verify RED**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.cw_cli.test_structure_check -v`

Expected: FAIL because the check registry does not exist.

- [ ] **Step 3: Implement stable structure finding codes**

```python
MISSING_PATH = "CW-STRUCT-010"
NEWER_SCHEMA = "CW-STRUCT-001"
INVALID_FRONTMATTER = "CW-STRUCT-020"
DUPLICATE_CHAPTER = "CW-STRUCT-030"
UNMANAGED_MARKDOWN = "CW-STRUCT-090"
```

Continue reading other files after one malformed document. Only the manifest's incompatible newer schema prevents safe project interpretation.

- [ ] **Step 4: Wire command output and preview-only initialization**

`cw init` must emit a sorted JSON operation list with `create` paths and no filesystem writes. If `--apply` is supplied, return status `2` and the exact message `init --apply requires the transaction engine; run without --apply for preview` until Plan 2 replaces this guard.

- [ ] **Step 5: Run the focused and aggregate CLI tests**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.cw_cli.test_structure_check tests.cw_cli.test_app -v`

Expected: PASS, including strict-warning exit status `1` and JSON severity preservation.

- [ ] **Step 6: Commit read-only foundation commands**

```bash
git add plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli tests/cw_cli
git commit -m "feat: check story project structure"
```

### Task 6: Add the initial `project-maintenance` skill and distribute 27 skills

**Files:**
- Create: `plugins/creative-writing-skills/skills/project-maintenance/SKILL.md`
- Modify: `config/distribution.json`
- Modify: `scripts/validate_distribution.py`
- Modify: `tests/test_distribution.py`
- Modify: `tests/test_sync_claude_distribution.py`
- Modify: `README.md`
- Generate: `cw/skills/project-maintenance/**`
- Generate: `cw/.claude-plugin/plugin.json`
- Generate: `cw/.zcode-plugin/plugin.json`
- Generate: `.claude-plugin/marketplace.json`
- Generate: `marketplace.json`
- Test: `tests/test_distribution.py`
- Test: `tests/test_sync_claude_distribution.py`

**Interfaces:**
- Consumes: packaged `resources/cli/cw.py`
- Produces: installed skill `$project-maintenance`
- Produces: canonical authored-skill count 17 and total-skill count 27 for this intermediate stage

- [ ] **Step 1: Write failing distribution assertions for one new authored skill**

Update the expected skill sets and count assertions to include only `project-maintenance` at this stage. Change the sync assertion from 26 to 27 generated skills. Add a test that the generated skill contains `resources/cli/cw.py` and `resources/cli/cwcli/app.py` byte-for-byte.

- [ ] **Step 2: Run distribution tests and verify RED**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_distribution tests.test_sync_claude_distribution -v`

Expected: FAIL because the skill is not registered or generated.

- [ ] **Step 3: Write the initial skill instructions**

```markdown
---
name: project-maintenance
description: Deterministic maintenance for canonical creative-writing projects. Use when an agent needs to inspect project structure, preview initialization, or run the bundled cw CLI.
---

# Project Maintenance

Resolve this skill directory, then run `python3 resources/cli/cw.py --version`.
Use `check structure` before reorganizing a story folder. Treat warnings as
agent repair work; do not ask the author to edit indexes or hashes.
```

Do not mention platform-specific instruction filenames in runtime skill prose or Python.

- [ ] **Step 4: Register the skill in canonical/authored inventories**

Add `project-maintenance` in sorted order to `config/distribution.json`, `EXPECTED_SKILLS`, `AUTHORED_SKILLS`, and test constants. Update README's inventory text to say 27 for this intermediate implementation stage without advertising unfinished commands.

- [ ] **Step 5: Generate and validate distributions**

Run: `python3 scripts/sync_claude_distribution.py --apply`

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_distribution tests.test_sync_claude_distribution -v`

Run: `python3 scripts/validate_distribution.py && python3 scripts/sync_claude_distribution.py --check`

Expected: all commands exit `0`; generator reports 27 synced skills; generated Python bytes match canonical files.

- [ ] **Step 6: Commit the distributed foundation**

```bash
git add plugins/creative-writing-skills/skills/project-maintenance config/distribution.json scripts/validate_distribution.py tests/test_distribution.py tests/test_sync_claude_distribution.py README.md cw .claude-plugin/marketplace.json marketplace.json
git commit -m "feat: distribute project maintenance skill"
```

### Task 7: Verify the foundation milestone

**Files:**
- Modify only if verification exposes a defect in files owned by Tasks 1–6.

**Interfaces:**
- Produces: a runnable packaged CLI and valid 27-skill distribution.

- [ ] **Step 1: Run the CLI test package**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/cw_cli -t . -v`

Expected: all foundation tests pass.

- [ ] **Step 2: Run the complete repository suite**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v`

Expected: all existing and new tests pass.

- [ ] **Step 3: Run distribution and archive checks**

Run: `python3 scripts/validate_distribution.py && python3 scripts/vendor_generic_skills.py --check && python3 scripts/sync_claude_distribution.py --check && python3 scripts/create_skill_zips.py`

Expected: all commands exit `0`; archive generation includes the 27 configured skills exactly.

- [ ] **Step 4: Record the milestone commit if verification required fixes**

Stage only the exact files changed to fix a reproduced verification failure, then commit with `git commit -m "fix: stabilize story CLI foundation"`.

Skip this commit only when `git status --short` shows no milestone fixes or regenerated drift.

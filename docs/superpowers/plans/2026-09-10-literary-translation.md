# Literary Translation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Support standalone and attached literary translation projects, multiple source editions and target versions, durable translation memory, and recoverable translation workflows.

**Architecture:** Add opt-in schema v2 while retaining schema-v1 authoring behavior. Keep translation services in a focused `cwcli.translation` package, reusing the existing Markdown parser, findings, transaction journal, and guarded mutations. Three authored skills supply literary judgment; the CLI records explicit decisions and checks structure and dependencies.

**Tech Stack:** Existing Python standard library CLI, `unittest`, restricted YAML frontmatter in Markdown, JSON command input and journal metadata, current Codex-to-Claude/ZCode generator. No new runtime dependency or model API client.

**Spec:** [Approved design](../specs/2026-09-10-literary-translation-design.md).

## Global Constraints

- «Рабочий текст — Markdown.»
- «Полученные исходные файлы сохраняются без изменений.»
- «Принятый текст не переписывается автоматически.»
- «Субагенты не обязательны.»
- «Vendored-снимки не изменяются ради переводческой функциональности.»
- «Сохраняются проектные границы `<AI>...</AI>` и `<hidden>...</hidden>`.»
- Runtime source is `plugins/creative-writing-skills/`; never hand-edit `cw/` or generated manifests.
- Preserve unknown files, nested project boundaries, direct user edits, preview/apply and undo/recovery behavior. Do not require Git in story projects.
- No OCR engine, publishing export, automatic literary arbitration, or full-series analysis prerequisite.
- Schema-v1 projects remain supported without migration. Only enabling translation upgrades a project to v2.
- Add exactly three authored skills: 32 → 35 total. Do not bump or release the plugin as part of this plan.
- After each task that edits canonical runtime resources, run `python3 scripts/sync_claude_distribution.py --apply` and `python3 scripts/sync_claude_distribution.py --check`; include derived changes in that task's commit. Task 8 additionally runs the complete distribution and archive checks.

---

## Execution map and repository conventions

This is one dependency-ordered plan: the skills consume the same project contract and CLI, so they are not independent products. Tasks 1–7 progressively deliver testable mechanics; task 8 exposes the complete literary workflow and updates distribution. Do not advertise partially available commands in skills before their mechanics pass.

All paths below are repository-relative. `CLI` in explanatory text means `plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli`; file lists use full repository-relative paths. Run commands at repository root.

Existing entry points inspected:

- `documents.py`: `parse_document(bytes) -> Document`, `render_document(Document) -> bytes`; only scalars and lists of strings are supported. Do not introduce nested YAML.
- `project.py`: `Project.resolve(relative, for_write=True)` rejects unsafe write paths; `iter_managed_markdown()` currently walks only `story`, `work`, `kb`.
- `schema.py`: currently v1-only, identity inferred from paths; v2 adds domain identity fields with names distinct from the prohibited generic `id` and `type`.
- `transactions.py`: `Change(path, before, after)`, `TransactionPlan(command, changes, metadata)`, `TransactionStore`, `TransactionEngine`; byte snapshots already support binary content.
- `scaffold.py`: `render_scaffold`, `plan_init`, `apply_init`; preserve existing positional calls and defaults.
- `app.py`: `run(argv, cwd=..., stdout=..., stderr=...)`; mutation preview is default, `--apply` executes.
- `checks/__init__.py`: register `Callable[[Project], list[Finding]]` in `CHECKERS`.
- `tests/cw_cli/helpers.py`: imports bundled CLI for tests. Use `unittest`, not pytest.

New package files and responsibilities:

| File under `CLI/translation/` | Responsibility |
| --- | --- |
| `__init__.py` | Package marker only |
| `contract.py` | v2 settings, metadata validators, record kinds and scope matching |
| `catalog.py` | Safe discovery and immutable domain record lookup |
| `sources.py` | Edition registration, originals import, working unit revisions and manuscript references |
| `directions.py` | Direction registration, coverage, per-volume source overrides and alignment |
| `memory.py` | Memory record creation, acceptance/supersession and conflict selection |
| `context.py` | Fixed translation input packet and provenance snapshot |
| `drafts.py` | Translation draft creation, acceptance and dependency assessment |
| `commands.py` | argparse registration and adapters to services |

Do not grow existing authoring `drafts.py` or `context.py` into a second implementation of translation services. Reuse public helpers where useful; extract shared safety/tag handling only when both callers need it, with regression tests.

## Data and command contract used by all tasks

The implementation details here resolve storage choices within the approved design.

### Project and records

Schema v2 adds `project-kind: authoring | translation`, `work-kind: book | series`, and `translation-enabled: true`. Enabling on a v1 project retains `project-kind: authoring`, manuscript paths and the original meaning of `language`. A new translation project uses `language` for working documentation. Unknown schema versions are rejected for mutation; v1 validation stays unchanged.

For a series, `volume-id` is a portable slug, not an integer. A book uses the internal empty volume value and omits `volumes/` in paths. New stable identity fields are `edition-id`, `direction-id`, `unit-id`, `entity-id`, `record-id`, and `alignment-id`. Domain references are IDs, never translated titles. The catalog rejects duplicate IDs in their namespace and portable path collisions; file renames do not change domain identity.

Every metadata example below uses the existing parser subset. Domain JSON request objects may contain nested values, but persisted Markdown frontmatter must remain flat. Notes, evidence quotations, style instructions, variants and rationale live in the Markdown body.

```yaml
# sources/ja-original/edition.md
edition-id: ja-original
language: ja
edition-role: original
revision-label: supplied-edition
coverage:
  - v001
  - v002
```

Edition body names provenance, publication/translator information when known, and extraction limitations. Coverage lists explicit work volume IDs; absent volumes stay absent. Source unit files contain `unit-id`, optional `volume-id`, and `original-path` OR `manuscript-path`. A manuscript reference is a descriptor whose body is not substituted for the actual manuscript. Imported opaque originals, including Markdown, are excluded from document parsing and generic editing.

```yaml
# translations/ru-main/translation.md
direction-id: ru-main
language: ru
primary-edition: ja-original
auxiliary-editions:
  - en-official
coverage:
  - v001
inheritance:
  - names
```

Direction body states literary strategy. In a series, an optional `translations/<direction>/volumes/<volume>/settings.md` replaces explicitly supplied source/inheritance fields for that volume; omitted fields inherit. Per-volume overrides do not silently change shared memory. Validate that selected sources cover every requested unit. A primary translation edition is legal; output provenance must say it is indirect.

Alignment records in `kb/source-comparisons/<alignment-id>.md` have `alignment-id`, `source-units`, `reference-units`, `status: observed | accepted`, and `relation: equivalent | split | merge | reordered | omitted`. Unit references are `<edition-id>:<unit-id>`. Omission requires a body explanation; relations do not assert literary equivalence by themselves. Direction draft source lists explicitly declare the units being translated, so auxiliary alignment never determines output completeness implicitly.

Memory records live in `translations/<direction>/memory/{terms,voices,decisions}/<record-id>.md`; `style.md` is a single direction-wide record with a `record-id`. Fields: `record-id`, `status: observed | proposed | accepted | superseded`, `subject`, `scope-volumes`, `scope-units`, `scope-entities`, `scope-relationships`, `evidence`, and optional `supersedes`. Scope fields are lists of strings; absent/empty means unrestricted. Dimensions combine with AND, entries in a dimension with OR. Scope-unit refs are source unit IDs; relationship IDs are author/agent-defined stable identifiers. Body contains the actual rule and examples, including variants and negative examples. Shared `kb/entities/<entity-id>.md` records identity and evidence, not obligatory target-language renderings.

An exception supersedes a general rule only in its narrower matching scope through explicit `supersedes`. Two applicable accepted rules for the same subject with no such precedence produce a conflict, not an arbitrary winner. Evidence includes edition/unit references and readable chapter/scene descriptions. Agent inference creates `proposed`; an explicit human decision or previously approved inheritance policy may accept a record without another question.

### Public Python interfaces

All following services are introduced by the named tasks. They are not assumed to exist today. `Project`, `TransactionPlan`, `Document` and `Finding` are the existing types.

```python
# contract.py, task 1
def project_settings(metadata: dict[str, object]) -> tuple[str, str, bool]:
    """Return project-kind, work-kind, translation-enabled; reject invalid v2."""

# sources.py, task 3
def plan_source(project: Project, request: dict[str, object]) -> TransactionPlan:
    """Register edition or import/refresh a unit using the request action."""

# directions.py, task 4
def plan_direction(project: Project, content: bytes) -> TransactionPlan:
    """Register/update direction settings from flat-frontmatter Markdown."""
def plan_alignment(project: Project, content: bytes) -> TransactionPlan:
    """Register/update an explicit source comparison record."""

# memory.py, task 5
def plan_memory(project: Project, direction: str, kind: str,
                content: bytes) -> TransactionPlan:
    """Create/update a memory record; kind is terms, voices, decisions or style."""
def select_memory(project: Project, direction: str,
                  scope: dict[str, list[str]]) -> tuple[str, ...]:
    """Return ordered accepted record paths; raise ValueError on conflict."""

# context.py, task 6
def build_packet(project: Project, direction: str, units: tuple[str, ...],
                 scope: dict[str, list[str]]) -> dict[str, object]:
    """Return fixed text, provenance, selected rules and dependency digests."""

# drafts.py, task 7
def plan_translation_draft(project: Project, direction: str, draft_id: str,
                           packet: dict[str, object], content: bytes) -> TransactionPlan:
    """Create draft with guarded input snapshot; never call a model."""
def plan_translation_accept(project: Project, draft_path: str) -> TransactionPlan:
    """Accept reviewed draft with guarded base and input revisions."""
def translation_status(project: Project, draft_path: str) -> dict[str, object]:
    """Return acceptance state, freshness and changed dependency paths."""

# checks/translation.py, task 7
def check_translation(project: Project) -> list[Finding]:
    """Read-only structural/dependency findings; [] for v1 projects."""
```

Commands use `cw translation` to avoid overloading authoring commands:

```text
cw init PATH --title TITLE --language LANG --kind translation --work-kind book|series [--apply]
cw translation enable --work-kind book|series [--apply]
cw translation source --request REQUEST.json [--apply]
cw translation direction --file DIRECTION.md [--apply]
cw translation alignment --file ALIGNMENT.md [--apply]
cw translation memory --direction ID --kind terms|voices|decisions|style --file RECORD.md [--apply]
cw translation context --direction ID --units EDITION:UNIT [EDITION:UNIT ...] --scope SCOPE.json
cw translation draft --direction ID --draft-id ID --packet PACKET.json --file TEXT.md [--apply]
cw translation accept DRAFT_PATH [--apply]
cw translation status DRAFT_PATH
cw check translation
```

All commands support `--format json`. `context` emits the packet without mutating project state; the agent writes its result to a temporary input file when needed. The draft transaction stores the exact packet in journal metadata and records its transaction ID in draft frontmatter. This reuses protected journal storage instead of inventing an unrelated cache writer. `context` never launches agents. Scope JSON uses the four scope fields above. Volume/unit scope is derived from requested units and cannot be overridden to select unrelated rules.

## Task 1: Schema v2 and compatibility-aware project discovery

**Files:**
- Create: `plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/translation/__init__.py`
- Create: `plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/translation/contract.py`
- Create: `plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/translation/catalog.py`
- Modify: `plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/schema.py`
- Modify: `plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/project.py`
- Modify: `plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/checks/structure.py`
- Test: `tests/cw_cli/test_translation_contract.py`
- Test: `tests/cw_cli/test_schema.py`, `tests/cw_cli/test_project.py`, `tests/cw_cli/test_structure_check.py`

**Interfaces:** Produces `project_settings` and `catalog.load_catalog(project) -> dict[str, Document]`, keyed by project-relative path. Catalog reads regular permitted records, rejects symlink/nested-boundary references and duplicate domain IDs, skips opaque originals. Preserve existing `allowed_document_kind(relative_id)` as a v1 default; add keyword `schema_version=1` for v2 callers. Add `schema.required_paths(metadata) -> tuple[tuple[str, ...], tuple[str, ...]]` returning directories/files for the selected project kind. Existing v1 constants retain their meanings.

- [x] Add failing tests including this compatibility example:

```python
import unittest
from . import helpers
from cwcli.translation.contract import project_settings

class TranslationContractTests(unittest.TestCase):
    def test_legacy_defaults_are_authoring(self):
        self.assertEqual(("authoring", "book", False),
                         project_settings({"schema-version": 1, "language": "ja"}))

    def test_new_translation_project(self):
        self.assertEqual(("translation", "series", True), project_settings({
            "schema-version": 2, "project-kind": "translation",
            "work-kind": "series", "translation-enabled": True, "language": "ru"}))
```

- [x] Run `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.cw_cli.test_translation_contract -v`; expect missing module/interface failure.
- [x] Implement schema dispatch without changing YAML parsing. Use this branching core, then enforce v2 enum/boolean fields with `ValueError` in services and findings in read-only checks:

```python
version = metadata.get("schema-version")
if type(version) is not int or version not in (1, 2):
    raise ValueError("unsupported project schema")
if version == 1:
    return "authoring", "book", False
```

- [x] Extend managed walking only for enabled v2: `sources` and `translations`; prune every `originals` subtree before parsing. Register strict v2 record paths including per-volume settings and shared entity/alignment paths. Test mixed book/series layout rejection and identical IDs at renamed paths. Keep unknown entries untouched.
- [x] Run the four listed test modules. Assert v1 generated paths and errors remain unchanged, standalone translation does not require `story/`, and sources outside the nearest project cannot be read through a reference.
- [x] Commit task files and their generated counterparts: `feat: define compatible translation project schema`.

## Task 2: Recoverable setup, enabling and transaction input guards

**Files:**
- Create: `plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/translation/commands.py`
- Modify: `plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/scaffold.py`
- Modify: `plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/app.py`
- Modify: `plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/transactions.py`
- Modify: `plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/migration.py`
- Test: `tests/cw_cli/test_translation_setup.py`, `tests/cw_cli/test_transactions_apply.py`, `tests/cw_cli/test_init_command.py`, `tests/cw_cli/test_migration_plan.py`

**Interfaces:** Add optional keyword-only `kind="authoring", work_kind="book"` to scaffold public calls. `commands.add_commands(subparsers, error_stream)` and `commands.run_translation(args, *, cwd, stdout, stderr) -> int` attach to existing app dispatch. Transaction metadata may include `read-guards: {relative_path: exact_sha256}` and `translation-packet`; old journals without these keys retain behavior. Reject any guard path crossing protected read boundaries, links or nested projects. Validate guards before first apply write; recovery continues the stored transaction and retains the original snapshot rather than rebasing it.

- [x] Add preview/apply tests using the existing `app.run` injection pattern:

```python
stdout, stderr = io.StringIO(), io.StringIO()
status = app.run(["init", str(root), "--title", "Series", "--language", "ru",
                  "--kind", "translation", "--work-kind", "series", "--format", "json"],
                 cwd=root.parent, stdout=stdout, stderr=stderr)
self.assertEqual(0, status, stderr.getvalue())
self.assertFalse(root.exists())
```

- [x] Run `python3 -m unittest tests.cw_cli.test_translation_setup -v`; expect argparse rejection until implemented.
- [x] Implement new initialization using `required_paths`, and `translation enable` as one plan changing manifest and creating absent translation directories/indexes. Existing populated `sources/` or `translations/` require explicit registration, never automatic adoption or overwrite. Preserve author manuscript bytes and unknown paths; do not route canonical v2 through legacy v1 migration. Legacy migration on v2 returns an actionable unsupported-operation error without writes.
- [x] Add transaction guard checks using exact binary digests, not UTF-8 logical hashes:

```python
import hashlib
actual = hashlib.sha256(source_bytes).hexdigest()
if actual != expected_digest:
    raise TransactionConflict(f"stale read precondition for {relative}")
```

Read through existing safe regular-file facilities, validate metadata when preparing/loading a journal, and preserve preview purity. This is optimistic conflict detection consistent with existing transactions, not a promise to lock out external editors.

- [x] Test a source edited between preview and apply: conflict, no output write. Test undo of enable, interrupted apply/recovery, unknown schema rejection and old init unchanged. Run all four listed modules.
- [x] Commit task files: `feat: initialize and enable translation projects safely`.

## Task 3: Source editions, opaque originals and working revisions

**Files:**
- Create: `plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/translation/sources.py`
- Modify: `plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/translation/catalog.py`
- Modify: `plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/translation/commands.py`
- Modify: `plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/edits.py`
- Test: `tests/cw_cli/test_translation_sources.py`

**Interfaces:** Implements `plan_source`. Request actions: `edition` with `content` Markdown string; `unit` with `edition`, `unit`, optional `volume`, `original-file`, `text-file`; `manuscript-unit` with `edition`, `unit`, optional `volume`, `manuscript-path`; `refresh-unit` with `edition`, `unit`, `text-file`. Import paths are explicit user-selected external regular files; source target paths are generated internally. Refuse symlink input and nonregular files. Existing original destinations cannot be replaced. A new supplied original uses a new edition identity; refreshing extraction preserves originals.

- [x] Write source tests; use a temporary v2 project initialized by the task-2 CLI. The helper `apply_plan(project, plan)` may follow the existing transaction test setup, but must invoke the real engine, not directly write planned changes.

```python
request = {"action": "unit", "edition": "ja-original", "unit": "u001",
           "volume": "v001", "original-file": str(original), "text-file": str(text)}
before = original.read_bytes()
plan = plan_source(project, request)
copies = [c for c in plan.changes if "/originals/" in c.path]
self.assertEqual(1, len(copies))
self.assertEqual(before, copies[0].after)
self.assertIsNone(copies[0].before)
```

- [x] Run `python3 -m unittest tests.cw_cli.test_translation_sources -v`; expect missing `plan_source`.
- [x] Implement imports as `Change` objects plus provenance in edition/unit records. Use SHA-256 for original bytes and existing journal snapshots for all overwritten working text. `refresh-unit` changes only working text/provenance, preserving `unit-id`. A manuscript descriptor reads the actual `story/` file; do not create a prose copy in `sources/`.

```python
changes.append(Change(destination, None, original_bytes))
metadata = {"read-guards": current_project_input_hashes,
            "translation-source": {"edition": edition_id, "unit": unit_id}}
return TransactionPlan(("translation", "source"), tuple(changes), metadata)
```

- [x] Protect `originals/` and domain identity/lifecycle frontmatter from generic agent edits while allowing direct user changes to be detected. Test binary and Markdown originals, extraction correction, missing volume coverage, manuscript edit detection, duplicate identity, nested project and symlink refusal.
- [x] Run source tests plus `tests.cw_cli.test_edits`, `tests.cw_cli.test_transactions_apply`. Commit: `feat: register translation sources with preserved provenance`.

## Task 4: Directions, explicit coverage and alignment

**Files:**
- Create: `plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/translation/directions.py`
- Modify: `plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/translation/contract.py`
- Modify: `plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/translation/commands.py`
- Test: `tests/cw_cli/test_translation_directions.py`

**Interfaces:** Implements `plan_direction`, `plan_alignment`. Add `effective_direction(project, direction, volume) -> dict[str, object]` in `directions.py`. `direction --file` accepts either a full direction record or a volume settings record containing `direction-id` and `volume-id`. Root direction must exist before applying an override.

- [x] Write tests for two same-language directions and per-volume precedence:

```python
settings = effective_direction(project, "ru-main", "v023")
self.assertEqual("ja-original", settings["primary-edition"])
self.assertEqual([], settings["auxiliary-editions"])
```

Fixture: root names `en-official` as auxiliary, v023 override explicitly has an empty auxiliary list because the edition ends at v022. Also test absence of an override: unavailable auxiliary is reported, not silently fabricated; required primary absence blocks the affected unit.

- [x] Run `python3 -m unittest tests.cw_cli.test_translation_directions -v`; expect missing service.
- [x] Implement flat field override, validating source IDs, language tags, coverage and reference cycles. An empty list is an explicit replacement, not missing:

```python
effective = dict(direction_metadata)
for field in ("primary-edition", "auxiliary-editions", "inheritance"):
    if field in volume_metadata:
        effective[field] = volume_metadata[field]
```

- [x] Implement explicit alignments as independent Markdown records. Test one-to-many, many-to-one, reordered and omitted records, accepted versus observed status, invalid references and distinct editions with identical chapter titles. Translation source as primary is accepted with indirect provenance.
- [x] Run module and contract tests. Commit: `feat: model translation directions and source alignment`.

## Task 5: Scoped memory with explicit acceptance and precedence

**Files:**
- Create: `plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/translation/memory.py`
- Modify: `plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/translation/contract.py`
- Modify: `plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/translation/commands.py`
- Test: `tests/cw_cli/test_translation_memory.py`

**Interfaces:** Implements `plan_memory` and `select_memory`. Add `scope_matches(record: dict[str, object], context: dict[str, list[str]]) -> bool` in contract. Shared entity creation uses `memory --kind entity` as an additional accepted command kind with no direction argument; entity records go only to `kb/entities/`. Update argparse choices and command reference accordingly. Entity identity statements do not carry target-language rules.

- [x] Add an executable scope test and fixtures for accepted/proposed records:

```python
from cwcli.translation.contract import scope_matches

self.assertTrue(scope_matches({"scope-volumes": ["v023"],
                               "scope-entities": ["hero"]},
                              {"scope-volumes": ["v023"],
                               "scope-entities": ["hero", "mentor"]}))
self.assertFalse(scope_matches({"scope-volumes": ["v023"]},
                               {"scope-volumes": ["v001"]}))
```

- [x] Run `python3 -m unittest tests.cw_cli.test_translation_memory -v`; expect missing scope/memory interfaces.
- [x] Implement matching with exact identity values:

```python
fields = ("scope-volumes", "scope-units", "scope-entities", "scope-relationships")
return all(not record.get(field) or
           bool(set(record[field]) & set(context.get(field, [])))
           for field in fields)
```

Validate list types before matching. Select accepted rules only; reject overlapping same-subject rules unless an explicit valid narrower `supersedes` relation resolves the overlap. Detect supersession cycles and cross-direction supersession. Global replacement marks old record superseded in the same transaction; a scoped exception leaves the general record active outside its scope.

- [x] Store rule prose, examples, evidence, variants and rationale without translating or inferring them in Python. Test polysemous identical surface forms with different subjects, narrator voices, relationship scope, no cross-language leakage, rejected cycles, user-edited rule content and inheritance proposals remaining provisional.
- [x] Run memory and transaction tests. Commit: `feat: persist scoped translation terminology and voices`.

## Task 6: Fixed context packets and complete dependency tracking

**Files:**
- Create: `plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/translation/context.py`
- Modify: `plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/translation/commands.py`
- Test: `tests/cw_cli/test_translation_context.py`

**Interfaces:** Implements `build_packet`. JSON shape: `packet-version: 1`, `direction`, `units`, `scope`, `primary-text`, `reference-text`, `neighbor-text`, `rules`, `dependencies`, `memory-catalog-digest`, `provenance`. Text values are ordered lists of `{path, text}` objects. Dependencies map regular project paths to exact SHA-256. Rules come from `select_memory`; source resolution from catalog/effective direction. The catalog digest covers the direction's entire memory inventory to detect newly added applicable rules, not just changes to previously selected files.

- [x] Add packet tests using task-3 source and task-5 memory fixtures:

```python
packet = build_packet(project, "ru-main", ("ja-original:u001",), {})
self.assertEqual(1, packet["packet-version"])
self.assertEqual(["ja-original:u001"], packet["units"])
self.assertIn("translations/ru-main/translation.md", packet["dependencies"])
self.assertNotIn("translations/en-continuation/memory/style.md", packet["dependencies"])
```

- [x] Run `python3 -m unittest tests.cw_cli.test_translation_context -v`; expect missing packet builder.
- [x] Build text from exact source revisions and relevant accepted alignments; include adjacent units read-only with clear exclusion from the translation scope. Derived scope-units and scope-volumes cannot be contradicted by input. Include primary/auxiliary settings, evidence and neighbor dependencies, manifest and selected memory. No automatic five-chunk sampling is treated as a complete glossary.

```python
dependencies = {path: hashlib.sha256(data).hexdigest()
                for path, data in sorted(read_inputs.items())}
```

All reads use catalog boundary enforcement. Packet metadata explicitly states source precedence, indirect translation provenance, and the requirement to preserve early ambiguity. Hidden content remains marked in trusted translator packets, never becomes publishable prose. Do not reuse unrestricted packets as character/reader simulation contexts.

- [x] Test incomplete auxiliary coverage with an explicit override, changed neighbor text, new memory records, source alignment changes, missing primary and stable output on unchanged files. A partial failure must identify only affected units; separate context requests for other units succeed.
- [x] Run context and existing context-redaction tests. Commit: `feat: assemble versioned literary translation context`.

## Task 7: Draft acceptance, freshness, indexes and project health

**Files:**
- Create: `plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/translation/drafts.py`
- Create: `plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/checks/translation.py`
- Modify: `plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/translation/commands.py`
- Modify: `plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/checks/__init__.py`
- Modify: `plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/indexes.py`
- Modify: `plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/doctor.py`
- Modify: `plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/checks/prose.py`
- Modify: `plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/checks/kb.py`
- Modify: `plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/edits.py`
- Test: `tests/cw_cli/test_translation_drafts.py`, `tests/cw_cli/test_translation_check.py`, `tests/cw_cli/test_translation_integration.py`

**Interfaces:** Implements the three draft services and `check_translation`. Draft metadata: `direction-id`, `draft-id`, `source-units`, `packet-transaction`, `base-revision`, `status: draft | reviewed | accepted`; body contains prose. Status transition to reviewed uses an additional `cw translation set-status DRAFT_PATH reviewed` command; no arbitrary acceptance through generic edits. Draft content remains editable with exact edits. Accepted path mirrors draft basename within its volume. Revisions replace that accepted file only after matching its captured base; journal retains prior bytes.

- [x] Add lifecycle tests, including independence of acceptance and freshness:

```python
state = translation_status(project, draft_path)
self.assertEqual("accepted", state["status"])
accepted_before = accepted_path.read_bytes()
memory_path.write_text(memory_path.read_text() + "\nNew guidance.\n")
state = translation_status(project, draft_path)
self.assertEqual("accepted", state["status"])
self.assertEqual("needs-review", state["freshness"])
self.assertEqual(accepted_before, accepted_path.read_bytes())
```

- [x] Run the three new modules; expect missing lifecycle/checker interfaces.
- [x] Validate packet fields and re-read dependencies when creating a draft; never trust arbitrary packet text as current project input. Store packet text/provenance in immutable transaction metadata, with generated transaction ID allocated before rendering draft metadata. Reject stale/missing snapshots at accept; user/agent must build a fresh context and reviewed revision. Preserve read-only status for accepted-but-stale text.

```python
freshness = "needs-review" if changed_paths or memory_inventory_changed else "current"
return {"status": draft.metadata["status"], "freshness": freshness,
        "changed-dependencies": sorted(changed_paths)}
```

- [x] Acceptance requires reviewed state, current input guards and unchanged accepted base. Reject hidden material and preserve existing accepted-text handling of balanced AI suggestion wrappers. Unit coverage is explicit: reject duplicate accepted coverage in one direction unless it is the revision of the same output; support a draft translating multiple units from one volume. For cross-volume work use separate drafts. Detect omissions against declared direction coverage and available unit inventory; do not infer completeness from paragraph counts.
- [x] Add generated `sources/_index.md`, `translations/_index.md`, per-direction indexes and shared entity/comparison indexes via v2-aware index selection. No index inside `originals/`. Add new paths to doctor/link/KB behavior without scanning opaque originals. Prose checks select the direction language/profile for translation outputs and exclude original source text; v1 authoring output remains unchanged.
- [x] Check recovery after interrupted acceptance, undo of accepted replacement, missing journal, new rule inventory, deleted source, source file rename with stable ID, two target directions, same-language editions, and old v1 fixtures. Findings use `CW-TRANS-*`, descriptive paths and existing severity/exit conventions; `check all` includes translation but v1 returns no translation findings.
- [x] Run `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/cw_cli -t . -v`. Commit: `feat: track and accept translation drafts with revision checks`.

## Task 8: Literary skills, integration, distribution and end-to-end evidence

**Files:**
- Create: `plugins/creative-writing-skills/skills/literary-translation/SKILL.md`
- Create: `plugins/creative-writing-skills/skills/literary-translation/resources/workflow.md`
- Create: `plugins/creative-writing-skills/skills/literary-translation/agents/openai.yaml`
- Create: `plugins/creative-writing-skills/skills/translation-memory/SKILL.md`
- Create: `plugins/creative-writing-skills/skills/translation-memory/resources/records.md`
- Create: `plugins/creative-writing-skills/skills/translation-memory/agents/openai.yaml`
- Create: `plugins/creative-writing-skills/skills/translation-review/SKILL.md`
- Create: `plugins/creative-writing-skills/skills/translation-review/resources/review-rubric.md`
- Create: `plugins/creative-writing-skills/skills/translation-review/agents/openai.yaml`
- Modify: `plugins/creative-writing-skills/skills/project-setup/SKILL.md`
- Modify: `plugins/creative-writing-skills/skills/project-maintenance/SKILL.md`
- Modify: `plugins/creative-writing-skills/skills/project-maintenance/resources/project-contract.md`
- Modify: `plugins/creative-writing-skills/skills/project-maintenance/resources/command-reference.md`
- Modify: `plugins/creative-writing-skills/skills/creative-writing-muse/SKILL.md`
- Modify: `plugins/creative-writing-skills/skills/story-memory/SKILL.md`
- Modify: `plugins/creative-writing-skills/skills/project-doctor/SKILL.md`
- Modify: `config/distribution.json`, `scripts/validate_distribution.py`, `README.md`, `AGENTS.md`
- Modify: `tests/test_distribution.py`, `tests/test_sync_claude_distribution.py`, `tests/test_story_project_integration.py`
- Create: `tests/test_translation_skills.py`
- Create: `tests/fixtures/translation-pressure/scenarios.md`
- Create: `tests/fixtures/translation-pressure/results.md`
- Generated: `cw/`, distribution manifests and `zips/` only through repository scripts.

**Interfaces:** Three skills route to the implemented commands, sharing the contract resource through `$project-maintenance`. Skill-owned resources use relative links. No new worker role is required: muse can assign a bounded translation task through existing worker conventions with a fixed packet and distinct output paths. Sequential execution is fully described. UI metadata follows existing authored skill conventions and is excluded from generated Claude runtime by the existing generator.

- [x] Add a distribution test for the new authored inventory and a real lifecycle integration scenario before adding skill files:

```python
config = json.loads((ROOT / "config/distribution.json").read_text())
names = {"literary-translation", "translation-memory", "translation-review"}
self.assertTrue(names <= set(config["authored_skills"]))
self.assertEqual(35, len(config["canonical_skills"]))
```

Use `ROOT = Path(__file__).resolve().parents[1]` and standard `unittest` imports. Integration test executes `app.run`, not a regex proxy for literary correctness. Create small synthetic Japanese/English excerpts instead of committing copyrighted book text; declare coverage v001–v032/v001–v022 and materialize only the units needed by each fixture.

- [x] Run `python3 -m unittest tests.test_translation_skills -v`; expect missing inventory/resources.
- [x] Write the three skills as imperative instructions. `literary-translation` must include this operational core:

```text
Resolve the direction and source coverage before translating. Treat the selected
primary edition as the content authority. Use auxiliary editions only within the
approved strategy. Preserve deliberate ambiguity, omissions by a speaker, and
the timing of revelations. Do not add explanations or simplify a distinctive
voice merely to make the text smoother. Use a fixed context packet; keep worker
observations provisional. Continue independent units when one source is blocked.
```

`translation-memory` explains identity versus surface form, source observation versus target instruction, scoped exceptions, narrator/relationship voice, evidence, author-confirmed acceptance and inherited-policy limits. `translation-review` requires source and target locators, diagnosis and severity; offers separate fidelity and target-language passes and explicitly says technical checks do not establish literary quality. Examples cover direct/indirect translation, existing English continuity and independent Russian choices.
- [x] Integrate setup/muse/memory/doctor routing and document all final commands, including `memory --kind entity` and `set-status`. Add frontmatter/body examples from this plan, direction-specific language behavior and v1 upgrade preview. Keep implementation hashes and cache mechanics out of author-facing questions.
- [x] Update exact inventory assertions and README/AGENTS counts to 35. Locate remaining inventory assumptions with `rg -n '\b32\b|EXPECTED_SKILLS|authored_skills' scripts tests README.md AGENTS.md config`; change only inventory-related occurrences. Preserve pinned vendored content and plugin version.
- [x] Record pressure scenarios and inspect outcomes: English precedent contradicts Japanese meaning; a polite threatening voice; identical term spelling with two meanings; late-volume secret; unavailable auxiliary v023; two simultaneous languages; no subagents; user correction supersedes a term. In `results.md`, record actual observed responses/commands and pass/fail with limitations, never claim a model evaluation from static substring tests. Execute these scenarios via the chosen execution mode; no new user-visible tasks are necessary.
- [x] Run required repository checks in order:

```bash
python3 scripts/sync_claude_distribution.py --apply
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
python3 scripts/validate_distribution.py
python3 scripts/vendor_generic_skills.py --check
python3 scripts/sync_claude_distribution.py --check
python3 scripts/create_skill_zips.py
git diff --check
```

- [x] Inspect generated skill inventory, Codex reference transformations and exclusion of `agents/openai.yaml`. Run archive creation a second time and compare SHA-256 maps of `zips/*.skill` to verify deterministic results for the new inventory. Do not hand-fix generator output.
- [x] Commit canonical resources, tests and generated changes together: `feat: ship literary translation skills and workflows`. Report checks and any literary evaluation limitations. Do not release, tag or push without an explicit request.

## Plan self-review and handoff

Coverage mapping: compatible storage/schema (tasks 1–2), original preservation/revisions (3), editions/directions/coverage/alignment (4), terminology/voices/provenance/acceptance (5), context and language isolation (6), lifecycle/staleness/recovery/checks (7), three skills/distribution/all six approved scenarios (8). Source read guards are implemented before consumers; all cross-task service names are declared above. Commands for entity records and reviewed status are explicitly added by tasks 5 and 7.

This document is a plan, not evidence that runtime functionality exists. Before implementation, use either subagent-driven-development with review between tasks or executing-plans sequentially in this session. Start from the approved spec and this plan; preserve unrelated workspace edits.


## Execution refinements

- Empty list fields are interpreted through the existing flat parser (no YAML dependency).
- Source units store a positive per-volume order; context must not infer chronology from IDs.
- Context tolerates malformed source files only outside the selected volume; project checks still report them.
- `translation/indexes.py` isolates v2 indexes while preserving the v1 index service.
- Historical muse pressure outputs retain their exact tested snapshot; translation evaluation is recorded separately.
- Additional integration coverage lives in `tests/cw_cli/test_translation_boundaries.py`.

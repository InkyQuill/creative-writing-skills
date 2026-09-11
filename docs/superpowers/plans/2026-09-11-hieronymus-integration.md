# Optional Hieronymus Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make CWS and Hieronymus independently usable and mutually aware, with memory use governed by the user's free-text project agreement.

**Architecture:** CWS publishes a versioned structural contract and supplies an optional integration skill. Hieronymus supplies its own read-only project adapter and bundled compatibility resource. Agents interpret trust instructions; deterministic code handles identity, context boundaries, revisions and transport, never trust policy.

**Tech Stack:** Existing Markdown skills, Python standard library and unittest in CWS; Rust, serde/serde_json, existing serde_yaml_ng, existing MCP/CLI and SQLite domain services in Hieronymus. No new runtime dependency, shared SDK or third plugin.

**Spec:** [Approved integration design](../specs/2026-09-11-hieronymus-integration-design.md).

## Global Constraints

- «Договор не сводится к переключателю между двумя режимами, числовому рейтингу или обязательным полям.»
- «Если специальных указаний нет, файловая память основная, Hieronymus дополнительный.»
- «Наличие MCP, установленного плагина или технической привязки не меняет доверие автоматически.»
- «Доверие к сведениям не равнозначно поручению менять данные.»
- «Обязательной записи в оба хранилища нет.»
- «Если Hieronymus заменяет файловую память, полная Markdown-копия не обязательна.»
- «Субагенты не обязательны.»
- «Проектное предпочтение не позволяет подделать доверенную коррекцию в Hieronymus; внутреннее активное правило не отменяет договор пользователя.»
- No installation of the other product, no raw database access, no automatic whole-project ingestion, no background synchronization.
- Do not hand-edit generated CWS `cw/` output or Hieronymus installed plugin bundles. Do not modify vendored generic skills or frozen Python compatibility evidence.
- Preserve source tags, author secrets, nested project boundaries, unknown files, direct author edits and recoverable CWS mutations.
- Never advertise unimplemented translation features. Do not release, push, or bump versions as part of this plan.

---

## Repository roots, milestones and execution order

`CWS` means `/home/inky/Development/creative-writing-skills`; `H` means `/home/inky/Development/hieronymus`. Paths in each task are relative to its named root. Run commands from that root. The canonical plan lives in CWS; no second editable plan copy is required in H.

At planning time CWS is at `ea309a8`; H includes `ad61ea3` and user changes in `.gitignore`, `.claude/`, and two icon files. Recheck both worktrees at execution time. Use isolated worktrees according to the execution skill; preserve other work and commit only task-owned changes.

This is one cross-repository feature with two independently verifiable milestones:

- **Milestone A, tasks 1–5:** current schema-v1 authoring projects, project agreement, optional memory use and standalone Hieronymus project inspection. Deliverable without the translation feature.
- **Milestone B, tasks 6–8:** translation edition/direction mapping and external-memory revision dependencies. Requires tasks 1–7 of the existing [literary translation plan](2026-09-10-literary-translation.md); translation-skill routing additionally requires its task 8. Do not execute that entire plan implicitly. If prerequisites are absent, deliver A and identify B as pending, not as complete integration.
- **Task 9:** verification of the delivered milestone and cross-product acceptance. Full spec completion requires B and all applicable acceptance cases.

After every CWS runtime task, regenerate with `python3 scripts/sync_claude_distribution.py --apply`, check with `--check`, and include generated changes in the task commit. Add one authored skill relative to the actual inventory: 32 → 33 before translation, or 35 → 36 after translation. Amend the old translation plan's fixed counts to include this skill when reconciling plans; do not accidentally remove it to restore 35.

## File ownership and interfaces

| Location | Responsibility |
| --- | --- |
| CWS `plugins/creative-writing-skills/skills/project-maintenance/resources/external-project-contract.md` | Public structural rules, independent of memory authority |
| CWS `plugins/creative-writing-skills/skills/project-maintenance/resources/compatibility/cws-project-v1.json` | Versioned data-only examples and expected structural classifications |
| CWS `plugins/creative-writing-skills/skills/hieronymus-integration/` | Free-text agreement workflow and public-tool recipes |
| H `crates/hieronymus/src/cws_project.rs` | Read-only root and manifest discovery, document roles, relative-path safety |
| H `crates/hieronymus/src/cws_binding.rs` | Versioned technical binding and selection, without trust fields |
| H `crates/hiero/src/project_context.rs` | CLI JSON/human projection; no database or service startup |
| H `crates/hiero/resources/cws-project.md` | Bundled skill instructions for standalone CWS project reading |
| H `compatibility/rust/cws-project-v1.json` | Pinned copy of public examples for independent tests |
| CWS `cwcli/translation/external_memory.py` under the bundled CLI | External reference/freshness bookkeeping after translation prerequisites |

### Binding contract

Use an additive `cws` object in project-root `.hieronymus.json`; retain legacy outer fields only for old consumers outside the CWS path. New CWS consumers must use the object and never silently fall back to those legacy language defaults.

```json
{
  "series_slug": "example-work",
  "cws": {
    "binding_version": 1,
    "project_contract_version": 1,
    "directions": {
      "ru-main": {"series_slug": "example-work"},
      "ru-alternative": {"series_slug": "example-work"}
    }
  }
}
```

`series_slug` above is only a fixture, never a value to create in a user's installation. The root slug is the optional common-work binding; a direction slug is independently resolved. Source and target languages come from actual project/direction metadata, not from the map key or filename. `directions` may be empty for authoring. `cws` fields are technical; reject unsupported binding versions and unrecognized fields inside this v1 object. Preserve unrelated outer fields when explicitly adding a binding. Do not store credentials, host IDs, receipts, selected viewpoint, trust policy or task state here.

No automatic binding writer is required. The skill writes a binding only as part of authorized connection work, after resolving real series via public tools, validating paths and re-reading the current file. Project inspection never creates it. Multiple plausible choices are returned as ambiguous rather than selecting the first.

### Inspection contract

Add this read-only command, reusing existing global `--cwd` and `--args` parsing:

```sh
hiero project-context --cwd /path/to/project --args '{"direction_id":null}' --json
```

Output keys: `version:1`, `status`, `root`, `schema_version`, `instructions_path`, `binding`, `direction_id`, `source_language`, `target_language`, `diagnostics`. Optional values use null. `status` is `ready`, `unbound`, `ambiguous`, `unsupported`, `not_found`, or `invalid`; diagnostics are technical codes, not interpretations of the agreement. Return exit 0 for ready/unbound, 1 for ambiguous/unsupported/not_found and 2 for invalid input or unsafe filesystem access.

The command returns paths and technical metadata, not manuscript text or the contents of `AGENTS.md`. It does not construct a chronology, select a character, start a session or initiate a daemon. Skills read instructions and task evidence separately.

The external structural contract version is independent of `project.md`'s `schema-version`: contract v1 describes schema v1 initially and gains schema-v2 examples only after milestone B's prerequisites are implemented.

## Task 1 — Publish the current project contract with executable examples (CWS)

**Files:**
- Create: `plugins/creative-writing-skills/skills/project-maintenance/resources/external-project-contract.md`
- Create: `plugins/creative-writing-skills/skills/project-maintenance/resources/compatibility/cws-project-v1.json`
- Modify: `plugins/creative-writing-skills/skills/project-maintenance/SKILL.md`
- Modify: `plugins/creative-writing-skills/skills/project-maintenance/resources/project-contract.md`
- Create: `tests/test_external_project_contract.py`

**Interfaces:** Data format `{contract_version:1, project_schemas:[1], cases:[{name,files,expect}]}`. `files` maps portable relative paths to UTF-8 file contents. `expect` contains root, schema, roles or expected technical failure. Public roles: `instructions`, `manifest`, `accepted_prose`, `draft`, `work`, `knowledge`, `derived`, `private_state`, `opaque`. A role identifies structure, not authority.

- [ ] Add test fixtures for ordinary chapters, side-story ordering, draft metadata, `_index.md`, hidden text, nested projects, unknown schema and an unknown root file. Minimal positive case:

```json
{"name":"authoring-basic","files":{"AGENTS.md":"Prefer files unless I say otherwise.\n","project.md":"---\nschema-version: 1\ntitle: Example\nlanguage: ru\nstatus: drafting\n---\n","story/chapters/01.md":"---\nnumber: 1\n---\nText.\n"},"expect":{"root":".","schema_version":1,"roles":{"story/chapters/01.md":"accepted_prose"}}}
```

- [ ] Add a unittest that materializes each case into `TemporaryDirectory`, imports the existing `cwcli.project.discover_project` and schema checker via the repository's helper, and compares actual root/schema/allowed document kind to expected roles. Use a literal mapping from existing CWS document kinds to public roles, not a second path-classifier implementation. Core assertion:

```python
from tests.cw_cli import helpers
from cwcli.project import discover_project

project = discover_project(case_root / "story")
self.assertEqual(project.root, case_root.resolve())
self.assertEqual(project.manifest.metadata["schema-version"], 1)
```

- [ ] Run `python3 -m unittest discover -s tests -p test_external_project_contract.py -v`; expect missing fixture/resource failure first.
- [ ] Write the resource with the nearest-project boundary, manifest parser subset, numbered chapters and `after` ordering, roles above, protected paths, opaque legacy originals, direct author edits and source tags. Link from maintenance. State explicitly that neither `accepted_prose` nor `knowledge` decides trust.
- [ ] Run focused tests and distribution regeneration/check. Commit `docs: publish external CWS project contract` with fixtures/tests and generated resources.

## Task 2 — Implement safe standalone project discovery and binding (H)

**Files:**
- Create: `crates/hieronymus/src/cws_project.rs`
- Create: `crates/hieronymus/src/cws_binding.rs`
- Modify: `crates/hieronymus/src/lib.rs`
- Modify: `crates/hieronymus/src/agent_context.rs`
- Create: `crates/hieronymus/tests/cws_project.rs`
- Create: `compatibility/rust/cws-project-v1.json`

**Interfaces:**

```rust
pub enum DocumentRole {
    Instructions, Manifest, AcceptedProse, Draft, Work,
    Knowledge, Derived, PrivateState, Opaque,
}
pub struct CwsProject {
    pub root: std::path::PathBuf,
    pub schema_version: u64,
    pub language: String,
}
pub fn discover(start: &std::path::Path) -> Result<Option<CwsProject>, CwsError>;
pub fn classify(project: &CwsProject, relative: &std::path::Path)
    -> Result<DocumentRole, CwsError>;
pub struct SelectedBinding { pub series_slug: String }
pub fn select_binding(project: &CwsProject, direction: Option<&str>)
    -> Result<Option<SelectedBinding>, CwsError>;
```

Define `CwsError` with `UnsafePath`, `InvalidManifest`, `UnsupportedSchema(u64)`, `InvalidBinding`, `UnsupportedBinding(u64)`, `AmbiguousDirection`, `UnknownDirection(String)` and `Io(std::io::Error)`, with `thiserror` Display messages. Declare it in `cws_project`; binding imports it. Unknown structural roles return `Opaque`, not a guessed manuscript role.

- [ ] Copy task-1 fixture bytes into H with a recorded upstream commit in an adjacent comment/documentation reference. Add a test that materializes fixtures and invokes the new APIs. Also add an actual symlink test and this nested-boundary test:

```rust
#[test]
fn nested_project_does_not_inherit_outer_binding() {
    let dir = tempfile::tempdir().unwrap();
    let inner = dir.path().join("inner");
    std::fs::create_dir(&inner).unwrap();
    let manifest = "---\nschema-version: 1\ntitle: Test\nlanguage: ru\nstatus: drafting\n---\n";
    std::fs::write(dir.path().join("project.md"), manifest).unwrap();
    std::fs::write(inner.join("project.md"), manifest).unwrap();
    std::fs::write(dir.path().join(".hieronymus.json"),
        r#"{"series_slug":"outer","cws":{"binding_version":1,"project_contract_version":1,"directions":{}}}"#).unwrap();
    let project = hieronymus::cws_project::discover(&inner).unwrap().unwrap();
    assert!(hieronymus::cws_binding::select_binding(&project, None).unwrap().is_none());
}
```

- [ ] Run `cargo test -p hieronymus --test cws_project --locked`; expect unresolved new modules.
- [ ] Implement discovery using regular, non-linked `project.md` and nearest-boundary traversal. Parse only frontmatter through existing `serde_yaml_ng`; accept the CWS scalar/list subset and reject duplicate keys, nested structures where not supported, malformed metadata and unsupported schema. Do not deserialize manuscript body as YAML. Check symlinks, parent traversal and nested projects before classifying a requested path. Do not walk `.creative-writing/` or opaque directories.
- [ ] Implement `select_binding` for the nearest project's own `.hieronymus.json`. For milestone A reject translation selection as unsupported. Empty series IDs and malformed `cws` fail; unbound is distinct from invalid.
- [ ] Make legacy `discover_project_context` stop at an encountered CWS project boundary. If the marker has a `cws` object, return no legacy context and direct callers to project-context rather than returning default `ja/en`. Outside CWS preserve legacy behavior. Add regression tests for both branches.
- [ ] Run new tests and `cargo test -p hieronymus agent_context --locked`. Commit `feat: recognize CWS projects without CWS runtime`.

## Task 3 — Expose project inspection through the installed CLI (H)

**Files:**
- Create: `crates/hiero/src/project_context.rs`
- Modify: `crates/hiero/src/lib.rs`
- Modify: `crates/hiero/src/main.rs`
- Modify: `crates/hiero/src/agent_hook.rs`
- Create: `crates/hiero/tests/cws_project_context.rs`
- Modify: `docs/agent-workflows.md`

**Interfaces:** `pub fn inspect(cwd: &Path, direction: Option<&str>) -> serde_json::Value` projects task-2 results into the inspection envelope; filesystem errors appear as `status:"invalid"` with safe diagnostic codes. `pub fn exit_code(report: &Value) -> u8` implements the documented status mapping. Neither function loads daemon config. Add a main branch before service-dependent execution; reject `--start-daemon` for this command.

- [ ] Add a CLI test using `env!("CARGO_BIN_EXE_hiero")` with a temporary v1 project, empty PATH and nonexistent `--data-root`. Assert `unbound`, the correct language, no manuscript body or agreement text in stdout, and no created data root. Add cases for missing project, invalid JSON `--args`, selected unknown direction and `--start-daemon`.
- [ ] Run `cargo test -p hiero --test cws_project_context --locked`; expect unknown command failure.
- [ ] Implement command dispatch and exact JSON/human output, using `--args` only for `{ "direction_id": string|null }`; reject unknown keys. When a legacy hook encounters CWS, make its message direct the agent to this command and project instructions without embedding a guessed binding.
- [ ] Add documentation example and verify the command does not bootstrap or install either product. Run focused tests. Commit `feat: expose read-only CWS project context`.

## Task 4 — Teach generated Hieronymus skills project agreements (H)

**Files:**
- Create: `crates/hiero/resources/cws-project.md`
- Modify: `crates/hiero/src/agent_plugins.rs`
- Create: `crates/hiero/tests/cws_plugin_workflow.rs`
- Modify: `docs/agent-workflows.md`
- Modify: `docs/translation-workspace-integration.md`

**Interfaces:** Keep all eight existing skill names. Each generated bootstrap skill carries `resources/cws-project.md` beside its own `SKILL.md`; render from `include_str!("../resources/cws-project.md")`. Other skill bodies refer to bootstrap's project-context workflow by skill name, avoiding broken cross-skill filesystem links.

- [ ] Test `hiero::agent_plugins::render(&config)` for all existing targets: each bootstrap resource exists, has the same bytes, and is linked locally. Assert the obsolete unconditional boundary text is absent. These structural checks do not establish model compliance.
- [ ] Run `cargo test -p hiero --test cws_plugin_workflow --locked`; expect missing resource.
- [ ] Add this core instruction to the resource, with task-3 command and binding examples:

```markdown
Read the project's AGENTS.md and current user instructions before choosing memory.
Interpret trust conditions as free text, including local exceptions. Do not create
a mode flag, numeric ranking, or stored policy summary. With no special instruction,
project files are primary and Hieronymus is additional memory.

A rule's active status inside Hieronymus does not overrule the project agreement.
Preserve its actual status and provenance when reporting a disagreement. Applying
the agreement does not invalidate that rule inside Hieronymus. Internal writes
still use the supported evidence and trusted-ingress routes.

The current leading skill keeps control. Do not recursively launch the other
orchestrator. No installed CWS CLI is needed for reading a supported project;
protected lifecycle writes require its supported domain operations.
```

- [ ] Replace `BOUNDARY_TEXT` with the conditional project-agreement wording; preserve no-fabricated-authority requirements. Update bootstrap, recall, learn, remember, translate, review and orchestrate at their actual decision points, not only a final disclaimer. Avoid translating or importing secrets automatically.
- [ ] Replace stale public workflow guidance that treats `source_credibility="user_rule"` as sufficient authority with a link to actual ingress and the new agreement distinction. Do not rewrite historical compatibility fixtures.
- [ ] Run new tests and `cargo test -p hiero --test autonomous_plugin_workflow --locked`. Commit `feat: honor project memory agreements in Hieronymus skills`.

## Task 5 — Add optional CWS integration and delivery recipes (CWS)

**Files:**
- Create: `plugins/creative-writing-skills/skills/hieronymus-integration/SKILL.md`
- Create: `plugins/creative-writing-skills/skills/hieronymus-integration/resources/workflow.md`
- Create: `plugins/creative-writing-skills/skills/hieronymus-integration/resources/delivery.md`
- Modify: `plugins/creative-writing-skills/skills/creative-writing-muse/SKILL.md`
- Modify: `plugins/creative-writing-skills/skills/story-memory/SKILL.md`
- Modify: `plugins/creative-writing-skills/skills/project-setup/SKILL.md`
- Modify: `plugins/creative-writing-skills/skills/project-doctor/SKILL.md`
- Modify: `config/distribution.json`, `README.md`, `AGENTS.md`
- Create: `tests/test_hieronymus_integration.py`
- Create: `tests/fixtures/hieronymus-workflows.json`

**Interfaces:** Skill name `hieronymus-integration`, conditionally referenced as `$hieronymus-integration` in canonical Codex text. No MCP dependency is added to the CWS manifest. No new memory database or executable transport is bundled with CWS. Public Hieronymus tools are discovered in the current host; task-3 CLI is an optional deterministic aid when accessible.

- [ ] Add inventory and local-resource tests. Assert manifest has no required Hieronymus server and vendor snapshot inventory is unchanged. Add workflow fixtures with `id`, `agreement`, `user_message`, `available_tools`, `observed_results`, `expected_actions`, `forbidden_actions` for all task-9 cases.
- [ ] Run `python3 -m unittest discover -s tests -p test_hieronymus_integration.py -v`; expect missing skill and inventory entry.
- [ ] Write frontmatter:

```yaml
---
name: hieronymus-integration
description: >
  Apply the project's free-text memory agreement when literary work uses
  Hieronymus alongside or instead of file memory. Load when the user requests
  Hieronymus or the project agreement or binding refers to it; remain optional
  when its tools are unavailable.
---
```

- [ ] Write workflow with selective discovery, instruction rereading, binding validation, current-source references, preserving original free-text conditions, local conflict clarification and no forced mirror. A service mentioned in the agreement but unavailable must still trigger the relevant fallback discussion; do not make tool availability the only activation condition.
- [ ] Write delivery recipes for `hieronymus_recall`, `hieronymus_rag_search`, `hieronymus_short_term_add`/batch, evidence capture and decision tools by their advertised schemas. Use actual returned IDs/revisions. Distinguish advisory observation from activated rule and authentic correction; never put an instruction quote into a fake host event.
- [ ] Define the retry procedure precisely: retain actual successful response IDs; if a call times out, inspect via available public read tools. If a unique matching record cannot be established and the operation has no supported idempotency key, do not resend blindly. Record the delivery as unresolved in the task's existing work artifact only when continuation needs it. A durable note may hold operation UUID, destination, returned IDs and outcome; it must not copy the memory corpus or trust policy. Do not fabricate `idempotency_key` parameters on tools that lack them.
- [ ] Wire muse, story-memory and setup; doctor treats absent optional Hieronymus as ordinary capability absence, not broken project state. Update counts relative to installed inventory and regenerate/check distributions. Run focused tests and `python3 scripts/validate_distribution.py`. Commit `feat: add optional Hieronymus memory integration`.

## Task 6 — Add translation mapping and enforce direction context (H, after translation prerequisite)

**Files:**
- Modify: `crates/hieronymus/src/cws_project.rs`, `crates/hieronymus/src/cws_binding.rs`
- Modify: `crates/hieronymus/src/workspace.rs`
- Modify: `crates/hiero/src/application/mod.rs`
- Modify: `crates/hiero/src/application/series_sessions.rs`
- Modify: `crates/hiero/src/application/memory.rs`, `crates/hiero/src/application/terms.rs`
- Modify: `compatibility/rust/authority-context-v1.json`
- Modify: `crates/hiero/src/daemon/registry.rs` only if the existing extension mechanism needs additional tool coverage
- Modify: `crates/hiero/resources/cws-project.md`
- Create: `crates/hiero/tests/cws_direction_context.rs`
- Modify: `crates/hieronymus/tests/cws_project.rs`
- Modify: H and CWS copies of `cws-project-v1.json` after schema-v2 producer exists

**Interfaces:** Carry direction identity in the existing applicability predicates as `cws:direction:<direction-id>`. Carry source edition when a claim is edition-specific as `cws:edition:<edition-id>`; a direction-level rendering does not automatically require one edition. Claims about the common work have neither predicate unless the evidence limits them. Preserve volume/chapter/scene and knowledge gates separately.

The current `TranslationContext.story_scopes` and `ApplicabilityV1.scope_predicates` can carry these identities, but the inspected `StoryReadArgs` does not expose them and the API's language helper rejects overrides against registry defaults. Fix these concrete gaps; do not infer that ordinary relevance tags already isolate directions.

- [ ] Before implementation, verify the schema-v2 project/source/direction tests from the translation prerequisite pass. Add schema-v2 fixtures from its actual `contract.py` and `catalog.py`; no separately invented metadata format.
- [ ] Add public-path regression cases creating two directions with the same target language and two target languages in one series. Use existing real-application fixture setup from `tests/common/authority.rs` with distinct source evidence and rules. For each direction assert contract, validation, recall current lane, RAG current lane and session round-trip never apply the other direction's claims. Research/non_current results, if present, remain explicitly outside current applicability.
- [ ] Run `cargo test -p hiero --test cws_direction_context --locked`; expect ignored scopes or language mismatch before changes.
- [ ] Add `story_scopes: Option<Vec<String>>` to `StoryReadArgs` and advertised schemas for session start and scoped reads. Its apply method appends explicit predicates while preserving context volume/chapter seeds:

```rust
if let Some(scopes) = &self.story_scopes {
    for scope in scopes {
        if !context.story_scopes.contains(scope) {
            context.story_scopes.push(scope.clone());
        }
    }
}
```

Validate strings before this step; conflicting duplicate `cws:direction:` selections are rejected, not merged. Ensure stored sessions reload predicates and all sessionless read paths apply them. Agent capture supplies the same predicates in each typed claim. Do not replace a source's historic scope to force a match.
- [ ] Change `translation_context` to treat registry languages as defaults only when arguments are absent. Explicit nonempty languages are normalized and accepted; source/target applicability checks continue to enforce rule language matching. Reject empty explicit language values. Add regression tests that omitted languages still use old defaults and that a ru rule is not applied to en.
- [ ] Extend inspection to schema v2 and explicit direction selection. Read edition languages and per-volume source overrides from actual manifests; infer a direction from a selected path only when unique. Check declared edition coverage before producing ready translation context. Preserve book versus series layouts, reference editions and source hashes in task context; never infer alignment from chapter numbering.
- [ ] Run focused tests, update pinned fixture copies and skill examples, and commit `feat: preserve translation direction in Hieronymus context`.

## Task 7 — Track external memory without a mandatory Markdown mirror (CWS, after translation prerequisite)

**Files:**
- Create: `plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/translation/external_memory.py`
- Modify: `plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/translation/context.py`
- Modify: `plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/translation/drafts.py`
- Modify: `plugins/creative-writing-skills/skills/project-maintenance/resources/cli/cwcli/translation/commands.py`
- Modify: `plugins/creative-writing-skills/skills/project-maintenance/resources/command-reference.md`
- Create: `tests/cw_cli/test_translation_external_memory.py`
- Modify: `docs/superpowers/plans/2026-09-10-literary-translation.md` to point at this amendment, without rewriting historical completion state

**Interfaces:** External references are operation inputs, not a persisted trust policy. Define:

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class ExternalMemoryRef:
    provider: str
    namespace: str
    record_kind: str
    record_id: str
    revision: str

def assess_external_memory(
    captured: tuple[ExternalMemoryRef, ...],
    observed: tuple[ExternalMemoryRef, ...] | None,
) -> str:
    """Return current, needs-review, or unknown; never access a service."""
```

Namespace identifies the observed service identity plus series, so numeric IDs cannot collide across services. Use the actual `instance_id` exposed by Hieronymus service status together with the actual series slug; a daemon restart may conservatively require renewed verification. Do not invent a persistent database UUID that the service does not expose, or identify a database only by its pathname. If the host cannot obtain service identity through available public status/CLI surfaces, freshness is unknown rather than matched by bare record ID. Require caller-supplied nonempty strings from observed public results; no source text in this type. Record individual references and a conservative series authority revision reference when available, because a newly applicable rule may not change old record revisions. Lack of a public revision for an advisory item is unknown freshness, not a manufactured digest of backend state.

- [ ] Add executable tests:

```python
from cwcli.translation.external_memory import ExternalMemoryRef, assess_external_memory

ref = ExternalMemoryRef("hieronymus", "library-a/series-a", "authority", "series-a", "10")
new = ExternalMemoryRef("hieronymus", "library-a/series-a", "authority", "series-a", "11")
self.assertEqual(assess_external_memory((ref,), None), "unknown")
self.assertEqual(assess_external_memory((ref,), (ref,)), "current")
self.assertEqual(assess_external_memory((ref,), (new,)), "needs-review")
self.assertEqual(assess_external_memory((), None), "current")
```

Also test invalid/empty fields, duplicate logical IDs with conflicting revisions, missing observed references, changed authority revision and a different namespace. A changed/missing known reference is needs-review; an unavailable observation is unknown.
- [ ] Run `python3 -m unittest tests.cw_cli.test_translation_external_memory -v`; expect missing module.
- [ ] Implement comparison by `(provider,namespace,record_kind,record_id)` and exact revision, validate duplicates before comparison. Extend packet JSON with optional `external-memory-refs` and operation-local `excluded-file-memory` paths. The latter is a selection made for this task according to the agreement, not a project mode. Validate excluded paths as actual memory paths within the direction; never exclude source, strategy, manifest or accepted-base guards. Empty exclusions preserve prior behavior.
- [ ] For selected external-only memory, do not require file records or an entire file-memory catalog digest for that excluded scope. Store immutable context actually used and external references in the existing transaction packet. This task snapshot is not a live Markdown mirror. Unselected file-memory changes must not invalidate a draft solely because those files exist.
- [ ] Extend context/draft command input JSON with the new fields. At acceptance allow `external-memory-observed` references plus a task-specific note for an expressly permitted unresolved fallback; neither carries a persistent trust flag. The CLI compares references but cannot authenticate an agent's report or evaluate the free-text agreement. The skill must obtain fresh public observations and apply the agreement. Do not present this bookkeeping as an atomic remote check or a trusted correction receipt.
- [ ] Default unresolved or changed external dependencies to needs-review/unknown without modifying accepted text. A user-authorized acceptance under unavailable memory records that limitation and remains unknown freshness, even though text acceptance succeeds. No ordinary boolean may relabel unknown as current. Existing file-only packets and journal recovery retain their behavior.
- [ ] Run external-memory tests plus existing translation packet/draft/recovery tests. Regenerate/check distributions. Commit `feat: track external translation memory dependencies`.

## Task 8 — Reconcile translation skills and selective transfer (CWS and H)

**Files, CWS:**
- Modify: `plugins/creative-writing-skills/skills/literary-translation/SKILL.md`
- Modify: `plugins/creative-writing-skills/skills/translation-memory/SKILL.md`
- Modify: `plugins/creative-writing-skills/skills/translation-review/SKILL.md`
- Modify: `plugins/creative-writing-skills/skills/hieronymus-integration/resources/workflow.md`
- Modify: `plugins/creative-writing-skills/skills/hieronymus-integration/resources/delivery.md`
- Modify: `tests/fixtures/hieronymus-workflows.json`, `tests/test_hieronymus_integration.py`
- Modify: `docs/superpowers/specs/2026-09-10-literary-translation-design.md` with a short link to the approved storage amendment

**Files, H:**
- Modify: `crates/hiero/resources/cws-project.md`
- Modify: `docs/agent-workflows.md`

**Interfaces:** Both skill sets use the same binding and task-7 reference semantics. Transfer is an explicitly scoped task through public reads/writes, not a new migration daemon. The old translation skill files must exist from the prerequisite; do not create empty substitutes.

- [ ] Add behavior cases: prefer H for terms but accepted prose for voice; choose H for all memory without retaining Markdown records; reverse the preference mid-task; allow only a local exception; update persistent `AGENTS.md` without deleting unrelated instructions; explicit partial transfer with conflict.
- [ ] Run fixture/resource checks first. Verify expected failures stem from missing routing/amendments, not brittle prose wording.
- [ ] Add the following operational rule to both workflows:

```markdown
Apply a new user instruction in its stated scope immediately. Persist a durable
change in AGENTS.md, preserving independent conditions; do not globalize a local
exception. Changing trust does not prove old records were transferred.

For an authorized transfer, inventory the selected records and their provenance,
write through supported operations, retain returned IDs, then reconcile counts,
scopes, dispositions and unresolved conflicts. Report partial completion. Do not
delete originals or create an ongoing mirror unless that work was requested.
```

- [ ] Connect task-7 external observations to preparation and acceptance; preserve unknown freshness and source revisions. Include direction predicates on each memory call and claim. If the service cannot accept a requested authoritative write through supported routes, report the exact pending result rather than claim full replacement succeeded.
- [ ] Update docs and actual inventory totals, regenerate CWS. Run relevant tests in each repository and commit separately: `feat: integrate translation workflows with project memory agreements`.

## Task 9 — Verify independent distributions and real workflow behavior

**Files:**
- Create CWS: `docs/hieronymus-integration-acceptance.md`
- Extend CWS: `tests/test_external_project_contract.py`, `tests/test_hieronymus_integration.py`
- Extend H: `crates/hiero/tests/cws_project_context.rs`, `crates/hiero/tests/cws_direction_context.rs`

**Interfaces:** Acceptance records contain scenario, installed build/commit, host/version, input agreement and user message, actual tool outcomes, relevant resulting file/record identities and pass/fail. No secret values or unrelated project data. Record milestone A and B separately.

- [ ] Cross-check fixture copies byte-for-byte during coordinated development; normal CI in each repository consumes only its own pinned copy. No absolute dependency on the other checkout in tests or runtime.
- [ ] Run the full CWS checks from its AGENTS.md:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
python3 scripts/validate_distribution.py
python3 scripts/vendor_generic_skills.py --check
python3 scripts/sync_claude_distribution.py --check
python3 scripts/create_skill_zips.py
```

- [ ] Run the full H checks from its AGENTS.md:

```sh
cargo fmt --all -- --check
cargo clippy --all-targets --all-features --locked -- -D warnings
cargo test --all-features --locked
RUSTDOCFLAGS="-D warnings" cargo doc --no-deps --all-features --locked
```

From H `frontend/` run `bun run typecheck`, `bun run test`, `bun run build`; build frontend assets before all-feature Rust checks if the embedded-assets feature requires them. No Python parity gate is added.
- [ ] Exercise disposable installed workflows with the following exact decision cases. Each row is a distinct acceptance run; use synthetic story data and never the user's live memory database.

| Scenario | Required observation |
| --- | --- |
| No H installation | CWS uses files, creates no H config, and does not request installation |
| H without CWS installed | Reads supported project and agreement; does not mutate private lifecycle state |
| No agreement clause | Files primary; H results retain advisory status |
| Free-text mixed agreement | H terminology, accepted-prose voice, file author intent all remain distinct |
| In-session local exception | Changes only the stated task; no global policy flag is written |
| Durable preference change | AGENTS.md updated narrowly; no automatic migration or file deletion |
| H replaces memory | Successful work with no mandatory file-memory records or catalog requirement |
| Service unavailable | Independent work continues; dependent outcome follows actual fallback conditions |
| Partial/uncertain write | Accurate destination outcomes; no blind duplicate call |
| Two ru directions and en direction | No wrong-direction or wrong-language rule in current output |
| Stale source or new H rule | Historical evidence retained, dependent text marked for review |
| Hidden/future/AI-tagged information | No secret in reader-facing output and no proposal promoted to canon |
| Imported accepted Markdown rule | No fabricated trusted user event or receipt |
| Direct H translate versus muse | One leading workflow, no recursive orchestration |

- [ ] Run at least the current Codex and generated Claude distributions for the changed skill behavior when native hosts are available. If a host is unavailable, mark its behavior unverified; structural tests and simulated transcripts are not native acceptance. Do not claim semantic retrieval success from lexical fallback. Use H's documented real-model fixtures for any semantic qualification and record missing inputs honestly.
- [ ] Map all twelve spec criteria to these records. Record any unresolved prerequisite or native-host limitation. Commit only resulting acceptance documentation and test fixes in the respective repository. Full completion requires every applicable criterion and the translation prerequisite, not merely green text-presence tests.

## Self-review and handoff

- Spec coverage: free-text agreement and independent installation → tasks 4–5; structural contract and binding → tasks 1–3; direction/source context → task 6; replacement without mirror and revision guards → task 7; transfer and changing preferences → task 8; errors, provenance, secrets and independent verification → task 9 and focused tests.
- Technical choice remains separate from trust: binding has IDs only; external references are task inputs; no persisted trust summary or mandatory mode exists.
- Legacy behavior is preserved outside CWS, while old default languages cannot leak into a CWS-selected task.
- The translation prerequisite is explicit. Milestone A is useful and testable, but is not reported as the full approved design.
- This document is a plan. Test snippets describe tests to add; no implementation tests or native acceptance have been run while writing it.

Execution may use fresh subagents per task with reviews, or sequential execution through `superpowers:executing-plans`. At execution time re-read each repository's current AGENTS.md and reconcile concurrent changes before starting its task.

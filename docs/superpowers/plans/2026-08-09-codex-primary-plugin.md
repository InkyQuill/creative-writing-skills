# Codex-Primary Creative Writing Plugin Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Mars/Meridian package with an installable, vanilla Codex repo-marketplace plugin containing 25 creative-writing skills, preserve muse-led specialist delegation with a single-agent fallback, and generate the Claude compatibility distribution deterministically.

**Architecture:** The canonical runtime lives under `plugins/creative-writing-skills/`; `.agents/plugins/marketplace.json` exposes it to Codex. Repository-local Python 3.11 scripts validate the package, import pinned licensed skill snapshots, and derive `cw/` for Claude. Muse owns a machine-readable worker registry and focused Markdown worker prompts; Codex uses them for fresh subagents, while the Claude generator materializes them as Claude agent files.

**Tech Stack:** Markdown skills, JSON manifests/registries, Python 3.11 standard library (`argparse`, `dataclasses`, `hashlib`, `json`, `pathlib`, `re`, `shutil`, `subprocess`, `tempfile`, `unittest`), GitHub Actions, Claude Code CLI validation.

## Global Constraints

- Canonical plugin name: `creative-writing-skills`.
- Initial canonical version: `0.5.9`; after migration, `.codex-plugin/plugin.json` is the only version source.
- Canonical repository: `https://github.com/InkyQuill/creative-writing-skills`.
- Plugin license: `Apache-2.0`; retain inherited upstream attribution and identify InkyQuill as the current fork developer.
- Canonical plugin path: `plugins/creative-writing-skills/`.
- Repo marketplace path: `.agents/plugins/marketplace.json` with source `./plugins/creative-writing-skills`, installation `AVAILABLE`, authentication `ON_INSTALL`, and category `Productivity`.
- Ship exactly these 25 skills:
  `character-sim`, `creative-research`, `creative-writing-craft`,
  `creative-writing-modes`, `creative-writing-muse`, `grill-with-docs`,
  `information-hierarchy`, `intent-modeling`, `kb-management`,
  `knowledge-layers`, `llm-writing`, `md-validation`, `project-setup`,
  `qi-layer`, `reader-sim`, `reflect`, `shared-dao`, `story-memory`,
  `story-planning`, `story-review`, `structured-artifact`, `world-creation`,
  `writing-principles`, `writing-staffing`, and `zoom-out`.
- The ten generic skills are imported from the Apache-2.0-covered `cw/skills/` snapshot in `haowjy/creative-writing-skills` commit `fd7a3ad9cd7697a0645ff6ff4bd5e809cf7673a3`: `grill-with-docs`, `information-hierarchy`, `intent-modeling`, `knowledge-layers`, `llm-writing`, `md-validation`, `qi-layer`, `reflect`, `structured-artifact`, and `zoom-out`.
- Record `haowjy/meridian-base` commit `d3c4b3313d38e18dd7970f1db34af15c25dbf238` as immediate provenance for those ten skills, but do not fetch or refresh from it because it currently has no declared license.
- `world-creation` starts from `/Users/inkyquill/Documents/writing/aria/.agents/skills/world-creation`; credit `mattpocock/skills` `grill-me` at `84fdeffd12f2ee307994d1eb6feb48173b6e0502` and `danjdewhurst/story-skills` `worldbuilding` at `c482d48f4eb9b488f033a77a51f9fae55cc0d75f`, both MIT.
- Do not copy per-skill `agents/openai.yaml`; the current official OpenAI skill structure documents `SKILL.md`, `references/`, `scripts/`, and `assets/`. Move the useful world-creation starter prompt into plugin `interface.defaultPrompt`.
- Canonical skills use only `name` and `description` frontmatter unless an additional field is explicitly accepted by the repository validator and official Codex plugin schema.
- Canonical Codex skill references use `$skill-name`; generated Claude references use `/skill-name`. Conversion is fence-aware and applies only to references that resolve to the exact 25-skill registry.
- Canonical runtime files may not retain `/qi-maintenance` or `@kb-lead`: inline the necessary maintenance guidance and have muse apply `$story-memory` directly.
- Canonical prose and drafts remain read-only during `world-creation`.
- Support both `worldbuilding/` + `characters/` + `chapters/` and `kb/world/` + `kb/characters/` + `story/` project layouts.
- No MCP server, app manifest, or hooks are included.
- Use Python's standard library only; do not add a package manager or runtime dependency for build scripts.
- Preserve the user's uncommitted spec edits. Each task stages only the files it owns.

## Target File Map

| Path | Responsibility |
|---|---|
| `.agents/plugins/marketplace.json` | Codex repo-marketplace catalog entry. |
| `plugins/creative-writing-skills/.codex-plugin/plugin.json` | Canonical plugin identity, version, interface metadata, and skills path. |
| `plugins/creative-writing-skills/skills/*/` | The 25 canonical Codex skills and their local resources. |
| `plugins/creative-writing-skills/skills/creative-writing-muse/resources/workers/registry.json` | Machine-readable worker names, prompt paths, skill sets, access mode, and Claude metadata. |
| `plugins/creative-writing-skills/skills/creative-writing-muse/resources/workers/*.md` | Bounded specialist prompts used by Codex subagents and Claude agent generation. |
| `config/distribution.json` | Exact skill classifications, licensed import source, worker registry location, and Claude distribution paths. |
| `scripts/distribution.py` | Shared paths, JSON/frontmatter parsing, directory comparison, and atomic tree replacement. |
| `scripts/vendor_generic_skills.py` | Apply/check the pinned Apache-licensed generic-skill snapshot without Mars. |
| `scripts/validate_distribution.py` | Validate Codex manifest, marketplace, skills, resources, references, workers, platform leaks, and version consistency. |
| `scripts/sync_claude_distribution.py` | Generate `cw/skills`, `cw/agents`, and Claude metadata from canonical sources. |
| `scripts/create_skill_zips.py` | Build Claude.ai archives from generated `cw/skills`. |
| `scripts/release.py` | Read, bump, propagate, commit, and tag the canonical plugin version. |
| `THIRD_PARTY_NOTICES.md` | Upstream provenance and license summary. |
| `LICENSES/MIT-mattpocock-skills.txt` | Required MIT notice for `grill-me`-derived material. |
| `LICENSES/MIT-story-skills.txt` | Required MIT notice for `worldbuilding`-derived material. |
| `tests/test_distribution.py` | Canonical package and shared helper tests. |
| `tests/test_vendor_generic_skills.py` | Licensed snapshot import/check tests. |
| `tests/test_sync_claude_distribution.py` | Claude transform, agent generation, drift, and failure tests. |
| `tests/test_release.py` | Semantic-version bump and canonical-version propagation tests. |
| `tests/test_world_creation.py` | Layout discovery and prose-write-boundary contract tests. |
| `docs/behavioral-release-checklist.md` | Manual model-backed release scenarios. |

---

### Task 1: Establish the Canonical Codex Package and Shared Test Harness

**Files:**
- Create: `.agents/plugins/marketplace.json`
- Create: `plugins/creative-writing-skills/.codex-plugin/plugin.json`
- Create: `config/distribution.json`
- Create: `scripts/distribution.py`
- Create: `tests/__init__.py`
- Create: `tests/test_distribution.py`
- Modify: `.gitignore`

**Interfaces:**
- Produces: `scripts.distribution.REPO_ROOT: Path`, `PLUGIN_ROOT: Path`, `SKILLS_ROOT: Path`, `CW_ROOT: Path`.
- Produces: `load_json(path: Path) -> dict[str, object]`.
- Produces: `split_frontmatter(text: str) -> tuple[dict[str, object], str]` for the supported scalar and block-scalar skill metadata.
- Produces: `skill_directories(root: Path) -> dict[str, Path]`.
- Produces: `map_outside_fences(text: str, transform: Callable[[str], str]) -> str`.
- Produces: `extract_skill_references(text: str, sigil: str) -> set[str]`; it ignores fenced code, URLs, filesystem paths, and closing markup.
- Produces: `config/distribution.json` keys `canonical_skills`, `authored_skills`, `vendored_skills`, `workers`, `claude`.
- Consumed by: every later validation and generation task.

- [ ] **Step 1: Write the failing manifest and shared-helper tests**

Add these tests to `tests/test_distribution.py`:

```python
import json
import unittest
from pathlib import Path

from scripts.distribution import PLUGIN_ROOT, REPO_ROOT, load_json, split_frontmatter


EXPECTED_SKILLS = {
    "character-sim", "creative-research", "creative-writing-craft",
    "creative-writing-modes", "creative-writing-muse", "grill-with-docs",
    "information-hierarchy", "intent-modeling", "kb-management",
    "knowledge-layers", "llm-writing", "md-validation", "project-setup",
    "qi-layer", "reader-sim", "reflect", "shared-dao", "story-memory",
    "story-planning", "story-review", "structured-artifact", "world-creation",
    "writing-principles", "writing-staffing", "zoom-out",
}


class DistributionScaffoldTests(unittest.TestCase):
    def test_manifest_and_marketplace_use_canonical_identity(self):
        manifest = load_json(PLUGIN_ROOT / ".codex-plugin" / "plugin.json")
        marketplace = load_json(REPO_ROOT / ".agents" / "plugins" / "marketplace.json")
        self.assertEqual(manifest["name"], "creative-writing-skills")
        self.assertEqual(manifest["version"], "0.5.9")
        self.assertEqual(manifest["repository"], "https://github.com/InkyQuill/creative-writing-skills")
        self.assertEqual(manifest["skills"], "./skills/")
        self.assertEqual(marketplace["plugins"][0]["source"]["path"], "./plugins/creative-writing-skills")

    def test_distribution_config_lists_exact_skill_set(self):
        config = load_json(REPO_ROOT / "config" / "distribution.json")
        self.assertEqual(set(config["canonical_skills"]), EXPECTED_SKILLS)
        self.assertEqual(len(config["authored_skills"]), 15)
        self.assertEqual(len(config["vendored_skills"]), 10)

    def test_frontmatter_parser_returns_metadata_and_body(self):
        metadata, body = split_frontmatter("---\nname: demo\ndescription: |\n  First line.\n  Second line.\n---\n\n# Demo\n")
        self.assertEqual(metadata, {"name": "demo", "description": "First line.\nSecond line."})
        self.assertEqual(body, "\n# Demo\n")

    def test_reference_parser_distinguishes_skills_from_code_urls_and_tags(self):
        text = "Use $story-memory, not /story-memory.\n```bash\necho $chapter\n```\nhttps://example.com/story-memory\n</hidden>\n"
        self.assertEqual(extract_skill_references(text, "$"), {"story-memory"})
        self.assertEqual(extract_skill_references(text, "/"), {"story-memory"})
```

- [ ] **Step 2: Run the tests and verify the scaffold is absent**

Run: `python3 -m unittest tests.test_distribution -v`

Expected: FAIL because `scripts.distribution` and the Codex manifests do not exist.

- [ ] **Step 3: Implement the shared module and exact distribution config**

Create `scripts/distribution.py` with no third-party imports. Implement the constants from `Path(__file__).resolve().parent.parent`, strict JSON object loading, a frontmatter parser that accepts `name`, `description`, `disable-model-invocation`, and `argument-hint`, and `skill_directories()` that returns only directories containing `SKILL.md`.

`map_outside_fences()` splits on lines beginning with three or more backticks or tildes and transforms only non-fenced segments. `extract_skill_references()` uses it with `\$([a-z][a-z0-9-]*)` for Codex. For Claude slash references use `(?<![A-Za-z0-9_.</%-])/([a-z][a-z0-9-]*)(?![A-Za-z0-9./-])`; this excludes URLs, nested paths, and closing tags while still detecting standalone `/story-memory`.

Create `config/distribution.json` with this classification:

```json
{
  "canonical_skills": [
    "character-sim", "creative-research", "creative-writing-craft",
    "creative-writing-modes", "creative-writing-muse", "grill-with-docs",
    "information-hierarchy", "intent-modeling", "kb-management",
    "knowledge-layers", "llm-writing", "md-validation", "project-setup",
    "qi-layer", "reader-sim", "reflect", "shared-dao", "story-memory",
    "story-planning", "story-review", "structured-artifact", "world-creation",
    "writing-principles", "writing-staffing", "zoom-out"
  ],
  "authored_skills": [
    "character-sim", "creative-research", "creative-writing-craft",
    "creative-writing-modes", "creative-writing-muse", "kb-management",
    "project-setup", "reader-sim", "shared-dao", "story-memory",
    "story-planning", "story-review", "world-creation",
    "writing-principles", "writing-staffing"
  ],
  "vendored_skills": [
    "grill-with-docs", "information-hierarchy", "intent-modeling",
    "knowledge-layers", "llm-writing", "md-validation", "qi-layer",
    "reflect", "structured-artifact", "zoom-out"
  ],
  "workers": "skills/creative-writing-muse/resources/workers/registry.json",
  "claude": {
    "root": "cw",
    "marketplace": ".claude-plugin/marketplace.json"
  }
}
```

Create the canonical manifest with version `0.5.9`, author name `InkyQuill`, repository/homepage set to the fork, license `Apache-2.0`, `skills: "./skills/"`, and interface fields `displayName`, `shortDescription`, `longDescription`, `developerName`, `category`, `capabilities`, `websiteURL`, and three default prompts. One default prompt must be: `Use $world-creation to reconcile this setting idea with my story files.` Do not add `apps`, `mcpServers`, `hooks`, or asset paths.

Create the marketplace entry with the exact policies from Global Constraints. Add `/.agents/agents/` and `/.agents/skills/` to `.gitignore`, but do not ignore `.agents/plugins/marketplace.json`.

- [ ] **Step 4: Run the focused tests**

Run: `python3 -m unittest tests.test_distribution.DistributionScaffoldTests -v`

Expected: three tests PASS.

- [ ] **Step 5: Validate JSON syntax and inspect the package paths**

Run: `python3 -m json.tool .agents/plugins/marketplace.json >/dev/null && python3 -m json.tool plugins/creative-writing-skills/.codex-plugin/plugin.json >/dev/null && python3 -m json.tool config/distribution.json >/dev/null`

Expected: exit `0` with no output.

- [ ] **Step 6: Commit the package scaffold**

```bash
git add .gitignore .agents/plugins/marketplace.json plugins/creative-writing-skills/.codex-plugin/plugin.json config/distribution.json scripts/distribution.py tests/__init__.py tests/test_distribution.py
git commit -m "feat: scaffold canonical Codex plugin"
```

---

### Task 2: Import the Ten Licensed Generic Skill Snapshots

**Files:**
- Create: `scripts/vendor_generic_skills.py`
- Create: `tests/test_vendor_generic_skills.py`
- Create: `THIRD_PARTY_NOTICES.md`
- Create: `plugins/creative-writing-skills/skills/{grill-with-docs,information-hierarchy,intent-modeling,knowledge-layers,llm-writing,md-validation,qi-layer,reflect,structured-artifact,zoom-out}/**`

**Interfaces:**
- Consumes: `config/distribution.json["vendored_skills"]`.
- Produces: `VendorSource(url: str, commit: str, skills_path: str, license: str)` in `scripts/vendor_generic_skills.py`.
- Produces: `render_from_checkout(checkout: Path, output_root: Path) -> None`.
- Produces: `normalize_codex_references(text: str, canonical_skills: set[str], skill_name: str) -> str`.
- Produces CLI: `python3 scripts/vendor_generic_skills.py --apply [--source-checkout PATH]` and `--check [--source-checkout PATH]`.
- The default source is a temporary clone of `https://github.com/haowjy/creative-writing-skills.git` pinned to `fd7a3ad9cd7697a0645ff6ff4bd5e809cf7673a3`; tests pass `--source-checkout` and never require network.

- [ ] **Step 1: Write failing import, drift, and forbidden-source tests**

Add tests that build a temporary licensed source containing `cw/skills/demo/SKILL.md` and a temporary output root:

```python
class VendorGenericSkillsTests(unittest.TestCase):
    def test_render_copies_complete_skill_directory(self):
        render_from_checkout(self.checkout, self.output)
        self.assertEqual(
            (self.output / "demo" / "SKILL.md").read_text(),
            (self.checkout / "cw" / "skills" / "demo" / "SKILL.md").read_text(),
        )
        self.assertTrue((self.output / "demo" / "resources" / "guide.md").is_file())

    def test_check_reports_changed_vendored_file(self):
        render_from_checkout(self.checkout, self.output)
        (self.output / "demo" / "SKILL.md").write_text("changed\n")
        with self.assertRaisesRegex(VendorDriftError, "demo/SKILL.md"):
            check_checkout(self.checkout, self.output)

    def test_source_is_licensed_snapshot_not_meridian_base(self):
        self.assertEqual(SOURCE.license, "Apache-2.0")
        self.assertEqual(SOURCE.commit, "fd7a3ad9cd7697a0645ff6ff4bd5e809cf7673a3")
        self.assertNotIn("meridian-base", SOURCE.url)

    def test_normalizer_changes_known_skill_refs_but_preserves_shell_and_urls(self):
        source = "Use /story-memory.\n```bash\necho $chapter\n```\nhttps://example.com/story-memory\n"
        rendered = normalize_codex_references(source, {"story-memory"}, "demo")
        self.assertIn("Use $story-memory.", rendered)
        self.assertIn("echo $chapter", rendered)
        self.assertIn("https://example.com/story-memory", rendered)

    def test_normalizer_rejects_unbundled_skill_reference(self):
        with self.assertRaisesRegex(ValueError, "qi-layer: unbundled skill reference /qi-maintenance"):
            normalize_codex_references("Load /qi-maintenance.\n", {"qi-layer"}, "qi-layer")
```

- [ ] **Step 2: Run the tests and verify the vendor module is absent**

Run: `python3 -m unittest tests.test_vendor_generic_skills -v`

Expected: FAIL because `scripts.vendor_generic_skills` does not exist.

- [ ] **Step 3: Implement pinned snapshot apply/check behavior**

Implement `VendorSource` as a frozen dataclass. Clone with argument arrays, never a shell string:

```python
subprocess.run(
    ["git", "clone", "--filter=blob:none", "--no-checkout", SOURCE.url, str(checkout)],
    check=True,
)
subprocess.run(["git", "-C", str(checkout), "checkout", SOURCE.commit, "--", SOURCE.skills_path], check=True)
```

`render_from_checkout()` copies only names in `config/distribution.json["vendored_skills"]`, requires `SKILL.md`, preserves resources, and writes through a temporary sibling directory before replacing each destination. For Markdown files, `normalize_codex_references()` converts only slash references whose names are in the canonical registry. It rejects every standalone slash reference that looks like a skill but is not bundled.

Add one explicit licensed-snapshot adaptation for `qi-layer/SKILL.md`: replace the `/qi-maintenance` ownership sentence with `When colocated knowledge changes, keep its AGENTS.md and .context documentation synchronized with the source in the same change.` Apply this before reference validation. `--check` renders into a temporary directory and prints a relative-file diff summary before exiting `1` on drift. It must not access `meridian-base`.

- [ ] **Step 4: Apply the pinned snapshot**

Run: `python3 scripts/vendor_generic_skills.py --apply`

Expected: ten `synced <skill>` lines and ten complete skill directories under the canonical plugin.

- [ ] **Step 5: Add provenance notices**

Create `THIRD_PARTY_NOTICES.md` stating that these ten files are imported from the Apache-2.0 distribution at `haowjy/creative-writing-skills@fd7a3ad…`, that `haowjy/meridian-base@d3c4b331…` is their immediate development provenance, and that refreshes from the latter are prohibited until it declares a compatible license. Do not describe the ten skills as original InkyQuill work.

- [ ] **Step 6: Run tests and offline drift check**

Run: `python3 -m unittest tests.test_vendor_generic_skills -v`

Expected: all tests PASS.

Run: `python3 scripts/vendor_generic_skills.py --check`

Expected: the script creates a temporary pinned checkout, reports `10 vendored skills in sync`, and exits `0`.

- [ ] **Step 7: Commit the generic skills and provenance**

```bash
git add scripts/vendor_generic_skills.py tests/test_vendor_generic_skills.py THIRD_PARTY_NOTICES.md plugins/creative-writing-skills/skills
git commit -m "feat: vendor licensed generic skill snapshots"
```

---

### Task 3: Promote the Fourteen Existing Creative-Writing Skills

**Files:**
- Create: `plugins/creative-writing-skills/skills/{character-sim,creative-research,creative-writing-craft,creative-writing-modes,creative-writing-muse,kb-management,project-setup,reader-sim,shared-dao,story-memory,story-planning,story-review,writing-principles,writing-staffing}/**`
- Modify: `tests/test_distribution.py`

**Interfaces:**
- Consumes: root `skills/` for eleven source skills and `cw/skills/` for `kb-management`, `project-setup`, and `shared-dao`.
- Produces: fourteen canonical skill directories with Codex `name`/`description` frontmatter and no Mars metadata.
- Produces: project-setup behavior that targets `AGENTS.md` in the canonical skill.

- [ ] **Step 1: Add a failing canonical-skill inventory and frontmatter test**

```python
    def test_all_non_world_skills_exist_with_minimal_frontmatter(self):
        config = load_json(REPO_ROOT / "config" / "distribution.json")
        for name in set(config["canonical_skills"]) - {"world-creation"}:
            path = PLUGIN_ROOT / "skills" / name / "SKILL.md"
            self.assertTrue(path.is_file(), name)
            metadata, body = split_frontmatter(path.read_text())
            self.assertEqual(metadata["name"], name)
            self.assertTrue(str(metadata["description"]).strip())
            self.assertNotIn("type", metadata)
            self.assertNotIn("model-invocable", metadata)
            self.assertTrue(body.strip())
```

- [ ] **Step 2: Run the inventory test and verify fourteen directories are missing**

Run: `python3 -m unittest tests.test_distribution.DistributionScaffoldTests.test_all_non_world_skills_exist_with_minimal_frontmatter -v`

Expected: FAIL naming the first absent authored skill.

- [ ] **Step 3: Copy the eleven repository-authored skill trees**

Copy complete directories from root `skills/` into the canonical plugin with:

```bash
cp -R skills/character-sim plugins/creative-writing-skills/skills/character-sim
cp -R skills/creative-research plugins/creative-writing-skills/skills/creative-research
cp -R skills/creative-writing-craft plugins/creative-writing-skills/skills/creative-writing-craft
cp -R skills/creative-writing-modes plugins/creative-writing-skills/skills/creative-writing-modes
cp -R skills/creative-writing-muse plugins/creative-writing-skills/skills/creative-writing-muse
cp -R skills/reader-sim plugins/creative-writing-skills/skills/reader-sim
cp -R skills/story-memory plugins/creative-writing-skills/skills/story-memory
cp -R skills/story-planning plugins/creative-writing-skills/skills/story-planning
cp -R skills/story-review plugins/creative-writing-skills/skills/story-review
cp -R skills/writing-principles plugins/creative-writing-skills/skills/writing-principles
cp -R skills/writing-staffing plugins/creative-writing-skills/skills/writing-staffing
```

Then edit canonical copies only. Strip Mars-only `type` and `model-invocable` keys, retaining their behavior in Codex-compatible descriptions. Replace Meridian commands and environment variables with capability-based instructions. Convert every real `/skill-name` reference to `$skill-name`; do not change URLs, filesystem paths, HTML/XML closing tags, or fenced code.

- [ ] **Step 4: Promote the three Claude-only creative skills**

Run:

```bash
cp -R cw/skills/kb-management plugins/creative-writing-skills/skills/kb-management
cp -R cw/skills/project-setup plugins/creative-writing-skills/skills/project-setup
cp -R cw/skills/shared-dao plugins/creative-writing-skills/skills/shared-dao
```

Port `project-setup` to create/update `AGENTS.md`, not `CLAUDE.md`; preserve existing project files and require confirmation before creating the workspace. Port any Claude `@agent` calls to capability-based muse delegation or direct skill behavior. In `writing-staffing`, replace `@kb-lead` with an instruction for muse to apply `$story-memory` directly after decisions settle.

- [ ] **Step 5: Run frontmatter and forbidden-vocabulary tests**

Add this assertion to `tests/test_distribution.py`:

```python
    def test_canonical_runtime_has_no_mars_or_meridian_scaffolding(self):
        forbidden = re.compile(r"\b(?:Mars|Meridian)\b|meridian\s+(?:spawn|mars|context|work)|MERIDIAN_[A-Z_]+")
        for path in (PLUGIN_ROOT / "skills").rglob("*"):
            if path.is_file() and path.suffix in {".md", ".json", ".yaml"}:
                self.assertIsNone(forbidden.search(path.read_text()), str(path))

    def test_canonical_skill_references_use_dollar_and_resolve(self):
        canonical = set(load_json(REPO_ROOT / "config" / "distribution.json")["canonical_skills"])
        for path in (PLUGIN_ROOT / "skills").rglob("*.md"):
            text = path.read_text()
            self.assertEqual(extract_skill_references(text, "/"), set(), str(path))
            self.assertLessEqual(extract_skill_references(text, "$"), canonical, str(path))

    def test_canonical_runtime_has_no_unbundled_agent_reference(self):
        for path in (PLUGIN_ROOT / "skills").rglob("*.md"):
            self.assertNotIn("@kb-lead", map_outside_fences(path.read_text(), lambda value: value), str(path))
```

Run: `python3 -m unittest tests.test_distribution -v`

Expected: the inventory and vocabulary tests PASS; the 25-skill count still fails only because `world-creation` is not present.

- [ ] **Step 6: Commit the promoted creative skills**

```bash
git add plugins/creative-writing-skills/skills tests/test_distribution.py
git commit -m "feat: promote creative writing skills to Codex"
```

---

### Task 4: Integrate World Creation with Dual Project Layouts

**Files:**
- Create: `plugins/creative-writing-skills/skills/world-creation/SKILL.md`
- Create: `plugins/creative-writing-skills/skills/world-creation/references/world-file-format.md`
- Create: `LICENSES/MIT-mattpocock-skills.txt`
- Create: `LICENSES/MIT-story-skills.txt`
- Modify: `THIRD_PARTY_NOTICES.md`
- Create: `tests/test_world_creation.py`

**Interfaces:**
- Produces: direct and automatic `$world-creation` workflow.
- Produces: explicit aliases `worldbuilding/ ↔ kb/world/`, `characters/ ↔ kb/characters/`, `chapters/ ↔ story/`, `drafts/ ↔ work/drafts/`, `plot/ ↔ work/outline/`.
- Produces: immutable prose boundary covering canonical and draft prose in either layout.

- [ ] **Step 1: Write failing content-contract tests**

```python
class WorldCreationContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skill = (SKILLS_ROOT / "world-creation" / "SKILL.md").read_text()

    def test_both_project_layouts_are_named(self):
        for path in ("worldbuilding/", "kb/world/", "characters/", "kb/characters/", "chapters/", "story/", "drafts/", "work/drafts/"):
            self.assertIn(f"`{path}`", self.skill)

    def test_prose_is_read_only_and_canonization_requires_confirmation(self):
        self.assertRegex(self.skill, r"(?i)chapters.*read-only")
        self.assertRegex(self.skill, r"(?i)story.*read-only")
        self.assertRegex(self.skill, r"(?i)draft.*read-only")
        self.assertRegex(self.skill, r"(?i)confirmation.*canon")

    def test_unsupported_per_skill_interface_file_is_absent(self):
        self.assertFalse((SKILLS_ROOT / "world-creation" / "agents" / "openai.yaml").exists())
```

- [ ] **Step 2: Run the tests and verify the skill is absent**

Run: `python3 -m unittest tests.test_world_creation -v`

Expected: ERROR opening the missing canonical `SKILL.md`.

- [ ] **Step 3: Import and port the authored skill**

Copy the local `SKILL.md` as the starting point. Move `WORLD-FILE-FORMAT.md` to `references/world-file-format.md` and update its link. Do not copy `agents/openai.yaml`. Preserve one-question-at-a-time interrogation, recommendations, confirmation before canonization, consequence tracing, index maintenance, and minimal non-story edits.

Revise project discovery so neither layout is called legacy. Detect existing indexes and directories first, select the locally established layout, and ask only if both layouts are absent or equally populated. Name every prose and draft directory as read-only.

- [ ] **Step 4: Add exact third-party notices**

Copy the full MIT license text and copyright notices from:

- `mattpocock/skills@84fdeffd…/LICENSE` to `LICENSES/MIT-mattpocock-skills.txt`;
- `danjdewhurst/story-skills@c482d48f…/LICENSE` to `LICENSES/MIT-story-skills.txt`.

Add a `world-creation` section to `THIRD_PARTY_NOTICES.md` naming the local authored derivative, Matt Pocock's `skills/productivity/grill-me`, the reusable grilling method it represents, and Daniel Dewhurst's `skills/worldbuilding`. State that the resulting integration is modified for this plugin.

- [ ] **Step 5: Run world-creation and full inventory tests**

Run: `python3 -m unittest tests.test_world_creation tests.test_distribution -v`

Expected: all tests PASS and exactly 25 canonical skill directories are present.

- [ ] **Step 6: Commit world creation and licenses**

```bash
git add plugins/creative-writing-skills/skills/world-creation tests/test_world_creation.py THIRD_PARTY_NOTICES.md LICENSES
git commit -m "feat: add dual-layout world creation skill"
```

---

### Task 5: Port Muse and Specialist Roles to Codex Subagent Orchestration

**Files:**
- Modify: `plugins/creative-writing-skills/skills/creative-writing-muse/SKILL.md`
- Create: `plugins/creative-writing-skills/skills/creative-writing-muse/resources/workers/registry.json`
- Create: `plugins/creative-writing-skills/skills/creative-writing-muse/resources/workers/{brainstormer,character-sim,continuity-checker,critic,editor,outliner,reader-sim,style-creator,web-researcher,writer}.md`
- Modify: `tests/test_distribution.py`

**Interfaces:**
- Produces registry entries with fields `name`, `description`, `prompt`, `skills`, `access`, and `claude`.
- `access` enum: `read-only` or `workspace-write`.
- `claude` object: `model` (`inherit`) and `background` (`true` or `false`).
- Muse prompt contract: task goal, author intent, reader effect, failure boundary, input paths, output path or response shape, and facts that must remain unresolved.

- [ ] **Step 1: Write failing worker registry tests**

```python
EXPECTED_WORKERS = {
    "brainstormer", "character-sim", "continuity-checker", "critic", "editor",
    "outliner", "reader-sim", "style-creator", "web-researcher", "writer",
}

    def test_worker_registry_is_complete_and_resolvable(self):
        registry_path = PLUGIN_ROOT / "skills" / "creative-writing-muse" / "resources" / "workers" / "registry.json"
        registry = load_json(registry_path)
        self.assertEqual({item["name"] for item in registry["workers"]}, EXPECTED_WORKERS)
        canonical = set(load_json(REPO_ROOT / "config" / "distribution.json")["canonical_skills"])
        for item in registry["workers"]:
            self.assertIn(item["access"], {"read-only", "workspace-write"})
            self.assertTrue((registry_path.parent / item["prompt"]).is_file())
            self.assertLessEqual(set(item["skills"]), canonical)

    def test_review_workers_are_read_only(self):
        registry = load_json(PLUGIN_ROOT / "skills" / "creative-writing-muse" / "resources" / "workers" / "registry.json")
        access = {item["name"]: item["access"] for item in registry["workers"]}
        for name in {"character-sim", "continuity-checker", "critic", "editor", "reader-sim"}:
            self.assertEqual(access[name], "read-only")
```

- [ ] **Step 2: Run the tests and verify the registry is absent**

Run: `python3 -m unittest tests.test_distribution.DistributionScaffoldTests.test_worker_registry_is_complete_and_resolvable -v`

Expected: ERROR reading `registry.json`.

- [ ] **Step 3: Create the exact worker registry**

Use these skill mappings:

| Worker | Access | Skills |
|---|---|---|
| brainstormer | workspace-write | story-planning, story-memory, intent-modeling, llm-writing |
| character-sim | read-only | character-sim, writing-principles, llm-writing, story-memory |
| continuity-checker | read-only | story-review, md-validation, shared-dao, story-memory |
| critic | read-only | story-review, writing-principles, llm-writing, story-memory |
| editor | read-only | story-review, writing-principles, creative-writing-craft, llm-writing, story-memory |
| outliner | workspace-write | story-planning, story-memory, md-validation |
| reader-sim | read-only | reader-sim, writing-principles, llm-writing |
| style-creator | workspace-write | creative-writing-craft, writing-principles, llm-writing, story-memory |
| web-researcher | workspace-write | creative-research |
| writer | workspace-write | creative-writing-modes, creative-writing-craft, writing-principles, story-memory, llm-writing |

Set every Claude model to `inherit`; set `background: true` only for `web-researcher`.

- [ ] **Step 4: Port each former agent body into a bounded worker prompt**

Use `agents/<name>.md` as source material, remove model aliases, Mars tool permissions, sandbox declarations, and identity boilerplate. Every worker prompt must open with its function, declare required inputs and return shape, and repeat its access boundary. Workspace-write workers must say they own only caller-assigned paths and must not revert concurrent changes. Read-only workers must say they return findings to muse and never patch files.

- [ ] **Step 5: Rewrite muse for Codex-first routing and fallback**

The muse skill must:

1. auto-trigger for broad story work and remain explicitly invocable;
2. capture intent before dispatch;
3. read the registry and selected worker prompt before spawning;
4. dispatch independent roles in parallel and dependent draft/review stages sequentially;
5. read every result and own the verdict;
6. avoid forwarding raw reports;
7. use the same worker prompt as a current-context stance if subagents are unavailable;
8. disclose fallback only when lost independence matters;
9. route setting work to `$world-creation`;
10. update story memory only after decisions settle.

- [ ] **Step 6: Run worker and canonical validation tests**

Run: `python3 -m unittest tests.test_distribution -v`

Expected: all tests PASS.

- [ ] **Step 7: Commit Codex orchestration**

```bash
git add plugins/creative-writing-skills/skills/creative-writing-muse tests/test_distribution.py
git commit -m "feat: port muse orchestration to Codex subagents"
```

---

### Task 6: Build the Repository-Local Distribution Validator

**Files:**
- Create: `scripts/validate_distribution.py`
- Modify: `tests/test_distribution.py`

**Interfaces:**
- Produces: `validate(repo_root: Path) -> list[str]`; empty list means valid.
- Produces CLI: `python3 scripts/validate_distribution.py`, exit `0` on success and `1` with one bullet per problem.
- Consumes: canonical manifest, marketplace, distribution config, skills, worker registry, `cw/` when present.

- [ ] **Step 1: Write failing validator fixture tests**

Use `tempfile.TemporaryDirectory()` and copy the minimal package fixture. Cover these exact failures:

```python
    def test_validator_rejects_dangling_skill_reference(self):
        skill = self.skills / "demo" / "SKILL.md"
        skill.write_text("---\nname: demo\ndescription: Demo.\n---\nUse $missing-skill.\n")
        self.assertIn("demo: dangling skill reference $missing-skill", validate(self.root))

    def test_validator_rejects_missing_relative_resource(self):
        skill = self.skills / "demo" / "SKILL.md"
        skill.write_text("---\nname: demo\ndescription: Demo.\n---\nRead [guide](references/guide.md).\n")
        self.assertIn("demo: missing relative resource references/guide.md", validate(self.root))

    def test_validator_rejects_manifest_version_mismatch(self):
        self.claude_manifest["version"] = "0.0.0"
        self.write_claude_manifest()
        self.assertIn("cw plugin version 0.0.0 != canonical version 0.5.9", validate(self.root))

    def test_validator_rejects_claude_style_reference_in_codex(self):
        skill = self.skills / "demo" / "SKILL.md"
        skill.write_text("---\nname: demo\ndescription: Demo.\n---\nUse /story-memory.\n")
        self.assertIn("demo: Claude-style reference /story-memory in canonical Codex skill", validate(self.root))

    def test_validator_ignores_shell_variables_and_urls(self):
        skill = self.skills / "demo" / "SKILL.md"
        skill.write_text("---\nname: demo\ndescription: Demo.\n---\n```bash\necho $chapter\n```\nhttps://example.com/story-memory\n")
        self.assertNotIn("demo: dangling skill reference $chapter", validate(self.root))
```

- [ ] **Step 2: Run focused tests and verify the validator is absent**

Run: `python3 -m unittest tests.test_distribution.ValidatorTests -v`

Expected: FAIL importing `scripts.validate_distribution`.

- [ ] **Step 3: Implement manifest, marketplace, and skill validation**

Validate strict semver with `^[0-9]+\.[0-9]+\.[0-9]+$`, required plugin identity fields, `skills == "./skills/"`, existing relative paths, exact marketplace policies, exact 25-skill set, directory/frontmatter name equality, nonempty descriptions, and allowed canonical frontmatter keys.

Scan Markdown links with `\[[^]]+\]\((?!https?://|#|mailto:)([^)]+)\)`. Use `extract_skill_references()` rather than raw global replacement: canonical slash references are errors, canonical dollar references must resolve, and fenced shell variables such as `$chapter` are ignored. Ignore link placeholders inside fenced code only when the target contains `{` or `<`; otherwise relative links must resolve.

- [ ] **Step 4: Implement worker, vocabulary, and cross-distribution validation**

Validate registry schema, unique workers, prompt paths, skill mappings, access enums, and read-only role assignments. Scan canonical runtime for Mars/Meridian commands and environment variables. When `cw/` exists, compare canonical and Claude versions and reject Codex-only `spawn_agent`, `$skill-name`, and `AGENTS.md` vocabulary in generated Claude runtime files.

- [ ] **Step 5: Run unit tests and validator**

Run: `python3 -m unittest tests.test_distribution -v`

Expected: all tests PASS.

Run: `python3 scripts/validate_distribution.py`

Expected before Task 7: exit `1` only for known stale/missing Claude-derived output; canonical plugin checks all pass. Add `--canonical-only` to run canonical checks independently and require it to exit `0` now.

- [ ] **Step 6: Commit the validator**

```bash
git add scripts/validate_distribution.py tests/test_distribution.py
git commit -m "feat: validate Codex and compatibility distributions"
```

---

### Task 7: Generate the Claude Compatibility Distribution

**Files:**
- Create: `scripts/sync_claude_distribution.py`
- Create: `tests/test_sync_claude_distribution.py`
- Modify: `cw/.claude-plugin/plugin.json`
- Modify: `.claude-plugin/marketplace.json`
- Replace: `cw/skills/**`
- Replace: `cw/agents/**`
- Delete after replacement: `scripts/sync_cw_skills.py`

**Interfaces:**
- Produces: `transform_skill(text: str, skill_name: str) -> str`.
- Produces: `render_agent(worker: dict[str, object], prompt: str) -> str`.
- Produces: `render_distribution(output_root: Path) -> None`.
- Produces CLI: `python3 scripts/sync_claude_distribution.py --apply` and `--check`.
- Consumes: canonical plugin manifest, 25 skills, muse worker registry/prompts, and `config/distribution.json`.

- [ ] **Step 1: Write failing transformation tests**

```python
class ClaudeTransformTests(unittest.TestCase):
    def test_skill_transform_uses_claude_instruction_names(self):
        source = "---\nname: demo\ndescription: Demo.\n---\nRead AGENTS.md and use $story-memory.\n"
        rendered = transform_skill(source, "demo")
        self.assertIn("Read CLAUDE.md", rendered)
        self.assertIn("/story-memory", rendered)
        self.assertNotIn("AGENTS.md", rendered)
        self.assertNotIn("$story-memory", rendered)

    def test_worker_renders_as_claude_agent(self):
        worker = {
            "name": "critic", "description": "Critique prose.",
            "skills": ["story-review"], "access": "read-only",
            "claude": {"model": "inherit", "background": False},
        }
        rendered = render_agent(worker, "Return findings to muse.\n")
        self.assertIn("name: critic", rendered)
        self.assertIn("skills:\n  - story-review", rendered)
        self.assertIn("Return findings to muse.", rendered)
        self.assertNotIn("model: inherit", rendered)

    def test_unknown_codex_only_construct_fails(self):
        with self.assertRaisesRegex(UnsupportedTransformError, "spawn_agent"):
            transform_skill("---\nname: demo\ndescription: Demo.\n---\nCall spawn_agent directly.\n", "demo")

    def test_transform_preserves_fenced_shell_variable(self):
        source = "---\nname: demo\ndescription: Demo.\n---\nUse $story-memory.\n```bash\necho $chapter\n```\n"
        rendered = transform_skill(source, "demo")
        self.assertIn("Use /story-memory.", rendered)
        self.assertIn("echo $chapter", rendered)
```

- [ ] **Step 2: Run tests and verify the generator is absent**

Run: `python3 -m unittest tests.test_sync_claude_distribution -v`

Expected: FAIL importing `scripts.sync_claude_distribution`.

- [ ] **Step 3: Implement deterministic skill transforms**

Parse canonical frontmatter, emit Claude `name` and `description`, preserve `disable-model-invocation` and `argument-hint` where present, and transform known runtime syntax. Apply replacements only outside fenced code blocks. The supported table is:

```python
TEXT_REPLACEMENTS = {
    "AGENTS.md": "CLAUDE.md",
    "Codex subagent": "subagent",
    "Codex subagents": "subagents",
}
```

Transform `$known-skill` to `/known-skill` outside fenced code. After rendering, require every extracted Claude slash reference to resolve to the canonical registry and require every extracted dollar reference set to be empty. Reject `spawn_agent`, `collaboration.`, `.codex-plugin`, and unrecognized dollar references after known-skill replacement. Copy all non-`SKILL.md` files except `agents/openai.yaml`; transform Markdown resources with the same platform vocabulary rules.

- [ ] **Step 4: Implement Claude agent generation**

Render ten worker agents from the registry. Generate `cw/agents/muse.md` from the canonical muse body with frontmatter name `muse`, its canonical description, and the complete available skill list. Do not emit Mars model aliases, tool policies, sandbox fields, or unsupported frontmatter.

- [ ] **Step 5: Generate Claude manifests from canonical metadata**

Set `cw/.claude-plugin/plugin.json` version, description, author, homepage, repository, and license from the Codex manifest. Update `.claude-plugin/marketplace.json` to point at `./cw`, use the InkyQuill repository identity, and copy canonical version `0.5.9`.

- [ ] **Step 6: Apply, check, and validate generated output**

Run: `python3 scripts/sync_claude_distribution.py --apply`

Expected: 25 skill sync lines, 11 agent sync lines, and manifest sync lines.

Run: `python3 scripts/sync_claude_distribution.py --check`

Expected: exit `0` with `Claude distribution is in sync`.

Run: `python3 -m unittest tests.test_sync_claude_distribution -v && python3 scripts/validate_distribution.py`

Expected: all tests PASS and full validation exits `0`.

- [ ] **Step 7: Remove the obsolete Mars-backed sync script and commit**

```bash
git add scripts/sync_claude_distribution.py tests/test_sync_claude_distribution.py cw .claude-plugin/marketplace.json
git rm scripts/sync_cw_skills.py
git commit -m "feat: generate Claude compatibility from Codex"
```

---

### Task 8: Update Archives, Documentation, and Behavioral Release Checks

**Files:**
- Modify: `scripts/create_skill_zips.py`
- Create: `scripts/release.py`
- Delete: `scripts/release.sh`
- Modify: `README.md`
- Modify: `docs/architecture.md`
- Create: `docs/behavioral-release-checklist.md`
- Modify: `AGENTS.md`
- Modify: `CLAUDE.md`
- Modify: `tests/test_sync_claude_distribution.py`
- Create: `tests/test_release.py`

**Interfaces:**
- `create_skill_zips.find_skill_dirs(repo_root: Path) -> list[Path]` continues to read generated `cw/skills`.
- Produces: `create_skill_zips.validate_skill_set(skill_dirs: list[Path], expected_names: set[str]) -> None`, raising `ValueError` on missing or extra skills.
- Produces: `release.bump_semver(version: str, part: str) -> str` and CLI `python3 scripts/release.py [patch|minor|major] [--push]`.
- Documentation declares Codex marketplace installation as primary and Claude as compatibility.

- [ ] **Step 1: Add failing archive and release-version tests**

```python
class ArchiveContractTests(unittest.TestCase):
    def test_archive_validation_rejects_missing_skill(self):
        with self.assertRaisesRegex(ValueError, "missing: world-creation"):
            validate_skill_set([Path("character-sim")], {"character-sim", "world-creation"})
```

Create `tests/test_release.py` with:

```python
class ReleaseVersionTests(unittest.TestCase):
    def test_bump_semver(self):
        self.assertEqual(bump_semver("0.5.9", "patch"), "0.5.10")
        self.assertEqual(bump_semver("0.5.9", "minor"), "0.6.0")
        self.assertEqual(bump_semver("0.5.9", "major"), "1.0.0")

    def test_bump_rejects_non_semver(self):
        with self.assertRaisesRegex(ValueError, "strict semantic version"):
            bump_semver("0.5", "patch")
```

- [ ] **Step 2: Run the new tests and verify the interfaces are absent**

Run: `python3 -m unittest tests.test_sync_claude_distribution.ArchiveContractTests tests.test_release -v`

Expected: FAIL importing `validate_skill_set` and `scripts.release`.

- [ ] **Step 3: Implement archive inventory validation and release versioning**

Before writing archives, `create_skill_zips.py` loads the exact expected set from `config/distribution.json` and calls `validate_skill_set()`. The error lists sorted missing and extra names.

`scripts/release.py` reads the canonical manifest, validates the worktree is clean and branch is `main`, computes the next version, rejects an existing tag, updates only canonical `plugin.json`, runs `sync_claude_distribution.py --apply`, then runs unit tests, distribution validation, Claude drift check, and zip creation. After successful checks it stages the canonical manifest plus derived metadata, commits `Release v<version>`, tags it, and pushes the branch and tag only with `--push`. Use `subprocess.run([...], check=True)` argument arrays for every command.

- [ ] **Step 4: Rewrite installation and architecture documentation**

README order:

1. Codex primary installation: `codex plugin marketplace add InkyQuill/creative-writing-skills`, then install `creative-writing-skills` from that source.
2. Start naturally or invoke `$creative-writing-muse`; include `$world-creation` example.
3. Explain multi-agent specialist passes and the single-agent fallback.
4. Claude Code/Cowork marketplace compatibility.
5. Claude.ai release archives.
6. Contributor workflow using repository Python scripts, with no Mars/Meridian commands.

Update `docs/architecture.md` to show muse → worker-prompt → Codex subagent flow and `canonical plugin → Claude generator → cw/`. Update root `AGENTS.md` and `CLAUDE.md` so contributors edit canonical plugin skills first, run the generator, and never hand-edit generated `cw/` output.

- [ ] **Step 5: Create the exact manual behavioral checklist**

For each of these, include a representative prompt, expected skill/worker routing, observable pass criteria, and prohibited behavior: automatic muse activation, explicit muse, brainstorm, outline, draft, revision, critic, editor, reader simulation, continuity, character simulation, world creation, story memory, parallel independent workers, sequential draft-review, and forced single-agent fallback.

- [ ] **Step 6: Run archive/release tests, then build and inspect all Claude.ai archives**

Run: `python3 -m unittest tests.test_sync_claude_distribution.ArchiveContractTests tests.test_release -v`

Expected: all tests PASS.

Run: `python3 scripts/create_skill_zips.py`

Expected: `Successfully created 25 .skill files` and `zips/world-creation.skill` exists.

Run: `python3 -m zipfile -l zips/world-creation.skill`

Expected: archive contains `world-creation/SKILL.md` and `world-creation/references/world-file-format.md`, with no `agents/openai.yaml`.

- [ ] **Step 7: Run documentation and distribution validation**

Run: `python3 -m unittest discover -s tests -v && python3 scripts/validate_distribution.py && python3 scripts/sync_claude_distribution.py --check`

Expected: all tests and checks PASS.

- [ ] **Step 8: Commit docs and release artifacts workflow**

```bash
git add README.md docs/architecture.md docs/behavioral-release-checklist.md AGENTS.md CLAUDE.md scripts/create_skill_zips.py scripts/release.py tests/test_sync_claude_distribution.py tests/test_release.py
git rm scripts/release.sh
git commit -m "docs: make Codex the primary writing workflow"
```

---

### Task 9: Replace CI and Remove Mars/Meridian Scaffolding

**Files:**
- Modify: `.github/workflows/ci.yml`
- Modify: `.github/workflows/release.yml`
- Modify: `.githooks/pre-commit`
- Delete: `mars.toml`
- Delete: `meridian.toml`
- Delete: `agents/**`
- Delete: `skills/**`
- Delete: `bootstrap/**`
- Delete: `.codex/hooks.json`
- Delete: `.codex/hooks/deny-interactive-prompts/**`
- Delete: `.claude/hooks/**`
- Delete: `.claude/settings.json`
- Delete: `.claude/commands/**`
- Modify: `.gitignore`
- Modify: `tests/test_distribution.py`

**Interfaces:**
- CI canonical command: `python3 scripts/validate_distribution.py`.
- CI test command: `python3 -m unittest discover -s tests -v`.
- CI drift commands: `python3 scripts/vendor_generic_skills.py --check` and `python3 scripts/sync_claude_distribution.py --check`.
- Release version source: `plugins/creative-writing-skills/.codex-plugin/plugin.json`.

- [ ] **Step 1: Write a failing legacy-scaffolding absence test**

```python
    def test_removed_package_scaffolding_is_absent(self):
        for relative in (
            "mars.toml", "meridian.toml", "agents", "skills", "bootstrap",
            ".codex/hooks.json", ".codex/hooks/deny-interactive-prompts",
        ):
            self.assertFalse((REPO_ROOT / relative).exists(), relative)
```

- [ ] **Step 2: Run the test and verify legacy paths still exist**

Run: `python3 -m unittest tests.test_distribution.DistributionScaffoldTests.test_removed_package_scaffolding_is_absent -v`

Expected: FAIL on `mars.toml`.

- [ ] **Step 3: Replace CI validation and release version lookup**

Remove Meridian installation and `meridian mars check`. CI must install Node only for Claude CLI validation, then run unit tests, canonical validator, vendor check, Claude drift check, Claude plugin validation, and zip build. Because vendor check needs the pinned licensed source, clone `haowjy/creative-writing-skills` at `fd7a3ad…` into `${RUNNER_TEMP}/licensed-source` and pass `--source-checkout`.

In release validation, read version with a short Python command from `plugins/creative-writing-skills/.codex-plugin/plugin.json`; compare tag `v${version}`. Build 25 `.skill` files and attach them to the GitHub release.

- [ ] **Step 4: Replace the pre-commit hook**

The hook runs, in order:

```bash
python3 -m unittest discover -s tests
python3 scripts/validate_distribution.py
python3 scripts/sync_claude_distribution.py --check
python3 scripts/create_skill_zips.py
```

Skip only Claude CLI validation when `claude` is absent. Do not add a network-dependent vendor refresh to pre-commit.

- [ ] **Step 5: Remove obsolete source and generated scaffolding**

Delete the listed Mars/Meridian roots only after Task 7 full validation passes. Remove root `.claude/commands/` because it is not included by the `./cw` marketplace plugin and its stale skill names are superseded by generated plugin skills. Remove ignored generated Mars target patterns that no longer apply, while retaining zip and local cache ignores.

- [ ] **Step 6: Run the full local CI sequence**

Run:

```bash
python3 -m unittest discover -s tests -v
python3 scripts/validate_distribution.py
python3 scripts/vendor_generic_skills.py --check
python3 scripts/sync_claude_distribution.py --check
python3 scripts/create_skill_zips.py
```

Expected: all commands exit `0`; 25 archives are created; no Mars/Meridian runtime path is reported.

- [ ] **Step 7: Run Claude's validators when available**

Run: `claude plugins validate .claude-plugin/marketplace.json && claude plugins validate cw`

Expected: both validations PASS. If `claude` is not installed locally, CI remains the required evidence for this pair.

- [ ] **Step 8: Commit the platform cleanup**

```bash
git add .github/workflows/ci.yml .github/workflows/release.yml .githooks/pre-commit .gitignore tests/test_distribution.py
git add -u mars.toml meridian.toml agents skills bootstrap .codex .claude
git commit -m "chore: remove Mars and Meridian packaging"
```

---

### Task 10: Verify Marketplace Installation and Record the Migration

**Files:**
- Modify: `CHANGELOG.md`
- Modify: `docs/behavioral-release-checklist.md`
- Modify: `docs/superpowers/specs/2026-08-09-codex-primary-plugin-design.md` only to record the resolved licensed-source and per-skill-interface decisions if those edits are not already present.

**Interfaces:**
- Produces: evidence that the repo marketplace resolves and the installed plugin exposes 25 skills.
- Produces: completed static verification section and an uncompleted human/model behavioral checklist ready for a release candidate session.

- [ ] **Step 1: Add the migration changelog entry**

Under `[Unreleased]`, record Codex-primary packaging, 25 canonical skills, muse worker resources, `world-creation`, generated Claude compatibility, pinned licensed generic snapshots, new validation, and removal of Mars/Meridian requirements. Include a breaking-change note for contributors who edited root `skills/` or ran `meridian mars` commands.

- [ ] **Step 2: Run the complete verification suite from a clean process**

Run:

```bash
git diff --check
python3 -m unittest discover -s tests -v
python3 scripts/validate_distribution.py
python3 scripts/sync_claude_distribution.py --check
python3 scripts/create_skill_zips.py
```

Expected: no whitespace errors, all tests PASS, both checks exit `0`, and 25 archives are reported.

- [ ] **Step 3: Test the repo marketplace with Codex**

Run: `codex plugin marketplace add .`

Expected: Codex recognizes the local repo marketplace and lists `creative-writing-skills` as available. Install it through the Codex app's Plugins view, start a new conversation, and verify the skill list contains 25 unique names including `creative-writing-muse` and `world-creation`.

Do not mutate the user's global marketplace from automation if the CLI requests confirmation; perform this step interactively and record the observed result in `docs/behavioral-release-checklist.md`.

- [ ] **Step 4: Execute the two release-blocking behavioral scenarios**

Before broader manual evaluation, run:

1. `Help me develop a novel idea about a city that forgets one resident every winter.` Expected: automatic muse activation, intent capture, and specialist routing without canon writes.
2. `Use $world-creation to reconcile a new inheritance law with this project's existing lore.` Expected: both layouts are discovered, one decision question is asked with a recommendation, and no prose file is edited.

Record model/date, routing observed, files touched, and pass/fail in the checklist. Leave the remaining behavioral scenarios unchecked for the release-candidate pass rather than claiming model behavior from static tests.

- [ ] **Step 5: Inspect final repository state**

Run: `git status --short && git log --oneline -10`

Expected: only the user's pre-existing spec modification is uncommitted unless it was deliberately included; the task commits appear in order and no generated zip is staged.

- [ ] **Step 6: Commit migration record and resolved spec facts**

```bash
git add CHANGELOG.md docs/behavioral-release-checklist.md docs/superpowers/specs/2026-08-09-codex-primary-plugin-design.md
git commit -m "docs: record Codex plugin migration"
```

## Final Review Checkpoint

After Task 10, review the complete diff against the design spec before merging:

```bash
git diff fd7a3ad9cd7697a0645ff6ff4bd5e809cf7673a3..HEAD --stat
git diff fd7a3ad9cd7697a0645ff6ff4bd5e809cf7673a3..HEAD -- . ':!cw' ':!zips'
```

Confirm that canonical files are understandable without reading generator internals, generated `cw/` contains no hand-authored divergence, third-party notices match the pinned sources, and no active command or documentation path requires Mars or Meridian.

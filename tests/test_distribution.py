import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from scripts.distribution import (
    PLUGIN_ROOT,
    REPO_ROOT,
    extract_skill_references,
    load_json,
    map_outside_fences,
    split_frontmatter,
)
from scripts.validate_distribution import main as validate_main
from scripts.validate_distribution import (
    _is_within,
    compute_structured_artifact_audit,
    validate,
)
from scripts.sync_claude_distribution import transform_skill


EXPECTED_SKILLS = {
    "character-sim", "creative-research", "creative-writing-craft",
    "creative-writing-modes", "creative-writing-muse", "grill-with-docs",
    "information-hierarchy", "intent-modeling", "kb-management",
    "knowledge-layers", "llm-writing", "md-validation", "project-maintenance",
    "project-setup", "qi-layer", "reader-sim", "reflect", "shared-dao", "story-memory",
    "story-planning", "story-review", "structured-artifact",
    "targeted-editing", "world-creation", "writing-principles",
    "writing-staffing", "zoom-out",
}

EXPECTED_WORKERS = {
    "brainstormer", "character-sim", "continuity-checker", "critic", "editor",
    "outliner", "reader-sim", "style-creator", "web-researcher", "writer",
}

EXPECTED_WORKER_CONFIG = {
    "brainstormer": ("workspace-write", {"story-planning", "story-memory", "intent-modeling", "llm-writing"}),
    "character-sim": ("read-only", {"character-sim", "writing-principles", "llm-writing", "story-memory"}),
    "continuity-checker": ("read-only", {"story-review", "md-validation", "shared-dao", "story-memory"}),
    "critic": ("read-only", {"story-review", "writing-principles", "llm-writing", "story-memory"}),
    "editor": ("read-only", {"story-review", "writing-principles", "creative-writing-craft", "llm-writing", "story-memory"}),
    "outliner": ("workspace-write", {"story-planning", "story-memory", "md-validation"}),
    "reader-sim": ("read-only", {"reader-sim", "writing-principles", "llm-writing"}),
    "style-creator": ("workspace-write", {"creative-writing-craft", "writing-principles", "llm-writing", "story-memory"}),
    "web-researcher": ("workspace-write", {"creative-research"}),
    "writer": ("workspace-write", {"creative-writing-modes", "creative-writing-craft", "targeted-editing", "writing-principles", "story-memory", "llm-writing"}),
}

PRESSURE_RESULTS = REPO_ROOT / "tests" / "fixtures" / "muse-pressure" / "results.md"


class DistributionScaffoldTests(unittest.TestCase):
    def test_structured_artifact_audit_is_deterministic_and_current(self):
        skill_root = PLUGIN_ROOT / "skills" / "structured-artifact"
        expected = load_json(
            REPO_ROOT / "config" / "structured-artifact-audit.json"
        )
        self.assertEqual(compute_structured_artifact_audit(skill_root), expected)
        self.assertEqual(
            [item["path"] for item in expected["resources"]],
            sorted(item["path"] for item in expected["resources"]),
        )
        result = subprocess.run(
            ["python3", "scripts/audit_structured_artifact_resources.py"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertEqual(json.loads(result.stdout), expected)

    def test_structured_artifact_audit_helper_rejects_symlinks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            target = root / "target.js"
            target.write_text("safe();\n")
            (root / "linked.js").symlink_to(target)
            with self.assertRaisesRegex(
                ValueError,
                "cannot open resource linked.js",
            ):
                compute_structured_artifact_audit(root)

    def test_structured_artifact_audit_helper_rejects_directory_symlink_race(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve() / "skill"
            nested = root / "nested"
            nested.mkdir(parents=True)
            (nested / "approved.bin").write_bytes(b"approved")
            external = Path(directory) / "external"
            external.mkdir()
            (external / "approved.bin").write_bytes(b"external")
            backup = root / "nested-backup"
            real_open = os.open
            raced = False

            def replace_directory(path, flags, *args, dir_fd=None, **kwargs):
                nonlocal raced
                if path == "nested" and dir_fd is not None and not raced:
                    raced = True
                    nested.rename(backup)
                    nested.symlink_to(external, target_is_directory=True)
                return real_open(path, flags, *args, dir_fd=dir_fd, **kwargs)

            with mock.patch(
                "scripts.validate_distribution.os.open",
                side_effect=replace_directory,
            ):
                with self.assertRaisesRegex(ValueError, "cannot open resource nested"):
                    compute_structured_artifact_audit(root)

    def test_worker_registry_is_complete_and_resolvable(self):
        registry_path = PLUGIN_ROOT / "skills" / "creative-writing-muse" / "resources" / "workers" / "registry.json"
        registry = load_json(registry_path)
        workers = registry["workers"]
        self.assertEqual(len(workers), len(EXPECTED_WORKERS))
        self.assertEqual({item["name"] for item in workers}, EXPECTED_WORKERS)
        self.assertEqual(len({item["prompt"] for item in workers}), len(workers))
        canonical = set(load_json(REPO_ROOT / "config" / "distribution.json")["canonical_skills"])
        for item in workers:
            self.assertEqual(set(item), {"name", "description", "prompt", "skills", "access", "claude"})
            self.assertIn(item["access"], {"read-only", "workspace-write"})
            self.assertTrue((registry_path.parent / item["prompt"]).is_file())
            self.assertLessEqual(set(item["skills"]), canonical)
            expected_access, expected_skills = EXPECTED_WORKER_CONFIG[item["name"]]
            self.assertEqual(item["access"], expected_access)
            self.assertEqual(set(item["skills"]), expected_skills)
            self.assertEqual(item["claude"], {
                "model": "inherit",
                "background": item["name"] == "web-researcher",
            })

    def test_worker_prompts_have_required_contract_and_access_language(self):
        registry_path = PLUGIN_ROOT / "skills" / "creative-writing-muse" / "resources" / "workers" / "registry.json"
        for item in load_json(registry_path)["workers"]:
            text = (registry_path.parent / item["prompt"]).read_text()
            self.assertTrue(text.startswith("# Function\n"), item["name"])
            for heading in {"## Required inputs", "## Return shape", "## Access boundary"}:
                self.assertEqual(text.count(heading), 1, (item["name"], heading))
            if item["access"] == "read-only":
                self.assertIn("Read-only.", text, item["name"])
                self.assertIn("never patch", text, item["name"])
                self.assertNotIn("Workspace-write.", text, item["name"])
            else:
                self.assertIn("Workspace-write.", text, item["name"])
                self.assertIn("caller-assigned paths", text, item["name"])
                self.assertIn("do not revert", text, item["name"])

    def test_muse_pressure_evidence_is_complete_and_reproducible(self):
        text = PRESSURE_RESULTS.read_text()
        self.assertTrue(text.startswith("# Muse Pressure Verification\n"))
        muse_path = PLUGIN_ROOT / "skills" / "creative-writing-muse" / "SKILL.md"
        muse_text = muse_path.read_text()
        skill_match = re.search(
            r"<!-- revised-skill:start -->\n```text\n(.*?)```\n<!-- revised-skill:end -->",
            text,
            re.DOTALL,
        )
        self.assertIsNotNone(skill_match)
        self.assertEqual(skill_match.group(1), muse_text)
        expected_hash = hashlib.sha256(muse_text.encode()).hexdigest()
        self.assertIn(f"Revised skill SHA-256: `{expected_hash}`", text)

        families = {"parallel-sequential", "fallback-disclosure", "memory-intent"}
        for family in families:
            self.assertEqual(text.count(f"## Family: {family}"), 1)
            self.assertIn(f"<!-- prompt:{family}/control -->", text)
            self.assertIn(f"<!-- prompt:{family}/revised -->", text)
            for variant in {"control", "revised"}:
                markers = re.findall(
                    rf"<!-- sample:{family}/{variant}/(\d+) compliant=(true|false) -->",
                    text,
                )
                self.assertEqual({int(index) for index, _ in markers}, set(range(1, 6)))
                self.assertEqual(len(markers), 5)
            self.assertIn(f"### Variance: {family}", text)
            self.assertIn(f"<!-- final:{family} compliant=true -->", text)

        sample_sections = re.findall(
            r"<!-- sample:[^>]+ -->\n(.*?)(?=<!-- (?:sample|final):)",
            text,
            re.DOTALL,
        )
        self.assertEqual(len(sample_sections), 30)
        for section in sample_sections:
            self.assertRegex(section, r"(?s)### Output\n\n```text\n.+?```")
            self.assertRegex(section, r"(?s)### Manual score\n\n\S.+")

        final_sections = re.findall(
            r"<!-- final:[^>]+ -->\n(.*?)(?=\n## Family:|\Z)",
            text,
            re.DOTALL,
        )
        self.assertEqual(len(final_sections), 3)
        for section in final_sections:
            self.assertRegex(section, r"(?s)#### Full prompt\n\n(?:```|~~~~)text\n.+?(?:```|~~~~)")
            self.assertRegex(section, r"(?s)#### Raw output\n\n(?:```|~~~~)text\n.+?(?:```|~~~~)")
            self.assertRegex(section, r"(?s)#### Manual score\n\nPASS — .+")

    def test_review_workers_are_read_only(self):
        registry = load_json(PLUGIN_ROOT / "skills" / "creative-writing-muse" / "resources" / "workers" / "registry.json")
        access = {item["name"]: item["access"] for item in registry["workers"]}
        for name in {"character-sim", "continuity-checker", "critic", "editor", "reader-sim"}:
            self.assertEqual(access[name], "read-only")

    def test_continuity_worker_preserves_evidence_only_decision_boundary(self):
        path = PLUGIN_ROOT / "skills" / "creative-writing-muse" / "resources" / "workers" / "continuity-checker.md"
        text = path.read_text()
        self.assertIn("middle passages extra attention", text)
        self.assertIn("Report evidence without proposing repairs", text)
        self.assertIn("Leave fix selection and canon resolution to muse and the author", text)

    def test_story_planning_routes_to_each_task_specific_resource(self):
        skill = (PLUGIN_ROOT / "skills/story-planning/SKILL.md").read_text()
        self.assertIn("`resources/creative-direction.md`", skill)
        self.assertIn("`resources/brainstorming.md`", skill)
        self.assertIn("`resources/story-architecture.md`", skill)
        self.assertNotIn("`resources/story-planning.md`", skill)

    def test_project_setup_keeps_discovery_material_provisional_until_approval(self):
        text = (PLUGIN_ROOT / "skills/project-setup/SKILL.md").read_text()
        discovery, creation = text.split("## Create the Files", 1)
        self.assertRegex(
            discovery.lower(),
            r"keep\s+samples and voice goals provisional",
        )
        self.assertIn("do not save", discovery.lower())
        self.assertIn("once approved", creation.lower())
        self.assertIn("author confirmed", creation.lower())
        self.assertIn("draft project instructions for `AGENTS.md`", text)
        self.assertNotIn("draft an `AGENTS.md`", text)

    def test_project_setup_selects_and_extends_the_established_layout(self):
        text = (PLUGIN_ROOT / "skills/project-setup/SKILL.md").read_text()
        self.assertRegex(text, r"indexes and populated\s+directories")
        for index_name in ("`_index.md`", "`index.md`", "`INDEX.md`", "`README.md`"):
            self.assertIn(index_name, text)
        self.assertIn("use Layout A", text)
        self.assertIn("use Layout B", text)
        self.assertIn("population score", text)
        self.assertRegex(text, r"populated\s+core role directories")
        self.assertIn("durable files", text)
        self.assertIn("higher population score", text)
        self.assertRegex(text, r"Never create the\s+competing layout")

    def test_project_setup_requires_one_confirmed_layout_decision_when_ambiguous(self):
        text = (PLUGIN_ROOT / "skills/project-setup/SKILL.md").read_text()
        self.assertIn("If neither layout has evidence", text)
        self.assertRegex(
            text,
            r"recommend one layout with a project-specific\s+rationale",
        )
        self.assertIn("wait for explicit confirmation", text)
        self.assertIn("If both have the same population score", text)
        self.assertRegex(text, r"ask one focused\s+choice")
        self.assertIn("Do not propose paths or create files until", text)

    def test_project_setup_proposal_and_creation_paths_are_layout_conditional(self):
        text = (PLUGIN_ROOT / "skills/project-setup/SKILL.md").read_text()
        self.assertIn("### Layout A paths", text)
        self.assertIn("### Layout B paths", text)
        layout_a, layout_b = text.split("### Layout A paths", 1)[1].split(
            "### Layout B paths", 1
        )
        for path in (
            "`worldbuilding/`",
            "`characters/`",
            "`chapters/`",
            "`drafts/`",
            "`plot/`",
        ):
            self.assertIn(path, layout_a)
        self.assertIn("Do not create a `kb/`, `story/`", layout_a)
        for path in (
            "`kb/world/`",
            "`kb/characters/`",
            "`story/`",
            "`work/drafts/`",
            "`work/outline/`",
            "`kb/samples/`",
            "`kb/styles/`",
        ):
            self.assertIn(path, layout_b)
        self.assertIn("author-confirmed", layout_a.lower())
        self.assertIn("author-confirmed", layout_b.lower())
        self.assertIn("local conventions", layout_a.lower())
        self.assertIn("local conventions", layout_b.lower())

    def test_llm_writing_requires_an_authorized_artifact_path_for_disk_drafts(self):
        text = (PLUGIN_ROOT / "skills/llm-writing/SKILL.md").read_text()
        self.assertIn("explicitly writable artifact", text)
        self.assertIn("caller-assigned path", text)
        self.assertIn("draft and revise in the response context", text)
        self.assertNotIn("Write a full draft to disk so you can edit it piece by piece", text)

    def test_creative_direction_returns_scoped_analysis_to_muse(self):
        text = (
            PLUGIN_ROOT
            / "skills/story-planning/resources/creative-direction.md"
        ).read_text()
        self.assertIn("Return to muse", text)
        self.assertIn("options", text.lower())
        self.assertIn("evidence", text.lower())
        self.assertIn("tradeoffs", text.lower())
        self.assertIn("`Chapter 3: Scene where X discovers Y`", text)
        self.assertIn("`magic-system.md`", text)
        for author_facing_owner in (
            "Brainstorm alongside the author",
            "Synthesize and present",
            "author confirms direction",
            "Hand off",
            "update directly",
            "Record decisions",
        ):
            self.assertNotIn(author_facing_owner, text)

    def test_brainstorm_capture_preserves_author_and_hidden_provenance(self):
        text = (
            PLUGIN_ROOT
            / "skills/story-planning/resources/brainstorming.md"
        ).read_text()
        self.assertIn("Tag only new AI suggestions", text)
        self.assertIn("author statements remain untagged", text.lower())
        self.assertIn("hidden content stays wrapped in `<hidden>...</hidden>`", text.lower())
        self.assertNotIn("tag all generated content", text)

    def test_story_memory_promotion_preserves_source_tags_and_hidden_boundary(self):
        text = (
            PLUGIN_ROOT
            / "skills/story-memory/resources/writing-artifacts.md"
        ).read_text()
        self.assertIn("Untagged author-stated text remains untagged", text)
        self.assertIn("Preserve `<AI>...</AI>` markers", text)
        self.assertIn("Exclude `<hidden>...</hidden>`", text)
        self.assertIn("both the fact and its destination", text)

    def test_structured_artifact_examples_do_not_enable_markup_injection(self):
        resource_root = PLUGIN_ROOT / "skills/structured-artifact/resources"
        security_problems = [
            problem
            for problem in validate(REPO_ROOT, canonical_only=True)
            if "unsafe executable HTML/JavaScript" in problem
        ]
        self.assertEqual([], security_problems)
        tree = (resource_root / "tree-and-toc.md").read_text()
        diagrams = (resource_root / "diagrams.md").read_text()
        cards = (resource_root / "card-grid.md").read_text()
        self.assertNotIn("innerHTML", tree)
        self.assertNotIn("innerHTML", diagrams)
        self.assertIn("textContent", tree)
        self.assertIn("replaceChildren", tree)
        self.assertIn("textContent", diagrams)
        self.assertIn("replaceChildren", diagrams)
        self.assertIn("securityLevel: 'strict'", diagrams)
        self.assertNotIn("securityLevel: 'loose'", diagrams)
        self.assertNotRegex(diagrams, r"(?m)^\s*click\s+\w+\s+\w+")
        self.assertIn("ALLOWED_DETAIL_KEYS", diagrams)
        self.assertNotIn("new Set(Object.keys(DETAIL))", diagrams)
        self.assertIn("const d = DETAIL[key];\n  if (!d) return;", diagrams)
        self.assertNotIn("innerHTML", cards)
        self.assertNotIn("onclick", cards)
        self.assertIn(
            ".sort((a, b) => (a[s] === b[s] ? 0 : a[s] > b[s] ? 1 : -1))",
            cards,
        )
        for operation in (
            "createElement",
            "textContent",
            "addEventListener",
            "replaceChildren",
        ):
            self.assertIn(operation, cards)

    def test_knowledge_bootstrap_template_uses_canonical_skill_syntax(self):
        text = (
            PLUGIN_ROOT
            / "skills/knowledge-layers/resources/bootstrap.md"
        ).read_text()
        self.assertIn("Use `$md-validation` for link checking", text)
        self.assertNotIn("Use `/md-validation` for link checking", text)

    def test_prose_analyzer_commands_use_packaged_path_and_python3(self):
        root = PLUGIN_ROOT / "skills/story-review/resources"
        documents = (
            root / "prose-critique.md",
            root / "prose-critique/analyze.py",
            root / "prose-critique/baseline.md",
        )
        expected = "python3 resources/prose-critique/analyze.py"
        for path in documents:
            text = path.read_text()
            self.assertIn(expected, text, str(path))
            self.assertNotIn("uv run resources/analyze.py", text, str(path))

    def test_story_memory_evidence_examples_use_full_source_anchors(self):
        root = PLUGIN_ROOT / "skills/story-memory"
        markdown = "\n".join(path.read_text() for path in root.rglob("*.md"))
        self.assertNotRegex(markdown, r"\[(?:Ch\.?|Chapter)\s*\d+\]")
        self.assertIn(
            "Chapter 7: Scene where the protagonist learns when the mentor's secret project began",
            markdown,
        )
        self.assertIn("`magic-system.md`", markdown)

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

    def test_manifest_and_marketplace_use_canonical_identity(self):
        manifest = load_json(PLUGIN_ROOT / ".codex-plugin" / "plugin.json")
        marketplace = load_json(REPO_ROOT / ".agents" / "plugins" / "marketplace.json")
        self.assertEqual(manifest["name"], "creative-writing-skills")
        self.assertRegex(manifest["version"], r"^[0-9]+\.[0-9]+\.[0-9]+$")
        self.assertEqual(manifest["repository"], "https://github.com/InkyQuill/creative-writing-skills")
        self.assertEqual(manifest["skills"], "./skills/")
        self.assertEqual(marketplace["plugins"][0]["source"]["path"], "./plugins/creative-writing-skills")

        zcode_marketplace = load_json(REPO_ROOT / "marketplace.json")
        zcode_entry = zcode_marketplace["plugins"][0]
        self.assertEqual(zcode_marketplace["name"], manifest["name"])
        self.assertEqual(zcode_marketplace["description"], manifest["description"])
        self.assertEqual(zcode_entry["name"], manifest["name"])
        self.assertEqual(zcode_entry["description"], manifest["description"])
        self.assertEqual(zcode_entry["version"], manifest["version"])
        self.assertEqual(zcode_entry["source"], "./cw")
        zcode_manifest = load_json(REPO_ROOT / "cw" / ".zcode-plugin" / "plugin.json")
        self.assertEqual(zcode_manifest["name"], manifest["name"])
        self.assertEqual(zcode_manifest["version"], manifest["version"])

    def test_canonical_runtime_has_no_mars_or_meridian_scaffolding(self):
        forbidden = re.compile(r"\b(?:Mars|Meridian)\b|meridian\s+(?:spawn|mars|context|work)|MERIDIAN_[A-Z_]+")
        for path in (PLUGIN_ROOT / "skills").rglob("*"):
            if path.is_file() and path.suffix in {".md", ".json", ".yaml"}:
                self.assertIsNone(forbidden.search(path.read_text()), str(path))

    def test_removed_package_scaffolding_is_absent(self):
        for relative in (
            "mars.toml", "meridian.toml", "agents", "skills", "bootstrap",
            ".codex/hooks.json", ".codex/hooks/deny-interactive-prompts",
        ):
            self.assertFalse((REPO_ROOT / relative).exists(), relative)

    def test_active_workflow_docs_resolve_canonical_sources(self):
        research_paths = (
            REPO_ROOT / "docs" / "research" / "README.md",
            REPO_ROOT / "docs" / "research" / "reader-interest-second-pass.md",
        )
        for path in research_paths:
            text = path.read_text()
            self.assertNotRegex(text, r"\bMeridian\b", str(path))
            self.assertNotRegex(text, r"[\"`](?:agents|skills)/", str(path))
            canonical_sources = re.findall(
                r"`(plugins/creative-writing-skills/skills/[^`]+)`",
                text,
            )
            self.assertTrue(canonical_sources, str(path))
            for relative in canonical_sources:
                self.assertTrue((REPO_ROOT / relative.rstrip("/")).exists(), relative)

        workflow_path = REPO_ROOT / "docs" / "writing-workflow.html"
        workflow_text = workflow_path.read_text()
        self.assertNotRegex(workflow_text, r"[\"`](?:agents|skills)/")
        self.assertNotIn("cw/", workflow_text)
        data_match = re.search(
            r"    const DATA = (\{.*?\n  \});\n    let mode",
            workflow_text,
            re.DOTALL,
        )
        self.assertIsNotNone(data_match)
        data = json.loads(data_match.group(1))

        config = load_json(REPO_ROOT / "config" / "distribution.json")
        self.assertEqual(set(data["skills"]), set(config["canonical_skills"]))

        workers_root = (
            "plugins/creative-writing-skills/skills/creative-writing-muse/"
            "resources/workers"
        )
        registry = load_json(REPO_ROOT / workers_root / "registry.json")
        expected_worker_sources = {
            f"{workers_root}/{item['prompt']}" for item in registry["workers"]
        }
        expected_worker_sources.add(
            "plugins/creative-writing-skills/skills/creative-writing-muse/SKILL.md"
        )
        actual_worker_sources = {
            item["path"] for item in data["agents"].values() if item["path"]
        }
        self.assertEqual(actual_worker_sources, expected_worker_sources)

        self.assertEqual(
            set(data["agents"]["muse"]["routes"]),
            {item["name"] for item in registry["workers"]},
        )

        for worker in registry["workers"]:
            embedded = data["agents"][worker["name"]]
            self.assertEqual(embedded["description"], worker["description"])
            self.assertEqual(
                set(embedded["load"] + embedded["available"]),
                set(worker["skills"]),
            )

        for name, item in data["skills"].items():
            expected = f"plugins/creative-writing-skills/skills/{name}/SKILL.md"
            self.assertEqual(item["path"], expected)
            self.assertEqual(item["source"], "canonical plugin")
            self.assertTrue((REPO_ROOT / expected).is_file(), expected)
            metadata, _ = split_frontmatter((REPO_ROOT / expected).read_text())
            self.assertEqual(item["description"], str(metadata["description"]).strip())
            self.assertEqual(
                item["modelInvocable"],
                not metadata.get("disable-model-invocation", False),
            )

        muse_metadata, _ = split_frontmatter(
            (PLUGIN_ROOT / "skills/creative-writing-muse/SKILL.md").read_text()
        )
        self.assertEqual(
            data["agents"]["muse"]["description"],
            str(muse_metadata["description"]).strip(),
        )
        self.assertIn("fallback", workflow_text.lower())
        self.assertNotIn("@kb-lead", workflow_text)

    def test_canonical_skill_references_use_dollar_and_resolve(self):
        canonical = set(load_json(REPO_ROOT / "config" / "distribution.json")["canonical_skills"])
        for path in (PLUGIN_ROOT / "skills").rglob("*.md"):
            text = path.read_text()
            self.assertEqual(extract_skill_references(text, "/"), set(), str(path))
            self.assertLessEqual(extract_skill_references(text, "$"), canonical, str(path))

    def test_canonical_runtime_has_no_unbundled_agent_reference(self):
        for path in (PLUGIN_ROOT / "skills").rglob("*.md"):
            self.assertNotIn("@kb-lead", map_outside_fences(path.read_text(), lambda value: value), str(path))

    def test_distribution_config_lists_exact_skill_set(self):
        config = load_json(REPO_ROOT / "config" / "distribution.json")
        self.assertEqual(set(config["canonical_skills"]), EXPECTED_SKILLS)
        self.assertEqual(len(config["authored_skills"]), 17)
        self.assertEqual(len(config["vendored_skills"]), 10)
        self.assertEqual(
            ["reflect", "structured-artifact"],
            config["claude"]["disable_model_invocation"],
        )
        self.assertEqual(
            config["zcode"],
            {
                "root": "cw",
                "manifest": ".zcode-plugin/plugin.json",
                "marketplace": "marketplace.json",
            },
        )

    def test_canonical_codex_skills_do_not_disable_model_invocation(self):
        for skill_name in sorted(EXPECTED_SKILLS):
            metadata, _ = split_frontmatter(
                (PLUGIN_ROOT / "skills" / skill_name / "SKILL.md").read_text()
            )
            self.assertIsNot(
                True,
                metadata.get("disable-model-invocation"),
                skill_name,
            )

    def test_frontmatter_parser_returns_metadata_and_body(self):
        metadata, body = split_frontmatter("---\nname: demo\ndescription: |\n  First line.\n  Second line.\n---\n\n# Demo\n")
        self.assertEqual(metadata, {"name": "demo", "description": "First line.\nSecond line.\n"})
        self.assertEqual(body, "\n# Demo\n")

    def test_frontmatter_parser_decodes_supported_yaml_string_scalars(self):
        single_metadata, _ = split_frontmatter(
            "---\n"
            "name: demo\n"
            "description: 'Use the author''s exact intent.'\n"
            "---\n"
        )
        double_metadata, _ = split_frontmatter(
            "---\n"
            "name: demo\n"
            "description: \"Use the author's exact intent.\\n\"\n"
            "---\n"
        )

        self.assertEqual("Use the author's exact intent.", single_metadata["description"])
        self.assertEqual("Use the author's exact intent.\n", double_metadata["description"])

    def test_frontmatter_parser_distinguishes_literal_and_folded_blocks(self):
        literal_metadata, _ = split_frontmatter(
            "---\n"
            "name: demo\n"
            "description: |\n"
            "  first line\n"
            "  second line\n"
            "---\n"
        )
        folded_metadata, _ = split_frontmatter(
            "---\n"
            "name: demo\n"
            "description: >\n"
            "  first line\n"
            "  second line\n"
            "\n"
            "  next paragraph\n"
            "---\n"
        )

        self.assertEqual("first line\nsecond line\n", literal_metadata["description"])
        self.assertEqual(
            "first line second line\nnext paragraph\n",
            folded_metadata["description"],
        )

    def test_frontmatter_parser_preserves_blanks_around_more_indented_folded_blocks(self):
        into_block, _ = split_frontmatter(
            "---\n"
            "name: demo\n"
            "description: >\n"
            "  a\n"
            "\n"
            "    b\n"
            "---\n"
        )
        out_of_block, _ = split_frontmatter(
            "---\n"
            "name: demo\n"
            "description: >\n"
            "  a\n"
            "    b\n"
            "\n"
            "  c\n"
            "---\n"
        )
        out_of_block_after_two_blanks, _ = split_frontmatter(
            "---\n"
            "name: demo\n"
            "description: >\n"
            "  a\n"
            "    b\n"
            "\n"
            "\n"
            "  c\n"
            "---\n"
        )

        self.assertEqual("a\n\n  b\n", into_block["description"])
        self.assertEqual("a\n  b\n\nc\n", out_of_block["description"])
        self.assertEqual(
            "a\n  b\n\n\nc\n",
            out_of_block_after_two_blanks["description"],
        )

    def test_frontmatter_parser_rejects_malformed_double_quoted_scalars(self):
        for value in ('"unterminated', '"complete" trailing'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                split_frontmatter(
                    f"---\nname: demo\ndescription: {value}\n---\nBody.\n"
                )

    def test_reference_parser_distinguishes_skills_from_code_urls_and_tags(self):
        text = "Use $story-memory, not /story-memory.\n```bash\necho $chapter\n```\nhttps://example.com/story-memory\n</hidden>\n"
        self.assertEqual(extract_skill_references(text, "$"), {"story-memory"})
        self.assertEqual(extract_skill_references(text, "/"), {"story-memory"})

    def test_slash_reference_parser_distinguishes_calls_from_non_call_contexts(self):
        cases = {
            "standalone call": ("Use /story-memory.\n", {"story-memory"}),
            "inline-code call": ("Use `/story-memory`.\n", {"story-memory"}),
            "fenced-code token": ("```text\n/story-memory\n```\n", set()),
            "indented backtick fence": ("   ```text\n/story-memory\n   ```\n", set()),
            "indented tilde fence": ("   ~~~text\n/story-memory\n   ~~~\n", set()),
            "visible HTML-wrapped call": ("Use <code>/story-memory</code>.\n", {"story-memory"}),
            "HTML attribute": ("Read <a href=\"/story-memory\">the guide</a>.\n", set()),
            "multiline HTML attribute with visible call": (
                "<a\n href=\"/story-memory\">/reader-sim</a>\n",
                {"reader-sim"},
            ),
            "closing HTML tag": ("Close with </story-memory>.\n", set()),
            "Markdown link destination": ("Read [the guide](/story-memory).\n", set()),
            "visible Markdown link label": ("Read [/story-memory](/guide.md).\n", {"story-memory"}),
            "Markdown reference destination": ("[guide]: /story-memory\n", set()),
            "multiline Markdown reference destination": ("[guide]:\n  /story-memory\n", set()),
            "URL query value": ("Open https://example.com/?next=/story-memory.\n", set()),
            "absolute Markdown path": ("Read `/vocab.md` first.\n", set()),
            "home-directory path": ("Read `~/story-memory` first.\n", set()),
            "angle-template path": ("Read `kb/<domain>/vocab.md`.\n", set()),
            "brace-template path": ("Read `kb/{domain}/vocab.md`.\n", set()),
            "bracket-template path": ("Read `kb/[domain]/vocab.md`.\n", set()),
        }
        for label, (text, expected) in cases.items():
            with self.subTest(label=label):
                self.assertEqual(extract_skill_references(text, "/"), expected)

    def test_reference_parser_obeys_commonmark_fence_boundaries(self):
        cases = {
            "mixed marker": "~~~~text\n```\n/story-memory $story-memory\n~~~~\n",
            "shorter closer": "````text\n```\n/story-memory $story-memory\n````\n",
            "unclosed fence": "```text\n/story-memory $story-memory\n",
            "indented mixed marker": "   ~~~~text\n```\n/story-memory $story-memory\n   ~~~~\n",
        }
        for label, text in cases.items():
            with self.subTest(label=label):
                self.assertEqual(extract_skill_references(text, "/"), set())
                self.assertEqual(extract_skill_references(text, "$"), set())

    def test_reference_parser_obeys_commonmark_container_fences(self):
        cases = {
            "block quote": (
                "> ```bash\n> /story-memory $story-memory\n> ```\n"
            ),
            "list continuation": (
                "- ```bash\n  /story-memory $story-memory\n  ```\n"
            ),
            "nested list": (
                "1. - ~~~~bash\n     ```\n     /story-memory $story-memory\n     ~~~~\n"
            ),
            "composed quote list": (
                "> - ```bash\n>   /story-memory $story-memory\n>   ```\n"
            ),
        }
        for label, text in cases.items():
            with self.subTest(label=label):
                self.assertEqual(extract_skill_references(text, "/"), set())
                self.assertEqual(extract_skill_references(text, "$"), set())

    def test_reference_parser_preserves_list_state_for_contained_fences(self):
        cases = {
            "blank line in open fence": (
                "- ```markdown\n"
                "  literal\n"
                "\n"
                "  [placeholder](kb/{domain}/vocab.md)\n"
                "  $chapter /story-memory @ghost\n"
                "  ```\n"
            ),
            "continuation after empty marker": (
                "-\n"
                "    ```markdown\n"
                "    [placeholder](kb/{domain}/vocab.md)\n"
                "    $chapter /story-memory @ghost\n"
                "    ```\n"
            ),
        }
        for label, text in cases.items():
            with self.subTest(label=label):
                self.assertEqual(extract_skill_references(text, "/"), set())
                self.assertEqual(extract_skill_references(text, "$"), set())
                self.assertEqual(
                    map_outside_fences(
                        text,
                        lambda visible: visible
                        .replace("kb/{domain}/vocab.md", "visible-link")
                        .replace("@ghost", "@visible")
                    ),
                    text,
                )

    def test_reference_parser_does_not_open_over_indented_list_fence(self):
        cases = {
            "excessive marker padding": (
                "-     ```markdown /story-memory\n"
                "  [placeholder](kb/{domain}/vocab.md)\n"
                "  $chapter @ghost\n"
            ),
            "excessive continuation indent": (
                "-\n"
                "      ```markdown /story-memory\n"
                "  [placeholder](kb/{domain}/vocab.md)\n"
                "  $chapter @ghost\n"
            ),
        }
        for label, text in cases.items():
            with self.subTest(label=label):
                self.assertEqual(
                    extract_skill_references(text, "/"),
                    {"story-memory"},
                )
                self.assertEqual(extract_skill_references(text, "$"), {"chapter"})
                visible = map_outside_fences(
                    text,
                    lambda segment: segment
                    .replace("```markdown", "not-a-fence")
                    .replace("@ghost", "@visible"),
                )
                self.assertIn("not-a-fence", visible)
                self.assertIn("@visible", visible)

    def test_backtick_in_info_string_is_not_a_fence_opener(self):
        text = "```bad`info\n/story-memory $story-memory\n```\n"
        self.assertEqual(extract_skill_references(text, "/"), {"story-memory"})
        self.assertEqual(extract_skill_references(text, "$"), {"story-memory"})


class ValidatorTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name).resolve()
        self.plugin = self.root / "plugins" / "creative-writing-skills"
        self.skills = self.plugin / "skills"
        self.skills.mkdir(parents=True)

        self.manifest = {
            "name": "creative-writing-skills",
            "version": "0.5.9",
            "description": "Creative writing skills.",
            "author": {"name": "InkyQuill"},
            "homepage": "https://github.com/InkyQuill/creative-writing-skills",
            "repository": "https://github.com/InkyQuill/creative-writing-skills",
            "license": "Apache-2.0",
            "skills": "./skills/",
            "interface": {
                "displayName": "Creative Writing Skills",
                "shortDescription": "Plan and write fiction.",
                "longDescription": "Creative-writing workflows for fiction.",
                "developerName": "InkyQuill",
                "category": "Productivity",
                "capabilities": ["Interactive", "Write"],
                "websiteURL": "https://github.com/InkyQuill/creative-writing-skills",
                "defaultPrompt": ["Use $creative-writing-muse."],
            },
        }
        self._write_json(self.plugin / ".codex-plugin" / "plugin.json", self.manifest)

        marketplace = {
            "name": "creative-writing-skills",
            "interface": {"displayName": "Creative Writing Skills"},
            "plugins": [{
                "name": "creative-writing-skills",
                "source": {
                    "source": "local",
                    "path": "./plugins/creative-writing-skills",
                },
                "policy": {
                    "installation": "AVAILABLE",
                    "authentication": "ON_INSTALL",
                },
                "category": "Productivity",
            }],
        }
        self._write_json(self.root / ".agents" / "plugins" / "marketplace.json", marketplace)

        authored = {
            "character-sim", "creative-research", "creative-writing-craft",
            "creative-writing-modes", "creative-writing-muse", "kb-management",
            "project-maintenance", "project-setup", "reader-sim", "shared-dao", "story-memory",
            "story-planning", "story-review", "targeted-editing",
            "world-creation", "writing-principles", "writing-staffing",
        }
        config = {
            "canonical_skills": sorted(EXPECTED_SKILLS),
            "authored_skills": sorted(authored),
            "vendored_skills": sorted(EXPECTED_SKILLS - authored),
            "workers": "skills/creative-writing-muse/resources/workers/registry.json",
            "claude": {
                "root": "cw",
                "marketplace": ".claude-plugin/marketplace.json",
                "disable_model_invocation": [
                    "reflect",
                    "structured-artifact",
                ],
            },
            "zcode": {
                "root": "cw",
                "manifest": ".zcode-plugin/plugin.json",
                "marketplace": "marketplace.json",
            },
        }
        self._write_json(self.root / "config" / "distribution.json", config)
        self._write_json(
            self.root / "config" / "structured-artifact-audit.json",
            {
                "schema_version": 1,
                "hash_algorithm": "sha256",
                "resources": [],
            },
        )

        for name in EXPECTED_SKILLS:
            skill = self.skills / name / "SKILL.md"
            skill.parent.mkdir(parents=True)
            skill.write_text(f"---\nname: {name}\ndescription: Demo.\n---\n{name}\n")

        workers_root = self.skills / "creative-writing-muse" / "resources" / "workers"
        workers = []
        for name in sorted(EXPECTED_WORKERS):
            prompt = workers_root / f"{name}.md"
            prompt.parent.mkdir(parents=True, exist_ok=True)
            prompt.write_text(f"# Function\n\n{name}\n")
            workers.append({
                "name": name,
                "description": f"{name} worker.",
                "prompt": prompt.name,
                "skills": sorted(EXPECTED_WORKER_CONFIG[name][1]),
                "access": EXPECTED_WORKER_CONFIG[name][0],
                "claude": {
                    "model": "inherit",
                    "background": name == "web-researcher",
                },
            })
        self._write_json(workers_root / "registry.json", {"workers": workers})

        self.claude_manifest = {
            key: self.manifest[key]
            for key in (
                "name", "version", "description", "author", "homepage",
                "repository", "license",
            )
        }
        self.write_claude_manifest()
        for name in EXPECTED_SKILLS:
            skill = self.root / "cw" / "skills" / name / "SKILL.md"
            skill.parent.mkdir(parents=True)
            invocation_metadata = (
                "disable-model-invocation: true\n"
                if name in {"reflect", "structured-artifact"}
                else ""
            )
            skill.write_text(
                f"---\nname: {name}\ndescription: Demo.\n"
                f"{invocation_metadata}---\n{name}\n"
            )
        canonical_structured = self.skills / "structured-artifact/SKILL.md"
        generated_structured = self.root / "cw/skills/structured-artifact/SKILL.md"
        generated_structured.write_text(
            transform_skill(
                canonical_structured.read_text(),
                "structured-artifact",
                EXPECTED_SKILLS,
                disable_model_invocation=True,
            )
        )
        self.approve_structured_artifact_resources("SKILL.md")
        agents = EXPECTED_WORKERS | {"muse"}
        for name in agents:
            agent = self.root / "cw" / "agents" / f"{name}.md"
            agent.parent.mkdir(parents=True, exist_ok=True)
            agent.write_text(f"---\nname: {name}\ndescription: Demo.\n---\n{name}\n")
        claude_marketplace = {
            "name": "cw",
            "owner": {"name": "InkyQuill"},
            "metadata": {
                "description": self.manifest["description"],
                "version": self.manifest["version"],
            },
            "plugins": [{
                "name": "creative-writing-skills",
                "description": self.manifest["description"],
                "source": "./cw",
            }],
        }
        self._write_json(self.root / ".claude-plugin" / "marketplace.json", claude_marketplace)
        self._write_json(
            self.root / "cw" / ".zcode-plugin" / "plugin.json",
            self.claude_manifest,
        )
        zcode_marketplace = {
            "name": "creative-writing-skills",
            "description": self.manifest["description"],
            "plugins": [{
                "name": "creative-writing-skills",
                "description": self.manifest["description"],
                "version": self.manifest["version"],
                "source": "./cw",
            }],
        }
        self._write_json(self.root / "marketplace.json", zcode_marketplace)

    def _write_json(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))

    def write_claude_manifest(self):
        self._write_json(self.root / "cw" / ".claude-plugin" / "plugin.json", self.claude_manifest)

    def approve_structured_artifact_resources(self, *relative_paths):
        resources = []
        root = self.skills / "structured-artifact"
        for relative_path in sorted(set(relative_paths) | {"SKILL.md"}):
            path = root / relative_path
            resources.append({
                "path": relative_path,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            })
        self._write_json(
            self.root / "config" / "structured-artifact-audit.json",
            {
                "schema_version": 1,
                "hash_algorithm": "sha256",
                "resources": resources,
            },
        )

    def test_validator_accepts_complete_fixture(self):
        self.assertEqual(validate(self.root), [])

    def test_validator_rejects_dangling_skill_reference(self):
        skill = self.skills / "demo" / "SKILL.md"
        skill.parent.mkdir()
        skill.write_text("---\nname: demo\ndescription: Demo.\n---\nUse $missing-skill.\n")
        self.assertIn("demo: dangling skill reference $missing-skill", validate(self.root))

    def test_validator_rejects_missing_relative_resource(self):
        skill = self.skills / "demo" / "SKILL.md"
        skill.parent.mkdir()
        skill.write_text("---\nname: demo\ndescription: Demo.\n---\nRead [guide](references/guide.md).\n")
        self.assertIn("demo: missing relative resource references/guide.md", validate(self.root))

    def test_validator_rejects_missing_backticked_instructional_resources(self):
        skill = self.skills / "story-memory" / "SKILL.md"
        skill.write_text(
            "---\nname: story-memory\ndescription: Demo.\n---\n"
            "Read `resources/missing.md` and `references/also-missing.py`.\n"
        )
        problems = validate(self.root)
        self.assertIn(
            "story-memory: missing relative resource resources/missing.md",
            problems,
        )
        self.assertIn(
            "story-memory: missing relative resource references/also-missing.py",
            problems,
        )

    def test_validator_ignores_backticked_commands_and_fenced_code_paths(self):
        skill = self.skills / "story-memory" / "SKILL.md"
        skill.write_text(
            "---\nname: story-memory\ndescription: Demo.\n---\n"
            "Run `python3 resources/missing.py --check`.\n"
            "```bash\npython3 resources/also-missing.py\n```\n"
        )
        problems = validate(self.root)
        self.assertNotIn(
            "story-memory: missing relative resource resources/missing.py",
            problems,
        )
        self.assertNotIn(
            "story-memory: missing relative resource resources/also-missing.py",
            problems,
        )

    def test_validator_resolves_backticked_resources_from_other_canonical_skills(self):
        resource = self.skills / "story-review" / "resources" / "guide.md"
        resource.parent.mkdir()
        resource.write_text("# Guide\n")
        skill = self.skills / "story-memory" / "SKILL.md"
        skill.write_text(
            "---\nname: story-memory\ndescription: Demo.\n---\n"
            "Use $story-review → `resources/guide.md`.\n"
        )
        self.assertNotIn(
            "story-memory: missing relative resource resources/guide.md",
            validate(self.root),
        )

    def test_validator_rejects_unscoped_sibling_resource_collision(self):
        resource = self.skills / "story-review" / "resources" / "guide.md"
        resource.parent.mkdir()
        resource.write_text("# Unrelated guide\n")
        skill = self.skills / "story-memory" / "SKILL.md"
        skill.write_text(
            "---\nname: story-memory\ndescription: Demo.\n---\n"
            "Read `resources/guide.md`.\n"
        )

        self.assertIn(
            "story-memory: missing relative resource resources/guide.md",
            validate(self.root),
        )

    def test_validator_requires_explicit_cross_skill_target_to_own_resource(self):
        wrong = self.skills / "story-planning" / "resources" / "guide.md"
        wrong.parent.mkdir()
        wrong.write_text("# Wrong sibling guide\n")
        skill = self.skills / "story-memory" / "SKILL.md"
        skill.write_text(
            "---\nname: story-memory\ndescription: Demo.\n---\n"
            "Use $story-review → `resources/guide.md`.\n"
        )

        self.assertIn(
            "story-memory: missing relative resource resources/guide.md",
            validate(self.root),
        )

    def test_validator_does_not_reuse_skill_reference_from_another_context(self):
        resource = self.skills / "story-review" / "resources" / "guide.md"
        resource.parent.mkdir()
        resource.write_text("# Review guide\n")
        skill = self.skills / "story-memory" / "SKILL.md"
        skill.write_text(
            "---\nname: story-memory\ndescription: Demo.\n---\n"
            "Use $story-review for critique.\n"
            "Read `resources/guide.md`.\n"
        )

        self.assertIn(
            "story-memory: missing relative resource resources/guide.md",
            validate(self.root),
        )

    def test_validator_does_not_reuse_skill_reference_from_prior_list_item(self):
        resource = self.skills / "story-review" / "resources" / "guide.md"
        resource.parent.mkdir()
        resource.write_text("# Review guide\n")
        skill = self.skills / "story-memory" / "SKILL.md"
        skill.write_text(
            "---\nname: story-memory\ndescription: Demo.\n---\n"
            "- Use $story-review for critique.\n"
            "- Read `resources/guide.md`.\n"
        )

        self.assertIn(
            "story-memory: missing relative resource resources/guide.md",
            validate(self.root),
        )

    def test_validator_separates_nested_and_blockquoted_list_contexts(self):
        resource = self.skills / "story-review" / "resources" / "guide.md"
        resource.parent.mkdir()
        resource.write_text("# Review guide\n")
        skill = self.skills / "story-memory" / "SKILL.md"
        cases = (
            "- Use $story-review for critique.\n"
            "    - Read `resources/guide.md`.\n",
            "> - Use $story-review for critique.\n"
            "> - Read `resources/guide.md`.\n",
        )

        for body in cases:
            with self.subTest(body=body):
                skill.write_text(
                    "---\nname: story-memory\ndescription: Demo.\n---\n" + body
                )
                self.assertIn(
                    "story-memory: missing relative resource resources/guide.md",
                    validate(self.root),
                )

    def test_validator_rejects_explicit_cross_skill_resource_escape(self):
        escaped = self.skills / "escape.md"
        escaped.write_text("outside skill root\n")
        skill = self.skills / "story-memory" / "SKILL.md"
        skill.write_text(
            "---\nname: story-memory\ndescription: Demo.\n---\n"
            "Use $story-review → `resources/../../escape.md`.\n"
        )

        self.assertIn(
            "story-memory: missing relative resource resources/../../escape.md",
            validate(self.root),
        )

    def test_validator_reports_whitespace_only_resource_target(self):
        skill = self.skills / "story-memory" / "SKILL.md"
        skill.write_text(
            "---\nname: story-memory\ndescription: Demo.\n---\n"
            "Read [blank](   ).\n"
        )
        self.assertIn("story-memory: missing relative resource <empty>", validate(self.root))

    def test_validator_rejects_manifest_version_mismatch(self):
        self.claude_manifest["version"] = "0.0.0"
        self.write_claude_manifest()
        self.assertIn(
            "cw plugin version 0.0.0 != canonical version "
            f"{self.manifest['version']}",
            validate(self.root),
        )

    def test_validator_rejects_zcode_marketplace_version_drift(self):
        path = self.root / "marketplace.json"
        marketplace = json.loads(path.read_text())
        marketplace["plugins"][0]["version"] = "0.0.0"
        self._write_json(path, marketplace)
        self.assertIn(
            "ZCode marketplace version 0.0.0 != canonical version "
            f"{self.manifest['version']}",
            validate(self.root),
        )

    def test_validator_rejects_zcode_marketplace_source_drift(self):
        path = self.root / "marketplace.json"
        marketplace = json.loads(path.read_text())
        marketplace["plugins"][0]["source"] = "./plugins/creative-writing-skills"
        self._write_json(path, marketplace)
        self.assertIn(
            "ZCode marketplace plugin source must be ./cw",
            validate(self.root),
        )

    def test_validator_rejects_zcode_manifest_version_drift(self):
        path = self.root / "cw" / ".zcode-plugin" / "plugin.json"
        manifest = json.loads(path.read_text())
        manifest["version"] = "0.0.0"
        self._write_json(path, manifest)
        self.assertIn(
            "cw ZCode manifest version does not match canonical manifest",
            validate(self.root),
        )

    def test_validator_rejects_missing_zcode_marketplace(self):
        (self.root / "marketplace.json").unlink()
        self.assertTrue(
            any(
                problem.startswith("missing ZCode marketplace")
                for problem in validate(self.root)
            )
        )

    def test_validator_rejects_non_canonical_zcode_config_paths(self):
        path = self.root / "config" / "distribution.json"
        config = json.loads(path.read_text())
        config["zcode"]["marketplace"] = "zcode-marketplace.json"
        self._write_json(path, config)
        self.assertIn(
            "distribution config ZCode paths are not canonical",
            validate(self.root, canonical_only=True),
        )

    def test_validator_rejects_symlinked_zcode_control_paths(self):
        marketplace = self.root / "marketplace.json"
        marketplace_target = self.root / "external-zcode-marketplace.json"
        marketplace.rename(marketplace_target)
        marketplace.symlink_to(marketplace_target)
        self.assertIn("ZCode marketplace must not traverse symlinks", validate(self.root))

        manifest = self.root / "cw" / ".zcode-plugin" / "plugin.json"
        manifest_target = manifest.parent / "manifest-target.json"
        manifest.rename(manifest_target)
        manifest.symlink_to(manifest_target.name)
        self.assertIn("cw ZCode manifest must not traverse symlinks", validate(self.root))

    def test_validator_rejects_zcode_path_through_symlink_loop(self):
        (self.root / "zloop").symlink_to("zloop")
        config_path = self.root / "config" / "distribution.json"
        config = json.loads(config_path.read_text())
        config["zcode"]["marketplace"] = "zloop/marketplace.json"
        self._write_json(config_path, config)
        self.assertIn(
            "ZCode marketplace must not traverse symlinks",
            validate(self.root),
        )

    def test_validator_rejects_true_disable_model_invocation_in_codex(self):
        skill = self.skills / "story-memory" / "SKILL.md"
        skill.write_text(
            "---\n"
            "name: story-memory\n"
            "description: Demo.\n"
            "disable-model-invocation: true\n"
            "---\n"
            "Story memory.\n"
        )

        self.assertIn(
            "story-memory: disable-model-invocation true is Claude-only",
            validate(self.root, canonical_only=True),
        )

    def test_validator_rejects_unlisted_executable_resource(self):
        resource = (
            self.skills / "structured-artifact" / "resources" / "unsafe.html"
        )
        resource.parent.mkdir(exist_ok=True)
        resource.write_text(
            '<div id="output"></div><script>output.innerHTML = userHtml;</script>\n'
        )

        self.assertIn(
            "structured-artifact audit: unlisted resource resources/unsafe.html",
            validate(self.root, canonical_only=True),
        )

    def test_validator_rejects_unlisted_claude_executable_resource(self):
        resource = (
            self.root / "cw/skills/structured-artifact/resources/unsafe.html"
        )
        resource.parent.mkdir(exist_ok=True)
        resource.write_text(
            '<script>document /* gap */ .write?.(userHtml)</script>\n'
        )

        self.assertIn(
            "cw/skills/structured-artifact audit: unlisted resource "
            "resources/unsafe.html",
            validate(self.root),
        )

    def test_validator_discovers_executable_bearing_declared_text_suffixes(self):
        resources = self.skills / "structured-artifact/resources"
        resources.mkdir(exist_ok=True)
        cases = {
            "component.tsx": "export const Demo = () => <button>Go</button>;\n",
            "embedded.txt": "<script>run()</script>\n",
            "vector.xml": '<svg xmlns="http://www.w3.org/2000/svg"></svg>\n',
            "fenced.rst": "```javascript\nrun();\n```\n",
        }
        for name, source in cases.items():
            with self.subTest(name=name):
                path = resources / name
                path.write_text(source)
                self.assertIn(
                    "structured-artifact audit: unlisted resource "
                    f"resources/{name}",
                    validate(self.root, canonical_only=True),
                )
                path.unlink()

    def test_validator_audits_every_structured_artifact_file_without_classifying_it(self):
        resources = self.skills / "structured-artifact/resources"
        nested = resources / "nested"
        nested.mkdir(parents=True)
        cases = {
            "unsafe.xhtml": "<script>run()</script>\n",
            "component.mdx": "export const Demo = () => <button />;\n",
            "widget.vue": "<script>run()</script>\n",
            "runner": "document.write?.(html);\n",
            "nested/quoted.md": "> ```js\n> run();\n> ```\n",
            "nested/list.md": "- ```html\n  <script>run()</script>\n  ```\n",
            "nested/pandoc.md": "```{.js}\nrun();\n```\n",
            "nested/node.md": "```node\nrun();\n```\n",
        }
        for relative, source in cases.items():
            with self.subTest(relative=relative):
                path = resources / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(source)
                self.assertIn(
                    "structured-artifact audit: unlisted resource "
                    f"resources/{relative}",
                    validate(self.root, canonical_only=True),
                )
                path.unlink()

    def test_validator_rejects_differing_claude_bytes_for_arbitrary_suffix(self):
        canonical = self.skills / "structured-artifact/resources/example.xhtml"
        generated = self.root / "cw/skills/structured-artifact/resources/example.xhtml"
        canonical.parent.mkdir(exist_ok=True)
        generated.parent.mkdir(exist_ok=True)
        canonical.write_text("<p>approved</p>\n")
        generated.write_text("<p>different</p>\n")
        self.approve_structured_artifact_resources("resources/example.xhtml")

        self.assertIn(
            "cw/skills/structured-artifact audit: SHA-256 mismatch for "
            "resources/example.xhtml",
            validate(self.root),
        )

    def test_validator_rejects_dot_audit_path_without_crashing(self):
        self._write_json(
            self.root / "config/structured-artifact-audit.json",
            {
                "schema_version": 1,
                "hash_algorithm": "sha256",
                "resources": [{"path": ".", "sha256": "0" * 64}],
            },
        )

        self.assertIn(
            "structured-artifact audit path is not a safe relative path: .",
            validate(self.root, canonical_only=True),
        )

    def test_validator_matches_generator_crlf_markdown_semantics(self):
        canonical = self.skills / "structured-artifact/resources/crlf.md"
        generated = self.root / "cw/skills/structured-artifact/resources/crlf.md"
        canonical.parent.mkdir(exist_ok=True)
        generated.parent.mkdir(exist_ok=True)
        canonical.write_bytes(
            b"Use $story-memory.\r\n\r\n```js\r\nroot.replaceChildren(node);\r\n```\r\n"
        )
        generated.write_text(
            "Use /story-memory.\n\n```js\nroot.replaceChildren(node);\n```\n"
        )
        self.approve_structured_artifact_resources("resources/crlf.md")

        self.assertFalse(
            [problem for problem in validate(self.root) if "crlf.md" in problem]
        )

    def test_validator_reports_audit_subtree_traversal_failure(self):
        resources = self.skills / "structured-artifact/resources"
        blocked = resources / "blocked"
        blocked.mkdir(parents=True)
        hidden = blocked / "hidden.xhtml"
        hidden.write_text("<script>run()</script>\n")
        real_open = os.open
        real_scandir = os.scandir
        blocked_fd = None

        def record_subtree(path, flags, *args, dir_fd=None, **kwargs):
            nonlocal blocked_fd
            descriptor = real_open(path, flags, *args, dir_fd=dir_fd, **kwargs)
            if path == "blocked" and dir_fd is not None:
                blocked_fd = descriptor
            return descriptor

        def fail_subtree(descriptor):
            if descriptor == blocked_fd:
                raise PermissionError("simulated subtree failure")
            return real_scandir(descriptor)

        with (
            mock.patch("scripts.validate_distribution.os.open", record_subtree),
            mock.patch("scripts.validate_distribution.os.scandir", fail_subtree),
        ):
            problems = validate(self.root, canonical_only=True)
        self.assertTrue(
            any("simulated subtree failure" in problem for problem in problems),
            problems,
        )

    def test_validator_reports_audit_file_read_failure(self):
        resources = self.skills / "structured-artifact/resources"
        resources.mkdir(exist_ok=True)
        approved = resources / "approved.js"
        approved.write_text("safe();\n")
        generated = self.root / "cw/skills/structured-artifact/resources/approved.js"
        generated.parent.mkdir(exist_ok=True)
        generated.write_text("safe();\n")
        self.approve_structured_artifact_resources("resources/approved.js")
        real_open = os.open
        real_read = os.read
        approved_fd = None
        failed = False

        def record_approved(path, flags, *args, dir_fd=None, **kwargs):
            nonlocal approved_fd
            descriptor = real_open(path, flags, *args, dir_fd=dir_fd, **kwargs)
            if path == "approved.js" and dir_fd is not None and approved_fd is None:
                approved_fd = descriptor
            return descriptor

        def fail_approved(descriptor, size):
            nonlocal failed
            if descriptor == approved_fd and not failed:
                failed = True
                raise PermissionError("simulated audit read failure")
            return real_read(descriptor, size)

        with (
            mock.patch("scripts.validate_distribution.os.open", record_approved),
            mock.patch("scripts.validate_distribution.os.read", fail_approved),
        ):
            problems = validate(self.root)
        self.assertTrue(
            any("simulated audit read failure" in problem for problem in problems),
            problems,
        )

    def test_validator_reports_audit_stat_failure(self):
        target = self.skills / "structured-artifact/resources/stat-fail.bin"
        target.parent.mkdir(exist_ok=True)
        target.write_bytes(b"review me")
        real_open = os.open
        real_fstat = os.fstat
        target_fd = None
        failed = False

        def record_target(path, flags, *args, dir_fd=None, **kwargs):
            nonlocal target_fd
            descriptor = real_open(path, flags, *args, dir_fd=dir_fd, **kwargs)
            if path == "stat-fail.bin" and dir_fd is not None:
                target_fd = descriptor
            return descriptor

        def fail_target(descriptor):
            nonlocal failed
            if descriptor == target_fd and not failed:
                failed = True
                raise PermissionError("simulated stat failure")
            return real_fstat(descriptor)

        with (
            mock.patch("scripts.validate_distribution.os.open", record_target),
            mock.patch("scripts.validate_distribution.os.fstat", fail_target),
        ):
            problems = validate(self.root, canonical_only=True)
        self.assertIn(
            "structured-artifact audit: cannot stat resource "
            "resources/stat-fail.bin: simulated stat failure",
            problems,
        )

    def test_validator_rejects_canonical_leaf_symlink_race(self):
        resource = self.skills / "structured-artifact/resources/race.bin"
        resource.parent.mkdir(exist_ok=True)
        resource.write_bytes(b"approved")
        self.approve_structured_artifact_resources("resources/race.bin")
        external = self.root / "external.bin"
        external.write_bytes(b"external")
        backup = resource.with_name("race-backup.bin")
        real_open = os.open
        raced = False

        def replace_leaf(path, flags, *args, dir_fd=None, **kwargs):
            nonlocal raced
            if path == "race.bin" and dir_fd is not None and not raced:
                raced = True
                resource.rename(backup)
                resource.symlink_to(external)
            return real_open(path, flags, *args, dir_fd=dir_fd, **kwargs)

        with mock.patch(
            "scripts.validate_distribution.os.open",
            side_effect=replace_leaf,
        ):
            problems = validate(self.root, canonical_only=True)
        self.assertTrue(
            any(
                "structured-artifact audit: cannot open resource resources/race.bin"
                in problem
                for problem in problems
            ),
            problems,
        )

    def test_validator_rejects_claude_leaf_symlink_race(self):
        canonical = self.skills / "structured-artifact/resources/race.bin"
        generated = self.root / "cw/skills/structured-artifact/resources/race.bin"
        canonical.parent.mkdir(exist_ok=True)
        generated.parent.mkdir(exist_ok=True)
        canonical.write_bytes(b"approved")
        generated.write_bytes(b"approved")
        self.approve_structured_artifact_resources("resources/race.bin")
        external = self.root / "external.bin"
        external.write_bytes(b"external")
        backup = generated.with_name("race-backup.bin")
        real_open = os.open
        race_opens = 0

        def replace_generated_leaf(path, flags, *args, dir_fd=None, **kwargs):
            nonlocal race_opens
            if path == "race.bin" and dir_fd is not None:
                race_opens += 1
                if race_opens == 2:
                    generated.rename(backup)
                    generated.symlink_to(external)
            return real_open(path, flags, *args, dir_fd=dir_fd, **kwargs)

        with mock.patch(
            "scripts.validate_distribution.os.open",
            side_effect=replace_generated_leaf,
        ):
            problems = validate(self.root)
        self.assertTrue(
            any(
                "cw/skills/structured-artifact audit: cannot open resource "
                "resources/race.bin" in problem
                for problem in problems
            ),
            problems,
        )

    def test_validator_rejects_invalid_audit_schema(self):
        audit = self.root / "config/structured-artifact-audit.json"
        self._write_json(audit, {
            "schema_version": 2,
            "hash_algorithm": "sha512",
            "resources": "automatic",
            "extra": True,
        })

        problems = validate(self.root, canonical_only=True)
        self.assertIn("structured-artifact audit fields do not match schema", problems)
        self.assertIn("structured-artifact audit schema_version must be 1", problems)
        self.assertIn("structured-artifact audit hash_algorithm must be sha256", problems)
        self.assertIn("structured-artifact audit resources must be a list", problems)

    def test_validator_rejects_canonical_executable_resource_mutations_by_hash(self):
        resource = (
            self.skills / "structured-artifact" / "resources" / "audited.md"
        )
        resource.parent.mkdir(exist_ok=True)
        resource.write_text("```js\nroot.replaceChildren(node);\n```\n")
        self.approve_structured_artifact_resources("resources/audited.md")
        mutations = {
            "logical assignment": "```js\nnode.innerHTML ||= html;\n```\n",
            "optional call": "```js\ndocument.write?.(html);\n```\n",
            "computed optional call": "```js\ndocument['writeln']?.(html);\n```\n",
            "comment trivia": "```js\ndocument /* gap */ .write(html);\n```\n",
            "quoted Mermaid key": (
                "```mermaid\n%%{init: {'securityLevel': 'loose'}}%%\ngraph TD\n```\n"
            ),
        }
        expected = (
            "structured-artifact audit: SHA-256 mismatch for resources/audited.md"
        )
        for label, source in mutations.items():
            with self.subTest(label=label):
                resource.write_text(source)
                self.assertIn(expected, validate(self.root, canonical_only=True))

    def test_validator_rejects_claude_executable_resource_mutations_by_hash(self):
        canonical = self.skills / "structured-artifact/resources/audited.md"
        generated = self.root / "cw/skills/structured-artifact/resources/audited.md"
        canonical.parent.mkdir(exist_ok=True)
        generated.parent.mkdir(exist_ok=True)
        approved = "```js\nroot.replaceChildren(node);\n```\n"
        canonical.write_text(approved)
        generated.write_text(approved)
        self.approve_structured_artifact_resources("resources/audited.md")
        mutations = (
            "```js\nnode.innerHTML ||= html;\n```\n",
            "```js\ndocument.write?.(html);\n```\n",
            "```js\ndocument[/* gap */ 'writeln']?.(html);\n```\n",
            "```mermaid\n%%{init: {\"securityLevel\": \"loose\"}}%%\ngraph TD\n```\n",
        )
        expected = (
            "cw/skills/structured-artifact audit: SHA-256 mismatch for "
            "resources/audited.md"
        )
        for source in mutations:
            with self.subTest(source=source):
                generated.write_text(source)
                self.assertIn(expected, validate(self.root))

    def test_validator_accepts_approved_strings_comments_prose_and_safe_dom(self):
        source = (
            "# Reviewed examples\n\n"
            "Prose may say `node.innerHTML = html` without executing it.\n\n"
            "```js\n"
            "const warning = 'never use document.write(html)';\n"
            "// document.write(html) is prohibited.\n"
            "/* node.insertAdjacentHTML('beforeend', html) is prohibited. */\n"
            "const button = document?.createElement('button');\n"
            "button.textContent = warning;\n"
            "button.addEventListener('click', render);\n"
            "root.replaceChildren(button);\n"
            "```\n"
        )
        canonical = self.skills / "structured-artifact/resources/reviewed.md"
        generated = self.root / "cw/skills/structured-artifact/resources/reviewed.md"
        canonical.parent.mkdir(exist_ok=True)
        generated.parent.mkdir(exist_ok=True)
        canonical.write_text(source)
        generated.write_text(source)
        self.approve_structured_artifact_resources("resources/reviewed.md")

        self.assertFalse(
            [problem for problem in validate(self.root) if "reviewed.md" in problem]
        )

    def test_validator_rejects_missing_and_unsafe_audit_entries(self):
        audit_path = self.root / "config/structured-artifact-audit.json"
        cases = {
            "missing": {
                "path": "resources/missing.js",
                "sha256": "0" * 64,
            },
            "escape": {
                "path": "../outside.js",
                "sha256": "0" * 64,
            },
        }
        for label, entry in cases.items():
            with self.subTest(label=label):
                self._write_json(audit_path, {
                    "schema_version": 1,
                    "hash_algorithm": "sha256",
                    "resources": [entry],
                })
                problems = validate(self.root, canonical_only=True)
                if label == "missing":
                    self.assertIn(
                        "structured-artifact audit: listed resource is missing "
                        "resources/missing.js",
                        problems,
                    )
                else:
                    self.assertIn(
                        "structured-artifact audit path is not a safe relative path: "
                        "../outside.js",
                        problems,
                    )

    def test_validator_rejects_duplicate_unsorted_and_symlinked_audit_entries(self):
        resources = self.skills / "structured-artifact/resources"
        resources.mkdir(exist_ok=True)
        first = resources / "a.js"
        second = resources / "b.js"
        first.write_text("a();\n")
        second.write_text("b();\n")
        digest = hashlib.sha256(first.read_bytes()).hexdigest()
        audit = self.root / "config/structured-artifact-audit.json"
        self._write_json(audit, {
            "schema_version": 1,
            "hash_algorithm": "sha256",
            "resources": [
                {"path": "resources/b.js", "sha256": hashlib.sha256(second.read_bytes()).hexdigest()},
                {"path": "resources/a.js", "sha256": digest},
                {"path": "resources/a.js", "sha256": digest},
            ],
        })
        problems = validate(self.root, canonical_only=True)
        self.assertIn("structured-artifact audit resources must be sorted by path", problems)
        self.assertIn("structured-artifact audit contains duplicate path resources/a.js", problems)

        target = self.root / "outside.js"
        target.write_text("a();\n")
        first.unlink()
        first.symlink_to(target)
        self._write_json(audit, {
            "schema_version": 1,
            "hash_algorithm": "sha256",
            "resources": [{"path": "resources/a.js", "sha256": digest}],
        })
        self.assertTrue(
            any(
                problem.startswith(
                    "structured-artifact audit: cannot open resource resources/a.js"
                )
                for problem in validate(self.root, canonical_only=True)
            )
        )

    def test_validator_rejects_symlinked_audit_path_ancestor_without_following_it(self):
        skill_root = self.skills / "structured-artifact"
        outside = self.root / "outside"
        outside.mkdir()
        target = outside / "audited.js"
        target.write_text("safe();\n")
        (skill_root / "linked").symlink_to(outside, target_is_directory=True)
        self._write_json(
            self.root / "config/structured-artifact-audit.json",
            {
                "schema_version": 1,
                "hash_algorithm": "sha256",
                "resources": [{
                    "path": "linked/audited.js",
                    "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                }],
            },
        )

        problems = validate(self.root, canonical_only=True)
        self.assertIn(
            "structured-artifact: runtime resource linked must not be a symlink",
            problems,
        )
        self.assertTrue(
            any(
                problem.startswith(
                    "structured-artifact audit: cannot open resource linked"
                )
                for problem in problems
            )
        )

    def test_validator_rejects_invalid_claude_invocation_policy(self):
        cases = {
            "not a list": (
                "reflect",
                "distribution config Claude disable_model_invocation must be a list of skill names",
            ),
            "duplicates": (
                ["reflect", "reflect"],
                "distribution config Claude disable_model_invocation contains duplicates",
            ),
            "not sorted": (
                ["structured-artifact", "reflect"],
                "distribution config Claude disable_model_invocation must be sorted",
            ),
            "not canonical": (
                ["not-a-skill"],
                "distribution config Claude disable_model_invocation is not a subset of canonical skills: not-a-skill",
            ),
        }
        path = self.root / "config/distribution.json"
        original = path.read_text()
        for label, (value, expected) in cases.items():
            with self.subTest(label=label):
                config = json.loads(original)
                config["claude"]["disable_model_invocation"] = value
                self._write_json(path, config)
                self.assertIn(expected, validate(self.root, canonical_only=True))
        path.write_text(original)

    def test_claude_validation_keeps_safe_invocation_policy_when_config_is_invalid(self):
        config_path = self.root / "config/distribution.json"
        config = json.loads(config_path.read_text())
        config["claude"]["disable_model_invocation"] = ["not-a-skill"]
        self._write_json(config_path, config)
        reflect = self.root / "cw/skills/reflect/SKILL.md"
        reflect.write_text(
            reflect.read_text().replace("disable-model-invocation: true\n", "")
        )

        problems = validate(self.root)

        self.assertIn(
            "distribution config Claude disable_model_invocation is not a subset "
            "of canonical skills: not-a-skill",
            problems,
        )
        self.assertIn(
            "cw/skills/reflect/SKILL.md: disable-model-invocation must be true",
            problems,
        )

    def test_validator_rejects_claude_style_reference_in_codex(self):
        skill = self.skills / "demo" / "SKILL.md"
        skill.parent.mkdir()
        skill.write_text("---\nname: demo\ndescription: Demo.\n---\nUse /story-memory.\n")
        self.assertIn("demo: Claude-style reference /story-memory in canonical Codex skill", validate(self.root))

    def test_validator_ignores_shell_variables_and_urls(self):
        skill = self.skills / "demo" / "SKILL.md"
        skill.parent.mkdir()
        skill.write_text(
            "---\nname: demo\ndescription: Demo.\n---\n"
            "```bash\necho $chapter\n```\n"
            "https://example.com/story-memory/$url_variable?next=/story-memory\n"
            "Read [remote](https://example.com/$remote).\n"
        )
        problems = validate(self.root)
        self.assertNotIn("demo: dangling skill reference $chapter", problems)
        self.assertNotIn("demo: dangling skill reference $url", problems)
        self.assertNotIn("demo: dangling skill reference $remote", problems)
        self.assertNotIn("demo: Claude-style reference /story-memory in canonical Codex skill", problems)

    def test_validator_checks_real_links_inside_fences(self):
        skill = self.skills / "story-memory" / "SKILL.md"
        skill.write_text(
            "---\nname: story-memory\ndescription: Demo.\n---\n"
            "```markdown\n[guide](references/missing.md)\n```\n"
        )
        self.assertIn(
            "story-memory: missing relative resource references/missing.md",
            validate(self.root),
        )

    def test_validator_ignores_only_fenced_placeholder_links(self):
        skill = self.skills / "story-memory" / "SKILL.md"
        skill.write_text(
            "---\nname: story-memory\ndescription: Demo.\n---\n"
            "```markdown\n[brace](kb/{domain}/vocab.md)\n[angle](kb/<domain>/vocab.md)\n```\n"
        )
        problems = validate(self.root)
        self.assertNotIn(
            "story-memory: missing relative resource kb/{domain}/vocab.md",
            problems,
        )
        self.assertNotIn(
            "story-memory: missing relative resource kb/<domain>/vocab.md",
            problems,
        )

    def test_validator_keeps_mixed_and_shorter_fences_open(self):
        skill = self.skills / "story-memory" / "SKILL.md"
        skill.write_text(
            "---\nname: story-memory\ndescription: Demo.\n---\n"
            "~~~~markdown\n"
            "```\n"
            "[placeholder](kb/{domain}/vocab.md)\n"
            "$chapter\n"
            "~~~~\n"
            "````markdown\n"
            "```\n"
            "[other](kb/<domain>/vocab.md)\n"
            "$scene\n"
            "````\n"
        )
        problems = validate(self.root)
        for unexpected in (
            "story-memory: missing relative resource kb/{domain}/vocab.md",
            "story-memory: missing relative resource kb/<domain>/vocab.md",
            "story-memory: dangling skill reference $chapter",
            "story-memory: dangling skill reference $scene",
        ):
            self.assertNotIn(unexpected, problems)

    def test_validator_ignores_placeholders_inside_container_fences(self):
        skill = self.skills / "story-memory" / "SKILL.md"
        skill.write_text(
            "---\nname: story-memory\ndescription: Demo.\n---\n"
            "> - ````markdown\n"
            ">   ```\n"
            ">   [placeholder](kb/{domain}/vocab.md)\n"
            ">   $chapter\n"
            ">   ````\n"
        )
        problems = validate(self.root)
        self.assertNotIn(
            "story-memory: missing relative resource kb/{domain}/vocab.md",
            problems,
        )
        self.assertNotIn("story-memory: dangling skill reference $chapter", problems)

    def test_validator_ignores_references_in_list_state_fences(self):
        cases = {
            "blank line in open fence": (
                "- ```markdown\n"
                "  literal\n"
                "\n"
                "  [placeholder](kb/{domain}/vocab.md)\n"
                "  $chapter /story-memory @ghost\n"
                "  ```\n"
            ),
            "continuation after empty marker": (
                "-\n"
                "    ```markdown\n"
                "    [placeholder](kb/{domain}/vocab.md)\n"
                "    $chapter /story-memory @ghost\n"
                "    ```\n"
            ),
        }
        skill = self.skills / "story-memory" / "SKILL.md"
        for label, body in cases.items():
            with self.subTest(label=label):
                skill.write_text(
                    "---\nname: story-memory\ndescription: Demo.\n---\n" + body
                )
                problems = validate(self.root)
                for unexpected in (
                    "story-memory: missing relative resource kb/{domain}/vocab.md",
                    "story-memory: dangling skill reference $chapter",
                    "story-memory: Claude-style reference /story-memory in canonical Codex skill",
                    "story-memory: dangling worker reference @ghost",
                ):
                    self.assertNotIn(unexpected, problems)

    def test_validator_treats_invalid_backtick_info_as_visible_content(self):
        skill = self.skills / "story-memory" / "SKILL.md"
        skill.write_text(
            "---\nname: story-memory\ndescription: Demo.\n---\n"
            "```bad`info\n"
            "[guide](references/missing.md)\n"
            "$missing-skill\n"
            "```\n"
        )
        problems = validate(self.root)
        self.assertIn(
            "story-memory: missing relative resource references/missing.md",
            problems,
        )
        self.assertIn("story-memory: dangling skill reference $missing-skill", problems)

    def test_validator_rejects_placeholder_links_outside_fences(self):
        skill = self.skills / "story-memory" / "SKILL.md"
        skill.write_text(
            "---\nname: story-memory\ndescription: Demo.\n---\n"
            "Read [guide](kb/{domain}/vocab.md).\n"
        )
        self.assertIn(
            "story-memory: missing relative resource kb/{domain}/vocab.md",
            validate(self.root),
        )

    def test_validator_accepts_existing_relative_resource_with_fragment(self):
        skill_root = self.skills / "story-memory"
        resource = skill_root / "references" / "guide.md"
        resource.parent.mkdir()
        resource.write_text("# Guide\n")
        (skill_root / "SKILL.md").write_text(
            "---\nname: story-memory\ndescription: Demo.\n---\n"
            "Read [guide](references/guide.md#details).\n"
        )
        self.assertNotIn(
            "story-memory: missing relative resource references/guide.md#details",
            validate(self.root),
        )

    def test_validator_rejects_non_semantic_canonical_version(self):
        self.manifest["version"] = "v0.5.9"
        self._write_json(self.plugin / ".codex-plugin" / "plugin.json", self.manifest)
        self.assertIn("canonical plugin version v0.5.9 is not strict semver", validate(self.root))

    def test_validator_rejects_marketplace_policy_drift(self):
        path = self.root / ".agents" / "plugins" / "marketplace.json"
        marketplace = json.loads(path.read_text())
        marketplace["plugins"][0]["policy"]["authentication"] = "NONE"
        self._write_json(path, marketplace)
        self.assertIn("marketplace authentication policy NONE != ON_INSTALL", validate(self.root))

    def test_validator_rejects_frontmatter_name_mismatch(self):
        skill = self.skills / "story-memory" / "SKILL.md"
        skill.write_text("---\nname: memories\ndescription: Demo.\n---\nBody.\n")
        self.assertIn("story-memory: frontmatter name memories != directory name", validate(self.root))

    def test_validator_rejects_unresolved_worker_skill(self):
        path = self.skills / "creative-writing-muse" / "resources" / "workers" / "registry.json"
        registry = json.loads(path.read_text())
        registry["workers"][0]["skills"] = ["missing-skill"]
        self._write_json(path, registry)
        name = registry["workers"][0]["name"]
        self.assertIn(f"worker {name}: dangling skill mapping missing-skill", validate(self.root))

    def test_validator_rejects_wrong_resolved_worker_skill_mapping(self):
        path = self.skills / "creative-writing-muse" / "resources" / "workers" / "registry.json"
        registry = json.loads(path.read_text())
        critic = next(item for item in registry["workers"] if item["name"] == "critic")
        critic["skills"] = ["creative-research"]
        self._write_json(path, registry)
        self.assertIn(
            "worker critic: skill mapping does not match canonical registry",
            validate(self.root),
        )

    def test_validator_rejects_review_worker_with_write_access(self):
        path = self.skills / "creative-writing-muse" / "resources" / "workers" / "registry.json"
        registry = json.loads(path.read_text())
        critic = next(item for item in registry["workers"] if item["name"] == "critic")
        critic["access"] = "workspace-write"
        self._write_json(path, registry)
        self.assertIn("worker critic: review role must be read-only", validate(self.root))

    def test_validator_rejects_meridian_vocabulary_outside_fences(self):
        skill = self.skills / "story-memory" / "SKILL.md"
        skill.write_text(
            "---\nname: story-memory\ndescription: Demo.\n---\n"
            "Run meridian mars check.\n"
        )
        self.assertIn("story-memory: forbidden canonical runtime vocabulary meridian mars", validate(self.root))

    def test_validator_rejects_claude_instruction_filename_in_canonical_runtime(self):
        skill = self.skills / "story-memory" / "SKILL.md"
        skill.write_text(
            "---\nname: story-memory\ndescription: Demo.\n---\n"
            "Read `CLAUDE.md` before continuing.\n"
        )
        self.assertIn(
            "story-memory: Claude-only vocabulary CLAUDE.md",
            validate(self.root),
        )

    def test_validator_scans_fences_and_non_markdown_runtime_vocabulary(self):
        skill_root = self.skills / "story-memory"
        (skill_root / "SKILL.md").write_text(
            "---\nname: story-memory\ndescription: Demo.\n---\n"
            "```bash\nmArS add package\n```\n"
        )
        (skill_root / "tool.py").write_text("root = 'MERIDIAN_TASK_DIR'\n")
        (skill_root / "run.sh").write_text("meridian publish\n")
        problems = validate(self.root)
        self.assertIn("story-memory: forbidden canonical runtime vocabulary mArS", problems)
        self.assertIn("story-memory: forbidden canonical runtime vocabulary MERIDIAN_TASK_DIR", problems)
        self.assertIn("story-memory: forbidden canonical runtime vocabulary meridian", problems)

    def test_validator_rejects_codex_vocabulary_in_claude_runtime(self):
        skill = self.root / "cw" / "skills" / "story-memory" / "SKILL.md"
        skill.write_text(
            "---\nname: story-memory\ndescription: Demo.\n---\n"
            "Read AGENTS.md, call spawn_agent, and use $story-review.\n"
        )
        problems = validate(self.root)
        self.assertIn("cw/skills/story-memory/SKILL.md: Codex-only vocabulary AGENTS.md", problems)
        self.assertIn("cw/skills/story-memory/SKILL.md: Codex-only vocabulary spawn_agent", problems)
        self.assertIn("cw/skills/story-memory/SKILL.md: Codex-only skill reference $story-review", problems)

    def test_validator_scans_claude_fences_and_scripts_for_platform_vocabulary(self):
        skill_root = self.root / "cw" / "skills" / "story-memory"
        (skill_root / "SKILL.md").write_text(
            "---\nname: story-memory\ndescription: Demo.\n---\n"
            "```bash\nMars sync\n```\n"
        )
        (skill_root / "tool.py").write_text("value = 'meridian.toml'\n")
        problems = validate(self.root)
        self.assertIn(
            "cw/skills/story-memory/SKILL.md: forbidden runtime vocabulary Mars",
            problems,
        )
        self.assertIn(
            "cw/skills/story-memory/tool.py: forbidden runtime vocabulary meridian",
            problems,
        )

    def test_validator_reports_invalid_utf8_once_per_canonical_file(self):
        skill_file = self.skills / "story-memory" / "SKILL.md"
        skill_file.write_bytes(b"\xff")
        resource = self.skills / "story-review" / "bad.md"
        resource.write_bytes(b"\xff")
        worker_prompt = (
            self.skills / "creative-writing-muse" / "resources" / "workers" / "critic.md"
        )
        worker_prompt.write_bytes(b"\xff")
        problems = validate(self.root)
        for name in ("story-memory", "story-review", "creative-writing-muse"):
            matches = [problem for problem in problems if problem.startswith(f"{name}: cannot read")]
            self.assertEqual(len(matches), 1, (name, problems))

    def test_validator_reports_invalid_utf8_once_for_claude_runtime(self):
        path = self.root / "cw" / "skills" / "story-memory" / "bad.md"
        path.write_bytes(b"\xff")
        problems = validate(self.root)
        matches = [
            problem for problem in problems
            if problem.startswith("cw/skills/story-memory/bad.md: cannot read")
        ]
        self.assertEqual(len(matches), 1, problems)

    def test_validator_reports_invalid_worker_registry_once(self):
        path = (
            self.skills / "creative-writing-muse" / "resources" / "workers" / "registry.json"
        )
        path.write_bytes(b"\xff")
        problems = validate(self.root)
        matches = [
            problem for problem in problems
            if problem.startswith("invalid worker registry:")
            or problem.startswith("creative-writing-muse: cannot read resources/workers/registry.json")
        ]
        self.assertEqual(len(matches), 1, problems)

    def test_validator_reports_invalid_claude_manifest_once(self):
        path = self.root / "cw" / ".claude-plugin" / "plugin.json"
        path.write_bytes(b"\xff")
        problems = validate(self.root)
        matches = [
            problem for problem in problems
            if problem.startswith("invalid cw plugin manifest:")
            or problem.startswith("cw/.claude-plugin/plugin.json: cannot read")
        ]
        self.assertEqual(len(matches), 1, problems)

    def test_validator_reports_runtime_oserror_without_crashing(self):
        target = self.skills / "story-memory" / "bad.md"
        target.write_text("Unreadable in test.\n")
        original = Path.read_text

        def fail_selected(path, *args, **kwargs):
            if path == target:
                raise OSError("simulated read failure")
            return original(path, *args, **kwargs)

        with mock.patch.object(Path, "read_text", fail_selected):
            problems = validate(self.root)
        matches = [problem for problem in problems if "simulated read failure" in problem]
        self.assertEqual(len(matches), 1, problems)

    def test_validator_rejects_external_canonical_skill_symlink(self):
        skill = self.skills / "zoom-out"
        shutil.rmtree(skill)
        external = self.root / "external-skill"
        external.mkdir()
        (external / "SKILL.md").write_text(
            "---\nname: zoom-out\ndescription: Demo.\n---\nExternal.\n"
        )
        skill.symlink_to(external, target_is_directory=True)
        self.assertIn("zoom-out: skill directory must not be a symlink", validate(self.root))

    def test_validator_rejects_internal_canonical_plugin_root_symlink_before_read(self):
        target = self.root / "plugins" / "canonical-target"
        self.plugin.rename(target)
        self.plugin.symlink_to(target.name, target_is_directory=True)
        self.assertIn("canonical plugin root must not traverse symlinks", validate(self.root))

    def test_validator_rejects_external_canonical_plugin_root_symlink_before_read(self):
        target = self.root / "external-canonical-plugin"
        self.plugin.rename(target)
        self.plugin.symlink_to(target, target_is_directory=True)
        self.assertIn("canonical plugin root must not traverse symlinks", validate(self.root))

    def test_validator_rejects_symlinked_canonical_manifest_directory_before_read(self):
        control = self.plugin / ".codex-plugin"
        target = self.plugin / "manifest-control"
        control.rename(target)
        control.symlink_to(target.name, target_is_directory=True)
        self.assertIn("canonical manifest must not traverse symlinks", validate(self.root))

    def test_validator_rejects_external_canonical_manifest_file_before_read(self):
        manifest = self.plugin / ".codex-plugin" / "plugin.json"
        target = self.root / "external-canonical-manifest.json"
        manifest.rename(target)
        manifest.symlink_to(target)
        self.assertIn("canonical manifest must not traverse symlinks", validate(self.root))

    def test_validator_rejects_symlinked_distribution_control_files_before_read(self):
        cases = (
            (
                self.root / ".agents" / "plugins" / "marketplace.json",
                "Codex marketplace must not traverse symlinks",
            ),
            (
                self.root / "config" / "distribution.json",
                "distribution config must not traverse symlinks",
            ),
            (
                self.skills / "creative-writing-muse" / "resources" / "workers" / "registry.json",
                "worker registry must not traverse symlinks",
            ),
        )
        for index, (path, expected) in enumerate(cases):
            with self.subTest(path=path):
                fixture = ValidatorTests(methodName="test_validator_accepts_complete_fixture")
                fixture.setUp()
                self.addCleanup(fixture.doCleanups)
                relative = path.relative_to(self.root)
                fixture_path = fixture.root / relative
                target = fixture.root / f"control-{index}.json"
                fixture_path.rename(target)
                fixture_path.symlink_to(target)
                self.assertIn(expected, validate(fixture.root))

    def test_validator_does_not_traverse_symlinked_canonical_skills_root(self):
        external = self.root / "external-skills"
        self.skills.rename(external)
        self.skills.symlink_to(external, target_is_directory=True)
        self.assertIn("canonical skills root must not be a symlink", validate(self.root))

    def test_validator_rejects_external_canonical_runtime_symlink(self):
        external = self.root / "external.py"
        external.write_text("safe = True\n")
        link = self.skills / "story-memory" / "external.py"
        link.symlink_to(external)
        self.assertIn("story-memory: runtime resource external.py must not be a symlink", validate(self.root))

    def test_validator_rejects_internal_runtime_symlink_by_policy(self):
        skill = self.skills / "story-memory"
        target = skill / "guide.md"
        target.write_text("Guide.\n")
        (skill / "alias.md").symlink_to(target.name)
        self.assertIn("story-memory: runtime resource alias.md must not be a symlink", validate(self.root))

    def test_validator_rejects_external_claude_skill_symlink(self):
        skill = self.root / "cw" / "skills" / "zoom-out"
        shutil.rmtree(skill)
        external = self.root / "external-claude-skill"
        external.mkdir()
        (external / "SKILL.md").write_text(
            "---\nname: zoom-out\ndescription: Demo.\n---\nExternal.\n"
        )
        skill.symlink_to(external, target_is_directory=True)
        problems = validate(self.root)
        symlink_problems = [problem for problem in problems if "zoom-out" in problem and "symlink" in problem]
        self.assertEqual(
            symlink_problems,
            ["cw skill zoom-out: directory must not be a symlink"],
        )

    def test_validator_rejects_internal_claude_manifest_symlink_before_read(self):
        manifest = self.root / "cw" / ".claude-plugin" / "plugin.json"
        target = manifest.parent / "manifest-target.json"
        manifest.rename(target)
        manifest.symlink_to(target.name)
        self.assertIn("cw plugin manifest must not traverse symlinks", validate(self.root))

    def test_validator_rejects_external_claude_manifest_symlink_before_read(self):
        manifest = self.root / "cw" / ".claude-plugin" / "plugin.json"
        target = self.root / "external-claude-manifest.json"
        manifest.rename(target)
        manifest.symlink_to(target)
        self.assertIn("cw plugin manifest must not traverse symlinks", validate(self.root))

    def test_validator_rejects_symlinked_claude_control_paths_before_read(self):
        control = self.root / "cw" / ".claude-plugin"
        target = self.root / "cw" / "claude-control"
        control.rename(target)
        control.symlink_to(target.name, target_is_directory=True)
        self.assertIn("cw plugin manifest must not traverse symlinks", validate(self.root))

        marketplace = self.root / ".claude-plugin" / "marketplace.json"
        marketplace_target = self.root / "external-claude-marketplace.json"
        marketplace.rename(marketplace_target)
        marketplace.symlink_to(marketplace_target)
        self.assertIn("Claude marketplace must not traverse symlinks", validate(self.root))

    def test_validator_does_not_traverse_symlinked_claude_skills_root(self):
        skills = self.root / "cw" / "skills"
        external = self.root / "external-claude-skills"
        skills.rename(external)
        skills.symlink_to(external, target_is_directory=True)
        self.assertIn("cw skills root must not be a symlink", validate(self.root))

    def test_validator_does_not_traverse_symlinked_claude_root(self):
        claude = self.root / "cw"
        external = self.root / "external-claude"
        claude.rename(external)
        claude.symlink_to(external, target_is_directory=True)
        self.assertIn("cw root must not be a symlink", validate(self.root))

    def test_validator_does_not_traverse_symlinked_claude_agents_root(self):
        agents = self.root / "cw" / "agents"
        external = self.root / "external-claude-agents"
        agents.rename(external)
        agents.symlink_to(external, target_is_directory=True)
        self.assertIn("cw agents root must not be a symlink", validate(self.root))

    def test_validator_rejects_external_claude_runtime_symlink(self):
        external = self.root / "external-claude.py"
        external.write_text("safe = True\n")
        link = self.root / "cw" / "skills" / "story-memory" / "external.py"
        link.symlink_to(external)
        self.assertIn(
            "cw/skills/story-memory/external.py: runtime resource must not be a symlink",
            validate(self.root),
        )

    def test_validator_distinguishes_worker_mentions_from_other_at_tokens(self):
        skill = self.skills / "story-memory" / "SKILL.md"
        skill.write_text(
            "---\nname: story-memory\ndescription: Demo.\n---\n"
            "Delegate to @ghost and @missing-worker, but keep @writer.\n"
            "Email author@example.com. Install @xyflow/react.\n"
            "Use @theme, @media, @counter-style, @view-transition, @when, "
            "@else, and @supports-condition.\n"
            "Open https://example.com/@url-worker.\n"
        )
        problems = validate(self.root)
        self.assertIn("story-memory: dangling worker reference @ghost", problems)
        self.assertIn("story-memory: dangling worker reference @missing-worker", problems)
        for token in (
            "writer", "example", "xyflow", "theme", "media", "counter-style",
            "view-transition", "when", "else", "supports-condition", "url-worker",
        ):
            self.assertNotIn(f"story-memory: dangling worker reference @{token}", problems)

    def test_validator_does_not_treat_python_decorators_as_worker_references(self):
        generated = (
            self.root
            / "cw/skills/project-maintenance/resources/cli/cwcli/example.py"
        )
        generated.parent.mkdir(parents=True, exist_ok=True)
        generated.write_text(
            "from dataclasses import dataclass\n\n"
            "@dataclass(frozen=True)\n"
            "class Example:\n"
            "    value: str\n"
        )

        problems = validate(self.root)

        self.assertNotIn(
            "cw/skills/project-maintenance/resources/cli/cwcli/example.py: "
            "dangling worker reference @dataclass",
            problems,
        )

    def test_validator_reports_symlink_loops_without_crashing(self):
        skill = self.skills / "story-memory"
        (skill / "loop").symlink_to("loop")
        (skill / "SKILL.md").write_text(
            "---\nname: story-memory\ndescription: Demo.\n---\n"
            "Read [loop](loop/file.md).\n"
        )
        problems = validate(self.root)
        self.assertIn("story-memory: missing relative resource loop/file.md", problems)

    def test_validator_rejects_registry_path_through_symlink_loop(self):
        workers = self.skills / "creative-writing-muse" / "resources" / "workers"
        (workers / "loop").symlink_to("loop")
        config_path = self.root / "config" / "distribution.json"
        config = json.loads(config_path.read_text())
        config["workers"] = (
            "skills/creative-writing-muse/resources/workers/loop/registry.json"
        )
        self._write_json(config_path, config)
        problems = validate(self.root)
        self.assertIn(
            "worker registry must not traverse symlinks",
            problems,
        )

    def test_validator_rejects_claude_path_through_symlink_loop(self):
        (self.root / "loop").symlink_to("loop")
        config_path = self.root / "config" / "distribution.json"
        config = json.loads(config_path.read_text())
        config["claude"]["marketplace"] = "loop/marketplace.json"
        self._write_json(config_path, config)
        problems = validate(self.root)
        self.assertIn(
            "Claude marketplace must not traverse symlinks",
            problems,
        )

    def test_containment_rejects_symlink_loop(self):
        loop = self.root / "loop"
        loop.symlink_to("loop")
        self.assertFalse(_is_within(loop / "child", self.root))

    def test_canonical_only_skips_stale_claude_output(self):
        self.claude_manifest["version"] = "0.0.0"
        self.write_claude_manifest()
        self.assertEqual(validate(self.root, canonical_only=True), [])


class ValidatorCliTests(unittest.TestCase):
    def test_canonical_only_cli_runs_as_a_script(self):
        environment = os.environ.copy()
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        completed = subprocess.run(
            [sys.executable, "scripts/validate_distribution.py", "--canonical-only"],
            cwd=REPO_ROOT,
            env=environment,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertEqual(completed.stdout, "Distribution validation passed\n")

    def test_failure_output_is_bulleted_deterministic_and_has_no_success_message(self):
        fixture = ValidatorTests(methodName="test_validator_accepts_complete_fixture")
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        marketplace_path = fixture.root / ".agents" / "plugins" / "marketplace.json"
        marketplace = json.loads(marketplace_path.read_text())
        marketplace["plugins"][0]["policy"]["authentication"] = "NONE"
        fixture._write_json(marketplace_path, marketplace)
        skill = fixture.skills / "story-memory" / "SKILL.md"
        skill.write_text(
            "---\nname: story-memory\ndescription: Demo.\n---\nUse $missing-skill.\n"
        )

        outputs = []
        for _ in range(2):
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                result = validate_main([], repo_root=fixture.root)
            self.assertEqual(result, 1)
            outputs.append(stdout.getvalue())

        self.assertEqual(outputs[0], outputs[1])
        self.assertEqual(
            outputs[0].splitlines(),
            [
                "- marketplace authentication policy NONE != ON_INSTALL",
                "- story-memory: dangling skill reference $missing-skill",
            ],
        )
        self.assertNotIn("Distribution validation passed", outputs[0])

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
from scripts.validate_distribution import _is_within, validate


EXPECTED_SKILLS = {
    "character-sim", "creative-research", "creative-writing-craft",
    "creative-writing-modes", "creative-writing-muse", "grill-with-docs",
    "information-hierarchy", "intent-modeling", "kb-management",
    "knowledge-layers", "llm-writing", "md-validation", "project-setup",
    "qi-layer", "reader-sim", "reflect", "shared-dao", "story-memory",
    "story-planning", "story-review", "structured-artifact", "world-creation",
    "writing-principles", "writing-staffing", "zoom-out",
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
    "writer": ("workspace-write", {"creative-writing-modes", "creative-writing-craft", "writing-principles", "story-memory", "llm-writing"}),
}

PRESSURE_RESULTS = REPO_ROOT / "tests" / "fixtures" / "muse-pressure" / "results.md"


class DistributionScaffoldTests(unittest.TestCase):
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
        self.assertEqual(len(config["authored_skills"]), 15)
        self.assertEqual(len(config["vendored_skills"]), 10)

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
        self.root = Path(self.temporary_directory.name)
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
            "project-setup", "reader-sim", "shared-dao", "story-memory",
            "story-planning", "story-review", "world-creation",
            "writing-principles", "writing-staffing",
        }
        config = {
            "canonical_skills": sorted(EXPECTED_SKILLS),
            "authored_skills": sorted(authored),
            "vendored_skills": sorted(EXPECTED_SKILLS - authored),
            "workers": "skills/creative-writing-muse/resources/workers/registry.json",
            "claude": {
                "root": "cw",
                "marketplace": ".claude-plugin/marketplace.json",
            },
        }
        self._write_json(self.root / "config" / "distribution.json", config)

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
            skill.write_text(f"---\nname: {name}\ndescription: Demo.\n---\n{name}\n")
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

    def _write_json(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))

    def write_claude_manifest(self):
        self._write_json(self.root / "cw" / ".claude-plugin" / "plugin.json", self.claude_manifest)

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

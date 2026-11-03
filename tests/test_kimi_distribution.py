import io
import json
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from scripts.distribution import REPO_ROOT, load_json, split_frontmatter
from scripts.sync_claude_distribution import (
    main,
    render_agent,
    render_kimi_distribution,
    transform_skill,
)
from scripts.validate_distribution import validate


class KimiTransformTests(unittest.TestCase):
    def test_skill_transform_uses_qualified_kimi_references(self):
        source = (
            "---\n"
            "name: demo\n"
            "description: Use $story-memory when updating context.\n"
            "argument-hint: Optional focus\n"
            "---\n"
            "Use $story-review and preserve this fenced value:\n"
            "```text\n$story-memory\n```\n"
        )

        rendered = transform_skill(
            source,
            "demo",
            disable_model_invocation=True,
            runtime="kimi",
        )

        self.assertIn(
            'description: "Use /skill:creative-writing-skills:story-memory '
            'when updating context."',
            rendered,
        )
        self.assertIn("Use /skill:creative-writing-skills:story-review", rendered)
        self.assertIn("disable-model-invocation: true", rendered)
        self.assertNotIn("argument-hint", rendered)
        self.assertIn("```text\n$story-memory\n```", rendered)

    def test_read_only_agent_uses_kimi_tool_metadata_and_assigned_skills(self):
        worker = {
            "name": "critic",
            "description": "Critique prose.",
            "skills": ["story-review", "writing-principles"],
            "tools": ["Read", "Bash"],
            "access": "read-only",
            "claude": {"model": "inherit", "background": False},
        }

        rendered = render_agent(
            worker,
            "Use $story-review and return findings.\n",
            runtime="kimi",
        )

        self.assertIn("disallowedTools:\n  - Edit\n  - Write", rendered)
        self.assertNotIn("disallowed-tools:", rendered)
        self.assertNotIn("\ntools:", rendered)
        self.assertNotIn("background:", rendered)
        self.assertNotIn("skills:\n  - story-review", rendered)
        self.assertIn("- `/skill:creative-writing-skills:story-review`", rendered)
        self.assertIn("- `/skill:creative-writing-skills:writing-principles`", rendered)
        self.assertIn("Use /skill:creative-writing-skills:story-review", rendered)


class KimiDistributionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        shutil.copytree(REPO_ROOT / "plugins", self.root / "plugins")
        shutil.copytree(REPO_ROOT / "config", self.root / "config")
        shutil.copytree(REPO_ROOT / ".agents", self.root / ".agents")

    def apply(self):
        output = io.StringIO()
        with redirect_stdout(output):
            status = main(["--apply"], repo_root=self.root)
        self.assertEqual(0, status, output.getvalue())
        return output.getvalue()

    def test_render_materializes_complete_kimi_plugin(self):
        output_root = self.root / "rendered-kimi"

        render_kimi_distribution(output_root)

        config = load_json(REPO_ROOT / "config/distribution.json")
        registry = load_json(
            REPO_ROOT
            / "plugins/creative-writing-skills/skills/creative-writing-muse/"
            "resources/workers/registry.json"
        )
        expected_skills = set(config["canonical_skills"])
        expected_agents = {worker["name"] for worker in registry["workers"]} | {"muse"}
        self.assertEqual(
            expected_skills,
            {path.name for path in (output_root / "skills").iterdir()},
        )
        self.assertEqual(
            expected_agents,
            {path.stem for path in (output_root / "agents").glob("*.md")},
        )
        canonical = load_json(
            REPO_ROOT
            / "plugins/creative-writing-skills/.codex-plugin/plugin.json"
        )
        manifest = load_json(output_root / ".kimi-plugin/plugin.json")
        self.assertEqual(canonical["name"], manifest["name"])
        self.assertEqual(canonical["version"], manifest["version"])
        self.assertEqual("./skills/", manifest["skills"])
        self.assertEqual("./agents/", manifest["agents"])
        self.assertNotIn("repository", manifest)
        self.assertNotIn("defaultPrompt", manifest["interface"])

        muse = (output_root / "skills/creative-writing-muse/SKILL.md").read_text()
        self.assertIn("/skill:creative-writing-skills:project-bootstrap", muse)
        self.assertNotIn("$project-bootstrap", muse)
        critic = (output_root / "agents/critic.md").read_text()
        self.assertIn("disallowedTools:\n  - Edit\n  - Write", critic)
        for name in expected_skills:
            metadata, body = split_frontmatter(
                (output_root / "skills" / name / "SKILL.md").read_text()
            )
            self.assertEqual(name, metadata["name"])
            self.assertTrue(metadata["description"])
            self.assertTrue(body.strip())

    def test_apply_generates_direct_install_manifest_and_reports_drift(self):
        output = self.apply()

        self.assertEqual(36, output.count("synced skill "))
        self.assertEqual(11, output.count("synced agent "))
        canonical = load_json(
            self.root / "plugins/creative-writing-skills/.codex-plugin/plugin.json"
        )
        root_manifest_path = self.root / "kimi.plugin.json"
        root_manifest = load_json(root_manifest_path)
        nested_manifest = load_json(self.root / "kimi/.kimi-plugin/plugin.json")
        self.assertEqual(canonical["version"], root_manifest["version"])
        self.assertEqual("./kimi/skills/", root_manifest["skills"])
        self.assertEqual("./kimi/agents/", root_manifest["agents"])
        self.assertEqual(canonical["version"], nested_manifest["version"])
        self.assertEqual([], validate(self.root))

        root_manifest["version"] = "0.0.0"
        root_manifest_path.write_text(json.dumps(root_manifest) + "\n")
        check_output = io.StringIO()
        with redirect_stdout(check_output):
            status = main(["--check"], repo_root=self.root)
        self.assertEqual(1, status)
        self.assertEqual(
            "changed generated file: kimi.plugin.json\n",
            check_output.getvalue(),
        )

    def test_validator_rejects_unqualified_skill_reference(self):
        self.apply()
        skill = self.root / "kimi/skills/story-memory/SKILL.md"
        skill.write_text(skill.read_text() + "\nUse /story-review.\n")

        self.assertIn(
            "kimi/skills/story-memory/SKILL.md: unqualified Kimi Code skill "
            "reference /story-review",
            validate(self.root),
        )

    def test_validator_rejects_root_manifest_identity_drift(self):
        self.apply()
        path = self.root / "kimi.plugin.json"
        manifest = load_json(path)
        manifest["version"] = "0.0.0"
        path.write_text(json.dumps(manifest) + "\n")

        self.assertIn(
            "Kimi Code root manifest version does not match canonical manifest",
            validate(self.root),
        )

    def test_apply_rejects_noncanonical_kimi_config_without_mutation(self):
        config_path = self.root / "config/distribution.json"
        config = load_json(config_path)
        config["kimi"]["root"] = "../outside"
        config_path.write_text(json.dumps(config) + "\n")

        output = io.StringIO()
        with redirect_stdout(output):
            status = main(["--apply"], repo_root=self.root)

        self.assertEqual(1, status)
        self.assertIn("distribution Kimi paths are not canonical", output.getvalue())
        self.assertFalse((self.root / "cw").exists())
        self.assertFalse((self.root / "kimi").exists())


if __name__ == "__main__":
    unittest.main()

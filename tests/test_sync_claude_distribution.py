import io
import json
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from scripts.sync_claude_distribution import (
    UnsupportedTransformError,
    _commit_candidate,
    main,
    render_agent,
    render_distribution,
    transform_skill,
)


EXPECTED_SKILLS = {
    "character-sim",
    "creative-research",
    "creative-writing-craft",
    "creative-writing-modes",
    "creative-writing-muse",
    "grill-with-docs",
    "information-hierarchy",
    "intent-modeling",
    "kb-management",
    "knowledge-layers",
    "llm-writing",
    "md-validation",
    "project-setup",
    "qi-layer",
    "reader-sim",
    "reflect",
    "shared-dao",
    "story-memory",
    "story-planning",
    "story-review",
    "structured-artifact",
    "world-creation",
    "writing-principles",
    "writing-staffing",
    "zoom-out",
}

EXPECTED_WORKERS = {
    "brainstormer",
    "character-sim",
    "continuity-checker",
    "critic",
    "editor",
    "outliner",
    "reader-sim",
    "style-creator",
    "web-researcher",
    "writer",
}


class ClaudeTransformTests(unittest.TestCase):
    def test_skill_transform_converts_description_and_preserves_claude_flags(self):
        source = (
            "---\n"
            "name: demo\n"
            "description: Use $story-memory when updating AGENTS.md.\n"
            "disable-model-invocation: true\n"
            "argument-hint: Optional focus\n"
            "---\n"
            "# Demo\n"
        )

        rendered = transform_skill(source, "demo")

        self.assertIn("description: \"Use /story-memory when updating CLAUDE.md.\"", rendered)
        self.assertIn("disable-model-invocation: true", rendered)
        self.assertIn('argument-hint: "Optional focus"', rendered)
        self.assertNotIn("AGENTS.md", rendered)
        self.assertNotIn("$story-memory", rendered)

    def test_skill_transform_uses_claude_instruction_names(self):
        source = (
            "---\n"
            "name: demo\n"
            "description: Demo.\n"
            "---\n"
            "Read AGENTS.md and use $story-memory.\n"
        )

        rendered = transform_skill(source, "demo")

        self.assertIn("Read CLAUDE.md", rendered)
        self.assertIn("/story-memory", rendered)
        self.assertNotIn("AGENTS.md", rendered)
        self.assertNotIn("$story-memory", rendered)

    def test_worker_renders_as_claude_agent(self):
        worker = {
            "name": "critic",
            "description": "Critique prose.",
            "skills": ["story-review"],
            "access": "read-only",
            "claude": {"model": "inherit", "background": False},
        }

        rendered = render_agent(worker, "Return findings to muse.\n")

        self.assertIn("name: critic", rendered)
        self.assertIn("skills:\n  - story-review", rendered)
        self.assertIn("Return findings to muse.", rendered)
        self.assertNotIn("model: inherit", rendered)

    def test_unknown_codex_only_construct_fails(self):
        source = (
            "---\n"
            "name: demo\n"
            "description: Demo.\n"
            "---\n"
            "Call spawn_agent directly.\n"
        )

        with self.assertRaisesRegex(UnsupportedTransformError, "spawn_agent"):
            transform_skill(source, "demo")

    def test_transform_preserves_fenced_shell_variable(self):
        source = (
            "---\n"
            "name: demo\n"
            "description: Demo.\n"
            "---\n"
            "Use $story-memory.\n"
            "```bash\n"
            "echo $chapter\n"
            "```\n"
        )

        rendered = transform_skill(source, "demo")

        self.assertIn("Use /story-memory.", rendered)
        self.assertIn("echo $chapter", rendered)


class ClaudeDistributionRenderTests(unittest.TestCase):
    def test_render_distribution_materializes_complete_claude_tree(self):
        with tempfile.TemporaryDirectory() as temporary:
            output_root = Path(temporary) / "cw"

            render_distribution(output_root)

            skill_names = {path.name for path in (output_root / "skills").iterdir()}
            agent_names = {path.stem for path in (output_root / "agents").glob("*.md")}
            self.assertEqual(EXPECTED_SKILLS, skill_names)
            self.assertEqual(EXPECTED_WORKERS | {"muse"}, agent_names)

            project_setup = (output_root / "skills/project-setup/SKILL.md").read_text()
            qi_layer = (output_root / "skills/qi-layer/SKILL.md").read_text()
            worker_resource = (
                output_root
                / "skills/creative-writing-muse/resources/workers/critic.md"
            ).read_text()
            self.assertIn("CLAUDE.md", project_setup)
            self.assertNotIn("AGENTS.md", project_setup)
            self.assertNotIn("AGENTS.md", qi_layer)
            self.assertIn("/story-review", worker_resource)
            self.assertNotIn("$story-review", worker_resource)

            source_script = Path(
                "plugins/creative-writing-skills/skills/story-review/"
                "resources/prose-critique/analyze.py"
            ).read_bytes()
            rendered_script = (
                output_root
                / "skills/story-review/resources/prose-critique/analyze.py"
            ).read_bytes()
            self.assertEqual(source_script, rendered_script)

            critic = (output_root / "agents/critic.md").read_text()
            researcher = (output_root / "agents/web-researcher.md").read_text()
            muse = (output_root / "agents/muse.md").read_text()
            for forbidden in ("model:", "tools:", "sandbox:", "access:"):
                self.assertNotIn(forbidden, critic)
                self.assertNotIn(forbidden, muse)
            self.assertNotIn("background:", critic)
            self.assertIn("background: true", researcher)
            for skill in EXPECTED_SKILLS:
                self.assertIn(f"  - {skill}\n", muse)
            self.assertNotIn("AGENTS.md", muse)
            self.assertNotIn("$creative-writing-muse", muse)

            manifest = json.loads(
                (output_root / ".claude-plugin/plugin.json").read_text()
            )
            self.assertEqual("creative-writing-skills", manifest["name"])
            self.assertEqual("0.5.9", manifest["version"])
            self.assertEqual({"name": "InkyQuill"}, manifest["author"])
            self.assertEqual(
                "https://github.com/InkyQuill/creative-writing-skills",
                manifest["repository"],
            )
            self.assertEqual("Apache-2.0", manifest["license"])


class ClaudeDistributionCliTests(unittest.TestCase):
    def _copy_canonical_inputs(self, root: Path) -> None:
        shutil.copytree("plugins", root / "plugins")
        shutil.copytree("config", root / "config")

    def test_apply_generates_marketplace_and_check_reports_precise_drift(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary)
            self._copy_canonical_inputs(repo_root)
            marketplace_path = repo_root / ".claude-plugin/marketplace.json"
            marketplace_path.parent.mkdir(parents=True)
            marketplace_path.write_text("{}\n")

            apply_output = io.StringIO()
            with redirect_stdout(apply_output):
                apply_status = main(["--apply"], repo_root=repo_root)

            self.assertEqual(0, apply_status)
            self.assertEqual(25, apply_output.getvalue().count("synced skill "))
            self.assertEqual(11, apply_output.getvalue().count("synced agent "))
            marketplace = json.loads(marketplace_path.read_text())
            self.assertEqual("creative-writing-skills", marketplace["name"])
            self.assertEqual({"name": "InkyQuill"}, marketplace["owner"])
            self.assertEqual("0.5.9", marketplace["metadata"]["version"])
            self.assertEqual("./cw", marketplace["plugins"][0]["source"])

            changed = repo_root / "cw/skills/story-memory/SKILL.md"
            changed.write_text(changed.read_text() + "drift\n")
            check_output = io.StringIO()
            with redirect_stdout(check_output):
                check_status = main(["--check"], repo_root=repo_root)

            self.assertEqual(1, check_status)
            self.assertEqual(
                "changed generated file: cw/skills/story-memory/SKILL.md\n",
                check_output.getvalue(),
            )

    def test_apply_leaves_existing_distribution_untouched_when_render_fails(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary)
            self._copy_canonical_inputs(repo_root)
            cw_root = repo_root / "cw"
            cw_root.mkdir()
            (cw_root / "sentinel.txt").write_text("original cw\n")
            marketplace_path = repo_root / ".claude-plugin/marketplace.json"
            marketplace_path.parent.mkdir(parents=True)
            marketplace_path.write_text('{"original": true}\n')
            bad_skill = (
                repo_root
                / "plugins/creative-writing-skills/skills/project-setup/SKILL.md"
            )
            bad_skill.write_text(bad_skill.read_text() + "Call spawn_agent.\n")

            output = io.StringIO()
            with redirect_stdout(output):
                status = main(["--apply"], repo_root=repo_root)

            self.assertEqual(1, status)
            self.assertIn("spawn_agent", output.getvalue())
            self.assertEqual([Path("sentinel.txt")], [
                path.relative_to(cw_root) for path in cw_root.rglob("*")
            ])
            self.assertEqual("original cw\n", (cw_root / "sentinel.txt").read_text())
            self.assertEqual('{"original": true}\n', marketplace_path.read_text())

    def test_apply_rolls_back_existing_distribution_when_install_is_interrupted(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cw_root = root / "cw"
            cw_root.mkdir()
            (cw_root / "value.txt").write_text("old cw\n")
            candidate_cw = root / "candidate-cw"
            candidate_cw.mkdir()
            (candidate_cw / "value.txt").write_text("new cw\n")
            marketplace_path = root / "marketplace.json"
            marketplace_path.write_text("old marketplace\n")
            candidate_marketplace = root / "candidate-marketplace.json"
            candidate_marketplace.write_text("new marketplace\n")
            transaction_root = root / "transaction"
            transaction_root.mkdir()
            real_replace = __import__("os").replace

            def interrupt_install(source, destination):
                if Path(source) == candidate_cw and Path(destination) == cw_root:
                    raise KeyboardInterrupt("injected install interrupt")
                return real_replace(source, destination)

            with patch(
                "scripts.sync_claude_distribution.os.replace",
                side_effect=interrupt_install,
            ):
                with self.assertRaisesRegex(
                    KeyboardInterrupt, "injected install interrupt"
                ):
                    _commit_candidate(
                        candidate_cw,
                        cw_root,
                        candidate_marketplace,
                        marketplace_path,
                        transaction_root,
                    )

            self.assertEqual("old cw\n", (cw_root / "value.txt").read_text())
            self.assertEqual("old marketplace\n", marketplace_path.read_text())


if __name__ == "__main__":
    unittest.main()

import io
import json
import os
import shutil
import tempfile
import unittest
import zipfile
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from scripts.create_skill_zips import (
    build_archives,
    create_skill_zip,
    validate_skill_set,
)
from scripts.distribution import split_frontmatter
from scripts.sync_claude_distribution import (
    UnsupportedTransformError,
    _commit_candidate,
    _render_zcode_marketplace,
    _transform_resource_markdown,
    main,
    render_agent,
    render_distribution,
    transform_skill,
)


EXPECTED_SKILLS = {
    "character-sim",
    "cli-doctor",
    "creative-research",
    "creative-writing-craft",
    "creative-writing-modes",
    "creative-writing-muse",
    "decision-grill",
    "information-hierarchy",
    "intent-modeling",
    "kb-management",
    "knowledge-layers",
    "llm-writing",
    "md-validation",
    "project-doctor",
    "project-feedback",
    "project-maintenance",
    "project-setup",
    "qi-layer",
    "reader-sim",
    "reflect",
    "shared-dao",
    "story-memory",
    "story-planning",
    "story-review",
    "structured-artifact",
    "targeted-editing",
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


class ArchiveContractTests(unittest.TestCase):
    def test_project_maintenance_archive_bundles_public_cli_and_checkers(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            skill = Path("cw/skills/project-maintenance")

            create_skill_zip(skill, output)

            with zipfile.ZipFile(output / "project-maintenance.skill") as archive:
                names = set(archive.namelist())
            prefix = "project-maintenance/resources/cli/"
            self.assertLessEqual(
                {
                    prefix + "cw.py",
                    prefix + "cwcli/app.py",
                    prefix + "cwcli/checks/continuity.py",
                    prefix + "cwcli/checks/prose.py",
                },
                names,
            )

    def test_archive_validation_rejects_missing_skill(self):
        with self.assertRaisesRegex(ValueError, "missing: world-creation"):
            validate_skill_set(
                [Path("character-sim")],
                {"character-sim", "world-creation"},
            )

    def test_archive_validation_reports_sorted_missing_and_extra_skills(self):
        with self.assertRaisesRegex(
            ValueError,
            r"missing: alpha, world-creation; extra: obsolete, surprise",
        ):
            validate_skill_set(
                [Path("surprise"), Path("character-sim"), Path("obsolete")],
                {"world-creation", "character-sim", "alpha"},
            )

    def test_inventory_mismatch_is_rejected_before_existing_archives_are_touched(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary)
            (repo_root / "config").mkdir()
            (repo_root / "config/distribution.json").write_text(
                json.dumps(
                    {"canonical_skills": ["character-sim", "world-creation"]}
                )
            )
            skill = repo_root / "cw/skills/character-sim"
            skill.mkdir(parents=True)
            (skill / "SKILL.md").write_text("# Character simulation\n")
            output = repo_root / "zips"
            output.mkdir()
            sentinel = output / "existing.skill"
            sentinel.write_bytes(b"existing archive")

            with self.assertRaisesRegex(ValueError, "missing: world-creation"):
                build_archives(repo_root)

            self.assertEqual(b"existing archive", sentinel.read_bytes())

    def test_archives_are_deterministic_and_include_all_runtime_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            skill = root / "world-creation"
            (skill / "references").mkdir(parents=True)
            (skill / "agents").mkdir()
            (skill / "SKILL.md").write_text("# World creation\n")
            reference = skill / "references/world-file-format.md"
            reference.write_text("# World file format\n")
            (skill / "agents/openai.yaml").write_text("excluded: true\n")
            output = root / "output"
            output.mkdir()

            create_skill_zip(skill, output)
            first = (output / "world-creation.skill").read_bytes()
            os.utime(reference, (2_000_000_000, 2_000_000_000))
            create_skill_zip(skill, output)
            second = (output / "world-creation.skill").read_bytes()

            self.assertEqual(first, second)
            with zipfile.ZipFile(io.BytesIO(second)) as archive:
                self.assertEqual(
                    [
                        "world-creation/SKILL.md",
                        "world-creation/references/world-file-format.md",
                    ],
                    archive.namelist(),
                )
                self.assertEqual(
                    {(1980, 1, 1, 0, 0, 0)},
                    {item.date_time for item in archive.infolist()},
                )

    def test_archive_rejects_symlinks_before_writing(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            skill = root / "demo"
            skill.mkdir()
            (skill / "SKILL.md").write_text("# Demo\n")
            outside = root / "outside.md"
            outside.write_text("outside\n")
            (skill / "leak.md").symlink_to(outside)
            output = root / "output"
            output.mkdir()

            with self.assertRaisesRegex(ValueError, "symlink"):
                create_skill_zip(skill, output)

            self.assertFalse((output / "demo.skill").exists())


class ClaudeTransformTests(unittest.TestCase):
    def test_skill_transform_converts_description_and_emits_configured_claude_flag(self):
        source = (
            "---\n"
            "name: demo\n"
            "description: Use $story-memory when updating AGENTS.md.\n"
            "argument-hint: Optional focus\n"
            "---\n"
            "# Demo\n"
        )

        rendered = transform_skill(
            source,
            "demo",
            disable_model_invocation=True,
        )

        self.assertIn("description: \"Use /story-memory when updating CLAUDE.md.\"", rendered)
        self.assertIn("disable-model-invocation: true", rendered)
        self.assertIn('argument-hint: "Optional focus"', rendered)
        self.assertNotIn("AGENTS.md", rendered)
        self.assertNotIn("$story-memory", rendered)

    def test_skill_transform_omits_unconfigured_claude_flag(self):
        source = "---\nname: demo\ndescription: Demo.\n---\n# Demo\n"

        rendered = transform_skill(source, "demo")

        self.assertNotIn("disable-model-invocation", rendered)

    def test_skill_transform_rejects_claude_flag_in_canonical_input(self):
        source = (
            "---\n"
            "name: demo\n"
            "description: Demo.\n"
            "disable-model-invocation: true\n"
            "---\n"
            "# Demo\n"
        )

        with self.assertRaisesRegex(
            UnsupportedTransformError,
            "disable-model-invocation true is not supported in canonical Codex skills",
        ):
            transform_skill(source, "demo")

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

    def test_read_only_worker_disallows_file_mutation_tools(self):
        worker = {
            "name": "critic",
            "description": "Critique prose.",
            "skills": ["story-review"],
            "access": "read-only",
            "claude": {"model": "inherit", "background": False},
        }

        rendered = render_agent(worker, "Return findings to muse.\n")

        self.assertIn(
            "disallowed-tools:\n  - Edit\n  - Write\n  - NotebookEdit", rendered
        )

    def test_workspace_write_worker_has_no_tool_restriction(self):
        worker = {
            "name": "writer",
            "description": "Draft prose.",
            "skills": ["story-review"],
            "access": "workspace-write",
            "claude": {"model": "inherit", "background": False},
        }

        rendered = render_agent(worker, "Draft the scene.\n")

        self.assertNotIn("disallowed-tools", rendered)

    def test_worker_rejects_invalid_access(self):
        worker = {
            "name": "critic",
            "description": "Critique prose.",
            "skills": ["story-review"],
            "access": "read-write",
            "claude": {"model": "inherit", "background": False},
        }

        with self.assertRaisesRegex(ValueError, "access must be read-only or workspace-write"):
            render_agent(worker, "Return findings to muse.\n")

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

    def test_generic_transform_preserves_fenced_skill_reference(self):
        source = (
            "---\n"
            "name: demo\n"
            "description: Demo.\n"
            "---\n"
            "```markdown\n"
            "Use $md-validation before committing.\n"
            "```\n"
        )

        rendered = transform_skill(source, "demo")

        self.assertIn("Use $md-validation before committing.", rendered)
        self.assertNotIn("Use /md-validation before committing.", rendered)

    def test_bootstrap_transform_rejects_duplicate_canonical_instruction(self):
        instruction = (
            "Use `$md-validation` for link checking and diagram validation before\n"
            "committing."
        )

        with self.assertRaisesRegex(
            UnsupportedTransformError,
            "fenced validation instruction.*exactly once; found 2",
        ):
            _transform_resource_markdown(
                f"```markdown\n{instruction}\n\n{instruction}\n```\n",
                "knowledge-layers",
                Path("resources/bootstrap.md"),
                frozenset({"knowledge-layers", "md-validation"}),
            )


class ClaudeDistributionRenderTests(unittest.TestCase):
    def test_zcode_marketplace_uses_caller_supplied_icon(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary)
            manifest_path = (
                repo_root
                / "plugins/creative-writing-skills/.codex-plugin/plugin.json"
            )
            manifest_path.parent.mkdir(parents=True)
            manifest_path.write_text(
                json.dumps(
                    {
                        "name": "creative-writing-skills",
                        "description": "Creative writing skills.",
                        "version": "0.6.0",
                    }
                )
            )
            icon = "https://assets.example.test/custom-icon.png"

            marketplace = _render_zcode_marketplace(repo_root, icon)

            self.assertEqual(icon, marketplace["plugins"][0]["icon"])

    def test_render_distribution_preserves_project_maintenance_cli_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            output_root = Path(temporary) / "cw"

            render_distribution(output_root)

            for relative in (
                "resources/cli/cw.py",
                "resources/cli/cwcli/app.py",
                "resources/cli/cwcli/checks/continuity.py",
                "resources/cli/cwcli/checks/prose.py",
            ):
                source = Path(
                    "plugins/creative-writing-skills/skills/project-maintenance"
                ) / relative
                rendered = output_root / "skills/project-maintenance" / relative
                self.assertEqual(source.read_bytes(), rendered.read_bytes(), relative)

    def test_render_distribution_materializes_complete_claude_tree(self):
        with tempfile.TemporaryDirectory() as temporary:
            output_root = Path(temporary) / "cw"

            render_distribution(output_root)

            skill_names = {path.name for path in (output_root / "skills").iterdir()}
            agent_names = {path.stem for path in (output_root / "agents").glob("*.md")}
            self.assertEqual(EXPECTED_SKILLS, skill_names)
            self.assertEqual(EXPECTED_WORKERS | {"muse"}, agent_names)

            project_setup = (output_root / "skills/project-setup/SKILL.md").read_text()
            grill = (output_root / "skills/decision-grill/SKILL.md").read_text()
            story_planning = (
                output_root / "skills/story-planning/SKILL.md"
            ).read_text()
            qi_layer = (output_root / "skills/qi-layer/SKILL.md").read_text()
            bootstrap = (
                output_root
                / "skills/knowledge-layers/resources/bootstrap.md"
            ).read_text()
            worker_resource = (
                output_root
                / "skills/creative-writing-muse/resources/workers/critic.md"
            ).read_text()
            self.assertIn("CLAUDE.md", project_setup)
            self.assertNotIn("AGENTS.md", project_setup)
            self.assertIn(
                "authored body is the durable writing contract",
                project_setup,
            )
            self.assertIn("remain unmanaged", project_setup)
            self.assertIn("Project conventions in `CLAUDE.md`", grill)
            self.assertNotIn("AGENTS.md", grill)
            for resource in (
                "creative-direction.md",
                "brainstorming.md",
                "story-architecture.md",
            ):
                self.assertIn(f"`resources/{resource}`", story_planning)
            self.assertNotIn("AGENTS.md", qi_layer)
            self.assertIn(
                "instruction filename required by the active harness", qi_layer
            )
            self.assertIn("must never import itself", qi_layer)
            self.assertNotIn("CLAUDE.md, not CLAUDE.md", qi_layer)
            self.assertNotIn("sibling CLAUDE.md", qi_layer)
            self.assertNotIn("@CLAUDE.md", qi_layer)
            self.assertIn("{instruction-file}", bootstrap)
            self.assertIn("## Starter instruction file", bootstrap)
            self.assertNotIn("AGENTS.md", bootstrap)
            self.assertIn("Use `/md-validation` for link checking", bootstrap)
            self.assertNotIn("Use `$md-validation` for link checking", bootstrap)
            for path in (
                "`project.md`",
                "`story/chapters/`",
                "`kb/`",
                "`work/drafts/`",
                "`.creative-writing/`",
            ):
                self.assertIn(path, project_setup)
            self.assertIn("There is no\nalternative layout choice", project_setup)
            self.assertIn("Use `/project-maintenance`", project_setup)
            generated_cards = (
                output_root
                / "skills/structured-artifact/resources/card-grid.md"
            ).read_text()
            self.assertNotIn("innerHTML", generated_cards)
            self.assertNotIn("onclick", generated_cards)
            self.assertIn("replaceChildren", generated_cards)
            self.assertIn(
                ".sort((a, b) => (a[s] === b[s] ? 0 : a[s] > b[s] ? 1 : -1))",
                generated_cards,
            )
            self.assertIn("/story-review", worker_resource)
            self.assertNotIn("$story-review", worker_resource)

            self.assertFalse(
                (
                    output_root
                    / "skills/story-review/resources/prose-critique/analyze.py"
                ).exists()
            )
            self.assertFalse(
                (
                    output_root
                    / "skills/story-memory/resources/continuity_check.py"
                ).exists()
            )

            critic = (output_root / "agents/critic.md").read_text()
            researcher = (output_root / "agents/web-researcher.md").read_text()
            muse = (output_root / "agents/muse.md").read_text()
            for forbidden in ("model:", "sandbox:", "access:"):
                self.assertNotIn(forbidden, critic)
                self.assertNotIn(forbidden, muse)
            # critic is a read-only worker: it must be hard-blocked from
            # mutating tools, not merely instructed not to use them.
            self.assertIn(
                "disallowed-tools:\n  - Edit\n  - Write\n  - NotebookEdit", critic
            )
            # muse is workspace-write and must not carry the same restriction.
            self.assertNotIn("disallowed-tools:", muse)
            self.assertNotIn("background:", critic)
            self.assertIn("background: true", researcher)
            for skill in EXPECTED_SKILLS:
                self.assertIn(f"  - {skill}\n", muse)
            self.assertNotIn("AGENTS.md", muse)
            self.assertNotIn("$creative-writing-muse", muse)

            disabled = set()
            for skill in EXPECTED_SKILLS:
                metadata, _ = split_frontmatter(
                    (output_root / "skills" / skill / "SKILL.md").read_text()
                )
                if metadata.get("disable-model-invocation") is True:
                    disabled.add(skill)
            self.assertEqual({"reflect", "structured-artifact"}, disabled)

            manifest = json.loads(
                (output_root / ".claude-plugin/plugin.json").read_text()
            )
            canonical_manifest = json.loads(
                Path(
                    "plugins/creative-writing-skills/.codex-plugin/plugin.json"
                ).read_text()
            )
            self.assertEqual("creative-writing-skills", manifest["name"])
            self.assertEqual(canonical_manifest["version"], manifest["version"])
            self.assertEqual({"name": "InkyQuill"}, manifest["author"])
            self.assertEqual(
                "https://github.com/InkyQuill/creative-writing-skills",
                manifest["repository"],
            )
            self.assertEqual("Apache-2.0", manifest["license"])

            intent_metadata, _ = split_frontmatter(
                (output_root / "skills/intent-modeling/SKILL.md").read_text()
            )
            qi_metadata, _ = split_frontmatter(qi_layer)
            muse_skill_metadata, _ = split_frontmatter(
                (output_root / "skills/creative-writing-muse/SKILL.md").read_text()
            )
            self.assertEqual(
                "Use before acting on human instructions: separate what they said "
                "from what they meant.",
                intent_metadata["description"],
            )
            self.assertEqual(
                "Use when writing or maintaining harness instruction files and "
                ".context/CONTEXT.md: keep intent docs minimal and load-bearing.",
                qi_metadata["description"],
            )
            self.assertEqual(
                "Use when fiction or story work spans planning, drafting, critique, "
                "research, continuity, voice, or durable story state, or when the "
                "author explicitly asks for a muse or broad end-to-end creative-writing "
                "help.\n",
                muse_skill_metadata["description"],
            )


class ClaudeDistributionCliTests(unittest.TestCase):
    def _copy_canonical_inputs(self, root: Path) -> None:
        shutil.copytree("plugins", root / "plugins")
        shutil.copytree("config", root / "config")

    def _write_config(self, repo_root: Path, mutate) -> None:
        path = repo_root / "config/distribution.json"
        config = json.loads(path.read_text())
        mutate(config)
        path.write_text(json.dumps(config) + "\n")

    def test_apply_rejects_duplicate_bootstrap_instruction_without_mutation(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary) / "repo"
            repo_root.mkdir()
            self._copy_canonical_inputs(repo_root)
            bootstrap = (
                repo_root
                / "plugins/creative-writing-skills/skills/knowledge-layers/"
                "resources/bootstrap.md"
            )
            instruction = (
                "Use `$md-validation` for link checking and diagram validation before\n"
                "committing."
            )
            bootstrap.write_text(
                bootstrap.read_text().replace(
                    instruction,
                    instruction + "\n\n" + instruction,
                )
            )
            cw_root = repo_root / "cw"
            cw_root.mkdir()
            sentinel = cw_root / "sentinel.txt"
            sentinel.write_text("original cw\n")
            stdout = io.StringIO()

            with redirect_stdout(stdout):
                status = main(["--apply"], repo_root=repo_root)

            self.assertEqual(1, status)
            self.assertIn("exactly once; found 2", stdout.getvalue())
            self.assertEqual("original cw\n", sentinel.read_text())

    def test_apply_rejects_noncanonical_claude_config_without_mutation(self):
        cases = {
            "absolute root": lambda config, outside: config["claude"].update(
                {"root": str(outside / "target-cw")}
            ),
            "parent-relative root": lambda config, outside: config["claude"].update(
                {"root": "../outside/target-cw"}
            ),
            "absolute marketplace": lambda config, outside: config["claude"].update(
                {"marketplace": str(outside / "marketplace.json")}
            ),
            "extra Claude key": lambda config, outside: config["claude"].update(
                {"extra": "value"}
            ),
            "extra top-level key": lambda config, outside: config.update(
                {"extra": "value"}
            ),
        }
        for label, mutate in cases.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                repo_root = root / "repo"
                outside = root / "outside"
                repo_root.mkdir()
                outside.mkdir()
                self._copy_canonical_inputs(repo_root)
                cw_root = repo_root / "cw"
                cw_root.mkdir()
                (cw_root / "sentinel.txt").write_text("original cw\n")
                target_cw = outside / "target-cw"
                target_cw.mkdir()
                (target_cw / "sentinel.txt").write_text("outside cw\n")
                (outside / "marketplace.json").write_text("outside marketplace\n")
                self._write_config(
                    repo_root,
                    lambda config: mutate(config, outside),
                )

                status = main(["--apply"], repo_root=repo_root)

                self.assertEqual(1, status)
                self.assertEqual(
                    "original cw\n", (cw_root / "sentinel.txt").read_text()
                )
                self.assertEqual(
                    "outside cw\n", (target_cw / "sentinel.txt").read_text()
                )
                self.assertEqual(
                    "outside marketplace\n",
                    (outside / "marketplace.json").read_text(),
                )

    def test_apply_rejects_invalid_claude_invocation_policy_without_mutation(self):
        cases = {
            "missing": (
                lambda config: config["claude"].pop("disable_model_invocation"),
                "distribution Claude fields do not match schema",
            ),
            "not a list": (
                lambda config: config["claude"].update(
                    {"disable_model_invocation": "reflect"}
                ),
                "distribution Claude disable_model_invocation must be a list of skill names",
            ),
            "duplicates": (
                lambda config: config["claude"].update(
                    {"disable_model_invocation": ["reflect", "reflect"]}
                ),
                "distribution Claude disable_model_invocation must not contain duplicates",
            ),
            "not sorted": (
                lambda config: config["claude"].update(
                    {
                        "disable_model_invocation": [
                            "structured-artifact",
                            "reflect",
                        ]
                    }
                ),
                "distribution Claude disable_model_invocation must be sorted",
            ),
            "not canonical": (
                lambda config: config["claude"].update(
                    {"disable_model_invocation": ["not-a-skill"]}
                ),
                "distribution Claude disable_model_invocation must be a subset of canonical_skills",
            ),
        }
        for label, (mutate, expected) in cases.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as temporary:
                repo_root = Path(temporary) / "repo"
                repo_root.mkdir()
                self._copy_canonical_inputs(repo_root)
                config_path = repo_root / "config/distribution.json"
                config = json.loads(config_path.read_text())
                config["claude"].setdefault(
                    "disable_model_invocation",
                    ["reflect", "structured-artifact"],
                )
                mutate(config)
                config_path.write_text(json.dumps(config) + "\n")
                cw_root = repo_root / "cw"
                cw_root.mkdir()
                sentinel = cw_root / "sentinel.txt"
                sentinel.write_text("original cw\n")
                stdout = io.StringIO()

                with redirect_stdout(stdout):
                    status = main(["--apply"], repo_root=repo_root)

                self.assertEqual(1, status)
                self.assertIn(expected, stdout.getvalue())
                self.assertEqual("original cw\n", sentinel.read_text())

    def test_apply_rejects_nonpartitioned_skill_inventories_without_mutation(self):
        cases = {
            "duplicate authored skill": lambda config: config[
                "authored_skills"
            ].append(config["authored_skills"][0]),
            "overlapping inventories": lambda config: config[
                "authored_skills"
            ].append(config["vendored_skills"][0]),
            "incomplete inventories": lambda config: config[
                "authored_skills"
            ].pop(),
        }
        for label, mutate in cases.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as temporary:
                repo_root = Path(temporary)
                self._copy_canonical_inputs(repo_root)
                cw_root = repo_root / "cw"
                cw_root.mkdir()
                (cw_root / "sentinel.txt").write_text("original cw\n")
                self._write_config(repo_root, mutate)

                status = main(["--apply"], repo_root=repo_root)

                self.assertEqual(1, status)
                self.assertEqual(
                    "original cw\n", (cw_root / "sentinel.txt").read_text()
                )

    def test_apply_rejects_escaped_worker_registry_without_mutation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo_root = root / "repo"
            outside = root / "outside"
            repo_root.mkdir()
            outside.mkdir()
            self._copy_canonical_inputs(repo_root)
            cw_root = repo_root / "cw"
            cw_root.mkdir()
            (cw_root / "sentinel.txt").write_text("original cw\n")
            registry = outside / "registry.json"
            registry.write_text('{"workers": []}\n')
            self._write_config(
                repo_root,
                lambda config: config.update({"workers": "../../outside/registry.json"}),
            )

            status = main(["--apply"], repo_root=repo_root)

            self.assertEqual(1, status)
            self.assertEqual("original cw\n", (cw_root / "sentinel.txt").read_text())
            self.assertEqual('{"workers": []}\n', registry.read_text())

    def test_apply_rejects_parent_segments_in_control_paths_without_mutation(self):
        cases = {
            "worker registry": lambda repo_root: self._write_config(
                repo_root,
                lambda config: config.update(
                    {
                        "workers": (
                            "skills/creative-writing-muse/../creative-writing-muse/"
                            "resources/workers/registry.json"
                        )
                    }
                ),
            ),
            "worker prompt": lambda repo_root: (
                lambda path, value: path.write_text(
                    json.dumps(
                        {
                            **value,
                            "workers": [
                                {
                                    **value["workers"][0],
                                    "prompt": "../workers/brainstormer.md",
                                },
                                *value["workers"][1:],
                            ],
                        }
                    )
                    + "\n"
                )
            )(
                repo_root
                / "plugins/creative-writing-skills/skills/creative-writing-muse/"
                "resources/workers/registry.json",
                json.loads(
                    (
                        repo_root
                        / "plugins/creative-writing-skills/skills/creative-writing-muse/"
                        "resources/workers/registry.json"
                    ).read_text()
                ),
            ),
        }
        for label, mutate in cases.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as temporary:
                repo_root = Path(temporary)
                self._copy_canonical_inputs(repo_root)
                cw_root = repo_root / "cw"
                cw_root.mkdir()
                (cw_root / "sentinel.txt").write_text("original cw\n")
                mutate(repo_root)

                status = main(["--apply"], repo_root=repo_root)

                self.assertEqual(1, status)
                self.assertEqual(
                    "original cw\n", (cw_root / "sentinel.txt").read_text()
                )

    def test_apply_rejects_symlinked_marketplace_parent_without_mutation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo_root = root / "repo"
            outside = root / "outside"
            repo_root.mkdir()
            outside.mkdir()
            self._copy_canonical_inputs(repo_root)
            cw_root = repo_root / "cw"
            cw_root.mkdir()
            (cw_root / "sentinel.txt").write_text("original cw\n")
            outside_marketplace = outside / "marketplace.json"
            outside_marketplace.write_text("outside marketplace\n")
            (repo_root / ".claude-plugin").symlink_to(outside, target_is_directory=True)

            status = main(["--apply"], repo_root=repo_root)

            self.assertEqual(1, status)
            self.assertEqual("original cw\n", (cw_root / "sentinel.txt").read_text())
            self.assertEqual("outside marketplace\n", outside_marketplace.read_text())

    def test_apply_rejects_canonical_resource_symlinks_without_mutation(self):
        def markdown_link(repo_root, outside):
            target = outside / "outside.md"
            target.write_text("external Markdown\n")
            link = (
                repo_root
                / "plugins/creative-writing-skills/skills/character-sim/"
                "resources/leak.md"
            )
            link.parent.mkdir()
            link.symlink_to(target)

        def binary_link(repo_root, outside):
            target = outside / "outside.bin"
            target.write_bytes(b"external binary\n")
            link = (
                repo_root
                / "plugins/creative-writing-skills/skills/character-sim/"
                "resources/leak.bin"
            )
            link.parent.mkdir()
            link.symlink_to(target)

        def directory_link(repo_root, outside):
            target = outside / "external-directory"
            target.mkdir()
            (target / "leak.md").write_text("external directory\n")
            link = (
                repo_root
                / "plugins/creative-writing-skills/skills/character-sim/"
                "resources"
            )
            link.symlink_to(target, target_is_directory=True)

        def loop_link(repo_root, outside):
            skill = (
                repo_root
                / "plugins/creative-writing-skills/skills/character-sim"
            )
            (skill / "loop").symlink_to(skill, target_is_directory=True)

        for label, mutate in {
            "Markdown file": markdown_link,
            "binary file": binary_link,
            "directory": directory_link,
            "loop": loop_link,
        }.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                repo_root = root / "repo"
                outside = root / "outside"
                repo_root.mkdir()
                outside.mkdir()
                self._copy_canonical_inputs(repo_root)
                cw_root = repo_root / "cw"
                cw_root.mkdir()
                (cw_root / "sentinel.txt").write_text("original cw\n")
                mutate(repo_root, outside)

                status = main(["--apply"], repo_root=repo_root)

                self.assertEqual(1, status)
                self.assertEqual(
                    "original cw\n", (cw_root / "sentinel.txt").read_text()
                )

    def test_apply_excludes_openai_yaml_symlink_without_following_it(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo_root = root / "repo"
            outside = root / "outside"
            repo_root.mkdir()
            outside.mkdir()
            self._copy_canonical_inputs(repo_root)
            outside_file = outside / "openai.yaml"
            outside_file.write_text("external control data\n")
            agents = (
                repo_root
                / "plugins/creative-writing-skills/skills/character-sim/agents"
            )
            agents.mkdir()
            (agents / "openai.yaml").symlink_to(outside_file)

            status = main(["--apply"], repo_root=repo_root)

            self.assertEqual(0, status)
            self.assertFalse(
                (repo_root / "cw/skills/character-sim/agents/openai.yaml").exists()
            )
            self.assertEqual("external control data\n", outside_file.read_text())

    def test_apply_rejects_special_files_and_directories_used_as_files_before_staging(self):
        def fifo_resource(repo_root):
            resource = (
                repo_root
                / "plugins/creative-writing-skills/skills/character-sim/"
                "resources/channel"
            )
            resource.parent.mkdir()
            os.mkfifo(resource)

        def skill_document_directory(repo_root):
            skill_file = (
                repo_root
                / "plugins/creative-writing-skills/skills/character-sim/SKILL.md"
            )
            skill_file.unlink()
            skill_file.mkdir()

        def worker_prompt_directory(repo_root):
            prompt = (
                repo_root
                / "plugins/creative-writing-skills/skills/creative-writing-muse/"
                "resources/workers/critic.md"
            )
            prompt.unlink()
            prompt.mkdir()

        for label, mutate in {
            "FIFO resource": fifo_resource,
            "SKILL.md directory": skill_document_directory,
            "worker prompt directory": worker_prompt_directory,
        }.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as temporary:
                repo_root = Path(temporary)
                self._copy_canonical_inputs(repo_root)
                cw_root = repo_root / "cw"
                cw_root.mkdir()
                (cw_root / "sentinel.txt").write_text("original cw\n")
                mutate(repo_root)

                status = main(["--apply"], repo_root=repo_root)

                self.assertEqual(1, status)
                self.assertEqual(
                    "original cw\n", (cw_root / "sentinel.txt").read_text()
                )
                self.assertFalse(
                    any(
                        path.name.startswith(".claude-distribution-")
                        for path in repo_root.iterdir()
                    )
                )

    def test_apply_uses_selected_checkout_skill_registry_in_both_directions(self):
        cases = {
            "accept checkout-only skill": ("local-demo", 0),
            "reject live-only skill": ("zoom-out", 1),
        }
        for label, (reference, expected_status) in cases.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as temporary:
                repo_root = Path(temporary)
                self._copy_canonical_inputs(repo_root)
                self._write_config(
                    repo_root,
                    lambda config: [
                        config[key].__setitem__(
                            config[key].index("zoom-out"), "local-demo"
                        )
                        for key in ("canonical_skills", "vendored_skills")
                    ],
                )
                skills_root = repo_root / "plugins/creative-writing-skills/skills"
                source = skills_root / "zoom-out"
                replacement = skills_root / "local-demo"
                source.rename(replacement)
                skill_file = replacement / "SKILL.md"
                text = skill_file.read_text().replace(
                    "name: zoom-out", "name: local-demo", 1
                )
                skill_file.write_text(text + f"\nLoad ${reference}.\n")

                status = main(["--apply"], repo_root=repo_root)

                self.assertEqual(expected_status, status)
                if expected_status == 0:
                    rendered = (
                        repo_root / "cw/skills/local-demo/SKILL.md"
                    ).read_text()
                    self.assertIn("Load /local-demo.", rendered)
                else:
                    self.assertFalse((repo_root / "cw").exists())

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
            self.assertEqual(30, apply_output.getvalue().count("synced skill "))
            self.assertEqual(11, apply_output.getvalue().count("synced agent "))
            marketplace = json.loads(marketplace_path.read_text())
            canonical_manifest = json.loads(
                (
                    repo_root
                    / "plugins/creative-writing-skills/.codex-plugin/plugin.json"
                ).read_text()
            )
            self.assertEqual("creative-writing-skills", marketplace["name"])
            self.assertEqual({"name": "InkyQuill"}, marketplace["owner"])
            self.assertEqual(
                canonical_manifest["version"], marketplace["metadata"]["version"]
            )
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

    def test_check_reports_typed_inventory_drift_in_path_order(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary)
            self._copy_canonical_inputs(repo_root)
            self.assertEqual(0, main(["--apply"], repo_root=repo_root))
            cw_root = repo_root / "cw"
            (cw_root / "extra-link").symlink_to(repo_root / "outside")
            mode_changed = cw_root / "skills/character-sim/SKILL.md"
            mode_changed.chmod(0o755)
            (cw_root / "skills/obsolete-empty").mkdir()
            (cw_root / "skills/story-memory/SKILL.md").unlink()
            wrong_type = cw_root / "skills/zoom-out/SKILL.md"
            wrong_type.unlink()
            wrong_type.mkdir()

            output = io.StringIO()
            with redirect_stdout(output):
                status = main(["--check"], repo_root=repo_root)

            self.assertEqual(1, status)
            self.assertEqual(
                [
                    "unexpected generated symlink: cw/extra-link",
                    "changed generated file: cw/skills/character-sim/SKILL.md "
                    "(mode 0644 != 0755)",
                    "unexpected generated directory: cw/skills/obsolete-empty",
                    "missing generated file: cw/skills/story-memory/SKILL.md",
                    "changed generated path: cw/skills/zoom-out/SKILL.md "
                    "(expected file, found directory)",
                ],
                output.getvalue().splitlines(),
            )

    def test_check_classifies_marketplace_symlink_as_changed_type(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary)
            self._copy_canonical_inputs(repo_root)
            self.assertEqual(0, main(["--apply"], repo_root=repo_root))
            marketplace = repo_root / ".claude-plugin/marketplace.json"
            marketplace.unlink()
            outside = repo_root / "outside-marketplace.json"
            outside.write_text("outside\n")
            marketplace.symlink_to(outside)

            output = io.StringIO()
            with redirect_stdout(output):
                status = main(["--check"], repo_root=repo_root)

            self.assertEqual(1, status)
            self.assertEqual(
                "changed generated path: .claude-plugin/marketplace.json "
                "(expected file, found symlink)\n",
                output.getvalue(),
            )

    def test_check_reports_zcode_marketplace_drift(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary)
            self._copy_canonical_inputs(repo_root)
            self.assertEqual(0, main(["--apply"], repo_root=repo_root))
            zcode_marketplace = repo_root / "marketplace.json"
            zcode_manifest = repo_root / "cw/.zcode-plugin/plugin.json"
            self.assertTrue(zcode_marketplace.is_file())
            self.assertEqual(
                json.loads(zcode_manifest.read_text()),
                json.loads((repo_root / "cw/.claude-plugin/plugin.json").read_text()),
            )
            canonical_manifest = json.loads(
                (
                    repo_root
                    / "plugins/creative-writing-skills/.codex-plugin/plugin.json"
                ).read_text()
            )
            generated = json.loads(zcode_marketplace.read_text())
            self.assertEqual("creative-writing-skills", generated["name"])
            self.assertEqual(
                canonical_manifest["description"], generated["description"]
            )
            self.assertEqual(
                canonical_manifest["version"],
                generated["plugins"][0]["version"],
            )
            self.assertEqual("./cw", generated["plugins"][0]["source"])
            self.assertEqual(
                json.loads((repo_root / "config/distribution.json").read_text())["zcode"][
                    "icon"
                ],
                generated["plugins"][0]["icon"],
            )
            claude_marketplace = json.loads(
                (repo_root / ".claude-plugin/marketplace.json").read_text()
            )
            self.assertNotIn("icon", claude_marketplace["plugins"][0])
            zcode_marketplace.write_text("{}\n")

            output = io.StringIO()
            with redirect_stdout(output):
                status = main(["--check"], repo_root=repo_root)

            self.assertEqual(1, status)
            self.assertEqual(
                "changed generated file: marketplace.json\n",
                output.getvalue(),
            )

    def test_apply_rejects_noncanonical_zcode_config_without_mutation(self):
        cases = {
            "absolute marketplace": lambda config, outside: config["zcode"].update(
                {"marketplace": str(outside / "marketplace.json")}
            ),
            "parent-relative marketplace": lambda config, outside: config[
                "zcode"
            ].update({"marketplace": "../outside/marketplace.json"}),
            "nonexistent manifest": lambda config, outside: config["zcode"].update(
                {"manifest": ".zcode-marketplace/plugin.json"}
            ),
            "root mismatch": lambda config, outside: config["zcode"].update(
                {"root": "cw-copy"}
            ),
            "extra ZCode key": lambda config, outside: config["zcode"].update(
                {"extra": "value"}
            ),
            "relative icon": lambda config, outside: config["zcode"].update(
                {"icon": "./assets/scroll-quill.png"}
            ),
        }
        for label, mutate in cases.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                repo_root = root / "repo"
                outside = root / "outside"
                repo_root.mkdir()
                outside.mkdir()
                self._copy_canonical_inputs(repo_root)
                cw_root = repo_root / "cw"
                cw_root.mkdir()
                (cw_root / "sentinel.txt").write_text("original cw\n")
                (outside / "marketplace.json").write_text("outside marketplace\n")
                self._write_config(
                    repo_root,
                    lambda config: mutate(config, outside),
                )

                status = main(["--apply"], repo_root=repo_root)

                self.assertEqual(1, status)
                self.assertEqual(
                    "original cw\n", (cw_root / "sentinel.txt").read_text()
                )
                self.assertFalse((repo_root / "marketplace.json").exists())
                self.assertEqual(
                    "outside marketplace\n",
                    (outside / "marketplace.json").read_text(),
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
                        (
                            ("cw", candidate_cw, cw_root),
                            ("claude-marketplace", candidate_marketplace, marketplace_path),
                        ),
                        transaction_root,
                    )

            self.assertEqual("old cw\n", (cw_root / "value.txt").read_text())
            self.assertEqual("old marketplace\n", marketplace_path.read_text())

    def test_transaction_attempts_both_restores_and_retains_failed_backups(self):
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
            previous_cw = transaction_root / "previous-cw"
            previous_marketplace = transaction_root / "previous-claude-marketplace"
            real_replace = os.replace

            def fail_forward_and_restores(source, destination):
                source = Path(source)
                destination = Path(destination)
                if source == candidate_marketplace and destination == marketplace_path:
                    raise OSError("injected marketplace install failure")
                if source == previous_marketplace and destination == marketplace_path:
                    raise OSError("injected marketplace restore failure")
                if source == previous_cw and destination == cw_root:
                    raise OSError("injected cw restore failure")
                return real_replace(source, destination)

            with patch(
                "scripts.sync_claude_distribution.os.replace",
                side_effect=fail_forward_and_restores,
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "claude-marketplace restore failure.*cw restore failure",
                ):
                    _commit_candidate(
                        (
                            ("cw", candidate_cw, cw_root),
                            ("claude-marketplace", candidate_marketplace, marketplace_path),
                        ),
                        transaction_root,
                    )

            self.assertTrue(previous_cw.is_dir())
            self.assertEqual("old cw\n", (previous_cw / "value.txt").read_text())
            self.assertTrue(previous_marketplace.is_file())
            self.assertEqual("old marketplace\n", previous_marketplace.read_text())

    def test_transaction_preserves_interrupt_semantics_when_restore_fails(self):
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
            previous_cw = transaction_root / "previous-cw"
            real_replace = os.replace

            def interrupt_and_fail_restore(source, destination):
                source = Path(source)
                destination = Path(destination)
                if source == candidate_marketplace and destination == marketplace_path:
                    raise KeyboardInterrupt("injected install interrupt")
                if source == previous_cw and destination == cw_root:
                    raise OSError("injected cw restore failure")
                return real_replace(source, destination)

            with patch(
                "scripts.sync_claude_distribution.os.replace",
                side_effect=interrupt_and_fail_restore,
            ):
                with self.assertRaises(KeyboardInterrupt) as caught:
                    _commit_candidate(
                        (
                            ("cw", candidate_cw, cw_root),
                            ("claude-marketplace", candidate_marketplace, marketplace_path),
                        ),
                        transaction_root,
                    )

            self.assertIn("cw restore failure", str(caught.exception))
            self.assertEqual(
                "old cw\n", (previous_cw / "value.txt").read_text()
            )

    def test_transaction_keeps_restoring_the_other_member_after_one_restore_fails(self):
        for failed_restore in ("cw", "claude-marketplace"):
            with self.subTest(failed_restore=failed_restore), tempfile.TemporaryDirectory() as temporary:
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
                previous_cw = transaction_root / "previous-cw"
                previous_marketplace = transaction_root / "previous-claude-marketplace"
                real_replace = os.replace

                def fail_install_and_one_restore(source, destination):
                    source = Path(source)
                    destination = Path(destination)
                    if source == candidate_marketplace and destination == marketplace_path:
                        raise OSError("injected marketplace install failure")
                    if failed_restore == "cw" and source == previous_cw:
                        raise OSError("injected cw restore failure")
                    if failed_restore == "claude-marketplace" and source == previous_marketplace:
                        raise OSError("injected marketplace restore failure")
                    return real_replace(source, destination)

                with patch(
                    "scripts.sync_claude_distribution.os.replace",
                    side_effect=fail_install_and_one_restore,
                ):
                    with self.assertRaisesRegex(
                        ValueError, f"{failed_restore} restore failure"
                    ):
                        _commit_candidate(
                            (
                                ("cw", candidate_cw, cw_root),
                                ("claude-marketplace", candidate_marketplace, marketplace_path),
                            ),
                            transaction_root,
                        )

                if failed_restore == "cw":
                    self.assertEqual(
                        "old marketplace\n", marketplace_path.read_text()
                    )
                    self.assertEqual(
                        "old cw\n", (previous_cw / "value.txt").read_text()
                    )
                else:
                    self.assertEqual("old cw\n", (cw_root / "value.txt").read_text())
                    self.assertEqual(
                        "old marketplace\n", previous_marketplace.read_text()
                    )

    def test_apply_retains_recovery_directory_when_a_restore_fails(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo_root = Path(temporary)
            self._copy_canonical_inputs(repo_root)
            cw_root = repo_root / "cw"
            cw_root.mkdir()
            (cw_root / "sentinel.txt").write_text("old cw\n")
            marketplace_path = repo_root / ".claude-plugin/marketplace.json"
            marketplace_path.parent.mkdir()
            marketplace_path.write_text("old marketplace\n")
            real_replace = os.replace

            def fail_marketplace_install_and_restore(source, destination):
                source = Path(source)
                destination = Path(destination)
                if (
                    source.name == "candidate-claude-marketplace.json"
                    and destination == marketplace_path
                ):
                    raise OSError("injected marketplace install failure")
                if (
                    source.name == "previous-claude-marketplace"
                    and destination == marketplace_path
                ):
                    raise OSError("injected marketplace restore failure")
                return real_replace(source, destination)

            output = io.StringIO()
            with patch(
                "scripts.sync_claude_distribution.os.replace",
                side_effect=fail_marketplace_install_and_restore,
            ), redirect_stdout(output):
                status = main(["--apply"], repo_root=repo_root)

            self.assertEqual(1, status)
            self.assertEqual("old cw\n", (cw_root / "sentinel.txt").read_text())
            recovery_directories = sorted(
                path
                for path in repo_root.iterdir()
                if path.name.startswith(".claude-distribution-")
            )
            self.assertEqual(1, len(recovery_directories))
            backup = recovery_directories[0] / "previous-claude-marketplace"
            self.assertEqual("old marketplace\n", backup.read_text())
            self.assertIn(str(recovery_directories[0]), output.getvalue())

    def test_transaction_rolls_back_each_forward_rename_for_absent_and_present_members(self):
        for cw_present in (False, True):
            for marketplace_present in (False, True):
                operations = ["install cw", "install marketplace"]
                if cw_present:
                    operations.insert(0, "backup cw")
                if marketplace_present:
                    operations.insert(-1, "backup marketplace")
                for failed_operation in operations:
                    with (
                        self.subTest(
                            cw_present=cw_present,
                            marketplace_present=marketplace_present,
                            failed_operation=failed_operation,
                        ),
                        tempfile.TemporaryDirectory() as temporary,
                    ):
                        root = Path(temporary)
                        cw_root = root / "cw"
                        if cw_present:
                            cw_root.mkdir()
                            (cw_root / "value.txt").write_text("old cw\n")
                        candidate_cw = root / "candidate-cw"
                        candidate_cw.mkdir()
                        (candidate_cw / "value.txt").write_text("new cw\n")
                        marketplace_path = root / "marketplace.json"
                        if marketplace_present:
                            marketplace_path.write_text("old marketplace\n")
                        candidate_marketplace = root / "candidate-marketplace.json"
                        candidate_marketplace.write_text("new marketplace\n")
                        transaction_root = root / "transaction"
                        transaction_root.mkdir()
                        previous_cw = transaction_root / "previous-cw"
                        previous_marketplace = (
                            transaction_root / "previous-claude-marketplace"
                        )
                        real_replace = os.replace
                        operation_paths = {
                            "backup cw": (cw_root, previous_cw),
                            "install cw": (candidate_cw, cw_root),
                            "backup marketplace": (
                                marketplace_path,
                                previous_marketplace,
                            ),
                            "install marketplace": (
                                candidate_marketplace,
                                marketplace_path,
                            ),
                        }

                        def fail_selected(source, destination):
                            pair = (Path(source), Path(destination))
                            if pair == operation_paths[failed_operation]:
                                raise OSError(f"injected {failed_operation} failure")
                            return real_replace(source, destination)

                        with patch(
                            "scripts.sync_claude_distribution.os.replace",
                            side_effect=fail_selected,
                        ):
                            with self.assertRaisesRegex(
                                OSError, f"injected {failed_operation} failure"
                            ):
                                _commit_candidate(
                                    (
                                        ("cw", candidate_cw, cw_root),
                                        ("claude-marketplace", candidate_marketplace, marketplace_path),
                                    ),
                                    transaction_root,
                                )

                        self.assertEqual(cw_present, cw_root.exists())
                        if cw_present:
                            self.assertEqual(
                                "old cw\n", (cw_root / "value.txt").read_text()
                            )
                        self.assertEqual(
                            marketplace_present, marketplace_path.exists()
                        )
                        if marketplace_present:
                            self.assertEqual(
                                "old marketplace\n", marketplace_path.read_text()
                            )


if __name__ == "__main__":
    unittest.main()

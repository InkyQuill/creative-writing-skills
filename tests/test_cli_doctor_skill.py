import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = (
    ROOT
    / "plugins"
    / "creative-writing-skills"
    / "skills"
    / "cli-doctor"
)
SKILL = SKILL_ROOT / "SKILL.md"
LAUNCHER_SETUP = SKILL_ROOT / "resources" / "launcher-setup.md"


def all_runtime_markdown() -> str:
    return "\n".join(
        path.read_text(encoding="utf-8") for path in (SKILL, LAUNCHER_SETUP)
    )


class CliDoctorSkillTests(unittest.TestCase):
    def test_skill_has_valid_identity_and_routes_to_launcher_details(self):
        text = SKILL.read_text(encoding="utf-8")
        self.assertRegex(text, r"(?m)^---\nname: cli-doctor\ndescription: .+\n---$")
        self.assertTrue(LAUNCHER_SETUP.is_file())
        self.assertIn("resources/launcher-setup.md", text)

    def test_diagnosis_precedes_any_setup_offer(self):
        text = SKILL.read_text(encoding="utf-8")
        diagnosis = text.index("Diagnose first")
        setup = text.index("Only after the active task")
        self.assertLess(diagnosis, setup)
        self.assertRegex(text, r"(?is)diagnos.{0,120}(first|before).{0,180}(launcher|setup)")

    def test_resolves_and_tests_exact_bundled_entrypoint(self):
        text = SKILL.read_text(encoding="utf-8")
        self.assertRegex(text, r"(?is)resolve.{0,180}(installed|skill).{0,220}project-maintenance")
        self.assertIn("resources/cli/cw.py", text)
        self.assertRegex(text, r"(?is)test.{0,160}exact bundled entrypoint")

    def test_direct_python_invocation_is_default_for_active_task(self):
        text = all_runtime_markdown()
        self.assertRegex(text, r"python3 .*resources/cli/cw\.py")
        self.assertIn("Python 3.10", text)
        self.assertRegex(
            SKILL.read_text(encoding="utf-8"),
            r"(?is)(default|use).{0,180}direct.{0,180}(current|active) task",
        )

    def test_all_supported_platforms_have_direct_invocations(self):
        text = SKILL.read_text(encoding="utf-8")
        for platform in ("Windows", "macOS", "Linux"):
            self.assertIn(platform, text)
        self.assertRegex(text, r"py -3 .*resources\\cli\\cw\.py")
        self.assertNotIn("py -3.10", text)
        self.assertRegex(text, r"python3 .*resources/cli/cw\.py")

    def test_zero_configuration_does_not_install_or_copy_runtime(self):
        text = all_runtime_markdown()
        self.assertRegex(text, r"(?is)no third-party (packages|dependencies)")
        self.assertRegex(text, r"(?is)(do not|never).{0,100}cop(y|ied).{0,100}(story|project)")
        self.assertNotRegex(text, r"(?i)(pip|uv|poetry) install")

    def test_persistent_changes_require_preview_and_explicit_approval(self):
        text = all_runtime_markdown()
        self.assertRegex(
            text,
            r"(?is)preview.{0,260}(PATH|profile|launcher)",
        )
        self.assertRegex(
            text,
            r"(?is)explicit (approval|permission).{0,220}(persistent launcher|PATH|profile)",
        )
        self.assertRegex(text, r"(?is)(never|do not).{0,100}(silently|without approval).{0,120}(profile|PATH)")

    def test_main_skill_keeps_persistent_setup_in_resource(self):
        main = SKILL.read_text(encoding="utf-8")
        resource = LAUNCHER_SETUP.read_text(encoding="utf-8")
        self.assertLess(len(main.splitlines()), 60)
        self.assertGreater(len(resource), 200)
        self.assertIn("launcher-setup.md", main)

    def test_launcher_is_executable_wrapper_not_symlink_to_cw_py(self):
        text = LAUNCHER_SETUP.read_text(encoding="utf-8")
        self.assertRegex(text, r"(?is)user-(owned|scoped).{0,120}executable wrapper")
        self.assertNotIn("symlink", text.lower())


if __name__ == "__main__":
    unittest.main()

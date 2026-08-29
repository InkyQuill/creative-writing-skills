import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = (
    ROOT
    / "plugins"
    / "creative-writing-skills"
    / "skills"
    / "project-feedback"
)
SKILL = SKILL_ROOT / "SKILL.md"
REPORTING = SKILL_ROOT / "resources" / "issue-reporting.md"


def all_runtime_markdown() -> str:
    return "\n".join(
        path.read_text(encoding="utf-8") for path in (SKILL, REPORTING)
    )


class ProjectFeedbackSkillTests(unittest.TestCase):
    def test_skill_identity_and_trigger_are_discriminating(self):
        text = SKILL.read_text(encoding="utf-8")
        self.assertRegex(text, r"(?m)^---\nname: project-feedback\ndescription: .+\n---$")
        description = text.split("---", 2)[1]
        for trigger in ("bug", "regression", "broken script", "generated", "instruction"):
            self.assertIn(trigger, description.lower())
        self.assertIn("https://github.com/InkyQuill/creative-writing-skills/issues", text)

    def test_feedback_never_replaces_or_unnecessarily_blocks_primary_work(self):
        text = all_runtime_markdown()
        self.assertRegex(text, r"(?is)continue.{0,160}(primary|actual).{0,80}(task|work)")
        self.assertRegex(text, r"(?is)(never|do not).{0,120}(replace|unnecessarily block).{0,100}(primary|actual)")
        self.assertRegex(text, r"(?is)do not file feedback.{0,160}(ordinary story-content ambiguity|author preference)")

    def test_scope_includes_all_local_canonical_skills_but_excludes_upstream_tools(self):
        text = all_runtime_markdown()
        lowered = re.sub(r"\s+", " ", text.lower().replace("`", ""))
        for owned in (
            "canonical creative writing skills plugin skills",
            "bundled cw cli",
            "generated claude or zcode distribution",
            "project docs and contracts",
            "authored and internal skills such as story-memory",
            "pinned or adapted vendored copy of a skill such as llm-writing",
            "packaging or distribution of that local copy",
        ):
            self.assertIn(owned, lowered)
        for excluded in (
            "superpowers",
            "codex",
            "claude",
            "zcode",
            "github cli (`gh`)",
            "skill or plugin not shipped by this repository",
            "upstream defect in the original project from which a skill was vendored",
        ):
            self.assertIn(excluded.replace("`", ""), lowered)
        self.assertRegex(
            text,
            r"(?is)upstream defect.{0,240}out of scope.{0,220}(pinned copy|adaptation|packaging|distribution)",
        )
        self.assertRegex(
            text,
            r"(?is)if ownership is unclear.{0,100}diagnose.{0,100}(do not|don't).{0,80}file",
        )

    def test_duplicate_search_covers_open_and_closed_and_inspects_matches(self):
        text = all_runtime_markdown()
        self.assertRegex(text, r"(?is)search.{0,120}(both )?open and closed.{0,160}(before|prior)")
        self.assertRegex(text, r"(?is)inspect.{0,120}(plausible|candidate|matching).{0,120}issue")
        self.assertRegex(text, r"(?is)(not|never).{0,80}(title alone|title-only)")
        self.assertRegex(text, r"(?is)regression.{0,160}(link|reference).{0,100}(prior|existing)")

    def test_creation_requires_verified_high_confidence_evidence(self):
        text = all_runtime_markdown()
        for requirement in (
            "project ownership",
            "reproducible",
            "local setup",
            "transient external",
            "no existing issue",
            "actionable body",
        ):
            self.assertIn(requirement, text.lower())
        self.assertRegex(text, r"(?is)verify.{0,160}(local evidence|instructions|prose).{0,260}(before|creation|create)")

    def test_high_confidence_creation_is_automatic_without_redundant_confirmation(self):
        text = all_runtime_markdown()
        self.assertRegex(text, r"(?is)(confidence|high-confidence).{0,160}(capability|capable).{0,180}create")
        self.assertRegex(text, r"(?is)without.{0,80}(redundant|additional).{0,40}(confirmation|approval)")
        self.assertRegex(text, r"(?is)ask.{0,100}only.{0,160}(ambiguity|disclosure|intent)")
        self.assertRegex(text, r"(?is)report.{0,80}(created|new).{0,80}url")

    def test_capability_checks_do_not_require_maintainer_access(self):
        text = all_runtime_markdown()
        lowered = text.lower()
        for capability in ("gh", "authenticated", "issues enabled"):
            self.assertIn(capability, lowered)
        self.assertRegex(text, r"(?is)repository.{0,20}(is )?reachable")
        self.assertRegex(text, r"(?is)(maintainer|write).{0,120}(not required|does not determine|do not require)")
        self.assertRegex(text, r"(?is)(ordinary|any) authenticated.{0,80}(user|account).{0,100}(create|file).{0,40}issue")

    def test_missing_capability_falls_back_once_without_login_or_retry_loop(self):
        text = all_runtime_markdown()
        for failure in ("gh", "authentication", "network", "permission", "creation fails"):
            self.assertIn(failure, text.lower())
        self.assertRegex(text, r"(?is)(do not|never).{0,100}(request|ask for|prompt for).{0,60}(login|authentication)")
        self.assertRegex(text, r"(?is)(do not|never).{0,80}(loop|repeatedly retry|retry loop)")
        self.assertRegex(text, r"(?is)(work/reviews|task/report).{0,220}(draft|inline)")
        self.assertRegex(text, r"(?is)(exact|specific).{0,80}failure.{0,180}(location|content)")

    def test_privacy_and_redaction_boundaries_are_explicit(self):
        text = all_runtime_markdown().lower()
        for secret in (
            "manuscript prose",
            "<hidden>",
            "private story facts",
            "credentials",
            "tokens",
            "cookies",
            "environment dumps",
            "absolute paths",
            "usernames",
        ):
            self.assertIn(secret, text)
        self.assertIn("redact", text)

    def test_existing_issues_are_never_mutated_automatically(self):
        text = all_runtime_markdown()
        self.assertRegex(
            text,
            r"(?is)never.{0,100}(comment|close|reopen|edit).{0,160}existing issue.{0,160}(automatically|separate)",
        )
        self.assertRegex(text, r"(?is)(labels|milestones|assignees|severity).{0,180}(convention|do not)")

    def test_issue_body_is_actionable_and_safe_command_uses_body_file(self):
        text = REPORTING.read_text(encoding="utf-8")
        for section in (
            "Affected component",
            "Minimal reproduction",
            "Expected behavior",
            "Actual behavior",
            "Sanitized evidence",
            "Impact",
            "Environment",
        ):
            self.assertIn(section, text)
        self.assertIn("--body-file", text)
        self.assertRegex(text, r"(?is)(argument vector|without shell interpolation)")

    def test_all_local_markdown_links_resolve_and_only_tracker_is_external(self):
        markdown_files = sorted(SKILL_ROOT.rglob("*.md"))
        self.assertEqual(markdown_files, [SKILL, REPORTING])
        external_links = []
        for source in markdown_files:
            text = source.read_text(encoding="utf-8")
            for target in re.findall(r"\[[^]]+\]\(([^)]+)\)", text):
                if target.startswith(("https://", "http://")):
                    external_links.append(target)
                else:
                    self.assertFalse(Path(target).is_absolute(), target)
                    self.assertTrue((source.parent / target).resolve().is_file(), target)
        self.assertEqual(
            external_links,
            ["https://github.com/InkyQuill/creative-writing-skills/issues"],
        )


if __name__ == "__main__":
    unittest.main()

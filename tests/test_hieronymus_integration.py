import json
import unittest
from pathlib import Path

from scripts.distribution import split_frontmatter


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "creative-writing-skills"
SKILL = PLUGIN / "skills" / "hieronymus-integration"


class HieronymusIntegrationTests(unittest.TestCase):
    def test_skill_has_exact_identity_and_local_resources(self):
        metadata, body = split_frontmatter((SKILL / "SKILL.md").read_text())
        self.assertEqual("hieronymus-integration", metadata["name"])
        self.assertEqual(
            "Apply the project's free-text memory agreement when literary work uses "
            "Hieronymus alongside or instead of file memory. Load when the user requests "
            "Hieronymus or the project agreement or binding refers to it; remain optional "
            "when its tools are unavailable.",
            str(metadata["description"]).strip(),
        )
        for resource in ("workflow.md", "delivery.md"):
            self.assertTrue((SKILL / "resources" / resource).is_file())
            self.assertIn(f"resources/{resource}", body)

    def test_workflow_preserves_optional_free_text_contract(self):
        text = (SKILL / "resources" / "workflow.md").read_text()
        normalized = " ".join(text.split())
        required = (
            "free-text",
            "files are primary",
            "Hieronymus is supplemental",
            "tool availability",
            "trust",
            "write authorization",
            "no mandatory mirror",
            "current user instruction",
            "local exception",
            "actual status",
            "actual provenance",
            "one leading workflow",
        )
        for phrase in required:
            self.assertIn(phrase, normalized)

    def test_capability_discovery_uses_live_nested_status_without_overclaiming(self):
        text = (SKILL / "resources" / "workflow.md").read_text()
        normalized = " ".join(text.split())
        for phrase in (
            "hiero status --json",
            "status.instance_id",
            "status.semantic.state",
            "status.readiness",
            "hieronymus_status",
            "service availability",
            "does not start or repair",
            "degraded provider",
            "actual tool outcome",
        ):
            self.assertIn(phrase, normalized)
        self.assertIn("`running: true` is not proof", normalized)

    def test_delivery_uses_public_tools_and_safe_retry_contract(self):
        text = (SKILL / "resources" / "delivery.md").read_text()
        normalized = " ".join(text.split())
        for tool in (
            "hieronymus_recall",
            "hieronymus_rag_search",
            "hieronymus_short_term_add",
            "hieronymus_short_term_add_batch",
            "hieronymus_evidence_capture",
            "hieronymus_decide",
            "hieronymus_correct",
        ):
            self.assertIn(tool, normalized)
        for phrase in (
            "actual returned IDs",
            "actual returned revisions",
            "advisory observation",
            "activated rule",
            "authentic correction",
            "fake host event",
            "inspect through available public read tools",
            "do not resend blindly",
            "no supported idempotency key",
            "Never probe a mutating tool",
            "needed schema is unavailable",
            "Keep a rejected intended disposition unresolved",
            "additional advisory copy is a separate mutation",
            "Existing authorization is sufficient",
            "operation UUID",
            "unresolved",
        ):
            self.assertIn(phrase, normalized)
        self.assertNotIn('"idempotency_key"', text)

    def test_evidence_capture_recipe_matches_discriminated_schema_and_response(self):
        text = (SKILL / "resources" / "delivery.md").read_text()
        capture = text.split("Use `hieronymus_evidence_capture`", 1)[1].split(
            "For an evidence-grounded learned decision", 1
        )[0]
        normalized = " ".join(capture.split())

        self.assertIn(
            '`{"kind":"file","path":...,"expected_hash":...}`',
            normalized,
        )
        self.assertIn(
            '`{"kind":"retained","evidence_id":...,"expected_hash":...}`',
            normalized,
        )
        self.assertIn(
            "`reference`, `source_identity`, `selected_text`, "
            "`paragraph_start`, `paragraph_end`, and `paragraph_text`",
            normalized,
        )
        self.assertNotIn("revision", capture.lower())

    def test_existing_skills_route_optional_integration(self):
        routed = {
            "creative-writing-muse": ("project agreement", "binding"),
            "story-memory": ("project agreement", "Hieronymus"),
            "project-setup": ("free-text", "Hieronymus"),
            "project-doctor": ("ordinary capability absence", "Hieronymus"),
        }
        for name, phrases in routed.items():
            text = (PLUGIN / "skills" / name / "SKILL.md").read_text()
            normalized = " ".join(text.split())
            self.assertIn("$hieronymus-integration", normalized, name)
            for phrase in phrases:
                self.assertIn(phrase, normalized, name)

    def test_translation_skills_and_resources_apply_the_memory_agreement(self):
        files = {
            "literary-translation/SKILL.md": (
                "$hieronymus-integration",
                "memory agreement",
                "without requiring Markdown memory records",
            ),
            "translation-memory/SKILL.md": (
                "$hieronymus-integration",
                "memory agreement",
                "does not require a Markdown copy",
            ),
            "translation-review/SKILL.md": (
                "$hieronymus-integration",
                "memory agreement",
                "does not require a Markdown record",
            ),
            "literary-translation/resources/workflow.md": (
                "accepted prose for voice",
                "external-memory-observed",
                "unknown",
            ),
            "translation-memory/resources/records.md": (
                "selected store",
                "no mandatory Markdown mirror",
                "source revision",
            ),
            "translation-review/resources/review-rubric.md": (
                "external-memory-observed",
                "known changed or missing",
                "historical unknown",
            ),
        }
        for relative, phrases in files.items():
            text = (PLUGIN / "skills" / relative).read_text()
            normalized = " ".join(text.split())
            for phrase in phrases:
                self.assertIn(phrase, normalized, relative)

    def test_workflow_applies_new_instructions_and_transfers_selected_records_only(self):
        workflow = " ".join(
            (SKILL / "resources" / "workflow.md").read_text().split()
        )
        for phrase in (
            "Apply a new user instruction in its stated scope immediately.",
            "Persist a durable change in the nearest project instructions",
            "preserving independent conditions",
            "do not globalize a local exception",
            "Changing trust does not prove old records were transferred.",
            "For an authorized transfer, inventory the selected records and their provenance",
            "retain returned IDs",
            "reconcile counts, scopes, dispositions and unresolved conflicts",
            "Report partial completion.",
            "Do not delete originals or create an ongoing mirror",
        ):
            self.assertIn(phrase, workflow)

    def test_delivery_carries_direction_and_external_reference_evidence(self):
        delivery = " ".join(
            (SKILL / "resources" / "delivery.md").read_text().split()
        )
        for phrase in (
            "story_scopes",
            "cws:direction:<direction-id>",
            "applicability.scope_predicates",
            "provider",
            "namespace",
            "record_kind",
            "record_id",
            "revision",
            '{"unverified":"<technical reason>"}',
            "observed arrays accept strict references only",
            "status.instance_id",
            "external-memory-observed",
            "exact pending result",
        ):
            self.assertIn(phrase, delivery)

    def test_inventory_adds_one_authored_skill_without_vendor_change(self):
        config = json.loads((ROOT / "config" / "distribution.json").read_text())
        self.assertEqual(36, len(config["canonical_skills"]))
        self.assertEqual(26, len(config["authored_skills"]))
        self.assertIn("hieronymus-integration", config["canonical_skills"])
        self.assertIn("hieronymus-integration", config["authored_skills"])
        self.assertEqual(
            {
                "decision-grill",
                "information-hierarchy",
                "intent-modeling",
                "knowledge-layers",
                "llm-writing",
                "md-validation",
                "qi-layer",
                "reflect",
                "structured-artifact",
                "zoom-out",
            },
            set(config["vendored_skills"]),
        )

    def test_plugin_manifest_has_no_required_hieronymus_server(self):
        manifest = json.loads((PLUGIN / ".codex-plugin" / "plugin.json").read_text())
        self.assertNotIn("hieronymus", json.dumps(manifest).lower())

    def test_workflow_fixture_covers_named_acceptance_cases(self):
        scenarios = json.loads(
            (ROOT / "tests" / "fixtures" / "hieronymus-workflows.json").read_text()
        )
        expected_ids = {
            "no-h-installation",
            "h-without-cws-installed",
            "no-agreement-clause",
            "free-text-mixed-agreement",
            "in-session-local-exception",
            "durable-preference-change",
            "h-replaces-memory",
            "service-unavailable",
            "partial-uncertain-write",
            "multiple-language-directions",
            "stale-source-or-new-h-rule",
            "tagged-information",
            "imported-accepted-markdown-rule",
            "direct-h-translate-versus-muse",
            "reverse-preference-mid-task",
            "selected-partial-transfer-conflict",
        }
        self.assertEqual(expected_ids, {item["id"] for item in scenarios})
        self.assertEqual(16, len(scenarios))
        required = {
            "id",
            "agreement",
            "user_message",
            "available_tools",
            "observed_results",
            "expected_actions",
            "forbidden_actions",
        }
        for item in scenarios:
            self.assertEqual(required, set(item), item["id"])
            for field in (
                "available_tools",
                "observed_results",
                "expected_actions",
                "forbidden_actions",
            ):
                self.assertIsInstance(item[field], list, (item["id"], field))

        by_id = {item["id"]: item for item in scenarios}
        durable = by_id["durable-preference-change"]
        self.assertTrue(
            any(
                "preserving unrelated instructions" in action
                for action in durable["expected_actions"]
            )
        )
        transfer = by_id["selected-partial-transfer-conflict"]
        self.assertTrue(
            any("actual IDs" in action for action in transfer["expected_actions"])
        )
        self.assertTrue(
            any(
                "unresolved conflict" in action
                for action in transfer["expected_actions"]
            )
        )

    def test_generated_distribution_contains_integration_skill(self):
        generated = ROOT / "cw" / "skills" / "hieronymus-integration"
        self.assertTrue((generated / "SKILL.md").is_file())
        self.assertTrue((generated / "resources" / "workflow.md").is_file())
        self.assertTrue((generated / "resources" / "delivery.md").is_file())


if __name__ == "__main__":
    unittest.main()

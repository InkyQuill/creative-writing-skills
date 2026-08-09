import json
import unittest
from pathlib import Path

from scripts.distribution import (
    PLUGIN_ROOT,
    REPO_ROOT,
    extract_skill_references,
    load_json,
    split_frontmatter,
)


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

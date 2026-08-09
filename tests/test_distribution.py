import json
import re
import unittest
from pathlib import Path

from scripts.distribution import (
    PLUGIN_ROOT,
    REPO_ROOT,
    extract_skill_references,
    load_json,
    map_outside_fences,
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


class DistributionScaffoldTests(unittest.TestCase):
    def test_worker_registry_is_complete_and_resolvable(self):
        registry_path = PLUGIN_ROOT / "skills" / "creative-writing-muse" / "resources" / "workers" / "registry.json"
        registry = load_json(registry_path)
        self.assertEqual({item["name"] for item in registry["workers"]}, EXPECTED_WORKERS)
        canonical = set(load_json(REPO_ROOT / "config" / "distribution.json")["canonical_skills"])
        for item in registry["workers"]:
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

    def test_review_workers_are_read_only(self):
        registry = load_json(PLUGIN_ROOT / "skills" / "creative-writing-muse" / "resources" / "workers" / "registry.json")
        access = {item["name"]: item["access"] for item in registry["workers"]}
        for name in {"character-sim", "continuity-checker", "critic", "editor", "reader-sim"}:
            self.assertEqual(access[name], "read-only")

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
        self.assertEqual(manifest["version"], "0.5.9")
        self.assertEqual(manifest["repository"], "https://github.com/InkyQuill/creative-writing-skills")
        self.assertEqual(manifest["skills"], "./skills/")
        self.assertEqual(marketplace["plugins"][0]["source"]["path"], "./plugins/creative-writing-skills")

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

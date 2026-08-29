import json
import tempfile
import unittest
from pathlib import Path

from . import helpers  # Adds the canonical CLI directory to sys.path.
from cwcli import project, scaffold
from cwcli.checks import kb


def make_project(root: Path) -> project.Project:
    for relative, data in scaffold.render_scaffold("KB", "en").items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    (root / ".creative-writing/context").mkdir(parents=True, exist_ok=True)
    (root / ".creative-writing/transactions").mkdir(parents=True, exist_ok=True)
    return project.discover_project(root)


class KnowledgeCheckTests(unittest.TestCase):
    def test_all_durable_source_kinds_are_accepted_and_work_only_warns(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            model = make_project(root)
            (root / "story/chapters/one.md").write_text("---\nnumber: 1\n---\nStory\n", encoding="utf-8")
            (root / "work/brainstorm/idea.md").write_text("---\n---\nIdea\n", encoding="utf-8")
            tx = root / ".creative-writing/transactions/tx-confirm"
            tx.mkdir()
            (tx / "manifest.json").write_text(json.dumps({"state": "committed"}), encoding="utf-8")
            pages = {
                "story.md": ["story/chapters/one.md"],
                "kb.md": ["kb/world/story.md"],
                "url.md": ["https://example.com/source"],
                "decision.md": ["decision:tx-confirm"],
                "work.md": ["work/brainstorm/idea.md"],
            }
            for name, sources in pages.items():
                rendered = "\n".join(f"  - {source}" for source in sources)
                (root / "kb/world" / name).write_text(f"---\nsources:\n{rendered}\n---\n", encoding="utf-8")

            findings = kb.check_kb(model)

            work = [item for item in findings if item.code == kb.WORK_ONLY_SOURCE]
            self.assertEqual(["kb/world/work.md"], [item.path for item in work])
            self.assertIn("confirm", work[0].next_action.casefold())
            self.assertFalse([item for item in findings if item.code == kb.INVALID_SOURCE])

    def test_missing_invalid_and_malformed_sources_do_not_abort_peers(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            model = make_project(root)
            (root / "kb/world/missing.md").write_text("---\ntitle: Missing\n---\n", encoding="utf-8")
            (root / "kb/world/invalid.md").write_text("---\nsources:\n  - nowhere.md\n---\n", encoding="utf-8")
            (root / "kb/world/broken.md").write_text("---\nsources: [bad]\n---\n", encoding="utf-8")

            codes = {item.code for item in kb.check_kb(model)}

            self.assertTrue({kb.MISSING_SOURCES, kb.INVALID_SOURCE, kb.UNREADABLE_PAGE}.issubset(codes))

    def test_archived_or_nested_kb_pages_are_not_live_durable_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            model = make_project(root)
            (root / "kb/world/archived.md").write_text("---\nstatus: archived\n---\n", encoding="utf-8")
            nested = root / "kb/world/nested"
            nested.mkdir()
            (nested / "project.md").write_text("nested", encoding="utf-8")
            (nested / "page.md").write_text("nested", encoding="utf-8")
            (root / "kb/world/ref.md").write_text(
                "---\nsources:\n  - kb/world/archived.md\n  - kb/world/nested/page.md\n---\n",
                encoding="utf-8",
            )

            invalid = [item for item in kb.check_kb(model) if item.code == kb.INVALID_SOURCE]

            self.assertEqual(2, len(invalid))

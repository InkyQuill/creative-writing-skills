import json
import tempfile
import unittest
from pathlib import Path

from . import helpers  # Adds the canonical CLI directory to sys.path.
from cwcli import project, scaffold, transactions
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
    def test_vocabulary_collisions_and_live_links_to_archived_records(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            model = make_project(root)
            (root / "kb/vocab.md").write_text(
                "---\n---\n| term | meaning |\n|---|---|\n| Élan | one |\n| élan | two |\n",
                encoding="utf-8",
            )
            (root / "kb/world/old.md").write_text("---\nstatus: archived\n---\nOld.\n", encoding="utf-8")
            (root / "kb/world/live.md").write_text(
                "---\nsources:\n  - https://example.com\n---\n[Old](old.md)\n`[ignored](old.md)`\n",
                encoding="utf-8",
            )
            findings = kb.check_kb(model)
            self.assertIn(kb.VOCABULARY_COLLISION, {item.code for item in findings})
            archived = [item for item in findings if item.code == kb.ARCHIVED_REFERENCE]
            self.assertEqual(["kb/world/live.md"], [item.path for item in archived])
            self.assertEqual([5], [item.line for item in archived])
    def test_all_durable_source_kinds_are_accepted_and_work_only_warns(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            model = make_project(root)
            (root / "story/chapters/one.md").write_text("---\nnumber: 1\n---\nStory\n", encoding="utf-8")
            (root / "work/brainstorm/idea.md").write_text("---\n---\nIdea\n", encoding="utf-8")
            store = transactions.TransactionStore(model)
            store.prepare(
                transactions.TransactionPlan(command=("confirm",), changes=(), metadata={}),
                transaction_id="tx-confirm",
            )
            store.write_state("tx-confirm", "committed")
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

    def test_external_opaque_paths_are_durable_without_percent_decoding(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            model = make_project(root)
            (root / "kb/world/ref.md").write_text(
                "---\nsources:\n"
                "  - https://example.com/%FF\n"
                "  - http://example.com/%00\n"
                "  - '%FF.md'\n"
                "---\n",
                encoding="utf-8",
            )

            invalid = [item for item in kb.check_kb(model) if item.code == kb.INVALID_SOURCE]

            self.assertEqual(1, len(invalid))
            self.assertIn("%FF.md", invalid[0].message)

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

    def test_invalid_companions_do_not_hide_work_only_and_bad_paths_stay_contained(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            model = make_project(root)
            (root / "work/brainstorm/idea.md").write_text("---\n---\n", encoding="utf-8")
            (root / "kb/world/ref.md").write_text(
                "---\nsources:\n  - work/brainstorm/idea.md\n  - missing.md\n  - bad%00.md\n  - '%FF.md'\n---\n",
                encoding="utf-8",
            )

            findings = kb.check_kb(model)

            self.assertEqual(1, sum(item.code == kb.WORK_ONLY_SOURCE for item in findings))
            self.assertEqual(3, sum(item.code == kb.INVALID_SOURCE for item in findings))

    def test_generated_story_index_is_not_durable_provenance(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            model = make_project(root)
            (root / "kb/world/ref.md").write_text(
                "---\nsources:\n  - story/chapters/_index.md\n---\n",
                encoding="utf-8",
            )

            findings = kb.check_kb(model)

            self.assertEqual(1, sum(item.code == kb.INVALID_SOURCE for item in findings))

    def test_decision_sources_require_safe_id_and_strict_committed_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            model = make_project(root)
            transaction_root = root / ".creative-writing/transactions"
            for transaction_id in ("blobs", "minimal"):
                transaction = transaction_root / transaction_id
                transaction.mkdir(exist_ok=True)
                (transaction / "manifest.json").write_text(json.dumps({"state": "committed"}), encoding="utf-8")
            malformed = transaction_root / "malformed"
            malformed.mkdir()
            (malformed / "manifest.json").write_text("[]", encoding="utf-8")
            (root / "kb/world/ref.md").write_text(
                "---\nsources:\n  - decision:.\n  - decision:blobs\n  - decision:minimal\n  - decision:malformed\n---\n",
                encoding="utf-8",
            )

            findings = kb.check_kb(model)

            self.assertEqual(4, sum(item.code == kb.INVALID_SOURCE for item in findings))

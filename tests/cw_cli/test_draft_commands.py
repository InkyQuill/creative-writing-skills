import io
import json
import tempfile
import unittest
from pathlib import Path

from . import helpers  # Adds the canonical CLI directory to sys.path.
from cwcli import app, documents, drafts, project, scaffold, transactions
from cwcli.checks import drafts as draft_checks


class DraftCommandTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name) / "project"
        for relative, data in scaffold.render_scaffold("Draft CLI", "en").items():
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        self.target = self.root / "story/chapters/ch-001.md"
        self.target.write_bytes(b"---\nnumber: 1\ntitle: One\n---\nBase\n")

    def run_cli(self, argv: list[str]) -> tuple[int, dict[str, object], str]:
        stdout, stderr = io.StringIO(), io.StringIO()
        status = app.run(argv, cwd=self.root, stdout=stdout, stderr=stderr)
        payload = json.loads(stdout.getvalue()) if stdout.getvalue() else {}
        return status, payload, stderr.getvalue()

    def apply_create(self) -> Path:
        status, payload, error = self.run_cli(
            ["draft", "create", "story/chapters/ch-001.md", "--format", "json", "--apply"]
        )
        self.assertEqual((0, ""), (status, error))
        self.assertEqual("committed", payload["status"])
        return self.root / "work/drafts/ch-001.md"

    def test_create_preview_apply_and_status_preserve_exact_format(self):
        protected_before = self.protected_snapshot()
        status, preview, error = self.run_cli(
            ["draft", "create", "story/chapters/ch-001.md", "--format", "json"]
        )
        self.assertEqual((0, ""), (status, error))
        self.assertEqual("preview", preview["status"])
        self.assertFalse((self.root / "work/drafts/ch-001.md").exists())
        self.assertEqual(protected_before, self.protected_snapshot())

        draft_path = self.apply_create()
        source = draft_path.read_bytes().replace(b"status: working", b"status:\t'working'")
        draft_path.write_bytes(source)
        status, preview, _ = self.run_cli(
            ["draft", "set-status", "work/drafts/ch-001.md", "review", "--format", "json"]
        )
        self.assertEqual(0, status)
        self.assertEqual(source, draft_path.read_bytes())
        status, applied, _ = self.run_cli(
            [
                "draft", "set-status", "work/drafts/ch-001.md", "review",
                "--format", "json", "--apply",
            ]
        )
        self.assertEqual(0, status)
        self.assertEqual("committed", applied["status"])
        self.assertIn(b"status:\t'review'", draft_path.read_bytes())

        status, payload, _ = self.run_cli(
            ["draft", "set-status", "work/drafts/ch-001.md", "published", "--format", "json"]
        )
        self.assertEqual(1, status)
        self.assertEqual("conflict", payload["status"])

    def test_rebase_conflict_json_contains_complete_fragments_and_is_read_only(self):
        draft_path = self.apply_create()
        document = documents.parse_document(draft_path.read_bytes())
        draft_path.write_bytes(
            documents.render_document(
                documents.Document(dict(document.metadata), "Draft\n", document.newline, document.bom)
            )
        )
        self.target.write_bytes(b"---\nnumber: 1\ntitle: One\n---\nAuthor\n")
        before = draft_path.read_bytes()

        status, payload, error = self.run_cli(
            ["draft", "rebase", "work/drafts/ch-001.md", "--format", "json", "--apply"]
        )

        self.assertEqual((1, ""), (status, error))
        self.assertEqual("conflict", payload["status"])
        self.assertEqual(["Base\n"], payload["conflicts"][0]["base"])
        self.assertEqual(["Draft\n"], payload["conflicts"][0]["draft"])
        self.assertEqual(["Author\n"], payload["conflicts"][0]["current"])
        self.assertEqual(before, draft_path.read_bytes())

    def test_clean_rebase_preview_does_not_persist_new_base_revision(self):
        draft_path = self.apply_create()
        document = documents.parse_document(draft_path.read_bytes())
        draft_path.write_bytes(
            documents.render_document(
                documents.Document(dict(document.metadata), "Draft change\n", document.newline, document.bom)
            )
        )
        self.target.write_bytes(
            b"---\nnumber: 1\ntitle: One\n---\nBase\nAuthor addition\n"
        )
        protected_before = self.protected_snapshot()
        status, payload, _ = self.run_cli(
            ["draft", "rebase", "work/drafts/ch-001.md", "--format", "json"]
        )
        self.assertEqual(0, status)
        self.assertEqual("preview", payload["status"])
        self.assertEqual(protected_before, self.protected_snapshot())

    def test_lifecycle_commands_reject_duplicate_active_target_identity(self):
        draft_path = self.apply_create()
        document = documents.parse_document(draft_path.read_bytes())
        metadata = dict(document.metadata)
        metadata["status"] = "ready"
        draft_path.write_bytes(
            documents.render_document(
                documents.Document(
                    metadata, document.body, document.newline, document.bom
                )
            )
        )
        duplicate = self.root / "work/drafts/duplicate.md"
        duplicate.write_bytes(
            documents.render_document(
                documents.Document(
                    {**metadata, "target": "story/chapters/CH-001.md"},
                    document.body,
                    document.newline,
                    document.bom,
                )
            )
        )
        for command in ("accept", "rebase"):
            with self.subTest(command=command):
                status, payload, _ = self.run_cli(
                    ["draft", command, "work/drafts/ch-001.md", "--format", "json"]
                )
                self.assertEqual(1, status)
                self.assertEqual("conflict", payload["status"])
        status, payload, _ = self.run_cli(
            ["draft", "set-status", "work/drafts/ch-001.md", "review", "--format", "json"]
        )
        self.assertEqual(1, status)
        self.assertEqual("conflict", payload["status"])

    def test_accept_allocates_archive_id_before_preview_and_reuses_it_on_apply(self):
        draft_path = self.apply_create()
        document = documents.parse_document(draft_path.read_bytes())
        metadata = dict(document.metadata)
        metadata["status"] = "ready"
        draft_path.write_bytes(
            documents.render_document(
                documents.Document(metadata, "Accepted\n", document.newline, document.bom)
            )
        )
        status, preview, _ = self.run_cli(
            ["draft", "accept", "work/drafts/ch-001.md", "--format", "json"]
        )
        self.assertEqual(0, status)
        preview_id = preview["transaction_id"]
        self.assertTrue(preview_id)
        self.assertTrue(any(preview_id in item["path"] for item in preview["changes"]))

        status, applied, _ = self.run_cli(
            ["draft", "accept", "work/drafts/ch-001.md", "--format", "json", "--apply"]
        )
        self.assertEqual(0, status)
        applied_id = applied["transaction_id"]
        archive = self.root / f"work/archive/ch-001--{applied_id}.md"
        self.assertTrue(archive.exists())
        self.assertEqual(applied_id, documents.parse_document(archive.read_bytes()).metadata["accepted-transaction"])

    def test_invalid_lifecycle_is_conflict_and_checker_completes_across_bad_drafts(self):
        self.apply_create()
        bad = self.root / "work/drafts/bad.md"
        bad.write_bytes(b"---\ntarget: ../outside.md\nstatus: abandoned\n---\n<hidden>x</hidden>\n")
        malformed = self.root / "work/drafts/malformed.md"
        malformed.write_bytes(b"---\ntitle: [unsupported]\n---\n")
        model = project.discover_project(self.root)
        findings = draft_checks.check_drafts(model, transactions.TransactionStore(model))
        codes = {finding.code for finding in findings}
        self.assertTrue({draft_checks.ABANDONED_ACTIVE, draft_checks.INVALID_TARGET, draft_checks.MALFORMED_DRAFT} <= codes)
        self.assertTrue(all(finding.severity == "warning" for finding in findings))

        status, payload, _ = self.run_cli(
            ["draft", "accept", "work/drafts/ch-001.md", "--format", "json", "--apply"]
        )
        self.assertEqual(1, status)
        self.assertEqual("conflict", payload["status"])

        status, report, error = self.run_cli(["check", "drafts", "--format", "json"])
        self.assertEqual((0, ""), (status, error))
        self.assertEqual(["drafts"], report["checks"])

    def test_checker_reports_unsafe_missing_base_and_invalid_utf8_without_stopping(self):
        (self.root / "work/drafts/unsafe.md").write_bytes(
            b"---\ntarget: story/chapters/con.md\nstatus: working\n---\nBody\n"
        )
        (self.root / "work/drafts/no-base.md").write_bytes(
            b"---\ntarget: story/chapters/ch-001.md\nstatus: working\n---\nBody\n"
        )
        valid_target = b"Valid target\n"
        valid_revision = documents.logical_hash(valid_target)
        (self.root / "work/drafts/invalid-target.md").write_bytes(
            b"---\ntarget: story/chapters/invalid.md\nbase-revision: "
            + valid_revision.encode("ascii")
            + b"\nstatus: working\n---\nBody\n"
        )
        model = project.discover_project(self.root)
        store = transactions.TransactionStore(model)
        store.remember_revision(valid_revision, valid_target)
        (self.root / "story/chapters/invalid.md").write_bytes(b"\xff")
        findings = draft_checks.check_drafts(model, store)
        by_path = {(finding.path, finding.code) for finding in findings}
        self.assertIn(("work/drafts/unsafe.md", draft_checks.INVALID_TARGET), by_path)
        self.assertIn(("work/drafts/no-base.md", draft_checks.UNRECOVERABLE_BASE), by_path)
        self.assertTrue(
            any(path == "work/drafts/invalid-target.md" for path, _ in by_path)
        )

    def protected_snapshot(self) -> dict[str, bytes]:
        protected = self.root / ".creative-writing"
        return {
            path.relative_to(protected).as_posix(): path.read_bytes()
            for path in protected.rglob("*")
            if path.is_file()
        }


if __name__ == "__main__":
    unittest.main()

import hashlib
import io
import json
import os
import shlex
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from . import helpers  # Adds the canonical CLI directory to sys.path.
from cwcli import app, context, doctor, project, scaffold
from cwcli.checks import CHECKERS
from cwcli.findings import Finding
from cwcli.transactions import Change, TransactionPlan, TransactionStore


def snapshot_tree(root: Path) -> tuple[tuple[str, str, str], ...]:
    entries = []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            entries.append((relative, "symlink", os.readlink(path)))
        elif path.is_file():
            entries.append((relative, "file", hashlib.sha256(path.read_bytes()).hexdigest()))
        elif path.is_dir():
            entries.append((relative, "directory", ""))
    return tuple(entries)


class DoctorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "project"
        for relative, data in scaffold.render_scaffold("Doctor", "en").items():
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        (self.root / ".creative-writing/context").mkdir(parents=True)
        (self.root / ".creative-writing/transactions").mkdir(parents=True)
        self.project = project.discover_project(self.root)

    def run_cli(self, argv: list[str], *, cwd: Path | None = None) -> tuple[int, str, str]:
        stdout, stderr = io.StringIO(), io.StringIO()
        status = app.run(argv, cwd=cwd or self.root, stdout=stdout, stderr=stderr)
        return status, stdout.getvalue(), stderr.getvalue()

    def test_doctor_is_byte_for_byte_read_only_and_groups_in_exact_order(self):
        target = self.root / "story/chapters/new.md"
        plan = TransactionPlan(
            command=("edit", "replace"),
            changes=(Change("story/chapters/new.md", None, b"new\n"),),
            metadata={},
        )
        TransactionStore(self.project).prepare(plan, transaction_id="tx-doctor")
        before = snapshot_tree(self.root)

        status, output, error = self.run_cli(["doctor", "--format", "json"])
        payload = json.loads(output)

        self.assertIn(status, {0, 1})
        self.assertEqual("", error)
        self.assertEqual(before, snapshot_tree(self.root))
        self.assertFalse(target.exists())
        self.assertEqual("agent", payload["audience"])
        self.assertEqual(
            [
                "protect recoverability",
                "restore safe interpretation",
                "refresh derived files",
                "improve provenance",
                "optional cleanup",
            ],
            [group["title"] for group in payload["groups"]],
        )
        recoverability = payload["groups"][0]
        self.assertIn("CW-JOURNAL-050", {item["code"] for item in recoverability["findings"]})
        expected = (doctor._cw_argv("recover", "tx-doctor"), doctor._cw_argv("recover", "tx-doctor") + ("--apply",))
        self.assertEqual([list(item) for item in expected], [item["argv"] for item in recoverability["commands"]])

    def test_mechanical_commands_preview_before_apply_and_semantic_finding_has_none(self):
        injected = {
            "journal": lambda _project: [
                Finding(
                    "CW-JOURNAL-050",
                    "warning",
                    "incomplete",
                    path=".creative-writing/transactions/tx-1/manifest.json",
                    next_action="cw recover tx-1 --apply",
                )
            ],
            "links": lambda _project: [
                Finding(
                    "CW-LINK-040",
                    "warning",
                    "index drift",
                    next_action="Preview cw reindex, review the diff, then apply it explicitly.",
                )
            ],
            "continuity": lambda _project: [
                Finding(
                    "CW-CONT-020",
                    "error",
                    "Mara appears after recorded death",
                    next_action="Ask the author whether the scene or death record is correct.",
                )
            ],
        }
        with mock.patch.dict(CHECKERS, injected, clear=True):
            report = doctor.diagnose_project(self.project)

        self.assertEqual(
            (doctor._cw_argv("recover", "tx-1"), doctor._cw_argv("recover", "tx-1") + ("--apply",)),
            tuple(command.argv for command in report.groups[0].commands),
        )
        self.assertEqual((), report.groups[1].commands)
        self.assertEqual(
            (doctor._cw_argv("reindex"), doctor._cw_argv("reindex") + ("--apply",)),
            tuple(command.argv for command in report.groups[2].commands),
        )
        semantic = report.groups[1].findings[0]
        self.assertTrue(semantic.next_action.startswith("Ask the author"))

    def test_stale_context_is_cleanup_not_an_ordinary_check(self):
        chapter = self.root / "story/chapters/ch-001.md"
        chapter.write_text("---\nnumber: 1\n---\nVisible.\n", encoding="utf-8")
        plan = context.plan_context(self.project, "chapter", "story/chapters/ch-001.md", "reader")
        context.render_snapshot(self.project, plan)
        chapter.write_text("---\nnumber: 1\n---\nChanged.\n", encoding="utf-8")
        before = snapshot_tree(self.root)

        report = doctor.diagnose_project(self.project)

        cleanup = report.groups[4]
        self.assertIn("CW-CONTEXT-STALE", {item.code for item in cleanup.findings})
        self.assertEqual(
            (doctor._cw_argv("clean-context"), doctor._cw_argv("clean-context") + ("--apply",)),
            tuple(command.argv for command in cleanup.commands),
        )
        self.assertEqual(before, snapshot_tree(self.root))

    def test_doctor_requires_project_and_runtime_failure_is_status_two(self):
        outside = Path(self.temporary.name) / "outside"
        outside.mkdir()
        status, output, error = self.run_cli(["doctor", "--format", "json"], cwd=outside)
        self.assertEqual(2, status)
        self.assertEqual("", error)
        self.assertEqual("error", json.loads(output)["status"])

    def test_text_and_json_have_same_codes_commands_and_agent_audience(self):
        TransactionStore(self.project).prepare(
            TransactionPlan(("edit",), (Change("story/new.md", None, b"x"),), {}),
            transaction_id="tx-parity",
        )
        _, json_output, _ = self.run_cli(["doctor", "--format", "json"])
        _, text_output, _ = self.run_cli(["doctor", "--format", "text"])
        payload = json.loads(json_output)
        codes = [item["code"] for group in payload["groups"] for item in group["findings"]]
        commands = [command["display"] for group in payload["groups"] for command in group["commands"]]
        self.assertIn("audience: agent", text_output)
        for value in (*codes, *commands):
            self.assertIn(value, text_output)

    def test_recovery_id_is_argv_first_and_shell_safe(self):
        transaction_id = "tx ;$(touch pwn) `id`"
        TransactionStore(self.project).prepare(
            TransactionPlan(("edit",), (Change("story/new.md", None, b"x"),), {}),
            transaction_id=transaction_id,
        )

        report = doctor.diagnose_project(self.project)
        commands = report.groups[0].commands

        self.assertEqual(transaction_id, commands[0].argv[3])
        self.assertEqual(shlex.join(commands[0].argv), commands[0].display(windows=False))
        self.assertEqual(
            subprocess.list2cmdline(list(commands[0].argv)),
            commands[0].display(windows=True),
        )
        payload = report.groups[0].as_dict()["commands"]
        self.assertEqual(transaction_id, payload[0]["argv"][3])
        finding = next(item for item in report.groups[0].findings if item.code == "CW-JOURNAL-050")
        self.assertEqual(shlex.join((*doctor._cw_argv("recover", transaction_id), "--apply")), finding.next_action)

    def test_subsystem_blockers_suppress_all_mechanical_commands(self):
        injected = {
            "journal": lambda _project: [
                Finding(
                    "CW-JOURNAL-050",
                    "warning",
                    "incomplete",
                    path=".creative-writing/transactions/tx/manifest.json",
                ),
                Finding("CW-JOURNAL-020", "error", "corrupt blob"),
            ],
            "links": lambda _project: [
                Finding(
                    "CW-LINK-040",
                    "warning",
                    "drift",
                    next_action="Preview cw reindex, review the diff, then apply it explicitly.",
                ),
                Finding("CW-STRUCT-050", "warning", "collision"),
            ],
        }
        context_findings = [
            Finding("CW-CONTEXT-STALE", "warning", "stale"),
            Finding("CW-CONTEXT-CORRUPT", "warning", "corrupt"),
        ]
        with mock.patch.dict(CHECKERS, injected, clear=True):
            with mock.patch("cwcli.doctor.snapshot_status", return_value=context_findings):
                report = doctor.diagnose_project(self.project)

        self.assertTrue(all(not group.commands for group in report.groups))
        corrupt = next(item for item in report.groups[4].findings if item.code == "CW-CONTEXT-CORRUPT")
        self.assertIn("manually", corrupt.next_action)

    def test_missing_required_index_parent_suppresses_reindex(self):
        shutil.rmtree(self.root / "kb/styles")

        report = doctor.diagnose_project(self.project)

        missing = [
            item
            for item in report.findings
            if item.code == "CW-STRUCT-010" and item.path == "kb/styles"
        ]
        self.assertEqual(1, len(missing))
        self.assertEqual((), report.groups[2].commands)

    def test_missing_generated_index_with_existing_parent_remains_repairable(self):
        (self.root / "kb/styles/_index.md").unlink()

        report = doctor.diagnose_project(self.project)

        self.assertTrue((self.root / "kb/styles").is_dir())
        missing = [
            item
            for item in report.findings
            if item.code == "CW-STRUCT-010" and item.path == "kb/styles/_index.md"
        ]
        self.assertEqual(1, len(missing))
        self.assertEqual(
            (doctor._cw_argv("reindex"), doctor._cw_argv("reindex") + ("--apply",)),
            tuple(command.argv for command in report.groups[2].commands),
        )


if __name__ == "__main__":
    unittest.main()

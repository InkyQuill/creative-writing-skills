"""Command-line entrypoint for the story-project CLI foundation."""

import argparse
from dataclasses import asdict
import json
import sys
import uuid
from pathlib import Path
from typing import TextIO

from . import __version__
from .checks import CHECKERS, run_checks
from .checks.drafts import check_drafts
from .checks.structure import check_structure
from .cli_doctor import diagnose_cli
from .context import (
    ContextPlanError,
    ContextSnapshotError,
    clean_context,
    plan_context,
    render_snapshot,
)
from .doctor import diagnose_project
from .documents import DocumentError, logical_hash
from .drafts import (
    DraftConflict,
    DraftError,
    plan_abandon_draft,
    plan_accept_draft,
    plan_create_draft,
    plan_rebase_draft,
    plan_set_draft_status,
)
from .edits import EditConflict, EditPlanError, load_operations, plan_edits
from .findings import ExecutionError, Finding, Report
from .indexes import plan_reindex
from .migration import (
    MigrationPlanError,
    load_migration_plan,
    migration_project,
    plan_apply_migration,
    plan_migration,
)
from .project import Project, ProjectDiscoveryError, ProjectPathError, discover_project
from .scaffold import InitError, apply_init, preview_init
from .transactions import (
    TransactionConflict,
    TransactionEngine,
    TransactionError,
    TransactionPlan,
    TransactionStore,
)


class _ArgumentError(ValueError):
    """An argparse error that can be reported through the caller's streams."""


class _PreviewRevisionStore:
    """A validating in-memory revision view for mutation-free draft previews."""

    def __init__(self, backing: TransactionStore):
        self._backing = backing
        self.project = backing.project
        self._revisions: dict[str, bytes] = {}

    def remember_revision(self, revision: str, data: bytes) -> str:
        if logical_hash(data) != revision:
            raise ValueError("revision data does not match the supplied logical hash")
        existing = self._revisions.get(revision)
        if existing is not None and existing != data:
            raise ValueError("revision identity has conflicting exact bytes")
        self._revisions[revision] = data
        return revision

    def load_revision(self, revision: str) -> bytes:
        if revision in self._revisions:
            return self._revisions[revision]
        return self._backing.load_revision(revision)


class _Parser(argparse.ArgumentParser):
    def __init__(self, *, error_stream: TextIO, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self.error_stream = error_stream

    def error(self, message: str) -> None:
        self.print_usage(self.error_stream)
        self.error_stream.write(f"{self.prog}: error: {message}\n")
        raise _ArgumentError(message)


def _parser(*, error_stream: TextIO) -> argparse.ArgumentParser:
    parser = _Parser(error_stream=error_stream, prog="cw")
    parser.add_argument("--version", action="store_true", help="show the CLI version")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--strict", action="store_true", help="treat warnings as failures")
    commands = parser.add_subparsers(dest="command", parser_class=_Parser)

    check = commands.add_parser("check", error_stream=error_stream)
    check_commands = check.add_subparsers(dest="check_command", required=True, parser_class=_Parser)
    for name in (*sorted(CHECKERS), "all"):
        check_command = check_commands.add_parser(name, error_stream=error_stream)
        check_command.add_argument("path", nargs="?", default=".")
        _report_options(check_command)

    context = commands.add_parser("context", error_stream=error_stream)
    context.add_argument("context_kind", choices=("draft", "chapter", "kb"))
    context.add_argument("path")
    context.add_argument("--as", dest="context_role", default="trusted")
    context.add_argument("--snapshot", action="store_true")
    _format_option(context)

    clean_context_command = commands.add_parser("clean-context", error_stream=error_stream)
    _mutation_options(clean_context_command)

    doctor = commands.add_parser("doctor", error_stream=error_stream)
    _format_option(doctor)

    cli_doctor = commands.add_parser("cli-doctor", error_stream=error_stream)
    _format_option(cli_doctor)

    init = commands.add_parser("init", error_stream=error_stream)
    init.add_argument("path", nargs="?", default=".")
    init.add_argument("--title", required=True)
    init.add_argument("--language", required=True)
    _mutation_options(init)

    reindex = commands.add_parser("reindex", error_stream=error_stream)
    _mutation_options(reindex)

    draft = commands.add_parser("draft", error_stream=error_stream)
    draft_commands = draft.add_subparsers(dest="draft_command", required=True, parser_class=_Parser)
    draft_create = draft_commands.add_parser("create", error_stream=error_stream)
    draft_create.add_argument("target")
    draft_create.add_argument("--draft-path")
    _mutation_options(draft_create)
    draft_status = draft_commands.add_parser("set-status", error_stream=error_stream)
    draft_status.add_argument("draft")
    draft_status.add_argument("status")
    _mutation_options(draft_status)
    for name in ("rebase", "accept", "abandon"):
        command = draft_commands.add_parser(name, error_stream=error_stream)
        command.add_argument("draft")
        _mutation_options(command)

    migrate = commands.add_parser("migrate", error_stream=error_stream)
    migrate_mode = migrate.add_mutually_exclusive_group(required=True)
    migrate_mode.add_argument("--plan", action="store_true")
    migrate_mode.add_argument(
        "--preview", metavar="PLAN", help="validate a plan and show its full transaction diff without writing"
    )
    migrate_mode.add_argument(
        "--apply", metavar="PLAN", help="commit a previously reviewed migration plan"
    )
    migrate.add_argument("--expect-plan-hash")
    _format_option(migrate)

    edit = commands.add_parser("edit", error_stream=error_stream)
    edit_commands = edit.add_subparsers(dest="edit_command", required=True, parser_class=_Parser)
    for kind in ("replace", "insert-before", "insert-after", "delete"):
        command = edit_commands.add_parser(kind, error_stream=error_stream)
        command.add_argument("path")
        if kind in {"replace", "delete"}:
            command.add_argument("--old-file", required=True)
        else:
            command.add_argument("--anchor-file", required=True)
        if kind != "delete":
            command.add_argument("--new-file", required=True)
        count = command.add_mutually_exclusive_group()
        count.add_argument("--expect-count", type=int)
        count.add_argument("--all", action="store_true")
        _mutation_options(command)

    batch = edit_commands.add_parser("apply", error_stream=error_stream)
    batch.add_argument("operations")
    _mutation_options(batch)

    history = commands.add_parser("history", error_stream=error_stream)
    _format_option(history)
    history_commands = history.add_subparsers(dest="history_command", parser_class=_Parser)
    history_show = history_commands.add_parser("show", error_stream=error_stream)
    history_show.add_argument("transaction_id")
    _format_option(history_show)

    undo = commands.add_parser("undo", error_stream=error_stream)
    undo.add_argument("transaction_id")
    _mutation_options(undo)

    recover = commands.add_parser("recover", error_stream=error_stream)
    recover.add_argument("transaction_id")
    _mutation_options(recover)
    return parser


def _report_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--format", choices=("text", "json"), default=argparse.SUPPRESS)
    parser.add_argument("--strict", action="store_true", default=argparse.SUPPRESS)


def _format_option(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--format", choices=("text", "json"), default=argparse.SUPPRESS)


def _mutation_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--apply", action="store_true")
    _format_option(parser)


def run(argv: list[str], *, cwd: Path, stdout: TextIO, stderr: TextIO) -> int:
    """Run the CLI with explicit process context and output streams."""
    parser = _parser(error_stream=stderr)
    try:
        args = parser.parse_args(argv)
        if not args.version and args.command is None:
            parser.error("the following arguments are required: command")
    except _ArgumentError:
        return 2
    if args.version:
        if args.format == "json":
            json.dump({"name": "cw", "version": __version__}, stdout)
        else:
            stdout.write(f"cw {__version__}")
        stdout.write("\n")
        return 0

    if args.command == "init":
        return _run_init(args, cwd=cwd, stdout=stdout, stderr=stderr)

    if args.command == "cli-doctor":
        entrypoint = Path(__file__).absolute().parent.parent / "cw.py"
        result = diagnose_cli(entrypoint, Path(sys.executable), repair_launcher=True)
        if args.format == "json":
            _write_command_data(result.as_dict(), output_format="json", stdout=stdout)
        else:
            stdout.write(result.as_text() + "\n")
        return result.exit_status()

    if args.command == "doctor":
        try:
            result = diagnose_project(discover_project(cwd))
        except (DocumentError, OSError, ProjectDiscoveryError, ProjectPathError, UnicodeError, ValueError) as error:
            return _write_command_error(
                error, conflict=False, output_format=args.format, stdout=stdout, stderr=stderr
            )
        if args.format == "json":
            _write_command_data(result.as_dict(), output_format="json", stdout=stdout)
        else:
            stdout.write(result.as_text() + "\n")
        return result.exit_status()

    if args.command == "draft":
        return _run_draft(args, cwd=cwd, stdout=stdout, stderr=stderr)

    if args.command == "migrate":
        return _run_migrate(args, cwd=cwd, stdout=stdout, stderr=stderr)

    if args.command == "context":
        return _run_context(args, cwd=cwd, stdout=stdout, stderr=stderr)

    if args.command == "clean-context":
        return _run_clean_context(args, cwd=cwd, stdout=stdout, stderr=stderr)

    if args.command == "check":
        names = sorted(CHECKERS) if args.check_command == "all" else [args.check_command]
        try:
            project = discover_project(_from_cwd(cwd, args.path))
        except (DocumentError, OSError, ProjectDiscoveryError) as error:
            if args.format != "json":
                stderr.write(f"cw: error: {error}\n")
                return 2
            report = Report(
                [],
                checks=names,
                execution_errors=[ExecutionError(check=name, message=str(error)) for name in names],
            )
        else:
            report = run_checks(project, names)
        return _write_report(report, output_format=args.format, strict=args.strict, stdout=stdout)

    if args.command == "edit":
        return _run_edit(args, cwd=cwd, stdout=stdout, stderr=stderr)

    if args.command == "history":
        return _run_history(args, cwd=cwd, stdout=stdout, stderr=stderr)

    if args.command == "undo":
        return _run_undo(args, cwd=cwd, stdout=stdout, stderr=stderr)

    if args.command == "recover":
        return _run_recover(args, cwd=cwd, stdout=stdout, stderr=stderr)

    if args.command == "reindex":
        return _run_reindex(args, cwd=cwd, stdout=stdout, stderr=stderr)

    return _write_report(Report([]), output_format=args.format, strict=args.strict, stdout=stdout)


def _write_report(report: Report, *, output_format: str, strict: bool, stdout: TextIO) -> int:
    if output_format == "json":
        json.dump(report.as_json(strict=strict), stdout)
        stdout.write("\n")
    else:
        stdout.write(report.as_text())
        if report.findings:
            stdout.write("\n")
        for error in report.execution_errors:
            stdout.write(f"CW-CHECK-EXEC [error] {error.check}: {error.message}\n")
    return report.exit_status(strict=strict)


def _run_context(args: argparse.Namespace, *, cwd: Path, stdout: TextIO, stderr: TextIO) -> int:
    try:
        project = discover_project(cwd)
        planned = plan_context(project, args.context_kind, args.path, args.context_role)
        result = planned.as_dict()
        if args.snapshot:
            snapshot = render_snapshot(project, planned)
            result["snapshot"] = snapshot.as_dict()
            if snapshot.boundary_warning:
                result["warnings"] = [
                    *planned.warnings,
                    "restricted context contains ordinary prose; the knowledge boundary cannot be guaranteed",
                ]
        _write_command_data(result, output_format=args.format, stdout=stdout)
        return 0
    except (
        ContextPlanError,
        ContextSnapshotError,
        DocumentError,
        OSError,
        ProjectDiscoveryError,
        ProjectPathError,
        UnicodeError,
        ValueError,
    ) as error:
        return _write_command_error(
            error,
            conflict=False,
            output_format=args.format,
            stdout=stdout,
            stderr=stderr,
        )


def _run_clean_context(args: argparse.Namespace, *, cwd: Path, stdout: TextIO, stderr: TextIO) -> int:
    try:
        project = discover_project(cwd)
        result = clean_context(project, apply=args.apply)
        _write_command_data(result.as_dict(), output_format=args.format, stdout=stdout)
        return 0
    except (
        ContextSnapshotError,
        DocumentError,
        OSError,
        ProjectDiscoveryError,
        ProjectPathError,
        UnicodeError,
        ValueError,
    ) as error:
        return _write_command_error(
            error,
            conflict=False,
            output_format=args.format,
            stdout=stdout,
            stderr=stderr,
        )


def _from_cwd(cwd: Path, path: str) -> Path:
    target = Path(path)
    return target if target.is_absolute() else cwd / target


def _run_edit(args: argparse.Namespace, *, cwd: Path, stdout: TextIO, stderr: TextIO) -> int:
    try:
        if args.edit_command == "apply":
            project = discover_project(cwd)
            operations = load_operations(_from_cwd(cwd, args.operations))
        else:
            project, relative = _single_edit_target(cwd, args.path)
            operation: dict[str, object] = {"op": args.edit_command, "path": relative}
            if args.edit_command in {"replace", "delete"}:
                operation["old"] = _read_content(cwd, args.old_file)
            else:
                operation["anchor"] = _read_content(cwd, args.anchor_file)
            if args.edit_command != "delete":
                operation["new"] = _read_content(cwd, args.new_file)
            if args.expect_count is not None:
                operation["expect-count"] = args.expect_count
            elif args.all:
                operation["all"] = True
            operations = (operation,)

        planned = plan_edits(project, operations)
        plan = TransactionPlan(
            command=("edit", args.edit_command),
            changes=planned.changes,
            metadata={**planned.metadata, "undoable": True},
        )
        return _preview_or_apply(
            TransactionEngine(project), plan, apply=args.apply,
            output_format=args.format, stdout=stdout,
        )
    except EditConflict as error:
        return _write_command_error(error, conflict=True, output_format=args.format, stdout=stdout, stderr=stderr)
    except TransactionConflict as error:
        return _write_command_error(error, conflict=True, output_format=args.format, stdout=stdout, stderr=stderr)
    except (DocumentError, EditPlanError, OSError, ProjectDiscoveryError, ProjectPathError, TransactionError, UnicodeError, ValueError) as error:
        conflict = isinstance(error, TransactionError) and "stale precondition" in str(error)
        return _write_command_error(error, conflict=conflict, output_format=args.format, stdout=stdout, stderr=stderr)


def _run_history(args: argparse.Namespace, *, cwd: Path, stdout: TextIO, stderr: TextIO) -> int:
    try:
        engine = TransactionEngine(discover_project(cwd))
        if args.history_command == "show":
            result: dict[str, object] = {"transaction": engine.store.manifest(args.transaction_id)}
        else:
            result = {"transactions": list(engine.store.history())}
        _write_command_data(result, output_format=args.format, stdout=stdout)
        return 0
    except (DocumentError, OSError, ProjectDiscoveryError, TransactionError, UnicodeError, ValueError) as error:
        return _write_command_error(error, conflict=False, output_format=args.format, stdout=stdout, stderr=stderr)


def _run_undo(args: argparse.Namespace, *, cwd: Path, stdout: TextIO, stderr: TextIO) -> int:
    try:
        engine = TransactionEngine(discover_project(cwd))
        plan = engine.inverse(args.transaction_id)
        return _preview_or_apply(
            engine, plan, apply=args.apply, output_format=args.format, stdout=stdout
        )
    except TransactionConflict as error:
        return _write_command_error(error, conflict=True, output_format=args.format, stdout=stdout, stderr=stderr)
    except (DocumentError, OSError, ProjectDiscoveryError, TransactionError, UnicodeError, ValueError) as error:
        return _write_command_error(error, conflict=False, output_format=args.format, stdout=stdout, stderr=stderr)


def _run_recover(args: argparse.Namespace, *, cwd: Path, stdout: TextIO, stderr: TextIO) -> int:
    try:
        engine = TransactionEngine(discover_project(cwd))
        record = engine.preflight_recovery(args.transaction_id)
        if args.apply:
            record = engine.recover(args.transaction_id)
            status = record.state
        else:
            status = "preview"
        _write_command_data(
            {
                "action": "restore-before-snapshots",
                "completed": list(record.completed),
                "state": record.state,
                "status": status,
                "transaction_id": record.id,
            },
            output_format=args.format,
            stdout=stdout,
        )
        return 0
    except TransactionConflict as error:
        return _write_command_error(error, conflict=True, output_format=args.format, stdout=stdout, stderr=stderr)
    except (DocumentError, KeyError, OSError, ProjectDiscoveryError, TransactionError, TypeError, UnicodeError, ValueError) as error:
        return _write_command_error(
            error,
            conflict=False,
            output_format=args.format,
            stdout=stdout,
            stderr=stderr,
        )


def _run_init(args: argparse.Namespace, *, cwd: Path, stdout: TextIO, stderr: TextIO) -> int:
    target = _from_cwd(cwd, args.path)
    try:
        plan = preview_init(target, args.title, args.language)
        if not args.apply:
            json.dump(_init_preview(plan), stdout)
            stdout.write("\n")
            return 0

        applied = apply_init(target, args.title, args.language)
        record = applied.record
        _write_command_data(
            {
                "status": record.state,
                "transaction_id": record.id,
                "command": list(plan.command),
                "changes": [
                    {
                        "action": "create" if change.before is None else "replace",
                        "path": change.path,
                    }
                    for change in plan.changes
                ],
                "metadata": dict(plan.metadata),
                "diagnostics": list(applied.diagnostics),
            },
            output_format=args.format,
            stdout=stdout,
        )
        return 0
    except (DocumentError, InitError, OSError, ProjectPathError, TransactionError, UnicodeError, ValueError) as error:
        conflict = isinstance(error, TransactionConflict)
        return _write_command_error(
            error, conflict=conflict, output_format=args.format, stdout=stdout, stderr=stderr
        )


def _run_reindex(args: argparse.Namespace, *, cwd: Path, stdout: TextIO, stderr: TextIO) -> int:
    try:
        project = discover_project(cwd)
        plan = plan_reindex(project)
        return _preview_or_apply(
            TransactionEngine(project),
            plan,
            apply=args.apply,
            output_format=args.format,
            stdout=stdout,
        )
    except TransactionConflict as error:
        return _write_command_error(
            error, conflict=True, output_format=args.format, stdout=stdout, stderr=stderr
        )
    except (DocumentError, OSError, ProjectDiscoveryError, ProjectPathError, TransactionError, UnicodeError, ValueError) as error:
        return _write_command_error(
            error, conflict=False, output_format=args.format, stdout=stdout, stderr=stderr
        )


def _run_draft(args: argparse.Namespace, *, cwd: Path, stdout: TextIO, stderr: TextIO) -> int:
    try:
        project = discover_project(cwd)
        engine = TransactionEngine(project)
        planning_store = engine.store if args.apply else _PreviewRevisionStore(engine.store)
        if args.draft_command == "create":
            plan = plan_create_draft(project, args.target, args.draft_path, planning_store)
            transaction_id = None
        elif args.draft_command == "set-status":
            plan = plan_set_draft_status(project, args.draft, args.status)
            transaction_id = None
        elif args.draft_command == "rebase":
            plan = plan_rebase_draft(project, args.draft, planning_store)
            transaction_id = None
        else:
            transaction_id = uuid.uuid4().hex
            if args.draft_command == "accept":
                plan = plan_accept_draft(project, args.draft, engine.store, transaction_id)
            else:
                plan = plan_abandon_draft(project, args.draft, transaction_id)
        return _preview_or_apply(
            engine,
            plan,
            apply=args.apply,
            output_format=args.format,
            stdout=stdout,
            transaction_id=transaction_id,
        )
    except DraftConflict as error:
        facts = {
            "status": "conflict",
            "exit_status": 1,
            "message": str(error),
            "conflicts": [asdict(conflict) for conflict in error.conflicts],
        }
        if args.format == "json":
            _write_command_data(facts, output_format=args.format, stdout=stdout)
        else:
            stderr.write(json.dumps(facts, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
        return 1
    except (DraftError, TransactionConflict) as error:
        return _write_command_error(
            error, conflict=True, output_format=args.format, stdout=stdout, stderr=stderr
        )
    except (DocumentError, OSError, ProjectDiscoveryError, ProjectPathError, TransactionError, UnicodeError, ValueError) as error:
        return _write_command_error(
            error, conflict=False, output_format=args.format, stdout=stdout, stderr=stderr
        )


def _run_migrate(args: argparse.Namespace, *, cwd: Path, stdout: TextIO, stderr: TextIO) -> int:
    root = Path(cwd).absolute()
    try:
        if args.plan:
            if args.expect_plan_hash is not None:
                raise MigrationPlanError("--expect-plan-hash is valid only with --preview or --apply")
            planned = plan_migration(root)
            _write_command_data(planned.to_payload(), output_format=args.format, stdout=stdout)
            return 0
        if args.expect_plan_hash is None:
            raise MigrationPlanError("--expect-plan-hash is required with --preview or --apply")
        plan_path = args.preview if args.preview is not None else args.apply
        loaded = load_migration_plan(_from_cwd(cwd, plan_path))
        plan = plan_apply_migration(root, loaded, args.expect_plan_hash)
        project = migration_project(root)
        engine = TransactionEngine(project)
        preview = engine.preview(plan)
        if args.preview is not None:
            _write_command_data(
                {
                    "status": "preview",
                    "transaction_id": None,
                    "plan_hash": loaded.plan_hash,
                    **preview,
                },
                output_format=args.format,
                stdout=stdout,
            )
            return 0
        record = engine.apply(plan)
        findings: list[Finding] = []
        execution_errors: list[ExecutionError] = []
        try:
            committed_project = discover_project(root)
        except (DocumentError, OSError, ProjectDiscoveryError) as error:
            execution_errors.extend(
                ExecutionError(check=name, message=str(error))
                for name in ("structure", "drafts")
            )
        else:
            try:
                findings.extend(check_structure(committed_project))
            except (DocumentError, OSError, ValueError) as error:
                execution_errors.append(
                    ExecutionError(check="structure", message=str(error))
                )
            try:
                findings.extend(
                    check_drafts(
                        committed_project,
                        TransactionEngine(committed_project).store,
                    )
                )
            except (DocumentError, OSError, TransactionError, ValueError) as error:
                execution_errors.append(
                    ExecutionError(check="drafts", message=str(error))
                )
        post_report = Report(
            findings,
            checks=["structure", "drafts"],
            execution_errors=execution_errors,
        )
        _write_command_data(
            {
                "status": record.state,
                "transaction_id": record.id,
                "plan_hash": loaded.plan_hash,
                "checks": post_report.checks,
                "findings": post_report.as_json()["findings"],
                "execution_errors": post_report.as_json()["execution_errors"],
                **preview,
            },
            output_format=args.format,
            stdout=stdout,
        )
        return 0
    except (MigrationPlanError, TransactionConflict) as error:
        return _write_command_error(
            error, conflict=True, output_format=args.format, stdout=stdout, stderr=stderr
        )
    except (DocumentError, OSError, ProjectPathError, TransactionError, UnicodeError, ValueError) as error:
        return _write_command_error(
            error, conflict=False, output_format=args.format, stdout=stdout, stderr=stderr
        )


def _single_edit_target(cwd: Path, value: str) -> tuple[Project, str]:
    target = _from_cwd(cwd, value).absolute()
    project = discover_project(cwd)
    if Path(value).is_absolute() and (not target.is_file() or target.is_symlink()):
        raise EditPlanError("absolute edit target must be an existing regular file inside the project")
    try:
        relative = project.relative_id(target)
        resolved = project.resolve(relative, for_write=True)
    except ProjectPathError as error:
        raise EditConflict(str(error)) from error
    if resolved != target or not target.is_file() or target.is_symlink():
        raise EditConflict("edit target must be an existing regular file inside the project")
    return project, relative


def _read_content(cwd: Path, value: str) -> str:
    path = _from_cwd(cwd, value)
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise EditPlanError(f"cannot read content file {path}: {error}") from error


def _preview_or_apply(
    engine: TransactionEngine,
    plan: TransactionPlan,
    *,
    apply: bool,
    output_format: str,
    stdout: TextIO,
    transaction_id: str | None = None,
) -> int:
    preview = engine.preview(plan)
    result: dict[str, object] = {
        "status": "preview",
        "transaction_id": transaction_id,
        **preview,
    }
    if apply:
        record = engine.apply(plan, transaction_id=transaction_id)
        result["status"] = record.state
        result["transaction_id"] = record.id
    _write_command_data(result, output_format=output_format, stdout=stdout)
    return 0


def _write_command_error(
    error: BaseException,
    *,
    conflict: bool,
    output_format: str,
    stdout: TextIO,
    stderr: TextIO,
) -> int:
    status = 1 if conflict else 2
    facts = {
        "status": "conflict" if conflict else "error",
        "exit_status": status,
        "message": str(error),
    }
    if output_format == "json":
        _write_command_data(facts, output_format=output_format, stdout=stdout)
    else:
        stderr.write(
            f"status: {facts['status']}\n"
            f"exit-status: {facts['exit_status']}\n"
            f"message: {facts['message']}\n"
        )
    return status


def _write_command_data(data: object, *, output_format: str, stdout: TextIO) -> None:
    if output_format == "json":
        json.dump(data, stdout, ensure_ascii=False, sort_keys=True)
    else:
        json.dump(data, stdout, ensure_ascii=False, indent=2, sort_keys=True)
    stdout.write("\n")


def _init_preview(plan: TransactionPlan) -> list[dict[str, str]]:
    file_operations = [{"op": "create", "path": change.path} for change in plan.changes]
    directory_operations = [
        {"op": "create-directory", "path": path}
        for path in plan.metadata["protected-directories"]
    ]
    return sorted((*file_operations, *directory_operations), key=lambda operation: operation["path"])


def main(argv: list[str] | None = None) -> int:
    return run(sys.argv[1:] if argv is None else argv, cwd=Path.cwd(), stdout=sys.stdout, stderr=sys.stderr)

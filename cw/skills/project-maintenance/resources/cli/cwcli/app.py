"""Command-line entrypoint for the story-project CLI foundation."""

import argparse
import json
import sys
from pathlib import Path
from typing import TextIO

from . import __version__
from .checks.structure import check_structure
from .documents import DocumentError
from .edits import EditConflict, EditPlanError, load_operations, plan_edits
from .findings import ExecutionError, Report
from .project import Project, ProjectDiscoveryError, ProjectPathError, discover_project
from .scaffold import render_scaffold
from .transactions import (
    TransactionConflict,
    TransactionEngine,
    TransactionError,
    TransactionPlan,
)


class _ArgumentError(ValueError):
    """An argparse error that can be reported through the caller's streams."""


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
    structure = check_commands.add_parser("structure", error_stream=error_stream)
    structure.add_argument("path", nargs="?", default=".")
    _report_options(structure)

    init = commands.add_parser("init", error_stream=error_stream)
    init.add_argument("path", nargs="?", default=".")
    init.add_argument("--title", required=True)
    init.add_argument("--language", required=True)
    init.add_argument("--apply", action="store_true")

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
        if args.apply:
            stderr.write("init --apply requires the transaction engine; run without --apply for preview\n")
            return 2
        operations = _init_preview(args.title, args.language)
        json.dump(operations, stdout)
        stdout.write("\n")
        return 0

    if args.command == "check" and args.check_command == "structure":
        try:
            target = _from_cwd(cwd, args.path)
            report = Report(check_structure(discover_project(target)), checks=["structure"])
        except (DocumentError, OSError, ProjectDiscoveryError) as error:
            if args.format == "json":
                report = Report(
                    [],
                    checks=["structure"],
                    execution_errors=[ExecutionError(check="structure", message=str(error))],
                )
                return _write_report(report, output_format=args.format, strict=args.strict, stdout=stdout)
            stderr.write(f"cw: error: {error}\n")
            return 2
        return _write_report(report, output_format=args.format, strict=args.strict, stdout=stdout)

    if args.command == "edit":
        return _run_edit(args, cwd=cwd, stdout=stdout, stderr=stderr)

    if args.command == "history":
        return _run_history(args, cwd=cwd, stdout=stdout, stderr=stderr)

    if args.command == "undo":
        return _run_undo(args, cwd=cwd, stdout=stdout, stderr=stderr)

    return _write_report(Report([]), output_format=args.format, strict=args.strict, stdout=stdout)


def _write_report(report: Report, *, output_format: str, strict: bool, stdout: TextIO) -> int:
    if output_format == "json":
        json.dump(report.as_json(strict=strict), stdout)
        stdout.write("\n")
    else:
        stdout.write(report.as_text())
        if report.findings:
            stdout.write("\n")
    return report.exit_status(strict=strict)


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


def _single_edit_target(cwd: Path, value: str) -> tuple[Project, str]:
    target = _from_cwd(cwd, value).absolute()
    project = discover_project(target if target.exists() else cwd)
    if Path(value).is_absolute() and (not target.is_file() or target.is_symlink()):
        raise EditPlanError("absolute edit target must be an existing regular file inside the project")
    try:
        relative = project.relative_id(target)
        resolved = project.resolve(relative, for_write=True)
    except ProjectPathError as error:
        raise EditPlanError(str(error)) from error
    if resolved != target or not target.is_file() or target.is_symlink():
        raise EditPlanError("edit target must be an existing regular file inside the project")
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
) -> int:
    preview = engine.preview(plan)
    result: dict[str, object] = {
        "status": "preview",
        "transaction_id": None,
        **preview,
    }
    if apply:
        record = engine.apply(plan)
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


def _init_preview(title: str, language: str) -> list[dict[str, str]]:
    file_operations = [{"op": "create", "path": path} for path in render_scaffold(title, language)]
    directory_operations = [
        {"op": "create-directory", "path": path}
        for path in (".creative-writing/context", ".creative-writing/transactions")
    ]
    return sorted((*file_operations, *directory_operations), key=lambda operation: operation["path"])


def main(argv: list[str] | None = None) -> int:
    return run(sys.argv[1:] if argv is None else argv, cwd=Path.cwd(), stdout=sys.stdout, stderr=sys.stderr)

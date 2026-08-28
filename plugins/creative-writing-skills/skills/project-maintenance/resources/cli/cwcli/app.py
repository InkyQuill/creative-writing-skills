"""Command-line entrypoint for the story-project CLI foundation."""

import argparse
import json
import sys
from pathlib import Path
from typing import TextIO

from . import __version__
from .checks.structure import check_structure
from .documents import DocumentError
from .findings import ExecutionError, Report
from .project import ProjectDiscoveryError, discover_project
from .scaffold import render_scaffold


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
    return parser


def _report_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--format", choices=("text", "json"), default=argparse.SUPPRESS)
    parser.add_argument("--strict", action="store_true", default=argparse.SUPPRESS)


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


def _init_preview(title: str, language: str) -> list[dict[str, str]]:
    file_operations = [{"op": "create", "path": path} for path in render_scaffold(title, language)]
    directory_operations = [
        {"op": "create-directory", "path": path}
        for path in (".creative-writing/context", ".creative-writing/transactions")
    ]
    return sorted((*file_operations, *directory_operations), key=lambda operation: operation["path"])


def main(argv: list[str] | None = None) -> int:
    return run(sys.argv[1:] if argv is None else argv, cwd=Path.cwd(), stdout=sys.stdout, stderr=sys.stderr)

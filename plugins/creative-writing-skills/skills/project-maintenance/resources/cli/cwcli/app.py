"""Command-line entrypoint for the story-project CLI foundation."""

import argparse
import json
import sys
from pathlib import Path
from typing import TextIO

from . import __version__
from .findings import Report


class _ArgumentError(ValueError):
    """An argparse error that can be reported through the caller's streams."""


class _Parser(argparse.ArgumentParser):
    def __init__(self, *, error_stream: TextIO) -> None:
        super().__init__(prog="cw")
        self.error_stream = error_stream

    def error(self, message: str) -> None:
        self.print_usage(self.error_stream)
        self.error_stream.write(f"{self.prog}: error: {message}\n")
        raise _ArgumentError(message)


def _parser(*, error_stream: TextIO) -> argparse.ArgumentParser:
    parser = _Parser(error_stream=error_stream)
    parser.add_argument("--version", action="store_true", help="show the CLI version")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--strict", action="store_true", help="treat warnings as failures")
    return parser


def run(argv: list[str], *, cwd: Path, stdout: TextIO, stderr: TextIO) -> int:
    """Run the CLI with explicit process context and output streams."""
    del cwd
    try:
        args = _parser(error_stream=stderr).parse_args(argv)
    except _ArgumentError:
        return 2
    if args.version:
        if args.format == "json":
            json.dump({"name": "cw", "version": __version__}, stdout)
        else:
            stdout.write(f"cw {__version__}")
        stdout.write("\n")
        return 0

    report = Report([])
    if args.format == "json":
        json.dump(report.as_json(strict=args.strict), stdout)
    else:
        stdout.write(report.as_text())
        if report.findings:
            stdout.write("\n")
    return report.exit_status(strict=args.strict)


def main(argv: list[str] | None = None) -> int:
    return run(sys.argv[1:] if argv is None else argv, cwd=Path.cwd(), stdout=sys.stdout, stderr=sys.stderr)

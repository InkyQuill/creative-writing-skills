"""Command-line entrypoint for the story-project CLI foundation."""

import argparse
import json
import sys
from pathlib import Path
from typing import TextIO

from . import __version__
from .findings import Report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cw")
    parser.add_argument("--version", action="store_true", help="show the CLI version")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--strict", action="store_true", help="treat warnings as failures")
    return parser


def run(argv: list[str], *, cwd: Path, stdout: TextIO, stderr: TextIO) -> int:
    """Run the CLI with explicit process context and output streams."""
    del cwd, stderr
    args = _parser().parse_args(argv)
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

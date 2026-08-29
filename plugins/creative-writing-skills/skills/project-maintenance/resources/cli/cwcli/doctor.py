"""Read-only, agent-oriented diagnosis for canonical story projects."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import os
from pathlib import Path, PurePosixPath
import shlex
import subprocess
import sys

from .checks import CHECKERS, run_checks
from .context import snapshot_status
from .findings import ExecutionError, Finding, finding_json
from .project import Project
from .schema import SCAFFOLD_DIRECTORIES


@dataclass(frozen=True)
class RepairCommand:
    """One executable command represented as data, never raw shell source."""

    argv: tuple[str, ...]

    def display(self, *, windows: bool | None = None) -> str:
        return _render_argv(self.argv, windows=windows)

    def as_dict(self) -> dict[str, object]:
        return {"argv": list(self.argv), "display": self.display()}


@dataclass(frozen=True)
class RepairGroup:
    """One stable repair tier; commands are previews followed by explicit applies."""

    priority: int
    title: str
    findings: tuple[Finding, ...]
    commands: tuple[RepairCommand, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "priority": self.priority,
            "title": self.title,
            "findings": [finding_json(finding) for finding in self.findings],
            "commands": [command.as_dict() for command in self.commands],
        }


@dataclass(frozen=True)
class DoctorReport:
    """A deterministic repair plan over the same findings as ``cw check``."""

    groups: tuple[RepairGroup, ...]
    execution_errors: tuple[ExecutionError, ...] = ()
    audience: str = "agent"

    @property
    def findings(self) -> tuple[Finding, ...]:
        return tuple(finding for group in self.groups for finding in group.findings)

    def exit_status(self) -> int:
        if self.execution_errors:
            return 2
        return int(any(finding.severity == "error" for finding in self.findings))

    def as_dict(self) -> dict[str, object]:
        return {
            "audience": self.audience,
            "groups": [group.as_dict() for group in self.groups],
            "execution_errors": [asdict(error) for error in self.execution_errors],
        }

    def as_text(self) -> str:
        lines = [f"audience: {self.audience}"]
        for group in self.groups:
            lines.append(f"{group.priority}. {group.title}")
            for finding in group.findings:
                location = f" ({finding.path}" if finding.path else ""
                if location and finding.line is not None:
                    location += f":{finding.line}"
                if location:
                    location += ")"
                lines.append(
                    f"  {finding.code} [{finding.severity}] {finding.message}{location}"
                )
                if finding.next_action:
                    lines.append(f"    Next: {finding.next_action}")
            for command in group.commands:
                lines.append(f"  $ {command.display()}")
        for error in self.execution_errors:
            lines.append(f"CW-DOCTOR-EXEC [error] {error.check}: {error.message}")
        return "\n".join(lines)


_GROUPS = (
    (1, "protect recoverability"),
    (2, "restore safe interpretation"),
    (3, "refresh derived files"),
    (4, "improve provenance"),
    (5, "optional cleanup"),
)


def _cw_argv(*args: str) -> tuple[str, ...]:
    entrypoint = Path(__file__).resolve().parent.parent / "cw.py"
    return (sys.executable, str(entrypoint), *args)


def diagnose_project(project: Project) -> DoctorReport:
    """Inspect a project without changing its files, journal, or caches."""

    report = run_checks(project, sorted(CHECKERS))
    findings = [*report.findings]
    try:
        findings.extend(snapshot_status(project))
    except Exception as error:
        execution_errors = (
            *report.execution_errors,
            ExecutionError(check="context", message=str(error)),
        )
    else:
        execution_errors = tuple(report.execution_errors)

    findings = [_direct_action(_manualize_blocker(finding)) for finding in findings]
    buckets: dict[int, list[Finding]] = {priority: [] for priority, _title in _GROUPS}
    for finding in sorted(findings, key=_finding_key):
        buckets[_priority(finding)].append(finding)

    groups = tuple(
        RepairGroup(
            priority=priority,
            title=title,
            findings=tuple(buckets[priority]),
            commands=_commands(buckets[priority], findings),
        )
        for priority, title in _GROUPS
    )
    return DoctorReport(groups=groups, execution_errors=execution_errors)


def _priority(finding: Finding) -> int:
    if finding.code.startswith("CW-JOURNAL-"):
        return 1
    if finding.code == "CW-LINK-040":
        return 3
    if finding.code.startswith("CW-KB-"):
        return 4
    if finding.code.startswith("CW-CONTEXT-") or finding.severity == "info":
        return 5
    return 2


def _commands(
    findings: list[Finding], all_findings: list[Finding]
) -> tuple[RepairCommand, ...]:
    commands: list[RepairCommand] = []
    journal_blocked = any(
        finding.code.startswith("CW-JOURNAL-") and finding.code != "CW-JOURNAL-050"
        for finding in all_findings
    )
    context_blocked = any(
        finding.code in {"CW-CONTEXT-CORRUPT", "CW-CONTEXT-UNSAFE"}
        for finding in all_findings
    )
    reindex_blocked = any(
        (
            finding.code
            in {
                "CW-LINK-090",
                "CW-STRUCT-001",
                "CW-STRUCT-011",
                "CW-STRUCT-020",
                "CW-STRUCT-050",
            }
            or (
                finding.code == "CW-STRUCT-010"
                and finding.path in SCAFFOLD_DIRECTORIES
            )
        )
        for finding in all_findings
    )
    for finding in findings:
        pair: tuple[tuple[str, ...], tuple[str, ...]] | None = None
        if finding.code == "CW-JOURNAL-050" and not journal_blocked:
            transaction_id = _transaction_id(finding)
            if transaction_id is not None:
                preview = _cw_argv("recover", transaction_id)
                pair = (preview, (*preview, "--apply"))
        elif (
            finding.code == "CW-LINK-040"
            and not reindex_blocked
            and finding.next_action is not None
            and "Preview cw reindex" in finding.next_action
        ):
            preview = _cw_argv("reindex")
            pair = (preview, (*preview, "--apply"))
        elif (
            finding.code in {"CW-CONTEXT-STALE", "CW-CONTEXT-MISSING"}
            and not context_blocked
        ):
            preview = _cw_argv("clean-context")
            pair = (preview, (*preview, "--apply"))
        if pair is not None:
            for argv in pair:
                command = RepairCommand(argv)
                if command not in commands:
                    commands.append(command)
    return tuple(commands)


def _transaction_id(finding: Finding) -> str | None:
    if finding.path is None:
        return None
    parts = PurePosixPath(finding.path).parts
    if (
        len(parts) == 4
        and parts[:2] == (".creative-writing", "transactions")
        and parts[3] == "manifest.json"
    ):
        return parts[2]
    return None


def _direct_action(finding: Finding) -> Finding:
    if finding.code == "CW-JOURNAL-050":
        transaction_id = _transaction_id(finding)
        if transaction_id is not None:
            return replace(
                finding,
                next_action=_render_argv((*_cw_argv("recover", transaction_id), "--apply")),
            )
    return finding


def _manualize_blocker(finding: Finding) -> Finding:
    if finding.code in {"CW-CONTEXT-CORRUPT", "CW-CONTEXT-UNSAFE"}:
        return replace(
            finding,
            next_action=(
                "Inspect and preserve the unsafe cache entry manually; do not run "
                "cw clean-context until every cache entry validates."
            ),
        )
    return finding


def _render_argv(argv: tuple[str, ...], *, windows: bool | None = None) -> str:
    if windows is None:
        windows = os.name == "nt"
    return subprocess.list2cmdline(list(argv)) if windows else shlex.join(argv)


def _finding_key(finding: Finding) -> tuple[str, str, int, str]:
    return (finding.path or "", finding.code, finding.line or 0, finding.message)


__all__ = ["DoctorReport", "RepairCommand", "RepairGroup", "diagnose_project"]

"""Read-only, agent-oriented diagnosis for canonical story projects."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from .checks import CHECKERS, run_checks
from .context import snapshot_status
from .findings import ExecutionError, Finding
from .project import Project


@dataclass(frozen=True)
class RepairGroup:
    """One stable repair tier; commands are previews followed by explicit applies."""

    priority: int
    title: str
    findings: tuple[Finding, ...]
    commands: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "priority": self.priority,
            "title": self.title,
            "findings": [asdict(finding) for finding in self.findings],
            "commands": list(self.commands),
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
                lines.append(f"  $ {command}")
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

    buckets: dict[int, list[Finding]] = {priority: [] for priority, _title in _GROUPS}
    for finding in sorted(findings, key=_finding_key):
        buckets[_priority(finding)].append(finding)

    groups = tuple(
        RepairGroup(
            priority=priority,
            title=title,
            findings=tuple(buckets[priority]),
            commands=_commands(buckets[priority]),
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


def _commands(findings: list[Finding]) -> tuple[str, ...]:
    commands: list[str] = []
    for finding in findings:
        pair: tuple[str, str] | None = None
        if finding.code == "CW-JOURNAL-050" and finding.next_action:
            apply = finding.next_action.strip()
            if apply.startswith("cw recover ") and apply.endswith(" --apply"):
                pair = (apply.removesuffix(" --apply"), apply)
        elif finding.code == "CW-LINK-040":
            pair = ("cw reindex", "cw reindex --apply")
        elif finding.code in {"CW-CONTEXT-STALE", "CW-CONTEXT-MISSING"}:
            pair = ("cw clean-context", "cw clean-context --apply")
        if pair is not None:
            for command in pair:
                if command not in commands:
                    commands.append(command)
    return tuple(commands)


def _finding_key(finding: Finding) -> tuple[str, str, int, str]:
    return (finding.path or "", finding.code, finding.line or 0, finding.message)


__all__ = ["DoctorReport", "RepairGroup", "diagnose_project"]

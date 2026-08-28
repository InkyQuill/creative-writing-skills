"""Stable finding and report models used by the story-project CLI."""

from dataclasses import asdict, dataclass, field
from typing import Literal

Severity = Literal["info", "warning", "error"]


@dataclass(frozen=True)
class Finding:
    code: str
    severity: Severity
    message: str
    path: str | None = None
    line: int | None = None
    next_action: str | None = None


@dataclass(frozen=True)
class ExecutionError:
    check: str
    message: str


@dataclass(frozen=True)
class Report:
    findings: list[Finding]
    checks: list[str] = field(default_factory=list)
    execution_errors: list[ExecutionError] = field(default_factory=list)

    def exit_status(self, *, strict: bool = False) -> int:
        if self.execution_errors:
            return 2
        return int(
            any(item.severity == "error" for item in self.findings)
            or (strict and any(item.severity == "warning" for item in self.findings))
        )

    def as_json(self, *, strict: bool = False) -> dict[str, object]:
        has_error = any(item.severity == "error" for item in self.findings)
        return {
            "checks": self.checks,
            "findings": [asdict(item) for item in self.findings],
            "execution_errors": [asdict(item) for item in self.execution_errors],
            "strict_failure": strict and self.exit_status(strict=True) == 1 and not has_error,
        }

    def as_text(self) -> str:
        """Return one deterministic, human-readable line for each finding."""
        lines = []
        for item in self.findings:
            location = ""
            if item.path is not None:
                location = f" ({item.path}"
                if item.line is not None:
                    location += f":{item.line}"
                location += ")"
            action = f" Next: {item.next_action}" if item.next_action else ""
            lines.append(f"{item.code} [{item.severity}] {item.message}{location}{action}")
        return "\n".join(lines)

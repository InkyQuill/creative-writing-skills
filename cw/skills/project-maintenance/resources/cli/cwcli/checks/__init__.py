"""Deterministic, exception-contained checks for canonical story projects."""

from __future__ import annotations

from collections.abc import Callable, Iterable

from ..findings import ExecutionError, Finding, Report
from ..project import Project
from ..transactions import TransactionStore
from .continuity import check_continuity
from .drafts import check_drafts
from .journal import check_journal
from .kb import check_kb
from .links import check_links
from .prose import check_prose
from .structure import check_structure


Checker = Callable[[Project], list[Finding]]


def _check_drafts(project: Project) -> list[Finding]:
    """Adapt the drafts service to the one-argument checker contract."""

    return check_drafts(project, TransactionStore(project))


CHECKERS: dict[str, Checker] = {
    "continuity": check_continuity,
    "drafts": _check_drafts,
    "journal": check_journal,
    "kb": check_kb,
    "links": check_links,
    "prose": check_prose,
    "structure": check_structure,
}


def run_checks(project: Project, names: Iterable[str]) -> Report:
    """Run selected checks independently and return one deterministic report."""

    selected = sorted(set(names))
    unknown = [name for name in selected if name not in CHECKERS]
    if unknown:
        raise ValueError(f"unknown checks: {', '.join(unknown)}")

    findings: list[Finding] = []
    execution_errors: list[ExecutionError] = []
    for name in selected:
        try:
            findings.extend(CHECKERS[name](project))
        except Exception as error:
            execution_errors.append(ExecutionError(check=name, message=str(error)))

    findings.sort(key=lambda item: (item.path or "", item.code, item.line or 0, item.message))
    return Report(findings=findings, checks=selected, execution_errors=execution_errors)


__all__ = ["CHECKERS", "Checker", "run_checks"]

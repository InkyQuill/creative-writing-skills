"""Deterministic, exception-contained checks for canonical story projects."""

from __future__ import annotations

from collections.abc import Callable, Iterable

from ..findings import CheckCoverage, ExecutionError, Finding, Report
from ..project import Project
from ..transactions import TransactionStore
from .continuity import check_continuity
from .drafts import check_drafts
from .journal import check_journal
from .kb import check_kb
from .links import check_links
from .prose import check_prose
from .structure import check_structure
from .translation import check_translation


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
    "translation": check_translation,
}


def run_checks(project: Project, names: Iterable[str], *, draft_typography: bool = False) -> Report:
    """Run selected checks independently and return one deterministic report."""

    selected = sorted(set(names))
    unknown = [name for name in selected if name not in CHECKERS]
    if unknown:
        raise ValueError(f"unknown checks: {', '.join(unknown)}")

    findings: list[Finding] = []
    execution_errors: list[ExecutionError] = []
    from ..catalog import document_paths, classify_document, lifecycle_drafts, KNOWLEDGE_TAGS
    from ..documents import read_document
    coverage = []
    try:
        paths = document_paths(project)
        relative_paths = tuple(project.relative_id(p) for p in paths)
        flexible = project.unstructured or project.selection is not None
    except (OSError, UnicodeError, ValueError) as error:
        return Report([], checks=selected, execution_errors=[ExecutionError(name, str(error)) for name in selected])
    for name in selected:
        try:
            checked = relative_paths
            skip = None
            if flexible:
                if name == 'translation' and project.metadata.get('schema-version') != 2:
                    skip = 'managed translation is not enabled'
                    checked = ()
                elif name == 'journal' and not (project.root / '.creative-writing').exists():
                    skip = 'no transaction journal exists'
                    checked = ()
                elif name == 'drafts':
                    checked = tuple(project.relative_id(p) for p in lifecycle_drafts(project))
                    if not checked:
                        skip = 'no managed draft lifecycle metadata'
                elif name in {'kb', 'continuity'}:
                    tags = KNOWLEDGE_TAGS if name == 'kb' else {'continuity'}
                    checked = tuple(project.relative_id(p) for p in paths
                                    if classify_document(project, project.relative_id(p)).tags & tags)
                    if not checked:
                        skip = 'no documents identified for this optional check'
                elif name == 'structure':
                    opaque = []
                    for path in paths:
                        try:
                            if read_document(path.read_bytes()).metadata_error:
                                opaque.append(path)
                        except OSError:
                            # The structure checker emits the per-file finding.
                            continue
                    if opaque:
                        skip = 'opaque metadata is unassessed; author bytes preserved'
            coverage.append(CheckCoverage(name, checked, skip))
            if flexible and skip and not checked:
                continue
            if name == "prose":
                findings.extend(check_prose(project, draft_typography=draft_typography))
            else:
                findings.extend(CHECKERS[name](project))
        except Exception as error:
            execution_errors.append(ExecutionError(check=name, message=str(error)))

    findings.sort(key=lambda item: (item.path or "", item.code, item.line or 0, item.message))
    return Report(findings=findings, checks=selected, execution_errors=execution_errors, coverage=coverage)


__all__ = ["CHECKERS", "Checker", "run_checks"]

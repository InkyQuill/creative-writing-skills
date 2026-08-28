"""Working-draft parsing and transaction planning."""

from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from pathlib import PurePosixPath

from .documents import Document, Scalar, logical_hash, parse_document, render_document
from .project import Project, ProjectPathError
from .transactions import Change, TransactionPlan, TransactionStore


ACTIVE_STATUSES = frozenset({"working", "review", "ready"})
_CLI_MANAGED_METADATA = frozenset({"target", "base-revision", "status"})


class DraftError(ValueError):
    """Raised when a draft cannot be interpreted or planned safely."""


@dataclass(frozen=True)
class Draft:
    """One strict active draft and its lifecycle identity."""

    metadata: dict[str, Scalar | list[str]]
    path: str
    target: str
    base_revision: str | None
    status: str


def load_draft(project: Project, path: str) -> Draft:
    """Load a valid active draft without following filesystem links."""

    _validate_draft_path(path)
    try:
        source = project.resolve(path, for_write=True)
    except (ProjectPathError, TypeError) as error:
        raise DraftError(f"unsafe draft path {path!r}: {error}") from error
    try:
        document = parse_document(_read_regular_file(source, f"draft {path}"))
    except (OSError, UnicodeError, ValueError) as error:
        raise DraftError(f"cannot parse draft {path}: {error}") from error

    target = document.metadata.get("target")
    if not isinstance(target, str):
        raise DraftError(f"draft {path} must have a string target")
    _validate_target_path(target)
    base_revision = document.metadata.get("base-revision")
    if base_revision is not None and not _is_digest(base_revision):
        raise DraftError(f"draft {path} has an invalid base-revision")
    status = document.metadata.get("status")
    if not isinstance(status, str) or status not in ACTIVE_STATUSES:
        raise DraftError(
            f"draft {path} status must be one of working, review, or ready"
        )
    return Draft(dict(document.metadata), path, target, base_revision, status)


def plan_create_draft(
    project: Project,
    target: str,
    draft_path: str | None,
    store: TransactionStore,
) -> TransactionPlan:
    """Plan a new working draft while preserving any accepted target exactly."""

    _validate_target_path(target)
    if store.project.root != project.root:
        raise DraftError("transaction store belongs to a different project")
    destination_id = draft_path or f"work/drafts/{PurePosixPath(target).name}"
    _validate_draft_path(destination_id)
    try:
        target_path = project.resolve(target, for_write=True)
        destination = project.resolve(destination_id, for_write=True)
    except (ProjectPathError, TypeError) as error:
        raise DraftError(f"unsafe draft or target path: {error}") from error

    if os.path.lexists(destination):
        raise DraftError(f"draft path already exists: {destination_id}")
    _reject_duplicate_target(project, target)

    base_revision: str | None = None
    if os.path.lexists(target_path):
        try:
            target_bytes = _read_regular_file(target_path, f"target {target}")
            accepted = parse_document(target_bytes)
        except (OSError, UnicodeError, ValueError) as error:
            raise DraftError(f"cannot parse target {target}: {error}") from error
        base_revision = logical_hash(target_bytes)
        store.remember_revision(base_revision, target_bytes)
        metadata = {
            key: value
            for key, value in accepted.metadata.items()
            if key not in _CLI_MANAGED_METADATA
        }
        body = accepted.body
        newline = accepted.newline
        bom = accepted.bom
    else:
        metadata = {}
        body = ""
        newline = "\n"
        bom = False

    metadata["target"] = target
    if base_revision is not None:
        metadata["base-revision"] = base_revision
    metadata["status"] = "working"
    rendered = render_document(
        Document(metadata=metadata, body=body, newline=newline, bom=bom)
    )
    return TransactionPlan(
        command=("draft", "create", target),
        changes=(Change(destination_id, None, rendered),),
        metadata={"draft": destination_id, "target": target, "undoable": True},
    )


def _reject_duplicate_target(project: Project, target: str) -> None:
    directory = project.root / "work" / "drafts"
    if directory.is_symlink():
        raise DraftError("work/drafts must be an ordinary directory without links")
    if not directory.exists():
        return
    if not directory.is_dir():
        raise DraftError("work/drafts must be an ordinary directory")
    for path in sorted(directory.iterdir(), key=lambda candidate: candidate.name):
        if path.name == "_index.md" or path.suffix.casefold() != ".md":
            continue
        relative = project.relative_id(path)
        draft = load_draft(project, relative)
        if draft.target == target:
            raise DraftError(f"active draft already targets {target}: {relative}")


def _validate_target_path(path: str) -> None:
    if not isinstance(path, str):
        raise DraftError("draft target must be a project-relative string")
    pure = PurePosixPath(path)
    if (
        str(pure) != path
        or pure.parent != PurePosixPath("story/chapters")
        or pure.name == "_index.md"
        or pure.suffix.casefold() != ".md"
    ):
        raise DraftError("draft target must be story/chapters/<name>.md")


def _validate_draft_path(path: str) -> None:
    if not isinstance(path, str):
        raise DraftError("draft path must be a project-relative string")
    pure = PurePosixPath(path)
    if (
        str(pure) != path
        or pure.parent != PurePosixPath("work/drafts")
        or pure.name == "_index.md"
        or pure.suffix.casefold() != ".md"
    ):
        raise DraftError("draft path must be work/drafts/<name>.md")


def _is_digest(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _read_regular_file(path: os.PathLike[str], label: str) -> bytes:
    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except OSError as error:
        raise DraftError(f"{label} must be an ordinary file without links") from error
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise DraftError(f"{label} must be an ordinary file without links")
        with os.fdopen(descriptor, "rb") as stream:
            descriptor = -1
            return stream.read()
    finally:
        if descriptor >= 0:
            os.close(descriptor)


__all__ = [
    "ACTIVE_STATUSES",
    "Draft",
    "DraftError",
    "load_draft",
    "plan_create_draft",
]

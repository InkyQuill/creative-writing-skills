"""Working-draft parsing and transaction planning."""

from __future__ import annotations

import os
import re
import stat
import unicodedata
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from .documents import Document, Scalar, logical_hash, parse_document, render_document
from .project import Project, ProjectPathError
from .rebase import RebaseConflict, three_way_rebase
from .transactions import (
    Change,
    TransactionError,
    TransactionPlan,
    TransactionStore,
)


ACTIVE_STATUSES = frozenset({"working", "review", "ready"})
_CLI_MANAGED_METADATA = frozenset({"target", "base-revision", "status"})


class DraftError(ValueError):
    """Raised when a draft cannot be interpreted or planned safely."""


class DraftConflict(DraftError):
    """Raised when a draft and its accepted target cannot be merged safely."""

    def __init__(self, conflicts: tuple[RebaseConflict, ...]):
        super().__init__(f"draft rebase has {len(conflicts)} competing fragment(s)")
        self.conflicts = conflicts


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
    _resolve_target(project, target)
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

    target_path = _resolve_target(project, target)
    if store.project.root != project.root:
        raise DraftError("transaction store belongs to a different project")
    destination_id = (
        f"work/drafts/{PurePosixPath(target).name}"
        if draft_path is None
        else draft_path
    )
    _validate_draft_path(destination_id)
    try:
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


def plan_rebase_draft(
    project: Project,
    draft_path: str,
    store: TransactionStore,
) -> TransactionPlan:
    """Plan a conservative rebase of one draft onto its current target."""

    if store.project.root != project.root:
        raise DraftError("transaction store belongs to a different project")
    draft = load_draft(project, draft_path)
    if draft.base_revision is None:
        raise DraftError(f"draft {draft_path} has no base-revision to rebase")

    try:
        draft_source = _read_regular_file(
            project.resolve(draft_path, for_write=True), f"draft {draft_path}"
        )
        draft_document = parse_document(draft_source)
        if draft_document.metadata != draft.metadata:
            raise DraftError(f"draft {draft_path} changed while planning its rebase")
        base_source = store.load_revision(draft.base_revision)
        base_document = parse_document(base_source)
        target_path = _resolve_target(project, draft.target)
        current_source = _read_regular_file(target_path, f"target {draft.target}")
        current_document = parse_document(current_source)
    except (OSError, UnicodeError, ValueError, TransactionError) as error:
        raise DraftError(
            f"cannot load recoverable rebase inputs for {draft_path}: {error}"
        ) from error

    current_revision = logical_hash(current_source)
    if current_revision == draft.base_revision:
        return TransactionPlan(
            command=("draft", "rebase", draft_path),
            changes=(),
            metadata={
                "draft": draft_path,
                "target": draft.target,
                "base-revision": current_revision,
                "undoable": True,
            },
        )

    result = three_way_rebase(
        base_document.body, draft_document.body, current_document.body
    )
    if result.conflicts:
        raise DraftConflict(result.conflicts)
    assert result.text is not None

    after = _render_rebased_draft(
        draft_source, draft_document, result.text, current_revision
    )
    # Save the exact target revision only after the complete conflict scan. A
    # subsequent rebase must be able to recover the new base named by the
    # applied draft metadata.
    store.remember_revision(current_revision, current_source)
    return TransactionPlan(
        command=("draft", "rebase", draft_path),
        changes=(Change(draft_path, draft_source, after),),
        metadata={
            "draft": draft_path,
            "target": draft.target,
            "base-revision": current_revision,
            "undoable": True,
        },
    )


_BASE_REVISION_SCALAR = re.compile(
    br"base-revision:[ \t]*(?P<quote>['\"]?)(?P<value>[0-9a-f]{64})"
    br"(?P=quote)(?P<suffix>[ \t]*(?:\#.*)?)"
)


def _render_rebased_draft(
    source: bytes,
    document: Document,
    body: str,
    base_revision: str,
) -> bytes:
    original_body = document.body.encode("utf-8")
    if not source.endswith(original_body):
        raise DraftError("cannot identify the draft body without rewriting frontmatter")
    prefix = source[: len(source) - len(original_body)] if original_body else source
    updated_prefix = _replace_base_revision_value(prefix, base_revision)
    normalized_body = body.replace("\r\n", "\n").replace("\r", "\n")
    rendered_body = normalized_body.replace("\n", document.newline).encode("utf-8")
    rendered = updated_prefix + rendered_body
    reparsed = parse_document(rendered)
    expected_metadata = dict(document.metadata)
    expected_metadata["base-revision"] = base_revision
    if reparsed.metadata != expected_metadata or reparsed.body != rendered_body.decode("utf-8"):
        raise DraftError("rebased draft could not be rendered safely")
    return rendered


def _replace_base_revision_value(prefix: bytes, base_revision: str) -> bytes:
    """Replace only the raw scalar token, retaining all surrounding bytes."""

    replacement = base_revision.encode("ascii")
    rendered: list[bytes] = []
    matches = 0
    for source_line in prefix.splitlines(keepends=True):
        if source_line.endswith(b"\r\n"):
            content, ending = source_line[:-2], b"\r\n"
        elif source_line.endswith((b"\n", b"\r")):
            content, ending = source_line[:-1], source_line[-1:]
        else:
            content, ending = source_line, b""
        match = _BASE_REVISION_SCALAR.fullmatch(content)
        if match is not None:
            matches += 1
            content = (
                content[: match.start("value")]
                + replacement
                + content[match.end("value") :]
            )
        rendered.append(content + ending)
    if matches != 1:
        raise DraftError("draft must contain exactly one base-revision field")
    return b"".join(rendered)


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
        if _portable_identity(draft.target) == _portable_identity(target):
            raise DraftError(f"active draft already targets {target}: {relative}")


def _resolve_target(project: Project, target: str) -> Path:
    _validate_target_path(target)
    try:
        return project.resolve(target, for_write=True)
    except (ProjectPathError, TypeError) as error:
        raise DraftError(f"unsafe draft target {target!r}: {error}") from error


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


def _portable_identity(path: str) -> str:
    return unicodedata.normalize("NFC", path).casefold()


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
    "DraftConflict",
    "DraftError",
    "load_draft",
    "plan_create_draft",
    "plan_rebase_draft",
]

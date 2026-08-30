"""Resilient, read-only findings for active story drafts."""

from __future__ import annotations

import os
import stat
import unicodedata
from pathlib import Path

from ..documents import logical_hash, parse_document
from ..drafts import ACTIVE_STATUSES
from ..findings import Finding
from ..project import Project, ProjectPathError
from ..transactions import TransactionError, TransactionStore


MALFORMED_DRAFT = "CW-DRAFT-010"
INVALID_TARGET = "CW-DRAFT-020"
INVALID_STATUS = "CW-DRAFT-021"
ABANDONED_ACTIVE = "CW-DRAFT-022"
MISSING_OPTIONAL_METADATA = "CW-DRAFT-030"
DUPLICATE_TARGET = "CW-DRAFT-040"
UNRECOVERABLE_BASE = "CW-DRAFT-050"
STALE_DRAFT = "CW-DRAFT-051"
SOURCE_TAG = "CW-DRAFT-060"


def check_drafts(project: Project, store: TransactionStore) -> list[Finding]:
    """Return stable warnings for every inspectable active draft.

    Draft-local defects make lifecycle commands refuse that draft, but they do
    not prevent unrelated reading or review, so this broad checker reports them
    as repairable warnings and continues after malformed files.
    """

    directory = project.root / "work" / "drafts"
    if store.project.root != project.root:
        return [_warning(MALFORMED_DRAFT, "transaction store belongs to another project", None)]
    if directory.is_symlink() or not directory.is_dir():
        return []

    findings: list[Finding] = []
    targets: dict[str, list[str]] = {}
    for path in sorted(directory.iterdir(), key=lambda item: (_identity(item.name), item.name)):
        if path.name == "_index.md" or path.suffix.casefold() != ".md":
            continue
        relative = project.relative_id(path)
        try:
            source = _read_regular(path)
            document = parse_document(source)
        except (OSError, UnicodeError, ValueError) as error:
            findings.append(
                _warning(
                    MALFORMED_DRAFT,
                    f"draft cannot be interpreted safely: {error}",
                    relative,
                )
            )
            continue

        title = document.metadata.get("title")
        if not isinstance(title, str) or not title.strip():
            findings.append(
                _warning(
                    MISSING_OPTIONAL_METADATA,
                    "draft has no optional title metadata",
                    relative,
                )
            )

        status = document.metadata.get("status")
        if status == "abandoned":
            findings.append(
                _warning(
                    ABANDONED_ACTIVE,
                    "abandoned draft remains in the active drafts directory",
                    relative,
                )
            )
        elif status not in ACTIVE_STATUSES:
            findings.append(
                _warning(
                    INVALID_STATUS,
                    "active draft status must be working, review, or ready",
                    relative,
                )
            )

        target = document.metadata.get("target")
        target_path: Path | None = None
        if not isinstance(target, str) or not _valid_target(target):
            findings.append(
                _warning(
                    INVALID_TARGET,
                    "draft target must be story/chapters/<name>.md or story/side-stories/<name>.md",
                    relative,
                )
            )
        else:
            try:
                target_path = project.resolve(target, for_write=True)
            except (OSError, ProjectPathError, TypeError, ValueError) as error:
                findings.append(
                    _warning(
                        INVALID_TARGET,
                        f"draft target is unsafe in this project: {error}",
                        relative,
                    )
                )
            else:
                # Only active lifecycle artifacts contend for a target. Inactive
                # files retain their own repair warnings but must not block work.
                if status not in ACTIVE_STATUSES:
                    target_path = None
                else:
                    targets.setdefault(_identity(target), []).append(relative)

        base = document.metadata.get("base-revision")
        if base is None:
            if target_path is not None and os.path.lexists(target_path):
                findings.append(
                    _warning(
                        UNRECOVERABLE_BASE,
                        "an existing target requires a recoverable base-revision",
                        relative,
                    )
                )
        else:
            if not _digest(base):
                findings.append(
                    _warning(UNRECOVERABLE_BASE, "draft base-revision is invalid", relative)
                )
            else:
                try:
                    store.load_revision(base)
                except (OSError, TransactionError, UnicodeError, ValueError) as error:
                    findings.append(
                        _warning(
                            UNRECOVERABLE_BASE,
                            f"draft base-revision cannot be recovered: {error}",
                            relative,
                        )
                    )
                else:
                    if target_path is not None:
                        try:
                            current = _read_regular(target_path)
                            current_hash = logical_hash(current)
                        except (OSError, UnicodeError, ValueError):
                            findings.append(
                                _warning(
                                    STALE_DRAFT,
                                    "draft base target is missing or unsafe",
                                    relative,
                                )
                            )
                        else:
                            if current_hash != base:
                                findings.append(
                                    _warning(
                                        STALE_DRAFT,
                                        "draft target changed after its base revision",
                                        relative,
                                    )
                                )

        text = source.decode("utf-8-sig")
        if any(tag in text for tag in ("<AI", "</AI", "<hidden", "</hidden")):
            findings.append(
                _warning(
                    SOURCE_TAG,
                    "active draft contains source tags that require lifecycle review",
                    relative,
                )
            )

    for paths in targets.values():
        if len(paths) < 2:
            continue
        ordered = sorted(paths)
        for path in ordered:
            others = ", ".join(item for item in ordered if item != path)
            findings.append(
                _warning(
                    DUPLICATE_TARGET,
                    f"another active draft has the same target: {others}",
                    path,
                )
            )
    return sorted(findings, key=lambda item: (item.path or "", item.code, item.message))


def _warning(code: str, message: str, path: str | None) -> Finding:
    return Finding(
        code=code,
        severity="warning",
        message=message,
        path=path,
        next_action="Repair this draft before running a lifecycle command that requires it.",
    )


def _valid_target(value: str) -> bool:
    path = Path(value)
    return (
        "\\" not in value
        and path.as_posix() == value
        and path.parent.as_posix() in {"story/chapters", "story/side-stories"}
        and path.name != "_index.md"
        and path.suffix.casefold() == ".md"
    )


def _digest(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _identity(value: str) -> str:
    return unicodedata.normalize("NFC", value).casefold()


def _read_regular(path: Path) -> bytes:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise OSError("not a regular file")
        with os.fdopen(descriptor, "rb") as stream:
            descriptor = -1
            return stream.read()
    finally:
        if descriptor >= 0:
            os.close(descriptor)


__all__ = [
    "ABANDONED_ACTIVE",
    "DUPLICATE_TARGET",
    "INVALID_STATUS",
    "INVALID_TARGET",
    "MALFORMED_DRAFT",
    "MISSING_OPTIONAL_METADATA",
    "SOURCE_TAG",
    "STALE_DRAFT",
    "UNRECOVERABLE_BASE",
    "check_drafts",
]

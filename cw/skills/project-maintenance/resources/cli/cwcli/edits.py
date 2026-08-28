"""Read-only planning for exact-anchor story document edits."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import replace
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import TypeAlias

from .documents import Document, DocumentError, parse_document, render_document
from .project import Project, ProjectPathError
from .transactions import Change, TransactionPlan


EditOperation: TypeAlias = Mapping[str, object]


class EditPlanError(ValueError):
    """Raised when an edit plan is malformed or targets an unsafe document."""


class EditConflict(EditPlanError):
    """Raised when an exact anchor does not have the declared match count."""


_TEXT_OPERATION_FIELDS = {
    "replace": (frozenset({"op", "path", "old", "new"}), frozenset({"expect-count", "all"})),
    "insert-before": (frozenset({"op", "path", "anchor", "new"}), frozenset({"expect-count", "all"})),
    "insert-after": (frozenset({"op", "path", "anchor", "new"}), frozenset({"expect-count", "all"})),
    "delete": (frozenset({"op", "path", "old"}), frozenset({"expect-count", "all"})),
}
_FRONTMATTER_FIELDS = frozenset({"op", "path", "key", "value"})
_PROTECTED_FRONTMATTER_KEYS = frozenset({"schema-version", "base-revision", "status"})
_FRONTMATTER_KEY = re.compile(r"^[^\s:#][^:\r\n]*$")


def load_operations(path: Path) -> tuple[EditOperation, ...]:
    """Load and validate a UTF-8 JSON array of exact edit operations."""

    try:
        with Path(path).open(encoding="utf-8-sig") as stream:
            loaded = json.load(stream, object_pairs_hook=_json_object)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise EditPlanError(f"cannot load edit operations from {path}: {error}") from error

    if not isinstance(loaded, list):
        raise EditPlanError("edit operations JSON must contain an array")
    return _validate_operations(loaded)


def plan_edits(project: Project, operations: Iterable[EditOperation]) -> TransactionPlan:
    """Calculate an all-or-nothing transaction without changing the filesystem."""

    validated = _validate_operations(operations)
    if not validated:
        raise EditPlanError("edit plan must contain at least one operation")

    targets: dict[str, Path] = {}
    for operation in validated:
        relative = operation["path"]
        assert isinstance(relative, str)
        if Path(relative).name.casefold() == "_index.md":
            raise EditPlanError(f"generated index cannot be edited directly: {relative}")
        if Path(relative).suffix.casefold() != ".md":
            raise EditPlanError(f"edit target must be a Markdown document: {relative}")
        try:
            target = project.resolve(relative, for_write=True)
        except (ProjectPathError, TypeError) as error:
            raise EditPlanError(str(error)) from error
        if not target.is_file() or target.is_symlink():
            raise EditPlanError(f"edit target is not an existing regular file: {relative}")
        targets.setdefault(relative, target)

    originals: dict[str, bytes] = {}
    for relative, target in targets.items():
        try:
            source = target.read_bytes()
            parse_document(source)
        except (OSError, UnicodeError, DocumentError) as error:
            raise EditPlanError(f"cannot read edit target {relative}: {error}") from error
        originals[relative] = source

    working = dict(originals)
    for operation in validated:
        relative = operation["path"]
        assert isinstance(relative, str)
        working[relative] = _apply_operation(working[relative], operation, relative)

    changes = tuple(
        Change(relative, originals[relative], working[relative])
        for relative in targets
    )
    return TransactionPlan(
        command=("edit", "apply"),
        changes=changes,
        metadata={"operation-count": len(validated)},
    )


def _validate_operations(operations: Iterable[EditOperation]) -> tuple[EditOperation, ...]:
    if isinstance(operations, (str, bytes, Mapping)):
        raise EditPlanError("edit operations must be an iterable of objects")
    try:
        candidates = tuple(operations)
    except TypeError as error:
        raise EditPlanError("edit operations must be an iterable of objects") from error

    validated: list[EditOperation] = []
    for index, candidate in enumerate(candidates, start=1):
        if not isinstance(candidate, Mapping):
            raise EditPlanError(f"operation {index} must be an object")
        operation = dict(candidate)
        if not all(isinstance(key, str) for key in operation):
            raise EditPlanError(f"operation {index} field names must be strings")
        _validate_unicode_strings(operation, index)
        kind = operation.get("op")
        if not isinstance(kind, str) or kind not in {*_TEXT_OPERATION_FIELDS, "frontmatter-set"}:
            raise EditPlanError(f"operation {index} has unknown operation kind: {kind!r}")

        required, optional = (
            _TEXT_OPERATION_FIELDS[kind]
            if kind in _TEXT_OPERATION_FIELDS
            else (_FRONTMATTER_FIELDS, frozenset())
        )
        keys = frozenset(operation)
        missing = required - keys
        unknown = keys - required - optional
        if missing:
            raise EditPlanError(f"operation {index} is missing field(s): {', '.join(sorted(missing))}")
        if unknown:
            raise EditPlanError(f"operation {index} has unknown field(s): {', '.join(sorted(unknown))}")

        _validate_relative_path(operation["path"], index)
        if kind == "frontmatter-set":
            _validate_frontmatter_operation(operation, index)
        else:
            _validate_text_operation(operation, index)
        validated.append(operation)
    return tuple(validated)


def _validate_relative_path(value: object, index: int) -> None:
    if not isinstance(value, str) or not value:
        raise EditPlanError(f"operation {index} path must be a non-empty string")
    native = Path(value)
    windows = PureWindowsPath(value)
    posix = PurePosixPath(value)
    if (
        "\\" in value
        or native.is_absolute()
        or posix.is_absolute()
        or windows.is_absolute()
        or windows.drive
        or windows.root
        or ".." in native.parts
        or posix.as_posix() != value
        or value in {".", ".."}
    ):
        raise EditPlanError(f"operation {index} path must be project-relative")


def _validate_text_operation(operation: dict[str, object], index: int) -> None:
    kind = operation["op"]
    anchor_key = "anchor" if kind in {"insert-before", "insert-after"} else "old"
    anchor = operation[anchor_key]
    if not isinstance(anchor, str) or not anchor:
        raise EditPlanError(f"operation {index} {anchor_key} must be a non-empty string")
    if "new" in operation and not isinstance(operation["new"], str):
        raise EditPlanError(f"operation {index} new must be a string")
    if "expect-count" in operation and "all" in operation:
        raise EditPlanError(f"operation {index} cannot combine expect-count and all")
    if "expect-count" in operation:
        count = operation["expect-count"]
        if isinstance(count, bool) or not isinstance(count, int) or count < 1:
            raise EditPlanError(f"operation {index} expect-count must be a positive integer")
    if "all" in operation and not isinstance(operation["all"], bool):
        raise EditPlanError(f"operation {index} all must be a boolean")


def _validate_frontmatter_operation(operation: dict[str, object], index: int) -> None:
    key = operation["key"]
    if not isinstance(key, str) or not _FRONTMATTER_KEY.fullmatch(key):
        raise EditPlanError(f"operation {index} key must be a valid frontmatter key")
    if key in _PROTECTED_FRONTMATTER_KEYS:
        raise EditPlanError(f"frontmatter field {key!r} is owned by a domain command")
    value = operation["value"]
    if isinstance(value, list):
        if not all(isinstance(item, str) for item in value):
            raise EditPlanError(f"operation {index} value list must contain only strings")
    elif not isinstance(value, (str, int, bool)):
        raise EditPlanError(f"operation {index} value has an unsupported frontmatter type")


def _apply_operation(source: bytes, operation: EditOperation, relative: str) -> bytes:
    try:
        document = parse_document(source)
    except (UnicodeError, DocumentError) as error:
        raise EditPlanError(f"cannot safely edit malformed document {relative}: {error}") from error

    kind = operation["op"]
    if kind == "frontmatter-set":
        metadata = dict(document.metadata)
        key = operation["key"]
        value = operation["value"]
        assert isinstance(key, str)
        assert isinstance(value, (str, int, bool, list))
        metadata[key] = value
        return render_document(replace(document, metadata=metadata))

    normalized_body = _normalize_newlines(document.body)
    anchor_key = "anchor" if kind in {"insert-before", "insert-after"} else "old"
    anchor = operation[anchor_key]
    assert isinstance(anchor, str)
    normalized_anchor = _normalize_newlines(anchor)
    actual = _match_count(normalized_body, normalized_anchor)
    _require_count(actual, operation)

    if kind == "replace":
        replacement = operation["new"]
    elif kind == "insert-before":
        replacement = str(operation["new"]) + normalized_anchor
    elif kind == "insert-after":
        replacement = normalized_anchor + str(operation["new"])
    else:
        replacement = ""
    normalized_replacement = _normalize_newlines(str(replacement))
    edited = normalized_body.replace(normalized_anchor, normalized_replacement)
    rendered_body = edited.replace("\n", document.newline).encode("utf-8")
    prefix = _raw_document_prefix(source, document)
    rendered = prefix + rendered_body

    try:
        reparsed = parse_document(rendered)
    except (UnicodeError, DocumentError) as error:
        raise EditPlanError(
            f"text edit would create an invalid frontmatter boundary in {relative}: {error}"
        ) from error
    if (
        _has_frontmatter(source) != _has_frontmatter(rendered)
        or reparsed.metadata != document.metadata
    ):
        raise EditPlanError(
            f"text edit would change frontmatter or protected lifecycle metadata in {relative}"
        )
    return rendered


def _raw_document_prefix(source: bytes, document: Document) -> bytes:
    body = document.body.encode("utf-8")
    if body:
        if not source.endswith(body):
            raise EditPlanError("document body does not match its exact source bytes")
        return source[: -len(body)]
    return source


def _has_frontmatter(source: bytes) -> bool:
    text = source.decode("utf-8-sig")
    first_line = text.splitlines(keepends=False)[:1]
    return bool(first_line and first_line[0] == "---")


def _normalize_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _validate_unicode_strings(value: object, index: int) -> None:
    if isinstance(value, str):
        try:
            value.encode("utf-8")
        except UnicodeEncodeError as error:
            raise EditPlanError(
                f"operation {index} contains text that is not valid Unicode scalar data"
            ) from error
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            _validate_unicode_strings(key, index)
            _validate_unicode_strings(item, index)
        return
    if isinstance(value, (list, tuple)):
        for item in value:
            _validate_unicode_strings(item, index)


def _json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise EditPlanError(f"duplicate JSON field: {key}")
        result[key] = value
    return result


def _match_count(text: str, needle: str) -> int:
    return text.count(needle)


def _require_count(actual: int, operation: EditOperation) -> None:
    if operation.get("all") is True:
        if actual == 0:
            raise EditConflict("expected at least one match, found 0")
        return
    expected = operation.get("expect-count", 1)
    assert isinstance(expected, int) and not isinstance(expected, bool)
    if actual != expected:
        raise EditConflict(f"expected {expected} match(es), found {actual}")


__all__ = [
    "EditConflict",
    "EditOperation",
    "EditPlanError",
    "load_operations",
    "plan_edits",
]

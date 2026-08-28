"""Limited, byte-preserving frontmatter handling for story documents."""

from __future__ import annotations

import copy
import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import TypeAlias


Scalar: TypeAlias = str | int | bool


class DocumentError(ValueError):
    """Raised when frontmatter needs an unsafe or unsupported interpretation."""


@dataclass(frozen=True)
class Document:
    """A story document and its limited frontmatter metadata.

    Parsed instances retain their original bytes privately so an unchanged
    document can be written back without formatting churn.
    """

    metadata: dict[str, Scalar | list[str]]
    body: str
    newline: str
    bom: bool
    _source_bytes: bytes | None = field(default=None, init=False, repr=False, compare=False)
    _original_metadata: dict[str, Scalar | list[str]] | None = field(
        default=None, init=False, repr=False, compare=False
    )
    _original_body: str | None = field(default=None, init=False, repr=False, compare=False)
    _original_newline: str | None = field(default=None, init=False, repr=False, compare=False)
    _original_bom: bool | None = field(default=None, init=False, repr=False, compare=False)


_KEY_LINE = re.compile(r"^([^\s:#][^:\r\n]*?):(?:[ \t]*(.*))?$")
_LIST_LINE = re.compile(r"^  -(?:[ \t](.*))?$")
_INTEGER = re.compile(r"^-?(?:0|[1-9][0-9]*)$")
_BLOCK_SCALAR = re.compile(r"^[>|][+-]?(?:[0-9]+)?(?:\s|$)")
_UNSUPPORTED_YAML_VALUE_PREFIXES = ("&", "*", "!", "{", "[")


def canonical_text(data: bytes) -> str:
    """Decode a UTF-8 document and normalize its byte-insignificant details."""

    text = data.decode("utf-8-sig")
    return text.replace("\r\n", "\n").replace("\r", "\n")


def logical_hash(data: bytes) -> str:
    """Return the stable SHA-256 hash used to identify document content."""

    return hashlib.sha256(canonical_text(data).encode("utf-8")).hexdigest()


def parse_document(data: bytes) -> Document:
    """Parse a document with the deliberately small supported frontmatter subset."""

    text = _decode_document(data)
    newline = _detect_newline(text)
    bom = data.startswith(b"\xef\xbb\xbf")
    lines = text.splitlines(keepends=True)

    if not lines or _line_content(lines[0]) != "---":
        return _parsed_document({}, text, newline, bom, data)

    closing_index = _find_closing_delimiter(lines)
    if closing_index is None:
        raise _error(len(lines) + 1, "unterminated frontmatter")

    metadata = _parse_metadata(lines[1:closing_index], first_line_number=2)
    body = "".join(lines[closing_index + 1 :])
    return _parsed_document(metadata, body, newline, bom, data)


def render_document(document: Document) -> bytes:
    """Render a document, retaining exact source bytes if its public content is unchanged."""

    if _matches_source(document):
        assert document._source_bytes is not None
        return document._source_bytes

    if document.newline not in {"\n", "\r\n", "\r"}:
        raise DocumentError("newline must be LF, CRLF, or CR")

    if document.metadata:
        lines = ["---"]
        for key, value in document.metadata.items():
            _validate_key(key)
            if isinstance(value, list):
                lines.append(f"{key}:")
                for item in value:
                    if not isinstance(item, str):
                        raise DocumentError(f"metadata list {key!r} must contain strings")
                    lines.append(f"  - {_render_string(item)}")
            elif isinstance(value, (str, int, bool)):
                lines.append(f"{key}: {_render_scalar(value)}")
            else:
                raise DocumentError(f"metadata value {key!r} has an unsupported type")
        lines.append("---")
        text = document.newline.join(lines) + document.newline + document.body
    else:
        text = document.body

    prefix = b"\xef\xbb\xbf" if document.bom else b""
    return prefix + text.encode("utf-8")


def _decode_document(data: bytes) -> str:
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        prefix = data[: error.start].decode("utf-8", errors="ignore")
        line_number = len(prefix.replace("\r\n", "\n").replace("\r", "\n").split("\n"))
        raise _error(line_number, "invalid UTF-8") from error


def _detect_newline(text: str) -> str:
    match = re.search(r"\r\n|\n|\r", text)
    return match.group(0) if match else "\n"


def _find_closing_delimiter(lines: list[str]) -> int | None:
    for index, line in enumerate(lines[1:], start=1):
        if _line_content(line) == "---":
            return index
    return None


def _parse_metadata(lines: list[str], first_line_number: int) -> dict[str, Scalar | list[str]]:
    metadata: dict[str, Scalar | list[str]] = {}
    list_key: str | None = None

    for offset, source_line in enumerate(lines):
        line_number = first_line_number + offset
        line = _line_content(source_line)
        if not line or line.startswith("#"):
            continue

        list_match = _LIST_LINE.match(line)
        if list_match:
            if list_key is None:
                raise _error(line_number, "list item has no preceding empty key")
            listed = metadata[list_key]
            assert isinstance(listed, list)
            listed.append(_parse_list_item(list_match.group(1) or "", line_number))
            continue

        if line[:1].isspace():
            if ":" in line:
                raise _error(line_number, "nested mapping is not supported")
            raise _error(line_number, "indented content is not supported")

        if line.startswith("-"):
            raise _error(line_number, "list item must be indented by two spaces")

        key_match = _KEY_LINE.match(line)
        if not key_match:
            raise _error(line_number, "unsupported frontmatter syntax")

        key, raw_value = key_match.groups()
        _validate_key(key, line_number)
        if key in metadata:
            raise _error(line_number, "duplicate key")

        value = _parse_scalar(raw_value or "", line_number)
        if raw_value is None or raw_value.strip() == "":
            metadata[key] = []
            list_key = key
        else:
            metadata[key] = value
            list_key = None

    for key, value in tuple(metadata.items()):
        if value == []:
            metadata[key] = ""
    return metadata


def _parse_scalar(value: str, line_number: int) -> Scalar:
    value = value.strip()
    if _BLOCK_SCALAR.match(value):
        raise _error(line_number, "block scalar is not supported")
    if not value:
        return ""
    if value.startswith('"'):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as error:
            raise _error(line_number, "invalid JSON string") from error
        if not isinstance(parsed, str):
            raise _error(line_number, "quoted scalar must be a string")
        return parsed
    if value.startswith("'"):
        if len(value) < 2 or not value.endswith("'"):
            raise _error(line_number, "unterminated single-quoted string")
        return value[1:-1].replace("''", "'")
    if value.startswith(_UNSUPPORTED_YAML_VALUE_PREFIXES):
        raise _error(line_number, "anchors, aliases, tags, and flow collections are not supported")
    if value in {"true", "false"}:
        return value == "true"
    if _INTEGER.fullmatch(value):
        return int(value)
    return value


def _parse_list_item(value: str, line_number: int) -> str:
    parsed = _parse_scalar(value, line_number)
    if isinstance(parsed, str):
        return parsed
    return value.strip()


def _parsed_document(
    metadata: dict[str, Scalar | list[str]], body: str, newline: str, bom: bool, source: bytes
) -> Document:
    document = Document(
        metadata=metadata,
        body=body,
        newline=newline,
        bom=bom,
    )
    object.__setattr__(document, "_source_bytes", source)
    object.__setattr__(document, "_original_metadata", copy.deepcopy(metadata))
    object.__setattr__(document, "_original_body", body)
    object.__setattr__(document, "_original_newline", newline)
    object.__setattr__(document, "_original_bom", bom)
    return document


def _matches_source(document: Document) -> bool:
    return (
        document._source_bytes is not None
        and document._original_metadata == document.metadata
        and document._original_body == document.body
        and document._original_newline == document.newline
        and document._original_bom == document.bom
    )


def _line_content(line: str) -> str:
    return line.rstrip("\r\n")


def _error(line_number: int, message: str) -> DocumentError:
    return DocumentError(f"line {line_number}: {message}")


def _validate_key(key: object, line_number: int | None = None) -> None:
    if not isinstance(key, str) or not _KEY_LINE.match(f"{key}:"):
        message = "invalid metadata key"
        if line_number is None:
            raise DocumentError(message)
        raise _error(line_number, message)


def _render_scalar(value: Scalar) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    return _render_string(value)


def _render_string(value: str) -> str:
    if (
        value
        and value == value.strip()
        and not _INTEGER.fullmatch(value)
        and value not in {"true", "false"}
        and not _BLOCK_SCALAR.match(value)
        and "\n" not in value
        and "\r" not in value
        and not value.startswith(("'", '"'))
    ):
        return value
    return json.dumps(value, ensure_ascii=False)


__all__ = [
    "Document",
    "DocumentError",
    "Scalar",
    "canonical_text",
    "logical_hash",
    "parse_document",
    "render_document",
]

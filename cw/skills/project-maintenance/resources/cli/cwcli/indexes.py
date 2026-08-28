"""Deterministic, fully derived registries for managed story documents."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from pathlib import PurePosixPath

from .documents import Document, parse_document, render_document
from .project import Project
from .schema import GENERATED_INDEX_FILES, allowed_document_kind
from .transactions import Change, TransactionPlan


_INDEX_TITLES = {
    "story/_index.md": "Story",
    "story/chapters/_index.md": "Chapters",
    "work/_index.md": "Work",
    "work/drafts/_index.md": "Drafts",
    "work/plans/_index.md": "Plans",
    "work/reviews/_index.md": "Reviews",
    "work/brainstorm/_index.md": "Brainstorm",
    "work/archive/_index.md": "Archive",
    "kb/_index.md": "Knowledge Base",
    "kb/characters/_index.md": "Characters",
    "kb/world/_index.md": "World",
    "kb/canon/_index.md": "Canon",
    "kb/continuity/_index.md": "Continuity",
    "kb/continuity/scenes/_index.md": "Scene Continuity",
    "kb/styles/_index.md": "Styles",
    "kb/samples/_index.md": "Samples",
    "kb/issues/_index.md": "Issues",
}

_FRONTMATTER_FIELDS = {
    "chapter": ("number", "title", "status"),
    "work-artifact": ("title", "status", "target", "subject", "base-revision"),
    "kb-content": ("title", "status", "subject", "class", "sources"),
    "continuity-scene": ("title", "status", "subject", "sources"),
    "continuity-record": ("title", "status"),
    "vocabulary": ("title", "status"),
}


def plan_reindex(
    project: Project,
    *,
    overlay: Iterable[Change] = (),
    index_ids: Iterable[str] | None = None,
) -> TransactionPlan:
    """Plan exact replacements for every stale generated registry."""

    selected = tuple(GENERATED_INDEX_FILES if index_ids is None else index_ids)
    if len(set(selected)) != len(selected) or any(
        index_id not in GENERATED_INDEX_FILES for index_id in selected
    ):
        raise ValueError("index_ids must contain unique generated index paths")

    documents: dict[str, Document] = {}
    for path in project.iter_managed_markdown():
        relative_id = project.relative_id(path)
        if not _is_relevant_to_indexes(relative_id, selected):
            continue
        if allowed_document_kind(relative_id) not in {
            "chapter",
            "work-artifact",
            "kb-content",
            "continuity-scene",
            "continuity-record",
            "vocabulary",
        }:
            continue
        document = parse_document(path.read_bytes())
        if _is_indexable(relative_id, document):
            documents[relative_id] = document

    overlay_changes = tuple(overlay)
    for change in overlay_changes:
        if not _is_relevant_to_indexes(change.path, selected):
            continue
        if change.after is None:
            documents.pop(change.path, None)
            continue
        kind = allowed_document_kind(change.path)
        if kind == "generated-index":
            continue
        document = parse_document(change.after)
        if _is_indexable(change.path, document):
            documents[change.path] = document
        else:
            documents.pop(change.path, None)

    ordered_documents = sorted(documents.items())

    changes: list[Change] = []
    for index_id in selected:
        target = project.resolve(index_id, for_write=True)
        before = target.read_bytes() if target.is_file() and not target.is_symlink() else None
        if before is None:
            rendered = render_index(index_id, ordered_documents)
        else:
            newline, bom = _source_format(before)
            rendered = render_index(
                index_id,
                ordered_documents,
                newline=newline,
                bom=bom,
            )
        if before != rendered:
            changes.append(Change(index_id, before, rendered))
    return TransactionPlan(
        command=("reindex",),
        changes=tuple(changes),
        metadata={"derived": True, "undoable": True},
    )


def _is_relevant_to_indexes(relative_id: str, index_ids: tuple[str, ...]) -> bool:
    path = PurePosixPath(relative_id)
    return any(
        _is_beneath(path, PurePosixPath(index_id).parent)
        for index_id in index_ids
    )


def _is_indexable(relative_id: str, document: Document) -> bool:
    kind = allowed_document_kind(relative_id)
    if kind not in {
        "chapter",
        "work-artifact",
        "kb-content",
        "continuity-scene",
        "continuity-record",
        "vocabulary",
    }:
        return False
    status = document.metadata.get("status")
    if status == "archived":
        return False
    if relative_id.startswith("work/archive/"):
        return status in {"accepted", "abandoned"}
    return True


def render_index(
    index_id: str,
    documents: Iterable[tuple[str, Document]] = (),
    *,
    newline: str = "\n",
    bom: bool = False,
) -> bytes:
    """Render one registry from documents beneath its authored directory."""

    title = _INDEX_TITLES[index_id]
    parent = PurePosixPath(index_id).parent
    entries = [
        _render_entry(relative_id, document)
        for relative_id, document in documents
        if _is_beneath(PurePosixPath(relative_id), parent)
    ]
    body = f"# {title}\n\n<!-- generated registry -->\n"
    if entries:
        body += "\n" + "\n".join(entries) + "\n"
    if newline != "\n":
        body = body.replace("\n", newline)
    return render_document(
        Document(metadata={"generated": True}, body=body, newline=newline, bom=bom)
    )


def _is_beneath(path: PurePosixPath, directory: PurePosixPath) -> bool:
    try:
        path.relative_to(directory)
    except ValueError:
        return False
    return True


def _render_entry(relative_id: str, document: Document) -> str:
    kind = allowed_document_kind(relative_id)
    fields = _FRONTMATTER_FIELDS.get(kind or "", ())
    details = [
        f"{key}={json.dumps(document.metadata[key], ensure_ascii=False, sort_keys=True)}"
        for key in fields
        if key in document.metadata
    ]
    suffix = "" if not details else " — " + "; ".join(details)
    return f"- `{relative_id}`{suffix}"


def _source_format(data: bytes) -> tuple[str, bool]:
    text = data.decode("utf-8-sig")
    match = re.search(r"\r\n|\n|\r", text)
    return (match.group(0) if match else "\n", data.startswith(b"\xef\xbb\xbf"))


__all__ = ["plan_reindex", "render_index"]

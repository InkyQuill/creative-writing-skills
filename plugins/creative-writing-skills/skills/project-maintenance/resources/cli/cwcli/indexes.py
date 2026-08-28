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


def plan_reindex(project: Project) -> TransactionPlan:
    """Plan exact replacements for every stale generated registry."""

    documents: list[tuple[str, Document]] = []
    for path in project.iter_managed_markdown():
        relative_id = project.relative_id(path)
        kind = allowed_document_kind(relative_id)
        if kind not in {"chapter", "work-artifact", "kb-content", "continuity-scene"}:
            continue
        if relative_id.startswith("work/archive/"):
            continue
        document = parse_document(path.read_bytes())
        if document.metadata.get("status") == "archived":
            continue
        documents.append((relative_id, document))
    documents.sort(key=lambda item: item[0])

    changes: list[Change] = []
    for index_id in GENERATED_INDEX_FILES:
        target = project.resolve(index_id, for_write=True)
        before = target.read_bytes() if target.is_file() and not target.is_symlink() else None
        if before is None:
            rendered = render_index(index_id, documents)
        else:
            newline, bom = _source_format(before)
            rendered = render_index(
                index_id,
                documents,
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

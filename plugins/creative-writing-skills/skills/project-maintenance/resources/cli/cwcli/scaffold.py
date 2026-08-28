"""Deterministic rendering for a new story project scaffold."""

from __future__ import annotations

from .documents import Document, render_document
from .schema import SCHEMA_VERSION, SCAFFOLD_FILES


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

_STARTER_DOCUMENTS = {
    "kb/vocab.md": (
        "Vocabulary",
        "# Vocabulary\n\nRecord canonical names, spellings, aliases, and terminology here.\n",
    ),
    "kb/continuity/timeline.md": (
        "Timeline",
        "# Timeline\n\nRecord established events in story order.\n",
    ),
    "kb/continuity/state.md": (
        "State",
        "# State\n\nRecord the current durable state of characters, places, and unresolved changes.\n",
    ),
    "kb/continuity/promises.md": (
        "Promises",
        "# Promises\n\nRecord setups, reader expectations, and planned payoffs.\n",
    ),
    "kb/continuity/questions.md": (
        "Questions",
        "# Questions\n\nRecord open continuity questions that need an author decision.\n",
    ),
}


def render_scaffold(title: str, language: str) -> dict[str, bytes]:
    """Render every authored file in a new project in stable path order."""

    rendered: dict[str, bytes] = {}
    for relative_id in SCAFFOLD_FILES:
        if relative_id == "project.md":
            rendered[relative_id] = _render_manifest(title, language)
        elif relative_id in _INDEX_TITLES:
            rendered[relative_id] = _render_index(_INDEX_TITLES[relative_id])
        else:
            document_title, body = _STARTER_DOCUMENTS[relative_id]
            rendered[relative_id] = _render_document({"title": document_title}, body)
    return rendered


def _render_manifest(title: str, language: str) -> bytes:
    body = (
        f"# {title}\n\n"
        "## Project instructions\n\n"
        "Keep manuscript prose in `story/chapters/`. Keep plans, drafts, reviews, and brainstorming "
        "in `work/`. Record durable story knowledge in `kb/`, and keep project-specific conventions "
        "and decisions in this manifest.\n"
    )
    return _render_document(
        {
            "schema-version": SCHEMA_VERSION,
            "title": title,
            "language": language,
            "status": "planning",
        },
        body,
    )


def _render_index(title: str) -> bytes:
    return _render_document({"generated": True}, f"# {title}\n\n<!-- generated registry -->\n")


def _render_document(metadata: dict[str, str | int | bool], body: str) -> bytes:
    return render_document(Document(metadata=metadata, body=body, newline="\n", bom=False))

"""Schema v1 metadata validation for story projects."""

from __future__ import annotations

import re

from .documents import Document
from .findings import Finding


SCHEMA_VERSION = 1
PROJECT_STATUSES = frozenset({"planning", "drafting", "revising", "complete", "archived"})
DRAFT_STATUSES = frozenset({"working", "review", "ready"})
WORLD_CLASSES = frozenset({"location", "faction", "system", "artifact", "concept"})
SCAFFOLD_FILES: tuple[str, ...] = (
    "kb/_index.md",
    "kb/canon/_index.md",
    "kb/characters/_index.md",
    "kb/continuity/_index.md",
    "kb/continuity/promises.md",
    "kb/continuity/questions.md",
    "kb/continuity/scenes/_index.md",
    "kb/continuity/state.md",
    "kb/continuity/timeline.md",
    "kb/issues/_index.md",
    "kb/samples/_index.md",
    "kb/styles/_index.md",
    "kb/vocab.md",
    "kb/world/_index.md",
    "project.md",
    "story/_index.md",
    "story/chapters/_index.md",
    "work/_index.md",
    "work/archive/_index.md",
    "work/brainstorm/_index.md",
    "work/drafts/_index.md",
    "work/plans/_index.md",
    "work/reviews/_index.md",
)

_DRAFT_TARGET = re.compile(r"story/chapters/[^/]+\.md\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


def validate_metadata(relative_id: str, document: Document) -> list[Finding]:
    """Return schema-v1 findings for one project-relative Markdown document."""

    if relative_id == "project.md":
        return _validate_manifest(document.metadata, relative_id)

    findings = _validate_document_identity(document.metadata, relative_id)
    if relative_id.endswith("/_index.md"):
        return findings
    if relative_id.startswith("story/chapters/"):
        findings.extend(_validate_chapter(document.metadata, relative_id))
    elif relative_id.startswith("work/drafts/"):
        findings.extend(_validate_draft(document.metadata, relative_id))
    elif relative_id.startswith(("work/plans/", "work/reviews/", "work/brainstorm/")):
        findings.extend(_validate_work_artifact(document.metadata, relative_id))
    elif relative_id.startswith("kb/world/"):
        findings.extend(_validate_world_page(document.metadata, relative_id))
    elif relative_id.startswith("kb/"):
        findings.extend(_validate_sources(document.metadata, relative_id, required=False))
    return findings


def _validate_manifest(metadata: dict[str, object], relative_id: str) -> list[Finding]:
    findings = []
    if metadata.get("schema-version") != SCHEMA_VERSION:
        findings.append(_error("invalid-schema-version", "schema-version must be 1", relative_id))
    findings.extend(_validate_non_empty_string(metadata, "title", relative_id))
    findings.extend(_validate_non_empty_string(metadata, "language", relative_id))
    if metadata.get("status") not in PROJECT_STATUSES:
        statuses = ", ".join(sorted(PROJECT_STATUSES))
        findings.append(_error("invalid-project-status", f"status must be one of: {statuses}", relative_id))
    return findings


def _validate_document_identity(metadata: dict[str, object], relative_id: str) -> list[Finding]:
    findings = []
    if "id" in metadata:
        findings.append(
            _error("repeated-document-id", "document identity is inferred from its project-relative path", relative_id)
        )
    if "type" in metadata:
        findings.append(
            _error("repeated-document-type", "document type is inferred from its directory", relative_id)
        )
    return findings


def _validate_chapter(metadata: dict[str, object], relative_id: str) -> list[Finding]:
    findings = []
    number = metadata.get("number")
    if not isinstance(number, int) or isinstance(number, bool) or number < 1:
        findings.append(_error("invalid-chapter-number", "number must be a positive integer", relative_id))
    findings.extend(_validate_non_empty_string(metadata, "title", relative_id))
    status = metadata.get("status")
    if status is not None and status not in {"accepted", "final"}:
        findings.append(_error("invalid-chapter-status", "status must be accepted or final", relative_id))
    return findings


def _validate_draft(metadata: dict[str, object], relative_id: str) -> list[Finding]:
    findings = []
    target = metadata.get("target")
    target_is_manuscript_chapter = isinstance(target, str) and bool(_DRAFT_TARGET.fullmatch(target))
    if not target_is_manuscript_chapter:
        findings.append(
            _error("invalid-draft-target", "target must be a story/chapters/*.md path", relative_id)
        )

    if metadata.get("status") not in DRAFT_STATUSES:
        statuses = ", ".join(sorted(DRAFT_STATUSES))
        findings.append(_error("invalid-draft-status", f"status must be one of: {statuses}", relative_id))

    if "base-revision" not in metadata:
        if target_is_manuscript_chapter:
            findings.append(
                Finding(
                    code="needs-context-draft-target",
                    severity="info",
                    message="NEEDS_CONTEXT: target existence determines whether base-revision is required",
                    path=relative_id,
                    next_action="Use a project-aware draft checker to inspect the target.",
                )
            )
    elif not isinstance(metadata["base-revision"], str) or not _SHA256.fullmatch(metadata["base-revision"]):
        findings.append(
            _error("invalid-base-revision", "base-revision must be a lowercase SHA-256 identifier", relative_id)
        )
    return findings


def _validate_work_artifact(metadata: dict[str, object], relative_id: str) -> list[Finding]:
    findings = _validate_non_empty_string(metadata, "subject", relative_id)
    findings.extend(_validate_non_empty_string(metadata, "status", relative_id))
    return findings


def _validate_world_page(metadata: dict[str, object], relative_id: str) -> list[Finding]:
    findings = []
    if metadata.get("class") not in WORLD_CLASSES:
        classes = ", ".join(sorted(WORLD_CLASSES))
        findings.append(_error("invalid-world-class", f"class must be one of: {classes}", relative_id))
    findings.extend(_validate_sources(metadata, relative_id, required=True))
    return findings


def _validate_sources(
    metadata: dict[str, object], relative_id: str, *, required: bool
) -> list[Finding]:
    if "sources" not in metadata:
        return [_error("missing-sources", "sources must be a list of strings", relative_id)] if required else []
    sources = metadata["sources"]
    if not isinstance(sources, list) or not all(isinstance(source, str) for source in sources):
        return [_error("invalid-sources", "sources must be a list of strings", relative_id)]
    return []


def _validate_non_empty_string(metadata: dict[str, object], key: str, relative_id: str) -> list[Finding]:
    value = metadata.get(key)
    if not isinstance(value, str) or not value.strip():
        return [_error(f"invalid-{key}", f"{key} must be a non-empty string", relative_id)]
    return []


def _error(code: str, message: str, relative_id: str) -> Finding:
    return Finding(code=code, severity="error", message=message, path=relative_id)

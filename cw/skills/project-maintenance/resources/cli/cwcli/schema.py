"""Schema-v1 structural validation for story projects."""

from __future__ import annotations

import re
from pathlib import PurePosixPath

from .documents import Document
from .findings import Finding


SCHEMA_VERSION = 1
SUPPORTED_SCHEMA_VERSIONS = (1, 2)
PROJECT_STATUSES = frozenset({"planning", "drafting", "revising", "complete", "archived"})
GENERATED_INDEX_FILES: tuple[str, ...] = (
    "kb/_index.md",
    "kb/canon/_index.md",
    "kb/characters/_index.md",
    "kb/continuity/_index.md",
    "kb/continuity/scenes/_index.md",
    "kb/issues/_index.md",
    "kb/samples/_index.md",
    "kb/styles/_index.md",
    "kb/world/_index.md",
    "story/_index.md",
    "story/chapters/_index.md",
    "story/side-stories/_index.md",
    "work/_index.md",
    "work/archive/_index.md",
    "work/brainstorm/_index.md",
    "work/drafts/_index.md",
    "work/plans/_index.md",
    "work/reviews/_index.md",
)

CONTINUITY_RECORD_FILES = frozenset(
    {
        "kb/continuity/promises.md",
        "kb/continuity/questions.md",
        "kb/continuity/state.md",
        "kb/continuity/timeline.md",
    }
)

SCAFFOLD_FILES: tuple[str, ...] = tuple(
    sorted((*GENERATED_INDEX_FILES, *CONTINUITY_RECORD_FILES, "kb/vocab.md", "project.md"))
)

SCAFFOLD_DIRECTORIES: tuple[str, ...] = (
    ".creative-writing",
    ".creative-writing/context",
    ".creative-writing/transactions",
    "kb",
    "kb/canon",
    "kb/characters",
    "kb/continuity",
    "kb/continuity/scenes",
    "kb/issues",
    "kb/samples",
    "kb/styles",
    "kb/world",
    "story",
    "story/chapters",
    "story/side-stories",
    "work",
    "work/archive",
    "work/brainstorm",
    "work/drafts",
    "work/plans",
    "work/reviews",
)

WORK_ARTIFACT_DIRECTORIES = frozenset(
    {"work/archive", "work/brainstorm", "work/drafts", "work/plans", "work/reviews"}
)
KB_CONTENT_DIRECTORIES = frozenset(
    {"kb/canon", "kb/characters", "kb/issues", "kb/samples", "kb/styles", "kb/world"}
)

INVALID_SCHEMA_VERSION = "CW-SCHEMA-001"
INVALID_TITLE = "CW-SCHEMA-010"
INVALID_LANGUAGE = "CW-SCHEMA-011"
INVALID_PROJECT_STATUS = "CW-SCHEMA-012"
INVALID_PROSE_PROFILE = "CW-SCHEMA-013"
REPEATED_DOCUMENT_ID = "CW-SCHEMA-020"
REPEATED_DOCUMENT_TYPE = "CW-SCHEMA-021"
INVALID_CHAPTER_NUMBER = "CW-SCHEMA-030"
INVALID_SIDE_STORY_AFTER = "CW-SCHEMA-031"
INVALID_SIDE_STORY_SUBTYPE = "CW-SCHEMA-032"
INVALID_GENERATED_MARKER = "CW-SCHEMA-040"


def allowed_document_kind(relative_id: str, *, schema_version: int = 1) -> str | None:
    """Return the schema-v1 path-inferred kind for an allowed Markdown path."""

    if schema_version == 2:
        from .translation.contract import translation_kind
        kind = translation_kind(relative_id)
        if kind is not None:
            return kind
    if relative_id == "project.md":
        return "manifest"
    if relative_id in GENERATED_INDEX_FILES:
        return "generated-index"
    if relative_id == "kb/vocab.md":
        return "vocabulary"
    if relative_id in CONTINUITY_RECORD_FILES:
        return "continuity-record"

    path = PurePosixPath(relative_id)
    if path.suffix != ".md" or path.name == "_index.md":
        return None
    parent = path.parent.as_posix()
    if parent == "story/chapters":
        return "chapter"
    if parent == "story/side-stories":
        return "side-story"
    if parent in WORK_ARTIFACT_DIRECTORIES:
        return "work-artifact"
    if parent in KB_CONTENT_DIRECTORIES:
        return "kb-content"
    if parent == "kb/continuity/scenes":
        return "continuity-scene"
    return None


def validate_metadata(
    relative_id: str, document: Document, *, kind_override: str | None = None
) -> list[Finding]:
    """Return findings for structurally defined schema-v1 metadata only.

    Artifact-specific semantic fields and Markdown table columns are deliberately
    unconstrained in schema v1. Tightening them requires a future schema version.
    """

    kind = kind_override or allowed_document_kind(relative_id)
    if kind == "manifest":
        return _validate_manifest(document.metadata, relative_id)

    findings = _validate_document_identity(document.metadata, relative_id)
    if kind == "generated-index":
        if document.metadata.get("generated") is not True:
            findings.append(
                _warning(
                    INVALID_GENERATED_MARKER,
                    "generated index frontmatter must contain generated: true",
                    relative_id,
                    "Regenerate this index from the authored files in its directory.",
                )
            )
    elif kind == "chapter":
        number = document.metadata.get("number")
        if not isinstance(number, int) or isinstance(number, bool) or number < 1:
            findings.append(
                _warning(
                    INVALID_CHAPTER_NUMBER,
                    "number must be a positive non-boolean integer for deterministic chapter ordering",
                    relative_id,
                    "Set number to a unique positive integer after confirming the intended chapter order.",
                )
            )
    elif kind == "side-story":
        after = document.metadata.get("after")
        if not _is_manuscript_reference(after, allow_selected_parent=kind_override is not None):
            findings.append(
                _warning(
                    INVALID_SIDE_STORY_AFTER,
                    "after must name a direct chapter or side-story Markdown document",
                    relative_id,
                    "Set after to the durable manuscript path that anchors this side story's placement.",
                )
            )
        subtype = document.metadata.get("subtype")
        if subtype is not None and (
            not isinstance(subtype, str)
            or re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", subtype) is None
        ):
            findings.append(
                _warning(
                    INVALID_SIDE_STORY_SUBTYPE,
                    "subtype must be a lower-case slug when present",
                    relative_id,
                    "Use a stable subtype such as omake or interlude, or remove the optional field.",
                )
            )
    return findings


def _is_manuscript_reference(value: object, *, allow_selected_parent: bool = False) -> bool:
    if not isinstance(value, str):
        return False
    path = PurePosixPath(value)
    return (
        str(path) == value
        and not path.is_absolute()
        and ".." not in path.parts
        and (allow_selected_parent or path.parent.as_posix() in {"story/chapters", "story/side-stories"})
        and path.parent.as_posix() != "."
        and path.name != "_index.md"
        and path.suffix.casefold() == ".md"
    )


def _validate_manifest(metadata: dict[str, object], relative_id: str) -> list[Finding]:
    findings: list[Finding] = []
    schema_version = metadata.get("schema-version")
    if not isinstance(schema_version, int) or isinstance(schema_version, bool) or schema_version not in SUPPORTED_SCHEMA_VERSIONS:
        findings.append(
            Finding(
                code=INVALID_SCHEMA_VERSION,
                severity="error",
                message="schema-version must be a supported non-boolean integer 1 or 2",
                path=relative_id,
                next_action=(
                    "Inspect or migrate the project contract, then set schema-version to the matching "
                    "supported version (1 or 2)."
                ),
            )
        )
    if schema_version == 2:
        from .translation.contract import project_settings
        try:
            project_settings(metadata)
        except ValueError as error:
            findings.append(Finding(code=INVALID_SCHEMA_VERSION, severity="error", message=str(error), path=relative_id, next_action="Repair v2 project settings."))
    findings.extend(
        _validate_non_empty_string(
            metadata,
            "title",
            INVALID_TITLE,
            relative_id,
            "Set title to the author's non-empty project title without changing manuscript content.",
        )
    )
    if "prose-profile" in metadata:
        value = metadata["prose-profile"]
        if not isinstance(value, str) or re.fullmatch(
            r"[a-z0-9]+(?:-[a-z0-9]+)*", value
        ) is None:
            findings.append(
                _warning(
                    INVALID_PROSE_PROFILE,
                    "prose-profile must be a non-empty lower-case slug using letters, numbers, and internal hyphens",
                    relative_id,
                    "Preserve the intended profile and rewrite its selector as a lower-case slug.",
                )
            )
    findings.extend(
        _validate_non_empty_string(
            metadata,
            "language",
            INVALID_LANGUAGE,
            relative_id,
            "Set language to the non-empty language identifier used by this project.",
        )
    )
    if metadata.get("status") not in PROJECT_STATUSES:
        statuses = ", ".join(sorted(PROJECT_STATUSES))
        findings.append(
            _warning(
                INVALID_PROJECT_STATUS,
                f"status must be one of: {statuses}",
                relative_id,
                f"After confirming the project lifecycle, set status to one of: {statuses}.",
            )
        )
    return findings


def prose_profile(metadata: dict[str, object]) -> str:
    """Return the schema-v1 prose profile, applying its additive default."""

    value = metadata.get("prose-profile")
    return value if isinstance(value, str) and value else "general"


def _validate_document_identity(metadata: dict[str, object], relative_id: str) -> list[Finding]:
    findings: list[Finding] = []
    if "id" in metadata:
        findings.append(
            _warning(
                REPEATED_DOCUMENT_ID,
                "document identity is inferred from its project-relative path",
                relative_id,
                "Remove the redundant id field; keep the file at the same path to preserve its identity.",
            )
        )
    if "type" in metadata:
        findings.append(
            _warning(
                REPEATED_DOCUMENT_TYPE,
                "document type is inferred from its allowed directory",
                relative_id,
                "Remove the redundant type field after confirming the file is in its intended directory.",
            )
        )
    return findings


def _validate_non_empty_string(
    metadata: dict[str, object],
    key: str,
    code: str,
    relative_id: str,
    next_action: str,
) -> list[Finding]:
    value = metadata.get(key)
    if not isinstance(value, str) or not value.strip():
        return [_warning(code, f"{key} must be a non-empty string", relative_id, next_action)]
    return []


def _warning(code: str, message: str, relative_id: str, next_action: str) -> Finding:
    return Finding(
        code=code,
        severity="warning",
        message=message,
        path=relative_id,
        next_action=next_action,
    )


__all__ = [
    "CONTINUITY_RECORD_FILES",
    "GENERATED_INDEX_FILES",
    "KB_CONTENT_DIRECTORIES",
    "PROJECT_STATUSES",
    "INVALID_PROSE_PROFILE",
    "SCAFFOLD_DIRECTORIES",
    "SCAFFOLD_FILES",
    "SCHEMA_VERSION",
    "WORK_ARTIFACT_DIRECTORIES",
    "allowed_document_kind",
    "prose_profile",
    "validate_metadata",
]


def required_paths(metadata):
    from .translation.contract import project_settings
    kind, _, enabled = project_settings(metadata)
    if not enabled and metadata.get("scaffold-template") == "compact":
        return (
            ".creative-writing", ".creative-writing/context",
            ".creative-writing/transactions",
        ), ("project.md", ".cws-layout.json")
    if not enabled:
        return SCAFFOLD_DIRECTORIES, SCAFFOLD_FILES
    extra_dirs = ('sources', 'translations', 'kb/entities', 'kb/source-comparisons')
    extra_files = tuple(p + '/_index.md' for p in extra_dirs)
    dirs, files = SCAFFOLD_DIRECTORIES, SCAFFOLD_FILES
    if kind == 'translation':
        dirs = tuple(p for p in dirs if p in ('.creative-writing', '.creative-writing/context', '.creative-writing/transactions', 'kb'))
        files = ('project.md', 'kb/_index.md')
    return tuple(sorted(set(dirs + extra_dirs))), tuple(sorted(set(files + extra_files)))

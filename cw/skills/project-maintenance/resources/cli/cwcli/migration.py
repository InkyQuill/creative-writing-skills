"""Read-only planning and strict validation for story-project migrations."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import unicodedata
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from types import MappingProxyType
from typing import Mapping

from .documents import Document, parse_document, render_document
from .indexes import plan_reindex
from .project import Project
from .scaffold import render_scaffold
from .schema import GENERATED_INDEX_FILES, SCAFFOLD_DIRECTORIES, allowed_document_kind
from .transactions import Change, TransactionPlan


PLAN_VERSION = 1
TARGET_SCHEMA = 1
_PLAN_KEYS = frozenset(
    {"plan-version", "source-schema", "target-schema", "operations", "unresolved", "plan-hash"}
)
_MOVE_OPERATION_KEYS = frozenset({"source", "destination", "action"})
_MERGE_OPERATION_KEYS = frozenset({"sources", "destination", "action", "content"})
_UNRESOLVED_KEYS = frozenset({"sources", "destination", "reason"})
_A_ROOTS = frozenset(
    {"chapters", "drafts", "characters", "worldbuilding", "samples", "style", "styles", "plot"}
)
_CONTINUITY_NAMES = frozenset({"timeline.md", "state.md", "promises.md", "questions.md"})
_WINDOWS_RESERVED_NAMES = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{number}" for number in range(1, 10)}
    | {f"LPT{number}" for number in range(1, 10)}
)
_WINDOWS_FORBIDDEN_CHARACTERS = frozenset('<>:"\\|?*')


class MigrationPlanError(ValueError):
    """Raised when a migration plan or source tree is unsafe or malformed."""


@dataclass(frozen=True)
class MigrationOperation:
    """One mechanical migration operation over project-relative paths."""

    source: str | None
    destination: str
    action: str
    sources: tuple[str, ...] = ()
    content: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "sources", tuple(self.sources))

    def to_payload(self) -> dict[str, object]:
        if self.action == "merge":
            return {
                "sources": list(self.sources),
                "destination": self.destination,
                "action": self.action,
                "content": self.content,
            }
        return {
            "source": self.source,
            "destination": self.destination,
            "action": self.action,
        }


@dataclass(frozen=True)
class MigrationPlan:
    """A complete immutable migration preview."""

    plan_version: int
    source_schema: int
    target_schema: int
    operations: tuple[MigrationOperation, ...]
    unresolved: tuple[Mapping[str, object], ...]
    plan_hash: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "operations", tuple(self.operations))
        object.__setattr__(
            self,
            "unresolved",
            tuple(
                MappingProxyType(
                    {
                        "sources": tuple(item["sources"]),
                        "destination": item["destination"],
                        "reason": item["reason"],
                    }
                )
                for item in self.unresolved
            ),
        )

    def to_payload(self, *, include_hash: bool = True) -> dict[str, object]:
        """Return the canonical JSON-compatible representation of this plan."""

        payload: dict[str, object] = {
            "plan-version": self.plan_version,
            "source-schema": self.source_schema,
            "target-schema": self.target_schema,
            "operations": [operation.to_payload() for operation in self.operations],
            "unresolved": [
                {
                    "sources": list(item["sources"]),
                    "destination": item["destination"],
                    "reason": item["reason"],
                }
                for item in self.unresolved
            ],
        }
        if include_hash:
            payload["plan-hash"] = self.plan_hash
        return payload


def canonical_plan_hash(payload: dict[str, object]) -> str:
    """Hash a plan payload's strict canonical JSON, excluding its stored hash."""

    if not isinstance(payload, dict):
        raise TypeError("migration plan payload must be a dictionary")
    canonical_payload = dict(payload)
    canonical_payload.pop("plan-hash", None)
    encoded = json.dumps(
        canonical_payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def plan_migration(root: Path) -> MigrationPlan:
    """Inspect a legacy tree without following links or changing any bytes."""

    root = Path(root).absolute()
    _require_real_directory(root, "migration root")
    paths = _walk_markdown(root)
    path_set = set(paths)
    source_schema = _source_schema(root)
    if source_schema > TARGET_SCHEMA:
        raise MigrationPlanError(f"cannot plan a downgrade from schema {source_schema}")

    layout_a_evidence = tuple(path for path in paths if _is_layout_a(path))
    layout_b_evidence = tuple(path for path in paths if _is_layout_b(path))
    mixed_layout = bool(layout_a_evidence and layout_b_evidence)

    operations: list[MigrationOperation] = []
    unresolved: list[dict[str, object]] = []
    handled: set[str] = set()

    if "project.md" in path_set and source_schema == 0:
        try:
            _legacy_manifest_document(
                _read_regular_file_no_follow(root / "project.md", "project manifest"),
                root.name or "Migrated Story",
            )
        except (MigrationPlanError, UnicodeError, ValueError) as error:
            unresolved.append(
                _unresolved(("project.md",), "project.md", f"manifest-upgrade: {error}")
            )
            handled.add("project.md")

    instruction_paths = tuple(path for path in paths if _is_platform_instruction(path))
    for path in instruction_paths:
        unresolved.append(_unresolved((path,), "project.md", "project-instructions"))
        handled.add(path)

    domain_vocab = tuple(path for path in paths if path != "kb/vocab.md" and _basename(path) == "vocab.md")
    if domain_vocab:
        vocab_sources = domain_vocab + (("kb/vocab.md",) if "kb/vocab.md" in path_set else ())
        unresolved.append(_unresolved(vocab_sources, "kb/vocab.md", "domain-vocab-merge"))
        handled.update(domain_vocab)
        if "kb/vocab.md" in path_set:
            handled.add("kb/vocab.md")

    timeline_sources = tuple(
        path
        for path in paths
        if (
            path in {"plot/timeline.md", "kb/timeline.md", "kb/continuity/timeline.md"}
            or _parts(path)[:2] == ("kb", "timeline")
        )
        and _basename(path) != "_index.md"
    )
    if len(timeline_sources) > 1:
        unresolved.append(_unresolved(timeline_sources, "kb/continuity/timeline.md", "timeline-merge"))
        handled.update(timeline_sources)

    if mixed_layout:
        mixed_sources = tuple(sorted(set(layout_a_evidence + layout_b_evidence), key=_path_sort_key))
        unresolved.append(_unresolved(mixed_sources, None, "mixed-layout"))
        handled.update(mixed_sources)

    for path in paths:
        if path in handled or _basename(path) == "_index.md":
            continue
        destination = _canonical_destination(path, timeline_count=len(timeline_sources))
        if destination is None:
            unresolved.append(_unresolved((path,), None, "unknown-role"))
            continue
        try:
            _source_path(path, "migration source")
            _strict_path(path, "portable migration source")
            destination = _portable_destination(destination)
            _strict_path(destination, "migration destination")
        except MigrationPlanError as error:
            proposed_destination = _portable_destination(destination)
            try:
                _strict_path(proposed_destination, "migration destination")
            except MigrationPlanError:
                proposed_destination = None
            unresolved.append(
                _unresolved(
                    (path,), proposed_destination, f"nonportable-source: {error}"
                )
            )
            continue
        action = "preserve" if path == destination else "move"
        operations.append(MigrationOperation(path, destination, action))

    operations, collision_records = _remove_destination_collisions(operations, path_set)
    unresolved.extend(collision_records)
    operations.sort(
        key=lambda item: (
            _path_sort_key(item.destination),
            tuple(_path_sort_key(source) for source in _operation_sources(item)),
            item.action,
        )
    )
    unresolved.sort(key=_unresolved_sort_key)
    _validate_generated_plan(operations, unresolved)

    payload: dict[str, object] = {
        "plan-version": PLAN_VERSION,
        "source-schema": source_schema,
        "target-schema": TARGET_SCHEMA,
        "operations": [
            item.to_payload()
            for item in operations
        ],
        "unresolved": unresolved,
    }
    return MigrationPlan(
        plan_version=PLAN_VERSION,
        source_schema=source_schema,
        target_schema=TARGET_SCHEMA,
        operations=tuple(operations),
        unresolved=tuple(unresolved),
        plan_hash=canonical_plan_hash(payload),
    )


def load_migration_plan(path: Path, root: Path | None = None) -> MigrationPlan:
    """Load a plan, checking filesystem boundaries only against an explicit root."""

    path = Path(path).absolute()
    migration_root = Path(root).absolute() if root is not None else None
    try:
        raw = _read_regular_file_no_follow(path, "migration plan")
        payload = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise MigrationPlanError("migration plan must be valid UTF-8 JSON") from error
    if not isinstance(payload, dict):
        raise MigrationPlanError("migration plan must be a JSON object")
    _require_exact_keys(payload, _PLAN_KEYS, "migration plan")

    plan_version = _strict_integer(payload["plan-version"], "plan-version")
    source_schema = _strict_integer(payload["source-schema"], "source-schema", minimum=0)
    target_schema = _strict_integer(payload["target-schema"], "target-schema")
    if plan_version != PLAN_VERSION:
        raise MigrationPlanError(f"unsupported plan-version: {plan_version}")
    if source_schema > TARGET_SCHEMA:
        raise MigrationPlanError(f"unsupported source-schema: {source_schema}")
    if target_schema != TARGET_SCHEMA:
        raise MigrationPlanError(f"unsupported target-schema: {target_schema}")

    stored_hash = payload["plan-hash"]
    if not isinstance(stored_hash, str) or len(stored_hash) != 64 or any(
        character not in "0123456789abcdef" for character in stored_hash
    ):
        raise MigrationPlanError("plan-hash must be a lowercase SHA-256 digest")
    if canonical_plan_hash(payload) != stored_hash:
        raise MigrationPlanError("migration plan hash mismatch")

    raw_operations = payload["operations"]
    if not isinstance(raw_operations, list):
        raise MigrationPlanError("operations must be a JSON array")
    operations: list[MigrationOperation] = []
    source_identities: set[tuple[str, ...]] = set()
    destination_identities: set[tuple[str, ...]] = set()
    for index, item in enumerate(raw_operations):
        if not isinstance(item, dict):
            raise MigrationPlanError(f"operations[{index}] must be an object")
        action = item.get("action")
        expected_keys = _MERGE_OPERATION_KEYS if action == "merge" else _MOVE_OPERATION_KEYS
        _require_exact_keys(item, expected_keys, f"operations[{index}]")
        destination = _strict_path(item["destination"], f"operations[{index}].destination")
        if action == "merge":
            raw_sources = item["sources"]
            if not isinstance(raw_sources, list) or not raw_sources:
                raise MigrationPlanError(f"operations[{index}].sources must be a non-empty array")
            sources = tuple(
                _source_path(value, f"operations[{index}].sources")
                for value in raw_sources
            )
            if len(set(sources)) != len(sources):
                raise MigrationPlanError(f"operations[{index}].sources contains duplicates")
            content = item["content"]
            if not isinstance(content, str):
                raise MigrationPlanError(f"operations[{index}].content must be UTF-8 text")
            try:
                content.encode("utf-8")
            except UnicodeEncodeError as error:
                raise MigrationPlanError(f"operations[{index}].content must be UTF-8 text") from error
            source = None
        else:
            if action not in {"move", "preserve"}:
                raise MigrationPlanError(f"operations[{index}].action must be move, preserve, or merge")
            source = _source_path(item["source"], f"operations[{index}].source")
            sources = (source,)
            content = None
            if (source == destination) != (action == "preserve"):
                raise MigrationPlanError("source=destination is valid only for preserve operations")
        destination_identity = _portable_path_identity(destination)
        for operation_source in sources:
            source_identity = _source_path_identity(operation_source)
            if source_identity in source_identities:
                raise MigrationPlanError(f"duplicate source: {operation_source}")
            source_identities.add(source_identity)
        if destination_identity in destination_identities:
            raise MigrationPlanError(f"duplicate or case-colliding destination: {destination}")
        destination_identities.add(destination_identity)
        operations.append(
            MigrationOperation(
                source,
                destination,
                action,
                sources if action == "merge" else (),
                content,
            )
        )
    _validate_operation_identity_overlaps(operations)

    raw_unresolved = payload["unresolved"]
    if not isinstance(raw_unresolved, list):
        raise MigrationPlanError("unresolved must be a JSON array")
    unresolved: list[dict[str, object]] = []
    for index, item in enumerate(raw_unresolved):
        if not isinstance(item, dict):
            raise MigrationPlanError(f"unresolved[{index}] must be an object")
        _require_exact_keys(item, _UNRESOLVED_KEYS, f"unresolved[{index}]")
        sources = item["sources"]
        if not isinstance(sources, list) or not sources:
            raise MigrationPlanError(f"unresolved[{index}].sources must be a non-empty array")
        validated_sources = [
            _opaque_unresolved_source(value, f"unresolved[{index}].sources")
            for value in sources
        ]
        if len(set(validated_sources)) != len(validated_sources):
            raise MigrationPlanError(f"unresolved[{index}].sources contains duplicates")
        destination = item["destination"]
        if destination is not None:
            destination = _strict_path(destination, f"unresolved[{index}].destination")
        reason = item["reason"]
        if not isinstance(reason, str) or not reason:
            raise MigrationPlanError(f"unresolved[{index}].reason must be a non-empty string")
        unresolved.append(_unresolved(tuple(validated_sources), destination, reason))

    if root is not None:
        assert migration_root is not None
        _require_real_directory(migration_root, "migration root")
        for operation in operations:
            for source in _operation_sources(operation):
                _reject_nested_boundary(migration_root, source)
            _reject_nested_boundary(migration_root, operation.destination)

    return MigrationPlan(
        plan_version=plan_version,
        source_schema=source_schema,
        target_schema=target_schema,
        operations=tuple(operations),
        unresolved=tuple(unresolved),
        plan_hash=stored_hash,
    )


def plan_apply_migration(
    root: Path, plan: MigrationPlan, expected_hash: str
) -> TransactionPlan:
    """Convert one fully validated migration mapping into an undoable transaction."""

    # Plan integrity is deliberately checked before inspecting the filesystem or
    # resolving a single source. A caller cannot use a malformed plan as a path
    # probing primitive, even when it was assembled without load_migration_plan().
    _validate_apply_plan(plan, expected_hash)

    migration_root = Path(root).absolute()
    _require_real_directory(migration_root, "migration root")
    actual_schema = _source_schema(migration_root)
    if actual_schema > TARGET_SCHEMA:
        raise MigrationPlanError(
            f"migration root uses newer source schema {actual_schema}"
        )
    if actual_schema != plan.source_schema:
        raise MigrationPlanError(
            f"migration source schema changed: expected {plan.source_schema}, "
            f"found {actual_schema}"
        )
    for operation in plan.operations:
        for source in _operation_sources(operation):
            _reject_nested_boundary(migration_root, source)
        _reject_nested_boundary(migration_root, operation.destination)

    for operation in plan.operations:
        for source in _operation_sources(operation):
            _require_source_entry(migration_root, source)
    for operation in plan.operations:
        if operation.action == "move":
            _require_absent_destination(migration_root, operation.destination)
        elif operation.action == "merge" and operation.destination not in operation.sources:
            destination = migration_root / PurePosixPath(operation.destination)
            if os.path.lexists(destination) and (
                destination.is_symlink() or not destination.is_file()
            ):
                raise MigrationPlanError(
                    f"migration merge destination is unsafe: {operation.destination}"
                )

    scaffold = render_scaffold(migration_root.name or "Migrated Story", "und")
    project = migration_project(migration_root, scaffold["project.md"])
    _validate_scaffold_destinations(project)
    for operation in plan.operations:
        _reject_portable_tree_collision(migration_root, operation.destination)
    created_directories = tuple(
        relative
        for relative in SCAFFOLD_DIRECTORIES
        if relative not in {".creative-writing", ".creative-writing/transactions"}
        and not os.path.lexists(migration_root / PurePosixPath(relative))
    )

    # Only after every destination, source kind, and project boundary succeeds do
    # we read source bytes. This makes all validation failures mutation-free and
    # prevents a partially readable plan from influencing the transaction.
    primary_by_path: dict[str, Change] = {}
    for operation in plan.operations:
        if operation.action == "preserve":
            continue
        if operation.action == "move":
            assert operation.source is not None
            source = _read_regular_file_no_follow(
                migration_root / PurePosixPath(operation.source),
                f"migration source {operation.source}",
                root=migration_root,
            )
            primary_by_path[operation.source] = Change(operation.source, source, None)
            primary_by_path[operation.destination] = Change(
                operation.destination, None, source
            )
            continue

        assert operation.action == "merge" and operation.content is not None
        before_sources = {
            source: _read_regular_file_no_follow(
                migration_root / PurePosixPath(source),
                f"migration source {source}",
                root=migration_root,
            )
            for source in operation.sources
        }
        destination_before = before_sources.get(operation.destination)
        if destination_before is None:
            destination_path = migration_root / PurePosixPath(operation.destination)
            if os.path.lexists(destination_path):
                destination_before = _read_regular_file_no_follow(
                    destination_path,
                    f"migration destination {operation.destination}",
                    root=migration_root,
                )
        for source, before in before_sources.items():
            if source != operation.destination:
                primary_by_path[source] = Change(source, before, None)
        primary_by_path[operation.destination] = Change(
            operation.destination,
            destination_before,
            operation.content.encode("utf-8"),
        )

    primary = list(primary_by_path.values())

    if "project.md" not in primary_by_path:
        manifest_change = _manifest_upgrade_change(
            migration_root, scaffold["project.md"]
        )
        if manifest_change is not None:
            primary_by_path["project.md"] = manifest_change
            primary = list(primary_by_path.values())

    occupied = {change.path for change in primary}
    for relative_id, after in scaffold.items():
        if relative_id in GENERATED_INDEX_FILES or relative_id in occupied:
            continue
        target = migration_root / PurePosixPath(relative_id)
        if os.path.lexists(target):
            if target.is_symlink() or not target.is_file():
                raise MigrationPlanError(
                    f"canonical scaffold destination is not a real file: {relative_id}"
                )
            continue
        primary.append(Change(relative_id, None, after))
        occupied.add(relative_id)

    derived = plan_reindex(
        project, overlay=tuple(primary), skip_unparseable=True
    ).changes
    changes = tuple(primary) + tuple(derived)
    return TransactionPlan(
        command=("migrate", "apply"),
        changes=changes,
        metadata={
            "plan-hash": plan.plan_hash,
            "source-schema": plan.source_schema,
            "target-schema": plan.target_schema,
            "directory-changes": {"create": created_directories, "remove": ()},
            "undoable": True,
        },
    )


def migration_project(root: Path, manifest: bytes | None = None) -> Project:
    """Return the project boundary used to preview/apply a legacy migration."""

    root = Path(root).absolute()
    if manifest is None:
        manifest_path = root / "project.md"
        if manifest_path.is_file() and not manifest_path.is_symlink():
            source = _read_regular_file_no_follow(
                manifest_path, "project manifest", root=root
            )
            try:
                parsed = parse_document(source)
            except (UnicodeError, ValueError):
                parsed = None
            if parsed is not None and parsed.metadata.get("schema-version") == TARGET_SCHEMA:
                manifest = source
            else:
                manifest = render_scaffold(root.name or "Migrated Story", "und")["project.md"]
        else:
            manifest = render_scaffold(root.name or "Migrated Story", "und")["project.md"]
    return Project(root=root, manifest=parse_document(manifest))


def _manifest_upgrade_change(root: Path, scaffold_manifest: bytes) -> Change | None:
    path = root / "project.md"
    if not os.path.lexists(path):
        return None
    before = _read_regular_file_no_follow(path, "project manifest")
    if _source_schema(root) == TARGET_SCHEMA:
        return None
    template = parse_document(scaffold_manifest)
    legacy = _legacy_manifest_document(before, root.name or "Migrated Story")
    metadata = dict(legacy.metadata)
    metadata["schema-version"] = TARGET_SCHEMA
    metadata.setdefault("title", template.metadata["title"])
    metadata.setdefault("language", template.metadata["language"])
    metadata.setdefault("status", template.metadata["status"])
    after = render_document(
        Document(metadata, legacy.body, legacy.newline, legacy.bom)
    )
    return None if after == before else Change("project.md", before, after)


def _legacy_manifest_document(source: bytes, title: str) -> Document:
    try:
        text = source.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise MigrationPlanError("legacy project.md is not UTF-8") from error
    bom = source.startswith(b"\xef\xbb\xbf")
    newline = _detected_newline(text)
    if text.startswith("---"):
        try:
            return parse_document(source)
        except ValueError as error:
            raise MigrationPlanError(
                "legacy project.md has malformed frontmatter"
            ) from error
    return Document({}, text, newline, bom)


def _detected_newline(text: str) -> str:
    positions = [
        (position, token)
        for token in ("\r\n", "\n", "\r")
        if (position := text.find(token)) >= 0
    ]
    return min(positions)[1] if positions else "\n"


def _validate_apply_plan(plan: MigrationPlan, expected_hash: str) -> None:
    if not isinstance(plan, MigrationPlan):
        raise MigrationPlanError("migration apply requires a loaded migration plan")
    if (
        not isinstance(expected_hash, str)
        or len(expected_hash) != 64
        or any(character not in "0123456789abcdef" for character in expected_hash)
    ):
        raise MigrationPlanError("expected plan hash must be a lowercase SHA-256 digest")
    payload = plan.to_payload()
    _require_exact_keys(payload, _PLAN_KEYS, "migration plan")
    if plan.plan_version != PLAN_VERSION or plan.target_schema != TARGET_SCHEMA:
        raise MigrationPlanError("migration plan schema is unsupported")
    if plan.source_schema < 0 or plan.source_schema > TARGET_SCHEMA:
        raise MigrationPlanError("migration source schema is unsupported")
    recomputed = canonical_plan_hash(payload)
    if recomputed != plan.plan_hash or expected_hash != plan.plan_hash:
        raise MigrationPlanError("migration plan hash mismatch")
    if plan.unresolved:
        raise MigrationPlanError("migration plan contains unresolved entries")
    unresolved = [
        {
            "sources": list(item["sources"]),
            "destination": item["destination"],
            "reason": item["reason"],
        }
        for item in plan.unresolved
    ]
    _validate_generated_plan(list(plan.operations), unresolved)
    for operation in plan.operations:
        for source in _operation_sources(operation):
            _strict_path(source, "transactional migration source")
        kind = allowed_document_kind(operation.destination)
        root_manifest = (
            operation.destination == "project.md"
            and operation.source == "project.md"
            and operation.action == "preserve"
        )
        merge_manifest = operation.action == "merge" and operation.destination == "project.md"
        if merge_manifest:
            assert operation.content is not None
            try:
                merged_manifest = parse_document(operation.content.encode("utf-8"))
            except (UnicodeError, ValueError) as error:
                raise MigrationPlanError(
                    "merged project.md content must be a parseable schema-v1 manifest"
                ) from error
            if merged_manifest.metadata.get("schema-version") != TARGET_SCHEMA:
                raise MigrationPlanError(
                    "merged project.md content must declare schema-version 1"
                )
        if (
            kind is None
            or kind == "generated-index"
            or (kind == "manifest" and not (root_manifest or merge_manifest))
        ):
            raise MigrationPlanError(
                f"migration destination is not a canonical schema-v1 content role: "
                f"{operation.destination}"
            )
        if (
            PurePosixPath(operation.destination).name == "project.md"
            and operation.destination != "project.md"
        ):
            raise MigrationPlanError(
                f"nested project manifest destination is forbidden: {operation.destination}"
            )


def _require_source_entry(root: Path, relative: str) -> None:
    path = root / PurePosixPath(relative)
    if not _secure_dirfd_supported():
        descriptor = _fallback_regular_identity(
            path, f"migration source {relative}", root=root
        )
        os.close(descriptor)
        return
    parent_descriptor = _open_directory_no_follow(path.parent, f"migration source parent {relative}")
    try:
        try:
            entry = os.stat(path.name, dir_fd=parent_descriptor, follow_symlinks=False)
        except OSError as error:
            raise MigrationPlanError(f"migration source is missing: {relative}") from error
        if not stat.S_ISREG(entry.st_mode):
            raise MigrationPlanError(f"migration source must be a real file: {relative}")
    finally:
        os.close(parent_descriptor)


def _require_absent_destination(root: Path, relative: str) -> None:
    path = root / PurePosixPath(relative)
    current = root
    for part in path.relative_to(root).parts[:-1]:
        current /= part
        if os.path.lexists(current) and (current.is_symlink() or not current.is_dir()):
            raise MigrationPlanError(f"migration destination has an unsafe parent: {relative}")
    if os.path.lexists(path):
        raise MigrationPlanError(f"migration destination already exists: {relative}")


def _validate_scaffold_destinations(project: Project) -> None:
    for relative in SCAFFOLD_DIRECTORIES:
        _reject_portable_tree_collision(project.root, relative)
        directory = project.root / PurePosixPath(relative)
        if os.path.lexists(directory) and (directory.is_symlink() or not directory.is_dir()):
            raise MigrationPlanError(
                f"canonical scaffold destination is not a real directory: {relative}"
            )
    for relative in render_scaffold(project.root.name or "Migrated Story", "und"):
        _reject_portable_tree_collision(project.root, relative)
        try:
            target = project.resolve(relative, for_write=True)
        except (OSError, ValueError) as error:
            raise MigrationPlanError(
                f"unsafe canonical scaffold destination {relative}: {error}"
            ) from error
        if os.path.lexists(target) and (target.is_symlink() or not target.is_file()):
            raise MigrationPlanError(
                f"canonical scaffold destination is not a real file: {relative}"
            )


def _reject_portable_tree_collision(root: Path, relative: str) -> None:
    """Reject case/NFC aliases in the existing tree without following links."""

    current = root
    parts = PurePosixPath(relative).parts
    for index, part in enumerate(parts):
        try:
            with os.scandir(current) as scanner:
                entries = tuple(scanner)
        except FileNotFoundError:
            return
        except OSError as error:
            raise MigrationPlanError(
                f"cannot inspect migration destination {relative}"
            ) from error
        identity = _identity_component(part)
        matches = [entry for entry in entries if _identity_component(entry.name) == identity]
        if not matches:
            return
        aliases = [entry.name for entry in matches if entry.name != part]
        if aliases:
            raise MigrationPlanError(
                f"portable destination collides for {relative}: existing {aliases[0]}"
            )
        exact = next(entry for entry in matches if entry.name == part)
        if index < len(parts) - 1 and not exact.is_dir(follow_symlinks=False):
            raise MigrationPlanError(
                f"migration destination has an unsafe parent: {relative}"
            )
        current /= part


def _identity_component(value: str) -> str:
    return unicodedata.normalize("NFC", value).casefold()


def _walk_markdown(root: Path) -> tuple[str, ...]:
    results: list[str] = []

    def visit(directory: Path, prefix: tuple[str, ...]) -> None:
        try:
            with os.scandir(directory) as scanner:
                entries = sorted(scanner, key=lambda entry: _path_sort_key(entry.name))
        except OSError as error:
            raise MigrationPlanError(f"cannot inspect migration source {directory}") from error
        for entry in entries:
            relative_parts = (*prefix, entry.name)
            relative = PurePosixPath(*relative_parts).as_posix()
            try:
                entry_stat = entry.stat(follow_symlinks=False)
            except OSError as error:
                raise MigrationPlanError(f"cannot inspect migration source {relative}") from error
            if stat.S_ISLNK(entry_stat.st_mode):
                continue
            if stat.S_ISDIR(entry_stat.st_mode):
                if _directory_has_manifest(Path(entry.path)):
                    continue
                visit(Path(entry.path), relative_parts)
            elif stat.S_ISREG(entry_stat.st_mode) and entry.name.casefold().endswith(".md"):
                results.append(relative)

    visit(root, ())
    results.sort(key=_path_sort_key)
    return tuple(results)


def _directory_has_manifest(directory: Path) -> bool:
    manifest = directory / "project.md"
    try:
        mode = manifest.lstat().st_mode
    except FileNotFoundError:
        return False
    return stat.S_ISREG(mode)


def _canonical_destination(path: str, *, timeline_count: int) -> str | None:
    parts = _parts(path)
    if _is_canonical(path):
        return path
    if not parts:
        return None

    first = parts[0]
    rest = parts[1:]
    if first == "chapters" and rest:
        return _direct_destination(rest, "story/chapters")
    if first == "drafts" and rest:
        return _direct_destination(rest, "work/drafts")
    if first == "characters" and rest:
        return _direct_destination(rest, "kb/characters")
    if first == "worldbuilding" and rest:
        return _direct_destination(rest, "kb/world")
    if first == "samples" and rest:
        return _direct_destination(rest, "kb/samples")
    if first in {"style", "styles"} and rest:
        return _direct_destination(rest, "kb/styles")
    if first == "plot" and rest:
        if len(rest) == 1 and rest[0] in _CONTINUITY_NAMES:
            return f"kb/continuity/{rest[0]}"
        if len(rest) == 2 and rest[0] == "scenes":
            return f"kb/continuity/scenes/{rest[1]}"
        return _direct_destination(rest, "work/plans")

    if len(parts) == 2 and first == "story":
        return f"story/chapters/{parts[1]}"
    if len(parts) == 3 and parts[:2] == ("work", "outline"):
        return f"work/plans/{parts[2]}"
    if len(parts) == 3 and parts[:2] == ("work", "critique-reports"):
        return f"work/reviews/{parts[2]}"
    if len(parts) == 2 and first == "kb" and parts[1] in _CONTINUITY_NAMES:
        return f"kb/continuity/{parts[1]}"
    if len(parts) == 3 and parts[:2] == ("kb", "scenes"):
        return f"kb/continuity/scenes/{parts[2]}"
    if parts[:2] == ("kb", "timeline") and timeline_count == 1:
        return "kb/continuity/timeline.md"
    return None


def _direct_destination(rest: tuple[str, ...], destination_root: str) -> str | None:
    if len(rest) != 1:
        return None
    return f"{destination_root}/{rest[0]}"


def _is_canonical(path: str) -> bool:
    parts = _parts(path)
    if path == "project.md" or path == "kb/vocab.md":
        return True
    if len(parts) == 3 and "/".join(parts[:2]) in {
        "story/chapters",
        "work/drafts",
        "work/plans",
        "work/reviews",
        "work/brainstorm",
        "work/archive",
        "kb/characters",
        "kb/world",
        "kb/canon",
        "kb/styles",
        "kb/samples",
        "kb/issues",
    }:
        return True
    if len(parts) == 3 and parts[:2] == ("kb", "continuity") and parts[2] in _CONTINUITY_NAMES:
        return True
    return len(parts) == 4 and parts[:3] == ("kb", "continuity", "scenes")


def _is_layout_a(path: str) -> bool:
    parts = _parts(path)
    return bool(parts and parts[0] in _A_ROOTS)


def _is_layout_b(path: str) -> bool:
    parts = _parts(path)
    return (
        (len(parts) == 2 and parts[0] == "story" and parts[1] != "_index.md")
        or (len(parts) >= 3 and parts[:2] in {("work", "outline"), ("work", "critique-reports")})
        or (len(parts) == 2 and parts[0] == "kb" and parts[1] in _CONTINUITY_NAMES)
        or (len(parts) >= 3 and parts[:2] in {("kb", "timeline"), ("kb", "scenes")})
        or (
            len(parts) == 3
            and parts[:2]
            in {
                ("kb", "world"),
                ("kb", "characters"),
                ("kb", "samples"),
                ("kb", "styles"),
                ("work", "drafts"),
            }
            and parts[2] != "_index.md"
        )
    )


def _is_platform_instruction(path: str) -> bool:
    names = ("AG" + "ENTS.md", "CL" + "AUDE.md", "GEM" + "INI.md")
    return path in names or path.casefold() == ".github/copilot-instructions.md"


def _remove_destination_collisions(
    operations: list[MigrationOperation], existing_paths: set[str]
) -> tuple[list[MigrationOperation], list[dict[str, object]]]:
    groups: dict[tuple[str, ...], list[MigrationOperation]] = {}
    for operation in operations:
        groups.setdefault(_portable_path_identity(operation.destination), []).append(operation)

    kept: list[MigrationOperation] = []
    unresolved: list[dict[str, object]] = []
    existing_by_identity = {_portable_path_identity(path): path for path in existing_paths}
    for identity, group in groups.items():
        external_destination = existing_by_identity.get(identity)
        sources = {item.source for item in group}
        if external_destination is not None and external_destination not in sources:
            sources.add(external_destination)
        if len(group) > 1 or len(sources) > 1:
            destination = sorted((item.destination for item in group), key=_path_sort_key)[0]
            unresolved.append(_unresolved(tuple(sorted(sources, key=_path_sort_key)), destination, "destination-collision"))
            preserves = sorted(
                (item for item in group if item.action == "preserve"),
                key=lambda item: _path_sort_key(item.source or ""),
            )
            if preserves:
                kept.append(preserves[0])
        else:
            kept.extend(group)
    return kept, unresolved


def _source_schema(root: Path) -> int:
    manifest = root / "project.md"
    try:
        mode = manifest.lstat().st_mode
    except FileNotFoundError:
        return 0
    if not stat.S_ISREG(mode):
        return 0
    try:
        text = _read_regular_file_no_follow(manifest, "project manifest").decode("utf-8-sig")
    except UnicodeError:
        return 0
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return 0
    for line in lines[1:]:
        if line.strip() == "---":
            break
        key, separator, value = line.partition(":")
        if separator and key.strip() == "schema-version":
            try:
                parsed = int(value.strip())
            except ValueError:
                return 0
            return parsed if parsed >= 0 else 0
    return 0


def _strict_path(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise MigrationPlanError(f"{label} must be a non-empty string")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise MigrationPlanError(f"{label} contains an ASCII control character")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as error:
        raise MigrationPlanError(f"{label} must contain valid Unicode") from error
    if "\\" in value:
        raise MigrationPlanError(f"{label} must use forward slashes")
    posix = PurePosixPath(value)
    windows = PureWindowsPath(value)
    if posix.is_absolute() or windows.is_absolute() or windows.drive or windows.root:
        raise MigrationPlanError(f"{label} must be project-relative")
    if value != posix.as_posix() or any(part in {"", ".", ".."} for part in posix.parts):
        raise MigrationPlanError(f"{label} is not a normalized project-relative path")
    for part in posix.parts:
        if unicodedata.normalize("NFC", part) != part:
            raise MigrationPlanError(f"{label} is not NFC-normalized")
        if part.endswith((".", " ")) or any(character in _WINDOWS_FORBIDDEN_CHARACTERS for character in part):
            raise MigrationPlanError(f"{label} is not portable")
        stem = part.rstrip(". ").split(".", 1)[0].upper()
        if stem in _WINDOWS_RESERVED_NAMES:
            raise MigrationPlanError(f"{label} contains a Windows reserved name")
    return value


def _source_path(value: object, label: str) -> str:
    """Validate an existing lexical identity without imposing new-path portability."""

    if not isinstance(value, str) or not value:
        raise MigrationPlanError(f"{label} must be a non-empty string")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as error:
        raise MigrationPlanError(f"{label} must contain valid Unicode") from error
    if "\\" in value:
        raise MigrationPlanError(f"{label} must use forward slashes")
    posix = PurePosixPath(value)
    windows = PureWindowsPath(value)
    if posix.is_absolute() or windows.is_absolute() or windows.drive or windows.root:
        raise MigrationPlanError(f"{label} must be project-relative")
    if value != posix.as_posix() or any(part in {"", ".", ".."} for part in posix.parts):
        raise MigrationPlanError(f"{label} is not a normalized project-relative path")
    return value


def _opaque_unresolved_source(value: object, label: str) -> str:
    """Validate an opaque identity that can be inspected but never applied."""

    if not isinstance(value, str) or not value:
        raise MigrationPlanError(f"{label} must be a non-empty string")
    if "\x00" in value:
        raise MigrationPlanError(f"{label} contains NUL")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as error:
        raise MigrationPlanError(f"{label} must contain valid Unicode") from error
    if value.startswith("/") or any(
        part in {"", ".", ".."} for part in value.split("/")
    ):
        raise MigrationPlanError(f"{label} is not a contained opaque identity")
    return value


def _portable_destination(value: str) -> str:
    return PurePosixPath(
        *(unicodedata.normalize("NFC", part) for part in PurePosixPath(value).parts)
    ).as_posix()


def _reject_nested_boundary(root: Path, relative: str) -> None:
    if not _secure_dirfd_supported():
        current = root
        for part in PurePosixPath(relative).parts[:-1]:
            current /= part
            if not os.path.lexists(current):
                return
            info = current.lstat()
            if (
                _is_reparse_point(info)
                or stat.S_ISLNK(info.st_mode)
                or not stat.S_ISDIR(info.st_mode)
            ):
                raise MigrationPlanError(f"operation crosses unsafe boundary: {relative}")
            manifest = current / "project.md"
            if os.path.lexists(manifest) and stat.S_ISREG(manifest.lstat().st_mode):
                raise MigrationPlanError(f"operation crosses nested project boundary: {relative}")
        return
    descriptor = _open_directory_no_follow(root, "migration root")
    try:
        for part in PurePosixPath(relative).parts[:-1]:
            try:
                entry = os.stat(part, dir_fd=descriptor, follow_symlinks=False)
            except FileNotFoundError:
                return
            except (NotImplementedError, TypeError) as error:
                raise MigrationPlanError("safe nested-project inspection is unsupported") from error
            except OSError as error:
                raise MigrationPlanError(f"cannot inspect operation parent for {relative}") from error
            if stat.S_ISLNK(entry.st_mode):
                raise MigrationPlanError(f"operation crosses symlink boundary: {relative}")
            if not stat.S_ISDIR(entry.st_mode):
                raise MigrationPlanError(f"operation parent is not a directory: {relative}")

            child_descriptor = _open_child_directory(descriptor, part, f"operation parent for {relative}")
            os.close(descriptor)
            descriptor = child_descriptor

            try:
                manifest = os.stat("project.md", dir_fd=descriptor, follow_symlinks=False)
            except FileNotFoundError:
                continue
            except (NotImplementedError, TypeError) as error:
                raise MigrationPlanError("safe nested-project inspection is unsupported") from error
            except OSError as error:
                raise MigrationPlanError(f"cannot inspect nested project for {relative}") from error
            if stat.S_ISREG(manifest.st_mode):
                raise MigrationPlanError(f"operation crosses nested project boundary: {relative}")
    finally:
        os.close(descriptor)


def _validate_generated_plan(
    operations: list[MigrationOperation], unresolved: list[dict[str, object]]
) -> None:
    source_identities: set[tuple[str, ...]] = set()
    destination_identities: set[tuple[str, ...]] = set()
    for index, operation in enumerate(operations):
        destination = _strict_path(operation.destination, f"operations[{index}].destination")
        if operation.action == "merge":
            if operation.source is not None or not operation.sources or not isinstance(operation.content, str):
                raise MigrationPlanError(f"operations[{index}] has an invalid merge shape")
            sources = tuple(
                _source_path(value, f"operations[{index}].sources")
                for value in operation.sources
            )
            try:
                operation.content.encode("utf-8")
            except UnicodeEncodeError as error:
                raise MigrationPlanError(f"operations[{index}].content must be UTF-8 text") from error
        else:
            if operation.action not in {"move", "preserve"} or operation.source is None:
                raise MigrationPlanError(f"operations[{index}].action must be move, preserve, or merge")
            source = _source_path(operation.source, f"operations[{index}].source")
            sources = (source,)
            if operation.sources not in {(), (source,)} or operation.content is not None:
                raise MigrationPlanError(f"operations[{index}] has invalid fields")
            if (source == destination) != (operation.action == "preserve"):
                raise MigrationPlanError("source=destination is valid only for preserve operations")
        destination_identity = _portable_path_identity(destination)
        for source in sources:
            source_identity = _source_path_identity(source)
            if source_identity in source_identities:
                raise MigrationPlanError(f"duplicate source: {source}")
            source_identities.add(source_identity)
        if destination_identity in destination_identities:
            raise MigrationPlanError(f"duplicate or case-colliding destination: {destination}")
        destination_identities.add(destination_identity)

    for index, item in enumerate(unresolved):
        _require_exact_keys(item, _UNRESOLVED_KEYS, f"unresolved[{index}]")
        sources = item["sources"]
        if not isinstance(sources, list) or not sources:
            raise MigrationPlanError(f"unresolved[{index}].sources must be a non-empty array")
        validated_sources = [
            _opaque_unresolved_source(value, f"unresolved[{index}].sources")
            for value in sources
        ]
        if len(set(validated_sources)) != len(validated_sources):
            raise MigrationPlanError(f"unresolved[{index}].sources contains duplicates")
        destination = item["destination"]
        if destination is not None:
            _strict_path(destination, f"unresolved[{index}].destination")
        reason = item["reason"]
        if not isinstance(reason, str) or not reason:
            raise MigrationPlanError(f"unresolved[{index}].reason must be a non-empty string")
    _validate_operation_identity_overlaps(operations)


def _validate_operation_identity_overlaps(
    operations: list[MigrationOperation],
) -> None:
    source_owners: dict[tuple[str, ...], set[int]] = {}
    for index, operation in enumerate(operations):
        for source in _operation_sources(operation):
            source_owners.setdefault(_portable_path_identity(source), set()).add(index)
    for index, operation in enumerate(operations):
        owners = source_owners.get(
            _portable_path_identity(operation.destination), set()
        )
        if not owners:
            continue
        same_operation_allowed = owners == {index} and operation.action in {
            "merge",
            "preserve",
        }
        if not same_operation_allowed:
            raise MigrationPlanError(
                "migration source and destination identities overlap across operations: "
                f"{operation.destination}"
            )


def _strict_integer(value: object, label: str, *, minimum: int = 1) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise MigrationPlanError(f"{label} must be a non-boolean integer >= {minimum}")
    return value


def _require_exact_keys(value: Mapping[str, object], expected: frozenset[str], label: str) -> None:
    actual = frozenset(value)
    if actual != expected:
        missing = sorted(expected - actual)
        unknown = sorted(actual - expected)
        raise MigrationPlanError(f"{label} keys are invalid; missing={missing}, unknown={unknown}")


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise MigrationPlanError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _require_real_directory(path: Path, label: str) -> None:
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError as error:
        raise MigrationPlanError(f"{label} does not exist: {path}") from error
    if not stat.S_ISDIR(mode):
        raise MigrationPlanError(f"{label} must be a real directory: {path}")


def _read_regular_file_no_follow(
    path: Path, label: str, *, root: Path | None = None
) -> bytes:
    if not _secure_dirfd_supported():
        descriptor = _fallback_regular_identity(path, label, root=root)
        try:
            opened_identity = _stat_identity(os.fstat(descriptor))
            with os.fdopen(descriptor, "rb") as stream:
                descriptor = -1
                data = stream.read()
            revalidated = _fallback_regular_identity(path, label, root=root)
            try:
                if _stat_identity(os.fstat(revalidated)) != opened_identity:
                    raise MigrationPlanError(f"{label} changed while it was read")
            finally:
                os.close(revalidated)
            return data
        finally:
            if descriptor >= 0:
                os.close(descriptor)
    parent_descriptor = _open_directory_no_follow(path.parent, f"{label} parent")
    try:
        try:
            entry = os.stat(path.name, dir_fd=parent_descriptor, follow_symlinks=False)
        except (NotImplementedError, TypeError) as error:
            raise MigrationPlanError("safe file loading is unsupported") from error
        except OSError as error:
            raise MigrationPlanError(f"{label} must be a real file without links: {path}") from error
        if not stat.S_ISREG(entry.st_mode):
            raise MigrationPlanError(f"{label} must be a real file without links: {path}")

        try:
            descriptor = os.open(
                path.name,
                os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0),
                dir_fd=parent_descriptor,
            )
        except (NotImplementedError, TypeError) as error:
            raise MigrationPlanError("safe file loading is unsupported") from error
        except OSError as error:
            raise MigrationPlanError(f"{label} must be a real file without links: {path}") from error
        try:
            if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                raise MigrationPlanError(f"{label} must be a real file without links: {path}")
            with os.fdopen(descriptor, "rb") as stream:
                descriptor = -1
                return stream.read()
        finally:
            if descriptor >= 0:
                os.close(descriptor)
    finally:
        os.close(parent_descriptor)


def _open_directory_no_follow(path: Path, label: str) -> int:
    _require_secure_dirfd_support()
    absolute = Path(os.path.abspath(path))
    anchor = Path(absolute.anchor)
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
    try:
        descriptor = os.open(anchor, flags)
    except OSError as error:
        raise MigrationPlanError(f"{label} has an unsafe filesystem boundary: {path}") from error
    try:
        if not stat.S_ISDIR(os.fstat(descriptor).st_mode):
            raise MigrationPlanError(f"{label} must be a real directory without links: {path}")
        for component in absolute.relative_to(anchor).parts:
            child_descriptor = _open_child_directory(descriptor, component, label)
            os.close(descriptor)
            descriptor = child_descriptor
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _open_child_directory(parent_descriptor: int, name: str, label: str) -> int:
    try:
        entry = os.stat(name, dir_fd=parent_descriptor, follow_symlinks=False)
    except (NotImplementedError, TypeError) as error:
        raise MigrationPlanError("safe directory traversal is unsupported") from error
    except OSError as error:
        raise MigrationPlanError(f"{label} has an unsafe or missing directory component") from error
    if not stat.S_ISDIR(entry.st_mode):
        raise MigrationPlanError(f"{label} has a directory link or non-directory component")
    try:
        descriptor = os.open(
            name,
            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0),
            dir_fd=parent_descriptor,
        )
    except (NotImplementedError, TypeError) as error:
        raise MigrationPlanError("safe directory traversal is unsupported") from error
    except OSError as error:
        raise MigrationPlanError(f"{label} has an unsafe or missing directory component") from error
    if not stat.S_ISDIR(os.fstat(descriptor).st_mode):
        os.close(descriptor)
        raise MigrationPlanError(f"{label} must contain only real directories")
    return descriptor


def _require_secure_dirfd_support() -> None:
    if not _secure_dirfd_supported():
        raise MigrationPlanError("safe no-follow file loading is unsupported on this platform")


def _secure_dirfd_supported() -> bool:
    return bool(
        getattr(os, "O_NOFOLLOW", 0)
        and getattr(os, "O_DIRECTORY", 0)
        and os.open in os.supports_dir_fd
        and os.stat in os.supports_dir_fd
        and os.stat in os.supports_follow_symlinks
    )


def _fallback_regular_identity(
    path: Path, label: str, *, root: Path | None = None
) -> int:
    """Windows-safe path walk plus open/fstat/revalidation identity checks."""

    absolute = Path(os.path.abspath(path))
    if root is not None:
        _require_contained(Path(root).absolute(), absolute, label)
    anchor = Path(absolute.anchor)
    ancestors: list[tuple[Path, tuple[int, int, int, bool]]] = []
    current = anchor
    for component in absolute.relative_to(anchor).parts[:-1]:
        current /= component
        try:
            info = current.lstat()
        except OSError as error:
            raise MigrationPlanError(f"{label} has a missing ancestor") from error
        if (
            _is_reparse_point(info)
            or stat.S_ISLNK(info.st_mode)
            or not stat.S_ISDIR(info.st_mode)
        ):
            raise MigrationPlanError(f"{label} has an unsafe ancestor")
        ancestors.append((current, _stat_identity(info)))
    try:
        before = absolute.lstat()
    except OSError as error:
        raise MigrationPlanError(f"{label} must be a real file without links: {path}") from error
    if (
        _is_reparse_point(before)
        or stat.S_ISLNK(before.st_mode)
        or not stat.S_ISREG(before.st_mode)
    ):
        raise MigrationPlanError(f"{label} must be a real file without links: {path}")
    try:
        descriptor = os.open(absolute, os.O_RDONLY | getattr(os, "O_CLOEXEC", 0))
    except OSError as error:
        raise MigrationPlanError(f"{label} could not be opened safely: {path}") from error
    try:
        opened = os.fstat(descriptor)
        after = absolute.lstat()
        if (
            _is_reparse_point(opened)
            or _is_reparse_point(after)
            or _stat_identity(before) != _stat_identity(opened)
            or _stat_identity(after) != _stat_identity(opened)
        ):
            raise MigrationPlanError(f"{label} changed while it was opened")
        for ancestor, identity in ancestors:
            if _stat_identity(ancestor.lstat()) != identity:
                raise MigrationPlanError(f"{label} ancestor changed while it was opened")
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _is_reparse_point(info: os.stat_result) -> bool:
    attributes = getattr(info, "st_file_attributes", 0)
    mask = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(attributes & mask)


def _stat_identity(info: os.stat_result) -> tuple[int, int, int, bool]:
    return (info.st_dev, info.st_ino, stat.S_IFMT(info.st_mode), _is_reparse_point(info))


def _require_contained(root: Path, path: Path, label: str) -> None:
    try:
        path.relative_to(root)
    except ValueError as error:
        raise MigrationPlanError(f"{label} is outside the migration root") from error


def _unresolved(sources: tuple[str, ...], destination: str | None, reason: str) -> dict[str, object]:
    return {"sources": list(sources), "destination": destination, "reason": reason}


def _unresolved_sort_key(item: Mapping[str, object]) -> tuple[object, ...]:
    destination = item["destination"]
    return (
        str(item["reason"]),
        "" if destination is None else str(destination).casefold(),
        tuple(str(value).casefold() for value in item["sources"]),
    )


def _path_sort_key(path: str) -> tuple[str, str]:
    return (unicodedata.normalize("NFC", path).casefold(), path)


def _portable_path_identity(path: str) -> tuple[str, ...]:
    return tuple(unicodedata.normalize("NFC", part).casefold() for part in PurePosixPath(path).parts)


def _source_path_identity(path: str) -> tuple[str, ...]:
    return PurePosixPath(path).parts


def _operation_sources(operation: MigrationOperation) -> tuple[str, ...]:
    if operation.action == "merge":
        return operation.sources
    assert operation.source is not None
    return (operation.source,)


def _parts(path: str) -> tuple[str, ...]:
    return PurePosixPath(path).parts


def _basename(path: str) -> str:
    return PurePosixPath(path).name.casefold()


__all__ = [
    "MigrationOperation",
    "MigrationPlan",
    "MigrationPlanError",
    "canonical_plan_hash",
    "load_migration_plan",
    "migration_project",
    "plan_apply_migration",
    "plan_migration",
]

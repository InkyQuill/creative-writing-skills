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


PLAN_VERSION = 1
TARGET_SCHEMA = 1
_PLAN_KEYS = frozenset(
    {"plan-version", "source-schema", "target-schema", "operations", "unresolved", "plan-hash"}
)
_OPERATION_KEYS = frozenset({"source", "destination", "action"})
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

    source: str
    destination: str
    action: str


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
            "operations": [
                {
                    "source": operation.source,
                    "destination": operation.destination,
                    "action": operation.action,
                }
                for operation in self.operations
            ],
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
    for path in paths:
        _strict_path(path, "discovered migration path")
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
            _strict_path(path, "migration source")
            _strict_path(destination, "migration destination")
        except MigrationPlanError as error:
            raise MigrationPlanError(f"cannot represent migration operation for {path}: {error}") from error
        action = "preserve" if path == destination else "move"
        operations.append(MigrationOperation(path, destination, action))

    operations, collision_records = _remove_destination_collisions(operations, path_set)
    unresolved.extend(collision_records)
    operations.sort(key=lambda item: (_path_sort_key(item.destination), _path_sort_key(item.source), item.action))
    unresolved.sort(key=_unresolved_sort_key)
    _validate_generated_plan(operations, unresolved)

    payload: dict[str, object] = {
        "plan-version": PLAN_VERSION,
        "source-schema": source_schema,
        "target-schema": TARGET_SCHEMA,
        "operations": [
            {"source": item.source, "destination": item.destination, "action": item.action}
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
        _require_exact_keys(item, _OPERATION_KEYS, f"operations[{index}]")
        source = _strict_path(item["source"], f"operations[{index}].source")
        destination = _strict_path(item["destination"], f"operations[{index}].destination")
        action = item["action"]
        if action not in {"move", "preserve"}:
            raise MigrationPlanError(f"operations[{index}].action must be move or preserve")
        if (source == destination) != (action == "preserve"):
            raise MigrationPlanError("source=destination is valid only for preserve operations")
        source_identity = _portable_path_identity(source)
        destination_identity = _portable_path_identity(destination)
        if source_identity in source_identities:
            raise MigrationPlanError(f"duplicate or case-colliding source: {source}")
        if destination_identity in destination_identities:
            raise MigrationPlanError(f"duplicate or case-colliding destination: {destination}")
        source_identities.add(source_identity)
        destination_identities.add(destination_identity)
        operations.append(MigrationOperation(source, destination, action))

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
        validated_sources = [_strict_path(value, f"unresolved[{index}].sources") for value in sources]
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
        migration_root = Path(root).absolute()
        _require_real_directory(migration_root, "migration root")
        for operation in operations:
            _reject_nested_boundary(migration_root, operation.source)
            _reject_nested_boundary(migration_root, operation.destination)

    return MigrationPlan(
        plan_version=plan_version,
        source_schema=source_schema,
        target_schema=target_schema,
        operations=tuple(operations),
        unresolved=tuple(unresolved),
        plan_hash=stored_hash,
    )


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
                key=lambda item: _path_sort_key(item.source),
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


def _reject_nested_boundary(root: Path, relative: str) -> None:
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
        source = _strict_path(operation.source, f"operations[{index}].source")
        destination = _strict_path(operation.destination, f"operations[{index}].destination")
        if operation.action not in {"move", "preserve"}:
            raise MigrationPlanError(f"operations[{index}].action must be move or preserve")
        if (source == destination) != (operation.action == "preserve"):
            raise MigrationPlanError("source=destination is valid only for preserve operations")
        source_identity = _portable_path_identity(source)
        destination_identity = _portable_path_identity(destination)
        if source_identity in source_identities:
            raise MigrationPlanError(f"duplicate or case-colliding source: {source}")
        if destination_identity in destination_identities:
            raise MigrationPlanError(f"duplicate or case-colliding destination: {destination}")
        source_identities.add(source_identity)
        destination_identities.add(destination_identity)

    for index, item in enumerate(unresolved):
        _require_exact_keys(item, _UNRESOLVED_KEYS, f"unresolved[{index}]")
        sources = item["sources"]
        if not isinstance(sources, list) or not sources:
            raise MigrationPlanError(f"unresolved[{index}].sources must be a non-empty array")
        validated_sources = [_strict_path(value, f"unresolved[{index}].sources") for value in sources]
        if len(set(validated_sources)) != len(validated_sources):
            raise MigrationPlanError(f"unresolved[{index}].sources contains duplicates")
        destination = item["destination"]
        if destination is not None:
            _strict_path(destination, f"unresolved[{index}].destination")
        reason = item["reason"]
        if not isinstance(reason, str) or not reason:
            raise MigrationPlanError(f"unresolved[{index}].reason must be a non-empty string")


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


def _read_regular_file_no_follow(path: Path, label: str) -> bytes:
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
    if (
        not getattr(os, "O_NOFOLLOW", 0)
        or not getattr(os, "O_DIRECTORY", 0)
        or os.open not in os.supports_dir_fd
        or os.stat not in os.supports_dir_fd
        or os.stat not in os.supports_follow_symlinks
    ):
        raise MigrationPlanError("safe no-follow file loading is unsupported on this platform")


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
    "plan_migration",
]

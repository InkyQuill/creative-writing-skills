"""Persistent plans and content-addressed snapshots for story-file transactions."""

from __future__ import annotations

import difflib
import hashlib
import json
import os
import shutil
import tempfile
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath, PureWindowsPath
from types import MappingProxyType

from .documents import logical_hash
from .project import Project


class TransactionError(RuntimeError):
    """Raised when a guarded transaction cannot be completed safely."""


@dataclass(frozen=True)
class Change:
    """One exact-byte replacement planned for a project-relative file."""

    path: str
    before: bytes | None
    after: bytes | None

    def __post_init__(self) -> None:
        _validate_change_path(self.path)


@dataclass(frozen=True)
class TransactionPlan:
    """The complete immutable input to a transaction."""

    command: tuple[str, ...]
    changes: tuple[Change, ...]
    metadata: Mapping[str, object]

    def __post_init__(self) -> None:
        object.__setattr__(self, "command", tuple(self.command))
        object.__setattr__(self, "changes", tuple(self.changes))
        object.__setattr__(self, "metadata", _freeze_metadata(self.metadata))


@dataclass(frozen=True)
class TransactionRecord:
    """An execution-state snapshot of a persisted transaction."""

    id: str
    state: str
    completed: tuple[str, ...]


class TransactionStore:
    """Persist transaction plans beneath a project's protected journal directory."""

    def __init__(self, project: Project):
        self.project = project
        self.root = project.root / ".creative-writing" / "transactions"

    def prepare(self, plan: TransactionPlan, *, transaction_id: str | None = None) -> TransactionRecord:
        """Snapshot ``plan`` and return its newly prepared transaction record."""

        identifier = transaction_id or uuid.uuid4().hex
        transaction_dir = self._transaction_dir(identifier)
        if transaction_dir.exists():
            raise FileExistsError(f"transaction already exists: {identifier}")

        manifest = {
            "changes": [self._manifest_change(change) for change in plan.changes],
            "command": list(plan.command),
            "completed": [],
            "metadata": _jsonable(plan.metadata),
            "state": "prepared",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        rendered_manifest = _render_json(manifest)

        transaction_dir.parent.mkdir(parents=True, exist_ok=True)
        try:
            transaction_dir.mkdir()
        except FileExistsError as error:
            raise FileExistsError(f"transaction already exists: {identifier}") from error

        try:
            self._write_json(transaction_dir / "manifest.json", rendered_manifest)
        except BaseException:
            shutil.rmtree(transaction_dir)
            raise
        return TransactionRecord(identifier, "prepared", ())

    def load(self, transaction_id: str) -> TransactionRecord:
        """Load a transaction's state without reading its blob contents."""

        manifest = self._read_manifest(transaction_id)
        return TransactionRecord(
            id=transaction_id,
            state=manifest["state"],
            completed=tuple(manifest["completed"]),
        )

    def write_state(
        self, transaction_id: str, state: str, *, completed: tuple[str, ...] = ()
    ) -> TransactionRecord:
        """Atomically replace just the execution state in an existing manifest."""

        manifest_path = self._transaction_dir(transaction_id) / "manifest.json"
        manifest = self._read_manifest(transaction_id)
        manifest["state"] = state
        manifest["completed"] = list(completed)
        self._write_json(manifest_path, _render_json(manifest))
        return TransactionRecord(transaction_id, state, tuple(completed))

    def blob(self, data: bytes) -> str:
        """Persist ``data`` once and return its SHA-256 content identifier."""

        if not isinstance(data, bytes):
            raise TypeError("blob data must be bytes")

        identifier = hashlib.sha256(data).hexdigest()
        blobs = self.root / "blobs"
        blobs.mkdir(parents=True, exist_ok=True)
        destination = blobs / identifier
        if destination.exists():
            return identifier

        self._write_bytes(destination, data)
        return identifier

    def _manifest_change(self, change: Change) -> dict[str, object]:
        return {
            "after": self._content_reference(change.after),
            "before": self._content_reference(change.before),
            "diff": _unified_diff(change.path, change.before, change.after),
            "path": change.path,
        }

    def _content_reference(self, data: bytes | None) -> dict[str, str | None]:
        if data is None:
            return {"blob": None, "byte_hash": None, "logical_hash": None}

        identifier = self.blob(data)
        return {
            "blob": identifier,
            "byte_hash": identifier,
            "logical_hash": logical_hash(data),
        }

    def _read_manifest(self, transaction_id: str) -> dict[str, object]:
        manifest_path = self._transaction_dir(transaction_id) / "manifest.json"
        with manifest_path.open(encoding="utf-8") as stream:
            return json.load(stream)

    def _transaction_dir(self, transaction_id: str) -> Path:
        if not isinstance(transaction_id, str) or not transaction_id:
            raise ValueError("transaction id must be a non-empty string")
        candidate = Path(transaction_id)
        if candidate.name != transaction_id or transaction_id in {".", ".."}:
            raise ValueError("transaction id must be a single path component")
        return self.root / transaction_id

    @staticmethod
    def _write_json(destination: Path, rendered: str) -> None:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=destination.parent,
            prefix=f".{destination.name}.",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temporary = Path(stream.name)
            try:
                stream.write(rendered)
                stream.flush()
                os.fsync(stream.fileno())
                os.replace(temporary, destination)
            except BaseException:
                temporary.unlink(missing_ok=True)
                raise

    @staticmethod
    def _write_bytes(destination: Path, data: bytes) -> None:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=destination.parent,
            prefix=f".{destination.name}.",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temporary = Path(stream.name)
            try:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
                os.replace(temporary, destination)
            except BaseException:
                temporary.unlink(missing_ok=True)
                raise


class TransactionEngine:
    """Guard, stage, apply, and recover multi-file project transactions."""

    def __init__(self, project: Project):
        self.project = project
        self.store = TransactionStore(project)
        self.replace_hook = os.replace
        self.unlink_hook = os.unlink

    def preview(self, plan: TransactionPlan) -> dict[str, object]:
        """Validate ``plan`` against the project and return its read-only preview."""

        self._validate_plan(plan)
        return {
            "changes": [
                {
                    "action": _change_action(change),
                    "diff": _unified_diff(change.path, change.before, change.after),
                    "path": change.path,
                }
                for change in plan.changes
            ],
            "command": list(plan.command),
            "metadata": _jsonable(plan.metadata),
        }

    def apply(
        self, plan: TransactionPlan, *, transaction_id: str | None = None
    ) -> TransactionRecord:
        """Apply ``plan`` only while every exact before-snapshot still matches."""

        self._validate_plan(plan)
        prepared = self.store.prepare(plan, transaction_id=transaction_id)
        completed: list[str] = []

        try:
            for change in plan.changes:
                if change.after is not None:
                    self._write_staged_bytes(prepared.id, change.path, change.after)

            # Staging may take time. Re-resolve and re-read every target before
            # allowing the first externally visible replacement.
            self._validate_plan(plan)
            self.store.write_state(prepared.id, "applying")

            for change in plan.changes:
                self._install_change(prepared.id, change)
                completed.append(change.path)
                self.store.write_state(
                    prepared.id, "applying", completed=tuple(completed)
                )

            return self.store.write_state(
                prepared.id, "committed", completed=tuple(completed)
            )
        except BaseException as error:
            rollback_errors = self._restore_completed(
                prepared.id, plan.changes, tuple(completed)
            )
            rollback_errors.extend(self._cleanup_temporaries(prepared.id, plan.changes))
            try:
                self.store.write_state(
                    prepared.id, "rolled-back", completed=tuple(completed)
                )
            except BaseException as state_error:
                rollback_errors.append(
                    f"could not record rolled-back state: {_error_text(state_error)}"
                )

            if rollback_errors:
                details = "; ".join(rollback_errors)
                raise TransactionError(
                    f"transaction {prepared.id} failed: {_error_text(error)}; "
                    f"rollback failed: {details}"
                ) from error
            raise TransactionError(
                f"transaction {prepared.id} failed: {_error_text(error)}; rolled back"
            ) from error

    def recover(self, transaction_id: str) -> TransactionRecord:
        """Restore an interrupted transaction from before-blobs; never roll forward."""

        record = self.store.load(transaction_id)
        if record.state not in {"prepared", "applying"}:
            raise TransactionError(
                f"cannot recover transaction {transaction_id} in state {record.state}"
            )

        changes = self._persisted_changes(transaction_id)
        by_path = {change.path: change for change in changes}
        if len(by_path) != len(changes):
            raise TransactionError(f"transaction {transaction_id} contains duplicate paths")
        if len(set(record.completed)) != len(record.completed) or any(
            path not in by_path for path in record.completed
        ):
            raise TransactionError(
                f"transaction {transaction_id} has invalid completed paths"
            )

        # Resolve the complete persisted target set before touching any file.
        self._resolve_changes(changes)
        recovery_errors: list[str] = []
        for path in reversed(record.completed):
            change = by_path[path]
            try:
                self._remove_temporary(transaction_id, change.path)
                self._restore_change(transaction_id, change)
            except BaseException as error:
                recovery_errors.append(f"{path}: {_error_text(error)}")

        recovery_errors.extend(self._cleanup_temporaries(transaction_id, changes))
        if recovery_errors:
            raise TransactionError(
                f"recovery of transaction {transaction_id} failed: "
                + "; ".join(recovery_errors)
            )
        return self.store.write_state(
            transaction_id, "rolled-back", completed=record.completed
        )

    def _validate_plan(self, plan: TransactionPlan) -> None:
        changes = self._resolve_changes(plan.changes)
        for change, target in changes:
            self._validate_target(change, target)

    def _resolve_changes(self, changes: tuple[Change, ...]) -> tuple[tuple[Change, Path], ...]:
        seen: set[str] = set()
        resolved: list[tuple[Change, Path]] = []
        for change in changes:
            if change.path in seen:
                raise TransactionError(f"duplicate transaction target: {change.path}")
            seen.add(change.path)
            try:
                target = self.project.resolve(change.path, for_write=True)
            except (OSError, ValueError) as error:
                raise TransactionError(
                    f"unsafe transaction target {change.path}: {_error_text(error)}"
                ) from error
            resolved.append((change, target))
        return tuple(resolved)

    def _validate_target(self, change: Change, target: Path) -> None:
        try:
            if not target.exists():
                actual = None
            elif not target.is_file():
                raise TransactionError(
                    f"stale precondition for {change.path}: target is not a regular file"
                )
            else:
                actual = target.read_bytes()
        except TransactionError:
            raise
        except OSError as error:
            raise TransactionError(
                f"could not read transaction target {change.path}: {_error_text(error)}"
            ) from error

        if actual != change.before:
            raise TransactionError(f"stale precondition for {change.path}")

    def _install_change(self, transaction_id: str, change: Change) -> None:
        target = self.project.resolve(change.path, for_write=True)
        if change.after is None:
            if change.before is not None:
                self.unlink_hook(target)
            return
        self.replace_hook(self._temporary_path(transaction_id, change.path), target)

    def _restore_completed(
        self,
        transaction_id: str,
        changes: tuple[Change, ...],
        completed: tuple[str, ...],
    ) -> list[str]:
        by_path = {change.path: change for change in changes}
        errors: list[str] = []
        for path in reversed(completed):
            try:
                self._remove_temporary(transaction_id, path)
                self._restore_change(transaction_id, by_path[path])
            except BaseException as error:
                errors.append(f"{path}: {_error_text(error)}")
        return errors

    def _restore_change(self, transaction_id: str, change: Change) -> None:
        target = self.project.resolve(change.path, for_write=True)
        if change.before is None:
            if target.exists():
                self.unlink_hook(target)
            return
        self._write_staged_bytes(transaction_id, change.path, change.before)
        self.replace_hook(self._temporary_path(transaction_id, change.path), target)

    def _cleanup_temporaries(
        self, transaction_id: str, changes: tuple[Change, ...]
    ) -> list[str]:
        errors: list[str] = []
        for change in changes:
            try:
                self._remove_temporary(transaction_id, change.path)
            except BaseException as error:
                errors.append(
                    f"could not clean temporary sibling for {change.path}: {_error_text(error)}"
                )
        return errors

    def _remove_temporary(self, transaction_id: str, path: str) -> None:
        self._temporary_path(transaction_id, path).unlink(missing_ok=True)

    def _write_staged_bytes(self, transaction_id: str, path: str, data: bytes) -> Path:
        destination = self._temporary_path(transaction_id, path)
        descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                descriptor = -1
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
        except BaseException:
            if descriptor >= 0:
                os.close(descriptor)
            destination.unlink(missing_ok=True)
            raise
        return destination

    def _temporary_path(self, transaction_id: str, path: str) -> Path:
        self.store._transaction_dir(transaction_id)
        target = self.project.resolve(path, for_write=True)
        identity = hashlib.sha256(f"{transaction_id}\0{path}".encode("utf-8")).hexdigest()
        return target.parent / f".cw-transaction-{identity}.tmp"

    def _persisted_changes(self, transaction_id: str) -> tuple[Change, ...]:
        manifest = self.store._read_manifest(transaction_id)
        rendered_changes = manifest.get("changes")
        if not isinstance(rendered_changes, list):
            raise TransactionError(f"transaction {transaction_id} has invalid changes")

        changes: list[Change] = []
        try:
            for rendered in rendered_changes:
                if not isinstance(rendered, dict):
                    raise TypeError("change must be an object")
                path = rendered["path"]
                if not isinstance(path, str):
                    raise TypeError("change path must be a string")
                before = self._read_blob_reference(rendered["before"])
                after = self._read_blob_reference(rendered["after"])
                changes.append(Change(path, before, after))
        except (KeyError, OSError, TypeError, ValueError) as error:
            raise TransactionError(
                f"transaction {transaction_id} has invalid snapshots: {_error_text(error)}"
            ) from error
        return tuple(changes)

    def _read_blob_reference(self, reference: object) -> bytes | None:
        if not isinstance(reference, dict):
            raise TypeError("content reference must be an object")
        identifier = reference.get("blob")
        if identifier is None:
            return None
        if (
            not isinstance(identifier, str)
            or len(identifier) != 64
            or any(character not in "0123456789abcdef" for character in identifier)
        ):
            raise ValueError("blob identifier must be a lowercase SHA-256 digest")
        data = (self.store.root / "blobs" / identifier).read_bytes()
        if hashlib.sha256(data).hexdigest() != identifier:
            raise ValueError(f"blob content does not match identifier {identifier}")
        return data


def _unified_diff(path: str, before: bytes | None, after: bytes | None) -> str:
    """Render an exact textual review diff for a planned byte replacement."""

    before_text = "" if before is None else before.decode("utf-8")
    after_text = "" if after is None else after.decode("utf-8")
    return "".join(
        difflib.unified_diff(
            before_text.splitlines(keepends=True),
            after_text.splitlines(keepends=True),
            fromfile=path,
            tofile=path,
        )
    )


def _freeze_metadata(metadata: Mapping[str, object]) -> Mapping[str, object]:
    if not isinstance(metadata, Mapping):
        raise TypeError("transaction metadata must be a mapping")
    return MappingProxyType({key: _freeze_jsonlike(value) for key, value in metadata.items()})


def _freeze_jsonlike(value: object) -> object:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze_jsonlike(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_jsonlike(item) for item in value)
    if isinstance(value, (set, frozenset)):
        return frozenset(_freeze_jsonlike(item) for item in value)
    return value


def _jsonable(value: object) -> object:
    if isinstance(value, Mapping):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    return value


def _render_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _validate_change_path(path: str) -> None:
    if not isinstance(path, str) or not path:
        raise ValueError("change path must be a non-empty project-relative POSIX path")
    if "\\" in path:
        raise ValueError("change path must use forward slashes")

    posix = PurePosixPath(path)
    windows = PureWindowsPath(path)
    if posix.is_absolute() or windows.is_absolute() or windows.drive or windows.root:
        raise ValueError("change path must be project-relative")

    segments = path.split("/")
    if any(segment in {"", ".", ".."} for segment in segments):
        raise ValueError("change path must be a normalized project-relative identity")


def _change_action(change: Change) -> str:
    if change.before is None and change.after is not None:
        return "create"
    if change.before is not None and change.after is None:
        return "delete"
    return "update"


def _error_text(error: BaseException) -> str:
    return str(error) or type(error).__name__


__all__ = [
    "Change",
    "TransactionEngine",
    "TransactionError",
    "TransactionPlan",
    "TransactionRecord",
    "TransactionStore",
]

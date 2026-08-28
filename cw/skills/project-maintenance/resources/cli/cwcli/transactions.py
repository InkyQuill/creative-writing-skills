"""Persistent plans and content-addressed snapshots for story-file transactions."""

from __future__ import annotations

import difflib
import errno
import hashlib
import json
import os
import shutil
import tempfile
import uuid
import warnings
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath, PureWindowsPath
from types import MappingProxyType

from .documents import logical_hash
from .project import Project


class TransactionError(RuntimeError):
    """Raised when a guarded transaction cannot be completed safely."""


class _StateDurabilityError(TransactionError):
    """Raised when a journal state transition is not durably confirmed."""


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
        self.directory_sync_hook = _fsync_directory

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
            "intents": [],
            "metadata": _jsonable(plan.metadata),
            "state": "prepared",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        rendered_manifest = _render_json(manifest)

        _mkdir_durable(transaction_dir.parent, self.directory_sync_hook)
        try:
            transaction_dir.mkdir()
            self.directory_sync_hook(transaction_dir.parent)
        except FileExistsError as error:
            raise FileExistsError(f"transaction already exists: {identifier}") from error

        try:
            self._write_json(transaction_dir / "manifest.json", rendered_manifest)
        except BaseException:
            shutil.rmtree(transaction_dir)
            self.directory_sync_hook(transaction_dir.parent)
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
        self,
        transaction_id: str,
        state: str,
        *,
        completed: tuple[str, ...] = (),
        intents: tuple[str, ...] | None = None,
    ) -> TransactionRecord:
        """Atomically replace execution state and optional durable intent progress."""

        manifest_path = self._transaction_dir(transaction_id) / "manifest.json"
        manifest = self._read_manifest(transaction_id)
        manifest["state"] = state
        manifest["completed"] = list(completed)
        if intents is not None:
            manifest["intents"] = list(intents)
        elif "intents" not in manifest:
            manifest["intents"] = list(completed)
        self._write_json(manifest_path, _render_json(manifest))
        return TransactionRecord(transaction_id, state, tuple(completed))

    def blob(self, data: bytes) -> str:
        """Persist ``data`` once and return its SHA-256 content identifier."""

        if not isinstance(data, bytes):
            raise TypeError("blob data must be bytes")

        identifier = hashlib.sha256(data).hexdigest()
        blobs = self.root / "blobs"
        _mkdir_durable(blobs, self.directory_sync_hook)
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

    def _write_json(self, destination: Path, rendered: str) -> None:
        stream = tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=destination.parent,
            prefix=f".{destination.name}.",
            suffix=".tmp",
            delete=False,
        )
        temporary = Path(stream.name)
        try:
            with stream:
                stream.write(rendered)
                stream.flush()
                os.fsync(stream.fileno())
            self.directory_sync_hook(destination.parent)
            os.replace(temporary, destination)
            self.directory_sync_hook(destination.parent)
        except BaseException as error:
            cleanup_error = _remove_internal_file(
                temporary, self.directory_sync_hook
            )
            if cleanup_error is not None:
                raise OSError(
                    f"{_error_text(error)}; temporary cleanup failed: "
                    f"{_error_text(cleanup_error)}"
                ) from error
            raise

    def _write_bytes(self, destination: Path, data: bytes) -> None:
        stream = tempfile.NamedTemporaryFile(
            mode="wb",
            dir=destination.parent,
            prefix=f".{destination.name}.",
            suffix=".tmp",
            delete=False,
        )
        temporary = Path(stream.name)
        try:
            with stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            self.directory_sync_hook(destination.parent)
            os.replace(temporary, destination)
            self.directory_sync_hook(destination.parent)
        except BaseException as error:
            cleanup_error = _remove_internal_file(
                temporary, self.directory_sync_hook
            )
            if cleanup_error is not None:
                raise OSError(
                    f"{_error_text(error)}; temporary cleanup failed: "
                    f"{_error_text(cleanup_error)}"
                ) from error
            raise


class TransactionEngine:
    """Guard, stage, apply, and recover multi-file project transactions."""

    def __init__(self, project: Project):
        self.project = project
        self.store = TransactionStore(project)
        self.replace_hook = os.replace
        self.unlink_hook = os.unlink
        self.directory_sync_hook = _fsync_directory

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
        intents: list[str] = []

        try:
            for change in plan.changes:
                if change.after is not None:
                    self._write_staged_bytes(prepared.id, change.path, change.after)

            # Staging may take time. Re-resolve and re-read every target before
            # allowing the first externally visible replacement.
            self._validate_plan(plan)
            self._write_nonterminal_state(
                prepared.id, "applying", completed=(), intents=()
            )

            for change in plan.changes:
                intents.append(change.path)
                self._write_nonterminal_state(
                    prepared.id,
                    "applying",
                    completed=tuple(completed),
                    intents=tuple(intents),
                )
                self._install_change(prepared.id, change)
                completed.append(change.path)
                self._write_nonterminal_state(
                    prepared.id,
                    "applying",
                    completed=tuple(completed),
                    intents=tuple(intents),
                )

            return self._write_terminal_state(
                prepared.id,
                "committed",
                completed=tuple(completed),
                intents=tuple(intents),
            )
        except BaseException as error:
            state_durability_failed = isinstance(error, _StateDurabilityError)
            rollback_intents, progress_errors = self._rollback_intents(
                prepared.id, tuple(intents), tuple(completed)
            )
            rollback_errors = progress_errors
            rollback_errors.extend(
                self._restore_intents(prepared.id, plan.changes, rollback_intents)
            )
            rollback_errors.extend(
                self._cleanup_temporaries(prepared.id, plan.changes)
            )

            if not state_durability_failed and not rollback_errors:
                try:
                    self._write_terminal_state(
                        prepared.id,
                        "rolled-back",
                        completed=tuple(completed),
                        intents=rollback_intents,
                    )
                except BaseException as state_error:
                    rollback_errors.append(_error_text(state_error))

            if state_durability_failed:
                rollback_errors.insert(
                    0, "a journal state transition was not durably confirmed"
                )

            if rollback_errors:
                details = "; ".join(rollback_errors)
                raise TransactionError(
                    f"transaction {prepared.id} failed: {_error_text(error)}; "
                    f"rollback failed and remains recoverable: {details}"
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
        intents = self._manifest_intents(transaction_id, record.completed)
        if len(set(intents)) != len(intents) or any(
            path not in by_path for path in intents
        ):
            raise TransactionError(
                f"transaction {transaction_id} has invalid intent paths"
            )

        # Resolve the complete persisted target set before touching any file.
        self._resolve_changes(changes)
        recovery_errors = self._restore_intents(transaction_id, changes, intents)
        recovery_errors.extend(self._cleanup_temporaries(transaction_id, changes))
        if recovery_errors:
            raise TransactionError(
                f"recovery of transaction {transaction_id} failed: "
                + "; ".join(recovery_errors)
            )
        try:
            return self._write_terminal_state(
                transaction_id,
                "rolled-back",
                completed=record.completed,
                intents=intents,
            )
        except BaseException as error:
            raise TransactionError(
                f"recovery of transaction {transaction_id} could not durably record "
                f"rolled-back state: {_error_text(error)}"
            ) from error

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
                self._mutate_and_sync(
                    lambda: self.unlink_hook(target), target.parent
                )
            return
        temporary = self._temporary_path(transaction_id, change.path)
        self._mutate_and_sync(
            lambda: self.replace_hook(temporary, target), target.parent
        )

    def _rollback_intents(
        self,
        transaction_id: str,
        local_intents: tuple[str, ...],
        completed: tuple[str, ...],
    ) -> tuple[tuple[str, ...], list[str]]:
        errors: list[str] = []
        persisted_intents: tuple[str, ...] = ()
        try:
            persisted_intents = self._manifest_intents(transaction_id, completed)
        except BaseException as error:
            errors.append(f"could not reload durable intents: {_error_text(error)}")
        return _ordered_union(persisted_intents, completed, local_intents), errors

    def _restore_intents(
        self,
        transaction_id: str,
        changes: tuple[Change, ...],
        intents: tuple[str, ...],
    ) -> list[str]:
        by_path = {change.path: change for change in changes}
        errors: list[str] = []
        for path in reversed(intents):
            change = by_path.get(path)
            if change is None:
                errors.append(f"{path}: intent has no persisted change")
                continue
            try:
                self._restore_if_needed(transaction_id, change)
            except BaseException as error:
                errors.append(f"{path}: {_error_text(error)}")
        return errors

    def _restore_if_needed(self, transaction_id: str, change: Change) -> None:
        target = self.project.resolve(change.path, for_write=True)
        current = self._current_bytes(change.path, target)
        if current == change.before:
            return
        if current != change.after:
            raise TransactionError(
                f"recovery conflict for {change.path}: current bytes match neither before nor after"
            )

        self._remove_temporary(transaction_id, change.path)
        if change.before is None:
            try:
                self._mutate_and_sync(lambda: self.unlink_hook(target), target.parent)
            except BaseException as error:
                if isinstance(error, TransactionError) or self._current_bytes(
                    change.path, target
                ) != change.before:
                    raise
            return
        self._write_staged_bytes(transaction_id, change.path, change.before)
        temporary = self._temporary_path(transaction_id, change.path)
        try:
            self._mutate_and_sync(
                lambda: self.replace_hook(temporary, target), target.parent
            )
        except BaseException as error:
            if isinstance(error, TransactionError) or self._current_bytes(
                change.path, target
            ) != change.before:
                raise

    def _current_bytes(self, path: str, target: Path) -> bytes | None:
        try:
            if not target.exists():
                return None
            if not target.is_file():
                raise TransactionError(
                    f"recovery conflict for {path}: target is not a regular file"
                )
            return target.read_bytes()
        except TransactionError:
            raise
        except OSError as error:
            raise TransactionError(
                f"could not classify recovery target {path}: {_error_text(error)}"
            ) from error

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
        temporary = self._temporary_path(transaction_id, path)
        if temporary.exists() or temporary.is_symlink():
            temporary.unlink()
            self.directory_sync_hook(temporary.parent)

    def _write_staged_bytes(self, transaction_id: str, path: str, data: bytes) -> Path:
        destination = self._temporary_path(transaction_id, path)
        descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                descriptor = -1
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            self.directory_sync_hook(destination.parent)
        except BaseException as error:
            if descriptor >= 0:
                os.close(descriptor)
            cleanup_error = _remove_internal_file(
                destination, self.directory_sync_hook
            )
            if cleanup_error is not None:
                raise TransactionError(
                    f"{_error_text(error)}; staged temporary cleanup failed: "
                    f"{_error_text(cleanup_error)}"
                ) from error
            raise
        return destination

    def _mutate_and_sync(self, mutation: Callable[[], object], directory: Path) -> None:
        mutation_error: BaseException | None = None
        try:
            mutation()
        except BaseException as error:
            mutation_error = error

        sync_error: BaseException | None = None
        try:
            self.directory_sync_hook(directory)
        except BaseException as error:
            sync_error = error

        if mutation_error is not None and sync_error is not None:
            raise TransactionError(
                f"mutation failed: {_error_text(mutation_error)}; target directory fsync failed: "
                f"{_error_text(sync_error)}"
            ) from mutation_error
        if mutation_error is not None:
            raise mutation_error
        if sync_error is not None:
            raise TransactionError(
                f"target directory fsync failed: {_error_text(sync_error)}"
            ) from sync_error

    def _write_nonterminal_state(
        self,
        transaction_id: str,
        state: str,
        *,
        completed: tuple[str, ...],
        intents: tuple[str, ...],
    ) -> TransactionRecord:
        try:
            return self.store.write_state(
                transaction_id, state, completed=completed, intents=intents
            )
        except BaseException as error:
            raise _StateDurabilityError(
                f"could not durably persist {state} state for transaction "
                f"{transaction_id}: {_error_text(error)}"
            ) from error

    def _write_terminal_state(
        self,
        transaction_id: str,
        state: str,
        *,
        completed: tuple[str, ...],
        intents: tuple[str, ...],
    ) -> TransactionRecord:
        previous = self.store.load(transaction_id)
        previous_intents = self._manifest_intents(transaction_id, previous.completed)
        if previous.state not in {"prepared", "applying"}:
            raise _StateDurabilityError(
                f"transaction {transaction_id} is already terminal in state {previous.state}"
            )
        try:
            return self.store.write_state(
                transaction_id, state, completed=completed, intents=intents
            )
        except BaseException as error:
            revert_errors: list[str] = []
            try:
                observed = self.store.load(transaction_id)
                if observed.state == state:
                    self.store.write_state(
                        transaction_id,
                        previous.state,
                        completed=previous.completed,
                        intents=previous_intents,
                    )
            except BaseException as revert_error:
                revert_errors.append(
                    f"could not restore nonterminal journal state: {_error_text(revert_error)}"
                )
            suffix = "" if not revert_errors else "; " + "; ".join(revert_errors)
            raise _StateDurabilityError(
                f"could not durably persist terminal {state} state for transaction "
                f"{transaction_id}: {_error_text(error)}{suffix}"
            ) from error

    def _manifest_intents(
        self, transaction_id: str, completed: tuple[str, ...]
    ) -> tuple[str, ...]:
        manifest = self.store._read_manifest(transaction_id)
        rendered = manifest.get("intents", [])
        if not isinstance(rendered, list) or any(
            not isinstance(path, str) for path in rendered
        ):
            raise TransactionError(
                f"transaction {transaction_id} has invalid durable intents"
            )
        rendered_intents = tuple(rendered)
        if (
            len(set(rendered_intents)) != len(rendered_intents)
            or any(not isinstance(path, str) for path in completed)
            or len(set(completed)) != len(completed)
        ):
            raise TransactionError(
                f"transaction {transaction_id} has duplicate or invalid progress paths"
            )
        return _ordered_union(rendered_intents, completed)

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


def _fsync_directory(directory: Path) -> bool:
    """Fsync a directory, or warn and return false when the platform cannot.

    POSIX filesystems normally support opening a directory and syncing its entry
    table. Some platforms, notably Windows, reject that operation. On those
    platforms file contents are still fsynced and atomic replacement is used, but
    crash durability of directory entries remains explicitly best-effort.
    """

    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    try:
        descriptor = os.open(directory, flags)
    except OSError as error:
        if _directory_fsync_unsupported(error):
            warnings.warn(
                "directory fsync is unsupported on this platform; transaction "
                "directory-entry durability is best-effort",
                RuntimeWarning,
                stacklevel=2,
            )
            return False
        raise

    try:
        os.fsync(descriptor)
    except OSError as error:
        if _directory_fsync_unsupported(error):
            warnings.warn(
                "directory fsync is unsupported on this platform; transaction "
                "directory-entry durability is best-effort",
                RuntimeWarning,
                stacklevel=2,
            )
            return False
        raise
    finally:
        os.close(descriptor)
    return True


def _directory_fsync_unsupported(error: OSError) -> bool:
    unsupported = {
        errno.EINVAL,
        getattr(errno, "ENOTSUP", errno.EINVAL),
        getattr(errno, "EOPNOTSUPP", errno.EINVAL),
    }
    if error.errno in unsupported:
        return True
    return os.name == "nt" and error.errno in {
        errno.EACCES,
        errno.EPERM,
        getattr(errno, "EISDIR", errno.EACCES),
    }


def _mkdir_durable(directory: Path, sync_hook: Callable[[Path], object]) -> None:
    missing: list[Path] = []
    current = directory
    while not current.exists():
        missing.append(current)
        if current.parent == current:
            break
        current = current.parent
    directory.mkdir(parents=True, exist_ok=True)
    for created in reversed(missing):
        sync_hook(created.parent)


def _remove_internal_file(
    path: Path, sync_hook: Callable[[Path], object]
) -> BaseException | None:
    if not path.exists() and not path.is_symlink():
        return None
    try:
        path.unlink()
        sync_hook(path.parent)
    except BaseException as error:
        return error
    return None


def _ordered_union(*groups: tuple[str, ...]) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for group in groups:
        for path in group:
            if path not in seen:
                seen.add(path)
                ordered.append(path)
    return tuple(ordered)


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

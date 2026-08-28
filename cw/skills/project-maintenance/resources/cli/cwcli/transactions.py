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


__all__ = ["Change", "TransactionPlan", "TransactionRecord", "TransactionStore"]

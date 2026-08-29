"""Read-only integrity checks for the append-only transaction journal."""

from __future__ import annotations

import hashlib
import json
import os
import stat
from pathlib import Path, PurePosixPath

from ..documents import logical_hash
from ..findings import Finding, Severity
from ..project import Project


INVALID_LAYOUT = "CW-JOURNAL-001"
INVALID_MANIFEST = "CW-JOURNAL-010"
INVALID_BLOB = "CW-JOURNAL-020"
INVALID_REVISION = "CW-JOURNAL-030"
INVALID_INTENT = "CW-JOURNAL-040"
INCOMPLETE_TRANSACTION = "CW-JOURNAL-050"

_TERMINAL_STATES = frozenset({"committed", "rolled-back"})
_ACTIVE_STATES = frozenset({"prepared", "applying"})
_DIGITS = frozenset("0123456789abcdef")


def check_journal(project: Project) -> list[Finding]:
    """Validate journal records and snapshots without recovery or cleanup."""

    root = project.root / ".creative-writing" / "transactions"
    if _path_kind(root) == "missing":
        return [_finding(INVALID_LAYOUT, "warning", "transaction journal directory is missing", ".creative-writing/transactions", "Restore the protected transaction directory without deleting project content.")]
    if _path_kind(root) != "directory":
        return [_finding(INVALID_LAYOUT, "error", "transaction journal must be an ordinary directory without links", ".creative-writing/transactions", "Move the conflicting entry aside without following it, then restore an ordinary directory.")]

    findings: list[Finding] = []
    referenced_blobs: dict[str, set[str | None]] = {}
    for entry in sorted(root.iterdir(), key=lambda item: item.name):
        if entry.name == "blobs":
            continue
        if entry.name == "revisions":
            findings.extend(_check_revisions(project, entry))
            continue
        relative = f".creative-writing/transactions/{entry.name}"
        if _path_kind(entry) != "directory":
            findings.append(_finding(INVALID_LAYOUT, "error", "transaction entry must be an ordinary directory without links", relative, "Preserve the entry and repair the journal layout; do not follow or delete it automatically."))
            continue
        manifest_path = entry / "manifest.json"
        try:
            manifest = json.loads(_read_regular(manifest_path).decode("utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            findings.append(_finding(INVALID_MANIFEST, "error", f"transaction manifest cannot be read safely: {error}", _journal_path(relative, "manifest.json"), "Preserve the journal record and restore its valid manifest from a trusted copy before undo or recovery."))
            continue
        errors, blobs = _validate_manifest(manifest)
        for identifier, logicals in blobs.items():
            referenced_blobs.setdefault(identifier, set()).update(logicals)
        for message in errors:
            findings.append(_finding(INVALID_MANIFEST, "error", message, _journal_path(relative, "manifest.json"), "Preserve the record and repair it only from trusted transaction evidence before undo or recovery."))
        if not isinstance(manifest, dict):
            continue
        state = manifest.get("state")
        if state in _ACTIVE_STATES:
            findings.append(_finding(INCOMPLETE_TRANSACTION, "warning", f"transaction is incomplete in state {state}", _journal_path(relative, "manifest.json"), f"Run cw recover {entry.name} --apply to restore before-snapshots and mark it rolled-back."))
        findings.extend(_intent_findings(manifest, _journal_path(relative, "manifest.json")))

    findings.extend(_check_blobs(project, root / "blobs", referenced_blobs))
    return sorted(findings, key=lambda item: (item.path or "", item.code, item.message))


def _validate_manifest(value: object) -> tuple[list[str], dict[str, set[str | None]]]:
    if not isinstance(value, dict):
        return ["transaction manifest must be a JSON object"], {}
    errors: list[str] = []
    blobs: dict[str, set[str | None]] = {}
    required = {"changes", "command", "completed", "intents", "metadata", "state", "timestamp"}
    if not required.issubset(value):
        errors.append(f"transaction manifest is missing fields: {', '.join(sorted(required - set(value)))}")
    if value.get("state") not in _ACTIVE_STATES | _TERMINAL_STATES:
        errors.append("transaction state is not recognized")
    for field in ("command", "completed", "intents", "changes"):
        if not isinstance(value.get(field), list):
            errors.append(f"transaction {field} must be an array")
    if not isinstance(value.get("metadata"), dict):
        errors.append("transaction metadata must be an object")
    changes = value.get("changes")
    if isinstance(changes, list):
        for index, change in enumerate(changes):
            if not isinstance(change, dict) or not {"path", "before", "after", "diff"}.issubset(change):
                errors.append(f"change {index} has an invalid shape")
                continue
            if not isinstance(change.get("path"), str) or not change["path"]:
                errors.append(f"change {index} has an invalid path")
            for side in ("before", "after"):
                reference = change.get(side)
                if not isinstance(reference, dict) or set(reference) != {"blob", "byte_hash", "logical_hash"}:
                    errors.append(f"change {index} {side} reference has an invalid shape")
                    continue
                blob = reference.get("blob")
                byte_hash = reference.get("byte_hash")
                logical = reference.get("logical_hash")
                if blob is None:
                    if byte_hash is not None or logical is not None:
                        errors.append(f"change {index} {side} absent content has hashes")
                elif not _is_digest(blob) or blob != byte_hash or (logical is not None and not _is_digest(logical)):
                    errors.append(f"change {index} {side} contains invalid snapshot hashes")
                else:
                    blobs.setdefault(blob, set()).add(logical)
    return errors, blobs


def _intent_findings(manifest: dict[str, object], path: str) -> list[Finding]:
    findings: list[Finding] = []
    intents = manifest.get("intents")
    completed = manifest.get("completed")
    changes = manifest.get("changes")
    allowed_files = {
        change.get("path")
        for change in changes
        if isinstance(change, dict) and isinstance(change.get("path"), str)
    } if isinstance(changes, list) else set()
    metadata = manifest.get("metadata")
    allowed_directories: set[str] = set()
    directory_changes = metadata.get("directory-changes") if isinstance(metadata, dict) else None
    if directory_changes is not None:
        if not isinstance(directory_changes, dict) or set(directory_changes) != {"create", "remove"}:
            findings.append(_finding(INVALID_INTENT, "error", "directory-changes must contain exactly create and remove arrays", path, "Repair directory intent metadata only from the original reviewed transaction plan."))
        else:
            for action in ("create", "remove"):
                paths = directory_changes.get(action)
                if not isinstance(paths, list) or not all(isinstance(item, str) and item for item in paths):
                    findings.append(_finding(INVALID_INTENT, "error", f"directory-changes.{action} must be a path array", path, "Repair directory intent metadata only from the original reviewed transaction plan."))
                    continue
                allowed_directories.update(f"@directory:{action}:{item}" for item in paths)
    allowed = allowed_files | allowed_directories
    for field, values in (("intents", intents), ("completed", completed)):
        if not isinstance(values, list):
            continue
        if len(values) != len(set(item for item in values if isinstance(item, str))):
            findings.append(_finding(INVALID_INTENT, "error", f"{field} contains duplicate entries", path, "Restore the exact progress list from durable transaction evidence."))
        for value in values:
            if not isinstance(value, str) or value not in allowed:
                findings.append(_finding(INVALID_INTENT, "error", f"{field} contains an unplanned file or directory intent", path, "Restore the exact progress list from durable transaction evidence."))
    return findings


def _check_blobs(project: Project, directory: Path, referenced: dict[str, set[str | None]]) -> list[Finding]:
    relative = ".creative-writing/transactions/blobs"
    if _path_kind(directory) == "missing" and not referenced:
        return []
    if _path_kind(directory) != "directory":
        return [_finding(INVALID_LAYOUT, "error", "blob store must be an ordinary directory without links", relative, "Restore the blob directory and required snapshots from a trusted copy.")]
    findings: list[Finding] = []
    identifiers = set(referenced)
    for entry in directory.iterdir():
        if _path_kind(entry) != "file" or not _is_digest(entry.name):
            findings.append(_finding(INVALID_BLOB, "error", "blob entry must be a digest-named ordinary file without links", f"{relative}/{entry.name}", "Preserve the entry and restore the content-addressed blob store from trusted evidence."))
            continue
        identifiers.add(entry.name)
    for identifier in sorted(identifiers):
        path = directory / identifier
        try:
            data = _read_regular(path)
        except OSError as error:
            findings.append(_finding(INVALID_BLOB, "error", f"required transaction blob is missing or unsafe: {error}", f"{relative}/{identifier}", "Restore this exact content-addressed blob from a trusted journal copy before undo or recovery."))
            continue
        if hashlib.sha256(data).hexdigest() != identifier:
            findings.append(_finding(INVALID_BLOB, "error", "transaction blob exact-byte hash does not match its identifier", f"{relative}/{identifier}", "Restore this exact content-addressed blob from a trusted journal copy before undo or recovery."))
            continue
        for expected_logical in referenced.get(identifier, set()):
            if expected_logical is None:
                continue
            try:
                actual_logical = logical_hash(data)
            except UnicodeError:
                actual_logical = None
            if actual_logical != expected_logical:
                findings.append(_finding(INVALID_BLOB, "error", "transaction blob logical hash does not match its manifest reference", f"{relative}/{identifier}", "Restore the exact UTF-8 snapshot or manifest reference from trusted transaction evidence."))
    return findings


def _check_revisions(project: Project, directory: Path) -> list[Finding]:
    relative = ".creative-writing/transactions/revisions"
    if _path_kind(directory) != "directory":
        return [_finding(INVALID_LAYOUT, "error", "revision store must be an ordinary directory without links", relative, "Restore the revision directory and descriptors from a trusted copy.")]
    findings: list[Finding] = []
    for entry in sorted(directory.iterdir(), key=lambda item: item.name):
        entry_relative = f"{relative}/{entry.name}"
        if not _is_digest(entry.name) or _path_kind(entry) != "directory":
            findings.append(_finding(INVALID_REVISION, "error", "revision entry must be a digest-named ordinary directory", entry_relative, "Preserve the entry and restore the revision layout from trusted transaction evidence."))
            continue
        try:
            descriptor = json.loads(_read_regular(entry / "descriptor.json").decode("utf-8"))
            snapshot = _read_regular(entry / "snapshot")
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            findings.append(_finding(INVALID_REVISION, "error", f"revision snapshot or descriptor cannot be read safely: {error}", entry_relative, "Restore the exact revision snapshot and descriptor from a trusted copy."))
            continue
        if not isinstance(descriptor, dict) or set(descriptor) != {"byte_hash", "logical_hash"}:
            findings.append(_finding(INVALID_REVISION, "error", "revision descriptor has an invalid shape", _journal_path(entry_relative, "descriptor.json"), "Restore the descriptor from the snapshot's trusted hashes."))
            continue
        byte_hash = descriptor.get("byte_hash")
        recorded_logical = descriptor.get("logical_hash")
        if byte_hash != hashlib.sha256(snapshot).hexdigest():
            findings.append(_finding(INVALID_REVISION, "error", "revision exact-byte hash does not match", entry_relative, "Restore the exact revision snapshot from a trusted copy."))
        try:
            actual_logical = logical_hash(snapshot)
        except UnicodeError:
            actual_logical = None
        if recorded_logical != entry.name or actual_logical != entry.name:
            findings.append(_finding(INVALID_REVISION, "error", "revision logical hash or descriptor identity does not match", entry_relative, "Restore the descriptor and UTF-8 snapshot from a trusted copy."))
    return findings


def _path_kind(path: Path) -> str:
    try:
        mode = path.lstat().st_mode
    except (FileNotFoundError, NotADirectoryError):
        return "missing"
    if stat.S_ISLNK(mode):
        return "symlink"
    if stat.S_ISREG(mode):
        return "file"
    if stat.S_ISDIR(mode):
        return "directory"
    return "other"


def _read_regular(path: Path) -> bytes:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise OSError("not a regular file")
        with os.fdopen(descriptor, "rb") as stream:
            descriptor = -1
            return stream.read()
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _is_digest(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(character in _DIGITS for character in value)


def _journal_path(parent: str, name: str) -> str:
    return PurePosixPath(parent, name).as_posix()


def _finding(code: str, severity: Severity, message: str, path: str, next_action: str) -> Finding:
    return Finding(code=code, severity=severity, message=message, path=path, next_action=next_action)


__all__ = ["INCOMPLETE_TRANSACTION", "INVALID_BLOB", "INVALID_INTENT", "INVALID_LAYOUT", "INVALID_MANIFEST", "INVALID_REVISION", "check_journal"]

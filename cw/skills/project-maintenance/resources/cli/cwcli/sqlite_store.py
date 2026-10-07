"""Bounded undo journal and durable context, stored in two project-local databases.

Both databases use rollback journals: ATTACH gives a single durable commit when
an operation needs to update both. Filesystem installation still uses the engine's
intent protocol. Connections are short lived; read paths never create or migrate.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from .documents import logical_hash

if TYPE_CHECKING:
    from .project import Project
    from .transactions import LegacyTransactionStore, TransactionPlan, TransactionRecord

UNDO_LIMIT = 50


class SQLiteStoreMixin:
    def __init__(self, project: Project) -> None:
        super().__init__(project)
        self.database_path = project.root / ".creative-writing/transactions.sqlite3"
        self.context_path = project.root / ".creative-writing/context.sqlite3"

    def _safe_database(self, path: Path) -> None:
        from . import transactions as tx

        tx._require_directory(path.parent, "protected .creative-writing directory")
        for candidate in (
            path,
            *(Path(str(path) + suffix) for suffix in ("-journal", "-wal", "-shm")),
        ):
            if tx._entry_exists(candidate):
                tx._require_regular_file(candidate, "SQLite database or journal")
                if candidate.stat().st_nlink != 1:
                    raise tx.TransactionError(
                        f"database must not have hard links: {candidate}"
                    )

    def _exists(self, path: Path) -> bool:
        from . import transactions as tx

        if not tx._entry_exists(path.parent):
            return False
        self._safe_database(path)
        return tx._entry_exists(path)

    def _ready(self) -> bool:
        if not self._exists(self.database_path):
            return False
        with self._read_database(self.database_path) as db:
            table = db.execute(
                "SELECT 1 FROM sqlite_master WHERE name='settings'"
            ).fetchone()
            return bool(
                table
                and db.execute(
                    "SELECT 1 FROM settings WHERE key='legacy-imported'"
                ).fetchone()
            )

    @contextmanager
    def _read_database(self, path: Path) -> Iterator[sqlite3.Connection]:
        from . import transactions as tx

        self._safe_database(path)
        connection = None
        try:
            connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
            connection.execute("PRAGMA query_only=ON")
            if connection.execute("PRAGMA user_version").fetchone()[0] not in (0, 1):
                raise tx.TransactionError(f"unsupported database version: {path.name}")
            yield connection
        except sqlite3.Error as error:
            raise tx.TransactionError(f"cannot read {path.name}: {error}") from error
        finally:
            if connection is not None:
                connection.close()

    @contextmanager
    def _write_database(self) -> Iterator[sqlite3.Connection]:
        from . import transactions as tx

        protected = self.database_path.parent
        tx._mkdir_durable(protected, self.directory_sync_hook)
        # A different inode from the engine's project lock; also serializes draft
        # revision writes performed outside engine.apply().
        with tx._project_transaction_lock(protected):
            self._safe_database(self.database_path)
            self._safe_database(self.context_path)
            if not self._exists(self.context_path) and self._ready():
                raise tx.TransactionError(
                    "context.sqlite3 is missing; restore it before writing"
                )
            if not self._exists(self.database_path) and self._exists(self.context_path):
                raise tx.TransactionError(
                    "transactions.sqlite3 is missing; restore it before writing"
                )
            connection = None
            try:
                connection = sqlite3.connect(self.database_path)
                connection.execute(
                    "ATTACH DATABASE ? AS context", (str(self.context_path),)
                )
                for schema in ("main", "context"):
                    version = connection.execute(
                        f"PRAGMA {schema}.user_version"
                    ).fetchone()[0]
                    if version not in (0, 1):
                        raise tx.TransactionError(
                            f"unsupported {schema} database version: {version}"
                        )
                connection.execute("PRAGMA auto_vacuum=FULL")
                connection.execute("PRAGMA journal_mode=DELETE")
                connection.execute("PRAGMA synchronous=FULL")
                connection.execute("PRAGMA context.journal_mode=DELETE")
                connection.execute("PRAGMA context.synchronous=FULL")
                connection.executescript("""
                    CREATE TABLE IF NOT EXISTS transactions (
                        sequence INTEGER PRIMARY KEY, id TEXT UNIQUE NOT NULL,
                        manifest TEXT NOT NULL);
                    CREATE TABLE IF NOT EXISTS blobs (id TEXT PRIMARY KEY, data BLOB NOT NULL);
                    CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                    CREATE TABLE IF NOT EXISTS context.packets (id TEXT PRIMARY KEY, packet TEXT NOT NULL);
                    CREATE TABLE IF NOT EXISTS context.packet_refs (id TEXT PRIMARY KEY, packet_id TEXT NOT NULL);
                    CREATE TABLE IF NOT EXISTS context.revisions (
                        id TEXT PRIMARY KEY, byte_hash TEXT NOT NULL, data BLOB NOT NULL);
                    CREATE TABLE IF NOT EXISTS context.receipts (id TEXT PRIMARY KEY, receipt TEXT NOT NULL);
                    PRAGMA main.user_version=1;
                    PRAGMA context.user_version=1;
                """)
                connection.execute("BEGIN IMMEDIATE")
                try:
                    self._import_legacy(connection)
                except (ValueError, TypeError, KeyError, AttributeError) as error:
                    raise tx.TransactionError(
                        f"invalid legacy journal: {error}"
                    ) from error
                connection.commit()
                self.directory_sync_hook(protected)
                self._remove_imported_legacy(connection)
                connection.execute("BEGIN IMMEDIATE")
                yield connection
                connection.commit()
            except sqlite3.Error as error:
                raise tx.TransactionError(
                    f"cannot write transaction databases: {error}"
                ) from error
            finally:
                if connection is not None:
                    connection.close()

    def _legacy(self) -> LegacyTransactionStore:
        from . import transactions as tx

        return tx.LegacyTransactionStore(self.project)

    def _import_legacy(self, db: sqlite3.Connection) -> None:
        from . import transactions as tx

        if db.execute("SELECT 1 FROM settings WHERE key='legacy-imported'").fetchone():
            return
        legacy = self._legacy()
        inventory = None
        if legacy._require_transactions_directory(allow_missing=True):
            inventory = self._legacy_inventory(legacy.root)
            # Validate the complete tree, including otherwise orphaned blobs,
            # before making either database authoritative or deleting anything.
            from .checks.journal import _intent_errors, _validate_manifest

            manifests = []
            for entry in legacy.history():
                manifest = legacy._read_manifest(entry["id"])
                errors, references = _validate_manifest(self.project, manifest)
                errors.extend(
                    message for message, _ in _intent_errors(self.project, manifest)
                )
                if errors:
                    raise tx.TransactionError(
                        f"invalid legacy transaction {entry['id']}: {'; '.join(errors)}"
                    )
                for identifier, logicals in references.items():
                    data = legacy.read_blob(identifier)
                    self._verify_blob(identifier, data)
                    for expected in logicals:
                        if expected is not None and logical_hash(data) != expected:
                            raise tx.TransactionError(
                                "legacy blob logical hash mismatch"
                            )
                if set((legacy.root / entry["id"]).iterdir()) != {
                    legacy.root / entry["id"] / "manifest.json"
                }:
                    raise tx.TransactionError(
                        "unexpected files in legacy transaction directory"
                    )
                manifests.append((entry["id"], manifest))
            blobs = legacy.root / "blobs"
            if tx._entry_exists(blobs):
                tx._require_directory(blobs, "transaction blob directory")
                for path in blobs.iterdir():
                    data = legacy.read_blob(path.name)
                    self._verify_blob(path.name, data)
                    db.execute("INSERT INTO blobs VALUES (?, ?)", (path.name, data))
            revisions = legacy.root / "revisions"
            if tx._entry_exists(revisions):
                tx._require_directory(revisions, "revision store directory")
                for path in revisions.iterdir():
                    data = legacy.load_revision(path.name)
                    if set(path.iterdir()) != {
                        path / "snapshot",
                        path / "descriptor.json",
                    }:
                        raise tx.TransactionError(
                            "unexpected files in legacy revision directory"
                        )
                    db.execute(
                        "INSERT INTO context.revisions VALUES (?, ?, ?)",
                        (path.name, hashlib.sha256(data).hexdigest(), data),
                    )
            for identifier, manifest in reversed(manifests):
                db.execute(
                    "INSERT INTO transactions(id, manifest) VALUES (?, ?)",
                    (identifier, tx._render_json(manifest)),
                )
                self._save_context(db, identifier, manifest)
            for identifier, manifest in manifests:
                stored = db.execute(
                    "SELECT manifest FROM transactions WHERE id=?", (identifier,)
                ).fetchone()[0]
                if json.loads(stored) != manifest:
                    raise tx.TransactionError(
                        "legacy manifest copy verification failed"
                    )
            for identifier, byte_hash, data in db.execute(
                "SELECT id, byte_hash, data FROM context.revisions"
            ):
                self._verify_revision(identifier, byte_hash, data)
            # Check the copied bytes through SQLite before committing migration.
            for identifier, data in db.execute("SELECT id, data FROM blobs"):
                self._verify_blob(identifier, data)
            if db.execute("PRAGMA integrity_check").fetchone() != ("ok",) or db.execute(
                "PRAGMA context.integrity_check"
            ).fetchone() != ("ok",):
                raise tx.TransactionError(
                    "database integrity check failed during migration"
                )
        current_inventory = (
            self._legacy_inventory(self.root) if tx._entry_exists(self.root) else None
        )
        if current_inventory != inventory:
            raise tx.TransactionError(
                "legacy journal changed during import; preserving original files"
            )
        db.execute("INSERT INTO settings VALUES ('legacy-imported', '1')")
        if inventory is not None:
            db.execute(
                "INSERT INTO settings VALUES ('legacy-cleanup', ?)",
                (json.dumps(inventory, sort_keys=True),),
            )

    def _remove_imported_legacy(self, db: sqlite3.Connection) -> None:
        from . import transactions as tx

        if not db.execute(
            "SELECT 1 FROM settings WHERE key='legacy-imported'"
        ).fetchone():
            return
        cleanup = db.execute(
            "SELECT value FROM settings WHERE key='legacy-cleanup'"
        ).fetchone()
        if not cleanup:
            if tx._entry_exists(self.root):
                tx._require_directory(self.root, "legacy transaction directory")
                if any(self.root.iterdir()):
                    raise tx.TransactionError(
                        "legacy journal appeared after migration; preserve it for manual reconciliation"
                    )
                self.root.rmdir()
            return
        inventory = json.loads(cleanup[0])
        retired = self.root.with_name("transactions.migrated")
        if tx._entry_exists(self.root):
            tx._require_directory(self.root, "legacy transaction directory")
            if tx._entry_exists(retired):
                raise tx.TransactionError(
                    "both legacy and migrated transaction directories exist"
                )
            if self._legacy_inventory(self.root) != inventory:
                raise tx.TransactionError(
                    "legacy journal changed after import; preserving both copies"
                )
            os.rename(self.root, retired)
            self.directory_sync_hook(retired.parent)
        if tx._entry_exists(retired):
            tx._require_directory(retired, "migrated transaction directory")
            remaining = self._legacy_inventory(retired)
            if any(
                key not in inventory or inventory[key] != value
                for key, value in remaining.items()
            ):
                raise tx.TransactionError(
                    "migrated journal changed during cleanup; preserving remaining files"
                )
            shutil.rmtree(retired)
            self.directory_sync_hook(retired.parent)
        db.execute("DELETE FROM settings WHERE key='legacy-cleanup'")
        db.commit()

    @staticmethod
    def _legacy_inventory(root: Path) -> dict[str, str | None]:
        from . import transactions as tx

        inventory = {}
        for directory, dirs, files in os.walk(root, followlinks=False):
            for name in dirs:
                path = Path(directory) / name
                tx._require_directory(path, "legacy directory")
                inventory[path.relative_to(root).as_posix()] = None
            for name in files:
                path = Path(directory) / name
                with tx._open_regular_file(path, "legacy file") as stream:
                    digest = hashlib.sha256()
                    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                        digest.update(chunk)
                inventory[path.relative_to(root).as_posix()] = digest.hexdigest()
        return inventory

    @staticmethod
    def _verify_blob(identifier: str, data: bytes) -> None:
        from . import transactions as tx

        tx._validate_digest(identifier, "blob identifier")
        if hashlib.sha256(data).hexdigest() != identifier:
            raise tx.TransactionError(
                f"blob content does not match identifier {identifier}"
            )

    @staticmethod
    def _save_context(db, identifier, manifest):
        from . import transactions as tx

        packet = manifest["metadata"].get("translation-packet")
        if packet is not None:
            rendered = tx._render_json(packet)
            packet_id = SQLiteStoreMixin.packet_id(packet)
            existing = db.execute(
                "SELECT packet FROM context.packets WHERE id=?", (packet_id,)
            ).fetchone()
            if existing and existing[0] != rendered:
                raise tx.TransactionError(f"context checksum mismatch: {packet_id}")
            reference = db.execute(
                "SELECT packet_id FROM context.packet_refs WHERE id=?", (identifier,)
            ).fetchone()
            if reference and reference[0] != packet_id:
                raise tx.TransactionError(
                    f"context already exists with different contents: {identifier}"
                )
            db.execute(
                "INSERT OR IGNORE INTO context.packets VALUES (?, ?)",
                (packet_id, rendered),
            )
            db.execute(
                "INSERT OR IGNORE INTO context.packet_refs VALUES (?, ?)",
                (identifier, packet_id),
            )
        if manifest["state"] == "committed":
            receipt = {key: manifest[key] for key in ("command", "timestamp")}
            db.execute(
                "INSERT OR REPLACE INTO context.receipts VALUES (?, ?)",
                (identifier, tx._render_json(receipt)),
            )
        else:
            db.execute("DELETE FROM context.receipts WHERE id=?", (identifier,))

    def prepare(
        self, plan: TransactionPlan, *, transaction_id: str | None = None
    ) -> TransactionRecord:
        from . import transactions as tx

        identifier = transaction_id or uuid.uuid4().hex
        self._transaction_dir(identifier)
        # Serialize before opening a write connection; invalid metadata has no effects.
        metadata = tx._jsonable(plan.metadata)
        tx._render_json(metadata)
        with self._write_database() as db:
            if (
                db.execute(
                    "SELECT 1 FROM transactions WHERE id=?", (identifier,)
                ).fetchone()
                or db.execute(
                    "SELECT 1 FROM context.receipts WHERE id=?", (identifier,)
                ).fetchone()
            ):
                raise FileExistsError(f"transaction already exists: {identifier}")
            changes = []
            for change in plan.changes:
                rendered = {
                    "path": change.path,
                    "diff": tx._unified_diff(change.path, change.before, change.after),
                }
                for side in ("before", "after"):
                    data = getattr(change, side)
                    reference = {"blob": None, "byte_hash": None, "logical_hash": None}
                    if data is not None:
                        digest = hashlib.sha256(data).hexdigest()
                        existing = db.execute(
                            "SELECT data FROM blobs WHERE id=?", (digest,)
                        ).fetchone()
                        if existing:
                            self._verify_blob(digest, existing[0])
                        db.execute(
                            "INSERT OR IGNORE INTO blobs VALUES (?, ?)", (digest, data)
                        )
                        try:
                            normalized = logical_hash(data)
                        except UnicodeError:
                            normalized = None
                        reference = {
                            "blob": digest,
                            "byte_hash": digest,
                            "logical_hash": normalized,
                        }
                    rendered[side] = reference
                changes.append(rendered)
            manifest = {
                "changes": changes,
                "command": list(plan.command),
                "completed": [],
                "intents": [],
                "metadata": metadata,
                "state": "prepared",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            db.execute(
                "INSERT INTO transactions(id, manifest) VALUES (?, ?)",
                (identifier, tx._render_json(manifest)),
            )
            self._save_context(db, identifier, manifest)
        return tx.TransactionRecord(identifier, "prepared", ())

    def _read_manifest(self, transaction_id: str) -> dict[str, object]:
        from . import transactions as tx

        self._transaction_dir(transaction_id)
        if not self._ready():
            return self._legacy()._read_manifest(transaction_id)
        with self._read_database(self.database_path) as db:
            row = db.execute(
                "SELECT manifest FROM transactions WHERE id=?", (transaction_id,)
            ).fetchone()
        if row is None:
            raise tx.TransactionError(
                f"transaction is missing or outside the undo history: {transaction_id}"
            )
        return json.loads(row[0])

    def history(self) -> tuple[dict[str, object], ...]:
        if not self._ready():
            return self._legacy().history()
        with self._read_database(self.database_path) as db:
            rows = db.execute(
                "SELECT id, manifest FROM transactions ORDER BY sequence DESC"
            ).fetchall()
        return tuple(
            dict(
                id=identifier,
                **{
                    key: manifest.get(key)
                    for key in ("state", "timestamp", "command", "metadata")
                },
                change_count=len(manifest["changes"]),
            )
            for identifier, raw in rows
            for manifest in [json.loads(raw)]
        )

    def write_state(
        self,
        transaction_id: str,
        state: str,
        *,
        completed: tuple[str, ...] = (),
        intents: tuple[str, ...] | None = None,
    ) -> TransactionRecord:
        from . import transactions as tx

        self._transaction_dir(transaction_id)
        with self._write_database() as db:
            row = db.execute(
                "SELECT manifest FROM transactions WHERE id=?", (transaction_id,)
            ).fetchone()
            if row is None:
                raise tx.TransactionError(f"transaction is missing: {transaction_id}")
            manifest = json.loads(row[0])
            manifest.update(state=state, completed=list(completed))
            manifest["intents"] = (
                list(intents)
                if intents is not None
                else manifest.get("intents", list(completed))
            )
            db.execute(
                "UPDATE transactions SET manifest=? WHERE id=?",
                (tx._render_json(manifest), transaction_id),
            )
            self._save_context(db, transaction_id, manifest)
        return tx.TransactionRecord(transaction_id, state, tuple(completed))

    def blob(self, data: bytes) -> str:
        if not isinstance(data, bytes):
            raise TypeError("blob data must be bytes")
        identifier = hashlib.sha256(data).hexdigest()
        with self._write_database() as db:
            existing = db.execute(
                "SELECT data FROM blobs WHERE id=?", (identifier,)
            ).fetchone()
            if existing:
                self._verify_blob(identifier, existing[0])
            db.execute("INSERT OR IGNORE INTO blobs VALUES (?, ?)", (identifier, data))
        return identifier

    def read_blob(self, identifier: str) -> bytes:
        from . import transactions as tx

        tx._validate_digest(
            identifier, "blob identifier must be a lowercase SHA-256 digest"
        )
        if not self._ready():
            return self._legacy().read_blob(identifier)
        with self._read_database(self.database_path) as db:
            row = db.execute(
                "SELECT data FROM blobs WHERE id=?", (identifier,)
            ).fetchone()
        if row is None:
            raise tx.TransactionError(f"missing transaction blob: {identifier}")
        self._verify_blob(identifier, row[0])
        return row[0]

    def remember_revision(self, logical_hash_value: str, data: bytes) -> str:
        from . import transactions as tx

        tx._validate_digest(logical_hash_value, "logical revision hash")
        if not isinstance(data, bytes):
            raise TypeError("revision data must be bytes")
        if logical_hash(data) != logical_hash_value:
            raise ValueError("revision data does not match the supplied logical hash")
        with self._write_database() as db:
            row = db.execute(
                "SELECT byte_hash, data FROM context.revisions WHERE id=?",
                (logical_hash_value,),
            ).fetchone()
            if row:
                self._verify_revision(logical_hash_value, *row)
            db.execute(
                "INSERT OR IGNORE INTO context.revisions VALUES (?, ?, ?)",
                (logical_hash_value, hashlib.sha256(data).hexdigest(), data),
            )
        return logical_hash_value

    @staticmethod
    def _verify_revision(identifier: str, byte_hash: str, data: bytes) -> bytes:
        from . import transactions as tx

        if hashlib.sha256(data).hexdigest() != byte_hash:
            raise tx.TransactionError(
                f"revision {identifier} exact-byte hash does not match"
            )
        if logical_hash(data) != identifier:
            raise tx.TransactionError(
                f"revision {identifier} logical hash does not match"
            )
        return data

    def load_revision(self, logical_hash_value: str) -> bytes:
        from . import transactions as tx

        tx._validate_digest(logical_hash_value, "logical revision hash")
        if not self._ready():
            return self._legacy().load_revision(logical_hash_value)
        with self._read_database(self.context_path) as db:
            row = db.execute(
                "SELECT byte_hash, data FROM revisions WHERE id=?",
                (logical_hash_value,),
            ).fetchone()
        if row is None:
            raise tx.TransactionError(f"missing revision: {logical_hash_value}")
        return self._verify_revision(logical_hash_value, *row)

    def packet(self, identifier: str) -> dict[str, object]:
        from . import transactions as tx

        self._transaction_dir(identifier)
        if not self._ready():
            return (
                self._legacy()
                ._read_manifest(identifier)["metadata"]
                .get("translation-packet")
            )
        with self._read_database(self.context_path) as db:
            row = db.execute(
                "SELECT id, packet FROM packets WHERE id=?", (identifier,)
            ).fetchone()
            if row is None:
                row = db.execute(
                    "SELECT packets.id, packet FROM packets JOIN packet_refs ON packets.id=packet_refs.packet_id WHERE packet_refs.id=?",
                    (identifier,),
                ).fetchone()
        if row is None:
            raise tx.TransactionError(f"missing translation context: {identifier}")
        if hashlib.sha256(row[1].encode("utf-8")).hexdigest() != row[0]:
            raise tx.TransactionError(f"context checksum mismatch: {identifier}")
        return json.loads(row[1])

    @staticmethod
    def packet_id(packet):
        from . import transactions as tx

        return hashlib.sha256(tx._render_json(packet).encode("utf-8")).hexdigest()

    def has_receipt(self, identifier: str) -> bool:
        if not self._ready():
            return False
        with self._read_database(self.context_path) as db:
            row = db.execute(
                "SELECT receipt FROM receipts WHERE id=?", (identifier,)
            ).fetchone()
        if row is None:
            return False
        receipt = json.loads(row[0])
        return (
            isinstance(receipt, dict)
            and isinstance(receipt.get("command"), list)
            and isinstance(receipt.get("timestamp"), str)
        )

    def prune(self, *, keep: str | None = None) -> None:
        """Keep 50 undoable commits plus all unfinished recovery records."""
        with self._write_database() as db:
            retained = 0
            referenced = set()
            for identifier, raw in db.execute(
                "SELECT id, manifest FROM transactions ORDER BY sequence DESC"
            ).fetchall():
                manifest = json.loads(raw)
                if manifest["state"] in {"committed", "rolled-back"}:
                    undoable = (
                        manifest["state"] == "committed"
                        and manifest["metadata"].get("undoable", True) is True
                    )
                    if identifier != keep and (not undoable or retained >= UNDO_LIMIT):
                        db.execute("DELETE FROM transactions WHERE id=?", (identifier,))
                        continue
                    retained += int(undoable)
                for change in manifest["changes"]:
                    referenced.update(
                        change[side]["blob"]
                        for side in ("before", "after")
                        if change[side]["blob"] is not None
                    )
            db.execute("CREATE TEMP TABLE live_blobs (id TEXT PRIMARY KEY)")
            db.executemany(
                "INSERT INTO live_blobs VALUES (?)", ((value,) for value in referenced)
            )
            db.execute("DELETE FROM blobs WHERE id NOT IN (SELECT id FROM live_blobs)")

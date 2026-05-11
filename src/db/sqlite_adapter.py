"""Concrete SQLite database adapter for EventLog.

This adapter owns low-level SQLite mechanics such as connection lifecycle,
schema initialization, execution helpers, row fetching, and transaction
primitives. Repository CRUD/query behavior remains in the repository layer.
"""

from __future__ import annotations

import logging
from os import PathLike
from pathlib import Path
import sqlite3
from types import TracebackType
from src.db.database_adapter import (
    BackendCleanupArtifactMetadata,
    BackendCleanupMetadata,
    CipherUnavailable,
    DatabaseAdapter,
    DatabaseAdapterError,
    DatabaseNewer,
    EncryptedDatabaseProfileMismatch,
    EncryptedDatabaseUnreadable,
    EncryptedDatabaseWrongKey,
    MigrationNeeded,
)
from src.db.schema.schema_executor import execute_schema_file

try:
    import sqlcipher3
except ImportError:  # pragma: no cover - exercised through runtime environment checks
    sqlcipher3 = None

LOGGER = logging.getLogger(__name__)
SQLITE_APPLICATION_ID = 0x45564C47  # ASCII: EVLG
SQLITE_USER_VERSION = 1
SQLCIPHER_WRONG_KEY_ERROR_SIGNATURES = (
    "file is not a database",
    "file is encrypted or is not a database",
)


def get_remembered_target_cleanup_metadata(
    database_path: str | PathLike[str],
) -> BackendCleanupMetadata:
    """Return SQLite-owned cleanup metadata for an unopened remembered target."""
    normalized_database_path = SQLiteAdapter._normalize_database_path(database_path)
    if normalized_database_path == ":memory:":
        return BackendCleanupMetadata()

    main_database_path = Path(normalized_database_path)
    candidate_artifacts = (
        BackendCleanupArtifactMetadata(
            path=main_database_path,
            artifact_kind="sqlite_main_database",
        ),
        BackendCleanupArtifactMetadata(
            path=Path(f"{normalized_database_path}-wal"),
            artifact_kind="sqlite_wal_sidecar",
        ),
        BackendCleanupArtifactMetadata(
            path=Path(f"{normalized_database_path}-shm"),
            artifact_kind="sqlite_shm_sidecar",
        ),
        BackendCleanupArtifactMetadata(
            path=Path(f"{normalized_database_path}-journal"),
            artifact_kind="sqlite_journal_sidecar",
        ),
    )
    return BackendCleanupMetadata(
        artifacts=tuple(artifact for artifact in candidate_artifacts if artifact.path.exists())
    )
class SQLCipherUnavailable(CipherUnavailable):
    """Raised when SQLite encrypted mode is requested but SQLCipher support is unavailable."""


class SQLiteAdapter(DatabaseAdapter):
    """Low-level SQLite adapter implementing the shared database contract."""

    def __init__(self, database_path: str | PathLike[str], *, encryption_key: bytes | None = None) -> None:
        """Create an adapter backed by a file path or ``:memory:`` database."""
        self._initialize_runtime_state(database_path, encryption_key=encryption_key)
        try:
            self.connect()
            self.initialize_schema()
        except Exception:
            self.close()
            raise

    @classmethod
    def migrate_database(
        cls,
        database_path: str | PathLike[str],
        *,
        encryption_key: bytes | None = None,
    ) -> bool:
        """Migrate one existing SQLite database to the current supported version.

        Returns ``True`` when a migration step was applied and ``False`` when the
        target was already at the current version.
        """
        adapter = cls._open_connected_adapter(database_path, encryption_key=encryption_key)
        try:
            return adapter.migrate_to_current_version()
        finally:
            adapter.close()

    def __enter__(self) -> SQLiteAdapter:
        """Return the adapter instance for ``with`` statement usage."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Roll back on exception and always close the database resources."""
        if exc_type is not None:
            self.rollback_transaction()
        self.close()

    def connect(self) -> None:
        """Establish the SQLite connection and row-oriented cursor state."""
        dbapi_module = self._resolve_dbapi_module()

        try:
            self.connection = dbapi_module.connect(self.database_path)
        except Exception as exc:
            raise DatabaseAdapterError(f"Could not open SQLite database {self.database_path!r}") from exc

        self.connection.row_factory = getattr(dbapi_module, "Row", sqlite3.Row)
        self.cursor = self.connection.cursor()

        if self._uses_encryption:
            self._apply_sqlcipher_key()
            self._verify_encrypted_readiness()

    def initialize_schema(self) -> None:
        """Bring the SQLite target to a ready metadata-validated schema state."""
        if self._database_preexisted:
            self._validate_existing_profile_metadata()
            return

        execute_schema_file(self.connection, self._schema_file_path())
        self._stamp_profile_metadata()
        LOGGER.info("Initialized SQLite schema for EventLog adapter.")

    def migrate_to_current_version(self) -> bool:
        """Apply supported SQLite migrations for an already existing database."""
        if not self._database_preexisted:
            raise DatabaseAdapterError(
                f"Cannot migrate SQLite database {self.database_path!r} because it does not exist yet."
            )

        self._require_supported_application_id()
        starting_user_version = self._read_pragma_int("user_version")
        if starting_user_version == SQLITE_USER_VERSION:
            return False
        if starting_user_version > SQLITE_USER_VERSION:
            raise DatabaseNewer(
                f"{self._profile_label()} {self.database_path!r} has newer user_version {starting_user_version!r}; "
                f"this app supports up to {SQLITE_USER_VERSION!r}."
            )

        current_user_version = starting_user_version
        while current_user_version < SQLITE_USER_VERSION:
            migration_step = self._resolve_supported_migration(current_user_version)
            if migration_step is None:
                raise MigrationNeeded(
                    f"{self._profile_label()} {self.database_path!r} requires migration from user_version "
                    f"{current_user_version!r} to {SQLITE_USER_VERSION!r}, but no supported migration path exists."
                )

            migration_step()
            migrated_user_version = self._read_pragma_int("user_version")
            if migrated_user_version <= current_user_version:
                raise DatabaseAdapterError(
                    f"SQLite migration for {self.database_path!r} did not advance user_version beyond "
                    f"{current_user_version!r}."
                )
            current_user_version = migrated_user_version

        return True

    def execute(
        self,
        query: str,
        params: tuple[object, ...] = (),
    ) -> sqlite3.Cursor:
        """Execute one SQL statement and return the SQLite cursor."""
        return self._require_open_connection().execute(query, params)

    def fetch(
        self,
        query: str,
        params: tuple[object, ...] = (),
    ) -> list[sqlite3.Row]:
        """Execute one SQL query and return all matching SQLite rows."""
        return self._require_open_connection().execute(query, params).fetchall()

    def fetchone(
        self,
        query: str,
        params: tuple[object, ...] = (),
    ) -> sqlite3.Row | None:
        """Execute one SQL query and return the first matching SQLite row."""
        return self._require_open_connection().execute(query, params).fetchone()

    def begin_transaction(self) -> None:
        """Start an explicit transaction for multi-step operations."""
        self._explicit_transaction_active = True
        self._require_open_connection().execute("BEGIN")

    def commit_transaction(self) -> None:
        """Commit the active transaction."""
        self._require_open_connection().commit()
        self._explicit_transaction_active = False

    def rollback_transaction(self) -> None:
        """Roll back the active transaction."""
        self._require_open_connection().rollback()
        self._explicit_transaction_active = False

    def close(self) -> None:
        """Close the cursor and SQLite connection."""
        cursor = self.cursor
        connection = self.connection
        self.cursor = None
        self.connection = None

        if cursor is not None:
            try:
                cursor.close()
            except Exception:
                pass

        if connection is not None:
            try:
                connection.close()
            except Exception:
                pass

    def get_cleanup_metadata(self) -> BackendCleanupMetadata:
        """Return backend-owned cleanup metadata for the active SQLite footprint."""
        if self.database_path == ":memory:":
            return BackendCleanupMetadata()

        main_database_path = Path(self.database_path)
        candidate_artifacts = (
            BackendCleanupArtifactMetadata(
                path=main_database_path,
                artifact_kind="database",
            ),
            BackendCleanupArtifactMetadata(
                path=Path(f"{self.database_path}-wal"),
                artifact_kind="wal",
            ),
            BackendCleanupArtifactMetadata(
                path=Path(f"{self.database_path}-shm"),
                artifact_kind="shm",
            ),
            BackendCleanupArtifactMetadata(
                path=Path(f"{self.database_path}-journal"),
                artifact_kind="journal",
            ),
        )
        return BackendCleanupMetadata(
            artifacts=tuple(artifact for artifact in candidate_artifacts if artifact.path.exists())
        )

    def get_cleanup_target_paths(self) -> tuple[Path, ...]:
        """Return cleanup target paths as a compatibility shim.

        New cleanup/reporting work should consume `get_cleanup_metadata()` so
        backend-owned artifact details stay in the adapter layer.
        """
        return tuple(artifact.path for artifact in self.get_cleanup_metadata().artifacts)

    def _initialize_runtime_state(
        self,
        database_path: str | PathLike[str],
        *,
        encryption_key: bytes | None,
    ) -> None:
        """Normalize constructor inputs into reusable adapter runtime state."""
        self.database_path = self._normalize_database_path(database_path)
        self.encryption_key = self._normalize_encryption_key(encryption_key)
        self._uses_encryption = self.encryption_key is not None
        self._database_preexisted = self._database_file_exists()
        self.connection = None
        self.cursor = None
        self._explicit_transaction_active = False

    def _require_open_connection(self):
        """Return the live SQLite connection or raise a stable closed-state error."""
        if self.connection is None:
            raise DatabaseAdapterError(f"SQLite database {self.database_path!r} is closed.")
        return self.connection

    @classmethod
    def _open_connected_adapter(
        cls,
        database_path: str | PathLike[str],
        *,
        encryption_key: bytes | None,
    ) -> SQLiteAdapter:
        """Return a connected SQLite adapter without running readiness validation."""
        adapter = cls.__new__(cls)
        adapter._initialize_runtime_state(database_path, encryption_key=encryption_key)
        try:
            adapter.connect()
        except Exception:
            adapter.close()
            raise
        return adapter

    @staticmethod
    def _normalize_database_path(database_path: str | PathLike[str]) -> str:
        """Return a SQLite connection target string for file or memory databases."""
        if str(database_path) == ":memory:":
            return ":memory:"
        return str(Path(database_path).expanduser())

    @staticmethod
    def _normalize_encryption_key(encryption_key: bytes | None) -> bytes | None:
        """Return validated raw encryption key bytes or ``None`` for plaintext mode."""
        if encryption_key is None:
            return None

        if not isinstance(encryption_key, bytes):
            raise TypeError("encryption_key must be bytes or None")

        if not encryption_key:
            raise ValueError("encryption_key must not be empty")

        return encryption_key

    def _database_file_exists(self) -> bool:
        """Return whether the configured database target already exists on disk."""
        if self.database_path == ":memory:":
            return False
        return Path(self.database_path).exists()

    def _resolve_dbapi_module(self):
        """Return the DB-API module matching the requested adapter mode."""
        if not self._uses_encryption:
            return sqlite3

        if sqlcipher3 is None:
            raise SQLCipherUnavailable(
                "SQLCipher support is unavailable. Install the configured sqlcipher3 dependency first."
            )

        return sqlcipher3

    def _apply_sqlcipher_key(self) -> None:
        """Apply the raw derived key bytes to the current SQLCipher connection."""
        assert self.encryption_key is not None
        key_pragma = f"PRAGMA key = \"x'{self.encryption_key.hex()}'\""

        try:
            self.connection.execute(key_pragma)
        except Exception as exc:
            raise EncryptedDatabaseUnreadable(
                f"Could not apply encrypted SQLite key material for {self.database_path!r}."
            ) from exc

    def _verify_encrypted_readiness(self) -> None:
        """Confirm that the encrypted connection can read the SQLite catalog safely."""
        try:
            self.connection.execute("SELECT COUNT(*) FROM sqlite_master").fetchone()
        except Exception as exc:
            if self._database_preexisted and self._looks_like_wrong_key_failure(exc):
                raise EncryptedDatabaseWrongKey(
                    f"Could not unlock encrypted SQLite database {self.database_path!r} with the supplied key material."
                ) from exc

            operation = "open" if self._database_preexisted else "create"
            raise EncryptedDatabaseUnreadable(
                f"Could not {operation} encrypted SQLite database {self.database_path!r}. "
                "The database may be unreadable, corrupted, or unlocked with incompatible key material."
            ) from exc

    @staticmethod
    def _looks_like_wrong_key_failure(exc: Exception) -> bool:
        """Return whether the backend failure text matches a known wrong-key signature."""
        message = str(exc).casefold()
        return any(signature in message for signature in SQLCIPHER_WRONG_KEY_ERROR_SIGNATURES)

    def _stamp_profile_metadata(self) -> None:
        """Stamp authoritative SQLite profile metadata for a newly created database."""
        try:
            self.connection.execute(f"PRAGMA application_id = {SQLITE_APPLICATION_ID}")
            self.connection.execute(f"PRAGMA user_version = {SQLITE_USER_VERSION}")
        except Exception as exc:
            raise self._profile_metadata_error(
                f"Could not stamp SQLite profile metadata for {self.database_path!r}."
            ) from exc

    def _validate_existing_profile_metadata(self) -> None:
        """Validate authoritative SQLite profile metadata for a preexisting database."""
        self._require_supported_application_id()

        user_version = self._read_pragma_int("user_version")
        if user_version < SQLITE_USER_VERSION:
            raise MigrationNeeded(
                f"{self._profile_label()} {self.database_path!r} requires migration from user_version "
                f"{user_version!r} to {SQLITE_USER_VERSION!r} before it can be used."
            )
        if user_version > SQLITE_USER_VERSION:
            raise DatabaseNewer(
                f"{self._profile_label()} {self.database_path!r} has newer user_version {user_version!r}; "
                f"this app supports up to {SQLITE_USER_VERSION!r}."
            )

    def _require_supported_application_id(self) -> None:
        """Require the authoritative EventLog SQLite application id."""
        application_id = self._read_pragma_int("application_id")
        if application_id != SQLITE_APPLICATION_ID:
            raise self._profile_metadata_error(
                f"{self._profile_label()} {self.database_path!r} has unsupported application_id "
                f"{application_id!r}; expected {SQLITE_APPLICATION_ID!r}."
            )


    def _profile_label(self) -> str:
        """Return the current SQLite profile label used in validation errors."""
        if self._uses_encryption:
            return "Encrypted SQLite database"
        return "SQLite database"

    def _profile_metadata_error(self, message: str) -> DatabaseAdapterError:
        """Return the profile-metadata exception type for the current adapter mode."""
        if self._uses_encryption:
            return EncryptedDatabaseProfileMismatch(message)
        return DatabaseAdapterError(message)

    def _read_pragma_int(self, pragma_name: str) -> int:
        """Return one integer SQLite PRAGMA value used for profile validation."""
        try:
            row = self.connection.execute(f"PRAGMA {pragma_name}").fetchone()
        except Exception as exc:
            raise self._profile_metadata_error(
                f"Could not read SQLite profile metadata {pragma_name!r} for {self.database_path!r}."
            ) from exc

        if row is None:
            raise self._profile_metadata_error(
                f"{self._profile_label()} {self.database_path!r} did not return PRAGMA {pragma_name!r}."
            )

        if isinstance(row, tuple):
            value = row[0]
        else:
            try:
                value = row[pragma_name]
            except (KeyError, TypeError, IndexError):
                value = row[0]

        if not isinstance(value, int) or isinstance(value, bool):
            raise self._profile_metadata_error(
                f"{self._profile_label()} {self.database_path!r} returned non-integer PRAGMA "
                f"{pragma_name!r}: {value!r}."
            )

        return value


    @staticmethod
    def _schema_file_path() -> Path:
        """Return the absolute path to the initial SQLite schema file."""
        return Path(__file__).resolve().parent / "schema" / "sqlite" / "initial_schema.sql"


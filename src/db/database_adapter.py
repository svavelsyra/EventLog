"""Low-level database adapter contract for EventLog.

This module defines the backend-facing persistence boundary used by repository
implementations. Adapters own connection lifecycle, schema initialization,
query execution helpers, and transaction primitives. Domain CRUD workflows stay
in the repository layer.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import TypeAlias, cast

SqlParameters: TypeAlias = tuple[object, ...]
DatabaseRow: TypeAlias = object
DatabaseCursor: TypeAlias = object


@dataclass(frozen=True, slots=True)
class BackendCleanupArtifactMetadata:
    """Backend-owned metadata for one active-footprint cleanup artifact."""

    path: Path
    artifact_kind: str = "active_footprint"
    allow_secure_overwrite: bool = True


@dataclass(frozen=True, slots=True)
class BackendCleanupMetadata:
    """Backend-owned active-footprint cleanup metadata for the current adapter."""

    artifacts: tuple[BackendCleanupArtifactMetadata, ...] = ()


class DatabaseAdapterError(Exception):
    """Base exception for database adapter and backend selection failures."""


class DatabaseNewer(DatabaseAdapterError):
    """Raised when the on-disk database format is newer than this app supports."""


class MigrationNeeded(DatabaseAdapterError):
    """Raised when a database requires a migration before normal use can continue."""


class WrongDatabaseAdapter(DatabaseAdapterError):
    """Raised when a repository is paired with an incompatible database adapter."""


class EncryptedDatabaseError(DatabaseAdapterError):
    """Base exception for encrypted database readiness and unlock failures."""


class CipherUnavailable(EncryptedDatabaseError):
    """Raised when encrypted mode is requested but the required cipher backend is unavailable."""


class EncryptedDatabaseWrongKey(EncryptedDatabaseError):
    """Raised when supplied key material cannot unlock an encrypted database."""


class EncryptedDatabaseUnreadable(EncryptedDatabaseError):
    """Raised when an encrypted database cannot be opened or read safely."""


class EncryptedDatabaseProfileMismatch(EncryptedDatabaseError):
    """Raised when encrypted database metadata does not match the expected adapter/profile."""


class DatabaseAdapter(ABC):
    """Abstract low-level adapter contract for database mechanics.

    Concrete adapters implement backend-specific behavior such as opening
    connections, initializing schemas, executing SQL, fetching rows, and
    managing transaction state.
    """

    @abstractmethod
    def connect(self) -> None:
        """Establish the underlying database connection.

        Returns:
            None.

        Raises:
            DatabaseAdapterError: If the backend connection cannot be opened.
        """
        raise NotImplementedError

    @abstractmethod
    def initialize_schema(self) -> None:
        """Create or align the backend schema needed for repository use.

        Returns:
            None.

        Raises:
            DatabaseAdapterError: If schema initialization cannot complete.
            DatabaseNewer: If the database format is newer than supported.
            MigrationNeeded: If a migration is required before use.
        """
        raise NotImplementedError

    @abstractmethod
    def execute(
        self,
        query: str,
        params: SqlParameters = (),
    ) -> DatabaseCursor:
        """Execute one SQL statement that may mutate state or return a cursor.

        Args:
            query: SQL text to execute.
            params: Positional SQL parameters bound to the statement.

        Returns:
            A backend-specific cursor or execution result object.

        Raises:
            DatabaseAdapterError: If statement execution fails.
        """
        raise NotImplementedError

    @abstractmethod
    def fetch(
        self,
        query: str,
        params: SqlParameters = (),
    ) -> list[DatabaseRow]:
        """Execute one SQL query and return all matching rows.

        Args:
            query: SQL text to execute.
            params: Positional SQL parameters bound to the statement.

        Returns:
            A list of backend-specific row objects.

        Raises:
            DatabaseAdapterError: If the query cannot be executed.
        """
        raise NotImplementedError

    @abstractmethod
    def fetchone(
        self,
        query: str,
        params: SqlParameters = (),
    ) -> DatabaseRow | None:
        """Execute one SQL query and return the first matching row.

        Args:
            query: SQL text to execute.
            params: Positional SQL parameters bound to the statement.

        Returns:
            One backend-specific row object, or ``None`` when no row matches.

        Raises:
            DatabaseAdapterError: If the query cannot be executed.
        """
        raise NotImplementedError

    @abstractmethod
    def begin_transaction(self) -> None:
        """Start an explicit database transaction.

        Returns:
            None.

        Raises:
            DatabaseAdapterError: If a transaction cannot be started.
        """
        raise NotImplementedError

    @abstractmethod
    def commit_transaction(self) -> None:
        """Commit the active database transaction.

        Returns:
            None.

        Raises:
            DatabaseAdapterError: If commit fails.
        """
        raise NotImplementedError

    @abstractmethod
    def rollback_transaction(self) -> None:
        """Roll back the active database transaction.

        Returns:
            None.

        Raises:
            DatabaseAdapterError: If rollback fails.
        """
        raise NotImplementedError

    @abstractmethod
    def close(self) -> None:
        """Release database resources held by the adapter.

        Returns:
            None.

        Raises:
            DatabaseAdapterError: If cleanup fails.
        """
        raise NotImplementedError

    def get_cleanup_metadata(self) -> BackendCleanupMetadata:
        """Return backend-owned metadata for active-footprint cleanup.

        This default implementation is intentionally transitional so existing
        adapters and test doubles that still expose `get_cleanup_target_paths()`
        remain compatible while direct dependents move to the explicit metadata
        seam.
        """

        legacy_target_getter = getattr(self, "get_cleanup_target_paths", None)
        if not callable(legacy_target_getter):
            return BackendCleanupMetadata()

        cleanup_target_paths = cast(tuple[Path, ...], legacy_target_getter())
        return BackendCleanupMetadata(
            artifacts=tuple(
                BackendCleanupArtifactMetadata(path=Path(cleanup_target_path))
                for cleanup_target_path in cleanup_target_paths
            )
        )


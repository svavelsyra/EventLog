"""Low-level database adapter contract for EventLog.

This module defines the backend-facing persistence boundary used by repository
implementations. Adapters own connection lifecycle, schema initialization,
query execution helpers, and transaction primitives. Domain CRUD workflows stay
in the repository layer.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TypeAlias

SqlParameters: TypeAlias = tuple[object, ...]
DatabaseRow: TypeAlias = object
DatabaseCursor: TypeAlias = object


class DatabaseAdapterError(Exception):
    """Base exception for database adapter and backend selection failures."""


class DatabaseNewer(DatabaseAdapterError):
    """Raised when the on-disk database format is newer than this app supports."""


class MigrationNeeded(DatabaseAdapterError):
    """Raised when a database requires a migration before normal use can continue."""


class WrongDatabaseAdapter(DatabaseAdapterError):
    """Raised when a repository is paired with an incompatible database adapter."""


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


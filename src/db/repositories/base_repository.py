"""Generic repository base for EventLog persistence classes.

This module defines the repository-facing base that sits above the low-level
adapter layer. Concrete repositories keep CRUD/query logic in the repository
layer while delegating connection and transaction mechanics to the injected
adapter.
"""

from __future__ import annotations

from abc import ABC

from src.db.database_adapter import DatabaseAdapter


class BaseRepository(ABC):
    """Dialect-agnostic base class for application-facing repositories.

    Args:
        adapter: Low-level database adapter used for execution and transaction
            mechanics.
    """

    def __init__(self, adapter: DatabaseAdapter) -> None:
        """Store the adapter used by the concrete repository.

        Args:
            adapter: Low-level database adapter used by this repository.
        """
        self._adapter = adapter

    @property
    def adapter(self) -> DatabaseAdapter:
        """Return the injected low-level database adapter.

        Returns:
            The adapter instance used by this repository.
        """
        return self._adapter

    def begin_transaction(self) -> None:
        """Start an explicit database transaction via the adapter.

        Returns:
            None.
        """
        self._adapter.begin_transaction()

    def commit_transaction(self) -> None:
        """Commit the active database transaction via the adapter.

        Returns:
            None.
        """
        self._adapter.commit_transaction()

    def rollback_transaction(self) -> None:
        """Roll back the active database transaction via the adapter.

        Returns:
            None.
        """
        self._adapter.rollback_transaction()

    def close(self) -> None:
        """Release database resources through the adapter.

        Returns:
            None.
        """
        self._adapter.close()


"""Repository factory for EventLog persistence.

Backend support selection now comes from the centralized bootstrap backend
policy seam so this factory can stay focused on repository construction.
"""

from __future__ import annotations

from os import PathLike

from src.db.repositories.base_repository import BaseRepository
from src.db.repositories.bootstrap_backend_policy import (
    SQLITE_DIALECT,
    create_event_log_repository,
)


class RepositoryFactory:
    """Create ready-to-use repositories for the currently supported backend.

    The current implementation intentionally supports only SQLite and in-memory
    SQLite. It should be treated as a compatibility-focused construction seam,
    not as the finished multi-backend bootstrap system.
    """

    @staticmethod
    def create_event_log_repository(
        *,
        database_path: str | PathLike[str],
        dialect: str = SQLITE_DIALECT,
        encryption_key: bytes | None = None,
    ) -> BaseRepository:
        """Create a ready-to-use EventLog repository for the supported dialect.

        Args:
            database_path: File path or ``:memory:`` target for the SQLite DB.
            dialect: Requested database dialect. Only ``"sqlite"`` is currently
                supported.
            encryption_key: Optional backend-ready derived key bytes used to
                open/create the encrypted SQLite backend.

        Returns:
            A repository-facing abstraction backed by the selected adapter.

        Raises:
            WrongDatabaseAdapter: If the requested dialect is unsupported.
        """
        return create_event_log_repository(
            database_path=database_path,
            dialect=dialect,
            encryption_key=encryption_key,
        )

    @staticmethod
    def create_in_memory_repository(*, encryption_key: bytes | None = None) -> BaseRepository:
        """Create a ready-to-use in-memory repository for tests and similar flows."""
        return RepositoryFactory.create_event_log_repository(
            database_path=":memory:",
            encryption_key=encryption_key,
        )


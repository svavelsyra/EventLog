"""Repository factory for EventLog persistence.

WARNING: This is a deliberately naive transitional factory.
It centralizes the current SQLite-only repository construction path so higher
layers stop hardcoding SQLite wiring, but it is not yet the final bootstrap
architecture. Future work should evolve this into the broader backend-agnostic
bootstrap coordinator described in `ai_instructions/architecture/db_architecture.md`.
"""

from __future__ import annotations

from os import PathLike

from src.db.database_adapter import WrongDatabaseAdapter
from src.db.repositories.base_repository import BaseRepository
from src.db.repositories.sqlite.event_log_repository import EventLogRepository
from src.db.sqlite_adapter import SQLiteAdapter

SQLITE_DIALECT = "sqlite"


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
    ) -> BaseRepository:
        """Create a ready-to-use EventLog repository for the supported dialect.

        Args:
            database_path: File path or ``:memory:`` target for the SQLite DB.
            dialect: Requested database dialect. Only ``"sqlite"`` is currently
                supported.

        Returns:
            A repository-facing abstraction backed by the selected adapter.

        Raises:
            WrongDatabaseAdapter: If the requested dialect is unsupported.
        """
        if dialect != SQLITE_DIALECT:
            raise WrongDatabaseAdapter(
                f"Unsupported repository dialect {dialect!r}. Only {SQLITE_DIALECT!r} is currently supported."
            )

        adapter = SQLiteAdapter(database_path)
        return EventLogRepository(adapter)

    @staticmethod
    def create_in_memory_repository() -> BaseRepository:
        """Create a ready-to-use in-memory repository for tests and similar flows."""
        return RepositoryFactory.create_event_log_repository(database_path=":memory:")


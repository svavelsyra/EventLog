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

from src.db.database_adapter import DatabaseAdapter
from src.db.schema.schema_executor import execute_schema_file

LOGGER = logging.getLogger(__name__)


class SQLiteAdapter(DatabaseAdapter):
    """Low-level SQLite adapter implementing the shared database contract."""

    def __init__(self, database_path: str | PathLike[str]) -> None:
        """Create an adapter backed by a file path or ``:memory:`` database."""
        self.database_path = self._normalize_database_path(database_path)
        self.connection: sqlite3.Connection
        self.cursor: sqlite3.Cursor
        self._explicit_transaction_active = False
        self.connect()
        self.initialize_schema()

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
        self.connection = sqlite3.connect(self.database_path)
        self.connection.row_factory = sqlite3.Row
        self.cursor = self.connection.cursor()

    def initialize_schema(self) -> None:
        """Create the schema when the database does not yet contain core tables."""
        if not self._core_tables_exist():
            execute_schema_file(self.connection, self._schema_file_path())
            LOGGER.info("Initialized SQLite schema for EventLog adapter.")

    def execute(
        self,
        query: str,
        params: tuple[object, ...] = (),
    ) -> sqlite3.Cursor:
        """Execute one SQL statement and return the SQLite cursor."""
        return self.connection.execute(query, params)

    def fetch(
        self,
        query: str,
        params: tuple[object, ...] = (),
    ) -> list[sqlite3.Row]:
        """Execute one SQL query and return all matching SQLite rows."""
        return self.connection.execute(query, params).fetchall()

    def fetchone(
        self,
        query: str,
        params: tuple[object, ...] = (),
    ) -> sqlite3.Row | None:
        """Execute one SQL query and return the first matching SQLite row."""
        return self.connection.execute(query, params).fetchone()

    def begin_transaction(self) -> None:
        """Start an explicit transaction for multi-step operations."""
        self._explicit_transaction_active = True
        self.connection.execute("BEGIN")

    def commit_transaction(self) -> None:
        """Commit the active transaction."""
        self.connection.commit()
        self._explicit_transaction_active = False

    def rollback_transaction(self) -> None:
        """Roll back the active transaction."""
        self.connection.rollback()
        self._explicit_transaction_active = False

    def close(self) -> None:
        """Close the cursor and SQLite connection."""
        self.cursor.close()
        self.connection.close()

    @staticmethod
    def _normalize_database_path(database_path: str | PathLike[str]) -> str:
        """Return a SQLite connection target string for file or memory databases."""
        if str(database_path) == ":memory:":
            return ":memory:"
        return str(Path(database_path).expanduser())

    def _core_tables_exist(self) -> bool:
        """Return whether the main entity tables already exist in the database."""
        row = self.connection.execute(
            """
            SELECT COUNT(*) AS table_count
            FROM sqlite_master
            WHERE type = 'table'
              AND name IN (
                  'communication_entries',
                  'event_entries',
                  'personnel_entries'
              )
            """
        ).fetchone()
        return bool(row is not None and row["table_count"] == 3)

    @staticmethod
    def _schema_file_path() -> Path:
        """Return the absolute path to the initial SQLite schema file."""
        return Path(__file__).resolve().parent / "schema" / "sqlite" / "initial_schema.sql"


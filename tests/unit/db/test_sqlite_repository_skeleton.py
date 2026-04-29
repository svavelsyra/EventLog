import sqlite3
from pathlib import Path

import pytest

from src.db.repositories.sqlite.event_log_repository import EventLogRepository
from src.db.sqlite_adapter import SQLiteAdapter


pytestmark = pytest.mark.unit

EXPECTED_TABLES = {
    "communication_entries",
    "event_entries",
    "personnel_entries",
    "settings",
}

def _get_table_names(repository: EventLogRepository) -> set[str]:
    rows = repository.connection.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
        """
    ).fetchall()
    return {row[0] for row in rows}


def test_repository_initializes_memory_connection_and_schema(
    repository: EventLogRepository,
) -> None:
    assert repository.database_path == ":memory:"
    assert repository.connection.row_factory is sqlite3.Row
    assert _get_table_names(repository) == EXPECTED_TABLES

    row = repository.connection.execute("SELECT 1 AS value").fetchone()

    assert isinstance(row, sqlite3.Row)
    assert row["value"] == 1


def test_initialize_schema_is_safe_to_call_multiple_times(
    repository: EventLogRepository,
) -> None:
    repository.initialize_schema()
    repository.initialize_schema()

    assert _get_table_names(repository) == EXPECTED_TABLES


def test_begin_transaction_and_commit_persist_changes(
    repository: EventLogRepository,
) -> None:
    repository.begin_transaction()
    repository.connection.execute(
        """
        INSERT INTO communication_entries (message_content, logged_time, operator)
        VALUES (?, ?, ?)
        """,
        ("Committed message", "2026-04-27T11:00:00", "Operator One"),
    )
    repository.commit()

    count = repository.connection.execute(
        "SELECT COUNT(*) FROM communication_entries"
    ).fetchone()[0]

    assert count == 1


def test_begin_transaction_and_rollback_discard_changes(
    repository: EventLogRepository,
) -> None:
    repository.begin_transaction()
    repository.connection.execute(
        """
        INSERT INTO communication_entries (message_content, logged_time, operator)
        VALUES (?, ?, ?)
        """,
        ("Rolled back message", "2026-04-27T11:05:00", "Operator Two"),
    )
    repository.rollback()

    count = repository.connection.execute(
        "SELECT COUNT(*) FROM communication_entries"
    ).fetchone()[0]

    assert count == 0


def test_close_releases_connection() -> None:
    repository = EventLogRepository(SQLiteAdapter(":memory:"))

    repository.close()

    with pytest.raises(sqlite3.ProgrammingError):
        repository.connection.execute("SELECT 1")


def test_context_manager_rolls_back_on_exception() -> None:
    with pytest.raises(RuntimeError):
        with EventLogRepository(SQLiteAdapter(":memory:")) as repository:
            repository.begin_transaction()
            repository.connection.execute(
                """
                INSERT INTO communication_entries (message_content, logged_time, operator)
                VALUES (?, ?, ?)
                """,
                ("Temporary message", "2026-04-27T11:10:00", "Operator Three"),
            )
            raise RuntimeError("boom")

    with pytest.raises(sqlite3.ProgrammingError):
        repository.connection.execute("SELECT 1")


def test_repository_supports_file_backed_database_path(tmp_path: Path) -> None:
    database_path = tmp_path / "eventlog.db"

    repository = EventLogRepository(SQLiteAdapter(database_path))
    try:
        assert repository.database_path == str(database_path)
        assert _get_table_names(repository) == EXPECTED_TABLES
    finally:
        repository.close()






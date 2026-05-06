import sqlite3
from pathlib import Path

import pytest

from src.core.entries import CommunicationEntry
from src.db.database_adapter import DatabaseAdapterError, DatabaseNewer, MigrationNeeded
from src.db.repositories.sqlite.event_log_repository import EventLogRepository
from src.db.sqlite_adapter import (
    SQLITE_APPLICATION_ID,
    SQLITE_USER_VERSION,
    SQLiteAdapter,
)


pytestmark = pytest.mark.unit

EXPECTED_TABLES = {
    "communication_entries",
    "communication_options",
    "communication_qualifiers_config",
    "communication_systems",
    "event_entries",
    "personnel_entries",
    "settings",
}

ENCRYPTION_KEY = bytes.fromhex(
    "00112233445566778899aabbccddeeff00112233445566778899aabbccddeeff"
)

def _get_table_names(repository: EventLogRepository) -> set[str]:
    rows = repository.connection.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
        """
    ).fetchall()
    return {row[0] for row in rows}


def _get_profile_metadata(connection: sqlite3.Connection) -> tuple[int, int]:
    application_id = connection.execute("PRAGMA application_id").fetchone()[0]
    user_version = connection.execute("PRAGMA user_version").fetchone()[0]
    return int(application_id), int(user_version)


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


def test_sqlite_adapter_reports_no_on_disk_cleanup_targets_for_memory_database() -> None:
    adapter = SQLiteAdapter(":memory:")
    try:
        assert adapter.get_cleanup_target_paths() == ()
    finally:
        adapter.close()


def test_sqlite_adapter_reports_existing_file_backed_cleanup_targets(tmp_path: Path) -> None:
    database_path = tmp_path / "eventlog.db"
    adapter = SQLiteAdapter(database_path)
    wal_path = Path(f"{database_path}-wal")
    journal_path = Path(f"{database_path}-journal")
    wal_path.write_text("wal", encoding="utf-8")
    journal_path.write_text("journal", encoding="utf-8")

    try:
        assert adapter.get_cleanup_target_paths() == (
            database_path,
            wal_path,
            journal_path,
        )
    finally:
        adapter.close()


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
        assert _get_profile_metadata(repository.connection) == (
            SQLITE_APPLICATION_ID,
            SQLITE_USER_VERSION,
        )
    finally:
        repository.close()


def test_sqlite_adapter_rejects_existing_plaintext_database_without_eventlog_profile_metadata(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "existing-plain.db"
    sqlite3.connect(database_path).close()

    with pytest.raises(DatabaseAdapterError, match="application_id"):
        SQLiteAdapter(database_path)


def test_sqlite_adapter_raises_migration_needed_for_existing_plaintext_database_with_older_user_version(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "older-version.db"
    connection = sqlite3.connect(database_path)
    try:
        connection.execute(f"PRAGMA application_id = {SQLITE_APPLICATION_ID}")
        connection.execute(f"PRAGMA user_version = {SQLITE_USER_VERSION - 1}")
        connection.commit()
    finally:
        connection.close()

    with pytest.raises(MigrationNeeded, match="requires migration"):
        SQLiteAdapter(database_path)


def test_sqlite_adapter_raises_database_newer_for_existing_plaintext_database_with_future_user_version(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "future-version.db"
    connection = sqlite3.connect(database_path)
    try:
        connection.execute(f"PRAGMA application_id = {SQLITE_APPLICATION_ID}")
        connection.execute(f"PRAGMA user_version = {SQLITE_USER_VERSION + 1}")
        connection.commit()
    finally:
        connection.close()

    with pytest.raises(DatabaseNewer, match="has newer user_version"):
        SQLiteAdapter(database_path)


def test_repository_supports_encrypted_file_backed_database_path(tmp_path: Path) -> None:
    database_path = tmp_path / "eventlog-encrypted.db"

    repository = EventLogRepository(SQLiteAdapter(database_path, encryption_key=ENCRYPTION_KEY))
    try:
        assert repository.database_path == str(database_path)
        assert _get_table_names(repository) == EXPECTED_TABLES

        entry_id = repository.create_communication_entry(
            CommunicationEntry(
                message_content="Encrypted repository message",
                operator="Operator Secure",
            )
        )
    finally:
        repository.close()

    reopened = EventLogRepository(SQLiteAdapter(database_path, encryption_key=ENCRYPTION_KEY))
    try:
        assert reopened.database_path == str(database_path)
        assert _get_table_names(reopened) == EXPECTED_TABLES

        loaded = reopened.get_communication_entry(entry_id)

        assert loaded is not None
        assert loaded.message_content == "Encrypted repository message"
        assert loaded.operator == "Operator Secure"
    finally:
        reopened.close()


def test_encrypted_repository_context_manager_rolls_back_on_exception(tmp_path: Path) -> None:
    database_path = tmp_path / "eventlog-encrypted-rollback.db"

    with pytest.raises(RuntimeError):
        with EventLogRepository(SQLiteAdapter(database_path, encryption_key=ENCRYPTION_KEY)) as repository:
            repository.begin_transaction()
            repository.connection.execute(
                """
                INSERT INTO communication_entries (message_content, logged_time, operator)
                VALUES (?, ?, ?)
                """,
                ("Encrypted temporary message", "2026-05-01T09:00:00", "Operator Four"),
            )
            raise RuntimeError("boom")

    reopened = EventLogRepository(SQLiteAdapter(database_path, encryption_key=ENCRYPTION_KEY))
    try:
        count = reopened.connection.execute(
            "SELECT COUNT(*) FROM communication_entries"
        ).fetchone()[0]

        assert count == 0
    finally:
        reopened.close()






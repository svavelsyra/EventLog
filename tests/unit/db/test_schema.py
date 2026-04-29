import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from src.db.schema.schema_executor import execute_schema_file


pytestmark = pytest.mark.unit

SCHEMA_FILE = (
    Path(__file__).resolve().parents[3]
    / "src"
    / "db"
    / "schema"
    / "sqlite"
    / "initial_schema.sql"
)

EXPECTED_TABLES = {
    "communication_entries",
    "event_entries",
    "personnel_entries",
    "settings",
}

EXPECTED_INDEXES = {
    "idx_comm_event_time",
    "idx_comm_logged_time",
    "idx_comm_operator",
    "idx_comm_system",
    "idx_comm_method_type",
    "idx_event_event_time",
    "idx_event_logged_time",
    "idx_event_operator",
    "idx_event_priority",
    "idx_event_category",
    "idx_personnel_who",
    "idx_personnel_active",
    "idx_personnel_logged_time",
    "idx_personnel_last_contact",
    "idx_personnel_alarm",
}


@pytest.fixture
def connection() -> Iterator[sqlite3.Connection]:
    database_connection = sqlite3.connect(":memory:")
    try:
        yield database_connection
    finally:
        database_connection.close()


@pytest.fixture
def initialized_connection(connection: sqlite3.Connection) -> sqlite3.Connection:
    execute_schema_file(connection, SCHEMA_FILE)
    return connection


def _get_schema_object_names(connection: sqlite3.Connection, object_type: str) -> set[str]:
    rows = connection.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = ? AND name NOT LIKE 'sqlite_%'
        """,
        (object_type,),
    ).fetchall()
    return {row[0] for row in rows}


def test_execute_schema_file_creates_expected_tables_and_indexes(
    connection: sqlite3.Connection,
) -> None:
    execute_schema_file(connection, SCHEMA_FILE)

    assert _get_schema_object_names(connection, "table") == EXPECTED_TABLES
    assert _get_schema_object_names(connection, "index") == EXPECTED_INDEXES


def test_execute_schema_file_is_idempotent(connection: sqlite3.Connection) -> None:
    execute_schema_file(connection, SCHEMA_FILE)
    execute_schema_file(connection, SCHEMA_FILE)

    assert _get_schema_object_names(connection, "table") == EXPECTED_TABLES
    assert _get_schema_object_names(connection, "index") == EXPECTED_INDEXES


def test_schema_applies_default_values(initialized_connection: sqlite3.Connection) -> None:
    initialized_connection.execute(
        """
        INSERT INTO communication_entries (message_content, logged_time, operator)
        VALUES (?, ?, ?)
        """,
        ("Radio check complete", "2026-04-27T10:00:00", "Operator One"),
    )
    initialized_connection.execute(
        """
        INSERT INTO event_entries (event_description, logged_time, operator)
        VALUES (?, ?, ?)
        """,
        ("Observation logged", "2026-04-27T10:05:00", "Operator Two"),
    )
    initialized_connection.execute(
        """
        INSERT INTO personnel_entries (who, logged_time, operator)
        VALUES (?, ?, ?)
        """,
        ("Alpha 1", "2026-04-27T10:10:00", "Operator Three"),
    )

    communication_row = initialized_connection.execute(
        "SELECT confirmed, edited FROM communication_entries"
    ).fetchone()
    event_row = initialized_connection.execute(
        "SELECT priority, edited FROM event_entries"
    ).fetchone()
    personnel_row = initialized_connection.execute(
        "SELECT edited, active, alarm_enabled, alarm_triggered FROM personnel_entries"
    ).fetchone()
    settings_row = initialized_connection.execute(
        "SELECT value FROM settings WHERE key = ?",
        ("edited_flag_grace_period_seconds",),
    ).fetchone()

    assert communication_row == (0, 0)
    assert event_row == ("Normal", 0)
    assert personnel_row == (0, 1, 0, 0)
    assert settings_row == ("300",)


@pytest.mark.parametrize(
    ("statement", "params"),
    [
        (
            """
            INSERT INTO communication_entries (message_content, logged_time, operator)
            VALUES (?, ?, ?)
            """,
            ("", "2026-04-27T10:00:00", "Operator One"),
        ),
        (
            """
            INSERT INTO event_entries (event_description, logged_time, operator)
            VALUES (?, ?, ?)
            """,
            ("", "2026-04-27T10:05:00", "Operator Two"),
        ),
        (
            """
            INSERT INTO personnel_entries (who, logged_time, operator)
            VALUES (?, ?, ?)
            """,
            ("", "2026-04-27T10:10:00", "Operator Three"),
        ),
    ],
)
def test_schema_rejects_empty_required_text_fields(
    initialized_connection: sqlite3.Connection,
    statement: str,
    params: tuple[str, str, str],
) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        initialized_connection.execute(statement, params)


@pytest.mark.parametrize(
    ("statement", "params"),
    [
        (
            """
            INSERT INTO communication_entries (
                message_content,
                logged_time,
                operator,
                confirmed
            )
            VALUES (?, ?, ?, ?)
            """,
            ("Message", "2026-04-27T10:00:00", "Operator One", 2),
        ),
        (
            """
            INSERT INTO event_entries (
                event_description,
                logged_time,
                operator,
                edited
            )
            VALUES (?, ?, ?, ?)
            """,
            ("Event", "2026-04-27T10:05:00", "Operator Two", 7),
        ),
        (
            """
            INSERT INTO personnel_entries (
                who,
                logged_time,
                operator,
                active
            )
            VALUES (?, ?, ?, ?)
            """,
            ("Alpha 1", "2026-04-27T10:10:00", "Operator Three", 4),
        ),
    ],
)
def test_schema_rejects_invalid_boolean_values(
    initialized_connection: sqlite3.Connection,
    statement: str,
    params: tuple[object, ...],
) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        initialized_connection.execute(statement, params)


def test_personnel_alarm_requires_expected_checkin_time(
    initialized_connection: sqlite3.Connection,
) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        initialized_connection.execute(
            """
            INSERT INTO personnel_entries (
                who,
                logged_time,
                operator,
                alarm_enabled
            )
            VALUES (?, ?, ?, ?)
            """,
            ("Alpha 1", "2026-04-27T10:10:00", "Operator Three", 1),
        )



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
    "communication_options",
    "communication_qualifiers_config",
    "communication_systems",
    "event_entries",
    "personnel_entries",
    "settings",
    "user_preferences",
}

EXPECTED_INDEXES = {
    "idx_comm_event_time",
    "idx_comm_logged_time",
    "idx_comm_operator",
    "idx_comm_option_active",
    "idx_comm_option_parent",
    "idx_comm_option_system",
    "idx_comm_qualifiers_system",
    "idx_comm_system",
    "idx_comm_systems_active",
    "idx_comm_systems_type",
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
    "uq_comm_option_unique_path",
    "uq_comm_qualifiers_system_key",
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


def _get_table_row_count(connection: sqlite3.Connection, table_name: str) -> int:
    row = connection.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()
    assert row is not None
    return int(row[0])


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
    assert _get_table_row_count(connection, "settings") == 1
    assert _get_table_row_count(connection, "user_preferences") == 0
    assert _get_table_row_count(connection, "communication_systems") == 5
    assert _get_table_row_count(connection, "communication_options") == 21
    assert _get_table_row_count(connection, "communication_qualifiers_config") == 6


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


def test_schema_seeds_operational_configuration_defaults(
    initialized_connection: sqlite3.Connection,
) -> None:
    system_rows = initialized_connection.execute(
        """
        SELECT system_name, system_type, child_label, sort_order, is_active
        FROM communication_systems
        ORDER BY sort_order, system_name
        """
    ).fetchall()
    option_rows = initialized_connection.execute(
        """
        SELECT cs.system_name, co.option_value, co.option_label, co.sort_order, co.is_active
        FROM communication_options AS co
        JOIN communication_systems AS cs
            ON cs.id = co.communication_system_id
        ORDER BY cs.sort_order, co.sort_order, co.option_value
        """
    ).fetchall()
    qualifier_rows = initialized_connection.execute(
        """
        SELECT cs.system_name, cqc.qualifier_key, cqc.label, cqc.field_type, cqc.default_value, cqc.visibility_mode
        FROM communication_qualifiers_config AS cqc
        JOIN communication_systems AS cs
            ON cs.id = cqc.communication_system_id
        ORDER BY cs.sort_order, cqc.qualifier_key
        """
    ).fetchall()

    assert system_rows == [
        ("RA180", "Radio System", "Kanal", 10, 1),
        ("Motorola", "Radio System", "Kanal", 20, 1),
        ("Rakel", "Radio System", "Talgrupp", 30, 1),
        ("Kurir", "Kurir", "Skydd", 40, 1),
        ("Telefon", "Telefon", None, 50, 1),
    ]
    assert option_rows == [
        ("RA180", "1", "Kanal 1", 10, 1),
        ("RA180", "2", "Kanal 2", 20, 1),
        ("RA180", "3", "Kanal 3", 30, 1),
        ("RA180", "4", "Kanal 4", 40, 1),
        ("RA180", "5", "Kanal 5", 50, 1),
        ("RA180", "6", "Kanal 6", 60, 1),
        ("RA180", "7", "Kanal 7", 70, 1),
        ("RA180", "8", "Kanal 8", 80, 1),
        ("Motorola", "1", "Kanal 1", 10, 1),
        ("Motorola", "2", "Kanal 2", 20, 1),
        ("Motorola", "3", "Kanal 3", 30, 1),
        ("Motorola", "4", "Kanal 4", 40, 1),
        ("Motorola", "5", "Kanal 5", 50, 1),
        ("Motorola", "6", "Kanal 6", 60, 1),
        ("Motorola", "7", "Kanal 7", 70, 1),
        ("Motorola", "8", "Kanal 8", 80, 1),
        ("Rakel", "BATALJON", "Bataljon", 10, 1),
        ("Rakel", "KOMPANI", "Kompani", 20, 1),
        ("Rakel", "ANDRA", "Andra", 30, 1),
        ("Kurir", "KLAR", "Klar", 10, 1),
        ("Kurir", "TTA", "TTA", 20, 1),
    ]
    assert qualifier_rows == [
        ("RA180", "data", "Data", "boolean", "true", "editable"),
        ("RA180", "encrypted", "Krypterad", "boolean", "true", "editable"),
        ("Motorola", "encrypted", "Krypterad", "boolean", "false", "forced"),
        ("Rakel", "encrypted", "Krypterad", "boolean", "true", "forced"),
        ("Telefon", "data", "Data", "boolean", "false", "editable"),
        ("Telefon", "encrypted", "Krypterad", "boolean", "false", "editable"),
    ]


def test_communication_entries_do_not_depend_on_live_config_foreign_keys(
    initialized_connection: sqlite3.Connection,
) -> None:
    foreign_key_rows = initialized_connection.execute(
        "PRAGMA foreign_key_list('communication_entries')"
    ).fetchall()

    assert {row[2] for row in foreign_key_rows} & {
        "communication_systems",
        "communication_options",
        "communication_qualifiers_config",
    } == set()


@pytest.mark.parametrize(
    ("statement", "params"),
    [
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


def test_schema_allows_blank_communication_message_and_operator_for_soft_save_flow(
    initialized_connection: sqlite3.Connection,
) -> None:
    initialized_connection.execute(
        """
        INSERT INTO communication_entries (message_content, logged_time, operator)
        VALUES (?, ?, ?)
        """,
        ("", "2026-04-27T10:00:00", ""),
    )


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



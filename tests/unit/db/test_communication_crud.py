import json
import sqlite3
from datetime import datetime, timedelta

import pytest

from src.core import CommunicationEntry
from src.db.repositories.sqlite.event_log_repository import EventLogRepository
from tests.unit.db.db_test_utils import (
    set_communication_logged_time,
    set_edit_grace_period_seconds,
)


pytestmark = pytest.mark.unit



def _get_communication_row(
    repository: EventLogRepository,
    entry_id: int,
) -> sqlite3.Row:
    row = repository.connection.execute(
        "SELECT * FROM communication_entries WHERE id = ?",
        (entry_id,),
    ).fetchone()
    assert row is not None
    return row


def _create_communication_entry(
    repository: EventLogRepository,
    **overrides: object,
) -> int:
    entry = CommunicationEntry(
        message_content="Test communication",
        operator="Default Operator",
        event_time=datetime(2026, 4, 27, 12, 0, 0),
        from_field="Alpha 1",
        to_field="HQ",
        communication_system="RA180",
        method_type="Radio",
    )

    for field_name, value in overrides.items():
        setattr(entry, field_name, value)

    return repository.create_communication_entry(entry)


def test_create_communication_entry_persists_all_fields_and_returns_id(
    repository: EventLogRepository,
) -> None:
    entry = CommunicationEntry(
        message_content="Relay sitrep to Bravo.",
        operator="Operator One",
        event_time=datetime(2026, 4, 27, 12, 30, 0),
        from_field="Alpha 1",
        to_field="Bravo 2",
        confirmed=True,
        edited=True,
        communication_system="RA180",
        method_type="Radio",
        method_channel="3",
        channel_designation="Command Net",
        system_capabilities={"encryption": True, "mode": "voice"},
    )

    before_create = datetime.now()
    entry_id = repository.create_communication_entry(entry)
    after_create = datetime.now()

    row = _get_communication_row(repository, entry_id)
    logged_time = datetime.fromisoformat(row["logged_time"])

    assert entry_id == 1
    assert entry.id is None
    assert entry.logged_time is None
    assert row["message_content"] == entry.message_content
    assert row["operator"] == entry.operator
    assert row["event_time"] == entry.event_time.isoformat()
    assert row["from_field"] == entry.from_field
    assert row["to_field"] == entry.to_field
    assert row["confirmed"] == 1
    assert row["edited"] == 1
    assert row["communication_system"] == entry.communication_system
    assert row["method_type"] == entry.method_type
    assert row["method_channel"] == entry.method_channel
    assert row["channel_designation"] == entry.channel_designation
    assert json.loads(row["system_capabilities"]) == entry.system_capabilities
    assert before_create <= logged_time <= after_create


def test_row_to_communication_entry_converts_storage_types_and_nulls(
    repository: EventLogRepository,
) -> None:
    cursor = repository.connection.execute(
        """
        INSERT INTO communication_entries (
            event_time,
            logged_time,
            message_content,
            from_field,
            to_field,
            operator,
            confirmed,
            edited,
            communication_system,
            method_type,
            method_channel,
            channel_designation,
            system_capabilities
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "2026-04-27T13:00:00",
            "2026-04-27T13:01:00",
            "Inbound report received.",
            None,
            "HQ",
            "Operator Two",
            1,
            0,
            "RA146",
            "Phone",
            None,
            None,
            '{"link": true, "priority": "high"}',
        ),
    )
    repository.connection.commit()

    row = _get_communication_row(repository, int(cursor.lastrowid))
    entry = repository._row_to_communication_entry(row)

    assert entry.id == cursor.lastrowid
    assert entry.message_content == "Inbound report received."
    assert entry.operator == "Operator Two"
    assert entry.event_time == datetime(2026, 4, 27, 13, 0, 0)
    assert entry.logged_time == datetime(2026, 4, 27, 13, 1, 0)
    assert entry.from_field is None
    assert entry.to_field == "HQ"
    assert entry.confirmed is True
    assert entry.edited is False
    assert entry.communication_system == "RA146"
    assert entry.method_type == "Phone"
    assert entry.method_channel is None
    assert entry.channel_designation is None
    assert entry.system_capabilities == {"link": True, "priority": "high"}


def test_create_communication_entry_supports_minimal_fields_round_trip(
    repository: EventLogRepository,
) -> None:
    entry_id = repository.create_communication_entry(
        CommunicationEntry(
            message_content="Radio check complete.",
            operator="Operator Three",
        )
    )

    row = _get_communication_row(repository, entry_id)
    entry = repository._row_to_communication_entry(row)

    assert entry.id == entry_id
    assert entry.message_content == "Radio check complete."
    assert entry.operator == "Operator Three"
    assert entry.event_time is None
    assert entry.logged_time is not None
    assert entry.from_field is None
    assert entry.to_field is None
    assert entry.confirmed is False
    assert entry.edited is False
    assert entry.communication_system is None
    assert entry.method_type is None
    assert entry.method_channel is None
    assert entry.channel_designation is None
    assert entry.system_capabilities is None


def test_create_communication_entry_does_not_commit_explicit_transaction(
    repository: EventLogRepository,
) -> None:
    repository.begin_transaction()

    entry_id = repository.create_communication_entry(
        CommunicationEntry(
            message_content="Hold position.",
            operator="Operator Four",
        )
    )

    count_before_rollback = repository.connection.execute(
        "SELECT COUNT(*) FROM communication_entries"
    ).fetchone()[0]
    repository.rollback()
    count_after_rollback = repository.connection.execute(
        "SELECT COUNT(*) FROM communication_entries"
    ).fetchone()[0]

    assert entry_id == 1
    assert count_before_rollback == 1
    assert count_after_rollback == 0


def test_get_communication_entry_returns_entry_by_id(
    repository: EventLogRepository,
) -> None:
    entry_id = _create_communication_entry(
        repository,
        message_content="Retrieve this message.",
        operator="Operator Retrieve",
        event_time=datetime(2026, 4, 27, 14, 0, 0),
    )

    entry = repository.get_communication_entry(entry_id)

    assert entry is not None
    assert entry.id == entry_id
    assert entry.message_content == "Retrieve this message."
    assert entry.operator == "Operator Retrieve"
    assert entry.event_time == datetime(2026, 4, 27, 14, 0, 0)


def test_get_communication_entry_returns_none_for_missing_id(
    repository: EventLogRepository,
) -> None:
    assert repository.get_communication_entry(999) is None


def test_get_all_communication_entries_returns_all_entries_sorted_by_event_time_desc(
    repository: EventLogRepository,
) -> None:
    oldest_id = _create_communication_entry(
        repository,
        message_content="Oldest message",
        event_time=datetime(2026, 4, 27, 8, 0, 0),
    )
    newest_id = _create_communication_entry(
        repository,
        message_content="Newest message",
        event_time=datetime(2026, 4, 27, 16, 0, 0),
    )
    middle_id = _create_communication_entry(
        repository,
        message_content="Middle message",
        event_time=datetime(2026, 4, 27, 12, 0, 0),
    )

    entries = repository.get_all_communication_entries()

    assert [entry.id for entry in entries] == [newest_id, middle_id, oldest_id]


@pytest.mark.parametrize(
    ("filters", "expected_message"),
    [
        ({"operator": "Operator Alpha"}, "Operator filtered message"),
        ({"communication_system": "RA146"}, "System filtered message"),
        ({"method_type": "Phone"}, "Method filtered message"),
        ({"from_field": "Bravo 2"}, "From filtered message"),
        ({"to_field": "Charlie 3"}, "To filtered message"),
        ({"participants": "Delta 4"}, "Participant filtered message"),
    ],
)
def test_get_all_communication_entries_supports_individual_filters(
    repository: EventLogRepository,
    filters: dict[str, str],
    expected_message: str,
) -> None:
    _create_communication_entry(
        repository,
        message_content="Operator filtered message",
        operator="Operator Alpha",
    )
    _create_communication_entry(
        repository,
        message_content="System filtered message",
        communication_system="RA146",
    )
    _create_communication_entry(
        repository,
        message_content="Method filtered message",
        method_type="Phone",
    )
    _create_communication_entry(
        repository,
        message_content="From filtered message",
        from_field="Bravo 2",
    )
    _create_communication_entry(
        repository,
        message_content="To filtered message",
        to_field="Charlie 3",
    )
    _create_communication_entry(
        repository,
        message_content="Participant filtered message",
        from_field="Delta 4",
        to_field="Echo 5",
    )
    _create_communication_entry(
        repository,
        message_content="Non matching message",
        operator="Operator Zulu",
        communication_system="Email",
        method_type="Data",
        from_field="Foxtrot 6",
        to_field="Golf 7",
    )

    entries = repository.get_all_communication_entries(filters)

    assert [entry.message_content for entry in entries] == [expected_message]


@pytest.mark.parametrize(
    ("filters", "expected_messages"),
    [
        (
            {"date_from": datetime(2026, 4, 27, 10, 0, 0)},
            ["Late message", "Mid message"],
        ),
        (
            {"date_to": datetime(2026, 4, 27, 10, 0, 0)},
            ["Mid message", "Early message"],
        ),
    ],
)
def test_get_all_communication_entries_supports_date_range_filters(
    repository: EventLogRepository,
    filters: dict[str, datetime],
    expected_messages: list[str],
) -> None:
    _create_communication_entry(
        repository,
        message_content="Early message",
        event_time=datetime(2026, 4, 27, 8, 0, 0),
    )
    _create_communication_entry(
        repository,
        message_content="Mid message",
        event_time=datetime(2026, 4, 27, 10, 0, 0),
    )
    _create_communication_entry(
        repository,
        message_content="Late message",
        event_time=datetime(2026, 4, 27, 12, 0, 0),
    )

    entries = repository.get_all_communication_entries(filters)

    assert [entry.message_content for entry in entries] == expected_messages


def test_get_all_communication_entries_combines_filters_with_and_logic(
    repository: EventLogRepository,
) -> None:
    _create_communication_entry(
        repository,
        message_content="Matching entry",
        operator="Operator Match",
        communication_system="RA180",
        method_type="Radio",
        from_field="Alpha 1",
        to_field="HQ",
        event_time=datetime(2026, 4, 27, 11, 0, 0),
    )
    _create_communication_entry(
        repository,
        message_content="Wrong operator",
        operator="Operator Other",
        communication_system="RA180",
        method_type="Radio",
        from_field="Alpha 1",
        to_field="HQ",
        event_time=datetime(2026, 4, 27, 11, 0, 0),
    )
    _create_communication_entry(
        repository,
        message_content="Wrong date",
        operator="Operator Match",
        communication_system="RA180",
        method_type="Radio",
        from_field="Alpha 1",
        to_field="HQ",
        event_time=datetime(2026, 4, 27, 7, 0, 0),
    )

    entries = repository.get_all_communication_entries(
        {
            "operator": "Operator Match",
            "communication_system": "RA180",
            "method_type": "Radio",
            "participants": "Alpha 1",
            "date_from": datetime(2026, 4, 27, 10, 0, 0),
        }
    )

    assert [entry.message_content for entry in entries] == ["Matching entry"]


def test_get_all_communication_entries_returns_empty_list_when_no_matches(
    repository: EventLogRepository,
) -> None:
    _create_communication_entry(repository, message_content="Existing message")

    entries = repository.get_all_communication_entries({"operator": "Missing Operator"})

    assert entries == []


def test_update_communication_entry_uses_configured_grace_period_seconds(
    repository: EventLogRepository,
) -> None:
    entry_id = _create_communication_entry(
        repository,
        message_content="Original message",
        operator="Original Operator",
        event_time=datetime(2026, 4, 27, 9, 0, 0),
    )
    original_entry = repository.get_communication_entry(entry_id)
    assert original_entry is not None
    assert original_entry.logged_time is not None

    set_edit_grace_period_seconds(repository, 60)

    old_logged_time = datetime.now() - timedelta(seconds=61)
    set_communication_logged_time(repository, entry_id, old_logged_time)

    updated = repository.update_communication_entry(
        CommunicationEntry(
            id=entry_id,
            message_content="Updated message",
            operator="Updated Operator",
            event_time=datetime(2026, 4, 27, 10, 30, 0),
            from_field="Bravo 2",
            to_field="Charlie 3",
            confirmed=True,
            edited=False,
            communication_system="RA146",
            method_type="Phone",
            method_channel="7",
            channel_designation="Ops Net",
            system_capabilities={"relay": True},
        )
    )

    reloaded_entry = repository.get_communication_entry(entry_id)

    assert updated is True
    assert reloaded_entry is not None
    assert reloaded_entry.message_content == "Updated message"
    assert reloaded_entry.operator == "Updated Operator"
    assert reloaded_entry.event_time == datetime(2026, 4, 27, 10, 30, 0)
    assert reloaded_entry.from_field == "Bravo 2"
    assert reloaded_entry.to_field == "Charlie 3"
    assert reloaded_entry.confirmed is True
    assert reloaded_entry.edited is True
    assert reloaded_entry.communication_system == "RA146"
    assert reloaded_entry.method_type == "Phone"
    assert reloaded_entry.method_channel == "7"
    assert reloaded_entry.channel_designation == "Ops Net"
    assert reloaded_entry.system_capabilities == {"relay": True}
    assert reloaded_entry.logged_time == old_logged_time


def test_update_communication_entry_honors_immediate_correction_grace_period(
    repository: EventLogRepository,
) -> None:
    entry_id = _create_communication_entry(repository, message_content="Fresh message")

    updated = repository.update_communication_entry(
        CommunicationEntry(
            id=entry_id,
            message_content="Fresh correction",
            operator="Default Operator",
            event_time=datetime(2026, 4, 27, 12, 0, 0),
            from_field="Alpha 1",
            to_field="HQ",
            confirmed=False,
            edited=True,
            communication_system="RA180",
            method_type="Radio",
            method_channel=None,
            channel_designation=None,
            system_capabilities=None,
        )
    )

    reloaded_entry = repository.get_communication_entry(entry_id)

    assert updated is True
    assert reloaded_entry is not None
    assert reloaded_entry.message_content == "Fresh correction"
    assert reloaded_entry.edited is False


def test_update_communication_entry_returns_false_when_entry_is_missing_or_unsaved(
    repository: EventLogRepository,
) -> None:
    missing_id_result = repository.update_communication_entry(
        CommunicationEntry(
            id=999,
            message_content="Missing",
            operator="Operator Missing",
        )
    )
    unsaved_result = repository.update_communication_entry(
        CommunicationEntry(
            message_content="Unsaved",
            operator="Operator Unsaved",
        )
    )

    assert missing_id_result is False
    assert unsaved_result is False


def test_delete_communication_entry_removes_entry_and_preserves_other_rows(
    repository: EventLogRepository,
) -> None:
    deleted_id = _create_communication_entry(repository, message_content="Delete me")
    kept_id = _create_communication_entry(repository, message_content="Keep me")

    deleted = repository.delete_communication_entry(deleted_id)

    assert deleted is True
    assert repository.get_communication_entry(deleted_id) is None
    kept_entry = repository.get_communication_entry(kept_id)
    assert kept_entry is not None
    assert kept_entry.message_content == "Keep me"


def test_delete_communication_entry_returns_false_for_missing_id(
    repository: EventLogRepository,
) -> None:
    assert repository.delete_communication_entry(999) is False


def test_search_communication_entries_finds_case_insensitive_substring_matches(
    repository: EventLogRepository,
) -> None:
    newest_id = _create_communication_entry(
        repository,
        message_content="hello from Bravo",
        event_time=datetime(2026, 4, 27, 15, 0, 0),
    )
    older_id = _create_communication_entry(
        repository,
        message_content="Report says HELLO again",
        event_time=datetime(2026, 4, 27, 9, 0, 0),
    )
    _create_communication_entry(repository, message_content="No match here")

    entries = repository.search_communication_entries("hello")

    assert [entry.id for entry in entries] == [newest_id, older_id]


def test_search_communication_entries_combines_text_and_filters(
    repository: EventLogRepository,
) -> None:
    _create_communication_entry(
        repository,
        message_content="Urgent resupply needed",
        operator="Operator Match",
        event_time=datetime(2026, 4, 27, 13, 0, 0),
    )
    _create_communication_entry(
        repository,
        message_content="Urgent route update",
        operator="Operator Other",
        event_time=datetime(2026, 4, 27, 14, 0, 0),
    )
    _create_communication_entry(
        repository,
        message_content="Routine resupply complete",
        operator="Operator Match",
        event_time=datetime(2026, 4, 27, 15, 0, 0),
    )

    entries = repository.search_communication_entries(
        "urgent",
        {"operator": "Operator Match"},
    )

    assert [entry.message_content for entry in entries] == ["Urgent resupply needed"]


def test_search_communication_entries_returns_empty_list_when_no_matches(
    repository: EventLogRepository,
) -> None:
    _create_communication_entry(repository, message_content="Existing communication")

    entries = repository.search_communication_entries("nonexistent")

    assert entries == []



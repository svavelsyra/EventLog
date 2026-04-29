from datetime import datetime, timedelta
import sqlite3

import pytest

from src.core import EventEntry
from src.db.repositories.sqlite.event_log_repository import EventLogRepository
from tests.unit.db.db_test_utils import set_edit_grace_period_seconds, set_event_logged_time


pytestmark = pytest.mark.unit



def _get_event_row(
    repository: EventLogRepository,
    entry_id: int,
) -> sqlite3.Row:
    row = repository.connection.execute(
        "SELECT * FROM event_entries WHERE id = ?",
        (entry_id,),
    ).fetchone()
    assert row is not None
    return row


def _create_event_entry(
    repository: EventLogRepository,
    **overrides: object,
) -> int:
    entry = EventEntry(
        event_description="Test event",
        operator="Default Operator",
        whom="Alpha 1",
        event_time=datetime(2026, 4, 27, 12, 0, 0),
        priority="Normal",
        category="Observation",
    )

    for field_name, value in overrides.items():
        setattr(entry, field_name, value)

    return repository.create_event_entry(entry)


def test_create_event_entry_persists_all_fields_and_returns_id(
    repository: EventLogRepository,
) -> None:
    entry = EventEntry(
        event_description="Enemy movement observed near bridge.",
        operator="Operator One",
        whom="Recon Team",
        event_time=datetime(2026, 4, 27, 12, 30, 0),
        priority="High",
        category="Observation",
        edited=True,
    )

    before_create = datetime.now()
    entry_id = repository.create_event_entry(entry)
    after_create = datetime.now()

    row = _get_event_row(repository, entry_id)
    logged_time = datetime.fromisoformat(row["logged_time"])

    assert entry_id == 1
    assert entry.id is None
    assert entry.logged_time is None
    assert row["event_description"] == entry.event_description
    assert row["operator"] == entry.operator
    assert row["whom"] == entry.whom
    assert row["event_time"] == entry.event_time.isoformat()
    assert row["priority"] == entry.priority
    assert row["category"] == entry.category
    assert row["edited"] == 1
    assert before_create <= logged_time <= after_create


def test_row_to_event_entry_converts_storage_types_and_nulls(
    repository: EventLogRepository,
) -> None:
    cursor = repository.connection.execute(
        """
        INSERT INTO event_entries (
            event_description,
            whom,
            event_time,
            logged_time,
            operator,
            priority,
            category,
            edited
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "Bridge secured.",
            None,
            None,
            "2026-04-27T13:01:00",
            "Operator Two",
            "Critical",
            None,
            1,
        ),
    )
    repository.connection.commit()

    row = _get_event_row(repository, int(cursor.lastrowid))
    entry = repository._row_to_event_entry(row)

    assert entry.id == cursor.lastrowid
    assert entry.event_description == "Bridge secured."
    assert entry.operator == "Operator Two"
    assert entry.whom is None
    assert entry.event_time is None
    assert entry.logged_time == datetime(2026, 4, 27, 13, 1, 0)
    assert entry.priority == "Critical"
    assert entry.category is None
    assert entry.edited is True


def test_create_event_entry_supports_minimal_fields_round_trip_and_priority_default(
    repository: EventLogRepository,
) -> None:
    entry_id = repository.create_event_entry(
        EventEntry(
            event_description="Routine patrol departed.",
            operator="Operator Three",
            priority=None,
        )
    )

    row = _get_event_row(repository, entry_id)
    entry = repository._row_to_event_entry(row)

    assert row["priority"] == "Normal"
    assert entry.id == entry_id
    assert entry.event_description == "Routine patrol departed."
    assert entry.operator == "Operator Three"
    assert entry.whom is None
    assert entry.event_time is None
    assert entry.logged_time is not None
    assert entry.priority == "Normal"
    assert entry.category is None
    assert entry.edited is False


def test_create_event_entry_does_not_commit_explicit_transaction(
    repository: EventLogRepository,
) -> None:
    repository.begin_transaction()

    entry_id = repository.create_event_entry(
        EventEntry(
            event_description="Temporary event.",
            operator="Operator Four",
        )
    )

    count_before_rollback = repository.connection.execute(
        "SELECT COUNT(*) FROM event_entries"
    ).fetchone()[0]
    repository.rollback()
    count_after_rollback = repository.connection.execute(
        "SELECT COUNT(*) FROM event_entries"
    ).fetchone()[0]

    assert entry_id == 1
    assert count_before_rollback == 1
    assert count_after_rollback == 0


def test_get_event_entry_returns_entry_by_id(
    repository: EventLogRepository,
) -> None:
    entry_id = _create_event_entry(
        repository,
        event_description="Retrieve this event.",
        operator="Operator Retrieve",
        event_time=datetime(2026, 4, 27, 14, 0, 0),
    )

    entry = repository.get_event_entry(entry_id)

    assert entry is not None
    assert entry.id == entry_id
    assert entry.event_description == "Retrieve this event."
    assert entry.operator == "Operator Retrieve"
    assert entry.event_time == datetime(2026, 4, 27, 14, 0, 0)


def test_get_event_entry_returns_none_for_missing_id(
    repository: EventLogRepository,
) -> None:
    assert repository.get_event_entry(999) is None


def test_get_all_event_entries_returns_all_entries_sorted_by_event_time_desc(
    repository: EventLogRepository,
) -> None:
    oldest_id = _create_event_entry(
        repository,
        event_description="Oldest event",
        event_time=datetime(2026, 4, 27, 8, 0, 0),
    )
    newest_id = _create_event_entry(
        repository,
        event_description="Newest event",
        event_time=datetime(2026, 4, 27, 16, 0, 0),
    )
    middle_id = _create_event_entry(
        repository,
        event_description="Middle event",
        event_time=datetime(2026, 4, 27, 12, 0, 0),
    )

    entries = repository.get_all_event_entries()

    assert [entry.id for entry in entries] == [newest_id, middle_id, oldest_id]


@pytest.mark.parametrize(
    ("filters", "expected_description"),
    [
        ({"operator": "Operator Alpha"}, "Operator filtered event"),
        ({"priority": "Critical"}, "Priority filtered event"),
        ({"category": "Kontakt"}, "Category filtered event"),
        ({"whom": "Bravo 2"}, "Whom filtered event"),
    ],
)
def test_get_all_event_entries_supports_individual_filters(
    repository: EventLogRepository,
    filters: dict[str, str],
    expected_description: str,
) -> None:
    _create_event_entry(
        repository,
        event_description="Operator filtered event",
        operator="Operator Alpha",
    )
    _create_event_entry(
        repository,
        event_description="Priority filtered event",
        priority="Critical",
    )
    _create_event_entry(
        repository,
        event_description="Category filtered event",
        category="Kontakt",
    )
    _create_event_entry(
        repository,
        event_description="Whom filtered event",
        whom="Bravo 2",
    )
    _create_event_entry(
        repository,
        event_description="Non matching event",
        operator="Operator Zulu",
        priority="Low",
        category="Other",
        whom="Charlie 3",
    )

    entries = repository.get_all_event_entries(filters)

    assert [entry.event_description for entry in entries] == [expected_description]


@pytest.mark.parametrize(
    ("filters", "expected_descriptions"),
    [
        (
            {"date_from": datetime(2026, 4, 27, 10, 0, 0)},
            ["Late event", "Mid event"],
        ),
        (
            {"date_to": datetime(2026, 4, 27, 10, 0, 0)},
            ["Mid event", "Early event"],
        ),
    ],
)
def test_get_all_event_entries_supports_date_range_filters(
    repository: EventLogRepository,
    filters: dict[str, datetime],
    expected_descriptions: list[str],
) -> None:
    _create_event_entry(
        repository,
        event_description="Early event",
        event_time=datetime(2026, 4, 27, 8, 0, 0),
    )
    _create_event_entry(
        repository,
        event_description="Mid event",
        event_time=datetime(2026, 4, 27, 10, 0, 0),
    )
    _create_event_entry(
        repository,
        event_description="Late event",
        event_time=datetime(2026, 4, 27, 12, 0, 0),
    )

    entries = repository.get_all_event_entries(filters)

    assert [entry.event_description for entry in entries] == expected_descriptions


def test_get_all_event_entries_combines_filters_with_and_logic(
    repository: EventLogRepository,
) -> None:
    _create_event_entry(
        repository,
        event_description="Matching event",
        operator="Operator Match",
        priority="Critical",
        category="Kontakt",
        whom="Alpha 1",
        event_time=datetime(2026, 4, 27, 11, 0, 0),
    )
    _create_event_entry(
        repository,
        event_description="Wrong operator",
        operator="Operator Other",
        priority="Critical",
        category="Kontakt",
        whom="Alpha 1",
        event_time=datetime(2026, 4, 27, 11, 0, 0),
    )
    _create_event_entry(
        repository,
        event_description="Wrong date",
        operator="Operator Match",
        priority="Critical",
        category="Kontakt",
        whom="Alpha 1",
        event_time=datetime(2026, 4, 27, 7, 0, 0),
    )

    entries = repository.get_all_event_entries(
        {
            "operator": "Operator Match",
            "priority": "Critical",
            "category": "Kontakt",
            "whom": "Alpha 1",
            "date_from": datetime(2026, 4, 27, 10, 0, 0),
        }
    )

    assert [entry.event_description for entry in entries] == ["Matching event"]


def test_get_all_event_entries_returns_empty_list_when_no_matches(
    repository: EventLogRepository,
) -> None:
    _create_event_entry(repository, event_description="Existing event")

    entries = repository.get_all_event_entries({"operator": "Missing Operator"})

    assert entries == []


def test_update_event_entry_changes_fields_preserves_logged_time_and_sets_edited_after_grace_period(
    repository: EventLogRepository,
) -> None:
    entry_id = _create_event_entry(
        repository,
        event_description="Original event",
        operator="Original Operator",
        whom="Alpha 1",
        event_time=datetime(2026, 4, 27, 9, 0, 0),
        priority="Normal",
        category="Observation",
    )
    original_entry = repository.get_event_entry(entry_id)
    assert original_entry is not None
    assert original_entry.logged_time is not None

    old_logged_time = datetime.now() - timedelta(minutes=6)
    set_event_logged_time(repository, entry_id, old_logged_time)

    updated = repository.update_event_entry(
        EventEntry(
            id=entry_id,
            event_description="Updated event",
            operator="Updated Operator",
            whom="Bravo 2",
            event_time=datetime(2026, 4, 27, 10, 30, 0),
            priority="Critical",
            category="Kontakt",
            edited=False,
        )
    )

    reloaded_entry = repository.get_event_entry(entry_id)

    assert updated is True
    assert reloaded_entry is not None
    assert reloaded_entry.event_description == "Updated event"
    assert reloaded_entry.operator == "Updated Operator"
    assert reloaded_entry.whom == "Bravo 2"
    assert reloaded_entry.event_time == datetime(2026, 4, 27, 10, 30, 0)
    assert reloaded_entry.priority == "Critical"
    assert reloaded_entry.category == "Kontakt"
    assert reloaded_entry.edited is True
    assert reloaded_entry.logged_time == old_logged_time


def test_update_event_entry_respects_longer_configured_grace_period(
    repository: EventLogRepository,
) -> None:
    entry_id = _create_event_entry(repository, event_description="Grace-period event")
    set_edit_grace_period_seconds(repository, 600)
    set_event_logged_time(repository, entry_id, datetime.now() - timedelta(seconds=360))

    updated = repository.update_event_entry(
        EventEntry(
            id=entry_id,
            event_description="Still within configured grace period",
            operator="Default Operator",
            whom="Alpha 1",
            event_time=datetime(2026, 4, 27, 12, 0, 0),
            priority="Normal",
            category="Observation",
            edited=True,
        )
    )

    reloaded_entry = repository.get_event_entry(entry_id)

    assert updated is True
    assert reloaded_entry is not None
    assert reloaded_entry.event_description == "Still within configured grace period"
    assert reloaded_entry.edited is False


def test_update_event_entry_honors_immediate_correction_grace_period(
    repository: EventLogRepository,
) -> None:
    entry_id = _create_event_entry(repository, event_description="Fresh event")

    updated = repository.update_event_entry(
        EventEntry(
            id=entry_id,
            event_description="Fresh correction",
            operator="Default Operator",
            whom="Alpha 1",
            event_time=datetime(2026, 4, 27, 12, 0, 0),
            priority=None,
            category=None,
            edited=True,
        )
    )

    reloaded_entry = repository.get_event_entry(entry_id)

    assert updated is True
    assert reloaded_entry is not None
    assert reloaded_entry.event_description == "Fresh correction"
    assert reloaded_entry.priority == "Normal"
    assert reloaded_entry.edited is False


def test_update_event_entry_returns_false_when_entry_is_missing_or_unsaved(
    repository: EventLogRepository,
) -> None:
    missing_id_result = repository.update_event_entry(
        EventEntry(
            id=999,
            event_description="Missing",
            operator="Operator Missing",
        )
    )
    unsaved_result = repository.update_event_entry(
        EventEntry(
            event_description="Unsaved",
            operator="Operator Unsaved",
        )
    )

    assert missing_id_result is False
    assert unsaved_result is False


def test_delete_event_entry_removes_entry_and_preserves_other_rows(
    repository: EventLogRepository,
) -> None:
    deleted_id = _create_event_entry(repository, event_description="Delete me")
    kept_id = _create_event_entry(repository, event_description="Keep me")

    deleted = repository.delete_event_entry(deleted_id)

    assert deleted is True
    assert repository.get_event_entry(deleted_id) is None
    kept_entry = repository.get_event_entry(kept_id)
    assert kept_entry is not None
    assert kept_entry.event_description == "Keep me"


def test_delete_event_entry_returns_false_for_missing_id(
    repository: EventLogRepository,
) -> None:
    assert repository.delete_event_entry(999) is False


def test_search_event_entries_finds_case_insensitive_substring_matches(
    repository: EventLogRepository,
) -> None:
    newest_id = _create_event_entry(
        repository,
        event_description="hello from Bravo",
        event_time=datetime(2026, 4, 27, 15, 0, 0),
    )
    older_id = _create_event_entry(
        repository,
        event_description="Report says HELLO again",
        event_time=datetime(2026, 4, 27, 9, 0, 0),
    )
    _create_event_entry(repository, event_description="No match here")

    entries = repository.search_event_entries("hello")

    assert [entry.id for entry in entries] == [newest_id, older_id]


def test_search_event_entries_combines_text_and_filters(
    repository: EventLogRepository,
) -> None:
    _create_event_entry(
        repository,
        event_description="Urgent bridge repair needed",
        operator="Operator Match",
        priority="Critical",
        event_time=datetime(2026, 4, 27, 13, 0, 0),
    )
    _create_event_entry(
        repository,
        event_description="Urgent route update",
        operator="Operator Other",
        priority="Critical",
        event_time=datetime(2026, 4, 27, 14, 0, 0),
    )
    _create_event_entry(
        repository,
        event_description="Routine bridge repair complete",
        operator="Operator Match",
        priority="Normal",
        event_time=datetime(2026, 4, 27, 15, 0, 0),
    )

    entries = repository.search_event_entries(
        "urgent",
        {"operator": "Operator Match", "priority": "Critical"},
    )

    assert len(entries) == 1
    assert entries[0].event_description == "Urgent bridge repair needed"


def test_search_event_entries_returns_empty_list_when_no_matches(
    repository: EventLogRepository,
) -> None:
    _create_event_entry(repository, event_description="Existing event")

    entries = repository.search_event_entries("nonexistent")

    assert entries == []



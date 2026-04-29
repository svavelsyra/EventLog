from datetime import datetime, timedelta
import sqlite3

import pytest

from src.core import PersonnelEntry
from src.db.repositories.sqlite.event_log_repository import EventLogRepository
from tests.unit.db.db_test_utils import freeze_repository_now, set_edit_grace_period_seconds


pytestmark = pytest.mark.unit



def _get_personnel_row(
    repository: EventLogRepository,
    entry_id: int,
) -> sqlite3.Row:
    row = repository.connection.execute(
        "SELECT * FROM personnel_entries WHERE id = ?",
        (entry_id,),
    ).fetchone()
    assert row is not None
    return row



def _set_personnel_logged_time(
    repository: EventLogRepository,
    entry_id: int,
    logged_time: datetime,
) -> None:
    repository.connection.execute(
        "UPDATE personnel_entries SET logged_time = ? WHERE id = ?",
        (logged_time.isoformat(), entry_id),
    )
    repository.connection.commit()



def _create_personnel_entry(
    repository: EventLogRepository,
    **overrides: object,
) -> int:
    entry = PersonnelEntry(
        who="Alpha 1",
        operator="Default Operator",
        status="On patrol",
        location="Grid A1",
        last_contact_time=datetime(2026, 4, 27, 12, 0, 0),
        mission_notes="Routine patrol.",
    )

    for field_name, value in overrides.items():
        setattr(entry, field_name, value)

    return repository.create_personnel_entry(entry)



def test_create_personnel_entry_persists_all_fields_and_returns_id(
    repository: EventLogRepository,
) -> None:
    entry = PersonnelEntry(
        who="Bravo 2",
        operator="Operator One",
        status="Holding position",
        location="Bridge North",
        last_contact_time=datetime(2026, 4, 27, 12, 30, 0),
        mission_notes="Awaiting extraction.",
        edited=True,
        active=False,
        supersedes="3,4",
        alarm_enabled=True,
        expected_checkin_time=datetime(2026, 4, 27, 14, 0, 0),
        alarm_triggered=True,
    )

    before_create = datetime.now()
    entry_id = repository.create_personnel_entry(entry)
    after_create = datetime.now()

    row = _get_personnel_row(repository, entry_id)
    logged_time = datetime.fromisoformat(row["logged_time"])

    assert entry_id == 1
    assert entry.id is None
    assert entry.logged_time is None
    assert row["who"] == entry.who
    assert row["operator"] == entry.operator
    assert row["status"] == entry.status
    assert row["location"] == entry.location
    assert row["last_contact_time"] == entry.last_contact_time.isoformat()
    assert row["mission_notes"] == entry.mission_notes
    assert row["edited"] == 1
    assert row["active"] == 0
    assert row["supersedes"] == entry.supersedes
    assert row["alarm_enabled"] == 1
    assert row["expected_checkin_time"] == entry.expected_checkin_time.isoformat()
    assert row["alarm_triggered"] == 1
    assert before_create <= logged_time <= after_create



def test_row_to_personnel_entry_converts_storage_types_and_nulls(
    repository: EventLogRepository,
) -> None:
    cursor = repository.connection.execute(
        """
        INSERT INTO personnel_entries (
            who,
            status,
            location,
            last_contact_time,
            mission_notes,
            logged_time,
            operator,
            edited,
            active,
            supersedes,
            alarm_enabled,
            expected_checkin_time,
            alarm_triggered
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "Charlie 3",
            None,
            None,
            None,
            None,
            "2026-04-27T13:01:00",
            "Operator Two",
            1,
            0,
            None,
            1,
            "2026-04-27T14:30:00",
            0,
        ),
    )
    repository.connection.commit()

    row = _get_personnel_row(repository, int(cursor.lastrowid))
    entry = repository._row_to_personnel_entry(row)

    assert entry.id == cursor.lastrowid
    assert entry.who == "Charlie 3"
    assert entry.operator == "Operator Two"
    assert entry.status is None
    assert entry.location is None
    assert entry.last_contact_time is None
    assert entry.mission_notes is None
    assert entry.logged_time == datetime(2026, 4, 27, 13, 1, 0)
    assert entry.edited is True
    assert entry.active is False
    assert entry.supersedes is None
    assert entry.alarm_enabled is True
    assert entry.expected_checkin_time == datetime(2026, 4, 27, 14, 30, 0)
    assert entry.alarm_triggered is False



def test_create_personnel_entry_supports_minimal_fields_round_trip_and_defaults(
    repository: EventLogRepository,
) -> None:
    entry_id = repository.create_personnel_entry(
        PersonnelEntry(
            who="Delta 4",
            operator="Operator Three",
        )
    )

    row = _get_personnel_row(repository, entry_id)
    entry = repository.get_personnel_entry(entry_id)

    assert entry is not None
    assert entry.id == entry_id
    assert entry.who == "Delta 4"
    assert entry.operator == "Operator Three"
    assert entry.status is None
    assert entry.location is None
    assert entry.mission_notes is None
    assert entry.logged_time is not None
    assert entry.last_contact_time == entry.logged_time
    assert row["last_contact_time"] == row["logged_time"]
    assert entry.edited is False
    assert entry.active is True
    assert entry.supersedes is None
    assert entry.alarm_enabled is False
    assert entry.expected_checkin_time is None
    assert entry.alarm_triggered is False



def test_create_personnel_entry_validates_alarm_fields(
    repository: EventLogRepository,
) -> None:
    with pytest.raises(ValueError, match="expected_checkin_time"):
        repository.create_personnel_entry(
            PersonnelEntry(
                who="Echo 5",
                operator="Operator Alarm",
                alarm_enabled=True,
            )
        )

    count = repository.connection.execute(
        "SELECT COUNT(*) FROM personnel_entries"
    ).fetchone()[0]
    assert count == 0



def test_create_personnel_entry_does_not_commit_explicit_transaction(
    repository: EventLogRepository,
) -> None:
    repository.begin_transaction()

    entry_id = repository.create_personnel_entry(
        PersonnelEntry(
            who="Foxtrot 6",
            operator="Operator Four",
        )
    )

    count_before_rollback = repository.connection.execute(
        "SELECT COUNT(*) FROM personnel_entries"
    ).fetchone()[0]
    repository.rollback()
    count_after_rollback = repository.connection.execute(
        "SELECT COUNT(*) FROM personnel_entries"
    ).fetchone()[0]

    assert entry_id == 1
    assert count_before_rollback == 1
    assert count_after_rollback == 0



def test_get_personnel_entry_returns_entry_by_id(
    repository: EventLogRepository,
) -> None:
    entry_id = _create_personnel_entry(
        repository,
        who="Golf 7",
        operator="Operator Retrieve",
        status="Returning",
    )

    entry = repository.get_personnel_entry(entry_id)

    assert entry is not None
    assert entry.id == entry_id
    assert entry.who == "Golf 7"
    assert entry.operator == "Operator Retrieve"
    assert entry.status == "Returning"



def test_get_personnel_entry_returns_none_for_missing_id(
    repository: EventLogRepository,
) -> None:
    assert repository.get_personnel_entry(999) is None



def test_get_all_personnel_entries_returns_all_entries_sorted_by_logged_time_desc(
    repository: EventLogRepository,
) -> None:
    oldest_id = _create_personnel_entry(repository, who="Oldest")
    middle_id = _create_personnel_entry(repository, who="Middle")
    newest_id = _create_personnel_entry(repository, who="Newest")

    _set_personnel_logged_time(repository, oldest_id, datetime(2026, 4, 27, 8, 0, 0))
    _set_personnel_logged_time(repository, middle_id, datetime(2026, 4, 27, 12, 0, 0))
    _set_personnel_logged_time(repository, newest_id, datetime(2026, 4, 27, 16, 0, 0))

    entries = repository.get_all_personnel_entries()

    assert [entry.id for entry in entries] == [newest_id, middle_id, oldest_id]


@pytest.mark.parametrize(
    ("filters", "expected_who"),
    [
        ({"who": "Match Who"}, "Match Who"),
        ({"operator": "Operator Match"}, "Match Operator"),
        ({"status": "Holding"}, "Match Status"),
        ({"location": "Bridge"}, "Match Location"),
        ({"active": 0}, "Match Inactive"),
        ({"alarm_enabled": 1}, "Match Alarm"),
    ],
)
def test_get_all_personnel_entries_supports_individual_filters(
    repository: EventLogRepository,
    filters: dict[str, object],
    expected_who: str,
) -> None:
    _create_personnel_entry(repository, who="Match Who")
    _create_personnel_entry(repository, who="Match Operator", operator="Operator Match")
    _create_personnel_entry(repository, who="Match Status", status="Holding")
    _create_personnel_entry(repository, who="Match Location", location="Bridge")
    _create_personnel_entry(repository, who="Match Inactive", active=False)
    _create_personnel_entry(
        repository,
        who="Match Alarm",
        alarm_enabled=True,
        expected_checkin_time=datetime(2026, 4, 27, 18, 0, 0),
    )
    _create_personnel_entry(
        repository,
        who="Non Match",
        operator="Operator Other",
        status="Moving",
        location="Hill",
        active=True,
        alarm_enabled=False,
    )

    entries = repository.get_all_personnel_entries(filters)

    assert [entry.who for entry in entries] == [expected_who]


@pytest.mark.parametrize(
    ("filters", "expected_who_values"),
    [
        (
            {"date_from": datetime(2026, 4, 27, 10, 0, 0)},
            ["Late", "Mid"],
        ),
        (
            {"date_to": datetime(2026, 4, 27, 10, 0, 0)},
            ["Mid", "Early"],
        ),
    ],
)
def test_get_all_personnel_entries_supports_logged_time_range_filters(
    repository: EventLogRepository,
    filters: dict[str, datetime],
    expected_who_values: list[str],
) -> None:
    early_id = _create_personnel_entry(repository, who="Early")
    mid_id = _create_personnel_entry(repository, who="Mid")
    late_id = _create_personnel_entry(repository, who="Late")

    _set_personnel_logged_time(repository, early_id, datetime(2026, 4, 27, 8, 0, 0))
    _set_personnel_logged_time(repository, mid_id, datetime(2026, 4, 27, 10, 0, 0))
    _set_personnel_logged_time(repository, late_id, datetime(2026, 4, 27, 12, 0, 0))

    entries = repository.get_all_personnel_entries(filters)

    assert [entry.who for entry in entries] == expected_who_values



def test_get_all_personnel_entries_combines_filters_with_and_logic(
    repository: EventLogRepository,
) -> None:
    matching_id = _create_personnel_entry(
        repository,
        who="Alpha Match",
        operator="Operator Match",
        active=False,
    )
    _set_personnel_logged_time(repository, matching_id, datetime(2026, 4, 27, 11, 0, 0))

    wrong_operator_id = _create_personnel_entry(
        repository,
        who="Alpha Match",
        operator="Operator Other",
        active=False,
    )
    _set_personnel_logged_time(repository, wrong_operator_id, datetime(2026, 4, 27, 11, 0, 0))

    wrong_date_id = _create_personnel_entry(
        repository,
        who="Alpha Match",
        operator="Operator Match",
        active=False,
    )
    _set_personnel_logged_time(repository, wrong_date_id, datetime(2026, 4, 27, 7, 0, 0))

    entries = repository.get_all_personnel_entries(
        {
            "who": "Alpha Match",
            "operator": "Operator Match",
            "active": 0,
            "date_from": datetime(2026, 4, 27, 10, 0, 0),
        }
    )

    assert [entry.id for entry in entries] == [matching_id]



def test_get_all_personnel_entries_returns_empty_list_when_no_matches(
    repository: EventLogRepository,
) -> None:
    _create_personnel_entry(repository, who="Existing")

    entries = repository.get_all_personnel_entries({"who": "Missing"})

    assert entries == []



def test_update_personnel_entry_changes_fields_preserves_logged_time_and_sets_edited_after_grace_period(
    repository: EventLogRepository,
) -> None:
    entry_id = _create_personnel_entry(
        repository,
        who="Update Target",
        operator="Original Operator",
        status="Original Status",
        location="Original Location",
        mission_notes="Original Notes",
        active=True,
        supersedes=None,
        alarm_enabled=False,
        alarm_triggered=False,
    )
    old_logged_time = datetime.now() - timedelta(minutes=6)
    _set_personnel_logged_time(repository, entry_id, old_logged_time)

    updated = repository.update_personnel_entry(
        PersonnelEntry(
            id=entry_id,
            who="Updated Target",
            operator="Updated Operator",
            status="Updated Status",
            location="Updated Location",
            last_contact_time=datetime(2026, 4, 27, 13, 15, 0),
            mission_notes="Updated Notes",
            edited=False,
            active=False,
            supersedes="1,2",
            alarm_enabled=True,
            expected_checkin_time=datetime(2026, 4, 27, 15, 0, 0),
            alarm_triggered=True,
        )
    )

    reloaded_entry = repository.get_personnel_entry(entry_id)

    assert updated is True
    assert reloaded_entry is not None
    assert reloaded_entry.who == "Updated Target"
    assert reloaded_entry.operator == "Updated Operator"
    assert reloaded_entry.status == "Updated Status"
    assert reloaded_entry.location == "Updated Location"
    assert reloaded_entry.last_contact_time == datetime(2026, 4, 27, 13, 15, 0)
    assert reloaded_entry.mission_notes == "Updated Notes"
    assert reloaded_entry.edited is True
    assert reloaded_entry.active is False
    assert reloaded_entry.supersedes == "1,2"
    assert reloaded_entry.alarm_enabled is True
    assert reloaded_entry.expected_checkin_time == datetime(2026, 4, 27, 15, 0, 0)
    assert reloaded_entry.alarm_triggered is True
    assert reloaded_entry.logged_time == old_logged_time



def test_update_personnel_entry_honors_immediate_correction_grace_period(
    repository: EventLogRepository,
) -> None:
    entry_id = _create_personnel_entry(repository, who="Fresh Personnel")

    updated = repository.update_personnel_entry(
        PersonnelEntry(
            id=entry_id,
            who="Fresh Personnel",
            operator="Default Operator",
            status="Corrected quickly",
            location="Grid B2",
            last_contact_time=datetime(2026, 4, 27, 12, 5, 0),
            mission_notes="Fast correction.",
        )
    )

    reloaded_entry = repository.get_personnel_entry(entry_id)

    assert updated is True
    assert reloaded_entry is not None
    assert reloaded_entry.status == "Corrected quickly"
    assert reloaded_entry.edited is False



def test_update_personnel_entry_respects_longer_configured_grace_period(
    repository: EventLogRepository,
) -> None:
    entry_id = _create_personnel_entry(repository, who="Grace Target")
    set_edit_grace_period_seconds(repository, 600)
    _set_personnel_logged_time(repository, entry_id, datetime.now() - timedelta(seconds=360))

    updated = repository.update_personnel_entry(
        PersonnelEntry(
            id=entry_id,
            who="Grace Target",
            operator="Default Operator",
            status="Still within grace period",
            location="Grid C3",
            last_contact_time=datetime(2026, 4, 27, 12, 10, 0),
            mission_notes="Configured grace period.",
        )
    )

    reloaded_entry = repository.get_personnel_entry(entry_id)

    assert updated is True
    assert reloaded_entry is not None
    assert reloaded_entry.status == "Still within grace period"
    assert reloaded_entry.edited is False



def test_update_personnel_entry_returns_false_when_entry_is_missing_or_unsaved(
    repository: EventLogRepository,
) -> None:
    missing_id_result = repository.update_personnel_entry(
        PersonnelEntry(
            id=999,
            who="Missing",
            operator="Operator Missing",
        )
    )
    unsaved_result = repository.update_personnel_entry(
        PersonnelEntry(
            who="Unsaved",
            operator="Operator Unsaved",
        )
    )

    assert missing_id_result is False
    assert unsaved_result is False



def test_update_personnel_entry_validates_alarm_fields(
    repository: EventLogRepository,
) -> None:
    entry_id = _create_personnel_entry(repository, who="Alarm Validation")

    with pytest.raises(ValueError, match="expected_checkin_time"):
        repository.update_personnel_entry(
            PersonnelEntry(
                id=entry_id,
                who="Alarm Validation",
                operator="Default Operator",
                alarm_enabled=True,
            )
        )



def test_delete_personnel_entry_removes_entry_and_preserves_other_rows(
    repository: EventLogRepository,
) -> None:
    deleted_id = _create_personnel_entry(repository, who="Delete Me")
    kept_id = _create_personnel_entry(repository, who="Keep Me")

    deleted = repository.delete_personnel_entry(deleted_id)

    assert deleted is True
    assert repository.get_personnel_entry(deleted_id) is None
    kept_entry = repository.get_personnel_entry(kept_id)
    assert kept_entry is not None
    assert kept_entry.who == "Keep Me"



def test_delete_personnel_entry_returns_false_for_missing_id(
    repository: EventLogRepository,
) -> None:
    assert repository.delete_personnel_entry(999) is False



def test_search_personnel_entries_finds_case_insensitive_matches_across_text_fields(
    repository: EventLogRepository,
) -> None:
    who_id = _create_personnel_entry(repository, who="Hotel Hello")
    status_id = _create_personnel_entry(repository, status="HELLO from status")
    notes_id = _create_personnel_entry(repository, mission_notes="Need hello supplies")
    _create_personnel_entry(repository, who="No Match", status="Standing by")

    _set_personnel_logged_time(repository, who_id, datetime(2026, 4, 27, 9, 0, 0))
    _set_personnel_logged_time(repository, status_id, datetime(2026, 4, 27, 12, 0, 0))
    _set_personnel_logged_time(repository, notes_id, datetime(2026, 4, 27, 15, 0, 0))

    entries = repository.search_personnel_entries("hello")

    assert [entry.id for entry in entries] == [notes_id, status_id, who_id]



def test_search_personnel_entries_combines_text_and_filters(
    repository: EventLogRepository,
) -> None:
    _create_personnel_entry(
        repository,
        who="Alpha Search",
        operator="Operator Match",
        mission_notes="Urgent resupply needed",
        active=True,
    )
    _create_personnel_entry(
        repository,
        who="Bravo Search",
        operator="Operator Other",
        mission_notes="Urgent route update",
        active=True,
    )
    _create_personnel_entry(
        repository,
        who="Charlie Search",
        operator="Operator Match",
        mission_notes="Routine resupply complete",
        active=False,
    )

    entries = repository.search_personnel_entries(
        "urgent",
        {"operator": "Operator Match", "active": 1},
    )

    assert [entry.who for entry in entries] == ["Alpha Search"]



def test_search_personnel_entries_returns_empty_list_when_no_matches(
    repository: EventLogRepository,
) -> None:
    _create_personnel_entry(repository, who="Existing Personnel")

    entries = repository.search_personnel_entries("nonexistent")

    assert entries == []



def test_get_active_personnel_entries_returns_only_active_entries_sorted_by_last_contact_time_desc(
    repository: EventLogRepository,
) -> None:
    newest_active_id = _create_personnel_entry(
        repository,
        who="Newest Active",
        last_contact_time=datetime(2026, 4, 27, 16, 0, 0),
    )
    _create_personnel_entry(
        repository,
        who="Inactive Entry",
        active=False,
        last_contact_time=datetime(2026, 4, 27, 17, 0, 0),
    )
    older_active_id = _create_personnel_entry(
        repository,
        who="Older Active",
        last_contact_time=datetime(2026, 4, 27, 10, 0, 0),
    )

    entries = repository.get_active_personnel_entries()

    assert [entry.id for entry in entries] == [newest_active_id, older_active_id]



def test_get_active_personnel_entries_returns_empty_list_when_no_active_entries(
    repository: EventLogRepository,
) -> None:
    _create_personnel_entry(repository, who="Inactive Only", active=False)

    entries = repository.get_active_personnel_entries()

    assert entries == []



def test_get_personnel_history_returns_matching_entries_in_logged_time_desc_order(
    repository: EventLogRepository,
) -> None:
    oldest_id = _create_personnel_entry(repository, who="History Target", active=True)
    newest_id = _create_personnel_entry(repository, who="History Target", active=False)
    _create_personnel_entry(repository, who="Other Target", active=True)

    _set_personnel_logged_time(repository, oldest_id, datetime(2026, 4, 27, 8, 0, 0))
    _set_personnel_logged_time(repository, newest_id, datetime(2026, 4, 27, 14, 0, 0))

    entries = repository.get_personnel_history("History Target")

    assert [entry.id for entry in entries] == [newest_id, oldest_id]
    assert {entry.active for entry in entries} == {True, False}



def test_get_personnel_history_returns_empty_list_when_no_matches(
    repository: EventLogRepository,
) -> None:
    _create_personnel_entry(repository, who="Someone Else")

    entries = repository.get_personnel_history("Missing History")

    assert entries == []



def test_get_overdue_alarms_returns_only_overdue_untriggered_entries_sorted_by_urgency(
    repository: EventLogRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixed_now = datetime(2026, 4, 27, 15, 0, 0)
    freeze_repository_now(monkeypatch, fixed_now)

    most_overdue_id = _create_personnel_entry(
        repository,
        who="Most Overdue",
        alarm_enabled=True,
        expected_checkin_time=datetime(2026, 4, 27, 13, 0, 0),
        alarm_triggered=False,
    )
    less_overdue_id = _create_personnel_entry(
        repository,
        who="Less Overdue",
        alarm_enabled=True,
        expected_checkin_time=datetime(2026, 4, 27, 14, 0, 0),
        alarm_triggered=False,
    )
    _create_personnel_entry(
        repository,
        who="Future Alarm",
        alarm_enabled=True,
        expected_checkin_time=datetime(2026, 4, 27, 16, 0, 0),
        alarm_triggered=False,
    )
    _create_personnel_entry(
        repository,
        who="Triggered Alarm",
        alarm_enabled=True,
        expected_checkin_time=datetime(2026, 4, 27, 12, 0, 0),
        alarm_triggered=True,
    )
    _create_personnel_entry(
        repository,
        who="Alarm Disabled",
        alarm_enabled=False,
        alarm_triggered=False,
    )

    entries = repository.get_overdue_alarms()

    assert [entry.id for entry in entries] == [most_overdue_id, less_overdue_id]



def test_get_overdue_alarms_returns_empty_list_when_no_entries_are_overdue(
    repository: EventLogRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    freeze_repository_now(monkeypatch, datetime(2026, 4, 27, 15, 0, 0))
    _create_personnel_entry(
        repository,
        who="Not Overdue",
        alarm_enabled=True,
        expected_checkin_time=datetime(2026, 4, 27, 16, 0, 0),
    )

    entries = repository.get_overdue_alarms()

    assert entries == []


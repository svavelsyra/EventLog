from datetime import datetime, timedelta

import pytest

from src.core import CommunicationEntry, EventEntry
from src.db.repositories.sqlite.event_log_repository import EventLogRepository
from tests.unit.db.db_test_utils import freeze_repository_now, set_edit_grace_period_seconds


pytestmark = pytest.mark.unit


def test_repository_initializes_settings_with_default_edit_grace_period(
    repository: EventLogRepository,
) -> None:
    setting_row = repository.connection.execute(
        "SELECT value FROM settings WHERE key = ?",
        ("edited_flag_grace_period_seconds",),
    ).fetchone()

    assert setting_row is not None
    assert setting_row["value"] == "300"


def test_get_setting_returns_validated_value_when_present(
    repository: EventLogRepository,
) -> None:
    value = repository._get_setting(
        "edited_flag_grace_period_seconds",
        default=0,
        validator=int,
    )

    assert value == 300


def test_get_setting_returns_default_when_validator_rejects_value(
    repository: EventLogRepository,
) -> None:
    set_edit_grace_period_seconds(repository, "not-a-number")

    value = repository._get_setting(
        "edited_flag_grace_period_seconds",
        default=300,
        validator=int,
    )

    assert value == 300


def test_invalid_edit_grace_setting_falls_back_to_default(
    repository: EventLogRepository,
) -> None:
    set_edit_grace_period_seconds(repository, "not-a-number")

    assert repository._get_edited_flag_grace_period_seconds() == 300


def test_negative_edit_grace_setting_falls_back_to_default(
    repository: EventLogRepository,
) -> None:
    set_edit_grace_period_seconds(repository, "-1")

    assert repository._get_edited_flag_grace_period_seconds() == 300


def test_missing_edit_grace_setting_row_falls_back_to_default(
    repository: EventLogRepository,
) -> None:
    repository.connection.execute(
        "DELETE FROM settings WHERE key = ?",
        ("edited_flag_grace_period_seconds",),
    )
    repository.connection.commit()

    assert repository._get_edited_flag_grace_period_seconds() == 300


def test_missing_settings_table_falls_back_to_default_for_non_critical_setting(
    repository: EventLogRepository,
) -> None:
    repository.connection.execute("DROP TABLE settings")
    repository.connection.commit()

    assert repository._get_edited_flag_grace_period_seconds() == 300


def test_zero_second_grace_period_marks_any_delayed_update_as_edited(
    monkeypatch: pytest.MonkeyPatch,
    repository: EventLogRepository,
) -> None:
    fixed_now = datetime(2026, 4, 28, 12, 0, 0)
    set_edit_grace_period_seconds(repository, "0")
    freeze_repository_now(monkeypatch, fixed_now)

    existing_entry = repository.get_communication_entry(
        repository.create_communication_entry(
            CommunicationEntry(
                message_content="Zero-second grace period",
                operator="Operator Test",
            )
        )
    )
    assert existing_entry is not None
    existing_entry.logged_time = fixed_now - timedelta(microseconds=1)

    edited_flag = repository._resolve_edited_flag(existing_entry)

    assert edited_flag is True


def test_exact_grace_period_boundary_does_not_mark_entry_as_edited(
    monkeypatch: pytest.MonkeyPatch,
    repository: EventLogRepository,
) -> None:
    fixed_now = datetime(2026, 4, 28, 12, 0, 0)
    set_edit_grace_period_seconds(repository, "10")
    freeze_repository_now(monkeypatch, fixed_now)

    existing_entry = repository.get_event_entry(
        repository.create_event_entry(
            EventEntry(
                event_description="Exact grace period boundary",
                operator="Operator Test",
            )
        )
    )
    assert existing_entry is not None
    existing_entry.logged_time = fixed_now - timedelta(seconds=10)

    edited_flag = repository._resolve_edited_flag(existing_entry)

    assert edited_flag is False







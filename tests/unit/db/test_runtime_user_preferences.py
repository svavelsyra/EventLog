import pytest

from src.core.runtime_user_preferences import (
    COMMUNICATION_TAB_COLUMNS_RUNTIME_PREFERENCE,
    UnknownRuntimePreferenceKeyError,
    get_tab_ui_runtime_preference_definition,
    get_tab_ui_runtime_preference_key,
)
from src.db.repositories.sqlite.event_log_repository import EventLogRepository


pytestmark = pytest.mark.unit


def test_read_runtime_preference_returns_default_for_missing_row(
    repository: EventLogRepository,
) -> None:
    assert repository.read_runtime_preference(
        COMMUNICATION_TAB_COLUMNS_RUNTIME_PREFERENCE.key,
    ) == COMMUNICATION_TAB_COLUMNS_RUNTIME_PREFERENCE.clone_default_value()


def test_tab_ui_runtime_preference_keys_follow_the_shared_namespace() -> None:
    assert get_tab_ui_runtime_preference_key("communication", "columns") == "ui.tab.communication.columns"
    assert get_tab_ui_runtime_preference_key("event", "filters") == "ui.tab.event.filters"
    assert get_tab_ui_runtime_preference_key("personnel", "display") == "ui.tab.personnel.display"


def test_tab_ui_definitions_have_expected_category_defaults() -> None:
    assert get_tab_ui_runtime_preference_definition("communication", "columns").clone_default_value() == {
        "visible": [],
        "order": [],
        "widths": {},
    }
    assert get_tab_ui_runtime_preference_definition("event", "filters").clone_default_value() == {
        "values": {},
    }
    assert get_tab_ui_runtime_preference_definition("personnel", "display").clone_default_value() == {
        "sort": {
            "column": "",
            "direction": "desc",
        },
        "toggles": {},
    }


def test_missing_runtime_preference_returns_fresh_default_copy(
    repository: EventLogRepository,
) -> None:
    filters_definition = get_tab_ui_runtime_preference_definition("event", "filters")

    first_value = repository.read_runtime_preference(filters_definition.key)
    assert first_value == {"values": {}}

    assert isinstance(first_value, dict)
    first_value["values"] = {"priority": "high"}

    assert repository.read_runtime_preference(filters_definition.key) == {
        "values": {},
    }



def test_write_and_read_json_runtime_preference_round_trip(
    repository: EventLogRepository,
) -> None:
    columns_state = {
        "order": ["time", "from", "message"],
        "visible": ["time", "message"],
        "widths": {"message": 320, "time": 140},
    }

    repository.write_runtime_preference(
        COMMUNICATION_TAB_COLUMNS_RUNTIME_PREFERENCE.key,
        columns_state,
    )

    assert repository.read_runtime_preference(
        COMMUNICATION_TAB_COLUMNS_RUNTIME_PREFERENCE.key,
    ) == columns_state


def test_tab_display_preference_round_trips(
    repository: EventLogRepository,
) -> None:
    display_definition = get_tab_ui_runtime_preference_definition("personnel", "display")
    display_state = {
        "sort": {
            "column": "last_contact_time",
            "direction": "asc",
        },
        "toggles": {
            "show_only_active": True,
            "highlight_overdue": True,
        },
    }

    repository.write_runtime_preference(display_definition.key, display_state)

    assert repository.read_runtime_preference(display_definition.key) == display_state



def test_clear_runtime_preference_restores_default(
    repository: EventLogRepository,
) -> None:
    repository.write_runtime_preference(
        COMMUNICATION_TAB_COLUMNS_RUNTIME_PREFERENCE.key,
        {
            "order": ["time"],
            "visible": ["time"],
            "widths": {"time": 140},
        },
    )

    repository.clear_runtime_preference(COMMUNICATION_TAB_COLUMNS_RUNTIME_PREFERENCE.key)

    assert repository.read_runtime_preference(
        COMMUNICATION_TAB_COLUMNS_RUNTIME_PREFERENCE.key,
    ) == COMMUNICATION_TAB_COLUMNS_RUNTIME_PREFERENCE.clone_default_value()



def test_read_runtime_preference_returns_default_for_malformed_json(
    repository: EventLogRepository,
) -> None:
    filters_definition = get_tab_ui_runtime_preference_definition("event", "filters")
    repository.connection.execute(
        """
        INSERT INTO user_preferences (key, value, description, modified_time)
        VALUES (?, ?, ?, ?)
        """,
        (
            filters_definition.key,
            "not-json",
            "broken",
            "2026-05-11T12:00:00",
        ),
    )
    repository.connection.commit()

    assert repository.read_runtime_preference(
        filters_definition.key,
    ) == filters_definition.clone_default_value()


def test_malformed_tab_columns_preference_falls_back_to_default(
    repository: EventLogRepository,
) -> None:
    columns_definition = get_tab_ui_runtime_preference_definition("communication", "columns")
    repository.connection.execute(
        """
        INSERT INTO user_preferences (key, value, description, modified_time)
        VALUES (?, ?, ?, ?)
        """,
        (
            columns_definition.key,
            '{"visible": ["time"], "order": ["time"], "widths": {"time": 0}}',
            "broken-shape",
            "2026-05-11T12:00:00",
        ),
    )
    repository.connection.commit()

    assert repository.read_runtime_preference(
        columns_definition.key,
    ) == columns_definition.clone_default_value()


def test_invalid_display_preference_is_rejected_on_write(
    repository: EventLogRepository,
) -> None:
    display_definition = get_tab_ui_runtime_preference_definition("personnel", "display")

    with pytest.raises(ValueError, match="sort.direction"):
        repository.write_runtime_preference(
            display_definition.key,
            {
                "sort": {
                    "column": "last_contact_time",
                    "direction": "sideways",
                },
                "toggles": {},
            },
        )



def test_read_runtime_preference_returns_default_when_table_is_missing(
    repository: EventLogRepository,
) -> None:
    repository.connection.execute("DROP TABLE user_preferences")
    repository.connection.commit()

    assert repository.read_runtime_preference(
        COMMUNICATION_TAB_COLUMNS_RUNTIME_PREFERENCE.key,
    ) == COMMUNICATION_TAB_COLUMNS_RUNTIME_PREFERENCE.clone_default_value()



def test_runtime_preference_access_rejects_unknown_keys(
    repository: EventLogRepository,
) -> None:
    with pytest.raises(UnknownRuntimePreferenceKeyError):
        repository.read_runtime_preference("ui.tab.unknown.columns")



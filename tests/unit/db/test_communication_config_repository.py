import pytest

from src.core import CommunicationEntry
from src.core.communication_portability import (
    CommunicationPortabilityBundle,
    PortableCommunicationOption,
    PortableCommunicationQualifier,
    PortableCommunicationSystem,
)
from src.db.repositories.sqlite.event_log_repository import EventLogRepository


pytestmark = pytest.mark.unit


def test_get_active_communication_system_configs_returns_seeded_phase_1_defaults(
    repository: EventLogRepository,
) -> None:
    configs = repository.get_active_communication_system_configs()

    assert [config.system_name for config in configs] == [
        "RA180",
        "Motorola",
        "Rakel",
        "Courier",
    ]

    ra180 = configs[0]
    courier = configs[-1]

    assert ra180.system_type == "Radio System"
    assert ra180.child_label == "Channel"
    assert [option.option_value for option in ra180.options] == [
        "1",
        "2",
        "3",
        "4",
        "5",
        "6",
        "7",
        "8",
    ]
    assert [option.option_label for option in ra180.options[:2]] == [
        "Channel 1",
        "Channel 2",
    ]
    assert ra180.options[0].children == ()
    assert [(qualifier.qualifier_key, qualifier.default_value) for qualifier in ra180.qualifiers] == [
        ("data", False),
        ("encrypted", False),
    ]
    assert [qualifier.visibility_mode for qualifier in ra180.qualifiers] == [
        "editable",
        "editable",
    ]

    assert courier.system_type == "Courier"
    assert courier.child_label is None
    assert courier.options == ()
    assert len(courier.qualifiers) == 1
    assert courier.qualifiers[0].qualifier_key == "encrypted"
    assert courier.qualifiers[0].default_value is False
    assert courier.qualifiers[0].visibility_mode == "hidden"


def test_get_active_communication_system_config_builds_recursive_options_and_filters_inactive_rows(
    repository: EventLogRepository,
) -> None:
    channel_one_row = repository.connection.execute(
        """
        SELECT co.id
        FROM communication_options AS co
        JOIN communication_systems AS cs
            ON cs.id = co.communication_system_id
        WHERE cs.system_name = ?
          AND co.option_value = ?
        """,
        ("RA180", "1"),
    ).fetchone()
    assert channel_one_row is not None

    repository.connection.execute(
        """
        INSERT INTO communication_options (
            communication_system_id,
            option_value,
            option_label,
            parent_option_id,
            child_label,
            sort_order,
            is_active
        )
        VALUES (
            (SELECT id FROM communication_systems WHERE system_name = ?),
            ?,
            ?,
            ?,
            ?,
            ?,
            ?
        )
        """,
        ("RA180", "DATA", "Data Route", channel_one_row[0], None, 10, 1),
    )
    repository.connection.execute(
        "UPDATE communication_systems SET is_active = 0 WHERE system_name = ?",
        ("Motorola",),
    )
    repository.connection.execute(
        """
        UPDATE communication_options
        SET is_active = 0
        WHERE communication_system_id = (
            SELECT id FROM communication_systems WHERE system_name = ?
        )
          AND option_value = ?
        """,
        ("RA180", "8"),
    )
    repository.connection.commit()

    active_configs = repository.get_active_communication_system_configs()
    ra180 = repository.get_active_communication_system_config("RA180")

    assert [config.system_name for config in active_configs] == ["RA180", "Rakel", "Courier"]
    assert repository.get_active_communication_system_config("Motorola") is None
    assert repository.get_active_communication_system_config("Missing") is None
    assert ra180 is not None
    assert [option.option_value for option in ra180.options] == [
        "1",
        "2",
        "3",
        "4",
        "5",
        "6",
        "7",
    ]
    assert [child.option_value for child in ra180.options[0].children] == ["DATA"]
    assert ra180.options[0].children[0].option_label == "Data Route"


def test_get_active_communication_system_config_parses_json_valid_values_and_default_types(
    repository: EventLogRepository,
) -> None:
    repository.connection.execute(
        """
        INSERT INTO communication_qualifiers_config (
            communication_system_id,
            qualifier_key,
            label,
            field_type,
            valid_values,
            default_value,
            help_text,
            visibility_mode
        )
        VALUES (
            (SELECT id FROM communication_systems WHERE system_name = ?),
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?
        )
        """,
        (
            "Courier",
            "delivery_mode",
            "Leveranssätt",
            "enum",
            '["oral", "written"]',
            "written",
            "How the courier delivered the message.",
            "editable",
        ),
    )
    repository.connection.commit()

    courier = repository.get_active_communication_system_config("Courier")

    assert courier is not None
    assert [(qualifier.qualifier_key, qualifier.default_value) for qualifier in courier.qualifiers] == [
        ("delivery_mode", "written"),
        ("encrypted", False),
    ]
    delivery_mode = courier.qualifiers[0]
    assert delivery_mode.valid_values == ("oral", "written")
    assert delivery_mode.help_text == "How the courier delivered the message."


def test_add_communication_option_supports_create_duplicate_and_reactivate_flow(
    repository: EventLogRepository,
) -> None:
    channel_one_row = repository.connection.execute(
        """
        SELECT co.id
        FROM communication_options AS co
        JOIN communication_systems AS cs
            ON cs.id = co.communication_system_id
        WHERE cs.system_name = ?
          AND co.option_value = ?
        """,
        ("RA180", "1"),
    ).fetchone()
    assert channel_one_row is not None

    created_result = repository.add_communication_option(
        system_name="RA180",
        option_value="DATA",
        option_label="Data Route",
        parent_option_id=int(channel_one_row[0]),
        sort_order=10,
    )

    assert created_result.status == "created"
    assert created_result.changed is True
    assert created_result.option_id is not None

    duplicate_result = repository.add_communication_option(
        system_name="RA180",
        option_value="DATA",
        option_label="Data Route",
        parent_option_id=int(channel_one_row[0]),
        sort_order=10,
    )

    assert duplicate_result.status == "already_exists"
    assert duplicate_result.changed is False
    assert duplicate_result.option_id == created_result.option_id

    deactivated_result = repository.deactivate_communication_option(option_id=created_result.option_id)

    assert deactivated_result.status == "deactivated"
    assert deactivated_result.changed is True

    reactivated_result = repository.add_communication_option(
        system_name="RA180",
        option_value="DATA",
        option_label="Data Route Updated",
        parent_option_id=int(channel_one_row[0]),
        sort_order=15,
    )

    assert reactivated_result.status == "reactivated"
    assert reactivated_result.changed is True
    assert reactivated_result.option_id == created_result.option_id

    ra180 = repository.get_active_communication_system_config("RA180")

    assert ra180 is not None
    assert [child.option_value for child in ra180.options[0].children] == ["DATA"]
    assert ra180.options[0].children[0].option_label == "Data Route Updated"
    assert ra180.options[0].children[0].sort_order == 15


def test_rename_and_deactivate_communication_option_preserve_saved_entries(
    repository: EventLogRepository,
) -> None:
    entry_id = repository.create_communication_entry(
        CommunicationEntry(
            message_content="Maintain listening watch.",
            operator="Operator One",
            communication_system="RA180",
            channel_designation="Channel 2",
        )
    )

    option_row = repository.connection.execute(
        """
        SELECT co.id
        FROM communication_options AS co
        JOIN communication_systems AS cs
            ON cs.id = co.communication_system_id
        WHERE cs.system_name = ?
          AND co.option_value = ?
        """,
        ("RA180", "2"),
    ).fetchone()
    assert option_row is not None
    option_id = int(option_row[0])

    updated_result = repository.rename_communication_option(
        option_id=option_id,
        option_label="Company Net",
    )
    unchanged_result = repository.rename_communication_option(
        option_id=option_id,
        option_label="Company Net",
    )
    deactivated_result = repository.deactivate_communication_option(option_id=option_id)
    inactive_result = repository.deactivate_communication_option(option_id=option_id)

    assert updated_result.status == "updated"
    assert updated_result.changed is True
    assert unchanged_result.status == "unchanged"
    assert unchanged_result.changed is False
    assert deactivated_result.status == "deactivated"
    assert deactivated_result.changed is True
    assert inactive_result.status == "already_inactive"
    assert inactive_result.changed is False

    ra180 = repository.get_active_communication_system_config("RA180")
    saved_entry = repository.get_communication_entry(entry_id)

    assert ra180 is not None
    assert [option.option_value for option in ra180.options] == ["1", "3", "4", "5", "6", "7", "8"]
    assert saved_entry is not None
    assert saved_entry.communication_system == "RA180"
    assert saved_entry.channel_designation == "Channel 2"


def test_replace_communication_portability_bundle_exactly_replaces_active_config(
    repository: EventLogRepository,
) -> None:
    bundle = CommunicationPortabilityBundle(
        communication_systems=(
            PortableCommunicationSystem(
                system_name="RA180",
                system_type="Radio System",
                child_label="Channel",
                sort_order=10,
                options=(
                    PortableCommunicationOption(
                        option_value="9",
                        option_label="Channel 9",
                        child_label="Relay",
                        sort_order=90,
                        children=(
                            PortableCommunicationOption(
                                option_value="ALT",
                                option_label="Alternate Relay",
                                child_label=None,
                                sort_order=5,
                            ),
                        ),
                    ),
                ),
                qualifiers=(
                    PortableCommunicationQualifier(
                        qualifier_key="encrypted",
                        label="Encrypted",
                        field_type="boolean",
                        valid_values=None,
                        default_value=True,
                        help_text="Imported exact-replace qualifier.",
                        visibility_mode="forced",
                    ),
                ),
            ),
        ),
    )

    repository.replace_communication_portability_bundle(bundle)

    active_configs = repository.get_active_communication_system_configs()
    assert [config.system_name for config in active_configs] == ["RA180"]

    ra180 = active_configs[0]
    assert [option.option_value for option in ra180.options] == ["9"]
    assert ra180.options[0].option_label == "Channel 9"
    assert ra180.options[0].child_label == "Relay"
    assert [child.option_value for child in ra180.options[0].children] == ["ALT"]
    assert [(qualifier.qualifier_key, qualifier.default_value) for qualifier in ra180.qualifiers] == [
        ("encrypted", True),
    ]
    assert [qualifier.visibility_mode for qualifier in ra180.qualifiers] == ["forced"]

    motorola_row = repository.connection.execute(
        "SELECT is_active FROM communication_systems WHERE system_name = ?",
        ("Motorola",),
    ).fetchone()
    assert motorola_row is not None
    assert int(motorola_row[0]) == 0

    old_channel_row = repository.connection.execute(
        """
        SELECT co.is_active
        FROM communication_options AS co
        JOIN communication_systems AS cs
            ON cs.id = co.communication_system_id
        WHERE cs.system_name = ?
          AND co.option_value = ?
          AND co.parent_option_id IS NULL
        """,
        ("RA180", "1"),
    ).fetchone()
    assert old_channel_row is not None
    assert int(old_channel_row[0]) == 0



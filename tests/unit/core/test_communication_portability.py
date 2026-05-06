import pytest
from typing import cast

from src.core.communication_config import CommunicationConfigLoader, CommunicationConfigSource
from src.core.communication_portability import (
    COMMUNICATION_PORTABILITY_BUNDLE_KIND,
    COMMUNICATION_PORTABILITY_BUNDLE_VERSION,
    CommunicationPortabilityBundle,
    CommunicationPortabilityContractError,
    EXCLUDED_COMMUNICATION_PORTABILITY_DOMAINS,
    PORTABLE_COMMUNICATION_DOMAINS,
    PortableCommunicationOption,
    PortableCommunicationQualifier,
    PortableCommunicationSystem,
    build_communication_portability_bundle,
    export_communication_portability_payload,
    import_communication_portability_payload,
    parse_communication_portability_payload,
    validate_communication_portability_payload,
)
from src.db.repositories.sqlite.event_log_repository import EventLogRepository
from src.db.sqlite_adapter import SQLiteAdapter


pytestmark = pytest.mark.unit


def _as_config_source(repository: EventLogRepository) -> CommunicationConfigSource:
    return cast(CommunicationConfigSource, cast(object, repository))


def _build_import_payload() -> dict[str, object]:
    return {
        "bundle_kind": COMMUNICATION_PORTABILITY_BUNDLE_KIND,
        "bundle_version": COMMUNICATION_PORTABILITY_BUNDLE_VERSION,
        "portable_domains": list(PORTABLE_COMMUNICATION_DOMAINS),
        "communication_systems": [
            {
                "system_name": "Field Telephone",
                "system_type": "Telephone",
                "child_label": "Line",
                "sort_order": 5,
                "options": [
                    {
                        "option_value": "LINE_A",
                        "option_label": "Line A",
                        "child_label": "Relay",
                        "sort_order": 10,
                        "children": [
                            {
                                "option_value": "ALT",
                                "option_label": "Alternate Relay",
                                "child_label": None,
                                "sort_order": 20,
                                "children": [],
                            },
                        ],
                    },
                ],
                "qualifiers": [
                    {
                        "qualifier_key": "encrypted",
                        "label": "Encrypted",
                        "field_type": "boolean",
                        "valid_values": None,
                        "default_value": False,
                        "help_text": "Whether the call path was encrypted.",
                        "visibility_mode": "editable",
                    },
                ],
            },
        ],
    }


def _add_nested_portability_config(repository: EventLogRepository) -> None:
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
    channel_one_id = int(channel_one_row[0])

    repository.add_communication_option(
        system_name="RA180",
        option_value="DATA",
        option_label="Data Route",
        parent_option_id=channel_one_id,
        child_label="Route Mode",
        sort_order=10,
    )
    data_row = repository.connection.execute(
        """
        SELECT co.id
        FROM communication_options AS co
        WHERE co.parent_option_id = ?
          AND co.option_value = ?
        """,
        (channel_one_id, "DATA"),
    ).fetchone()
    assert data_row is not None
    data_id = int(data_row[0])

    repository.add_communication_option(
        system_name="RA180",
        option_value="ALT",
        option_label="Alternate Route",
        parent_option_id=data_id,
        sort_order=20,
    )
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


def test_bundle_defaults_freeze_allowlisted_communication_scope_only() -> None:
    bundle = CommunicationPortabilityBundle()

    assert bundle.bundle_kind == COMMUNICATION_PORTABILITY_BUNDLE_KIND
    assert bundle.bundle_version == COMMUNICATION_PORTABILITY_BUNDLE_VERSION
    assert bundle.portable_domains == PORTABLE_COMMUNICATION_DOMAINS
    assert bundle.communication_systems == ()
    assert "event_metadata" in EXCLUDED_COMMUNICATION_PORTABILITY_DOMAINS
    assert "user_preferences" in EXCLUDED_COMMUNICATION_PORTABILITY_DOMAINS
    assert "communication_entries" in EXCLUDED_COMMUNICATION_PORTABILITY_DOMAINS


def test_bundle_payload_matches_versioned_recursive_communication_contract() -> None:
    bundle = CommunicationPortabilityBundle(
        communication_systems=(
            PortableCommunicationSystem(
                system_name="RA180",
                system_type="Radio System",
                child_label="Channel",
                sort_order=10,
                options=(
                    PortableCommunicationOption(
                        option_value="1",
                        option_label="Channel 1",
                        child_label="Route",
                        sort_order=1,
                        children=(
                            PortableCommunicationOption(
                                option_value="DATA",
                                option_label="Data Route",
                                child_label=None,
                                sort_order=10,
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
                        default_value=False,
                        help_text="Whether traffic is encrypted.",
                        visibility_mode="editable",
                    ),
                ),
            ),
        ),
    )

    payload = bundle.to_payload()

    assert payload == {
        "bundle_kind": "eventlog.communication_config",
        "bundle_version": 1,
        "portable_domains": [
            "communication_systems",
            "communication_options",
            "communication_qualifiers",
        ],
        "communication_systems": [
            {
                "system_name": "RA180",
                "system_type": "Radio System",
                "child_label": "Channel",
                "sort_order": 10,
                "options": [
                    {
                        "option_value": "1",
                        "option_label": "Channel 1",
                        "child_label": "Route",
                        "sort_order": 1,
                        "children": [
                            {
                                "option_value": "DATA",
                                "option_label": "Data Route",
                                "child_label": None,
                                "sort_order": 10,
                                "children": [],
                            },
                        ],
                    },
                ],
                "qualifiers": [
                    {
                        "qualifier_key": "encrypted",
                        "label": "Encrypted",
                        "field_type": "boolean",
                        "valid_values": None,
                        "default_value": False,
                        "help_text": "Whether traffic is encrypted.",
                        "visibility_mode": "editable",
                    },
                ],
            },
        ],
    }

    validate_communication_portability_payload(payload)


def test_validate_payload_rejects_missing_or_unsupported_version() -> None:
    missing_version_payload = {
        "bundle_kind": COMMUNICATION_PORTABILITY_BUNDLE_KIND,
        "portable_domains": list(PORTABLE_COMMUNICATION_DOMAINS),
        "communication_systems": [],
    }
    unsupported_version_payload = {
        "bundle_kind": COMMUNICATION_PORTABILITY_BUNDLE_KIND,
        "bundle_version": 99,
        "portable_domains": list(PORTABLE_COMMUNICATION_DOMAINS),
        "communication_systems": [],
    }

    with pytest.raises(CommunicationPortabilityContractError, match="bundle_version"):
        validate_communication_portability_payload(missing_version_payload)

    with pytest.raises(CommunicationPortabilityContractError, match="bundle_version"):
        validate_communication_portability_payload(unsupported_version_payload)


def test_validate_payload_rejects_scope_widening_via_extra_domain() -> None:
    widened_scope_payload = {
        "bundle_kind": COMMUNICATION_PORTABILITY_BUNDLE_KIND,
        "bundle_version": COMMUNICATION_PORTABILITY_BUNDLE_VERSION,
        "portable_domains": [*PORTABLE_COMMUNICATION_DOMAINS, "event_metadata"],
        "communication_systems": [],
    }

    with pytest.raises(CommunicationPortabilityContractError, match="allowlist"):
        validate_communication_portability_payload(widened_scope_payload)


def test_validate_payload_rejects_excluded_top_level_sections() -> None:
    invalid_payload = _build_import_payload()
    invalid_payload["user_preferences"] = {"last_operator": "Operator One"}

    with pytest.raises(CommunicationPortabilityContractError, match="contract exactly"):
        validate_communication_portability_payload(invalid_payload)


def test_validate_payload_rejects_unsupported_bundle_kind() -> None:
    invalid_payload = _build_import_payload()
    invalid_payload["bundle_kind"] = "eventlog.full_backup"

    with pytest.raises(CommunicationPortabilityContractError, match="bundle_kind"):
        validate_communication_portability_payload(invalid_payload)


def test_validate_payload_rejects_non_mapping_bundle_shape() -> None:
    malformed_payload = cast(dict[str, object], cast(object, ["not", "a", "mapping"]))

    with pytest.raises(CommunicationPortabilityContractError, match="bundle must be a mapping"):
        validate_communication_portability_payload(malformed_payload)


def test_validate_payload_rejects_unapproved_nested_fields() -> None:
    invalid_payload = {
        "bundle_kind": COMMUNICATION_PORTABILITY_BUNDLE_KIND,
        "bundle_version": COMMUNICATION_PORTABILITY_BUNDLE_VERSION,
        "portable_domains": list(PORTABLE_COMMUNICATION_DOMAINS),
        "communication_systems": [
            {
                "system_name": "Courier",
                "system_type": "Courier",
                "child_label": None,
                "sort_order": None,
                "options": [],
                "qualifiers": [],
                "secret_key_reference": "forbidden",
            },
        ],
    }

    with pytest.raises(CommunicationPortabilityContractError, match="contract exactly"):
        validate_communication_portability_payload(invalid_payload)


def test_build_portability_bundle_exports_seeded_runtime_config_deterministically(
    repository: EventLogRepository,
) -> None:
    loader = CommunicationConfigLoader(_as_config_source(repository))

    bundle = build_communication_portability_bundle(loader.get_config())
    payload = export_communication_portability_payload(loader.get_config())

    assert bundle.bundle_kind == COMMUNICATION_PORTABILITY_BUNDLE_KIND
    assert bundle.bundle_version == COMMUNICATION_PORTABILITY_BUNDLE_VERSION
    assert [system.system_name for system in bundle.communication_systems] == [
        "RA180",
        "Motorola",
        "Rakel",
        "Courier",
    ]
    ra180 = bundle.communication_systems[0]
    assert ra180.system_type == "Radio System"
    assert [option.option_value for option in ra180.options[:3]] == ["1", "2", "3"]
    assert [qualifier.qualifier_key for qualifier in ra180.qualifiers] == ["data", "encrypted"]

    courier = bundle.communication_systems[-1]
    assert courier.system_name == "Courier"
    assert courier.options == ()
    assert len(courier.qualifiers) == 1
    assert courier.qualifiers[0].qualifier_key == "encrypted"
    assert courier.qualifiers[0].visibility_mode == "hidden"

    assert payload["portable_domains"] == list(PORTABLE_COMMUNICATION_DOMAINS)
    communication_system_payloads = cast(list[dict[str, object]], payload["communication_systems"])
    first_system_payload = communication_system_payloads[0]
    assert "system_id" not in first_system_payload
    option_payloads = cast(list[dict[str, object]], first_system_payload["options"])
    assert "option_id" not in option_payloads[0]
    validate_communication_portability_payload(payload)


def test_build_portability_bundle_supports_empty_runtime_config(
    repository: EventLogRepository,
) -> None:
    repository.connection.execute("UPDATE communication_systems SET is_active = 0")
    repository.connection.commit()

    loader = CommunicationConfigLoader(_as_config_source(repository))
    bundle = build_communication_portability_bundle(loader.get_config())
    payload = export_communication_portability_payload(loader.get_config())

    assert bundle.communication_systems == ()
    assert payload["communication_systems"] == []
    validate_communication_portability_payload(payload)


def test_build_portability_bundle_preserves_nested_options_and_enum_qualifier_fields(
    repository: EventLogRepository,
) -> None:
    _add_nested_portability_config(repository)

    loader = CommunicationConfigLoader(_as_config_source(repository))
    bundle = build_communication_portability_bundle(loader.get_config(force_reload=True))
    payload = bundle.to_payload()

    ra180 = bundle.communication_systems[0]
    nested_option = ra180.options[0].children[0]
    assert nested_option.option_value == "DATA"
    assert nested_option.child_label == "Route Mode"
    assert nested_option.children[0].option_value == "ALT"
    assert nested_option.children[0].option_label == "Alternate Route"

    courier = bundle.communication_systems[-1]
    assert [qualifier.qualifier_key for qualifier in courier.qualifiers] == [
        "delivery_mode",
        "encrypted",
    ]
    delivery_mode = courier.qualifiers[0]
    assert delivery_mode.valid_values == ("oral", "written")
    assert delivery_mode.default_value == "written"
    assert delivery_mode.help_text == "How the courier delivered the message."

    courier_payload = cast(list[dict[str, object]], payload["communication_systems"])[-1]
    courier_qualifier_payloads = cast(list[dict[str, object]], courier_payload["qualifiers"])
    assert courier_qualifier_payloads[0]["valid_values"] == ["oral", "written"]
    assert courier_qualifier_payloads[0]["default_value"] == "written"
    validate_communication_portability_payload(payload)


def test_export_import_round_trip_preserves_allowlisted_bundle_after_reload() -> None:
    source_repository = EventLogRepository(SQLiteAdapter(":memory:"))
    target_repository = EventLogRepository(SQLiteAdapter(":memory:"))

    try:
        _add_nested_portability_config(source_repository)
        source_loader = CommunicationConfigLoader(_as_config_source(source_repository))
        source_payload = export_communication_portability_payload(
            source_loader.get_config(force_reload=True)
        )

        target_loader = CommunicationConfigLoader(_as_config_source(target_repository))
        result = import_communication_portability_payload(
            source_payload,
            import_target=target_repository,
            config_loader=target_loader,
        )

        assert export_communication_portability_payload(result.config) == source_payload
        assert (
            export_communication_portability_payload(
                target_loader.get_config(force_reload=True)
            )
            == source_payload
        )
    finally:
        source_repository.close()
        target_repository.close()


def test_import_payload_applies_bundle_and_reloads_runtime_from_database(
    repository: EventLogRepository,
) -> None:
    loader = CommunicationConfigLoader(_as_config_source(repository))
    assert loader.get_config().system_names == ("RA180", "Motorola", "Rakel", "Courier")

    payload = _build_import_payload()

    result = import_communication_portability_payload(
        payload,
        import_target=repository,
        config_loader=loader,
    )

    assert result.bundle == parse_communication_portability_payload(payload)
    assert result.config.system_names == ("Field Telephone",)

    imported_system = result.config.get_system("Field Telephone")
    assert imported_system is not None
    assert imported_system.system_type == "Telephone"
    assert imported_system.child_label == "Line"
    assert [option.option_value for option in imported_system.options] == ["LINE_A"]
    assert imported_system.options[0].children[0].option_value == "ALT"
    assert [qualifier.qualifier_key for qualifier in imported_system.qualifiers] == ["encrypted"]
    assert imported_system.qualifiers[0].default_value is False
    assert loader.get_config().system_names == ("Field Telephone",)


def test_import_payload_rejects_invalid_qualifier_contract_before_database_apply(
    repository: EventLogRepository,
) -> None:
    loader = CommunicationConfigLoader(_as_config_source(repository))
    original_payload = export_communication_portability_payload(loader.get_config())
    invalid_payload = _build_import_payload()
    invalid_payload["communication_systems"] = [
        {
            **cast(list[dict[str, object]], _build_import_payload()["communication_systems"])[0],
            "qualifiers": [
                {
                    "qualifier_key": "encrypted",
                    "label": "Encrypted",
                    "field_type": "radio_magic",
                    "valid_values": None,
                    "default_value": False,
                    "help_text": "Whether the call path was encrypted.",
                    "visibility_mode": "editable",
                },
            ],
        },
    ]

    with pytest.raises(CommunicationPortabilityContractError, match="field_type"):
        import_communication_portability_payload(
            invalid_payload,
            import_target=repository,
            config_loader=loader,
        )

    assert export_communication_portability_payload(loader.get_config(force_reload=True)) == original_payload



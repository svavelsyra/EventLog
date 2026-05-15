from typing import cast

from src.core import CommunicationConfigLoader, CommunicationConfigManager, SystemConfig
from src.core.communication_config import CommunicationConfigMutator, CommunicationConfigSource
from src.db.repositories.sqlite.event_log_repository import EventLogRepository


def _as_config_source(repository: EventLogRepository) -> CommunicationConfigSource:
    return cast(CommunicationConfigSource, cast(object, repository))


def _as_config_mutator(repository: EventLogRepository) -> CommunicationConfigMutator:
    return cast(CommunicationConfigMutator, cast(object, repository))


def test_loader_builds_runtime_system_config_from_repository_reads(
    repository: EventLogRepository,
) -> None:
    loader = CommunicationConfigLoader(_as_config_source(repository))

    config = loader.get_config()

    assert isinstance(config, SystemConfig)
    assert loader.has_cached_config is True
    assert config.system_names == ("RA180", "Motorola", "Rakel", "Kurir", "Telefon")
    assert config.is_empty is False

    ra180 = config.get_system("RA180")
    assert ra180 is not None
    assert ra180.system_type == "Radio System"
    assert ra180.child_label == "Kanal"
    assert [option.option_value for option in ra180.options[:3]] == ["1", "2", "3"]
    assert ra180.get_option("2") is not None
    assert ra180.get_option("2").option_label == "Kanal 2"
    assert ra180.get_option("2").children == ()

    encrypted = ra180.get_qualifier("encrypted")
    assert encrypted is not None
    assert encrypted.default_value is True
    assert encrypted.visibility_mode == "editable"

    data = ra180.get_qualifier("data")
    assert data is not None
    assert data.default_value is True
    assert data.visibility_mode == "editable"

    kurir = config.get_system("Kurir")
    assert kurir is not None
    assert kurir.child_label == "Skydd"
    assert [option.option_value for option in kurir.options] == ["KLAR", "TTA"]
    assert kurir.qualifiers == ()

    telefon = config.get_system("Telefon")
    assert telefon is not None
    assert telefon.options == ()
    assert [qualifier.qualifier_key for qualifier in telefon.qualifiers] == ["data", "encrypted"]


def test_loader_keeps_cached_config_until_explicit_reload(
    repository: EventLogRepository,
) -> None:
    loader = CommunicationConfigLoader(_as_config_source(repository))

    cached_config = loader.get_config()
    cached_ra180 = cached_config.get_system("RA180")
    assert cached_ra180 is not None
    assert cached_ra180.get_option("9") is None

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
        ("RA180", "9", "Channel 9", None, None, 90, 1),
    )
    repository.connection.execute(
        "UPDATE communication_systems SET is_active = 0 WHERE system_name = ?",
        ("Motorola",),
    )
    repository.connection.commit()

    unchanged_config = loader.get_config()
    unchanged_ra180 = unchanged_config.get_system("RA180")
    assert unchanged_ra180 is not None
    assert unchanged_config is cached_config
    assert "Motorola" in unchanged_config.system_names
    assert unchanged_ra180.get_option("9") is None

    reloaded_config = loader.reload_config()
    reloaded_ra180 = reloaded_config.get_system("RA180")
    assert reloaded_ra180 is not None
    assert reloaded_config is not cached_config
    assert "Motorola" not in reloaded_config.system_names
    assert reloaded_ra180.get_option("9") is not None
    assert reloaded_ra180.get_option("9").option_label == "Channel 9"


def test_loader_returns_predictable_empty_config_when_no_active_systems_exist(
    repository: EventLogRepository,
) -> None:
    repository.connection.execute("UPDATE communication_systems SET is_active = 0")
    repository.connection.commit()

    loader = CommunicationConfigLoader(_as_config_source(repository))
    config = loader.get_config()

    assert config.systems == ()
    assert config.system_names == ()
    assert config.get_system("RA180") is None
    assert config.is_empty is True


def test_manager_reloads_cached_config_after_successful_mutation_only(
    repository: EventLogRepository,
) -> None:
    loader = CommunicationConfigLoader(_as_config_source(repository))
    manager = CommunicationConfigManager(loader, _as_config_mutator(repository))

    cached_config = manager.get_config()
    cached_ra180 = cached_config.get_system("RA180")
    assert cached_ra180 is not None
    assert cached_ra180.get_option("9") is None

    created_result = manager.add_option(
        system_name="RA180",
        option_value="9",
        option_label="Channel 9",
        sort_order=90,
    )

    assert created_result.status == "created"
    assert created_result.changed is True
    assert created_result.config is not None
    assert loader.get_config() is created_result.config
    assert cached_config is not created_result.config
    created_ra180 = created_result.config.get_system("RA180")
    assert created_ra180 is not None
    assert created_ra180.get_option("9") is not None
    assert created_ra180.get_option("9").option_label == "Channel 9"

    duplicate_result = manager.add_option(
        system_name="RA180",
        option_value="9",
        option_label="Channel 9",
        sort_order=90,
    )

    assert duplicate_result.status == "already_exists"
    assert duplicate_result.changed is False
    assert duplicate_result.config is None
    assert loader.get_config() is created_result.config


def test_runtime_system_can_find_nested_option_by_ordered_value_path(
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

    repository.add_communication_option(
        system_name="RA180",
        option_value="DATA",
        option_label="Data Route",
        parent_option_id=int(channel_one_row[0]),
        sort_order=10,
    )
    data_row = repository.connection.execute(
        """
        SELECT co.id
        FROM communication_options AS co
        WHERE co.parent_option_id = ?
          AND co.option_value = ?
        """,
        (int(channel_one_row[0]), "DATA"),
    ).fetchone()
    assert data_row is not None

    repository.add_communication_option(
        system_name="RA180",
        option_value="ALT",
        option_label="Alternate Route",
        parent_option_id=int(data_row[0]),
        sort_order=20,
    )

    loader = CommunicationConfigLoader(_as_config_source(repository))
    config = loader.get_config(force_reload=True)
    ra180 = config.get_system("RA180")

    assert ra180 is not None
    assert ra180.find_option_by_path(()) is None
    assert ra180.find_option_by_path(("1",)) is not None
    assert ra180.find_option_by_path(("1",)).option_label == "Kanal 1"
    assert ra180.find_option_by_path(("1", "DATA")) is not None
    assert ra180.find_option_by_path(("1", "DATA")).option_label == "Data Route"
    nested_option = ra180.find_option_by_path(("1", "DATA", "ALT"))
    assert nested_option is not None
    assert nested_option.option_label == "Alternate Route"
    assert ra180.find_option_by_path(("1", "ALT")) is None
    assert ra180.find_option_by_path(("missing",)) is None


def test_runtime_system_can_find_option_by_stored_id_across_nested_tree(
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
    channel_one_id = int(channel_one_row[0])

    repository.add_communication_option(
        system_name="RA180",
        option_value="DATA",
        option_label="Data Route",
        parent_option_id=channel_one_id,
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
    alternate_row = repository.connection.execute(
        """
        SELECT co.id
        FROM communication_options AS co
        WHERE co.parent_option_id = ?
          AND co.option_value = ?
        """,
        (data_id, "ALT"),
    ).fetchone()
    assert alternate_row is not None
    alternate_id = int(alternate_row[0])

    loader = CommunicationConfigLoader(_as_config_source(repository))
    config = loader.get_config(force_reload=True)
    ra180 = config.get_system("RA180")

    assert ra180 is not None
    top_level_option = ra180.find_option_by_id(channel_one_id)
    assert top_level_option is not None
    assert top_level_option.option_value == "1"
    assert top_level_option.option_label == "Kanal 1"

    middle_option = ra180.find_option_by_id(data_id)
    assert middle_option is not None
    assert middle_option.option_value == "DATA"
    assert middle_option.option_label == "Data Route"

    nested_option = ra180.find_option_by_id(alternate_id)
    assert nested_option is not None
    assert nested_option.option_value == "ALT"
    assert nested_option.option_label == "Alternate Route"

    assert ra180.find_option_by_id(-1) is None




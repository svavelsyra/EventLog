from configparser import ConfigParser
from dataclasses import replace
from pathlib import Path
from os import PathLike
from typing import cast

import pytest

from src.config import (
    BootstrapUiConfig,
    DatabaseConfig,
    MainWindowConfig,
    load_app_config,
    load_bootstrap_ui_config,
    load_database_config,
    parse_bootstrap_ui_config,
    parse_database_config,
)
from src.config.app_config import BootstrapTargetConfig, DatabaseCreationDefaults
from src.core.entries import CommunicationEntry
from src.db.repositories import bootstrap_backend_policy as backend_policy_module
from src.db.repositories import repository_factory as repository_factory_module
from src.db.database_adapter import BackendCleanupMetadata, WrongDatabaseAdapter
from src.db.repositories.base_repository import BaseRepository
from src.db.repositories.bootstrap_backend_policy import (
    CleanupMetadataResolver,
    get_remembered_target_cleanup_metadata,
    is_supported_repository_dialect,
    supports_external_key_file_advisory,
)
from src.db.repositories.repository_factory import RepositoryFactory
from src.db.repositories.sqlite.event_log_repository import EventLogRepository


pytestmark = pytest.mark.unit

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


def _get_table_names(repository: EventLogRepository) -> set[str]:
    rows = repository.connection.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
        """
    ).fetchall()
    return {row[0] for row in rows}


def test_create_event_log_repository_supports_file_backed_sqlite(tmp_path: Path) -> None:
    database_path = tmp_path / "eventlog.db"

    repository = RepositoryFactory.create_event_log_repository(database_path=database_path)
    try:
        assert isinstance(repository, BaseRepository)
        assert isinstance(repository, EventLogRepository)
        assert repository.database_path == str(database_path)
        assert _get_table_names(repository) == EXPECTED_TABLES
    finally:
        repository.close()


def test_create_event_log_repository_forwards_optional_encryption_key(monkeypatch: pytest.MonkeyPatch) -> None:
    database_path = "secure-eventlog.db"
    encryption_key = bytes.fromhex(
        "00112233445566778899aabbccddeeff00112233445566778899aabbccddeeff"
    )
    captured: dict[str, object] = {}

    class StubAdapter:
        def __init__(self, path: str, *, encryption_key: bytes | None = None) -> None:
            captured["database_path"] = path
            captured["encryption_key"] = encryption_key

    class StubRepository:
        def __init__(self, adapter: object) -> None:
            captured["adapter"] = adapter

    monkeypatch.setattr(backend_policy_module, "SQLiteAdapter", StubAdapter)
    monkeypatch.setattr(backend_policy_module, "EventLogRepository", StubRepository)

    repository = RepositoryFactory.create_event_log_repository(
        database_path=database_path,
        encryption_key=encryption_key,
    )

    assert isinstance(repository, StubRepository)
    assert captured["database_path"] == database_path
    assert captured["encryption_key"] == encryption_key
    assert isinstance(captured["adapter"], StubAdapter)


@pytest.mark.parametrize(
    ("dialect", "expected"),
    [
        (repository_factory_module.SQLITE_DIALECT, True),
        ("postgres", False),
        ("", False),
    ],
)
def test_is_supported_repository_dialect_returns_factory_owned_support_contract(
    dialect: str,
    expected: bool,
) -> None:
    assert is_supported_repository_dialect(dialect) is expected


@pytest.mark.parametrize(
    ("dialect", "expected"),
    [
        (repository_factory_module.SQLITE_DIALECT, True),
        ("postgres", False),
        ("", False),
    ],
)
def test_supports_external_key_file_advisory_exposes_backend_capability_contract(
    dialect: str,
    expected: bool,
) -> None:
    assert supports_external_key_file_advisory(dialect) is expected


def test_get_remembered_target_cleanup_metadata_dispatches_through_factory_backend_seam(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}
    sentinel_metadata = BackendCleanupMetadata()

    def fake_sqlite_remembered_target_cleanup_metadata(
        database_path: str | PathLike[str],
    ) -> BackendCleanupMetadata:
        captured["database_path"] = database_path
        return sentinel_metadata

    monkeypatch.setitem(
        backend_policy_module._BACKEND_POLICIES,
        backend_policy_module.SQLITE_DIALECT,
        replace(
            backend_policy_module._BACKEND_POLICIES[backend_policy_module.SQLITE_DIALECT],
            cleanup_metadata_resolver=cast(
                CleanupMetadataResolver,
                fake_sqlite_remembered_target_cleanup_metadata,
            ),
        ),
    )

    metadata = get_remembered_target_cleanup_metadata(
        database_path="C:/Ops/eventlog.db",
        dialect="sqlite",
    )

    assert metadata is sentinel_metadata
    assert captured == {"database_path": "C:/Ops/eventlog.db"}


def test_load_database_config_reads_template_shaped_database_settings(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "config.ini"
    config_path.write_text(
        """
[DEFAULT]
db_type = SQLITE
require_key_file_for_creation = true
min_password_length = 12
secure_delete_passes = 5
kdf_iterations = 250000

[sqlite]
database_path = eventlog.db
require_key_file = true

[Logging]
log_level = INFO
        """.strip(),
        encoding="utf-8",
    )

    config = load_database_config(config_path)

    assert config == DatabaseConfig(
        dialect="sqlite",
        database_path="eventlog.db",
        require_key_file=True,
        require_key_file_for_creation=True,
        min_password_length=12,
        secure_delete_passes=5,
        kdf_iterations=250000,
    )
    assert config.bootstrap_target == BootstrapTargetConfig(
        dialect="sqlite",
        database_path="eventlog.db",
        require_key_file=True,
    )
    assert config.creation_defaults == DatabaseCreationDefaults(
        require_key_file_for_creation=True,
        min_password_length=12,
        secure_delete_passes=5,
        kdf_iterations=250000,
    )
    assert config.can_attempt_auto_open is True
    assert config.has_partial_bootstrap_memory is False


def test_parse_database_config_allows_technology_section_to_override_default_creation_policy() -> None:
    parser = ConfigParser()
    parser["DEFAULT"] = {
        "db_type": "sqlite",
        "min_password_length": "8",
        "require_key_file_for_creation": "false",
    }
    parser["sqlite"] = {
        "database_path": "eventlog.db",
        "min_password_length": "12",
        "require_key_file_for_creation": "true",
    }
    parser["Logging"] = {
        "log_level": "INFO",
    }

    assert parse_database_config(parser) == DatabaseConfig(
        dialect="sqlite",
        database_path="eventlog.db",
        require_key_file=False,
        require_key_file_for_creation=True,
        min_password_length=12,
        secure_delete_passes=3,
        kdf_iterations=100000,
    )


def test_load_app_config_and_parse_database_config_support_factory_consumers(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "factory-from-config.db"
    config_path = tmp_path / "config.ini"
    config_path.write_text(
        f"""
[DEFAULT]
db_type = sqlite

[sqlite]
database_path = {database_path}
        """.strip(),
        encoding="utf-8",
    )

    parser = load_app_config(config_path)
    database_config = parse_database_config(parser)
    assert database_config is not None

    repository = RepositoryFactory.create_event_log_repository(
        database_path=database_config.database_path,
        dialect=database_config.dialect,
    )
    try:
        assert isinstance(repository, BaseRepository)
        assert isinstance(repository, EventLogRepository)
        assert repository.database_path == str(database_path)
        assert _get_table_names(repository) == EXPECTED_TABLES
    finally:
        repository.close()


def test_parse_database_config_returns_none_when_no_supported_bootstrap_config_exists() -> None:
    missing_section_config = ConfigParser()

    assert parse_database_config(missing_section_config) is None

    unrelated_section_config = ConfigParser()
    unrelated_section_config["Logging"] = {"log_level": "INFO"}

    assert parse_database_config(unrelated_section_config) is None


def test_parse_database_config_does_not_infer_active_dialect_from_present_technology_section() -> None:
    inferred_sqlite_config = ConfigParser()
    inferred_sqlite_config["sqlite"] = {"database_path": "eventlog.db"}

    assert parse_database_config(inferred_sqlite_config) is None


def test_parse_database_config_ignores_unselected_technology_section_values() -> None:
    parser = ConfigParser()
    parser["DEFAULT"] = {
        "min_password_length": "12",
    }
    parser["sqlite"] = {
        "database_path": "eventlog.db",
        "require_key_file": "true",
    }

    assert parse_database_config(parser) == DatabaseConfig(
        dialect="",
        database_path="",
        require_key_file=False,
        require_key_file_for_creation=False,
        min_password_length=12,
        secure_delete_passes=3,
        kdf_iterations=100000,
    )


def test_parse_database_config_preserves_partial_remembered_bootstrap_values_for_recovery() -> None:
    missing_path_config = ConfigParser()
    missing_path_config["DEFAULT"] = {"db_type": "sqlite"}

    missing_path = parse_database_config(missing_path_config)

    assert missing_path == DatabaseConfig(
        dialect="sqlite",
        database_path="",
        require_key_file=False,
        min_password_length=8,
        secure_delete_passes=3,
        kdf_iterations=100000,
    )
    assert missing_path is not None
    assert missing_path.can_attempt_auto_open is False
    assert missing_path.has_partial_bootstrap_memory is True
    assert missing_path.bootstrap_target == BootstrapTargetConfig(
        dialect="sqlite",
        database_path="",
        require_key_file=False,
    )


def test_load_database_config_applies_security_defaults_when_optional_values_are_missing(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "config.ini"
    config_path.write_text(
        """
[DEFAULT]
db_type = sqlite

[sqlite]
database_path = eventlog.db
        """.strip(),
        encoding="utf-8",
    )

    config = load_database_config(config_path)

    assert config == DatabaseConfig(
        dialect="sqlite",
        database_path="eventlog.db",
        require_key_file=False,
        require_key_file_for_creation=False,
        min_password_length=8,
        secure_delete_passes=3,
        kdf_iterations=100000,
    )


def test_parse_database_config_accepts_stdlib_boolean_aliases_for_key_file_flag() -> None:
    parser = ConfigParser()
    parser["DEFAULT"] = {
        "db_type": "sqlite",
    }
    parser["sqlite"] = {
        "database_path": "eventlog.db",
        "require_key_file": "yes",
    }

    assert parse_database_config(parser) == DatabaseConfig(
        dialect="sqlite",
        database_path="eventlog.db",
        require_key_file=True,
        min_password_length=8,
        secure_delete_passes=3,
        kdf_iterations=100000,
    )


def test_parse_database_config_logs_invalid_boolean_field_and_uses_default(caplog: pytest.LogCaptureFixture) -> None:
    parser = ConfigParser()
    parser["DEFAULT"] = {"db_type": "sqlite"}
    parser["sqlite"] = {
        "database_path": "eventlog.db",
        "require_key_file": "maybe",
    }

    with caplog.at_level("WARNING"):
        config = parse_database_config(parser)

    assert config == DatabaseConfig(
        dialect="sqlite",
        database_path="eventlog.db",
        require_key_file=False,
        require_key_file_for_creation=False,
        min_password_length=8,
        secure_delete_passes=3,
        kdf_iterations=100000,
    )
    assert "sqlite.require_key_file" in caplog.text


def test_parse_database_config_logs_invalid_integer_field_and_uses_default(caplog: pytest.LogCaptureFixture) -> None:
    parser = ConfigParser()
    parser["DEFAULT"] = {
        "db_type": "sqlite",
        "min_password_length": "banana",
    }
    parser["sqlite"] = {
        "database_path": "eventlog.db",
    }

    with caplog.at_level("WARNING"):
        config = parse_database_config(parser)

    assert config == DatabaseConfig(
        dialect="sqlite",
        database_path="eventlog.db",
        require_key_file=False,
        require_key_file_for_creation=False,
        min_password_length=8,
        secure_delete_passes=3,
        kdf_iterations=100000,
    )
    assert "sqlite.min_password_length" in caplog.text


def test_parse_database_config_logs_out_of_range_secure_delete_passes_and_uses_default(
    caplog: pytest.LogCaptureFixture,
) -> None:
    parser = ConfigParser()
    parser["DEFAULT"] = {
        "db_type": "sqlite",
        "secure_delete_passes": "11",
    }
    parser["sqlite"] = {
        "database_path": "eventlog.db",
    }

    with caplog.at_level("WARNING"):
        config = parse_database_config(parser)

    assert config == DatabaseConfig(
        dialect="sqlite",
        database_path="eventlog.db",
        require_key_file=False,
        require_key_file_for_creation=False,
        min_password_length=8,
        secure_delete_passes=3,
        kdf_iterations=100000,
    )
    assert "sqlite.secure_delete_passes" in caplog.text
    assert "Out-of-range config value" in caplog.text


def test_parse_database_config_returns_default_policy_values_even_without_technology_section() -> None:
    parser = ConfigParser()
    parser["DEFAULT"] = {
        "require_key_file_for_creation": "true",
        "min_password_length": "12",
        "secure_delete_passes": "5",
        "kdf_iterations": "250000",
    }

    config = parse_database_config(parser)

    assert config == DatabaseConfig(
        dialect="",
        database_path="",
        require_key_file=False,
        require_key_file_for_creation=True,
        min_password_length=12,
        secure_delete_passes=5,
        kdf_iterations=250000,
    )
    assert config is not None
    assert config.bootstrap_target == BootstrapTargetConfig()
    assert config.creation_defaults == DatabaseCreationDefaults(
        require_key_file_for_creation=True,
        min_password_length=12,
        secure_delete_passes=5,
        kdf_iterations=250000,
    )
    assert config.can_attempt_auto_open is False
    assert config.has_partial_bootstrap_memory is False


def test_load_database_config_returns_none_for_removed_database_security_sections(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "config.ini"
    config_path.write_text(
        """
[Database]
db_type = sqlite
require_key_file = yes

[Security]
min_password_length = 12
        """.strip(),
        encoding="utf-8",
    )

    assert load_database_config(config_path) is None


def test_load_database_config_returns_none_for_removed_db_file_path_option_name(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "config.ini"
    config_path.write_text(
        """
[DEFAULT]
db_type = sqlite

[sqlite]
db_file_path = eventlog.db
        """.strip(),
        encoding="utf-8",
    )

    assert load_database_config(config_path) == DatabaseConfig(
        dialect="sqlite",
        database_path="",
        require_key_file=False,
        require_key_file_for_creation=False,
        min_password_length=8,
        secure_delete_passes=3,
        kdf_iterations=100000,
    )


def test_parse_database_config_keeps_remembered_key_file_hint_separate_from_create_policy() -> None:
    parser = ConfigParser()
    parser["DEFAULT"] = {
        "db_type": "sqlite",
        "require_key_file_for_creation": "no",
    }
    parser["sqlite"] = {
        "database_path": "eventlog.db",
        "require_key_file": "yes",
    }

    assert parse_database_config(parser) == DatabaseConfig(
        dialect="sqlite",
        database_path="eventlog.db",
        require_key_file=True,
        require_key_file_for_creation=False,
        min_password_length=8,
        secure_delete_passes=3,
        kdf_iterations=100000,
    )


@pytest.mark.parametrize(
    ("config_text", "expected_config"),
    [
        (
            """
[DEFAULT]
db_type = sqlite

[sqlite]
database_path = eventlog.db
require_key_file = maybe
            """.strip(),
            DatabaseConfig(
                dialect="sqlite",
                database_path="eventlog.db",
                require_key_file=False,
                require_key_file_for_creation=False,
                min_password_length=8,
                secure_delete_passes=3,
                kdf_iterations=100000,
            ),
        ),
        (
            """
[DEFAULT]
db_type = sqlite
min_password_length = 7

[sqlite]
database_path = eventlog.db
            """.strip(),
            DatabaseConfig(
                dialect="sqlite",
                database_path="eventlog.db",
                require_key_file=False,
                require_key_file_for_creation=False,
                min_password_length=7,
                secure_delete_passes=3,
                kdf_iterations=100000,
            ),
        ),
        (
            """
[DEFAULT]
db_type = sqlite
secure_delete_passes = 0

[sqlite]
database_path = eventlog.db
            """.strip(),
            DatabaseConfig(
                dialect="sqlite",
                database_path="eventlog.db",
                require_key_file=False,
                require_key_file_for_creation=False,
                min_password_length=8,
                secure_delete_passes=0,
                kdf_iterations=100000,
            ),
        ),
        (
            """
[DEFAULT]
db_type = sqlite
secure_delete_passes = 11

[sqlite]
database_path = eventlog.db
            """.strip(),
            DatabaseConfig(
                dialect="sqlite",
                database_path="eventlog.db",
                require_key_file=False,
                require_key_file_for_creation=False,
                min_password_length=8,
                secure_delete_passes=3,
                kdf_iterations=100000,
            ),
        ),
        (
            """
[DEFAULT]
db_type = sqlite
secure_delete_passes = many

[sqlite]
database_path = eventlog.db
            """.strip(),
            DatabaseConfig(
                dialect="sqlite",
                database_path="eventlog.db",
                require_key_file=False,
                require_key_file_for_creation=False,
                min_password_length=8,
                secure_delete_passes=3,
                kdf_iterations=100000,
            ),
        ),
        (
            """
[DEFAULT]
db_type = sqlite

[sqlite]
database_path = eventlog.db
require_key_file = yes
            """.strip(),
            DatabaseConfig(
                dialect="sqlite",
                database_path="eventlog.db",
                require_key_file=True,
                require_key_file_for_creation=False,
                min_password_length=8,
                secure_delete_passes=3,
                kdf_iterations=100000,
            ),
        ),
        (
            """
[DEFAULT]
db_type = sqlite
kdf_iterations = 99999

[sqlite]
database_path = eventlog.db
            """.strip(),
            DatabaseConfig(
                dialect="sqlite",
                database_path="eventlog.db",
                require_key_file=False,
                require_key_file_for_creation=False,
                min_password_length=8,
                secure_delete_passes=3,
                kdf_iterations=99999,
            ),
        ),
        (
            """
[DEFAULT]
min_password_length = banana
secure_delete_passes = zero
kdf_iterations = nope
            """.strip(),
            DatabaseConfig(
                dialect="",
                database_path="",
                require_key_file=False,
                require_key_file_for_creation=False,
                min_password_length=8,
                secure_delete_passes=3,
                kdf_iterations=100000,
            ),
        ),
    ],
)
def test_load_database_config_recovers_from_invalid_bootstrap_contract_values(
    tmp_path: Path,
    config_text: str,
    expected_config: DatabaseConfig,
) -> None:
    config_path = tmp_path / "config.ini"
    config_path.write_text(config_text, encoding="utf-8")

    assert load_database_config(config_path) == expected_config


def test_load_app_config_returns_empty_parser_for_missing_file(tmp_path: Path) -> None:
    missing_path = tmp_path / "missing.ini"
    parser = load_app_config(missing_path)

    assert isinstance(parser, ConfigParser)
    assert parser.sections() == []


def test_load_database_config_returns_none_for_missing_file(tmp_path: Path) -> None:
    missing_path = tmp_path / "missing.ini"

    assert load_database_config(missing_path) is None


def test_load_bootstrap_ui_config_returns_code_defaults_for_missing_file(tmp_path: Path) -> None:
    missing_path = tmp_path / "missing.ini"

    assert load_bootstrap_ui_config(missing_path) == BootstrapUiConfig(
        main_window=MainWindowConfig(
            window_state="normal",
            window_width=1200,
            window_height=700,
            window_x=100,
            window_y=100,
        ),
        language="sv",
        last_operator="",
    )


def test_load_bootstrap_ui_config_reads_application_and_user_sections(tmp_path: Path) -> None:
    config_path = tmp_path / "config.ini"
    config_path.write_text(
        """
[Application]
window_state = zoomed
window_width = 1366
window_height = 768
window_x = 15
window_y = 25
language = EN

[User]
last_operator = Sgt Example
        """.strip(),
        encoding="utf-8",
    )

    assert load_bootstrap_ui_config(config_path) == BootstrapUiConfig(
        main_window=MainWindowConfig(
            window_state="zoomed",
            window_width=1366,
            window_height=768,
            window_x=15,
            window_y=25,
        ),
        language="en",
        last_operator="Sgt Example",
    )


def test_parse_bootstrap_ui_config_logs_malformed_values_and_uses_defaults(
    caplog: pytest.LogCaptureFixture,
) -> None:
    parser = ConfigParser()
    parser["Application"] = {
        "window_state": "fullscreen",
        "window_width": "wide",
        "window_height": "0",
        "window_x": "left",
        "window_y": "200",
        "language": "   ",
    }
    parser["User"] = {
        "last_operator": "  Sgt Example  ",
    }

    with caplog.at_level("WARNING"):
        config = parse_bootstrap_ui_config(parser)

    assert config == BootstrapUiConfig(
        main_window=MainWindowConfig(
            window_state="normal",
            window_width=1200,
            window_height=700,
            window_x=100,
            window_y=200,
        ),
        language="sv",
        last_operator="Sgt Example",
    )
    assert "Application.window_state" in caplog.text
    assert "Application.window_width" in caplog.text
    assert "Application.window_height" in caplog.text
    assert "Application.window_x" in caplog.text



def test_create_in_memory_repository_returns_initialized_working_repository() -> None:
    repository = RepositoryFactory.create_in_memory_repository()
    try:
        assert isinstance(repository, BaseRepository)
        assert isinstance(repository, EventLogRepository)
        assert repository.database_path == ":memory:"
        assert _get_table_names(repository) == EXPECTED_TABLES

        entry_id = repository.create_communication_entry(
            CommunicationEntry(
                message_content="Factory-created message",
                operator="Operator One",
            )
        )

        loaded = repository.get_communication_entry(entry_id)

        assert loaded is not None
        assert loaded.message_content == "Factory-created message"
        assert loaded.operator == "Operator One"
    finally:
        repository.close()


def test_create_in_memory_repository_forwards_memory_target_and_encryption_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    encryption_key = bytes.fromhex(
        "ffeeddccbbaa99887766554433221100ffeeddccbbaa99887766554433221100"
    )
    captured: dict[str, object] = {}
    sentinel_repository = object()

    def fake_create_event_log_repository(
        *,
        database_path: str,
        dialect: str = repository_factory_module.SQLITE_DIALECT,
        encryption_key: bytes | None = None,
    ) -> object:
        captured["database_path"] = database_path
        captured["dialect"] = dialect
        captured["encryption_key"] = encryption_key
        return sentinel_repository

    monkeypatch.setattr(
        RepositoryFactory,
        "create_event_log_repository",
        staticmethod(fake_create_event_log_repository),
    )

    repository = RepositoryFactory.create_in_memory_repository(encryption_key=encryption_key)

    assert repository is sentinel_repository
    assert captured == {
        "database_path": ":memory:",
        "dialect": repository_factory_module.SQLITE_DIALECT,
        "encryption_key": encryption_key,
    }


def test_create_event_log_repository_rejects_unsupported_dialect() -> None:
    with pytest.raises(WrongDatabaseAdapter, match="Unsupported repository dialect"):
        RepositoryFactory.create_event_log_repository(
            database_path=":memory:",
            dialect="postgres",
        )


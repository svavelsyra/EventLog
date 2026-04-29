from configparser import ConfigParser
from pathlib import Path

import pytest

from src.config import DatabaseConfig, load_app_config, load_database_config, parse_database_config
from src.core.entries import CommunicationEntry
from src.db.database_adapter import WrongDatabaseAdapter
from src.db.repositories.base_repository import BaseRepository
from src.db.repositories.repository_factory import RepositoryFactory
from src.db.repositories.sqlite.event_log_repository import EventLogRepository


pytestmark = pytest.mark.unit

EXPECTED_TABLES = {
    "communication_entries",
    "event_entries",
    "personnel_entries",
    "settings",
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


def test_load_database_config_reads_template_shaped_database_settings(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "config.ini"
    config_path.write_text(
        """
[Database]
db_file_path = eventlog.db
db_type = SQLITE

[Logging]
log_level = INFO
        """.strip(),
        encoding="utf-8",
    )

    config = load_database_config(config_path)

    assert config == DatabaseConfig(dialect="sqlite", database_path="eventlog.db")


def test_load_app_config_and_parse_database_config_support_factory_consumers(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "factory-from-config.db"
    config_path = tmp_path / "config.ini"
    config_path.write_text(
        f"""
[Database]
db_file_path = {database_path}
db_type = sqlite
        """.strip(),
        encoding="utf-8",
    )

    parser = load_app_config(config_path)
    database_config = parse_database_config(parser)

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


def test_parse_database_config_rejects_missing_or_blank_required_values() -> None:
    missing_section_config = ConfigParser()

    assert parse_database_config(missing_section_config) is None

    blank_value_config = ConfigParser()
    blank_value_config["Database"] = {"db_type": "sqlite", "db_file_path": "   "}

    assert parse_database_config(blank_value_config) is None


def test_parse_database_config_returns_none_for_partially_configured_database_section() -> None:
    missing_dialect_config = ConfigParser()
    missing_dialect_config["Database"] = {"db_file_path": "eventlog.db"}

    missing_path_config = ConfigParser()
    missing_path_config["Database"] = {"db_type": "sqlite"}

    assert parse_database_config(missing_dialect_config) is None
    assert parse_database_config(missing_path_config) is None


def test_load_app_config_returns_empty_parser_for_missing_file(tmp_path: Path) -> None:
    missing_path = tmp_path / "missing.ini"
    parser = load_app_config(missing_path)

    assert isinstance(parser, ConfigParser)
    assert parser.sections() == []


def test_load_database_config_returns_none_for_missing_file(tmp_path: Path) -> None:
    missing_path = tmp_path / "missing.ini"

    assert load_database_config(missing_path) is None


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


def test_create_event_log_repository_rejects_unsupported_dialect() -> None:
    with pytest.raises(WrongDatabaseAdapter, match="Unsupported repository dialect"):
        RepositoryFactory.create_event_log_repository(
            database_path=":memory:",
            dialect="postgres",
        )


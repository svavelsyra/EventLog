from pathlib import Path

import pytest

from src.config import DatabaseConfig
from src.db import sqlite_target_resolver
from src.db.repositories.bootstrap_backend_policy import resolve_runtime_database_config


pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("database_path", "expected_database_path"),
    [
        ("", ""),
        (":memory:", ":memory:"),
    ],
)
def test_resolve_sqlite_runtime_database_config_preserves_special_non_file_targets(
    tmp_path: Path,
    database_path: str,
    expected_database_path: str,
) -> None:
    config = DatabaseConfig(dialect="sqlite", database_path=database_path)
    config_path = tmp_path / "config.ini"

    resolved = sqlite_target_resolver.resolve_runtime_database_config(config, config_path=config_path)

    assert resolved == DatabaseConfig(dialect="sqlite", database_path=expected_database_path)


def test_resolve_sqlite_runtime_database_config_preserves_absolute_path(tmp_path: Path) -> None:
    absolute_database_path = str((tmp_path / "eventlog.db").resolve())
    config = DatabaseConfig(dialect="sqlite", database_path=absolute_database_path)
    config_path = tmp_path / "config.ini"

    resolved = sqlite_target_resolver.resolve_runtime_database_config(config, config_path=config_path)

    assert resolved is config


def test_resolve_sqlite_runtime_database_config_resolves_relative_path_against_config_location(
    tmp_path: Path,
) -> None:
    config_directory = tmp_path / "instance"
    config_directory.mkdir()
    config = DatabaseConfig(dialect="sqlite", database_path="data/eventlog.db")
    config_path = config_directory / "config.ini"

    resolved = sqlite_target_resolver.resolve_runtime_database_config(config, config_path=config_path)

    assert resolved == DatabaseConfig(
        dialect="sqlite",
        database_path=str((config_directory / "data" / "eventlog.db").resolve()),
    )


def test_resolve_runtime_database_config_dispatches_to_sqlite_owned_resolver(tmp_path: Path) -> None:
    config_directory = tmp_path / "instance"
    config_directory.mkdir()
    config = DatabaseConfig(dialect="sqlite", database_path="eventlog.db")
    config_path = config_directory / "config.ini"

    resolved = resolve_runtime_database_config(config, config_path=config_path)

    assert resolved == DatabaseConfig(
        dialect="sqlite",
        database_path=str((config_directory / "eventlog.db").resolve()),
    )


def test_resolve_runtime_database_config_returns_config_unchanged_for_unknown_dialect(tmp_path: Path) -> None:
    config = DatabaseConfig(dialect="postgres", database_path="postgresql://example")
    config_path = tmp_path / "config.ini"

    resolved = resolve_runtime_database_config(config, config_path=config_path)

    assert resolved is config


from pathlib import Path

import pytest

from src.config import DatabaseConfig
from src.config.app_config import DEFAULT_LOG_FILE_PATH
from src.db import sqlite_target_resolver
from src.db.repositories.bootstrap_backend_policy import resolve_runtime_database_config


pytestmark = pytest.mark.unit


def test_runtime_data_paths_use_simple_data_folder_layout(tmp_path: Path) -> None:
    app_root = tmp_path / "portable-eventlog"
    config_path = app_root / "data" / "config.ini"

    assert config_path == app_root / "data" / "config.ini"
    assert sqlite_target_resolver.resolve_runtime_database_config(
        DatabaseConfig(dialect="sqlite"),
        config_path=config_path,
    ).database_path == str((app_root / "data" / "eventlog.db").resolve())
    assert config_path.parent / Path(DEFAULT_LOG_FILE_PATH) == app_root / "data" / "logs" / "eventlog.log"


def test_runtime_data_paths_move_consistently_with_the_app_folder(tmp_path: Path) -> None:
    original_root = tmp_path / "original-app"
    moved_root = tmp_path / "moved-app"
    original_config_path = original_root / "data" / "config.ini"
    moved_config_path = moved_root / "data" / "config.ini"

    assert sqlite_target_resolver.resolve_runtime_database_config(
        DatabaseConfig(dialect="sqlite"),
        config_path=original_config_path,
    ).database_path == str((original_root / "data" / "eventlog.db").resolve())
    assert sqlite_target_resolver.resolve_runtime_database_config(
        DatabaseConfig(dialect="sqlite"),
        config_path=moved_config_path,
    ).database_path == str((moved_root / "data" / "eventlog.db").resolve())


@pytest.mark.parametrize(
    "database_path",
    [
        "",
        ":memory:",
        "data/remembered.db",
    ],
)
def test_resolve_sqlite_runtime_database_config_ignores_remembered_target_text_and_uses_managed_path(
    tmp_path: Path,
    database_path: str,
) -> None:
    config = DatabaseConfig(dialect="sqlite", database_path=database_path)
    config_path = tmp_path / "config.ini"

    resolved = sqlite_target_resolver.resolve_runtime_database_config(config, config_path=config_path)

    assert resolved == DatabaseConfig(
        dialect="sqlite",
        database_path=str((config_path.parent / "eventlog.db").resolve()),
    )


def test_resolve_sqlite_runtime_database_config_preserves_existing_managed_path_instance(tmp_path: Path) -> None:
    config_path = tmp_path / "config.ini"
    config = DatabaseConfig(
        dialect="sqlite",
        database_path=str((config_path.parent / "eventlog.db").resolve()),
    )

    resolved = sqlite_target_resolver.resolve_runtime_database_config(config, config_path=config_path)

    assert resolved is config


def test_resolve_sqlite_runtime_database_config_replaces_arbitrary_absolute_target_with_managed_path(
    tmp_path: Path,
) -> None:
    config_directory = tmp_path / "instance"
    config_directory.mkdir()
    config = DatabaseConfig(dialect="sqlite", database_path=str((tmp_path / "other.db").resolve()))
    config_path = config_directory / "config.ini"

    resolved = sqlite_target_resolver.resolve_runtime_database_config(config, config_path=config_path)

    assert resolved == DatabaseConfig(
        dialect="sqlite",
        database_path=str((config_path.parent / "eventlog.db").resolve()),
    )


def test_resolve_runtime_database_config_dispatches_to_sqlite_owned_resolver(tmp_path: Path) -> None:
    config_directory = tmp_path / "instance"
    config_directory.mkdir()
    config = DatabaseConfig(dialect="sqlite", database_path="remembered.db")
    config_path = config_directory / "config.ini"

    resolved = resolve_runtime_database_config(config, config_path=config_path)

    assert resolved == DatabaseConfig(
        dialect="sqlite",
        database_path=str((config_path.parent / "eventlog.db").resolve()),
    )


def test_resolve_runtime_database_config_returns_config_unchanged_for_unknown_dialect(tmp_path: Path) -> None:
    config = DatabaseConfig(dialect="postgres", database_path="postgresql://example")
    config_path = tmp_path / "config.ini"

    resolved = resolve_runtime_database_config(config, config_path=config_path)

    assert resolved is config


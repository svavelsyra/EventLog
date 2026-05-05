from pathlib import Path

import pytest

from src.config import (
    DatabaseConfig,
    load_app_config,
    load_database_config,
    save_bootstrap_section_options,
)
from src.config.app_config import BootstrapTargetConfig
from src.db import sqlite_target_serializer
from src.db.repositories.bootstrap_backend_policy import save_bootstrap_target_config


pytestmark = pytest.mark.unit


def test_serialize_sqlite_bootstrap_target_options_returns_sqlite_owned_mapping() -> None:
    target = BootstrapTargetConfig(
        dialect="sqlite",
        database_path="eventlog.db",
        require_key_file=True,
    )

    assert dict(sqlite_target_serializer.serialize_options(target)) == {
        "database_path": "eventlog.db",
        "require_key_file": "true",
    }


def test_save_bootstrap_target_config_writes_remembered_fields_and_round_trips(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "config.ini"

    save_bootstrap_target_config(
        config_path,
        BootstrapTargetConfig(
            dialect=" SQLITE ",
            database_path="  eventlog.db  ",
            require_key_file=True,
        ),
    )

    parser = load_app_config(config_path)

    assert parser.get(parser.default_section, "db_type") == "sqlite"
    assert parser.get("sqlite", "database_path") == "eventlog.db"
    assert parser.getboolean("sqlite", "require_key_file") is True
    assert load_database_config(config_path) == DatabaseConfig(
        dialect="sqlite",
        database_path="eventlog.db",
        require_key_file=True,
        require_key_file_for_creation=False,
        min_password_length=8,
        secure_delete_passes=3,
        kdf_iterations=100000,
    )


def test_save_bootstrap_target_config_preserves_unrelated_sections_and_creation_defaults(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "config.ini"
    config_path.write_text(
        """
[DEFAULT]
db_type = sqlite
require_key_file_for_creation = true
min_password_length = 12
secure_delete_passes = 5
kdf_iterations = 250000

[sqlite]
database_path = old-eventlog.db
require_key_file = true
min_password_length = 20

[Logging]
log_level = INFO
        """.strip(),
        encoding="utf-8",
    )

    save_bootstrap_target_config(
        config_path,
        BootstrapTargetConfig(
            dialect="sqlite",
            database_path="new-eventlog.db",
            require_key_file=False,
        ),
    )

    parser = load_app_config(config_path)

    assert parser.get(parser.default_section, "db_type") == "sqlite"
    assert parser.get(parser.default_section, "require_key_file_for_creation") == "true"
    assert parser.get(parser.default_section, "min_password_length") == "12"
    assert parser.get(parser.default_section, "secure_delete_passes") == "5"
    assert parser.get(parser.default_section, "kdf_iterations") == "250000"
    assert parser.get("sqlite", "database_path") == "new-eventlog.db"
    assert parser.getboolean("sqlite", "require_key_file") is False
    assert parser.get("sqlite", "min_password_length") == "20"
    assert parser.get("Logging", "log_level") == "INFO"
    assert parser.has_option("sqlite", "key_file_path") is False
    assert load_database_config(config_path) == DatabaseConfig(
        dialect="sqlite",
        database_path="new-eventlog.db",
        require_key_file=False,
        require_key_file_for_creation=True,
        min_password_length=20,
        secure_delete_passes=5,
        kdf_iterations=250000,
    )


def test_save_bootstrap_target_config_with_empty_target_clears_stale_remembered_selectors_only(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "config.ini"
    config_path.write_text(
        """
[DEFAULT]
db_type = sqlite
require_key_file_for_creation = true
min_password_length = 12
secure_delete_passes = 5
kdf_iterations = 250000

[sqlite]
database_path = old-eventlog.db
require_key_file = true
min_password_length = 20

[Logging]
log_level = INFO

[Application]
language = sv
        """.strip(),
        encoding="utf-8",
    )

    save_bootstrap_target_config(config_path, BootstrapTargetConfig())

    parser = load_app_config(config_path)

    assert parser.has_option(parser.default_section, "db_type") is False
    assert parser.get(parser.default_section, "require_key_file_for_creation") == "true"
    assert parser.get(parser.default_section, "min_password_length") == "12"
    assert parser.get(parser.default_section, "secure_delete_passes") == "5"
    assert parser.get(parser.default_section, "kdf_iterations") == "250000"
    assert parser.has_option("sqlite", "database_path") is False
    assert parser.has_option("sqlite", "require_key_file") is False
    assert parser.get("sqlite", "min_password_length") == "20"
    assert parser.get("Logging", "log_level") == "INFO"
    assert parser.get("Application", "language") == "sv"
    assert load_database_config(config_path) == DatabaseConfig(
        dialect="",
        database_path="",
        require_key_file=False,
        require_key_file_for_creation=True,
        min_password_length=12,
        secure_delete_passes=5,
        kdf_iterations=250000,
    )


def test_save_bootstrap_target_config_clears_explicitly_declared_option_names_not_serializer_shape(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "config.ini"
    config_path.write_text(
        """
[DEFAULT]
db_type = sqlite

[sqlite]
database_path = old-eventlog.db
require_key_file = true
transient_serializer_only = should-stay
        """.strip(),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        sqlite_target_serializer,
        "serialize_options",
        lambda target: {
            "database_path": target.database_path,
            "require_key_file": "true" if target.require_key_file else "false",
            "transient_serializer_only": "unexpected",
        },
    )
    monkeypatch.setattr(
        sqlite_target_serializer,
        "removable_option_names",
        lambda: ("database_path", "require_key_file"),
    )

    save_bootstrap_target_config(config_path, BootstrapTargetConfig())

    parser = load_app_config(config_path)

    assert parser.has_option("sqlite", "database_path") is False
    assert parser.has_option("sqlite", "require_key_file") is False
    assert parser.get("sqlite", "transient_serializer_only") == "should-stay"


def test_save_bootstrap_target_config_persists_only_selected_dialect_for_unknown_backend(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "config.ini"

    save_bootstrap_target_config(
        config_path,
        BootstrapTargetConfig(
            dialect="custom",
            database_path="should-not-be-written",
            require_key_file=True,
        ),
    )

    parser = load_app_config(config_path)

    assert parser.get(parser.default_section, "db_type") == "custom"
    assert parser.has_section("custom") is False
    assert load_database_config(config_path) == DatabaseConfig(
        dialect="custom",
        database_path="",
        require_key_file=False,
        require_key_file_for_creation=False,
        min_password_length=8,
        secure_delete_passes=3,
        kdf_iterations=100000,
    )


def test_save_bootstrap_section_options_writes_generic_remembered_option_mapping(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "config.ini"
    config_path.write_text(
        """
[DEFAULT]
require_key_file_for_creation = true

[custom]
min_password_length = 14

[Logging]
log_level = INFO
        """.strip(),
        encoding="utf-8",
    )

    save_bootstrap_section_options(
        config_path,
        dialect=" custom ",
        remembered_section_options={
            "profile_name": " ops-main ",
            "instance_id": " alpha-1 ",
        },
    )

    parser = load_app_config(config_path)

    assert parser.get(parser.default_section, "db_type") == "custom"
    assert parser.get(parser.default_section, "require_key_file_for_creation") == "true"
    assert parser.get("custom", "profile_name") == "ops-main"
    assert parser.get("custom", "instance_id") == "alpha-1"
    assert parser.get("custom", "min_password_length") == "14"
    assert parser.get("Logging", "log_level") == "INFO"
    assert parser.has_option("custom", "database_path") is False


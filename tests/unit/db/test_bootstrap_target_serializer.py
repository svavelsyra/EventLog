from pathlib import Path

import pytest

from src.config import (
    BootstrapUiConfig,
    DatabaseConfig,
    MainWindowConfig,
    load_app_config,
    load_bootstrap_ui_config,
    load_database_config,
    render_config_template,
    save_bootstrap_ui_config,
    save_bootstrap_section_options,
    write_config_template,
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


def test_save_bootstrap_target_preserves_sections_and_creation_defaults(
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


def test_empty_bootstrap_target_clears_selectors_but_keeps_ui_data(
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

[User]
last_operator = Sgt Example
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
    assert parser.get("User", "last_operator") == "Sgt Example"
    assert load_database_config(config_path) == DatabaseConfig(
        dialect="",
        database_path="",
        require_key_file=False,
        require_key_file_for_creation=True,
        min_password_length=12,
        secure_delete_passes=5,
        kdf_iterations=250000,
    )
    assert load_bootstrap_ui_config(config_path) == BootstrapUiConfig(
        main_window=MainWindowConfig(),
        language="sv",
        last_operator="Sgt Example",
    )


def test_empty_bootstrap_target_clears_only_removable_option_names(
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


def test_unknown_backend_target_persists_selected_dialect_only(
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


def test_save_bootstrap_ui_writes_sections_and_round_trips(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "config.ini"
    config_path.write_text(
        """
[DEFAULT]
db_type = sqlite

[sqlite]
database_path = eventlog.db

[Logging]
log_level = INFO
        """.strip(),
        encoding="utf-8",
    )

    save_bootstrap_ui_config(
        config_path,
        BootstrapUiConfig(
            main_window=MainWindowConfig(
                window_state="zoomed",
                window_width=1440,
                window_height=900,
                window_x=20,
                window_y=40,
            ),
            language="EN",
            last_operator="  Sgt Example  ",
        ),
    )

    parser = load_app_config(config_path)

    assert parser.get(parser.default_section, "db_type") == "sqlite"
    assert parser.get("sqlite", "database_path") == "eventlog.db"
    assert parser.get("Logging", "log_level") == "INFO"
    assert parser.get("Application", "window_state") == "zoomed"
    assert parser.get("Application", "window_width") == "1440"
    assert parser.get("Application", "window_height") == "900"
    assert parser.get("Application", "window_x") == "20"
    assert parser.get("Application", "window_y") == "40"
    assert parser.get("Application", "language") == "en"
    assert parser.get("User", "last_operator") == "Sgt Example"
    assert load_bootstrap_ui_config(config_path) == BootstrapUiConfig(
        main_window=MainWindowConfig(
            window_state="zoomed",
            window_width=1440,
            window_height=900,
            window_x=20,
            window_y=40,
        ),
        language="en",
        last_operator="Sgt Example",
    )


def test_render_config_template_emits_canonical_sections_defaults_and_comments(
    tmp_path: Path,
) -> None:
    template_text = render_config_template()
    template_path = tmp_path / "config.ini.template"
    template_path.write_text(template_text, encoding="utf-8")

    parser = load_app_config(template_path)

    assert template_text.startswith("# EventLog Application Configuration Template\n")
    assert "# NEVER store passwords, derived keys, raw key-file content, or remembered key-file paths" in template_text
    assert parser.get(parser.default_section, "db_type") == "sqlite"
    assert parser.getboolean(parser.default_section, "require_key_file_for_creation") is False
    assert parser.getint(parser.default_section, "min_password_length") == 8
    assert parser.getint(parser.default_section, "secure_delete_passes") == 3
    assert parser.getint(parser.default_section, "kdf_iterations") == 100000
    assert parser.get("sqlite", "database_path") == "eventlog.db"
    assert parser.getboolean("sqlite", "require_key_file") is False
    assert parser.get("Logging", "log_level") == "INFO"
    assert parser.getboolean("Logging", "file_logging_enabled") is True
    assert parser.get("Logging", "log_file_path") == "logs/eventlog.log"
    assert parser.getint("Logging", "log_file_max_bytes") == 10485760
    assert parser.getint("Logging", "log_file_backup_count") == 5
    assert parser.getboolean("Logging", "console_logging_enabled") is True
    assert parser.get("Logging", "console_log_level") == "WARNING"
    assert parser.get("Logging", "status_bar_log_level") == "WARNING"
    assert parser.get("Logging", "log_format") == "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    assert parser.get("Logging", "date_format") == "%Y-%m-%d %H:%M:%S"
    assert parser.get("Application", "window_state") == "normal"
    assert parser.getint("Application", "window_width") == 1200
    assert parser.getint("Application", "window_height") == 700
    assert parser.getint("Application", "window_x") == 100
    assert parser.getint("Application", "window_y") == 100
    assert parser.get("Application", "language") == "sv"
    assert parser.get("User", "last_operator") == ""


def test_write_config_template_overwrites_existing_file_with_canonical_content(
    tmp_path: Path,
) -> None:
    template_path = tmp_path / "config.ini.template"
    template_path.write_text("outdated = true\n", encoding="utf-8")

    written_path = write_config_template(template_path)

    assert written_path == template_path
    assert template_path.read_text(encoding="utf-8") == render_config_template()



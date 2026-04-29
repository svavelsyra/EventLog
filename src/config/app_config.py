"""Reusable application configuration loading helpers for EventLog."""

from __future__ import annotations

from configparser import ConfigParser
from dataclasses import dataclass
from os import PathLike
from pathlib import Path

DATABASE_SECTION = "Database"


@dataclass(frozen=True, slots=True)
class DatabaseConfig:
    """Optional bootstrap database hints parsed from application configuration."""

    dialect: str | None = None
    database_path: str | None = None



def load_app_config(config_path: str | PathLike[str]) -> ConfigParser:
    """Read an INI configuration file and return the parsed config object."""
    parser = ConfigParser(inline_comment_prefixes=("#", ";"))
    normalized_path = Path(config_path).expanduser()

    if not normalized_path.exists():
        return parser

    loaded_paths = parser.read(normalized_path, encoding="utf-8")

    if not loaded_paths:
        raise FileNotFoundError(f"Could not read configuration file: {normalized_path}")

    return parser



def parse_database_config(parser: ConfigParser) -> DatabaseConfig | None:
    """Extract optional bootstrap database settings from a parsed config."""
    if not parser.has_section(DATABASE_SECTION):
        return None

    dialect = parser.get(DATABASE_SECTION, "db_type", fallback="").strip().lower()
    database_path = parser.get(DATABASE_SECTION, "db_file_path", fallback="").strip()

    if not dialect and not database_path:
        return None

    if not dialect or not database_path:
        return None

    return DatabaseConfig(dialect=dialect, database_path=database_path)



def load_database_config(config_path: str | PathLike[str]) -> DatabaseConfig | None:
    """Load and normalize optional bootstrap database settings from an INI file path."""
    return parse_database_config(load_app_config(config_path))


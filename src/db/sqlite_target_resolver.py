"""SQLite-owned bootstrap target normalization helpers.

This module owns SQLite-specific interpretation of remembered bootstrap target
values after generic config parsing has completed.
"""

from __future__ import annotations

from dataclasses import replace
from os import PathLike
from pathlib import Path

from src.config import DatabaseConfig


def resolve_runtime_database_config(
    database_config: DatabaseConfig,
    *,
    config_path: str | PathLike[str],
) -> DatabaseConfig:
    """Return runtime-ready config for the SQLite backend."""
    resolved_database_path = _resolve_database_path_from_config(
        database_config.database_path,
        config_path=config_path,
    )
    if resolved_database_path == database_config.database_path:
        return database_config

    return replace(database_config, database_path=resolved_database_path)


def _resolve_database_path_from_config(
    database_path: str,
    *,
    config_path: str | PathLike[str],
) -> str:
    """Resolve SQLite file targets relative to the loaded config file location."""
    normalized_database_path = database_path.strip()
    if not normalized_database_path or normalized_database_path == ":memory:":
        return normalized_database_path

    normalized_path = Path(normalized_database_path).expanduser()
    if normalized_path.is_absolute():
        return str(normalized_path)

    config_directory = Path(config_path).expanduser().resolve().parent
    return str((config_directory / normalized_path).resolve())


__all__ = ["resolve_runtime_database_config"]



"""SQLite-owned bootstrap target normalization helpers.

This module owns SQLite-specific interpretation of remembered bootstrap target
values after generic config parsing has completed.
"""

from __future__ import annotations

from dataclasses import replace
from os import PathLike
from pathlib import Path

from src.config import DatabaseConfig


_MANAGED_SQLITE_DATABASE_FILENAME = "eventlog.db"


def _resolve_managed_sqlite_database_path(config_path: str | PathLike[str]) -> str:
    """Return the SQLite-owned managed database path next to the active config file."""
    normalized_config_path = Path(config_path).expanduser().resolve()
    return str((normalized_config_path.parent / _MANAGED_SQLITE_DATABASE_FILENAME).resolve())


def resolve_runtime_database_config(
    database_config: DatabaseConfig,
    *,
    config_path: str | PathLike[str],
) -> DatabaseConfig:
    """Return runtime-ready config for the SQLite backend."""
    resolved_database_path = _resolve_managed_sqlite_database_path(config_path)
    if resolved_database_path == database_config.database_path:
        return database_config

    return replace(database_config, database_path=resolved_database_path)



__all__ = ["resolve_runtime_database_config"]



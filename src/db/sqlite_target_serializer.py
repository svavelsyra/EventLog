"""SQLite-owned bootstrap target serialization helpers.

This module owns SQLite-specific serialization of remembered bootstrap target
values before they are persisted through the generic config-layer INI writer.
"""

from __future__ import annotations

from collections.abc import Mapping

from src.config.app_config import BootstrapTargetConfig


REMEMBERED_OPTION_NAMES = ("database_path", "require_key_file")


def serialize_options(target: BootstrapTargetConfig) -> Mapping[str, str]:
    """Return SQLite-owned remembered bootstrap option strings."""
    return {
        "database_path": target.database_path,
        "require_key_file": "true" if target.require_key_file else "false",
    }


def removable_option_names() -> tuple[str, ...]:
    """Return the explicit SQLite-owned remembered option names cleared on reset."""
    return REMEMBERED_OPTION_NAMES


__all__ = ["REMEMBERED_OPTION_NAMES", "removable_option_names", "serialize_options"]


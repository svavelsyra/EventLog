"""Centralized startup/bootstrap backend policy ownership.

This module is the authoritative seam for backend-specific startup facts used by
presenters, app bootstrap persistence, reset preparation, and repository
construction. It owns only backend policy and dispatch concerns; actual adapter
readiness and repository CRUD behavior stay in their existing layers.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from os import PathLike

from src.config import DatabaseConfig, save_bootstrap_section_options
from src.config.app_config import BootstrapTargetConfig, DatabaseCreationDefaults
from src.db import sqlite_target_resolver, sqlite_target_serializer
from src.db.database_adapter import BackendCleanupMetadata, WrongDatabaseAdapter
from src.db.repositories.base_repository import BaseRepository
from src.db.repositories.sqlite.event_log_repository import EventLogRepository
from src.db.repositories.startup_selection import (
    PathExists,
    StartupFieldKind,
    StartupFieldName,
    StartupFieldRequirement,
    StartupSelectionProfile,
)
from src.db.sqlite_adapter import (
    SQLiteAdapter,
    get_remembered_target_cleanup_metadata as get_sqlite_remembered_target_cleanup_metadata,
)
from src.db.sqlite_key_preparer import prepare_sqlite_encryption_key

BackendKeyPreparer = Callable[[str, bytes | None, DatabaseCreationDefaults], bytes | None]
StartupFieldResolver = Callable[[str, bool, bool], tuple[StartupFieldRequirement, ...]]
StartupModeResolver = Callable[[str, str, PathExists], str]
RuntimeConfigResolver = Callable[[DatabaseConfig, str | PathLike[str]], DatabaseConfig]
OptionSerializer = Callable[[BootstrapTargetConfig], Mapping[str, str]]
CleanupMetadataResolver = Callable[[str | PathLike[str]], BackendCleanupMetadata]
RepositoryCreator = Callable[[str | PathLike[str], bytes | None], BaseRepository]
DatabaseMigrator = Callable[[str | PathLike[str], bytes | None], bool]

SQLITE_DIALECT = "sqlite"
_STARTUP_MODE_CREATE = "create"
_STARTUP_MODE_UNLOCK = "unlock"


@dataclass(frozen=True, slots=True)
class BootstrapBackendPolicy:
    """Backend-owned startup/bootstrap policy facts for one dialect."""

    dialect: str
    startup_profile: StartupSelectionProfile = StartupSelectionProfile()
    startup_field_resolver: StartupFieldResolver | None = None
    startup_mode_resolver: StartupModeResolver | None = None
    key_preparer: BackendKeyPreparer | None = None
    runtime_config_resolver: RuntimeConfigResolver | None = None
    target_option_serializer: OptionSerializer | None = None
    removable_target_option_names: tuple[str, ...] = ()
    cleanup_metadata_resolver: CleanupMetadataResolver | None = None
    repository_creator: RepositoryCreator | None = None
    database_migrator: DatabaseMigrator | None = None
    supports_external_key_file_advisory: bool = False


_SQLITE_STARTUP_PROFILE = StartupSelectionProfile(
    supports_existing_target_unlock_inference=True,
    supports_password=True,
    supports_external_key_file=True,
    supports_database_path_field=True,
)


def _normalize_dialect(dialect: str) -> str:
    """Return normalized backend dialect text for policy lookup."""
    return dialect.strip().lower()


def _build_sqlite_startup_fields(
    mode: str,
    uses_remembered_target: bool,
    require_key_file: bool,
) -> tuple[StartupFieldRequirement, ...]:
    """Return SQLite-owned startup field requirements for the selected flow."""
    fields: list[StartupFieldRequirement] = []

    if not uses_remembered_target:
        fields.append(
            StartupFieldRequirement(
                field_name=StartupFieldName.DATABASE_PATH,
                kind=StartupFieldKind.FILE_PATH,
                required=True,
                editable=True,
            )
        )

    fields.append(
        StartupFieldRequirement(
            field_name=StartupFieldName.PASSWORD,
            kind=StartupFieldKind.PASSWORD,
        )
    )

    if mode == _STARTUP_MODE_CREATE:
        fields.append(
            StartupFieldRequirement(
                field_name=StartupFieldName.PASSWORD_CONFIRMATION,
                kind=StartupFieldKind.PASSWORD,
            )
        )

    if require_key_file:
        fields.append(
            StartupFieldRequirement(
                field_name=StartupFieldName.KEY_FILE_PATH,
                kind=StartupFieldKind.FILE_PATH,
                required=True,
                editable=True,
            )
        )
    elif mode == _STARTUP_MODE_CREATE or not uses_remembered_target:
        fields.append(
            StartupFieldRequirement(
                field_name=StartupFieldName.KEY_FILE_PATH,
                kind=StartupFieldKind.FILE_PATH,
            )
        )

    return tuple(fields)


def _infer_sqlite_startup_mode(
    database_path: str,
    _fallback_mode: str,
    path_exists: PathExists,
) -> str:
    """Return SQLite-owned startup mode for the selected target path."""
    normalized_database_path = database_path.strip()
    if normalized_database_path and path_exists(normalized_database_path):
        return _STARTUP_MODE_UNLOCK

    return _STARTUP_MODE_CREATE


def _resolve_sqlite_runtime_config(
    database_config: DatabaseConfig,
    config_path: str | PathLike[str],
) -> DatabaseConfig:
    """Return runtime-ready config for the SQLite backend."""
    return sqlite_target_resolver.resolve_runtime_database_config(
        database_config,
        config_path=config_path,
    )


def _create_sqlite_repository(
    database_path: str | PathLike[str],
    encryption_key: bytes | None,
) -> BaseRepository:
    """Return a ready SQLite repository for the selected target."""
    adapter = SQLiteAdapter(database_path, encryption_key=encryption_key)
    return EventLogRepository(adapter)


def _migrate_sqlite_database(
    database_path: str | PathLike[str],
    encryption_key: bytes | None,
) -> bool:
    """Run backend-owned SQLite migration for the selected target."""
    return SQLiteAdapter.migrate_database(database_path, encryption_key=encryption_key)


_BACKEND_POLICIES: dict[str, BootstrapBackendPolicy] = {
    SQLITE_DIALECT: BootstrapBackendPolicy(
        dialect=SQLITE_DIALECT,
        startup_profile=_SQLITE_STARTUP_PROFILE,
        startup_field_resolver=_build_sqlite_startup_fields,
        startup_mode_resolver=_infer_sqlite_startup_mode,
        key_preparer=prepare_sqlite_encryption_key,
        runtime_config_resolver=_resolve_sqlite_runtime_config,
        target_option_serializer=sqlite_target_serializer.serialize_options,
        removable_target_option_names=sqlite_target_serializer.REMEMBERED_OPTION_NAMES,
        cleanup_metadata_resolver=get_sqlite_remembered_target_cleanup_metadata,
        repository_creator=_create_sqlite_repository,
        database_migrator=_migrate_sqlite_database,
        supports_external_key_file_advisory=True,
    ),
}


def resolve_bootstrap_backend_policy(dialect: str) -> BootstrapBackendPolicy | None:
    """Return the authoritative backend policy for the requested dialect."""
    return _BACKEND_POLICIES.get(_normalize_dialect(dialect))


def supported_repository_dialects() -> tuple[str, ...]:
    """Return the normalized repository dialects currently supported by runtime bootstrap."""
    return tuple(_BACKEND_POLICIES)


def resolve_startup_selection_profile(dialect: str) -> StartupSelectionProfile:
    """Return the backend-owned startup profile for the selected dialect."""
    policy = resolve_bootstrap_backend_policy(dialect)
    if policy is None:
        return StartupSelectionProfile()

    return policy.startup_profile


def resolve_startup_key_preparer(dialect: str) -> BackendKeyPreparer | None:
    """Return the backend-owned key preparer for the selected dialect, if any."""
    policy = resolve_bootstrap_backend_policy(dialect)
    if policy is None:
        return None

    return policy.key_preparer


def infer_startup_mode_for_selection(
    *,
    dialect: str,
    database_path: str,
    fallback_mode: str,
    path_exists: PathExists,
) -> str:
    """Return the backend-owned startup mode for the selected target details."""
    policy = resolve_bootstrap_backend_policy(dialect)
    if policy is None or policy.startup_mode_resolver is None:
        return fallback_mode

    return policy.startup_mode_resolver(database_path, fallback_mode, path_exists)


def resolve_backend_startup_fields(
    dialect: str,
    *,
    mode: str,
    uses_remembered_target: bool,
    require_key_file: bool,
) -> tuple[StartupFieldRequirement, ...]:
    """Return backend-owned technical startup field requirements."""
    policy = resolve_bootstrap_backend_policy(dialect)
    if policy is None or policy.startup_field_resolver is None:
        return ()

    return policy.startup_field_resolver(mode, uses_remembered_target, require_key_file)


def is_supported_repository_dialect(dialect: str) -> bool:
    """Return whether the requested repository dialect is currently supported."""
    return resolve_bootstrap_backend_policy(dialect) is not None


def supports_external_key_file_advisory(dialect: str) -> bool:
    """Return whether the backend technology may involve external key files."""
    policy = resolve_bootstrap_backend_policy(dialect)
    return bool(policy is not None and policy.supports_external_key_file_advisory)


def resolve_runtime_database_config(
    database_config: DatabaseConfig,
    *,
    config_path: str | PathLike[str],
) -> DatabaseConfig:
    """Return runtime-ready bootstrap config with backend-owned target normalization."""
    policy = resolve_bootstrap_backend_policy(database_config.dialect)
    if policy is None or policy.runtime_config_resolver is None:
        return database_config

    return policy.runtime_config_resolver(database_config, config_path)


def save_bootstrap_target_config(
    config_path: str | PathLike[str],
    target: BootstrapTargetConfig,
) -> None:
    """Persist remembered bootstrap state using backend-owned field serialization."""
    normalized_dialect = _normalize_dialect(target.dialect)
    policy = resolve_bootstrap_backend_policy(normalized_dialect)
    remembered_section_options = (
        {} if policy is None or policy.target_option_serializer is None else dict(policy.target_option_serializer(target))
    )
    cleared_section_options = None

    if not normalized_dialect:
        cleared_section_options = {
            backend_policy.dialect: backend_policy.removable_target_option_names
            for backend_policy in _BACKEND_POLICIES.values()
            if backend_policy.removable_target_option_names
        }

    save_bootstrap_section_options(
        config_path,
        dialect=normalized_dialect,
        remembered_section_options=remembered_section_options,
        cleared_section_options=cleared_section_options,
    )


def get_remembered_target_cleanup_metadata(
    *,
    database_path: str | PathLike[str],
    dialect: str = SQLITE_DIALECT,
) -> BackendCleanupMetadata:
    """Return backend-owned cleanup metadata for an unopened remembered target."""
    policy = resolve_bootstrap_backend_policy(dialect)
    if policy is None or policy.cleanup_metadata_resolver is None:
        supported_dialects_text = ", ".join(repr(supported) for supported in supported_repository_dialects())
        raise WrongDatabaseAdapter(
            f"Unsupported repository dialect {dialect!r}. Only {supported_dialects_text} is currently supported."
        )

    return policy.cleanup_metadata_resolver(database_path)


def create_event_log_repository(
    *,
    database_path: str | PathLike[str],
    dialect: str = SQLITE_DIALECT,
    encryption_key: bytes | None = None,
) -> BaseRepository:
    """Create a ready-to-use EventLog repository for the supported dialect."""
    policy = resolve_bootstrap_backend_policy(dialect)
    if policy is None or policy.repository_creator is None:
        supported_dialects_text = ", ".join(repr(supported) for supported in supported_repository_dialects())
        raise WrongDatabaseAdapter(
            f"Unsupported repository dialect {dialect!r}. Only {supported_dialects_text} is currently supported."
        )

    return policy.repository_creator(database_path, encryption_key)


def migrate_event_log_database(
    *,
    database_path: str | PathLike[str],
    dialect: str = SQLITE_DIALECT,
    encryption_key: bytes | None = None,
) -> bool:
    """Run backend-owned migration for the selected database target."""
    policy = resolve_bootstrap_backend_policy(dialect)
    if policy is None or policy.database_migrator is None:
        supported_dialects_text = ", ".join(repr(supported) for supported in supported_repository_dialects())
        raise WrongDatabaseAdapter(
            f"Unsupported repository dialect {dialect!r}. Only {supported_dialects_text} is currently supported."
        )

    return policy.database_migrator(database_path, encryption_key)


__all__ = [
    "BackendKeyPreparer",
    "BootstrapBackendPolicy",
    "SQLITE_DIALECT",
    "create_event_log_repository",
    "get_remembered_target_cleanup_metadata",
    "infer_startup_mode_for_selection",
    "is_supported_repository_dialect",
    "migrate_event_log_database",
    "resolve_backend_startup_fields",
    "resolve_bootstrap_backend_policy",
    "resolve_runtime_database_config",
    "resolve_startup_key_preparer",
    "resolve_startup_selection_profile",
    "save_bootstrap_target_config",
    "supported_repository_dialects",
    "supports_external_key_file_advisory",
]



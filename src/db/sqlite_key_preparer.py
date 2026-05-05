"""SQLite-owned key preparation helpers for encrypted startup flows.

This module keeps SQLite/SQLCipher-specific KDF policy out of the shared
security helper boundary and out of generic bootstrap orchestration. It turns
validated caller inputs into backend-ready key bytes suitable for the current
SQLite encrypted-open path.
"""

from __future__ import annotations

import hashlib

from src.config import DatabaseConfig
from src.config.app_config import DatabaseCreationDefaults
from src.security import DEFAULT_DERIVED_KEY_LENGTH_BYTES, derive_encryption_key

SQLITE_PASSWORD_ONLY_KDF_SALT: bytes = b"EventLog-Default-Salt-v1"
SQLITE_ENCRYPTION_KEY_LENGTH_BYTES: int = DEFAULT_DERIVED_KEY_LENGTH_BYTES


def _resolve_sqlite_kdf_salt(key_file_bytes: bytes | None) -> bytes:
    """Return the current SQLite-owned KDF salt for the supplied credential mode."""
    if key_file_bytes is None:
        return SQLITE_PASSWORD_ONLY_KDF_SALT

    if not isinstance(key_file_bytes, bytes):
        raise TypeError("key_file_bytes must be bytes or None")

    return hashlib.sha256(key_file_bytes).digest()


def prepare_sqlite_encryption_key(
    password: str,
    key_file_bytes: bytes | None,
    creation_defaults: DatabaseCreationDefaults | DatabaseConfig,
) -> bytes:
    """Return backend-ready SQLite encryption key bytes for startup/open flows."""
    if not isinstance(password, str):
        raise TypeError("password must be a string")

    if isinstance(creation_defaults, DatabaseConfig):
        creation_defaults = creation_defaults.creation_defaults

    if not isinstance(creation_defaults, DatabaseCreationDefaults):
        raise TypeError(
            "creation_defaults or database_config must be a DatabaseCreationDefaults or DatabaseConfig"
        )

    return derive_encryption_key(
        password,
        salt=_resolve_sqlite_kdf_salt(key_file_bytes),
        iterations=creation_defaults.kdf_iterations,
        length=SQLITE_ENCRYPTION_KEY_LENGTH_BYTES,
    )


__all__ = [
    "SQLITE_ENCRYPTION_KEY_LENGTH_BYTES",
    "SQLITE_PASSWORD_ONLY_KDF_SALT",
    "prepare_sqlite_encryption_key",
]



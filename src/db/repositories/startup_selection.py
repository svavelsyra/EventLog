"""Shared startup field/type definitions for backend-driven startup flows.

Backend policy ownership now lives in `bootstrap_backend_policy.py`. This module
keeps only the stable startup field and profile types shared across GUI and
backend policy code.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class StartupFieldName(StrEnum):
    """Stable field identifiers shared across startup layers."""

    DATABASE_PATH = "database_path"
    PASSWORD = "password"
    PASSWORD_CONFIRMATION = "password_confirmation"
    KEY_FILE_PATH = "key_file_path"


class StartupFieldKind(StrEnum):
    """Stable technical input kinds for startup requirements."""

    TEXT = "text"
    PASSWORD = "password"
    FILE_PATH = "file_path"


@dataclass(frozen=True, slots=True)
class StartupFieldRequirement:
    """Backend-owned technical startup field requirement."""

    field_name: StartupFieldName
    kind: StartupFieldKind
    required: bool = False
    editable: bool = True


@dataclass(frozen=True, slots=True)
class StartupSelectionProfile:
    """Backend-owned startup-selection capabilities for one dialect."""

    supports_existing_target_unlock_inference: bool = False
    supports_password: bool = False
    supports_external_key_file: bool = False
    supports_database_path_field: bool = False

__all__ = [
    "StartupFieldKind",
    "StartupFieldName",
    "StartupFieldRequirement",
    "StartupSelectionProfile",
]


from os import PathLike

import pytest

from src.db.repositories.bootstrap_backend_policy import (
    infer_startup_mode_for_selection,
    resolve_backend_startup_fields,
    resolve_startup_key_preparer,
    resolve_startup_selection_profile,
)
from src.db.repositories.startup_selection import (
    StartupSelectionProfile,
    StartupFieldKind,
    StartupFieldName,
    StartupFieldRequirement,
)
from src.db.sqlite_key_preparer import prepare_sqlite_encryption_key


pytestmark = pytest.mark.unit


def test_resolve_startup_selection_profile_returns_sqlite_capabilities() -> None:
    assert resolve_startup_selection_profile(" sqlite ") == StartupSelectionProfile(
        supports_existing_target_unlock_inference=True,
        supports_password=True,
        supports_external_key_file=True,
        supports_database_path_field=True,
    )


def test_resolve_startup_selection_profile_returns_empty_profile_for_unknown_dialect() -> None:
    assert resolve_startup_selection_profile("postgres") == StartupSelectionProfile()


def test_resolve_startup_key_preparer_returns_sqlite_preparer_only_for_sqlite() -> None:
    assert resolve_startup_key_preparer("sqlite") is prepare_sqlite_encryption_key
    assert resolve_startup_key_preparer("postgres") is None


def test_infer_startup_mode_for_selection_uses_backend_profile_for_existing_sqlite_target() -> None:
    captured: list[str] = []

    def path_exists(path: str | PathLike[str]) -> bool:
        normalized_path = str(path)
        captured.append(normalized_path)
        return normalized_path == "C:/Ops/eventlog.db"

    assert infer_startup_mode_for_selection(
        dialect="sqlite",
        database_path="  C:/Ops/eventlog.db  ",
        fallback_mode="create",
        path_exists=path_exists,
    ) == "unlock"
    assert captured == ["C:/Ops/eventlog.db"]


def test_infer_startup_mode_for_selection_keeps_fallback_for_unknown_dialect() -> None:
    path_checked = False

    def path_exists(_path: str | PathLike[str]) -> bool:
        nonlocal path_checked
        path_checked = True
        return True

    assert infer_startup_mode_for_selection(
        dialect="postgres",
        database_path="C:/Ops/eventlog.db",
        fallback_mode="create",
        path_exists=path_exists,
    ) == "create"
    assert path_checked is False


def test_resolve_backend_startup_fields_returns_empty_for_unknown_dialect() -> None:
    assert resolve_backend_startup_fields(
        "",
        mode="create",
        uses_remembered_target=False,
        require_key_file=False,
    ) == ()


def test_resolve_backend_startup_fields_describes_sqlite_create_flow() -> None:
    assert resolve_backend_startup_fields(
        "sqlite",
        mode="create",
        uses_remembered_target=False,
        require_key_file=False,
    ) == (
        StartupFieldRequirement(
            field_name=StartupFieldName.DATABASE_PATH,
            kind=StartupFieldKind.FILE_PATH,
            required=True,
            editable=True,
        ),
        StartupFieldRequirement(
            field_name=StartupFieldName.PASSWORD,
            kind=StartupFieldKind.PASSWORD,
        ),
        StartupFieldRequirement(
            field_name=StartupFieldName.PASSWORD_CONFIRMATION,
            kind=StartupFieldKind.PASSWORD,
        ),
        StartupFieldRequirement(
            field_name=StartupFieldName.KEY_FILE_PATH,
            kind=StartupFieldKind.FILE_PATH,
        ),
    )


def test_resolve_backend_startup_fields_describes_sqlite_unlock_with_remembered_key_file_requirement() -> None:
    assert resolve_backend_startup_fields(
        "sqlite",
        mode="unlock",
        uses_remembered_target=True,
        require_key_file=True,
    ) == (
        StartupFieldRequirement(
            field_name=StartupFieldName.PASSWORD,
            kind=StartupFieldKind.PASSWORD,
        ),
        StartupFieldRequirement(
            field_name=StartupFieldName.KEY_FILE_PATH,
            kind=StartupFieldKind.FILE_PATH,
            required=True,
            editable=True,
        ),
    )



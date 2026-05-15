import pytest

from src.config import DatabaseConfig
from src.db.repositories.bootstrap_backend_policy import (
    infer_startup_mode_for_selection,
    project_backend_startup_fields_for_selection,
    resolve_backend_startup_fields,
    resolve_effective_startup_selection,
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


def test_infer_startup_mode_for_selection_uses_backend_profile_for_existing_sqlite_target(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[str] = []

    def fake_exists(path: object) -> bool:
        normalized_path = str(path)
        captured.append(normalized_path)
        return normalized_path == "C:/Ops/eventlog.db"

    monkeypatch.setattr(
        "src.db.repositories.bootstrap_backend_policy.os.path.exists",
        fake_exists,
    )

    assert infer_startup_mode_for_selection(
        dialect="sqlite",
        database_path="  C:/Ops/eventlog.db  ",
        fallback_mode="create",
    ) == "unlock"
    assert captured == ["C:/Ops/eventlog.db"]


def test_infer_startup_mode_for_selection_keeps_fallback_for_unknown_dialect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path_checked = False

    def fake_exists(_path: object) -> bool:
        nonlocal path_checked
        path_checked = True
        return True

    monkeypatch.setattr(
        "src.db.repositories.bootstrap_backend_policy.os.path.exists",
        fake_exists,
    )

    assert infer_startup_mode_for_selection(
        dialect="postgres",
        database_path="C:/Ops/eventlog.db",
        fallback_mode="create",
    ) == "create"
    assert path_checked is False


def test_resolve_effective_startup_selection_locks_sqlite_to_managed_config_target() -> None:
    assert resolve_effective_startup_selection(
        DatabaseConfig(dialect="sqlite", database_path="eventlog.db"),
        submitted_dialect=" sqlite ",
        submitted_database_path="C:/Ops/other.db",
        uses_remembered_target=False,
    ) == resolve_effective_startup_selection(
        DatabaseConfig(dialect="sqlite", database_path="eventlog.db"),
        submitted_dialect="sqlite",
        submitted_database_path="eventlog.db",
        uses_remembered_target=True,
    )


def test_resolve_effective_startup_selection_preserves_manual_target_for_non_locked_selection() -> None:
    assert resolve_effective_startup_selection(
        DatabaseConfig(dialect="sqlite", database_path=""),
        submitted_dialect=" sqlite ",
        submitted_database_path="  C:/Ops/manual.db  ",
        uses_remembered_target=False,
    ).database_path == "C:/Ops/manual.db"


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


def test_project_backend_startup_fields_for_selection_hides_database_path_for_locked_target() -> None:
    raw_backend_fields = resolve_backend_startup_fields(
        "sqlite",
        mode="unlock",
        uses_remembered_target=True,
        require_key_file=False,
    )

    assert project_backend_startup_fields_for_selection(
        "sqlite",
        mode="unlock",
        database_path="eventlog.db",
        target_locked=True,
        backend_fields=raw_backend_fields,
    ) == (
        StartupFieldRequirement(
            field_name=StartupFieldName.PASSWORD,
            kind=StartupFieldKind.PASSWORD,
        ),
    )


def test_project_backend_startup_fields_for_selection_keeps_create_flow_target_only_until_path_exists() -> None:
    raw_backend_fields = resolve_backend_startup_fields(
        "sqlite",
        mode="create",
        uses_remembered_target=False,
        require_key_file=False,
    )

    assert project_backend_startup_fields_for_selection(
        "sqlite",
        mode="create",
        database_path="",
        target_locked=False,
        backend_fields=raw_backend_fields,
    ) == (
        StartupFieldRequirement(
            field_name=StartupFieldName.DATABASE_PATH,
            kind=StartupFieldKind.FILE_PATH,
            required=True,
            editable=True,
        ),
    )



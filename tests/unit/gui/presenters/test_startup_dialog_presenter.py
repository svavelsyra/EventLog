from pathlib import Path
from typing import cast

import pytest

from src.config import DatabaseConfig
from src.db.repositories.base_repository import BaseRepository
from src.db.repositories.startup_selection import StartupFieldKind, StartupFieldName
from src.db.repositories.startup_bootstrap import (
    BootstrapFailure,
    BootstrapFailureCode,
    BootstrapRepositoryRequest,
    BootstrapRepositoryResult,
    MigrationRequest,
    MigrationResult,
)
from src.db.sqlite_key_preparer import prepare_sqlite_encryption_key
from src.gui.presenters.startup_dialog_presenter import (
    StartupDialogFailureCode,
    StartupDialogMigrationResult,
    StartupDialogMode,
    StartupDialogPresenter,
    StartupDialogSubmission,
)
from src.security import GENERIC_INVALID_CREDENTIALS_MESSAGE


pytestmark = pytest.mark.unit


def _make_config(
    *,
    dialect: str = "sqlite",
    database_path: str = "eventlog.db",
    require_key_file: bool = False,
    require_key_file_for_creation: bool = False,
    min_password_length: int = 8,
) -> DatabaseConfig:
    return DatabaseConfig(
        dialect=dialect,
        database_path=database_path,
        require_key_file=require_key_file,
        require_key_file_for_creation=require_key_file_for_creation,
        min_password_length=min_password_length,
    )


def _make_mode_resolver(*existing_paths: str):
    normalized_existing_paths = {path.strip() for path in existing_paths}

    def _resolver(dialect: str, database_path: str, fallback_mode: StartupDialogMode) -> StartupDialogMode:
        if dialect.strip().lower() != "sqlite":
            return fallback_mode

        normalized_database_path = database_path.strip()
        if normalized_database_path and normalized_database_path in normalized_existing_paths:
            return StartupDialogMode.UNLOCK

        return StartupDialogMode.CREATE

    return _resolver


def _make_submission(
    *,
    mode: StartupDialogMode,
    dialect: str = "sqlite",
    operator: str = "",
    uses_remembered_target: bool = False,
    database_path: str = "eventlog.db",
    password: str = "",
    password_confirmation: str = "",
    key_file_path: str | Path | None = None,
) -> StartupDialogSubmission:
    return StartupDialogSubmission(
        mode=mode,
        dialect=dialect,
        operator=operator,
        uses_remembered_target=uses_remembered_target,
        field_values={
            StartupFieldName.DATABASE_PATH: database_path,
            StartupFieldName.PASSWORD: password,
            StartupFieldName.PASSWORD_CONFIRMATION: password_confirmation,
            StartupFieldName.KEY_FILE_PATH: "" if key_file_path is None else str(key_file_path),
        },
    )


def test_get_initial_state_prefers_unlock_when_bootstrap_target_is_complete() -> None:
    presenter = StartupDialogPresenter(
        _make_config(),
        startup_mode_resolver=_make_mode_resolver("eventlog.db"),
    )

    state = presenter.get_initial_state()

    assert state.mode is StartupDialogMode.UNLOCK
    assert state.title == "EventLog - Lås upp"
    assert state.submit_label == "Lås upp"
    assert state.password_policy_hint == ""
    assert state.allow_emergency_reset is True
    assert state.uses_remembered_target is False
    assert state.show_dialect_picker is False
    assert [field.field_name for field in state.backend_fields] == [StartupFieldName.PASSWORD]
    assert state.backend_fields[0].kind is StartupFieldKind.PASSWORD


def test_get_initial_state_falls_back_to_create_when_remembered_target_path_is_missing() -> None:
    presenter = StartupDialogPresenter(
        _make_config(dialect="sqlite", database_path="C:/Ops/missing.db"),
        startup_mode_resolver=_make_mode_resolver(),
    )

    state = presenter.get_initial_state()

    assert state.mode is StartupDialogMode.CREATE
    assert state.title == "EventLog - Skapa krypterad databas"
    assert state.uses_remembered_target is False
    assert StartupFieldName.PASSWORD_CONFIRMATION in [field.field_name for field in state.backend_fields]


def test_get_initial_state_falls_back_to_create_when_bootstrap_target_is_missing() -> None:
    presenter = StartupDialogPresenter(_make_config(dialect="", database_path=""))

    state = presenter.get_initial_state()

    assert state.mode is StartupDialogMode.CREATE
    assert state.title == "EventLog - Välj eller skapa databas"
    assert state.submit_label == "Skapa"
    assert state.dialect == ""
    assert state.password_policy_hint == "Minst 8 tecken för nytt lösenord."
    assert state.allow_emergency_reset is False
    assert state.show_dialect_picker is True
    assert state.backend_fields == ()


def test_get_initial_state_preserves_operator_prefill_in_view_state() -> None:
    presenter = StartupDialogPresenter(_make_config(dialect="", database_path=""))

    state = presenter.get_initial_state(operator="  Sgt Example  ")

    assert state.operator == "Sgt Example"


def test_build_state_for_create_stays_target_only_until_sqlite_path_is_selected() -> None:
    presenter = StartupDialogPresenter(_make_config(dialect="", database_path=""))

    empty_state = presenter.build_state(mode=StartupDialogMode.CREATE, dialect="")
    sqlite_state = presenter.build_state(mode=StartupDialogMode.CREATE, dialect="sqlite")
    sqlite_with_path_state = presenter.build_state(
        mode=StartupDialogMode.CREATE,
        dialect="sqlite",
        database_path="C:/Ops/new-eventlog.db",
    )

    assert empty_state.backend_fields == ()
    assert empty_state.title == "EventLog - Välj eller skapa databas"
    assert empty_state.password_policy_hint == "Minst 8 tecken för nytt lösenord."

    assert sqlite_state.title == "EventLog - Välj eller skapa databas"
    assert [field.field_name for field in sqlite_state.backend_fields] == [
        StartupFieldName.DATABASE_PATH,
    ]
    assert sqlite_state.password_policy_hint == "Minst 8 tecken för nytt lösenord."
    assert sqlite_state.backend_fields[0].required is True
    assert sqlite_state.backend_fields[0].kind is StartupFieldKind.FILE_PATH

    assert sqlite_with_path_state.title == "EventLog - Skapa krypterad databas"
    assert [field.field_name for field in sqlite_with_path_state.backend_fields] == [
        StartupFieldName.DATABASE_PATH,
        StartupFieldName.PASSWORD,
        StartupFieldName.PASSWORD_CONFIRMATION,
        StartupFieldName.KEY_FILE_PATH,
    ]
    assert sqlite_with_path_state.password_policy_hint == "Minst 8 tecken för nytt lösenord."
    assert sqlite_with_path_state.backend_fields[-1].required is False


def test_build_state_for_create_uses_create_policy_not_remembered_unlock_hint_for_key_file_requirement() -> None:
    presenter = StartupDialogPresenter(
        _make_config(
            dialect="",
            database_path="",
            require_key_file=True,
            require_key_file_for_creation=False,
        )
    )

    state = presenter.build_state(
        mode=StartupDialogMode.CREATE,
        dialect="sqlite",
        database_path="C:/Ops/new-eventlog.db",
    )

    assert state.backend_fields[-1].field_name is StartupFieldName.KEY_FILE_PATH
    assert state.backend_fields[-1].required is False


def test_build_state_for_create_requires_key_file_when_create_policy_demands_it() -> None:
    presenter = StartupDialogPresenter(
        _make_config(
            dialect="",
            database_path="",
            require_key_file=False,
            require_key_file_for_creation=True,
        )
    )

    state = presenter.build_state(
        mode=StartupDialogMode.CREATE,
        dialect="sqlite",
        database_path="C:/Ops/new-eventlog.db",
    )

    assert state.backend_fields[-1].required is True
    assert state.backend_fields[-1].field_name is StartupFieldName.KEY_FILE_PATH


def test_build_state_for_unlock_shows_key_file_picker_only_when_required() -> None:
    password_only_presenter = StartupDialogPresenter(_make_config(require_key_file=False))
    key_file_presenter = StartupDialogPresenter(_make_config(require_key_file=True))

    password_only_state = password_only_presenter.build_state(mode=StartupDialogMode.UNLOCK)
    key_file_state = key_file_presenter.build_state(mode=StartupDialogMode.UNLOCK)

    assert password_only_state.password_policy_hint == ""
    assert key_file_state.password_policy_hint == ""
    assert [field.field_name for field in password_only_state.backend_fields] == [StartupFieldName.PASSWORD]
    assert [field.field_name for field in key_file_state.backend_fields] == [
        StartupFieldName.PASSWORD,
        StartupFieldName.KEY_FILE_PATH,
    ]
    assert key_file_state.backend_fields[-1].required is True


def test_create_password_policy_hint_uses_configured_minimum_length() -> None:
    presenter = StartupDialogPresenter(_make_config(dialect="sqlite", database_path="", min_password_length=12))

    state = presenter.build_state(mode=StartupDialogMode.CREATE, dialect="sqlite")

    assert state.password_policy_hint == "Minst 12 tecken för nytt lösenord."


def test_build_state_for_manual_existing_database_shows_target_fields_when_no_remembered_target_exists() -> None:
    presenter = StartupDialogPresenter(_make_config(dialect="sqlite", database_path=""))

    state = presenter.build_state(mode=StartupDialogMode.UNLOCK)

    assert state.mode is StartupDialogMode.UNLOCK
    assert state.title == "EventLog - Öppna befintlig databas"
    assert state.submit_label == "Lås upp"
    assert state.dialect == "sqlite"
    assert state.database_path == ""
    assert state.uses_remembered_target is False
    assert state.show_dialect_picker is True
    assert state.allow_emergency_reset is True
    assert [field.field_name for field in state.backend_fields] == [
        StartupFieldName.DATABASE_PATH,
        StartupFieldName.PASSWORD,
        StartupFieldName.KEY_FILE_PATH,
    ]
    assert state.backend_fields[0].kind is StartupFieldKind.FILE_PATH
    assert state.backend_fields[0].editable is True
    assert state.backend_fields[-1].required is False


def test_build_state_for_managed_sqlite_unlock_ignores_manual_target_selection_request() -> None:
    presenter = StartupDialogPresenter(_make_config())

    state = presenter.build_state(
        mode=StartupDialogMode.UNLOCK,
        use_remembered_target=False,
        database_path="D:/Ops/eventlog.db",
    )

    assert state.title == "EventLog - Lås upp"
    assert state.uses_remembered_target is False
    assert state.show_dialect_picker is False
    assert state.database_path == "eventlog.db"
    assert [field.field_name for field in state.backend_fields] == [
        StartupFieldName.PASSWORD,
    ]


def test_recompute_state_for_managed_sqlite_ignores_manual_target_and_uses_managed_unlock_state() -> None:
    presenter = StartupDialogPresenter(
        _make_config(),
        startup_mode_resolver=_make_mode_resolver("eventlog.db"),
    )

    state = presenter.recompute_state(
        _make_submission(
            mode=StartupDialogMode.CREATE,
            dialect="sqlite",
            database_path="C:/Ops/existing.db",
            password="lösenord123",
            password_confirmation="lösenord123",
        )
    )

    assert state.mode is StartupDialogMode.UNLOCK
    assert state.title == "EventLog - Lås upp"
    assert state.uses_remembered_target is False
    assert state.show_dialect_picker is False
    assert state.database_path == "eventlog.db"
    assert StartupFieldName.PASSWORD_CONFIRMATION not in [field.field_name for field in state.backend_fields]


def test_recompute_state_for_managed_sqlite_uses_missing_managed_target_create_state() -> None:
    presenter = StartupDialogPresenter(
        _make_config(dialect="sqlite", database_path="C:/Ops/managed.db"),
        startup_mode_resolver=_make_mode_resolver(),
    )

    state = presenter.recompute_state(
        _make_submission(
            mode=StartupDialogMode.UNLOCK,
            dialect="sqlite",
            database_path="C:/Ops/new-eventlog.db",
            password="lösenord123",
        ),
    )

    assert state.mode is StartupDialogMode.CREATE
    assert state.title == "EventLog - Skapa krypterad databas"
    assert state.uses_remembered_target is False
    assert state.show_dialect_picker is False
    assert state.database_path == "C:/Ops/managed.db"
    assert StartupFieldName.PASSWORD_CONFIRMATION in [field.field_name for field in state.backend_fields]


def test_recompute_state_preserves_operator_in_view_state() -> None:
    presenter = StartupDialogPresenter(_make_config(dialect="", database_path=""))

    state = presenter.recompute_state(
        _make_submission(
            mode=StartupDialogMode.CREATE,
            dialect="sqlite",
            operator="  Sgt Example  ",
            database_path="C:/Ops/new-eventlog.db",
            password="lösenord123",
            password_confirmation="lösenord123",
        )
    )

    assert state.operator == "Sgt Example"


def test_recompute_state_preserves_key_file_path_in_view_state() -> None:
    presenter = StartupDialogPresenter(_make_config(dialect="", database_path=""))

    state = presenter.recompute_state(
        _make_submission(
            mode=StartupDialogMode.CREATE,
            dialect="sqlite",
            database_path="C:/Ops/new-eventlog.db",
            password="lösenord123",
            password_confirmation="lösenord123",
            key_file_path="  C:/keys/startup.key  ",
        )
    )

    assert state.key_file_path == "C:/keys/startup.key"


def test_submit_manual_unlock_remembers_actual_key_file_usage_after_success(tmp_path: Path) -> None:
    database_path = tmp_path / "existing.db"
    database_path.write_text("", encoding="utf-8")
    sentinel_repository = cast(BaseRepository, object())

    def fake_bootstrap(_request):
        return BootstrapRepositoryResult(repository=sentinel_repository)

    presenter = StartupDialogPresenter(
        _make_config(dialect="sqlite", database_path=""),
        bootstrap_callback=fake_bootstrap,
    )

    result = presenter.submit(
        _make_submission(
            mode=StartupDialogMode.UNLOCK,
            dialect="sqlite",
            database_path=str(database_path),
            password="lösenord123",
            uses_remembered_target=False,
            key_file_path=tmp_path / "manual.key",
        )
    )

    assert result.succeeded is True
    assert result.success is not None
    assert result.success.remembered_target.require_key_file is True


def test_submit_success_returns_stripped_last_operator(tmp_path: Path) -> None:
    sentinel_repository = cast(BaseRepository, object())

    def fake_bootstrap(_request):
        return BootstrapRepositoryResult(repository=sentinel_repository)

    presenter = StartupDialogPresenter(
        _make_config(dialect="sqlite", database_path=""),
        bootstrap_callback=fake_bootstrap,
    )

    result = presenter.submit(
        _make_submission(
            mode=StartupDialogMode.CREATE,
            dialect="sqlite",
            operator="  Sgt Example  ",
            database_path=str(tmp_path / "eventlog.db"),
            password="lösenord123",
            password_confirmation="lösenord123",
        )
    )

    assert result.succeeded is True
    assert result.success is not None
    assert result.success.last_operator == "Sgt Example"


def test_submit_create_rejects_password_confirmation_mismatch() -> None:
    presenter = StartupDialogPresenter(_make_config())

    result = presenter.submit(
        _make_submission(
            mode=StartupDialogMode.CREATE,
            dialect="sqlite",
            database_path="eventlog.db",
            password="lösenord123",
            password_confirmation="annat-lösenord",
        )
    )

    assert result.succeeded is False
    assert result.failure is not None
    assert result.failure.code is StartupDialogFailureCode.PASSWORD_CONFIRMATION_MISMATCH
    assert result.failure.field_name == "password_confirmation"
    assert result.failure.message == "Lösenorden matchar inte."


def test_submit_create_rejects_too_short_password_before_bootstrap() -> None:
    bootstrap_called = False
    sentinel_repository = cast(BaseRepository, object())

    def fake_bootstrap(_request):
        nonlocal bootstrap_called
        bootstrap_called = True
        return BootstrapRepositoryResult(repository=sentinel_repository)

    presenter = StartupDialogPresenter(_make_config(min_password_length=12), bootstrap_callback=fake_bootstrap)

    result = presenter.submit(
        _make_submission(
            mode=StartupDialogMode.CREATE,
            dialect="sqlite",
            database_path="eventlog.db",
            password="kort",
            password_confirmation="kort",
        )
    )

    assert result.succeeded is False
    assert result.failure is not None
    assert result.failure.code is StartupDialogFailureCode.INVALID_PASSWORD
    assert result.failure.field_name == "password"
    assert result.failure.message == "Lösenord måste vara minst 12 tecken"
    assert bootstrap_called is False


def test_submit_unlock_requires_key_file_when_mode_requires_it(tmp_path: Path) -> None:
    database_path = tmp_path / "eventlog.db"
    database_path.write_text("", encoding="utf-8")
    presenter = StartupDialogPresenter(_make_config(require_key_file=True, database_path=str(database_path)))

    result = presenter.submit(
        _make_submission(
            mode=StartupDialogMode.UNLOCK,
            dialect="sqlite",
            database_path=str(database_path),
            password="lösenord123",
        )
    )

    assert result.succeeded is False
    assert result.failure is not None
    assert result.failure.code is StartupDialogFailureCode.MISSING_REQUIRED_KEY_FILE
    assert result.failure.field_name == "key_file_path"
    assert result.failure.message == "Nyckelfil krävs för den här databasen."


def test_submit_create_requires_key_file_when_create_policy_demands_it() -> None:
    presenter = StartupDialogPresenter(_make_config(require_key_file_for_creation=True))

    result = presenter.submit(
        _make_submission(
            mode=StartupDialogMode.CREATE,
            dialect="sqlite",
            database_path="eventlog.db",
            password="lösenord123",
            password_confirmation="lösenord123",
        )
    )

    assert result.succeeded is False
    assert result.failure is not None
    assert result.failure.code is StartupDialogFailureCode.MISSING_REQUIRED_KEY_FILE
    assert result.failure.field_name == "key_file_path"


def test_submit_create_remembers_actual_key_file_usage_not_just_create_policy(tmp_path: Path) -> None:
    database_path = tmp_path / "eventlog.db"
    sentinel_repository = cast(BaseRepository, object())

    def fake_bootstrap(_request):
        return BootstrapRepositoryResult(repository=sentinel_repository)

    presenter = StartupDialogPresenter(
        _make_config(require_key_file_for_creation=False),
        bootstrap_callback=fake_bootstrap,
    )

    result = presenter.submit(
        _make_submission(
            mode=StartupDialogMode.CREATE,
            dialect="sqlite",
            database_path=str(database_path),
            password="lösenord123",
            password_confirmation="lösenord123",
            key_file_path=tmp_path / "startup.key",
        )
    )

    assert result.succeeded is True
    assert result.success is not None
    assert result.success.remembered_target.require_key_file is True



def test_submit_success_preserves_backend_neutral_access_invalidator(tmp_path: Path) -> None:
    sentinel_repository = cast(BaseRepository, object())

    def invalidate_access() -> None:
        raise AssertionError("test should only verify pass-through")

    def fake_bootstrap(_request):
        return BootstrapRepositoryResult(
            repository=sentinel_repository,
            invalidate_access=invalidate_access,
        )

    presenter = StartupDialogPresenter(
        _make_config(dialect="sqlite", database_path=""),
        bootstrap_callback=fake_bootstrap,
    )

    result = presenter.submit(
        _make_submission(
            mode=StartupDialogMode.CREATE,
            dialect="sqlite",
            database_path=str(tmp_path / "eventlog.db"),
            password="lösenord123",
            password_confirmation="lösenord123",
        )
    )

    assert result.succeeded is True
    assert result.success is not None
    assert result.success.invalidate_access is invalidate_access



def test_submit_success_preserves_backend_owned_cleanup_callback(tmp_path: Path) -> None:
    sentinel_repository = cast(BaseRepository, object())

    def backend_cleanup():
        raise AssertionError("test should only verify pass-through")

    def fake_bootstrap(_request):
        return BootstrapRepositoryResult(
            repository=sentinel_repository,
            backend_cleanup=backend_cleanup,
        )

    presenter = StartupDialogPresenter(
        _make_config(dialect="sqlite", database_path=""),
        bootstrap_callback=fake_bootstrap,
    )

    result = presenter.submit(
        _make_submission(
            mode=StartupDialogMode.CREATE,
            dialect="sqlite",
            database_path=str(tmp_path / "eventlog.db"),
            password="lösenord123",
            password_confirmation="lösenord123",
        )
    )

    assert result.succeeded is True
    assert result.success is not None
    assert result.success.backend_cleanup is backend_cleanup



def test_submit_successfully_hands_off_to_bootstrap_with_sqlite_key_preparer(tmp_path: Path) -> None:
    database_path = tmp_path / "eventlog.db"
    key_file_path = tmp_path / "unlock.key"
    captured: dict[str, object] = {}
    sentinel_repository = cast(BaseRepository, object())

    def fake_bootstrap(request: BootstrapRepositoryRequest) -> BootstrapRepositoryResult:
        captured["target"] = request.target
        captured["creation_defaults"] = request.creation_defaults
        captured["password"] = request.password
        captured["key_file_path"] = request.key_file_path
        captured["create_new_database"] = request.create_new_database
        captured["key_preparer"] = request.key_preparer
        return BootstrapRepositoryResult(repository=sentinel_repository)

    presenter = StartupDialogPresenter(
        _make_config(database_path=str(database_path), require_key_file=True),
        bootstrap_callback=fake_bootstrap,
    )

    result = presenter.submit(
        _make_submission(
            mode=StartupDialogMode.CREATE,
            dialect=" SQLITE ",
            database_path=f"  {database_path}  ",
            password="lösenord123",
            password_confirmation="lösenord123",
            key_file_path=key_file_path,
        )
    )

    assert result.succeeded is True
    assert result.success is not None
    assert result.success.repository is sentinel_repository
    assert result.success.remembered_target.dialect == "sqlite"
    assert result.success.remembered_target.database_path == str(database_path)
    assert result.success.remembered_target.require_key_file is True
    assert captured == {
        "target": _make_config(database_path=str(database_path), require_key_file=True).bootstrap_target,
        "creation_defaults": _make_config(database_path=str(database_path), require_key_file=True).creation_defaults,
        "password": "lösenord123",
        "key_file_path": str(key_file_path),
        "create_new_database": True,
        "key_preparer": prepare_sqlite_encryption_key,
    }


def test_submit_maps_invalid_credentials_to_retryable_password_clear(tmp_path: Path) -> None:
    database_path = tmp_path / "eventlog.db"
    database_path.write_text("", encoding="utf-8")

    def fake_bootstrap(_request):
        return BootstrapRepositoryResult(
            failure=BootstrapFailure(
                BootstrapFailureCode.INVALID_CREDENTIALS,
                GENERIC_INVALID_CREDENTIALS_MESSAGE,
            )
        )

    presenter = StartupDialogPresenter(
        _make_config(database_path=str(database_path)),
        bootstrap_callback=fake_bootstrap,
    )

    result = presenter.submit(
        _make_submission(
            mode=StartupDialogMode.UNLOCK,
            dialect="sqlite",
            database_path=str(database_path),
            password="lösenord123",
        )
    )

    assert result.succeeded is False
    assert result.failure is not None
    assert result.failure.code is StartupDialogFailureCode.INVALID_CREDENTIALS
    assert result.failure.message == GENERIC_INVALID_CREDENTIALS_MESSAGE
    assert result.failure.retryable is True
    assert result.failure.should_clear_password is True
    assert result.failure.should_clear_password_confirmation is False


def test_submit_maps_invalid_key_file_to_field_error(tmp_path: Path) -> None:
    database_path = tmp_path / "eventlog.db"
    database_path.write_text("", encoding="utf-8")

    def fake_bootstrap(_request):
        return BootstrapRepositoryResult(
            failure=BootstrapFailure(
                BootstrapFailureCode.INVALID_KEY_FILE,
                "Kan inte läsa nyckelfilen (behörighet saknas)",
            )
        )

    presenter = StartupDialogPresenter(
        _make_config(require_key_file=True, database_path=str(database_path)),
        bootstrap_callback=fake_bootstrap,
    )

    result = presenter.submit(
        _make_submission(
            mode=StartupDialogMode.UNLOCK,
            dialect="sqlite",
            database_path=str(database_path),
            password="lösenord123",
            key_file_path="C:/keys/secret.key",
        )
    )

    assert result.succeeded is False
    assert result.failure is not None
    assert result.failure.code is StartupDialogFailureCode.INVALID_KEY_FILE
    assert result.failure.field_name == "key_file_path"
    assert result.failure.message == "Kan inte läsa nyckelfilen (behörighet saknas)"


def test_submit_maps_migration_needed_to_dedicated_failure_code(tmp_path: Path) -> None:
    database_path = tmp_path / "eventlog.db"
    database_path.write_text("", encoding="utf-8")

    def fake_bootstrap(_request):
        return BootstrapRepositoryResult(
            failure=BootstrapFailure(
                BootstrapFailureCode.MIGRATION_NEEDED,
                "technical backend detail",
                retryable=False,
            )
        )

    presenter = StartupDialogPresenter(
        _make_config(database_path=str(database_path)),
        bootstrap_callback=fake_bootstrap,
    )

    result = presenter.submit(
        _make_submission(
            mode=StartupDialogMode.UNLOCK,
            dialect="sqlite",
            database_path=str(database_path),
            password="lösenord123",
        )
    )

    assert result.succeeded is False
    assert result.failure is not None
    assert result.failure.code is StartupDialogFailureCode.MIGRATION_NEEDED
    assert result.failure.message == (
        "Databasen behöver migreras innan den kan öppnas. Kör databasmigrering för databasen först."
    )
    assert result.failure.retryable is False
    assert result.failure.should_clear_password is False


def test_submit_maps_database_newer_to_dedicated_failure_code(tmp_path: Path) -> None:
    database_path = tmp_path / "eventlog.db"
    database_path.write_text("", encoding="utf-8")

    def fake_bootstrap(_request):
        return BootstrapRepositoryResult(
            failure=BootstrapFailure(
                BootstrapFailureCode.DATABASE_NEWER,
                "technical backend detail",
                retryable=False,
            )
        )

    presenter = StartupDialogPresenter(
        _make_config(database_path=str(database_path)),
        bootstrap_callback=fake_bootstrap,
    )

    result = presenter.submit(
        _make_submission(
            mode=StartupDialogMode.UNLOCK,
            dialect="sqlite",
            database_path=str(database_path),
            password="lösenord123",
        )
    )

    assert result.succeeded is False
    assert result.failure is not None
    assert result.failure.code is StartupDialogFailureCode.DATABASE_NEWER
    assert result.failure.message == (
        "Databasen kommer från en nyare version av EventLog. Uppdatera applikationen innan du försöker öppna den."
    )
    assert result.failure.retryable is False
    assert result.failure.should_clear_password is False


def test_migrate_successfully_hands_off_to_backend_owned_migration(tmp_path: Path) -> None:
    database_path = tmp_path / "eventlog.db"
    database_path.write_text("", encoding="utf-8")
    captured: dict[str, object] = {}

    def fake_migration(request: MigrationRequest) -> MigrationResult:
        captured["target"] = request.target
        captured["password"] = request.password
        captured["key_file_path"] = request.key_file_path
        captured["key_preparer"] = request.key_preparer
        return MigrationResult(migration_performed=True, message="Databasmigreringen slutfördes.")

    presenter = StartupDialogPresenter(
        _make_config(database_path=str(database_path)),
        migration_callback=fake_migration,
    )

    result = presenter.migrate(
        _make_submission(
            mode=StartupDialogMode.UNLOCK,
            dialect="sqlite",
            database_path=str(database_path),
            password="lösenord123",
        )
    )

    assert result == StartupDialogMigrationResult(message="Databasmigreringen slutfördes.")
    assert captured == {
        "target": _make_config(database_path=str(database_path)).bootstrap_target,
        "password": "lösenord123",
        "key_file_path": None,
        "key_preparer": prepare_sqlite_encryption_key,
    }


def test_migrate_maps_backend_failure_to_presenter_visible_migration_failed_error(tmp_path: Path) -> None:
    database_path = tmp_path / "eventlog.db"
    database_path.write_text("", encoding="utf-8")

    def fake_migration(_request: MigrationRequest) -> MigrationResult:
        return MigrationResult(
            failure=BootstrapFailure(
                BootstrapFailureCode.MIGRATION_FAILED,
                "Migreringssteg saknas för vald databasversion.",
                retryable=False,
            )
        )

    presenter = StartupDialogPresenter(
        _make_config(database_path=str(database_path)),
        migration_callback=fake_migration,
    )

    result = presenter.migrate(
        _make_submission(
            mode=StartupDialogMode.UNLOCK,
            dialect="sqlite",
            database_path=str(database_path),
            password="lösenord123",
        )
    )

    assert result.succeeded is False
    assert result.failure is not None
    assert result.failure.code is StartupDialogFailureCode.MIGRATION_FAILED
    assert result.failure.message == "Migreringssteg saknas för vald databasversion."
    assert result.failure.retryable is False


def test_submit_remembered_unlock_ignores_hidden_manual_target_values() -> None:
    captured: dict[str, object] = {}
    sentinel_repository = cast(BaseRepository, object())

    def fake_bootstrap(request):
        captured["target"] = request.target
        return BootstrapRepositoryResult(repository=sentinel_repository)

    presenter = StartupDialogPresenter(
        _make_config(dialect="sqlite", database_path="C:/Ops/remembered.db"),
        bootstrap_callback=fake_bootstrap,
        startup_mode_resolver=_make_mode_resolver("C:/Ops/remembered.db"),
    )

    result = presenter.submit(
        _make_submission(
            mode=StartupDialogMode.UNLOCK,
            dialect="postgres",
            uses_remembered_target=True,
            database_path="C:/Ops/stale-manual.db",
            password="lösenord123",
        )
    )

    assert result.succeeded is True
    assert captured["target"] == _make_config(
        dialect="sqlite",
        database_path="C:/Ops/remembered.db",
    ).bootstrap_target



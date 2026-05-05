from pathlib import Path
from typing import cast

import pytest

import src.db.repositories.startup_bootstrap as startup_bootstrap_module
from src.config import DatabaseConfig
from src.db.database_adapter import (
    BackendCleanupArtifactMetadata,
    BackendCleanupMetadata,
    DatabaseAdapter,
    DatabaseAdapterError,
    DatabaseNewer,
    EncryptedDatabaseProfileMismatch,
    EncryptedDatabaseUnreadable,
    EncryptedDatabaseWrongKey,
    MigrationNeeded,
)
from src.db.repositories.base_repository import BaseRepository
from src.db.sqlite_key_preparer import SQLITE_PASSWORD_ONLY_KDF_SALT, prepare_sqlite_encryption_key
from src.db.repositories.startup_bootstrap import (
    BackendCleanupConcern,
    BackendCleanupOutcome,
    BackendCleanupReport,
    BackendCleanupStatus,
    BootstrapFailureCode,
    BootstrapRepositoryRequest,
    bootstrap_repository,
    cleanup_remembered_bootstrap_target,
    MigrationRequest,
    MigrationResult,
    migrate_repository,
)
from src.security import GENERIC_INVALID_CREDENTIALS_MESSAGE, PasswordValidationError, derive_encryption_key


pytestmark = pytest.mark.unit


def _make_config(
    *,
    dialect: str = "sqlite",
    database_path: str = "eventlog.db",
    require_key_file: bool = False,
    min_password_length: int = 8,
    secure_delete_passes: int = 3,
) -> DatabaseConfig:
    return DatabaseConfig(
        dialect=dialect,
        database_path=database_path,
        require_key_file=require_key_file,
        min_password_length=min_password_length,
        secure_delete_passes=secure_delete_passes,
    )


def _make_request(
    *,
    config: DatabaseConfig | None = None,
    password: str = "",
    key_file_path: str | Path | None = None,
    create_new_database: bool = False,
    key_preparer=None,
) -> BootstrapRepositoryRequest:
    resolved_config = _make_config() if config is None else config
    return BootstrapRepositoryRequest(
        target=resolved_config.bootstrap_target,
        creation_defaults=resolved_config.creation_defaults,
        password=password,
        key_file_path=key_file_path,
        create_new_database=create_new_database,
        key_preparer=key_preparer,
    )


def _make_migration_request(
    *,
    config: DatabaseConfig | None = None,
    password: str = "",
    key_file_path: str | Path | None = None,
    key_preparer=None,
) -> MigrationRequest:
    resolved_config = _make_config() if config is None else config
    return MigrationRequest(
        target=resolved_config.bootstrap_target,
        creation_defaults=resolved_config.creation_defaults,
        password=password,
        key_file_path=key_file_path,
        key_preparer=key_preparer,
    )


@pytest.mark.parametrize(
    ("config", "create_new_database"),
    [
        (_make_config(database_path=""), False),
        (_make_config(dialect=""), True),
        (_make_config(database_path=""), True),
    ],
)
def test_bootstrap_repository_rejects_incomplete_bootstrap_target(
    config: DatabaseConfig,
    create_new_database: bool,
) -> None:
    result = bootstrap_repository(_make_request(config=config, create_new_database=create_new_database))

    assert result.succeeded is False
    assert result.repository is None
    assert result.failure is not None
    assert result.failure.code is BootstrapFailureCode.INCOMPLETE_BOOTSTRAP_TARGET
    assert result.failure.retryable is True


def test_bootstrap_repository_rejects_unsupported_dialect() -> None:
    result = bootstrap_repository(
        _make_request(config=_make_config(dialect="postgres"), create_new_database=True)
    )

    assert result.succeeded is False
    assert result.repository is None
    assert result.failure is not None
    assert result.failure.code is BootstrapFailureCode.UNSUPPORTED_DIALECT
    assert result.failure.retryable is False


def test_bootstrap_repository_checks_dialect_support_through_factory_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_is_supported_repository_dialect(dialect: str) -> bool:
        captured["dialect"] = dialect
        return False

    monkeypatch.setattr(
        startup_bootstrap_module,
        "is_supported_repository_dialect",
        fake_is_supported_repository_dialect,
    )

    result = bootstrap_repository(
        _make_request(config=_make_config(dialect="postgres"), create_new_database=True)
    )

    assert captured == {"dialect": "postgres"}
    assert result.succeeded is False
    assert result.repository is None
    assert result.failure is not None
    assert result.failure.code is BootstrapFailureCode.UNSUPPORTED_DIALECT
    assert result.failure.retryable is False


def test_bootstrap_repository_requires_key_file_when_bootstrap_target_demands_it() -> None:
    result = bootstrap_repository(
        _make_request(config=_make_config(require_key_file=True), create_new_database=True)
    )

    assert result.succeeded is False
    assert result.failure is not None
    assert result.failure.code is BootstrapFailureCode.MISSING_REQUIRED_KEY_FILE
    assert result.failure.retryable is True


def test_bootstrap_repository_maps_password_validation_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_validate_password(password: str, *, min_length: int) -> None:
        raise PasswordValidationError(f"Lösenord måste vara minst {min_length} tecken")

    monkeypatch.setattr(startup_bootstrap_module, "validate_password", fake_validate_password)

    result = bootstrap_repository(
        _make_request(
            config=_make_config(min_password_length=12),
            password="kort",
            create_new_database=True,
        )
    )

    assert result.succeeded is False
    assert result.failure is not None
    assert result.failure.code is BootstrapFailureCode.INVALID_PASSWORD
    assert result.failure.retryable is True
    assert result.failure.message == "Lösenord måste vara minst 12 tecken"


def test_bootstrap_repository_resolves_backend_key_preparer_from_policy_when_credentials_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}
    sentinel_repository = object()

    monkeypatch.setattr(startup_bootstrap_module, "validate_password", lambda password, *, min_length: None)
    monkeypatch.setattr(
        startup_bootstrap_module.RepositoryFactory,
        "create_event_log_repository",
        staticmethod(
            lambda *, database_path, dialect, encryption_key: captured.update(
                {
                    "database_path": database_path,
                    "dialect": dialect,
                    "encryption_key": encryption_key,
                }
            )
            or sentinel_repository
        ),
    )

    result = bootstrap_repository(
        _make_request(
            config=_make_config(database_path="policy-preparer.db"),
            password="lösenord123",
            create_new_database=True,
        )
    )

    assert result.succeeded is True
    assert result.failure is None
    assert result.repository is sentinel_repository
    assert captured["database_path"] == "policy-preparer.db"
    assert captured["dialect"] == "sqlite"
    encryption_key = captured["encryption_key"]
    assert isinstance(encryption_key, bytes)
    assert len(encryption_key) == 32


@pytest.mark.parametrize("prepared_key", [None, b"", "not-bytes"])
def test_bootstrap_repository_rejects_invalid_prepared_key(
    prepared_key: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(startup_bootstrap_module, "validate_password", lambda password, *, min_length: None)

    result = bootstrap_repository(
        _make_request(
            password="lösenord123",
            create_new_database=True,
            key_preparer=lambda password, key_file_bytes, creation_defaults: prepared_key,  # type: ignore[return-value]
        )
    )

    assert result.succeeded is False
    assert result.failure is not None
    assert result.failure.code is BootstrapFailureCode.INVALID_PREPARED_KEY
    assert result.failure.retryable is False


def test_bootstrap_repository_maps_wrong_key_repository_open_failure_to_invalid_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        startup_bootstrap_module.RepositoryFactory,
        "create_event_log_repository",
        staticmethod(
            lambda **kwargs: (_ for _ in ()).throw(EncryptedDatabaseWrongKey("wrong credentials"))
        ),
    )

    result = bootstrap_repository(_make_request(create_new_database=True))

    assert result.succeeded is False
    assert result.failure is not None
    assert result.failure.code is BootstrapFailureCode.INVALID_CREDENTIALS
    assert result.failure.retryable is True
    assert result.failure.message == GENERIC_INVALID_CREDENTIALS_MESSAGE


def test_bootstrap_repository_maps_profile_mismatch_to_dedicated_failure_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    encrypted_error = EncryptedDatabaseProfileMismatch("profile mismatch")

    monkeypatch.setattr(
        startup_bootstrap_module.RepositoryFactory,
        "create_event_log_repository",
        staticmethod(
            lambda **kwargs: (_ for _ in ()).throw(encrypted_error)
        ),
    )

    result = bootstrap_repository(_make_request(create_new_database=True))

    assert result.succeeded is False
    assert result.failure is not None
    assert result.failure.code is BootstrapFailureCode.PROFILE_MISMATCH
    assert result.failure.retryable is True
    assert result.failure.message == str(encrypted_error)


def test_bootstrap_repository_maps_migration_needed_to_dedicated_failure_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    migration_error = MigrationNeeded("database requires migration")

    monkeypatch.setattr(
        startup_bootstrap_module.RepositoryFactory,
        "create_event_log_repository",
        staticmethod(
            lambda **kwargs: (_ for _ in ()).throw(migration_error)
        ),
    )

    result = bootstrap_repository(_make_request(create_new_database=True))

    assert result.succeeded is False
    assert result.failure is not None
    assert result.failure.code is BootstrapFailureCode.MIGRATION_NEEDED
    assert result.failure.retryable is False
    assert result.failure.message == str(migration_error)


def test_bootstrap_repository_maps_database_newer_to_dedicated_failure_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    newer_error = DatabaseNewer("database was created by a newer app")

    monkeypatch.setattr(
        startup_bootstrap_module.RepositoryFactory,
        "create_event_log_repository",
        staticmethod(
            lambda **kwargs: (_ for _ in ()).throw(newer_error)
        ),
    )

    result = bootstrap_repository(_make_request(create_new_database=True))

    assert result.succeeded is False
    assert result.failure is not None
    assert result.failure.code is BootstrapFailureCode.DATABASE_NEWER
    assert result.failure.retryable is False
    assert result.failure.message == str(newer_error)


def test_migrate_repository_runs_backend_owned_migrator_and_returns_success_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    monkeypatch.setattr(startup_bootstrap_module, "validate_password", lambda password, *, min_length: None)
    monkeypatch.setattr(
        startup_bootstrap_module,
        "migrate_event_log_database",
        lambda *, database_path, dialect, encryption_key: captured.update(
            {
                "database_path": database_path,
                "dialect": dialect,
                "encryption_key": encryption_key,
            }
        )
        or True,
    )

    result = migrate_repository(
        _make_migration_request(
            config=_make_config(database_path="migrate-me.db"),
            password="lösenord123",
            key_preparer=prepare_sqlite_encryption_key,
        )
    )

    assert result == MigrationResult(
        migration_performed=True,
        message="Databasmigreringen slutfördes.",
    )
    assert captured["database_path"] == "migrate-me.db"
    assert captured["dialect"] == "sqlite"
    assert isinstance(captured["encryption_key"], bytes)


def test_migrate_repository_maps_adapter_error_to_migration_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        startup_bootstrap_module,
        "migrate_event_log_database",
        lambda **kwargs: (_ for _ in ()).throw(DatabaseAdapterError("migration failed")),
    )

    result = migrate_repository(_make_migration_request(config=_make_config(database_path="migrate-me.db")))

    assert result.succeeded is False
    assert result.failure is not None
    assert result.failure.code is BootstrapFailureCode.MIGRATION_FAILED
    assert result.failure.message == "migration failed"


def test_bootstrap_repository_maps_unreadable_encrypted_repository_open_failure_to_repository_open_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    encrypted_error = EncryptedDatabaseUnreadable("database unreadable")

    monkeypatch.setattr(
        startup_bootstrap_module.RepositoryFactory,
        "create_event_log_repository",
        staticmethod(
            lambda **kwargs: (_ for _ in ()).throw(encrypted_error)
        ),
    )

    result = bootstrap_repository(_make_request(create_new_database=True))

    assert result.succeeded is False
    assert result.failure is not None
    assert result.failure.code is BootstrapFailureCode.REPOSITORY_OPEN_FAILED
    assert result.failure.retryable is True
    assert result.failure.message == str(encrypted_error)


def test_bootstrap_repository_maps_generic_adapter_open_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        startup_bootstrap_module.RepositoryFactory,
        "create_event_log_repository",
        staticmethod(
            lambda **kwargs: (_ for _ in ()).throw(DatabaseAdapterError("adapter failed"))
        ),
    )

    result = bootstrap_repository(_make_request(create_new_database=True))

    assert result.succeeded is False
    assert result.failure is not None
    assert result.failure.code is BootstrapFailureCode.REPOSITORY_OPEN_FAILED
    assert result.failure.retryable is True
    assert result.failure.message == "adapter failed"


def test_bootstrap_repository_successfully_loads_key_material_prepares_key_and_opens_repository(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "bootstrap.db"
    config = _make_config(database_path=str(database_path), min_password_length=12)
    captured: dict[str, object] = {}
    sentinel_repository = object()
    loaded_key_file_bytes = b"key-file-bytes"
    prepared_key = bytes.fromhex(
        "00112233445566778899aabbccddeeff00112233445566778899aabbccddeeff"
    )

    def fake_validate_password(password: str, *, min_length: int) -> None:
        captured["validated_password"] = password
        captured["validated_min_length"] = min_length

    def fake_load_key_file_bytes(file_path: str | Path) -> bytes:
        captured["key_file_path"] = str(file_path)
        return loaded_key_file_bytes

    def fake_key_preparer(password: str, key_file_bytes: bytes | None, creation_defaults) -> bytes:
        captured["prepared_password"] = password
        captured["prepared_key_file_bytes"] = key_file_bytes
        captured["prepared_creation_defaults"] = creation_defaults
        return prepared_key

    def fake_create_event_log_repository(*, database_path: str, dialect: str, encryption_key: bytes | None):
        captured["factory_database_path"] = database_path
        captured["factory_dialect"] = dialect
        captured["factory_encryption_key"] = encryption_key
        return sentinel_repository

    monkeypatch.setattr(startup_bootstrap_module, "validate_password", fake_validate_password)
    monkeypatch.setattr(startup_bootstrap_module, "load_key_file_bytes", fake_load_key_file_bytes)
    monkeypatch.setattr(
        startup_bootstrap_module.RepositoryFactory,
        "create_event_log_repository",
        staticmethod(fake_create_event_log_repository),
    )

    result = bootstrap_repository(
        _make_request(
            config=config,
            password="lösenord12345",
            key_file_path=database_path.with_suffix(".key"),
            create_new_database=True,
            key_preparer=fake_key_preparer,
        )
    )

    assert result.succeeded is True
    assert result.failure is None
    assert result.repository is sentinel_repository
    assert captured == {
        "validated_password": "lösenord12345",
        "validated_min_length": 12,
        "key_file_path": str(database_path.with_suffix(".key")),
        "prepared_password": "lösenord12345",
        "prepared_key_file_bytes": loaded_key_file_bytes,
        "prepared_creation_defaults": config.creation_defaults,
        "factory_database_path": str(database_path),
        "factory_dialect": config.dialect,
        "factory_encryption_key": prepared_key,
    }


def test_bootstrap_repository_can_use_sqlite_key_preparer_bridge(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "sqlite-bridge.db"
    config = DatabaseConfig(
        dialect="sqlite",
        database_path=str(database_path),
        min_password_length=8,
        kdf_iterations=2,
    )
    captured: dict[str, object] = {}
    sentinel_repository = object()

    def fake_create_event_log_repository(*, database_path: str, dialect: str, encryption_key: bytes | None):
        captured["database_path"] = database_path
        captured["dialect"] = dialect
        captured["encryption_key"] = encryption_key
        return sentinel_repository

    monkeypatch.setattr(
        startup_bootstrap_module.RepositoryFactory,
        "create_event_log_repository",
        staticmethod(fake_create_event_log_repository),
    )

    result = bootstrap_repository(
        _make_request(
            config=config,
            password="lösenord123",
            create_new_database=True,
            key_preparer=prepare_sqlite_encryption_key,
        )
    )

    assert result.succeeded is True
    assert result.failure is None
    assert result.repository is sentinel_repository
    assert captured == {
        "database_path": str(database_path),
        "dialect": "sqlite",
        "encryption_key": derive_encryption_key(
            "lösenord123",
            salt=SQLITE_PASSWORD_ONLY_KDF_SALT,
            iterations=2,
            length=32,
        ),
    }


def test_bootstrap_repository_returns_idempotent_access_invalidator_on_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    close_calls: list[str] = []

    class StubAdapter(DatabaseAdapter):
        def connect(self) -> None:
            return None

        def initialize_schema(self) -> None:
            return None

        def execute(self, query: str, params=()):
            return None

        def fetch(self, query: str, params=()):
            return []

        def fetchone(self, query: str, params=()):
            return None

        def begin_transaction(self) -> None:
            return None

        def commit_transaction(self) -> None:
            return None

        def rollback_transaction(self) -> None:
            return None

        def close(self) -> None:
            close_calls.append("close")

    repository = BaseRepository(StubAdapter())

    monkeypatch.setattr(
        startup_bootstrap_module.RepositoryFactory,
        "create_event_log_repository",
        staticmethod(lambda **kwargs: repository),
    )

    result = bootstrap_repository(_make_request(create_new_database=True))

    assert result.succeeded is True
    assert result.repository is repository
    assert result.invalidate_access is not None

    result.invalidate_access()
    result.invalidate_access()

    assert close_calls == ["close"]



def test_bootstrap_repository_backend_cleanup_releases_active_persistence_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    close_calls: list[str] = []

    class StubAdapter(DatabaseAdapter):
        def connect(self) -> None:
            return None

        def initialize_schema(self) -> None:
            return None

        def execute(self, query: str, params=()):
            return None

        def fetch(self, query: str, params=()):
            return []

        def fetchone(self, query: str, params=()):
            return None

        def begin_transaction(self) -> None:
            return None

        def commit_transaction(self) -> None:
            return None

        def rollback_transaction(self) -> None:
            return None

        def close(self) -> None:
            close_calls.append("close")

    repository = BaseRepository(StubAdapter())

    monkeypatch.setattr(
        startup_bootstrap_module.RepositoryFactory,
        "create_event_log_repository",
        staticmethod(lambda **kwargs: repository),
    )

    result = bootstrap_repository(_make_request(create_new_database=True))

    assert result.succeeded is True
    assert result.repository is repository
    assert result.backend_cleanup is not None
    assert result.backend_cleanup() == BackendCleanupOutcome(
        status=BackendCleanupStatus.COMPLETED,
        cleanup_performed=True,
        detail="Backend cleanup preparation released active persistence access.",
    )
    assert close_calls == ["close"]


def test_bootstrap_repository_backend_cleanup_deletes_adapter_cleanup_targets(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    close_calls: list[str] = []
    cleanup_steps: list[tuple[str, Path, int | None]] = []
    database_path = tmp_path / "eventlog.db"
    wal_path = Path(f"{database_path}-wal")
    database_path.write_text("db", encoding="utf-8")
    wal_path.write_text("wal", encoding="utf-8")
    original_unlink = Path.unlink

    class StubAdapter(DatabaseAdapter):
        def connect(self) -> None:
            return None

        def initialize_schema(self) -> None:
            return None

        def execute(self, query: str, params=()):
            return None

        def fetch(self, query: str, params=()):
            return []

        def fetchone(self, query: str, params=()):
            return None

        def begin_transaction(self) -> None:
            return None

        def commit_transaction(self) -> None:
            return None

        def rollback_transaction(self) -> None:
            return None

        def close(self) -> None:
            close_calls.append("close")

        def get_cleanup_target_paths(self) -> tuple[Path, ...]:
            return tuple(path for path in (database_path, wal_path) if path.exists())

    repository = BaseRepository(StubAdapter())

    monkeypatch.setattr(
        startup_bootstrap_module.RepositoryFactory,
        "create_event_log_repository",
        staticmethod(lambda **kwargs: repository),
    )
    monkeypatch.setattr(
        startup_bootstrap_module,
        "best_effort_secure_delete",
        lambda path, *, allow_secure_overwrite, secure_delete_passes: (
            cleanup_steps.append(("overwrite", path, secure_delete_passes))
            if allow_secure_overwrite
            else None,
            cleanup_steps.append(("unlink", path, None)),
            original_unlink(path, missing_ok=True),
        )[-1],
    )

    result = bootstrap_repository(
        _make_request(
            config=_make_config(database_path=str(database_path), secure_delete_passes=5),
            create_new_database=True,
        )
    )

    assert result.succeeded is True
    assert result.backend_cleanup is not None

    assert result.backend_cleanup() == BackendCleanupOutcome(
        status=BackendCleanupStatus.COMPLETED,
        cleanup_performed=True,
        detail="Backend cleanup preparation released active persistence access and removed 2 backend-owned active artifacts.",
    )
    assert close_calls == ["close"]
    assert cleanup_steps == [
        ("overwrite", database_path, 5),
        ("unlink", database_path, None),
        ("overwrite", wal_path, 5),
        ("unlink", wal_path, None),
    ]
    assert database_path.exists() is False
    assert wal_path.exists() is False


def test_bootstrap_repository_backend_cleanup_uses_backend_owned_metadata_for_reporting_and_overwrite_policy(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    close_calls: list[str] = []
    cleanup_steps: list[tuple[str, Path, int | None]] = []
    database_path = tmp_path / "eventlog.db"
    wal_path = Path(f"{database_path}-wal")
    database_path.write_text("db", encoding="utf-8")
    wal_path.write_text("wal", encoding="utf-8")
    original_unlink = Path.unlink

    class StubAdapter(DatabaseAdapter):
        def connect(self) -> None:
            return None

        def initialize_schema(self) -> None:
            return None

        def execute(self, query: str, params=()):
            return None

        def fetch(self, query: str, params=()):
            return []

        def fetchone(self, query: str, params=()):
            return None

        def begin_transaction(self) -> None:
            return None

        def commit_transaction(self) -> None:
            return None

        def rollback_transaction(self) -> None:
            return None

        def close(self) -> None:
            close_calls.append("close")

        def get_cleanup_metadata(self) -> BackendCleanupMetadata:
            return BackendCleanupMetadata(
                artifacts=(
                    BackendCleanupArtifactMetadata(
                        path=database_path,
                        artifact_kind="sqlite_main_database",
                    ),
                    BackendCleanupArtifactMetadata(
                        path=wal_path,
                        artifact_kind="sqlite_wal_sidecar",
                        allow_secure_overwrite=False,
                    ),
                )
            )

    repository = BaseRepository(StubAdapter())

    monkeypatch.setattr(
        startup_bootstrap_module.RepositoryFactory,
        "create_event_log_repository",
        staticmethod(lambda **kwargs: repository),
    )
    monkeypatch.setattr(
        startup_bootstrap_module,
        "best_effort_secure_delete",
        lambda path, *, allow_secure_overwrite, secure_delete_passes: (
            cleanup_steps.append(("overwrite", path, secure_delete_passes))
            if allow_secure_overwrite
            else None,
            cleanup_steps.append(("unlink", path, None)),
            original_unlink(path, missing_ok=True),
        )[-1],
    )

    result = bootstrap_repository(
        _make_request(
            config=_make_config(database_path=str(database_path), secure_delete_passes=5),
            create_new_database=True,
        )
    )

    assert result.succeeded is True
    assert result.backend_cleanup is not None

    outcome = result.backend_cleanup()

    assert outcome == BackendCleanupOutcome(
        status=BackendCleanupStatus.COMPLETED,
        cleanup_performed=True,
        detail="Backend cleanup preparation released active persistence access and removed 2 backend-owned active artifacts.",
    )
    assert outcome.report == BackendCleanupReport(
        access_release_performed=True,
        artifacts_enumerated=2,
        artifacts_removed=2,
        artifacts_failed=0,
        removed_concerns=(BackendCleanupConcern.DATABASE_ARTIFACTS,),
        failed_concerns=(),
        removed_artifact_kinds=("sqlite_main_database", "sqlite_wal_sidecar"),
        failed_artifact_kinds=(),
    )
    assert close_calls == ["close"]
    assert cleanup_steps == [
        ("overwrite", database_path, 5),
        ("unlink", database_path, None),
        ("unlink", wal_path, None),
    ]
    assert database_path.exists() is False
    assert wal_path.exists() is False


def test_bootstrap_repository_backend_cleanup_appends_runtime_known_key_file_to_backend_owned_artifacts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    close_calls: list[str] = []
    cleanup_steps: list[tuple[str, Path, int | None]] = []
    database_path = tmp_path / "eventlog.db"
    key_file_path = tmp_path / "active.key"
    database_path.write_text("db", encoding="utf-8")
    key_file_path.write_text("secret", encoding="utf-8")
    original_unlink = Path.unlink

    class StubAdapter(DatabaseAdapter):
        def connect(self) -> None:
            return None

        def initialize_schema(self) -> None:
            return None

        def execute(self, query: str, params=()):
            return None

        def fetch(self, query: str, params=()):
            return []

        def fetchone(self, query: str, params=()):
            return None

        def begin_transaction(self) -> None:
            return None

        def commit_transaction(self) -> None:
            return None

        def rollback_transaction(self) -> None:
            return None

        def close(self) -> None:
            close_calls.append("close")

        def get_cleanup_metadata(self) -> BackendCleanupMetadata:
            return BackendCleanupMetadata(
                artifacts=(
                    BackendCleanupArtifactMetadata(
                        path=database_path,
                        artifact_kind="sqlite_main_database",
                    ),
                )
            )

    repository = BaseRepository(StubAdapter())

    monkeypatch.setattr(
        startup_bootstrap_module.RepositoryFactory,
        "create_event_log_repository",
        staticmethod(lambda **kwargs: repository),
    )
    monkeypatch.setattr(startup_bootstrap_module, "load_key_file_bytes", lambda file_path: b"key-bytes")
    monkeypatch.setattr(
        startup_bootstrap_module,
        "best_effort_secure_delete",
        lambda path, *, allow_secure_overwrite, secure_delete_passes: (
            cleanup_steps.append(("overwrite", path, secure_delete_passes))
            if allow_secure_overwrite
            else None,
            cleanup_steps.append(("unlink", path, None)),
            original_unlink(path, missing_ok=True),
        )[-1],
    )

    result = bootstrap_repository(
        _make_request(
            config=_make_config(database_path=str(database_path), secure_delete_passes=4),
            key_file_path=key_file_path,
            create_new_database=True,
            key_preparer=lambda password, key_file_bytes, creation_defaults: b"x" * 32,
        )
    )

    assert result.succeeded is True
    assert result.backend_cleanup is not None

    outcome = result.backend_cleanup()

    assert outcome == BackendCleanupOutcome(
        status=BackendCleanupStatus.COMPLETED,
        cleanup_performed=True,
        detail="Backend cleanup preparation released active persistence access and removed 1 backend-owned active artifacts.",
    )
    assert outcome.report == BackendCleanupReport(
        access_release_performed=True,
        artifacts_enumerated=1,
        artifacts_removed=1,
        artifacts_failed=0,
        removed_concerns=(BackendCleanupConcern.DATABASE_ARTIFACTS,),
        failed_concerns=(),
        removed_artifact_kinds=("sqlite_main_database",),
        failed_artifact_kinds=(),
    )
    assert close_calls == ["close"]
    assert cleanup_steps == [
        ("overwrite", database_path, 4),
        ("unlink", database_path, None),
    ]
    assert database_path.exists() is False
    assert key_file_path.exists() is True


def test_bootstrap_repository_backend_cleanup_raises_sanitized_error_when_artifact_delete_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    close_calls: list[str] = []
    database_path = tmp_path / "eventlog.db"
    wal_path = Path(f"{database_path}-wal")
    database_path.write_text("db", encoding="utf-8")
    wal_path.write_text("wal", encoding="utf-8")
    original_unlink = Path.unlink

    class StubAdapter(DatabaseAdapter):
        def connect(self) -> None:
            return None

        def initialize_schema(self) -> None:
            return None

        def execute(self, query: str, params=()):
            return None

        def fetch(self, query: str, params=()):
            return []

        def fetchone(self, query: str, params=()):
            return None

        def begin_transaction(self) -> None:
            return None

        def commit_transaction(self) -> None:
            return None

        def rollback_transaction(self) -> None:
            return None

        def close(self) -> None:
            close_calls.append("close")

        def get_cleanup_target_paths(self) -> tuple[Path, ...]:
            return tuple(path for path in (database_path, wal_path) if path.exists())

    def fake_unlink(self: Path, *, missing_ok: bool = False) -> None:
        if self == database_path:
            raise OSError("locked")
        original_unlink(self, missing_ok=missing_ok)  # type: ignore[arg-type]

    repository = BaseRepository(StubAdapter())

    monkeypatch.setattr(
        startup_bootstrap_module.RepositoryFactory,
        "create_event_log_repository",
        staticmethod(lambda **kwargs: repository),
    )
    monkeypatch.setattr(Path, "unlink", fake_unlink)

    result = bootstrap_repository(
        _make_request(config=_make_config(database_path=str(database_path)), create_new_database=True)
    )

    assert result.succeeded is True
    assert result.backend_cleanup is not None

    with pytest.raises(RuntimeError) as exc_info:
        result.backend_cleanup()

    assert str(exc_info.value) == "Backend cleanup could not remove one or more backend-owned active artifacts."
    assert isinstance(exc_info.value, startup_bootstrap_module.BackendCleanupError)
    cleanup_error = cast(startup_bootstrap_module.BackendCleanupError, exc_info.value)
    assert cleanup_error.outcome == BackendCleanupOutcome(
        status=BackendCleanupStatus.PARTIAL,
        cleanup_performed=True,
        detail=(
            "Backend cleanup released active persistence access and removed 0 backend-owned active artifacts "
            "before encountering a later cleanup failure."
        ),
    )
    assert close_calls == ["close"]
    assert database_path.exists() is True
    assert wal_path.exists() is True


def test_bootstrap_repository_backend_cleanup_keeps_partial_deletion_when_later_artifact_delete_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    close_calls: list[str] = []
    database_path = tmp_path / "eventlog.db"
    wal_path = Path(f"{database_path}-wal")
    database_path.write_text("db", encoding="utf-8")
    wal_path.write_text("wal", encoding="utf-8")
    original_unlink = Path.unlink

    class StubAdapter(DatabaseAdapter):
        def connect(self) -> None:
            return None

        def initialize_schema(self) -> None:
            return None

        def execute(self, query: str, params=()):
            return None

        def fetch(self, query: str, params=()):
            return []

        def fetchone(self, query: str, params=()):
            return None

        def begin_transaction(self) -> None:
            return None

        def commit_transaction(self) -> None:
            return None

        def rollback_transaction(self) -> None:
            return None

        def close(self) -> None:
            close_calls.append("close")

        def get_cleanup_target_paths(self) -> tuple[Path, ...]:
            return tuple(path for path in (database_path, wal_path) if path.exists())

    def fake_unlink(self: Path, *, missing_ok: bool = False) -> None:
        if self == wal_path:
            raise OSError("locked")
        original_unlink(self, missing_ok=missing_ok)  # type: ignore[arg-type]

    repository = BaseRepository(StubAdapter())

    monkeypatch.setattr(
        startup_bootstrap_module.RepositoryFactory,
        "create_event_log_repository",
        staticmethod(lambda **kwargs: repository),
    )
    monkeypatch.setattr(Path, "unlink", fake_unlink)

    result = bootstrap_repository(
        _make_request(config=_make_config(database_path=str(database_path)), create_new_database=True)
    )

    assert result.succeeded is True
    assert result.backend_cleanup is not None

    with pytest.raises(RuntimeError) as exc_info:
        result.backend_cleanup()

    assert str(exc_info.value) == "Backend cleanup could not remove one or more backend-owned active artifacts."
    assert isinstance(exc_info.value, startup_bootstrap_module.BackendCleanupError)
    cleanup_error = cast(startup_bootstrap_module.BackendCleanupError, exc_info.value)
    assert cleanup_error.outcome == BackendCleanupOutcome(
        status=BackendCleanupStatus.PARTIAL,
        cleanup_performed=True,
        detail=(
            "Backend cleanup released active persistence access and removed 1 backend-owned active artifacts "
            "before encountering a later cleanup failure."
        ),
    )
    assert close_calls == ["close"]
    assert database_path.exists() is False
    assert wal_path.exists() is True


def test_bootstrap_repository_backend_cleanup_continues_after_middle_artifact_delete_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    close_calls: list[str] = []
    database_path = tmp_path / "eventlog.db"
    wal_path = Path(f"{database_path}-wal")
    shm_path = Path(f"{database_path}-shm")
    database_path.write_text("db", encoding="utf-8")
    wal_path.write_text("wal", encoding="utf-8")
    shm_path.write_text("shm", encoding="utf-8")
    wal_handle = wal_path.open("rb")

    class StubAdapter(DatabaseAdapter):
        def connect(self) -> None:
            return None

        def initialize_schema(self) -> None:
            return None

        def execute(self, query: str, params=()):
            return None

        def fetch(self, query: str, params=()):
            return []

        def fetchone(self, query: str, params=()):
            return None

        def begin_transaction(self) -> None:
            return None

        def commit_transaction(self) -> None:
            return None

        def rollback_transaction(self) -> None:
            return None

        def close(self) -> None:
            close_calls.append("close")

        def get_cleanup_target_paths(self) -> tuple[Path, ...]:
            return tuple(path for path in (database_path, wal_path, shm_path) if path.exists())

    repository = BaseRepository(StubAdapter())

    monkeypatch.setattr(
        startup_bootstrap_module.RepositoryFactory,
        "create_event_log_repository",
        staticmethod(lambda **kwargs: repository),
    )
    monkeypatch.setattr(
        startup_bootstrap_module,
        "best_effort_secure_delete",
        lambda path, **kwargs: path.unlink(missing_ok=True),
    )

    result = bootstrap_repository(
        _make_request(config=_make_config(database_path=str(database_path)), create_new_database=True)
    )

    assert result.succeeded is True
    assert result.backend_cleanup is not None

    try:
        with pytest.raises(RuntimeError) as exc_info:
            result.backend_cleanup()

        assert str(exc_info.value) == "Backend cleanup could not remove one or more backend-owned active artifacts."
        assert isinstance(exc_info.value, startup_bootstrap_module.BackendCleanupError)
        cleanup_error = cast(startup_bootstrap_module.BackendCleanupError, exc_info.value)
        assert cleanup_error.outcome == BackendCleanupOutcome(
            status=BackendCleanupStatus.PARTIAL,
            cleanup_performed=True,
            detail=(
                "Backend cleanup released active persistence access and removed 2 backend-owned active artifacts "
                "before encountering a later cleanup failure."
            ),
        )
        assert close_calls == ["close"]
        assert database_path.exists() is False
        assert wal_path.exists() is True
        assert shm_path.exists() is False
    finally:
        wal_handle.close()
        wal_path.unlink(missing_ok=True)


def test_bootstrap_repository_backend_cleanup_retry_after_partial_failure_targets_only_remaining_artifacts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    close_calls: list[str] = []
    database_path = tmp_path / "eventlog.db"
    wal_path = Path(f"{database_path}-wal")
    shm_path = Path(f"{database_path}-shm")
    database_path.write_text("db", encoding="utf-8")
    wal_path.write_text("wal", encoding="utf-8")
    shm_path.write_text("shm", encoding="utf-8")
    wal_handle = wal_path.open("rb")

    class StubAdapter(DatabaseAdapter):
        def connect(self) -> None:
            return None

        def initialize_schema(self) -> None:
            return None

        def execute(self, query: str, params=()):
            return None

        def fetch(self, query: str, params=()):
            return []

        def fetchone(self, query: str, params=()):
            return None

        def begin_transaction(self) -> None:
            return None

        def commit_transaction(self) -> None:
            return None

        def rollback_transaction(self) -> None:
            return None

        def close(self) -> None:
            close_calls.append("close")

        def get_cleanup_target_paths(self) -> tuple[Path, ...]:
            return tuple(path for path in (database_path, wal_path, shm_path) if path.exists())

    repository = BaseRepository(StubAdapter())

    monkeypatch.setattr(
        startup_bootstrap_module.RepositoryFactory,
        "create_event_log_repository",
        staticmethod(lambda **kwargs: repository),
    )
    monkeypatch.setattr(
        startup_bootstrap_module,
        "best_effort_secure_delete",
        lambda path, **kwargs: path.unlink(missing_ok=True),
    )

    result = bootstrap_repository(
        _make_request(config=_make_config(database_path=str(database_path)), create_new_database=True)
    )

    assert result.succeeded is True
    assert result.backend_cleanup is not None

    try:
        with pytest.raises(RuntimeError) as exc_info:
            result.backend_cleanup()

        assert isinstance(exc_info.value, startup_bootstrap_module.BackendCleanupError)
        cleanup_error = cast(startup_bootstrap_module.BackendCleanupError, exc_info.value)
        assert cleanup_error.outcome == BackendCleanupOutcome(
            status=BackendCleanupStatus.PARTIAL,
            cleanup_performed=True,
            detail=(
                "Backend cleanup released active persistence access and removed 2 backend-owned active artifacts "
                "before encountering a later cleanup failure."
            ),
        )
        assert close_calls == ["close"]
        assert database_path.exists() is False
        assert wal_path.exists() is True
        assert shm_path.exists() is False

        wal_handle.close()

        assert result.backend_cleanup() == BackendCleanupOutcome(
            status=BackendCleanupStatus.COMPLETED,
            cleanup_performed=True,
            detail="Backend cleanup preparation removed 1 backend-owned active artifacts after access was already released.",
        )
        assert close_calls == ["close"]
        assert database_path.exists() is False
        assert wal_path.exists() is False
        assert shm_path.exists() is False
    finally:
        wal_handle.close()
        wal_path.unlink(missing_ok=True)



def test_bootstrap_repository_backend_cleanup_falls_back_to_delete_when_overwrite_attempt_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    close_calls: list[str] = []
    unlink_calls: list[Path] = []
    database_path = tmp_path / "eventlog.db"
    wal_path = Path(f"{database_path}-wal")
    database_path.write_text("db", encoding="utf-8")
    wal_path.write_text("wal", encoding="utf-8")
    original_unlink = Path.unlink

    class StubAdapter(DatabaseAdapter):
        def connect(self) -> None:
            return None

        def initialize_schema(self) -> None:
            return None

        def execute(self, query: str, params=()):
            return None

        def fetch(self, query: str, params=()):
            return []

        def fetchone(self, query: str, params=()):
            return None

        def begin_transaction(self) -> None:
            return None

        def commit_transaction(self) -> None:
            return None

        def rollback_transaction(self) -> None:
            return None

        def close(self) -> None:
            close_calls.append("close")

        def get_cleanup_target_paths(self) -> tuple[Path, ...]:
            return tuple(path for path in (database_path, wal_path) if path.exists())

    def fake_open(self: Path, mode: str = "r", *args, **kwargs):
        if self == database_path and mode == "r+b":
            raise OSError("overwrite blocked")
        return open(self, mode, *args, **kwargs)

    def fake_unlink(self: Path, *, missing_ok: bool = False) -> None:
        unlink_calls.append(self)
        original_unlink(self, missing_ok=missing_ok)  # type: ignore[arg-type]

    repository = BaseRepository(StubAdapter())

    monkeypatch.setattr(
        startup_bootstrap_module.RepositoryFactory,
        "create_event_log_repository",
        staticmethod(lambda **kwargs: repository),
    )
    monkeypatch.setattr(Path, "open", fake_open)
    monkeypatch.setattr(Path, "unlink", fake_unlink)

    result = bootstrap_repository(
        _make_request(
            config=_make_config(database_path=str(database_path), secure_delete_passes=2),
            create_new_database=True,
        )
    )

    assert result.succeeded is True
    assert result.backend_cleanup is not None
    assert result.backend_cleanup() == BackendCleanupOutcome(
        status=BackendCleanupStatus.COMPLETED,
        cleanup_performed=True,
        detail="Backend cleanup preparation released active persistence access and removed 2 backend-owned active artifacts.",
    )
    assert close_calls == ["close"]
    assert unlink_calls == [database_path, wal_path]
    assert database_path.exists() is False
    assert wal_path.exists() is False



def test_bootstrap_repository_backend_cleanup_is_idempotent_after_access_invalidation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    close_calls: list[str] = []
    database_path = tmp_path / "eventlog.db"
    wal_path = Path(f"{database_path}-wal")
    database_path.write_text("db", encoding="utf-8")
    wal_path.write_text("wal", encoding="utf-8")

    class StubAdapter(DatabaseAdapter):
        def connect(self) -> None:
            return None

        def initialize_schema(self) -> None:
            return None

        def execute(self, query: str, params=()):
            return None

        def fetch(self, query: str, params=()):
            return []

        def fetchone(self, query: str, params=()):
            return None

        def begin_transaction(self) -> None:
            return None

        def commit_transaction(self) -> None:
            return None

        def rollback_transaction(self) -> None:
            return None

        def close(self) -> None:
            close_calls.append("close")

        def get_cleanup_target_paths(self) -> tuple[Path, ...]:
            return tuple(path for path in (database_path, wal_path) if path.exists())

    repository = BaseRepository(StubAdapter())

    monkeypatch.setattr(
        startup_bootstrap_module.RepositoryFactory,
        "create_event_log_repository",
        staticmethod(lambda **kwargs: repository),
    )

    result = bootstrap_repository(_make_request(create_new_database=True))

    assert result.succeeded is True
    assert result.invalidate_access is not None
    assert result.backend_cleanup is not None

    result.invalidate_access()

    assert result.backend_cleanup() == BackendCleanupOutcome(
        status=BackendCleanupStatus.COMPLETED,
        cleanup_performed=True,
        detail="Backend cleanup preparation removed 2 backend-owned active artifacts after access was already released.",
    )
    assert close_calls == ["close"]
    assert database_path.exists() is False
    assert wal_path.exists() is False

    assert result.backend_cleanup() == BackendCleanupOutcome(
        status=BackendCleanupStatus.COMPLETED,
        cleanup_performed=False,
        detail="Backend cleanup preparation was already complete for the active persistence context.",
    )
    assert close_calls == ["close"]


def test_cleanup_remembered_bootstrap_target_deletes_sqlite_database_and_sidecars(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    cleanup_steps: list[tuple[str, Path, int | None]] = []
    database_path = tmp_path / "remembered.db"
    wal_path = Path(f"{database_path}-wal")
    shm_path = Path(f"{database_path}-shm")
    database_path.write_text("db", encoding="utf-8")
    wal_path.write_text("wal", encoding="utf-8")
    shm_path.write_text("shm", encoding="utf-8")
    original_unlink = Path.unlink

    monkeypatch.setattr(
        startup_bootstrap_module,
        "best_effort_secure_delete",
        lambda path, *, allow_secure_overwrite, secure_delete_passes: (
            cleanup_steps.append(("overwrite", path, secure_delete_passes))
            if allow_secure_overwrite
            else None,
            cleanup_steps.append(("unlink", path, None)),
            original_unlink(path, missing_ok=True),
        )[-1],
    )

    outcome = cleanup_remembered_bootstrap_target(
        _make_config(database_path=str(database_path), secure_delete_passes=4)
    )

    assert outcome == BackendCleanupOutcome(
        status=BackendCleanupStatus.COMPLETED,
        cleanup_performed=True,
        detail="Backend cleanup preparation removed 3 backend-owned remembered-target artifacts.",
    )
    assert outcome.report == BackendCleanupReport(
        access_release_performed=False,
        artifacts_enumerated=3,
        artifacts_removed=3,
        artifacts_failed=0,
        removed_concerns=(BackendCleanupConcern.DATABASE_ARTIFACTS,),
        failed_concerns=(),
        removed_artifact_kinds=(
            "sqlite_main_database",
            "sqlite_wal_sidecar",
            "sqlite_shm_sidecar",
        ),
        failed_artifact_kinds=(),
    )
    assert cleanup_steps == [
        ("overwrite", database_path, 4),
        ("unlink", database_path, None),
        ("overwrite", wal_path, 4),
        ("unlink", wal_path, None),
        ("overwrite", shm_path, 4),
        ("unlink", shm_path, None),
    ]
    assert database_path.exists() is False
    assert wal_path.exists() is False
    assert shm_path.exists() is False


def test_cleanup_remembered_bootstrap_target_raises_sanitized_partial_failure_for_remaining_artifacts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "remembered.db"
    wal_path = Path(f"{database_path}-wal")
    database_path.write_text("db", encoding="utf-8")
    wal_path.write_text("wal", encoding="utf-8")
    original_unlink = Path.unlink

    def fake_unlink(self: Path, *, missing_ok: bool = False) -> None:
        if self == wal_path:
            raise OSError("locked")
        original_unlink(self, missing_ok=missing_ok)  # type: ignore[arg-type]

    monkeypatch.setattr(Path, "unlink", fake_unlink)

    with pytest.raises(startup_bootstrap_module.BackendCleanupError) as exc_info:
        cleanup_remembered_bootstrap_target(_make_config(database_path=str(database_path)))

    assert str(exc_info.value) == (
        "Backend cleanup could not remove one or more backend-owned remembered-target artifacts."
    )
    assert exc_info.value.outcome == BackendCleanupOutcome(
        status=BackendCleanupStatus.PARTIAL,
        cleanup_performed=True,
        detail=(
            "Backend cleanup preparation removed 1 backend-owned remembered-target artifacts "
            "before encountering a later cleanup failure."
        ),
    )
    assert exc_info.value.outcome.report == BackendCleanupReport(
        access_release_performed=False,
        artifacts_enumerated=2,
        artifacts_removed=1,
        artifacts_failed=1,
        removed_concerns=(BackendCleanupConcern.DATABASE_ARTIFACTS,),
        failed_concerns=(BackendCleanupConcern.DATABASE_ARTIFACTS,),
        removed_artifact_kinds=("sqlite_main_database",),
        failed_artifact_kinds=("sqlite_wal_sidecar",),
    )
    assert database_path.exists() is False
    assert wal_path.exists() is True




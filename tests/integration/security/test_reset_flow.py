from __future__ import annotations

from pathlib import Path

import pytest

from src.config import DatabaseConfig
from src.db import sqlite_adapter as sqlite_adapter_module
from src.db.repositories.startup_bootstrap import (
    BackendCleanupConcern,
    BackendCleanupError,
    BackendCleanupOutcome,
    BackendCleanupReport,
    BackendCleanupStatus,
    BootstrapRepositoryRequest,
    bootstrap_repository,
)
from src.db.repositories.sqlite.event_log_repository import EventLogRepository
from src.db.sqlite_key_preparer import prepare_sqlite_encryption_key
from src.security import ResetCoordinator, ResetFailureCategory, ResetOutcome


pytestmark = pytest.mark.integration


DEFAULT_TEST_PASSWORD = "lösenord123"
TEST_KEY_FILE_BYTES = b"reset-flow-key-file-material-2026"
TEST_KDF_ITERATIONS = 2


SQLITE_RESET_CREDENTIAL_SCENARIOS = (
    pytest.param("", False, False, id="no_key_no_keyfile"),
    pytest.param(DEFAULT_TEST_PASSWORD, False, False, id="key_no_keyfile"),
    pytest.param(DEFAULT_TEST_PASSWORD, True, True, id="key_keyfile"),
    pytest.param("", True, True, id="no_key_keyfile"),
)


def _make_database_config(
    database_path: Path,
    *,
    require_key_file: bool,
) -> DatabaseConfig:
    return DatabaseConfig(
        dialect="sqlite",
        database_path=str(database_path),
        require_key_file=require_key_file,
        min_password_length=len(DEFAULT_TEST_PASSWORD),
        kdf_iterations=TEST_KDF_ITERATIONS,
    )


def _build_bootstrap_request(
    database_config: DatabaseConfig,
    *,
    password: str,
    key_file_path: Path | None,
    create_new_database: bool,
) -> BootstrapRepositoryRequest:
    return BootstrapRepositoryRequest(
        target=database_config.bootstrap_target,
        creation_defaults=database_config.creation_defaults,
        password=password,
        key_file_path=key_file_path,
        create_new_database=create_new_database,
        key_preparer=prepare_sqlite_encryption_key if password or key_file_path is not None else None,
    )


def _build_database_cleanup_artifact_paths(database_path: Path) -> tuple[Path, ...]:
    artifact_paths = [
        database_path,
        Path(f"{database_path}-wal"),
        Path(f"{database_path}-shm"),
    ]
    return tuple(artifact_paths)


@pytest.mark.parametrize(
    ("password", "uses_key_file", "require_key_file"),
    SQLITE_RESET_CREDENTIAL_SCENARIOS,
)
def test_reset_coordinator_denies_access_before_cleanup_for_on_disk_sqlite_modes(
    request: pytest.FixtureRequest,
    tmp_path: Path,
    password: str,
    uses_key_file: bool,
    require_key_file: bool,
) -> None:
    if (password or uses_key_file) and sqlite_adapter_module.sqlcipher3 is None:
        pytest.skip("Encrypted SQLite reset integration scenarios require sqlcipher3.")

    scenario_id = request.node.callspec.id
    database_path = tmp_path / f"{scenario_id}.db"
    key_file_path = tmp_path / f"{scenario_id}.key" if uses_key_file else None
    if key_file_path is not None:
        key_file_path.write_bytes(TEST_KEY_FILE_BYTES)

    database_config = _make_database_config(
        database_path,
        require_key_file=require_key_file,
    )

    create_result = bootstrap_repository(
        _build_bootstrap_request(
            database_config,
            password=password,
            key_file_path=key_file_path,
            create_new_database=True,
        )
    )

    assert create_result.succeeded is True
    assert create_result.failure is None
    assert create_result.repository is not None
    assert create_result.invalidate_access is not None
    create_repository = create_result.repository
    assert isinstance(create_repository, EventLogRepository)
    assert create_repository.get_all_event_entries() == []
    assert database_path.exists() is True

    create_result.invalidate_access()

    reopen_result = bootstrap_repository(
        _build_bootstrap_request(
            database_config,
            password=password,
            key_file_path=key_file_path,
            create_new_database=False,
        )
    )

    assert reopen_result.succeeded is True
    assert reopen_result.failure is None
    assert reopen_result.repository is not None
    assert reopen_result.invalidate_access is not None
    assert reopen_result.backend_cleanup is not None

    active_repository = reopen_result.repository
    assert isinstance(active_repository, EventLogRepository)
    active_repository_typed: EventLogRepository = active_repository
    assert active_repository_typed.get_all_event_entries() == []

    phase_order: list[str] = []
    database_cleanup_artifact_paths = _build_database_cleanup_artifact_paths(database_path)

    def deny_access() -> None:
        phase_order.append("deny")
        reopen_result.invalidate_access()

    def cleanup() -> None:
        phase_order.append("cleanup")
        with pytest.raises(Exception) as exc_info:
            active_repository_typed.get_all_event_entries()
        assert "closed" in str(exc_info.value).lower()

        cleanup_target_count = len(active_repository_typed.adapter.get_cleanup_target_paths())
        backend_cleanup_outcome = reopen_result.backend_cleanup()
        if cleanup_target_count > 0:
            expected_outcome = BackendCleanupOutcome(
                status=BackendCleanupStatus.COMPLETED,
                cleanup_performed=True,
                detail=(
                    "Backend cleanup preparation removed "
                    f"{cleanup_target_count} backend-owned active artifacts after access was already released."
                ),
            )
        else:
            expected_outcome = BackendCleanupOutcome(
                status=BackendCleanupStatus.COMPLETED,
                cleanup_performed=False,
                detail="Backend cleanup preparation was already complete for the active persistence context.",
            )

        assert backend_cleanup_outcome == expected_outcome
        for artifact_path in database_cleanup_artifact_paths:
            assert artifact_path.exists() is False

    first_outcome = ResetCoordinator(deny_access=deny_access, cleanup=cleanup).run()

    assert phase_order == ["deny", "cleanup"]
    assert first_outcome == ResetOutcome(
        had_active_context=True,
        denial_succeeded=True,
        cleanup_started=True,
        cleanup_completed=True,
    )
    for artifact_path in database_cleanup_artifact_paths:
        assert artifact_path.exists() is False
    if key_file_path is not None:
        assert key_file_path.exists() is True
    with pytest.raises(Exception) as exc_info:
        active_repository_typed.get_all_event_entries()
    assert "closed" in str(exc_info.value).lower()

    repeated_outcome = ResetCoordinator(deny_access=deny_access, cleanup=cleanup).run()

    assert phase_order == ["deny", "cleanup", "deny", "cleanup"]
    assert repeated_outcome == first_outcome
    for artifact_path in database_cleanup_artifact_paths:
        assert artifact_path.exists() is False
    if key_file_path is not None:
        assert key_file_path.exists() is True
    with pytest.raises(Exception) as exc_info:
        active_repository_typed.get_all_event_entries()
    assert "closed" in str(exc_info.value).lower()


def test_reset_coordinator_reports_explicit_partial_backend_cleanup_outcome_when_later_artifact_delete_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "partial-cleanup.db"
    wal_path = Path(f"{database_path}-wal")
    database_config = _make_database_config(database_path, require_key_file=False)

    create_result = bootstrap_repository(
        _build_bootstrap_request(
            database_config,
            password="",
            key_file_path=None,
            create_new_database=True,
        )
    )

    assert create_result.succeeded is True
    assert create_result.invalidate_access is not None
    create_result.invalidate_access()

    reopen_result = bootstrap_repository(
        _build_bootstrap_request(
            database_config,
            password="",
            key_file_path=None,
            create_new_database=False,
        )
    )

    assert reopen_result.succeeded is True
    assert reopen_result.failure is None
    assert reopen_result.repository is not None
    assert reopen_result.invalidate_access is not None
    assert reopen_result.backend_cleanup is not None

    active_repository = reopen_result.repository
    assert isinstance(active_repository, EventLogRepository)
    active_repository_typed: EventLogRepository = active_repository
    wal_path.write_text("synthetic wal sidecar", encoding="utf-8")

    original_unlink = Path.unlink

    def fake_unlink(self: Path, *, missing_ok: bool = False) -> None:
        if self == wal_path:
            raise OSError("locked")
        original_unlink(self, missing_ok=missing_ok)  # type: ignore[arg-type]

    monkeypatch.setattr(Path, "unlink", fake_unlink)

    phase_order: list[str] = []
    cleanup_error: BackendCleanupError | None = None

    def deny_access() -> None:
        phase_order.append("deny")
        reopen_result.invalidate_access()

    def cleanup() -> None:
        nonlocal cleanup_error
        phase_order.append("cleanup")

        with pytest.raises(Exception) as exc_info:
            active_repository_typed.get_all_event_entries()
        assert "closed" in str(exc_info.value).lower()

        try:
            reopen_result.backend_cleanup()
        except BackendCleanupError as exc:
            cleanup_error = exc
            raise

    reset_outcome = ResetCoordinator(deny_access=deny_access, cleanup=cleanup).run()

    assert phase_order == ["deny", "cleanup"]
    assert reset_outcome == ResetOutcome(
        had_active_context=True,
        denial_succeeded=True,
        cleanup_started=True,
        cleanup_completed=False,
        failure_categories=(ResetFailureCategory.CLEANUP,),
    )
    assert cleanup_error is not None
    assert str(cleanup_error) == "Backend cleanup could not remove one or more backend-owned active artifacts."
    assert cleanup_error.outcome == BackendCleanupOutcome(
        status=BackendCleanupStatus.PARTIAL,
        cleanup_performed=True,
        detail=(
            "Backend cleanup removed 1 backend-owned active artifacts "
            "before encountering a later cleanup failure."
        ),
    )
    assert cleanup_error.outcome.report == BackendCleanupReport(
        access_release_performed=False,
        artifacts_enumerated=2,
        artifacts_removed=1,
        artifacts_failed=1,
        removed_concerns=(BackendCleanupConcern.DATABASE_ARTIFACTS,),
        failed_concerns=(BackendCleanupConcern.DATABASE_ARTIFACTS,),
        removed_artifact_kinds=("database",),
        failed_artifact_kinds=("wal",),
    )
    assert database_path.exists() is False
    assert wal_path.exists() is True
    with pytest.raises(Exception) as exc_info:
        active_repository_typed.get_all_event_entries()
    assert "closed" in str(exc_info.value).lower()









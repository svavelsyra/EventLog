"""Startup/bootstrap orchestration helpers for ready repository creation.

This module owns non-GUI startup orchestration concerns that sit above the
repository factory but below presenters/dialogs. It validates remembered
bootstrap target state, gathers caller-provided credential inputs, uses the
shared security helper boundary for generic validation, delegates backend-owned
key preparation through an injected callback, and returns either a ready
repository or an explicit failure outcome.

IMPORTANT TRANSITIONAL NOTE:
- This module is intentionally a first Epic `002.004` seam, not the final
  bootstrap architecture.
- The current runtime still supports only SQLite, but support validation here
  should flow through the factory-owned repository support contract rather than
  grow more local backend-specific branching.
- That must NOT be treated as architectural approval to let generic bootstrap
  logic slowly become SQLite-specific over time.
- Future sessions should preserve the documented architecture split:
  generic bootstrap/orchestration here, backend-specific readiness and key/
  metadata behavior elsewhere.
- If support grows beyond one technology, the next architectural step is to
  centralize support/selection policy first, and only introduce per-technology
  bootstrap handlers if real divergence justifies them.
- Do NOT copy the current SQLite-only branch into more bootstrap code as if it
  were the intended end state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from os import PathLike
from pathlib import Path
from typing import Callable

from src.config import DatabaseConfig
from src.config.app_config import BootstrapTargetConfig, DatabaseCreationDefaults
from src.db.database_adapter import (
    BackendCleanupMetadata,
    DatabaseAdapterError,
    DatabaseNewer,
    EncryptedDatabaseError,
    EncryptedDatabaseProfileMismatch,
    EncryptedDatabaseUnreadable,
    EncryptedDatabaseWrongKey,
    MigrationNeeded,
)
from src.db.repositories.base_repository import BaseRepository
from src.db.repositories.bootstrap_backend_policy import (
    get_remembered_target_cleanup_metadata,
    is_supported_repository_dialect,
    migrate_event_log_database,
    resolve_startup_key_preparer,
)
from src.db.repositories.repository_factory import RepositoryFactory
from src.security import (
    GENERIC_INVALID_CREDENTIALS_MESSAGE,
    KeyFileValidationError,
    PasswordValidationError,
    SecurityHelperError,
    best_effort_secure_delete,
    load_key_file_bytes,
    validate_password,
)

BackendKeyPreparer = Callable[[str, bytes | None, DatabaseCreationDefaults], bytes | None]
AccessInvalidator = Callable[[], None]
BackendCleanup = Callable[[], "BackendCleanupOutcome"]



class BootstrapFailureCode(StrEnum):
    """Stable failure categories for startup/bootstrap callers."""

    INCOMPLETE_BOOTSTRAP_TARGET = "incomplete_bootstrap_target"
    UNSUPPORTED_DIALECT = "unsupported_dialect"
    PROFILE_MISMATCH = "profile_mismatch"
    MIGRATION_NEEDED = "migration_needed"
    DATABASE_NEWER = "database_newer"
    MISSING_REQUIRED_KEY_FILE = "missing_required_key_file"
    INVALID_PASSWORD = "invalid_password"
    INVALID_KEY_FILE = "invalid_key_file"
    INVALID_CREDENTIALS = "invalid_credentials"
    MISSING_KEY_PREPARER = "missing_key_preparer"
    INVALID_PREPARED_KEY = "invalid_prepared_key"
    KEY_PREPARATION_FAILED = "key_preparation_failed"
    REPOSITORY_OPEN_FAILED = "repository_open_failed"
    MIGRATION_FAILED = "migration_failed"


class BackendCleanupStatus(StrEnum):
    """Neutral backend-phase states for reset cleanup callbacks."""

    COMPLETED = "completed"
    PARTIAL = "partial"
    UNSUPPORTED = "unsupported"


class BackendCleanupConcern(StrEnum):
    """Sanitized backend-owned cleanup concern categories for higher layers."""

    DATABASE_ARTIFACTS = "database_artifacts"


@dataclass(frozen=True, slots=True)
class BackendCleanupReport:
    """Structured sanitized cleanup-report details for higher-layer interpretation."""

    access_release_performed: bool
    artifacts_enumerated: int
    artifacts_removed: int
    artifacts_failed: int
    removed_concerns: tuple[BackendCleanupConcern, ...] = ()
    failed_concerns: tuple[BackendCleanupConcern, ...] = ()
    removed_artifact_kinds: tuple[str, ...] = ()
    failed_artifact_kinds: tuple[str, ...] = ()


def _resolve_cleanup_concern(artifact_kind: str) -> BackendCleanupConcern:
    """Return the sanitized higher-layer cleanup concern for one backend artifact kind."""
    return BackendCleanupConcern.DATABASE_ARTIFACTS


@dataclass(frozen=True, slots=True)
class BackendCleanupOutcome:
    """Sanitized backend cleanup result reported beneath shared reset flow."""

    status: BackendCleanupStatus
    cleanup_performed: bool
    detail: str = ""
    report: BackendCleanupReport | None = field(default=None, compare=False)


class BackendCleanupError(RuntimeError):
    """Sanitized backend cleanup failure that can still report partial progress."""

    def __init__(self, message: str, *, outcome: BackendCleanupOutcome) -> None:
        super().__init__(message)
        self.outcome = outcome


@dataclass(frozen=True, slots=True)
class BootstrapFailure:
    """Explicit startup/bootstrap failure outcome for higher layers."""

    code: BootstrapFailureCode
    message: str
    retryable: bool = True


@dataclass(frozen=True, slots=True)
class BootstrapRepositoryRequest:
    """Caller-supplied startup inputs used to construct a ready repository.

    Args:
        target: Normalized bootstrap target details for the selected startup flow.
        creation_defaults: Create-time policy values still needed for password
            validation, KDF configuration, and secure-delete callbacks.
        password: Caller-provided password input. Empty string is allowed so the
            orchestration layer can support policy-driven no-password flows.
        key_file_path: Optional caller-selected key file path.
        create_new_database: Whether the caller is creating a new target instead
            of opening an existing remembered one.
        key_preparer: Backend-owned callback that converts validated caller
            inputs into backend-ready encryption key bytes when credentials are
            being used.
    """

    target: BootstrapTargetConfig
    creation_defaults: DatabaseCreationDefaults = field(default_factory=DatabaseCreationDefaults)
    password: str = ""
    key_file_path: str | PathLike[str] | None = None
    create_new_database: bool = False
    key_preparer: BackendKeyPreparer | None = None


@dataclass(frozen=True, slots=True)
class MigrationRequest:
    """Caller-supplied inputs used to run backend-owned database migration."""

    target: BootstrapTargetConfig
    creation_defaults: DatabaseCreationDefaults = field(default_factory=DatabaseCreationDefaults)
    password: str = ""
    key_file_path: str | PathLike[str] | None = None
    key_preparer: BackendKeyPreparer | None = None


@dataclass(frozen=True, slots=True)
class BootstrapRepositoryResult:
    """Return shape for startup/bootstrap repository orchestration."""

    repository: BaseRepository | None = None
    invalidate_access: AccessInvalidator | None = None
    backend_cleanup: BackendCleanup | None = None
    failure: BootstrapFailure | None = None

    @property
    def succeeded(self) -> bool:
        """Return whether repository bootstrap succeeded."""
        return self.repository is not None and self.failure is None


@dataclass(frozen=True, slots=True)
class MigrationResult:
    """Return shape for startup-triggered migration execution."""

    migration_performed: bool = False
    message: str = ""
    failure: BootstrapFailure | None = None
    report_path: Path | None = None

    @property
    def succeeded(self) -> bool:
        """Return whether migration completed without a mapped failure."""
        return self.failure is None


def _validate_bootstrap_target(
    request: BootstrapRepositoryRequest,
) -> BootstrapFailure | None:
    """Return an explicit failure when bootstrap target preconditions are not met."""
    target = request.target

    if request.create_new_database:
        if not target.dialect or not target.database_path:
            return BootstrapFailure(
                BootstrapFailureCode.INCOMPLETE_BOOTSTRAP_TARGET,
                "Databastyp och databassökväg krävs för att skapa en ny databas.",
            )
    elif not target.can_attempt_auto_open:
        return BootstrapFailure(
            BootstrapFailureCode.INCOMPLETE_BOOTSTRAP_TARGET,
            "Kom ihågkommen databasmål är ofullständigt och kan inte öppnas automatiskt.",
        )

    # TRANSITIONAL WARNING:
    # The runtime still has exactly one supported repository technology today,
    # but bootstrap should validate that support through the factory-owned
    # contract instead of copying more backend-specific equality checks here.
    #
    # Future sessions must not read this branch as a license to hardcode more
    # backend-specific bootstrap behavior here. The intended direction remains a
    # centralized support/selection contract so generic bootstrap validates
    # support without turning into a disguised SQLite bootstrap module.
    if not is_supported_repository_dialect(target.dialect):
        return BootstrapFailure(
            BootstrapFailureCode.UNSUPPORTED_DIALECT,
            f"Databastypen {target.dialect!r} stöds inte i aktuell startup-bootstrap.",
            retryable=False,
        )

    if target.require_key_file and request.key_file_path is None:
        return BootstrapFailure(
            BootstrapFailureCode.MISSING_REQUIRED_KEY_FILE,
            "Nyckelfil krävs för den här databasen.",
        )

    return None


def _validate_migration_target(request: MigrationRequest) -> BootstrapFailure | None:
    """Return an explicit failure when migration target preconditions are not met."""
    target = request.target

    if not target.dialect or not target.database_path:
        return BootstrapFailure(
            BootstrapFailureCode.INCOMPLETE_BOOTSTRAP_TARGET,
            "Databastyp och databassökväg krävs för att köra databasmigrering.",
        )

    if not is_supported_repository_dialect(target.dialect):
        return BootstrapFailure(
            BootstrapFailureCode.UNSUPPORTED_DIALECT,
            f"Databastypen {target.dialect!r} stöds inte i aktuell startup-bootstrap.",
            retryable=False,
        )

    if target.require_key_file and request.key_file_path is None:
        return BootstrapFailure(
            BootstrapFailureCode.MISSING_REQUIRED_KEY_FILE,
            "Nyckelfil krävs för den här databasen.",
        )

    return None


def _prepare_encryption_key(
    request: BootstrapRepositoryRequest | MigrationRequest,
) -> tuple[bytes | None, BootstrapFailure | None]:
    """Return prepared backend-ready key bytes or an explicit failure."""
    if request.password:
        try:
            validate_password(
                request.password,
                min_length=request.creation_defaults.min_password_length,
            )
        except PasswordValidationError as exc:
            return None, BootstrapFailure(
                BootstrapFailureCode.INVALID_PASSWORD,
                str(exc),
            )
        except (TypeError, ValueError) as exc:
            return None, BootstrapFailure(
                BootstrapFailureCode.INVALID_PASSWORD,
                str(exc),
                retryable=False,
            )

    key_file_bytes: bytes | None = None
    if request.key_file_path is not None:
        try:
            key_file_bytes = load_key_file_bytes(request.key_file_path)
        except KeyFileValidationError as exc:
            return None, BootstrapFailure(
                BootstrapFailureCode.INVALID_KEY_FILE,
                str(exc),
            )
        except (TypeError, ValueError) as exc:
            return None, BootstrapFailure(
                BootstrapFailureCode.INVALID_KEY_FILE,
                str(exc),
                retryable=False,
            )

    if not request.password and key_file_bytes is None:
        return None, None

    try:
        if request.key_preparer is not None:
            encryption_key = _run_key_preparer(
                request.key_preparer,
                request.password,
                key_file_bytes,
                request.creation_defaults,
            )
        else:
            resolved_key_preparer = resolve_startup_key_preparer(request.target.dialect)
            if resolved_key_preparer is None:
                return None, BootstrapFailure(
                    BootstrapFailureCode.MISSING_KEY_PREPARER,
                    "Backend-owned key preparation is required before encrypted startup can continue.",
                    retryable=False,
                )

            encryption_key = _run_key_preparer(
                resolved_key_preparer,
                request.password,
                key_file_bytes,
                request.creation_defaults,
            )
    except SecurityHelperError as exc:
        return None, BootstrapFailure(
            BootstrapFailureCode.KEY_PREPARATION_FAILED,
            str(exc),
        )
    except (TypeError, ValueError) as exc:
        return None, BootstrapFailure(
            BootstrapFailureCode.KEY_PREPARATION_FAILED,
            str(exc),
            retryable=False,
        )

    if not isinstance(encryption_key, bytes) or not encryption_key:
        return None, BootstrapFailure(
            BootstrapFailureCode.INVALID_PREPARED_KEY,
            "Backend-owned key preparation must return non-empty bytes.",
            retryable=False,
        )

    return encryption_key, None


def _run_migration(
    request: MigrationRequest,
    *,
    encryption_key: bytes | None,
) -> MigrationResult:
    """Run backend-owned migration and map backend failures into coarse outcomes."""
    target = request.target

    try:
        migration_performed = migrate_event_log_database(
            database_path=target.database_path,
            dialect=target.dialect,
            encryption_key=encryption_key,
        )
    except EncryptedDatabaseWrongKey:
        return MigrationResult(
            failure=BootstrapFailure(
                BootstrapFailureCode.INVALID_CREDENTIALS,
                GENERIC_INVALID_CREDENTIALS_MESSAGE,
            )
        )
    except EncryptedDatabaseProfileMismatch as exc:
        return MigrationResult(
            failure=BootstrapFailure(
                BootstrapFailureCode.PROFILE_MISMATCH,
                str(exc),
            )
        )
    except DatabaseNewer as exc:
        return MigrationResult(
            failure=BootstrapFailure(
                BootstrapFailureCode.DATABASE_NEWER,
                str(exc),
                retryable=False,
            )
        )
    except EncryptedDatabaseUnreadable as exc:
        return MigrationResult(
            failure=BootstrapFailure(
                BootstrapFailureCode.MIGRATION_FAILED,
                str(exc),
            )
        )
    except EncryptedDatabaseError as exc:
        return MigrationResult(
            failure=BootstrapFailure(
                BootstrapFailureCode.MIGRATION_FAILED,
                str(exc),
            )
        )
    except DatabaseAdapterError as exc:
        return MigrationResult(
            failure=BootstrapFailure(
                BootstrapFailureCode.MIGRATION_FAILED,
                str(exc),
            )
        )

    if migration_performed:
        return MigrationResult(
            migration_performed=True,
            message="Databasmigreringen slutfördes.",
        )

    return MigrationResult(
        migration_performed=False,
        message="Databasen använder redan aktuell version.",
    )


def _run_key_preparer(
    key_preparer: BackendKeyPreparer,
    password: str,
    key_file_bytes: bytes | None,
    creation_defaults: DatabaseCreationDefaults,
) -> bytes | None:
    """Run a non-optional backend key preparer with normalized inputs."""
    return key_preparer(password, key_file_bytes, creation_defaults)


def _open_repository(
    request: BootstrapRepositoryRequest,
    *,
    encryption_key: bytes | None,
) -> tuple[BaseRepository | None, BootstrapFailure | None]:
    """Return the opened repository or a mapped bootstrap failure."""
    target = request.target

    try:
        repository = RepositoryFactory.create_event_log_repository(
            database_path=target.database_path,
            dialect=target.dialect,
            encryption_key=encryption_key,
        )
    except EncryptedDatabaseWrongKey:
        return None, BootstrapFailure(
            BootstrapFailureCode.INVALID_CREDENTIALS,
            GENERIC_INVALID_CREDENTIALS_MESSAGE,
        )
    except EncryptedDatabaseProfileMismatch as exc:
        return None, BootstrapFailure(
            BootstrapFailureCode.PROFILE_MISMATCH,
            str(exc),
        )
    except MigrationNeeded as exc:
        return None, BootstrapFailure(
            BootstrapFailureCode.MIGRATION_NEEDED,
            str(exc),
            retryable=False,
        )
    except DatabaseNewer as exc:
        return None, BootstrapFailure(
            BootstrapFailureCode.DATABASE_NEWER,
            str(exc),
            retryable=False,
        )
    except EncryptedDatabaseUnreadable as exc:
        return None, BootstrapFailure(
            BootstrapFailureCode.REPOSITORY_OPEN_FAILED,
            str(exc),
        )
    except EncryptedDatabaseError as exc:
        return None, BootstrapFailure(
            BootstrapFailureCode.REPOSITORY_OPEN_FAILED,
            str(exc),
        )
    except DatabaseAdapterError as exc:
        return None, BootstrapFailure(
            BootstrapFailureCode.REPOSITORY_OPEN_FAILED,
            str(exc),
        )

    return repository, None


def _build_backend_cleanup_report(
    *,
    access_released_performed: bool,
    cleanup_metadata: BackendCleanupMetadata,
    removed_artifact_count: int,
    failed_artifact_count: int,
    removed_artifact_kinds: list[str],
    failed_artifact_kinds: list[str],
) -> BackendCleanupReport:
    """Return a structured sanitized cleanup report for the current backend pass.

    This report intentionally stays backend-agnostic in this layer. If later
    stories need backend-specific artifact categories or phase details, that
    metadata must come from the backend-owned cleanup seam rather than being
    inferred here from technology-specific filenames or suffixes.
    """

    return BackendCleanupReport(
        access_release_performed=access_released_performed,
        artifacts_enumerated=len(cleanup_metadata.artifacts),
        artifacts_removed=removed_artifact_count,
        artifacts_failed=failed_artifact_count,
        removed_concerns=tuple(dict.fromkeys(_resolve_cleanup_concern(kind) for kind in removed_artifact_kinds)),
        failed_concerns=tuple(dict.fromkeys(_resolve_cleanup_concern(kind) for kind in failed_artifact_kinds)),
        removed_artifact_kinds=tuple(dict.fromkeys(removed_artifact_kinds)),
        failed_artifact_kinds=tuple(dict.fromkeys(failed_artifact_kinds)),
    )


def cleanup_remembered_bootstrap_target(database_config: DatabaseConfig) -> BackendCleanupOutcome:
    """Delete backend-owned artifacts for the unopened remembered startup target."""
    target = database_config.bootstrap_target
    if not target.can_attempt_auto_open or not is_supported_repository_dialect(target.dialect):
        return BackendCleanupOutcome(
            status=BackendCleanupStatus.UNSUPPORTED,
            cleanup_performed=False,
            detail="Backend cleanup preparation could not inspect the remembered startup target.",
            report=BackendCleanupReport(
                access_release_performed=False,
                artifacts_enumerated=0,
                artifacts_removed=0,
                artifacts_failed=0,
                failed_concerns=(BackendCleanupConcern.DATABASE_ARTIFACTS,),
            ),
        )

    cleanup_metadata = get_remembered_target_cleanup_metadata(
        database_path=target.database_path,
        dialect=target.dialect,
    )
    deleted_artifact_count = 0
    failed_artifact_count = 0
    later_delete_failed = False
    removed_artifact_kinds: list[str] = []
    failed_artifact_kinds: list[str] = []

    for cleanup_artifact in cleanup_metadata.artifacts:
        try:
            best_effort_secure_delete(
                cleanup_artifact.path,
                allow_secure_overwrite=cleanup_artifact.allow_secure_overwrite,
                secure_delete_passes=max(0, database_config.creation_defaults.secure_delete_passes),
            )
        except OSError as exc:
            failed_artifact_count += 1
            failed_artifact_kinds.append(cleanup_artifact.artifact_kind)
            if deleted_artifact_count > 0:
                later_delete_failed = True
                continue
            raise BackendCleanupError(
                "Backend cleanup could not remove one or more backend-owned remembered-target artifacts.",
                outcome=BackendCleanupOutcome(
                    status=BackendCleanupStatus.PARTIAL,
                    cleanup_performed=deleted_artifact_count > 0,
                    detail=(
                        "Backend cleanup preparation removed "
                        f"{deleted_artifact_count} backend-owned remembered-target artifacts before encountering a later cleanup failure."
                    ),
                    report=_build_backend_cleanup_report(
                        access_released_performed=False,
                        cleanup_metadata=cleanup_metadata,
                        removed_artifact_count=deleted_artifact_count,
                        failed_artifact_count=failed_artifact_count,
                        removed_artifact_kinds=removed_artifact_kinds,
                        failed_artifact_kinds=failed_artifact_kinds,
                    ),
                ),
            ) from exc
        deleted_artifact_count += 1
        removed_artifact_kinds.append(cleanup_artifact.artifact_kind)

    if later_delete_failed:
        raise BackendCleanupError(
            "Backend cleanup could not remove one or more backend-owned remembered-target artifacts.",
            outcome=BackendCleanupOutcome(
                status=BackendCleanupStatus.PARTIAL,
                cleanup_performed=deleted_artifact_count > 0,
                detail=(
                    "Backend cleanup preparation removed "
                    f"{deleted_artifact_count} backend-owned remembered-target artifacts before encountering a later cleanup failure."
                ),
                report=_build_backend_cleanup_report(
                    access_released_performed=False,
                    cleanup_metadata=cleanup_metadata,
                    removed_artifact_count=deleted_artifact_count,
                    failed_artifact_count=failed_artifact_count,
                    removed_artifact_kinds=removed_artifact_kinds,
                    failed_artifact_kinds=failed_artifact_kinds,
                ),
            ),
        )

    if deleted_artifact_count > 0:
        detail = (
            "Backend cleanup preparation removed "
            f"{deleted_artifact_count} backend-owned remembered-target artifacts."
        )
    else:
        detail = "Backend cleanup preparation found no backend-owned remembered-target artifacts."

    return BackendCleanupOutcome(
        status=BackendCleanupStatus.COMPLETED,
        cleanup_performed=deleted_artifact_count > 0,
        detail=detail,
        report=_build_backend_cleanup_report(
            access_released_performed=False,
            cleanup_metadata=cleanup_metadata,
            removed_artifact_count=deleted_artifact_count,
            failed_artifact_count=failed_artifact_count,
            removed_artifact_kinds=removed_artifact_kinds,
            failed_artifact_kinds=failed_artifact_kinds,
        ),
    )


def _build_reset_callbacks(
    repository: BaseRepository,
    *,
    secure_delete_passes: int,
) -> tuple[AccessInvalidator, BackendCleanup]:
    """Return paired denial/cleanup callbacks that share repository-release state.

    The current concrete backend-preparation step is intentionally narrow:
    ensure the active persistence handle has been released before later artifact
    cleanup stories attach more backend-specific work.
    """

    access_released = False

    def ensure_access_released() -> bool:
        nonlocal access_released
        if access_released:
            return False

        repository.close()
        access_released = True
        return True

    def invalidate_access() -> None:
        ensure_access_released()

    def backend_cleanup() -> BackendCleanupOutcome:
        access_released_now = ensure_access_released()
        cleanup_metadata = repository.adapter.get_cleanup_metadata()
        deleted_artifact_count = 0
        failed_artifact_count = 0
        later_delete_failed = False
        removed_artifact_kinds: list[str] = []
        failed_artifact_kinds: list[str] = []

        for cleanup_artifact in cleanup_metadata.artifacts:
            try:
                best_effort_secure_delete(
                    cleanup_artifact.path,
                    allow_secure_overwrite=cleanup_artifact.allow_secure_overwrite,
                    secure_delete_passes=secure_delete_passes,
                )
            except OSError as exc:
                failed_artifact_count += 1
                failed_artifact_kinds.append(cleanup_artifact.artifact_kind)
                if deleted_artifact_count > 0:
                    later_delete_failed = True
                    continue
                raise BackendCleanupError(
                    "Backend cleanup could not remove one or more backend-owned active artifacts.",
                    outcome=BackendCleanupOutcome(
                        status=BackendCleanupStatus.PARTIAL,
                        cleanup_performed=access_released_now or deleted_artifact_count > 0,
                        detail=(
                            "Backend cleanup released active persistence access and removed "
                            f"{deleted_artifact_count} backend-owned active artifacts before encountering a later cleanup failure."
                            if access_released_now
                            else (
                                "Backend cleanup removed "
                                f"{deleted_artifact_count} backend-owned active artifacts before encountering a later cleanup failure."
                            )
                        ),
                        report=_build_backend_cleanup_report(
                            access_released_performed=access_released_now,
                            cleanup_metadata=cleanup_metadata,
                            removed_artifact_count=deleted_artifact_count,
                            failed_artifact_count=failed_artifact_count,
                            removed_artifact_kinds=removed_artifact_kinds,
                            failed_artifact_kinds=failed_artifact_kinds,
                        ),
                    ),
                ) from exc
            deleted_artifact_count += 1
            removed_artifact_kinds.append(cleanup_artifact.artifact_kind)

        if later_delete_failed:
            raise BackendCleanupError(
                "Backend cleanup could not remove one or more backend-owned active artifacts.",
                outcome=BackendCleanupOutcome(
                    status=BackendCleanupStatus.PARTIAL,
                    cleanup_performed=access_released_now or deleted_artifact_count > 0,
                    detail=(
                        "Backend cleanup released active persistence access and removed "
                        f"{deleted_artifact_count} backend-owned active artifacts before encountering a later cleanup failure."
                        if access_released_now
                        else (
                            "Backend cleanup removed "
                            f"{deleted_artifact_count} backend-owned active artifacts before encountering a later cleanup failure."
                        )
                    ),
                    report=_build_backend_cleanup_report(
                        access_released_performed=access_released_now,
                        cleanup_metadata=cleanup_metadata,
                        removed_artifact_count=deleted_artifact_count,
                        failed_artifact_count=failed_artifact_count,
                        removed_artifact_kinds=removed_artifact_kinds,
                        failed_artifact_kinds=failed_artifact_kinds,
                    ),
                ),
            )

        cleanup_performed = access_released_now or deleted_artifact_count > 0
        if deleted_artifact_count > 0:
            if access_released_now:
                detail = (
                    "Backend cleanup preparation released active persistence access and removed "
                    f"{deleted_artifact_count} backend-owned active artifacts."
                )
            else:
                detail = (
                    "Backend cleanup preparation removed "
                    f"{deleted_artifact_count} backend-owned active artifacts after access was already released."
                )
        elif access_released_now:
            detail = "Backend cleanup preparation released active persistence access."
        else:
            detail = "Backend cleanup preparation was already complete for the active persistence context."

        return BackendCleanupOutcome(
            status=BackendCleanupStatus.COMPLETED,
            cleanup_performed=cleanup_performed,
            detail=detail,
            report=_build_backend_cleanup_report(
                access_released_performed=access_released_now,
                cleanup_metadata=cleanup_metadata,
                removed_artifact_count=deleted_artifact_count,
                failed_artifact_count=failed_artifact_count,
                removed_artifact_kinds=removed_artifact_kinds,
                failed_artifact_kinds=failed_artifact_kinds,
            ),
        )

    return invalidate_access, backend_cleanup


def bootstrap_repository(request: BootstrapRepositoryRequest) -> BootstrapRepositoryResult:
    """Return a ready repository or an explicit bootstrap failure outcome."""
    target_failure = _validate_bootstrap_target(request)
    if target_failure is not None:
        return BootstrapRepositoryResult(failure=target_failure)

    encryption_key, failure = _prepare_encryption_key(request)
    if failure is not None:
        return BootstrapRepositoryResult(failure=failure)

    repository, failure = _open_repository(request, encryption_key=encryption_key)
    if failure is not None:
        return BootstrapRepositoryResult(failure=failure)

    assert repository is not None
    invalidate_access, backend_cleanup = _build_reset_callbacks(
        repository,
        secure_delete_passes=max(0, request.creation_defaults.secure_delete_passes),
    )

    return BootstrapRepositoryResult(
        repository=repository,
        invalidate_access=invalidate_access,
        backend_cleanup=backend_cleanup,
    )


def migrate_repository(request: MigrationRequest) -> MigrationResult:
    """Run backend-owned migration for a startup-selected database target."""
    target_failure = _validate_migration_target(request)
    if target_failure is not None:
        return MigrationResult(failure=target_failure)

    encryption_key, failure = _prepare_encryption_key(request)
    if failure is not None:
        return MigrationResult(failure=failure)

    return _run_migration(request, encryption_key=encryption_key)


__all__ = [
    "BackendCleanupConcern",
    "AccessInvalidator",
    "BackendCleanup",
    "BackendCleanupError",
    "BackendCleanupOutcome",
    "BackendCleanupReport",
    "BackendCleanupStatus",
    "BackendKeyPreparer",
    "BootstrapFailure",
    "BootstrapFailureCode",
    "BootstrapRepositoryRequest",
    "BootstrapRepositoryResult",
    "MigrationRequest",
    "MigrationResult",
    "bootstrap_repository",
    "cleanup_remembered_bootstrap_target",
    "migrate_repository",
]


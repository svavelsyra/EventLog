"""Presenter-first startup dialog logic for encrypted create and unlock flows.

This module deliberately avoids Tkinter widget code for now. It gives the GUI
layer a testable presenter seam that can model current dialog state, perform
local UI validation, and hand approved inputs into the existing non-GUI secure
bootstrap orchestration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from os import PathLike
from typing import Callable, Mapping, cast

import src.db.repositories.startup_bootstrap as startup_bootstrap_module
from src.config import DatabaseConfig
from src.config.app_config import BootstrapTargetConfig
from src.db.repositories.bootstrap_backend_policy import (
    infer_startup_mode_for_selection,
    project_backend_startup_fields_for_selection,
    resolve_effective_startup_selection,
    resolve_backend_startup_fields,
    resolve_startup_key_preparer,
)
from src.db.repositories.startup_bootstrap import (
    BackendCleanup,
    BackendKeyPreparer,
    BootstrapFailure,
    BootstrapFailureCode,
    MigrationRequest,
    MigrationResult,
    BootstrapRepositoryResult,
    bootstrap_repository,
    migrate_repository,
)
from src.db.repositories.startup_selection import StartupFieldName, StartupFieldRequirement
from src.security import PasswordValidationError, validate_password

BootstrapRepositoryCallable = Callable[
    [startup_bootstrap_module.BootstrapRepositoryRequest],
    BootstrapRepositoryResult,
]
MigrationCallable = Callable[[MigrationRequest], MigrationResult]
KeyPreparerResolver = Callable[[str], BackendKeyPreparer | None]
StartupModeResolver = Callable[[str, str, "StartupDialogMode"], "StartupDialogMode"]


class StartupDialogMode(StrEnum):
    """Supported startup dialog modes for the current secure-bootstrap phase."""

    CREATE = "create"
    UNLOCK = "unlock"


class StartupDialogFailureCode(StrEnum):
    """Stable presenter-visible failure categories for startup dialog callers."""

    MISSING_DIALECT = "missing_dialect"
    MISSING_DATABASE_PATH = "missing_database_path"
    PASSWORD_CONFIRMATION_MISMATCH = "password_confirmation_mismatch"
    INVALID_PASSWORD = "invalid_password"
    MISSING_REQUIRED_KEY_FILE = "missing_required_key_file"
    INVALID_KEY_FILE = "invalid_key_file"
    INVALID_CREDENTIALS = "invalid_credentials"
    UNSUPPORTED_DIALECT = "unsupported_dialect"
    PROFILE_MISMATCH = "profile_mismatch"
    MIGRATION_NEEDED = "migration_needed"
    DATABASE_NEWER = "database_newer"
    MIGRATION_FAILED = "migration_failed"
    BOOTSTRAP_TARGET_INVALID = "bootstrap_target_invalid"
    BOOTSTRAP_FAILED = "bootstrap_failed"


@dataclass(frozen=True, slots=True)
class StartupDialogState:
    """View-facing state for the current startup dialog mode."""

    mode: StartupDialogMode
    title: str
    submit_label: str
    dialect: str
    database_path: str
    min_password_length: int
    password_policy_hint: str
    allow_emergency_reset: bool
    key_file_path: str = ""
    uses_remembered_target: bool = False
    operator: str = ""
    show_dialect_picker: bool = True
    backend_fields: tuple[StartupFieldRequirement, ...] = ()
    show_migration_action: bool = False
    migration_action_label: str = "Migrera"
    submit_enabled: bool = True
    migration_action_enabled: bool = True


@dataclass(frozen=True, slots=True)
class StartupDialogSubmission:
    """Caller-supplied startup dialog values ready for presenter submission."""

    mode: StartupDialogMode
    dialect: str
    operator: str = ""
    uses_remembered_target: bool = False
    field_values: Mapping[StartupFieldName, str] = field(default_factory=dict)

    def get_field_value(self, field_name: StartupFieldName) -> str:
        """Return one raw submitted field value, defaulting missing fields to blank."""
        return self.field_values.get(field_name, "")


@dataclass(frozen=True, slots=True)
class StartupDialogFailure:
    """Presenter-visible failure shape for local validation or bootstrap errors."""

    code: StartupDialogFailureCode
    message: str
    field_name: str | None = None
    retryable: bool = True
    should_clear_password: bool = False
    should_clear_password_confirmation: bool = False


@dataclass(frozen=True, slots=True)
class StartupDialogSuccess:
    """Successful presenter outcome for startup dialog submission."""

    repository: object
    remembered_target: BootstrapTargetConfig
    last_operator: str = ""
    invalidate_access: Callable[[], None] | None = None
    backend_cleanup: BackendCleanup | None = None


@dataclass(frozen=True, slots=True)
class StartupDialogSubmissionResult:
    """Return shape for startup dialog presenter submit actions."""

    success: StartupDialogSuccess | None = None
    failure: StartupDialogFailure | None = None

    @property
    def succeeded(self) -> bool:
        """Return whether the presenter submission completed successfully."""
        return self.success is not None and self.failure is None


@dataclass(frozen=True, slots=True)
class StartupDialogMigrationResult:
    """Return shape for startup dialog migration actions."""

    message: str = ""
    failure: StartupDialogFailure | None = None

    @property
    def succeeded(self) -> bool:
        """Return whether the migration action completed successfully."""
        return self.failure is None


@dataclass(frozen=True, slots=True)
class _NormalizedStartupSubmission:
    """Presenter-normalized startup submission used for validation and handoff."""

    mode: StartupDialogMode
    uses_remembered_target: bool
    dialect: str
    operator: str
    database_path: str
    field_values: dict[StartupFieldName, str]
    backend_fields: tuple[StartupFieldRequirement, ...]

    def get_field_value(self, field_name: StartupFieldName) -> str:
        """Return one normalized field value, defaulting missing fields to blank."""
        return self.field_values.get(field_name, "")


StartupFieldResolver = Callable[[str, StartupDialogMode, bool, bool], tuple[StartupFieldRequirement, ...]]

_MIGRATION_NEEDED_MESSAGE = (
    "Databasen behöver migreras innan den kan öppnas. Kör databasmigrering för databasen först."
)
_MIGRATION_SUCCEEDED_MESSAGE = "Databasmigreringen lyckades. Du kan nu öppna databasen."
_DATABASE_NEWER_MESSAGE = (
    "Databasen kommer från en nyare version av EventLog. Uppdatera applikationen innan du försöker öppna den."
)


def resolve_backend_key_preparer(dialect: str) -> BackendKeyPreparer | None:
    """Return the backend-owned key preparer for the selected dialect, if any."""
    return resolve_startup_key_preparer(dialect)


def resolve_startup_fields(
    dialect: str,
    mode: StartupDialogMode,
    uses_remembered_target: bool,
    require_key_file: bool,
) -> tuple[StartupFieldRequirement, ...]:
    """Return backend-owned startup fields for the selected technology and flow."""
    return resolve_backend_startup_fields(
        dialect,
        mode=mode.value,
        uses_remembered_target=uses_remembered_target,
        require_key_file=require_key_file,
    )
def resolve_startup_mode(
    dialect: str,
    database_path: str,
    fallback_mode: StartupDialogMode,
) -> StartupDialogMode:
    """Return the backend-owned startup mode for the selected startup target."""
    return StartupDialogMode(
        infer_startup_mode_for_selection(
            dialect=dialect,
            database_path=database_path,
            fallback_mode=fallback_mode.value,
        )
    )


class StartupDialogPresenter:
    """Coordinate startup dialog state, validation, and bootstrap handoff."""

    def __init__(
        self,
        database_config: DatabaseConfig,
        *,
        bootstrap_callback: BootstrapRepositoryCallable = bootstrap_repository,
        migration_callback: MigrationCallable = migrate_repository,
        key_preparer_resolver: KeyPreparerResolver = resolve_backend_key_preparer,
        startup_field_resolver: StartupFieldResolver = resolve_startup_fields,
        startup_mode_resolver: StartupModeResolver = resolve_startup_mode,
    ) -> None:
        self._database_config = database_config
        self._bootstrap_callback = bootstrap_callback
        self._migration_callback = migration_callback
        self._key_preparer_resolver = key_preparer_resolver
        self._startup_field_resolver = startup_field_resolver
        self._startup_mode_resolver = startup_mode_resolver

    def get_initial_state(self, *, operator: str = "") -> StartupDialogState:
        """Return the preferred initial dialog state from remembered bootstrap hints."""
        initial_mode = (
            StartupDialogMode.UNLOCK
            if self._database_config.can_attempt_auto_open
            else StartupDialogMode.CREATE
        )
        return self.recompute_state(
            StartupDialogSubmission(
                mode=initial_mode,
                dialect=self._database_config.dialect,
                operator=operator,
                uses_remembered_target=self._database_config.can_attempt_auto_open,
                field_values={
                    StartupFieldName.DATABASE_PATH: self._database_config.database_path,
                },
            )
        )

    def recompute_state(
        self,
        submission: StartupDialogSubmission,
    ) -> StartupDialogState:
        """Return presenter-owned state recomputed from current operator input."""
        normalized_submission = self._normalize_submission(submission)
        return self.build_state(
            mode=normalized_submission.mode,
            dialect=normalized_submission.dialect,
            database_path=normalized_submission.database_path,
            key_file_path=normalized_submission.get_field_value(StartupFieldName.KEY_FILE_PATH),
            operator=normalized_submission.operator,
            use_remembered_target=normalized_submission.uses_remembered_target,
        )

    def build_state(
        self,
        *,
        mode: StartupDialogMode,
        dialect: str | None = None,
        database_path: str | None = None,
        key_file_path: str = "",
        operator: str = "",
        use_remembered_target: bool | None = None,
    ) -> StartupDialogState:
        """Return the current view-facing dialog state for the requested mode."""
        if dialect is None:
            source_dialect = self._database_config.dialect
        else:
            source_dialect = cast(str, dialect)

        if database_path is None:
            source_database_path = self._database_config.database_path
        else:
            source_database_path = cast(str, database_path)

        startup_selection = resolve_effective_startup_selection(
            self._database_config,
            submitted_dialect=cast(str, source_dialect or ""),
            submitted_database_path=cast(str, source_database_path or ""),
            uses_remembered_target=False,
        )
        resolved_dialect = self._normalize_dialect(startup_selection.dialect or "")
        resolved_database_path = self._normalize_database_path(startup_selection.database_path or "")
        resolved_key_file_path = self._normalize_optional_path(key_file_path)
        can_attempt_auto_open = self._database_config.can_attempt_auto_open
        target_locked = startup_selection.target_locked

        if mode is StartupDialogMode.CREATE:
            raw_backend_fields = self._startup_field_resolver(
                resolved_dialect,
                mode,
                False,
                self._require_key_file_policy_for_mode(mode),
            )
            backend_fields = project_backend_startup_fields_for_selection(
                resolved_dialect,
                mode=mode.value,
                database_path=resolved_database_path,
                target_locked=target_locked,
                backend_fields=raw_backend_fields,
            )

            return StartupDialogState(
                mode=mode,
                title=self._build_create_title(
                    dialect=resolved_dialect,
                    database_path=resolved_database_path,
                ),
                submit_label="Skapa",
                dialect=resolved_dialect,
                database_path=resolved_database_path,
                min_password_length=self._database_config.min_password_length,
                password_policy_hint=self._build_password_policy_hint(),
                allow_emergency_reset=False,
                key_file_path=resolved_key_file_path,
                uses_remembered_target=False,
                operator=operator,
                show_dialect_picker=not target_locked,
                backend_fields=backend_fields,
            )

        if use_remembered_target is None:
            resolved_use_remembered_target = can_attempt_auto_open
        else:
            resolved_use_remembered_target = use_remembered_target and can_attempt_auto_open

        if target_locked:
            resolved_use_remembered_target = False

        startup_selection = resolve_effective_startup_selection(
            self._database_config,
            submitted_dialect=cast(str, source_dialect or ""),
            submitted_database_path=cast(str, source_database_path or ""),
            uses_remembered_target=resolved_use_remembered_target,
        )
        resolved_dialect = self._normalize_dialect(startup_selection.dialect or "")
        resolved_database_path = self._normalize_database_path(startup_selection.database_path or "")
        target_locked = startup_selection.target_locked

        raw_backend_fields = self._startup_field_resolver(
            resolved_dialect,
            mode,
            resolved_use_remembered_target or (target_locked and mode is StartupDialogMode.UNLOCK),
            self._require_key_file_policy_for_mode(mode),
        )
        backend_fields = project_backend_startup_fields_for_selection(
            resolved_dialect,
            mode=mode.value,
            database_path=resolved_database_path,
            target_locked=target_locked,
            backend_fields=raw_backend_fields,
        )

        return StartupDialogState(
            mode=mode,
            title=(
                "EventLog - Lås upp"
                if target_locked
                else (
                "EventLog - Lås upp"
                if resolved_use_remembered_target
                else "EventLog - Öppna befintlig databas"
                )
            ),
            submit_label="Lås upp",
            dialect=resolved_dialect,
            database_path=resolved_database_path,
            min_password_length=self._database_config.min_password_length,
            password_policy_hint="",
            allow_emergency_reset=True,
            key_file_path=resolved_key_file_path,
            uses_remembered_target=resolved_use_remembered_target,
            operator=operator,
            show_dialect_picker=False if target_locked else not resolved_use_remembered_target,
            backend_fields=backend_fields,
        )

    @staticmethod
    def _build_create_title(*, dialect: str, database_path: str) -> str:
        """Return create-state title text for the current startup context."""
        if not database_path:
            return "EventLog - Välj eller skapa databas"

        return "EventLog - Skapa krypterad databas"

    def submit(self, submission: StartupDialogSubmission) -> StartupDialogSubmissionResult:
        """Validate startup inputs and hand them into secure bootstrap orchestration."""
        normalized_submission = self._normalize_submission(submission, infer_mode=False)
        local_failure = self._validate_submission(normalized_submission)
        if local_failure is not None:
            return StartupDialogSubmissionResult(failure=local_failure)

        bootstrap_target = self._build_effective_bootstrap_target(normalized_submission)
        key_file_path = self._resolve_submitted_key_file_path(normalized_submission)
        request_factory = cast(
            Callable[..., startup_bootstrap_module.BootstrapRepositoryRequest],
            startup_bootstrap_module.BootstrapRepositoryRequest,
        )
        request_kwargs: dict[str, object] = {
            "target": bootstrap_target,
            "creation_defaults": self._database_config.creation_defaults,
            "password": normalized_submission.get_field_value(StartupFieldName.PASSWORD),
            "key_file_path": key_file_path,
            "create_new_database": normalized_submission.mode is StartupDialogMode.CREATE,
            "key_preparer": self._key_preparer_resolver(bootstrap_target.dialect),
        }
        result = self._bootstrap_callback(
            request_factory(**request_kwargs)
        )

        if result.failure is not None:
            return StartupDialogSubmissionResult(
                failure=self._map_bootstrap_failure(result.failure, mode=normalized_submission.mode)
            )

        if result.repository is None:
            return StartupDialogSubmissionResult(
                failure=StartupDialogFailure(
                    StartupDialogFailureCode.BOOTSTRAP_FAILED,
                    "Startup lyckades inte öppna databasen.",
                    retryable=False,
                )
            )

        return StartupDialogSubmissionResult(
            success=StartupDialogSuccess(
                repository=result.repository,
                remembered_target=bootstrap_target,
                last_operator=normalized_submission.operator,
                invalidate_access=result.invalidate_access,
                backend_cleanup=result.backend_cleanup,
            )
        )

    def migrate(self, submission: StartupDialogSubmission) -> StartupDialogMigrationResult:
        """Validate migration inputs and hand them into backend-owned migration execution."""
        normalized_submission = self._normalize_submission(submission, infer_mode=False)
        local_failure = self._validate_submission(normalized_submission)
        if local_failure is not None:
            return StartupDialogMigrationResult(failure=local_failure)

        migration_request = MigrationRequest(
            target=self._build_effective_bootstrap_target(normalized_submission),
            creation_defaults=self._database_config.creation_defaults,
            password=normalized_submission.get_field_value(StartupFieldName.PASSWORD),
            key_file_path=self._resolve_submitted_key_file_path(normalized_submission),
            key_preparer=self._key_preparer_resolver(normalized_submission.dialect),
        )
        result = self._migration_callback(migration_request)
        if result.failure is not None:
            return StartupDialogMigrationResult(
                failure=self._map_bootstrap_failure(result.failure, mode=normalized_submission.mode)
            )

        return StartupDialogMigrationResult(
            message=result.message or _MIGRATION_SUCCEEDED_MESSAGE,
        )

    def _validate_submission(
        self,
        submission: _NormalizedStartupSubmission,
    ) -> StartupDialogFailure | None:
        """Return the first local validation failure for dialog submission."""
        if not submission.dialect:
            return StartupDialogFailure(
                StartupDialogFailureCode.MISSING_DIALECT,
                "Databastyp måste väljas.",
                field_name="dialect",
            )

        if not submission.database_path:
            return StartupDialogFailure(
                StartupDialogFailureCode.MISSING_DATABASE_PATH,
                "Databassökväg måste anges.",
                field_name=StartupFieldName.DATABASE_PATH.value,
            )

        for field in submission.backend_fields:
            if not field.required:
                continue
            if submission.get_field_value(field.field_name):
                continue
            if field.field_name is StartupFieldName.KEY_FILE_PATH:
                return StartupDialogFailure(
                    StartupDialogFailureCode.MISSING_REQUIRED_KEY_FILE,
                    "Nyckelfil krävs för den här databasen.",
                    field_name=StartupFieldName.KEY_FILE_PATH.value,
                )

        if submission.mode is StartupDialogMode.CREATE:
            if submission.get_field_value(StartupFieldName.PASSWORD) != submission.get_field_value(
                StartupFieldName.PASSWORD_CONFIRMATION
            ):
                return StartupDialogFailure(
                    StartupDialogFailureCode.PASSWORD_CONFIRMATION_MISMATCH,
                    "Lösenorden matchar inte.",
                    field_name=StartupFieldName.PASSWORD_CONFIRMATION.value,
                )

        password = submission.get_field_value(StartupFieldName.PASSWORD)
        if password:
            try:
                validate_password(
                    password,
                    min_length=self._database_config.creation_defaults.min_password_length,
                )
            except PasswordValidationError as exc:
                return StartupDialogFailure(
                    StartupDialogFailureCode.INVALID_PASSWORD,
                    str(exc),
                    field_name=StartupFieldName.PASSWORD.value,
                )

        return None

    def _build_effective_bootstrap_target(
        self,
        submission: _NormalizedStartupSubmission,
    ) -> BootstrapTargetConfig:
        """Return normalized remembered-target details for bootstrap and persistence."""
        return BootstrapTargetConfig(
            dialect=submission.dialect,
            database_path=submission.database_path,
            require_key_file=self._resolve_submitted_key_file_path(submission) is not None,
        )

    def _map_bootstrap_failure(
        self,
        failure: BootstrapFailure,
        *,
        mode: StartupDialogMode,
    ) -> StartupDialogFailure:
        """Translate bootstrap failures into presenter-visible dialog behavior."""
        if failure.code is BootstrapFailureCode.INVALID_PASSWORD:
            return StartupDialogFailure(
                StartupDialogFailureCode.INVALID_PASSWORD,
                failure.message,
                field_name=StartupFieldName.PASSWORD.value,
                retryable=failure.retryable,
            )

        if failure.code is BootstrapFailureCode.MISSING_REQUIRED_KEY_FILE:
            return StartupDialogFailure(
                StartupDialogFailureCode.MISSING_REQUIRED_KEY_FILE,
                failure.message,
                field_name=StartupFieldName.KEY_FILE_PATH.value,
                retryable=failure.retryable,
            )

        if failure.code is BootstrapFailureCode.INVALID_KEY_FILE:
            return StartupDialogFailure(
                StartupDialogFailureCode.INVALID_KEY_FILE,
                failure.message,
                field_name=StartupFieldName.KEY_FILE_PATH.value,
                retryable=failure.retryable,
            )

        if failure.code is BootstrapFailureCode.INVALID_CREDENTIALS:
            return StartupDialogFailure(
                StartupDialogFailureCode.INVALID_CREDENTIALS,
                failure.message,
                retryable=failure.retryable,
                should_clear_password=True,
                should_clear_password_confirmation=mode is StartupDialogMode.CREATE,
            )

        if failure.code is BootstrapFailureCode.UNSUPPORTED_DIALECT:
            return StartupDialogFailure(
                StartupDialogFailureCode.UNSUPPORTED_DIALECT,
                failure.message,
                field_name="dialect",
                retryable=failure.retryable,
            )

        if failure.code is BootstrapFailureCode.PROFILE_MISMATCH:
            return StartupDialogFailure(
                StartupDialogFailureCode.PROFILE_MISMATCH,
                failure.message,
                retryable=failure.retryable,
            )

        if failure.code is BootstrapFailureCode.MIGRATION_NEEDED:
            return StartupDialogFailure(
                StartupDialogFailureCode.MIGRATION_NEEDED,
                _MIGRATION_NEEDED_MESSAGE,
                retryable=failure.retryable,
            )

        if failure.code is BootstrapFailureCode.DATABASE_NEWER:
            return StartupDialogFailure(
                StartupDialogFailureCode.DATABASE_NEWER,
                _DATABASE_NEWER_MESSAGE,
                retryable=failure.retryable,
            )

        if failure.code is BootstrapFailureCode.MIGRATION_FAILED:
            return StartupDialogFailure(
                StartupDialogFailureCode.MIGRATION_FAILED,
                failure.message,
                retryable=failure.retryable,
            )

        if failure.code is BootstrapFailureCode.INCOMPLETE_BOOTSTRAP_TARGET:
            return StartupDialogFailure(
                StartupDialogFailureCode.BOOTSTRAP_TARGET_INVALID,
                failure.message,
                retryable=failure.retryable,
            )

        return StartupDialogFailure(
            StartupDialogFailureCode.BOOTSTRAP_FAILED,
            failure.message,
            retryable=failure.retryable,
        )

    @staticmethod
    def _normalize_dialect(dialect: str) -> str:
        """Return a normalized dialect string for presenter/bootstrap use."""
        return dialect.strip().lower()

    @staticmethod
    def _normalize_database_path(database_path: str) -> str:
        """Return a normalized database path string for presenter/bootstrap use."""
        return database_path.strip()

    @staticmethod
    def _normalize_optional_path(database_path: str) -> str:
        """Return a normalized optional path string for presenter/bootstrap use."""
        return database_path.strip()

    def _require_key_file_policy_for_mode(self, mode: StartupDialogMode) -> bool:
        """Return the admin-configured key-file policy for the requested mode."""
        if mode is StartupDialogMode.CREATE:
            return self._database_config.require_key_file_for_creation

        return self._database_config.require_key_file

    def _resolve_backend_fields(
        self,
        normalized_dialect: str,
        mode: StartupDialogMode,
        uses_remembered_target: bool,
        database_path: str,
        target_locked: bool,
    ) -> tuple[StartupFieldRequirement, ...]:
        """Return the active backend field contract for the normalized submission."""
        raw_backend_fields = self._startup_field_resolver(
            normalized_dialect,
            mode,
            uses_remembered_target,
            self._require_key_file_policy_for_mode(mode),
        )
        return project_backend_startup_fields_for_selection(
            normalized_dialect,
            mode=mode.value,
            database_path=database_path,
            target_locked=target_locked,
            backend_fields=raw_backend_fields,
        )

    def _normalize_submission(
        self,
        submission: StartupDialogSubmission,
        *,
        infer_mode: bool = True,
    ) -> _NormalizedStartupSubmission:
        """Return presenter-normalized startup input with remembered-target rules applied."""
        normalized_field_values = {
            StartupFieldName.DATABASE_PATH: self._normalize_database_path(
                submission.get_field_value(StartupFieldName.DATABASE_PATH)
            ),
            StartupFieldName.PASSWORD: submission.get_field_value(StartupFieldName.PASSWORD),
            StartupFieldName.PASSWORD_CONFIRMATION: submission.get_field_value(
                StartupFieldName.PASSWORD_CONFIRMATION
            ),
            StartupFieldName.KEY_FILE_PATH: self._normalize_optional_path(
                submission.get_field_value(StartupFieldName.KEY_FILE_PATH)
            ),
        }
        submitted_dialect = self._normalize_dialect(submission.dialect)
        requested_use_remembered_target = submission.uses_remembered_target and (
            submission.mode is StartupDialogMode.UNLOCK
        )
        startup_selection = resolve_effective_startup_selection(
            self._database_config,
            submitted_dialect=submitted_dialect,
            submitted_database_path=normalized_field_values[StartupFieldName.DATABASE_PATH],
            uses_remembered_target=requested_use_remembered_target,
        )
        uses_remembered_target = requested_use_remembered_target and not startup_selection.target_locked
        dialect = self._normalize_dialect(startup_selection.dialect)
        database_path = self._normalize_database_path(startup_selection.database_path)

        normalized_field_values[StartupFieldName.DATABASE_PATH] = database_path
        if infer_mode:
            resolved_mode = self._startup_mode_resolver(
                dialect,
                database_path,
                submission.mode,
            )
        else:
            resolved_mode = submission.mode
        backend_fields = self._resolve_backend_fields(
            dialect,
            resolved_mode,
            uses_remembered_target or (
                startup_selection.target_locked
                and resolved_mode is StartupDialogMode.UNLOCK
            ),
            database_path,
            startup_selection.target_locked,
        )

        return _NormalizedStartupSubmission(
            mode=resolved_mode,
            uses_remembered_target=uses_remembered_target,
            dialect=dialect,
            operator=submission.operator.strip(),
            database_path=database_path,
            field_values=normalized_field_values,
            backend_fields=backend_fields,
        )


    @staticmethod
    def _resolve_submitted_key_file_path(
        submission: _NormalizedStartupSubmission,
    ) -> str | PathLike[str] | None:
        """Return normalized key-file path only when the operator submitted one."""
        key_file_path = submission.get_field_value(StartupFieldName.KEY_FILE_PATH)
        return key_file_path or None


    def _build_password_policy_hint(self) -> str:
        """Return create-time password guidance from current config-backed policy."""
        return f"Minst {self._database_config.min_password_length} tecken för nytt lösenord."


__all__ = [
    "BootstrapRepositoryCallable",
    "KeyPreparerResolver",
    "StartupDialogFailure",
    "StartupDialogFailureCode",
    "StartupDialogMode",
    "StartupDialogMigrationResult",
    "StartupDialogPresenter",
    "StartupDialogState",
    "StartupDialogSubmission",
    "StartupDialogSubmissionResult",
    "StartupDialogSuccess",
    "StartupFieldResolver",
    "StartupModeResolver",
    "resolve_backend_key_preparer",
    "resolve_startup_mode",
    "resolve_startup_fields",
]



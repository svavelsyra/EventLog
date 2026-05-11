"""Current EventLog application entry point.

The application now consists of an app-owned Tk shell that hosts the startup
dialog first and, after successful startup, hands off to a minimal visible main
window scaffold on that same root.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from os import PathLike
from pathlib import Path

from src.config import (
    BootstrapUiConfig,
    CONFIG_TEMPLATE_FILENAME,
    DatabaseConfig,
    load_bootstrap_ui_config,
    load_database_config,
    save_bootstrap_ui_config,
    write_config_template,
)
from src.config.app_config import BootstrapTargetConfig
from src.core import (
    ResetAttemptFacts,
    ResetFollowUpFacts,
    ResetFollowUpIssue,
    assemble_reset_report_from_facts,
)
from src.core.app_runtime_state import AppRuntimeState
from src.db.repositories.bootstrap_backend_policy import (
    resolve_runtime_database_config,
    save_bootstrap_target_config,
    supports_external_key_file_advisory,
)
from src.db.repositories.startup_bootstrap import (
    BackendCleanupConcern,
    BackendCleanupError,
    BackendCleanupOutcome,
    cleanup_remembered_bootstrap_target,
)
from src.gui.app_shell import AppShell
from src.gui.startup_dialog_controller import (
    EmergencyResetCallback,
    EmergencyResetResult,
)
from src.gui.presenters.startup_dialog_presenter import StartupDialogSuccess
from src.security import ResetCoordinator, ResetOutcome
from src.security.reset_flow import delete_log_cleanup_targets

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.ini"
ResetCleanup = Callable[[], None]

LOGGER = logging.getLogger(__name__)

ResetFollowUpHint = ResetFollowUpIssue
MainWindowLifecycleCallback = Callable[[], str | None]

_MAIN_WINDOW_RESET_FAILURE_MESSAGE = "MISSLYCKADES"
_MAIN_WINDOW_MANUAL_FOLLOW_UP_MESSAGE = "Följ upp manuellt."
_MAIN_WINDOW_KEY_FILE_ADVISORY = "Eventuella nyckelfiler behöver tas bort manuellt."
_MAIN_WINDOW_TEMPLATE_WRITTEN_MESSAGE = f"Skrev {CONFIG_TEMPLATE_FILENAME}."
_MAIN_WINDOW_TEMPLATE_WRITE_FAILED_MESSAGE = f"Kunde inte skriva {CONFIG_TEMPLATE_FILENAME}."


@dataclass(frozen=True, slots=True, init=False)
class ActiveContextResetResult:
    """App-facing reset result that wraps the core report plus neutral outcome."""

    _success: bool
    _shared_outcome: ResetOutcome
    _follow_up_hints: tuple[ResetFollowUpHint, ...]
    _manual_key_file_cleanup_advisory: bool

    def __init__(
        self,
        success: bool,
        shared_outcome: ResetOutcome,
        follow_up_hints: tuple[ResetFollowUpHint, ...] = (),
        manual_key_file_cleanup_advisory: bool = False,
    ) -> None:
        object.__setattr__(self, "_success", success)
        object.__setattr__(self, "_shared_outcome", shared_outcome)
        object.__setattr__(self, "_follow_up_hints", follow_up_hints)
        object.__setattr__(self, "_manual_key_file_cleanup_advisory", manual_key_file_cleanup_advisory)

    @property
    def success(self) -> bool:
        """Return whether the reset completed without remaining follow-up issues."""
        return self._success

    @property
    def shared_outcome(self) -> ResetOutcome:
        """Return the neutral shared-flow reset outcome."""
        return self._shared_outcome

    @property
    def follow_up_hints(self) -> tuple[ResetFollowUpHint, ...]:
        """Return sanitized follow-up hints for incomplete cleanup."""
        return self._follow_up_hints

    @property
    def manual_key_file_cleanup_advisory(self) -> bool:
        """Return whether the caller should show a coarse manual key-file advisory."""
        return self._manual_key_file_cleanup_advisory


def _resolve_config_path(config_path: str | PathLike[str] | None) -> Path:
    """Return the config.ini path used for startup config load/save operations."""
    return DEFAULT_CONFIG_PATH if config_path is None else Path(config_path)



def resolve_database_config(config_path: str | PathLike[str] | None = None) -> DatabaseConfig:
    """Return runtime bootstrap configuration from config.ini or defaults."""
    resolved_config_path = _resolve_config_path(config_path)
    loaded_config = load_database_config(resolved_config_path)
    if loaded_config is not None:
        return resolve_runtime_database_config(
            loaded_config,
            config_path=resolved_config_path,
        )

    return DatabaseConfig()


def resolve_bootstrap_ui_settings(
    config_path: str | PathLike[str] | None = None,
) -> BootstrapUiConfig:
    """Return bootstrap-owned UI/user settings from config.ini or code defaults."""
    return load_bootstrap_ui_config(_resolve_config_path(config_path))



def _resolve_reset_denial_step(
    startup_result: StartupDialogSuccess | None,
) -> ResetCleanup | None:
    """Return the app-owned denial step for the active startup/bootstrap result."""
    if startup_result is None:
        return None

    if startup_result.invalidate_access is not None:
        return startup_result.invalidate_access

    def _missing_invalidator() -> None:
        raise RuntimeError("Active startup context does not expose access invalidation.")

    return _missing_invalidator


def _build_reset_follow_up_facts(
    *,
    backend_cleanup_failed: bool = False,
    backend_cleanup_outcome: BackendCleanupOutcome | None = None,
    log_cleanup_failed: bool = False,
    bootstrap_reset_failed: bool,
) -> ResetFollowUpFacts:
    """Return core-owned reset follow-up facts for a completed reset attempt."""
    database_artifacts_issue = backend_cleanup_failed

    if backend_cleanup_outcome is not None and backend_cleanup_outcome.report is not None:
        failed_concerns = backend_cleanup_outcome.report.failed_concerns
        database_artifacts_issue = BackendCleanupConcern.DATABASE_ARTIFACTS in failed_concerns

    return ResetFollowUpFacts(
        database_artifacts_issue=database_artifacts_issue,
        log_artifacts_issue=log_cleanup_failed,
        bootstrap_reset_issue=bootstrap_reset_failed,
    )


def _build_reset_result(
    *,
    outcome: ResetOutcome,
    phase_failure: bool,
    follow_up_facts: ResetFollowUpFacts,
    manual_key_file_cleanup_advisory: bool = False,
) -> ActiveContextResetResult:
    """Return the caller-visible reset result for the shared flow execution."""
    report = assemble_reset_report_from_facts(
        ResetAttemptFacts(
            phase_failure=phase_failure,
            follow_up=follow_up_facts,
        )
    )

    return ActiveContextResetResult(
        success=report.success,
        shared_outcome=outcome,
        follow_up_hints=report.follow_up_issues,
        manual_key_file_cleanup_advisory=(manual_key_file_cleanup_advisory and not report.success),
    )


def run_startup_bootstrap_reset(
    database_config: DatabaseConfig,
    *,
    config_path: str | PathLike[str] | None = None,
) -> ActiveContextResetResult:
    """Run the startup-only reset callback for remembered bootstrap state."""
    backend_cleanup_failed = False
    backend_cleanup_outcome: BackendCleanupOutcome | None = None
    log_cleanup_failed = False
    resolved_config_path = _resolve_config_path(config_path)

    try:
        backend_cleanup_outcome = cleanup_remembered_bootstrap_target(database_config)
    except BackendCleanupError as exc:
        backend_cleanup_failed = True
        backend_cleanup_outcome = exc.outcome
    except Exception:
        backend_cleanup_failed = True

    try:
        delete_log_cleanup_targets(resolved_config_path)
    except OSError:
        log_cleanup_failed = True

    bootstrap_reset_failed = False
    try:
        save_bootstrap_target_config(resolved_config_path, BootstrapTargetConfig())
    except Exception:
        bootstrap_reset_failed = True

    return _build_reset_result(
        outcome=ResetOutcome(
            had_active_context=False,
            denial_succeeded=True,
            cleanup_started=False,
            cleanup_completed=False,
        ),
        phase_failure=False,
        follow_up_facts=_build_reset_follow_up_facts(
            backend_cleanup_failed=backend_cleanup_failed,
            backend_cleanup_outcome=backend_cleanup_outcome,
            log_cleanup_failed=log_cleanup_failed,
            bootstrap_reset_failed=bootstrap_reset_failed,
        ),
        manual_key_file_cleanup_advisory=supports_external_key_file_advisory(
            database_config.bootstrap_target.dialect
        ),
    )


def _build_startup_emergency_reset_callback(
    database_config: DatabaseConfig,
    *,
    config_path: str | PathLike[str],
) -> EmergencyResetCallback | None:
    """Return the startup-dialog emergency-reset callback for current bootstrap state."""
    if not database_config.can_attempt_auto_open:
        return None

    def startup_reset_callback() -> EmergencyResetResult:
        return run_startup_bootstrap_reset(
            database_config,
            config_path=config_path,
        )

    return startup_reset_callback


def _build_main_window_reset_failure_message(result: ActiveContextResetResult) -> str:
    """Return a coarse shell-level reset failure message."""
    message_lines = [_MAIN_WINDOW_RESET_FAILURE_MESSAGE]
    if result.follow_up_hints:
        message_lines.append(_MAIN_WINDOW_MANUAL_FOLLOW_UP_MESSAGE)
    if result.manual_key_file_cleanup_advisory:
        message_lines.append(_MAIN_WINDOW_KEY_FILE_ADVISORY)

    return "\n".join(message_lines)


def run_active_context_close(startup_result: StartupDialogSuccess | None) -> ResetOutcome:
    """Release the active context for normal shell shutdown without destructive cleanup."""
    return ResetCoordinator(
        deny_access=_resolve_reset_denial_step(startup_result),
        cleanup=None,
    ).run()


def _build_main_window_reset_callback(
    shell: AppShell,
    startup_result: StartupDialogSuccess,
    *,
    config_path: str | PathLike[str],
) -> MainWindowLifecycleCallback:
    """Return the visible-shell destructive reset callback for the active context."""

    def reset_callback() -> str | None:
        result = run_active_context_reset(startup_result, config_path=config_path)
        if result.success:
            shell.close()
            return None

        return _build_main_window_reset_failure_message(result)

    return reset_callback


def _build_main_window_close_callback(
    shell: AppShell,
    startup_result: StartupDialogSuccess,
    *,
    config_path: str | PathLike[str],
    bootstrap_ui_config: BootstrapUiConfig,
    app_runtime_state: AppRuntimeState,
) -> MainWindowLifecycleCallback:
    """Return the visible-shell close callback for the active context."""

    def close_callback() -> str | None:
        outcome = run_active_context_close(startup_result)
        if not outcome.failure_categories:
            try:
                save_bootstrap_ui_config(
                    config_path,
                    BootstrapUiConfig(
                        main_window=shell.snapshot_main_window_config() or bootstrap_ui_config.main_window,
                        language=bootstrap_ui_config.language,
                        last_operator=app_runtime_state.active_operator.strip(),
                    ),
                )
            except Exception:
                LOGGER.warning("Failed to persist bootstrap UI config on close.", exc_info=True)
            shell.close()
            return None

        return _MAIN_WINDOW_RESET_FAILURE_MESSAGE

    return close_callback


def _build_config_template_regeneration_callback(
    *,
    config_path: str | PathLike[str],
) -> MainWindowLifecycleCallback:
    """Return the visible-shell callback that rewrites the reference config template."""

    def regenerate_template_callback() -> str | None:
        template_path = _resolve_config_path(config_path).with_name(CONFIG_TEMPLATE_FILENAME)
        try:
            write_config_template(template_path)
        except Exception:
            LOGGER.warning("Failed to regenerate config.ini.template.", exc_info=True)
            return _MAIN_WINDOW_TEMPLATE_WRITE_FAILED_MESSAGE

        return _MAIN_WINDOW_TEMPLATE_WRITTEN_MESSAGE

    return regenerate_template_callback



def run_active_context_reset(
    startup_result: StartupDialogSuccess | None,
    *,
    cleanup: ResetCleanup | None = None,
    config_path: str | PathLike[str] | None = None,
) -> ActiveContextResetResult:
    """Run the shared reset flow for the current startup/bootstrap result."""
    backend_cleanup_failed = False
    backend_cleanup_outcome: BackendCleanupOutcome | None = None
    log_cleanup_failed = False

    cleanup_step = cleanup
    if cleanup_step is None and startup_result is not None:
        resolved_config_path = _resolve_config_path(config_path)

        def cleanup_step() -> None:
            nonlocal backend_cleanup_failed, backend_cleanup_outcome, log_cleanup_failed

            if startup_result.backend_cleanup is not None:
                try:
                    backend_cleanup_outcome = startup_result.backend_cleanup()
                except BackendCleanupError as exc:
                    backend_cleanup_failed = True
                    backend_cleanup_outcome = exc.outcome
                    raise
                except Exception:
                    backend_cleanup_failed = True
                    raise

            try:
                delete_log_cleanup_targets(resolved_config_path)
            except OSError:
                log_cleanup_failed = True
                raise

    outcome = ResetCoordinator(
        deny_access=_resolve_reset_denial_step(startup_result),
        cleanup=cleanup_step,
    ).run()

    bootstrap_reset_failed = False
    if outcome.had_active_context and outcome.denial_succeeded:
        try:
            save_bootstrap_target_config(
                _resolve_config_path(config_path),
                BootstrapTargetConfig(),
            )
        except Exception:
            bootstrap_reset_failed = True

    return _build_reset_result(
        outcome=outcome,
        phase_failure=bool(outcome.failure_categories) or bootstrap_reset_failed,
        follow_up_facts=_build_reset_follow_up_facts(
            backend_cleanup_failed=backend_cleanup_failed,
            backend_cleanup_outcome=backend_cleanup_outcome,
            log_cleanup_failed=log_cleanup_failed,
            bootstrap_reset_failed=bootstrap_reset_failed,
        ),
        manual_key_file_cleanup_advisory=(
            startup_result is not None
            and supports_external_key_file_advisory(startup_result.remembered_target.dialect)
        ),
    )



def run_app(config_path: str | PathLike[str] | None = None) -> StartupDialogSuccess | None:
    """Run startup, show the minimal main window, and return the startup result."""
    resolved_config_path = _resolve_config_path(config_path)
    bootstrap_ui_settings = resolve_bootstrap_ui_settings(resolved_config_path)
    database_config = resolve_database_config(resolved_config_path)
    shell = AppShell()
    startup_result = shell.run_startup_dialog(
        database_config,
        last_operator_prefill=bootstrap_ui_settings.last_operator,
        emergency_reset_callback=_build_startup_emergency_reset_callback(
            database_config,
            config_path=resolved_config_path,
        ),
    )
    if startup_result is not None:
        app_runtime_state = AppRuntimeState(active_operator=startup_result.last_operator)
        try:
            save_bootstrap_target_config(resolved_config_path, startup_result.remembered_target)
        except Exception:
            shell.close()
            raise
        main_window_callbacks: dict[str, MainWindowLifecycleCallback] = {
            "template_callback": _build_config_template_regeneration_callback(
                config_path=resolved_config_path,
            ),
            "reset_callback": _build_main_window_reset_callback(
                shell,
                startup_result,
                config_path=resolved_config_path,
            ),
            "close_callback": _build_main_window_close_callback(
                shell,
                startup_result,
                config_path=resolved_config_path,
                bootstrap_ui_config=bootstrap_ui_settings,
                app_runtime_state=app_runtime_state,
            ),
        }
        shell.show_main_window(
            startup_result,
            app_runtime_state=app_runtime_state,
            window_config=bootstrap_ui_settings.main_window,
            **main_window_callbacks,
        )

    return startup_result



def main() -> int:
    """Run the current EventLog application shell."""
    run_app()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


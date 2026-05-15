"""Real startup-dialog controller wiring for presenter + Tk view.

This controller keeps the startup dialog runnable without moving validation or
secure-bootstrap policy into widget code. It owns only GUI-layer orchestration:
wiring callbacks, invoking the presenter, and closing the dialog when the
operator cancels or startup succeeds beneath a caller-owned app-shell root.
"""

from __future__ import annotations

import tkinter as tk
from dataclasses import replace
from tkinter import filedialog
from typing import Callable, Protocol, cast

from src.config import DatabaseConfig
from src.core import ResetFollowUpIssue
from src.db.repositories.startup_selection import StartupFieldName
from src.gui.presenters.startup_dialog_presenter import (
    StartupDialogFailureCode,
    StartupDialogPresenter,
    StartupDialogState,
    StartupDialogSubmission,
    StartupDialogSuccess,
    resolve_startup_mode,
)
from src.gui.views.startup_dialog_view import (
    StartupDialogActionCallbacks,
    StartupDialogView,
    VoidCallback,
)


class StartupDialogViewProtocol(Protocol):
    """Minimal view contract used by the startup dialog controller."""

    window: tk.Misc

    def render_state(self, state: StartupDialogState) -> None:
        """Render presenter-owned state."""

    def get_submission(self) -> StartupDialogSubmission:
        """Return the current startup submission from widget values."""

    def set_submission_changed_callback(self, callback: VoidCallback) -> None:
        """Register callback for submission-changing UI events."""

    def set_action_callbacks(
        self,
        callbacks: StartupDialogActionCallbacks,
    ) -> None:
        """Register action-oriented UI callbacks."""

    def set_error_message(self, message: str) -> None:
        """Display an error message in the dialog."""

    def clear_error_message(self) -> None:
        """Clear the current error message."""

    def set_status_message(self, message: str) -> None:
        """Display a neutral status message in the dialog."""

    def clear_status_message(self) -> None:
        """Clear the current status message."""

    def clear_sensitive_fields(self, *, clear_password_confirmation: bool = False) -> None:
        """Clear password-related input fields."""

    def focus_primary_input(self) -> None:
        """Move focus to the most relevant input."""

    def destroy(self) -> None:
        """Destroy the dialog widgets."""


class TkRootProtocol(Protocol):
    """Minimal caller-owned root contract used by the startup dialog controller."""

    def withdraw(self) -> None:
        """Hide the root window."""

    def wait_window(self, window: tk.Misc) -> None:
        """Block until the given dialog window is destroyed."""

    def destroy(self) -> None:
        """Destroy the root window and remaining descendants."""


ViewFactory = Callable[[tk.Misc], StartupDialogViewProtocol]
RootFactory = Callable[[], TkRootProtocol]


class EmergencyResetResult(Protocol):
    """Minimal reset-result contract consumed by the startup GUI layer."""

    @property
    def success(self) -> bool:
        """Return whether the reset completed without remaining follow-up issues."""

    @property
    def follow_up_hints(self) -> tuple[ResetFollowUpIssue, ...]:
        """Return sanitized follow-up hints for incomplete reset cleanup."""

    @property
    def manual_key_file_cleanup_advisory(self) -> bool:
        """Return whether to show a coarse manual key-file advisory."""


EmergencyResetCallback = Callable[[], EmergencyResetResult]

_RESET_FOLLOW_UP_MESSAGES = {
    ResetFollowUpIssue.DATABASE_ARTIFACTS: "databasartefakter",
    ResetFollowUpIssue.LOG_ARTIFACTS: "loggar",
    ResetFollowUpIssue.BOOTSTRAP_RESET: "startupminne",
}
_MANUAL_KEY_FILE_CLEANUP_ADVISORY = "Eventuella nyckelfiler behöver tas bort manuellt."


class StartupDialogController:
    """Wire the startup presenter and startup view into a runnable Tk dialog."""

    def __init__(
        self,
        database_config: DatabaseConfig,
        *,
        last_operator_prefill: str = "",
        presenter: StartupDialogPresenter | None = None,
        view_factory: ViewFactory = StartupDialogView,
        emergency_reset_callback: EmergencyResetCallback | None = None,
    ) -> None:
        self._presenter = presenter or StartupDialogPresenter(
            database_config,
            startup_mode_resolver=lambda dialect, database_path, fallback_mode: resolve_startup_mode(
                dialect,
                database_path,
                fallback_mode,
            ),
        )
        self._view_factory = view_factory
        self._emergency_reset_callback = emergency_reset_callback
        self._last_operator_prefill = last_operator_prefill.strip()

        self._view: StartupDialogViewProtocol | None = None
        self._result: StartupDialogSuccess | None = None
        self._pending_migration_submission: StartupDialogSubmission | None = None
        self._migration_running = False

    def run(self, *, root: TkRootProtocol) -> StartupDialogSuccess | None:
        """Run the startup dialog beneath the caller-owned root until completion."""
        self._result = None

        try:
            view = self._view_factory(cast(tk.Misc, cast(object, root)))
            self._view = view
            self._wire_callbacks(view)

            initial_state = self._presenter.get_initial_state(operator=self._last_operator_prefill)
            view.render_state(self._prepare_state_for_view(initial_state))
            view.clear_error_message()
            view.focus_primary_input()
            root.wait_window(view.window)
            return self._result
        finally:
            self._view = None

    def _wire_callbacks(self, view: StartupDialogViewProtocol) -> None:
        view.set_action_callbacks(
            StartupDialogActionCallbacks(
                submit=self._handle_submit,
                cancel=self._handle_cancel,
                migrate=self._handle_migrate,
                browse_key_file=self._handle_browse_key_file,
                emergency_reset=(
                    self._handle_emergency_reset
                    if self._emergency_reset_callback is not None
                    else None
                ),
            )
        )
        view.set_submission_changed_callback(self._handle_submission_changed)


    def _handle_submit(self) -> None:
        view = self._require_view()

        self._pending_migration_submission = None
        self._migration_running = False
        view.clear_status_message()
        view.clear_error_message()
        submission = view.get_submission()
        result = self._presenter.submit(submission)

        if result.success is not None:
            self._result = result.success
            self._close_dialog()
            return

        if result.failure is None:
            view.set_error_message("Startup lyckades inte slutföras.")
            view.focus_primary_input()
            return

        failure = result.failure
        if failure.code is StartupDialogFailureCode.MIGRATION_NEEDED:
            self._pending_migration_submission = submission
            updated_state = self._presenter.recompute_state(submission)
            view.render_state(self._prepare_state_for_view(updated_state))
        view.set_error_message(failure.message)
        if failure.should_clear_password:
            view.clear_sensitive_fields(
                clear_password_confirmation=failure.should_clear_password_confirmation,
            )
        view.focus_primary_input()

    def _handle_migrate(self) -> None:
        view = self._require_view()
        pending_submission = self._pending_migration_submission
        if pending_submission is None:
            return

        current_submission = view.get_submission()
        self._migration_running = True
        view.clear_error_message()
        view.clear_status_message()
        running_state = self._presenter.recompute_state(current_submission)
        view.render_state(self._prepare_state_for_view(running_state))

        try:
            result = self._presenter.migrate(current_submission)
        finally:
            self._migration_running = False

        updated_state = self._presenter.recompute_state(current_submission)
        self._pending_migration_submission = None
        view.render_state(self._prepare_state_for_view(updated_state))

        if result.succeeded:
            if result.message:
                view.set_status_message(result.message)
            view.focus_primary_input()
            return

        assert result.failure is not None
        view.set_error_message(result.failure.message)
        if result.failure.should_clear_password:
            view.clear_sensitive_fields(
                clear_password_confirmation=result.failure.should_clear_password_confirmation,
            )
        view.focus_primary_input()

    def _handle_cancel(self) -> None:
        self._result = None
        self._close_dialog()

    def _handle_browse_key_file(self) -> None:
        view = self._require_view()
        selected_path = filedialog.askopenfilename(parent=view.window, title="Välj nyckelfil")
        if not selected_path:
            return

        self._render_current_submission_with_updates(
            field_updates={StartupFieldName.KEY_FILE_PATH: selected_path},
        )

    def _handle_submission_changed(self) -> None:
        self._render_state_from_view()

    def _handle_emergency_reset(self) -> None:
        if self._emergency_reset_callback is None:
            return

        view = self._require_view()
        view.clear_error_message()
        view.clear_status_message()
        view.clear_sensitive_fields(clear_password_confirmation=True)

        reset_result = self._emergency_reset_callback()
        if reset_result.success:
            self._close_dialog()
            return

        view.set_error_message(self._build_emergency_reset_failure_message(reset_result))

    def _close_dialog(self) -> None:
        view = self._view
        if view is None:
            return

        try:
            view.destroy()
        except tk.TclError:
            pass

    def _require_view(self) -> StartupDialogViewProtocol:
        if self._view is None:
            raise RuntimeError("Startup dialog view is not available.")

        return self._view

    def _render_state_from_view(
        self,
    ) -> None:
        self._render_current_submission_with_updates()

    def _render_current_submission_with_updates(
        self,
        *,
        field_updates: dict[StartupFieldName, str] | None = None,
    ) -> None:
        view = self._require_view()
        current_submission = view.get_submission()
        if field_updates is None:
            self._render_state_from_submission(current_submission)
            return

        updated_field_values = dict(current_submission.field_values)
        updated_field_values.update(field_updates)
        updated_submission = StartupDialogSubmission(
            mode=current_submission.mode,
            dialect=current_submission.dialect,
            operator=current_submission.operator,
            uses_remembered_target=cast(bool, current_submission.uses_remembered_target),
            field_values=updated_field_values,
        )

        self._render_state_from_submission(updated_submission)

    def _render_state_from_submission(self, submission: StartupDialogSubmission) -> None:
        view = self._require_view()
        self._pending_migration_submission = None
        self._migration_running = False
        updated_state = self._presenter.recompute_state(submission)
        view.render_state(self._prepare_state_for_view(updated_state))
        view.clear_error_message()
        view.clear_status_message()
        view.focus_primary_input()


    def _prepare_state_for_view(self, state: StartupDialogState) -> StartupDialogState:
        """Return controller-adjusted view state for current callback availability."""
        prepared_state = state
        if self._emergency_reset_callback is None and prepared_state.allow_emergency_reset:
            prepared_state = replace(prepared_state, allow_emergency_reset=False)

        show_migration_action = self._pending_migration_submission is not None
        return replace(
            prepared_state,
            show_migration_action=show_migration_action,
            submit_enabled=not self._migration_running,
            migration_action_enabled=show_migration_action and not self._migration_running,
        )

    @staticmethod
    def _build_emergency_reset_failure_message(reset_result: EmergencyResetResult) -> str:
        """Return a coarse sanitized reset-failure message for the startup dialog."""
        follow_up_labels = tuple(
            dict.fromkeys(
                _RESET_FOLLOW_UP_MESSAGES[issue]
                for issue in reset_result.follow_up_hints
                if issue in _RESET_FOLLOW_UP_MESSAGES
            )
        )
        if not follow_up_labels and not reset_result.manual_key_file_cleanup_advisory:
            return "MISSLYCKADES"

        message_lines = ["MISSLYCKADES"]
        if follow_up_labels:
            message_lines.append(f"Följ upp manuellt: {', '.join(follow_up_labels)}.")
        if reset_result.manual_key_file_cleanup_advisory:
            message_lines.append(_MANUAL_KEY_FILE_CLEANUP_ADVISORY)

        return "\n".join(message_lines)

__all__ = [
    "EmergencyResetCallback",
    "RootFactory",
    "StartupDialogController",
    "StartupDialogViewProtocol",
    "TkRootProtocol",
    "ViewFactory",
]




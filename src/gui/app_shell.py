"""Top-level GUI shell seams for EventLog application lifetime.

The app shell owns the single Tk root for the whole current application
lifetime. It first hosts the startup dialog beneath that root and, after a
successful startup handoff, turns the same root into the minimal visible main
window shell.
"""

from __future__ import annotations

from enum import StrEnum
import tkinter as tk
from os import PathLike
from typing import Callable, Protocol, cast

from src.config import DatabaseConfig, MainWindowConfig
from src.core.app_runtime_state import AppRuntimeState
from src.db.adapters.event_log_adapter import EventLogAdapter
from src.gui.presenters.communication_presenter import CommunicationPresenter
from src.gui.presenters.startup_dialog_presenter import StartupDialogSuccess
from src.gui.startup_dialog_controller import (
    EmergencyResetCallback,
    StartupDialogController,
    TkRootProtocol,
)
from src.gui.views.main_window_shell_view import MainWindowShellView


MainWindowLifecycleCallback = Callable[[], str | None]
MainWindowFileActionCallback = Callable[[str | PathLike[str]], str | None]


class MainWindowLifecycleAction(StrEnum):
    """Shell-owned outcome for how the visible main-window phase should end."""

    EXIT_APPLICATION = "exit_application"
    RESTART_TO_STARTUP = "restart_to_startup"


class AppShellRootProtocol(TkRootProtocol, Protocol):
    """Minimal root contract needed across startup hosting and visible shell."""

    def deiconify(self) -> None:
        """Show the root window."""

    def mainloop(self) -> None:
        """Run the Tk event loop until the root closes."""

    def quit(self) -> None:
        """Request that the current Tk main loop returns."""


class StartupDialogRunner(Protocol):
    """Minimal startup-controller contract consumed by the app shell."""

    def run(self, *, root: TkRootProtocol) -> StartupDialogSuccess | None:
        """Run the startup dialog beneath the provided root."""


class StartupControllerFactory(Protocol):
    """Factory contract for the startup step hosted by the app shell."""

    def __call__(
        self,
        database_config: DatabaseConfig,
        *,
        last_operator_prefill: str = "",
        emergency_reset_callback: EmergencyResetCallback | None = None,
    ) -> StartupDialogRunner:
        """Return a runnable startup-step controller."""


class MainWindowFactory(Protocol):
    """Factory contract for the visible main-window shell."""

    def __call__(
        self,
        root: tk.Tk,
        startup_result: StartupDialogSuccess,
        *,
        app_runtime_state: AppRuntimeState,
        window_config: MainWindowConfig,
        status_bar_log_level: str,
        app_config_template_callback: MainWindowFileActionCallback | None = None,
        communication_template_callback: MainWindowFileActionCallback | None = None,
        communication_export_callback: MainWindowFileActionCallback | None = None,
        communication_import_callback: MainWindowFileActionCallback | None = None,
        reset_callback: MainWindowLifecycleCallback | None = None,
        close_callback: MainWindowLifecycleCallback | None = None,
    ) -> object:
        """Build the visible main-window shell on the app-owned root."""


class MainWindowSettingsProvider(Protocol):
    """Minimal main-window contract for snapshotting bootstrap-owned window state."""

    def snapshot_window_config(self) -> MainWindowConfig:
        """Return the current main-window geometry/state snapshot."""


def _create_startup_controller(
    database_config: DatabaseConfig,
    *,
    last_operator_prefill: str = "",
    emergency_reset_callback: EmergencyResetCallback | None = None,
) -> StartupDialogRunner:
    """Return the real startup controller used by the minimal app shell."""
    return StartupDialogController(
        database_config,
        last_operator_prefill=last_operator_prefill,
        emergency_reset_callback=emergency_reset_callback,
    )


def _create_main_window_shell(
    root: tk.Tk,
    startup_result: StartupDialogSuccess,
    *,
    app_runtime_state: AppRuntimeState,
    window_config: MainWindowConfig,
    status_bar_log_level: str,
    app_config_template_callback: MainWindowFileActionCallback | None = None,
    communication_template_callback: MainWindowFileActionCallback | None = None,
    communication_export_callback: MainWindowFileActionCallback | None = None,
    communication_import_callback: MainWindowFileActionCallback | None = None,
    reset_callback: MainWindowLifecycleCallback | None = None,
    close_callback: MainWindowLifecycleCallback | None = None,
) -> object:
    """Build the real minimal visible main-window shell."""
    main_window_factory = cast(Callable[..., MainWindowShellView], MainWindowShellView)
    main_window = main_window_factory(
        root,
        app_runtime_state,
        window_config=window_config,
        status_bar_log_level=status_bar_log_level,
        app_config_template_callback=app_config_template_callback,
        communication_template_callback=communication_template_callback,
        communication_export_callback=communication_export_callback,
        communication_import_callback=communication_import_callback,
        reset_callback=reset_callback,
        close_callback=close_callback,
    )
    communication_presenter = CommunicationPresenter(
        cast(EventLogAdapter, startup_result.repository),
        main_window.communication_tab_view,
        app_runtime_state,
    )
    communication_presenter.attach()
    setattr(main_window, "communication_presenter", communication_presenter)
    return main_window


class AppShell:
    """Own the Tk root lifetime for startup plus the minimal visible shell."""

    def __init__(
        self,
        *,
        root_factory: Callable[[], AppShellRootProtocol] = tk.Tk,
        startup_controller_factory: StartupControllerFactory = _create_startup_controller,
        main_window_factory: MainWindowFactory = _create_main_window_shell,
    ) -> None:
        self._root_factory = root_factory
        self._startup_controller_factory = startup_controller_factory
        self._main_window_factory = main_window_factory
        self._root: AppShellRootProtocol | None = None
        self._main_window: object | None = None
        self._main_window_lifecycle_action: MainWindowLifecycleAction | None = None

    def run_startup_dialog(
        self,
        database_config: DatabaseConfig,
        *,
        last_operator_prefill: str = "",
        emergency_reset_callback: EmergencyResetCallback | None = None,
    ) -> StartupDialogSuccess | None:
        """Run the blocking startup dialog under an app-shell-owned root."""
        root = self._ensure_root()
        root.withdraw()

        try:
            controller = self._startup_controller_factory(
                database_config,
                last_operator_prefill=last_operator_prefill,
                emergency_reset_callback=emergency_reset_callback,
            )
            result = controller.run(root=root)
        except Exception:
            self.close()
            raise

        if result is None:
            self.close()

        return result

    def show_main_window(
        self,
        startup_result: StartupDialogSuccess,
        *,
        app_runtime_state: AppRuntimeState,
        window_config: MainWindowConfig,
        status_bar_log_level: str,
        app_config_template_callback: MainWindowFileActionCallback | None = None,
        communication_template_callback: MainWindowFileActionCallback | None = None,
        communication_export_callback: MainWindowFileActionCallback | None = None,
        communication_import_callback: MainWindowFileActionCallback | None = None,
        reset_callback: MainWindowLifecycleCallback | None = None,
        close_callback: MainWindowLifecycleCallback | None = None,
    ) -> MainWindowLifecycleAction:
        """Turn the app-owned root into the visible shell and return its lifecycle outcome."""
        root = self._require_root()
        self._main_window_lifecycle_action = MainWindowLifecycleAction.EXIT_APPLICATION
        self._main_window = self._main_window_factory(
            cast(tk.Tk, cast(object, root)),
            startup_result,
            app_runtime_state=app_runtime_state,
            window_config=window_config,
            status_bar_log_level=status_bar_log_level,
            app_config_template_callback=app_config_template_callback,
            communication_template_callback=communication_template_callback,
            communication_export_callback=communication_export_callback,
            communication_import_callback=communication_import_callback,
            reset_callback=reset_callback,
            close_callback=close_callback,
        )
        root.deiconify()

        try:
            root.mainloop()
        except Exception:
            self.close()
            raise

        lifecycle_action = self._main_window_lifecycle_action or MainWindowLifecycleAction.EXIT_APPLICATION
        self._main_window_lifecycle_action = None
        self._teardown_main_window()

        if lifecycle_action is MainWindowLifecycleAction.RESTART_TO_STARTUP:
            root.withdraw()
            return lifecycle_action

        self.close()
        return lifecycle_action

    def request_restart_to_startup(self) -> None:
        """End the visible main-window phase and return the app to fresh startup."""
        self._signal_main_window_lifecycle_action(MainWindowLifecycleAction.RESTART_TO_STARTUP)

    def request_exit_application(self) -> None:
        """End the visible main-window phase and fully close the app shell."""
        self._signal_main_window_lifecycle_action(MainWindowLifecycleAction.EXIT_APPLICATION)

    def close(self) -> None:
        """Destroy the app-owned root if it still exists."""
        root = self._root
        self._root = None
        self._main_window_lifecycle_action = None
        self._teardown_main_window()
        if root is None:
            return

        try:
            root.destroy()
        except tk.TclError:
            pass

    def snapshot_main_window_config(self) -> MainWindowConfig | None:
        """Return the current main-window bootstrap snapshot when available."""
        main_window = self._main_window
        if main_window is None or not hasattr(main_window, "snapshot_window_config"):
            return None

        provider = cast(MainWindowSettingsProvider, main_window)
        return provider.snapshot_window_config()

    def refresh_communication_presenter_runtime_config(self) -> bool:
        """Reload and re-render Communication config in the visible main window when available."""
        main_window = self._main_window
        if main_window is None or not hasattr(main_window, "communication_presenter"):
            return False

        communication_presenter = getattr(main_window, "communication_presenter")
        if not hasattr(communication_presenter, "reload_runtime_config"):
            return False

        communication_presenter.reload_runtime_config()
        return True

    def _ensure_root(self) -> AppShellRootProtocol:
        if self._root is None:
            self._root = cast(AppShellRootProtocol, self._root_factory())

        assert self._root is not None
        return self._root

    def _require_root(self) -> AppShellRootProtocol:
        if self._root is None:
            raise RuntimeError("App shell root is not available.")

        assert self._root is not None
        return self._root

    def _signal_main_window_lifecycle_action(self, action: MainWindowLifecycleAction) -> None:
        self._main_window_lifecycle_action = action
        root = self._root
        if root is None:
            return

        root.quit()

    def _teardown_main_window(self) -> None:
        main_window = self._main_window
        self._main_window = None
        if main_window is None:
            return

        if hasattr(main_window, "destroy"):
            getattr(main_window, "destroy")()
            return

        if hasattr(main_window, "dispose"):
            getattr(main_window, "dispose")()


__all__ = [
    "AppShell",
    "MainWindowFileActionCallback",
    "MainWindowLifecycleAction",
    "AppShellRootProtocol",
    "MainWindowLifecycleCallback",
    "MainWindowFactory",
    "MainWindowSettingsProvider",
    "StartupControllerFactory",
    "StartupDialogRunner",
]


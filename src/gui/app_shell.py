"""Top-level GUI shell seams for EventLog application lifetime.

The app shell owns the single Tk root for the whole current application
lifetime. It first hosts the startup dialog beneath that root and, after a
successful startup handoff, turns the same root into the minimal visible main
window shell.
"""

from __future__ import annotations

import tkinter as tk
from typing import Callable, Protocol, cast

from src.config import DatabaseConfig, MainWindowConfig
from src.core.app_runtime_state import AppRuntimeState
from src.gui.presenters.startup_dialog_presenter import StartupDialogSuccess
from src.gui.startup_dialog_controller import (
    EmergencyResetCallback,
    StartupDialogController,
    TkRootProtocol,
)
from src.gui.views.main_window_shell_view import MainWindowShellView


MainWindowLifecycleCallback = Callable[[], str | None]


class AppShellRootProtocol(TkRootProtocol, Protocol):
    """Minimal root contract needed across startup hosting and visible shell."""

    def deiconify(self) -> None:
        """Show the root window."""

    def mainloop(self) -> None:
        """Run the Tk event loop until the root closes."""


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
        window_config: MainWindowConfig | None = None,
        template_callback: MainWindowLifecycleCallback | None = None,
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
    window_config: MainWindowConfig | None = None,
    template_callback: MainWindowLifecycleCallback | None = None,
    reset_callback: MainWindowLifecycleCallback | None = None,
    close_callback: MainWindowLifecycleCallback | None = None,
) -> object:
    """Build the real minimal visible main-window shell."""
    del startup_result
    return MainWindowShellView(
        root,
        app_runtime_state,
        window_config=window_config,
        template_callback=template_callback,
        reset_callback=reset_callback,
        close_callback=close_callback,
    )


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
        window_config: MainWindowConfig | None = None,
        template_callback: MainWindowLifecycleCallback | None = None,
        reset_callback: MainWindowLifecycleCallback | None = None,
        close_callback: MainWindowLifecycleCallback | None = None,
    ) -> None:
        """Turn the app-owned root into the visible main-window shell."""
        root = self._require_root()
        self._main_window = self._main_window_factory(
            cast(tk.Tk, cast(object, root)),
            startup_result,
            app_runtime_state=app_runtime_state,
            window_config=window_config,
            template_callback=template_callback,
            reset_callback=reset_callback,
            close_callback=close_callback,
        )
        root.deiconify()

        try:
            root.mainloop()
        finally:
            self.close()

    def close(self) -> None:
        """Destroy the app-owned root if it still exists."""
        root = self._root
        self._root = None
        self._main_window = None
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


__all__ = [
    "AppShell",
    "AppShellRootProtocol",
    "MainWindowLifecycleCallback",
    "MainWindowFactory",
    "MainWindowSettingsProvider",
    "StartupControllerFactory",
    "StartupDialogRunner",
]


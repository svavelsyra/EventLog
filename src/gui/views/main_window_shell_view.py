"""Minimal visible main-window shell for the first production GUI scaffold.

This view intentionally owns only the top-level shell structure needed for the
first visible GUI slice: toolbar area, tab container, and status area. Real tab
workflows, destructive actions, and richer status behavior remain later stories.
"""

from __future__ import annotations

from collections.abc import Callable
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

from src.config import MainWindowConfig
from src.core.app_runtime_state import AppRuntimeState


ShellActionCallback = Callable[[], str | None]


class MainWindowShellView:
    """Render the minimal production-owned main window shell on the Tk root."""

    _DEFAULT_STATUS_TEXT = "Statusyta - loggning och operatörsstatus kommer senare."

    def __init__(
        self,
        root: tk.Tk,
        app_runtime_state: AppRuntimeState,
        *,
        window_config: MainWindowConfig | None = None,
        template_callback: ShellActionCallback | None = None,
        reset_callback: ShellActionCallback | None = None,
        close_callback: ShellActionCallback | None = None,
    ) -> None:
        self.root = root
        self.app_runtime_state = app_runtime_state
        self._window_config = window_config or MainWindowConfig()
        self._template_callback = template_callback
        self._reset_callback = reset_callback
        self._close_callback = close_callback
        self.root.title("EventLog - Pluton Event Logger")
        self.menu_bar = tk.Menu(self.root)
        self.tools_menu = tk.Menu(self.menu_bar, tearoff=False)
        self.tools_menu.add_command(
            label="Skriv configmall",
            command=self.handle_template_requested,
        )
        self.menu_bar.add_cascade(label="Verktyg", menu=self.tools_menu)
        self.root.configure(menu=self.menu_bar)
        self._apply_window_config(self._window_config)
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)

        self.toolbar_frame = ttk.Frame(self.root, padding=(12, 10))
        self.toolbar_frame.grid(row=0, column=0, sticky=tk.EW)
        self.toolbar_frame.columnconfigure(0, weight=1)
        self.toolbar_label = ttk.Label(
            self.toolbar_frame,
            text="Verktygsfält - shell för kommande kommandon.",
            anchor="w",
        )
        self.toolbar_label.grid(row=0, column=0, sticky=tk.W)
        default_button_font = tkfont.nametofont("TkDefaultFont").copy()
        default_button_font.configure(weight="bold")
        self._reset_button_font = default_button_font
        self.reset_button = tk.Button(
            self.toolbar_frame,
            text="Nollställ",
            command=self.handle_reset_requested,
            font=self._reset_button_font,
            background="#c62828",
            foreground="#ffffff",
            activebackground="#8e0000",
            activeforeground="#ffffff",
            highlightbackground="#c62828",
            highlightcolor="#8e0000",
            highlightthickness=1,
            borderwidth=2,
            relief="raised",
            cursor="hand2",
            padx=12,
            pady=6,
        )
        self.reset_button.grid(row=0, column=1, sticky=tk.E)

        self.notebook = ttk.Notebook(self.root)
        self.notebook.grid(row=1, column=0, sticky=tk.NSEW, padx=12, pady=(0, 8))

        self.tab_hosts: dict[str, ttk.Frame] = {}
        self.placeholder_labels: dict[str, ttk.Label] = {}
        self._build_placeholder_tab(
            key="communication",
            tab_text="Kommunikation",
            heading_text="Kommunikation",
            placeholder_text="Platshållare för kommande kommunikationsflöde.",
        )
        self._build_placeholder_tab(
            key="event",
            tab_text="Händelser",
            heading_text="Händelser",
            placeholder_text="Platshållare för kommande händelseflöde.",
        )
        self._build_placeholder_tab(
            key="personnel",
            tab_text="Personal",
            heading_text="Personal",
            placeholder_text="Platshållare för kommande personalflöde.",
        )

        self.status_frame = ttk.Frame(self.root, padding=(12, 8))
        self.status_frame.grid(row=2, column=0, sticky=tk.EW)
        self.status_frame.columnconfigure(0, weight=1)
        self.status_label = ttk.Label(
            self.status_frame,
            text=self._DEFAULT_STATUS_TEXT,
            anchor="w",
        )
        self.status_label.grid(row=0, column=0, sticky=tk.W)
        self.root.protocol("WM_DELETE_WINDOW", self.handle_close_requested)

    def set_status_message(self, message: str) -> None:
        """Display a coarse shell-level status or lifecycle message."""
        self.status_label.configure(text=message or self._DEFAULT_STATUS_TEXT)

    def handle_reset_requested(self) -> None:
        """Trigger the app-owned destructive reset callback when available."""
        self._run_shell_action(self._reset_callback)

    def handle_template_requested(self) -> None:
        """Trigger the app-owned config-template regeneration callback when available."""
        self._run_shell_action(self._template_callback)

    def handle_close_requested(self) -> None:
        """Trigger the app-owned close callback when available."""
        self._run_shell_action(self._close_callback)

    def snapshot_window_config(self) -> MainWindowConfig:
        """Return the current main-window geometry/state for bootstrap persistence."""
        self.root.update_idletasks()
        try:
            root_state = str(self.root.state())
        except tk.TclError:
            root_state = "normal"

        return MainWindowConfig(
            window_state="zoomed" if root_state == "zoomed" else "normal",
            window_width=max(1, self.root.winfo_width()),
            window_height=max(1, self.root.winfo_height()),
            window_x=max(0, self.root.winfo_x()),
            window_y=max(0, self.root.winfo_y()),
        )

    def _build_placeholder_tab(
        self,
        *,
        key: str,
        tab_text: str,
        heading_text: str,
        placeholder_text: str,
    ) -> None:
        tab_frame = ttk.Frame(self.notebook, padding=16)
        tab_frame.columnconfigure(0, weight=1)

        heading_label = ttk.Label(tab_frame, text=heading_text, style="Heading.TLabel")
        heading_label.grid(row=0, column=0, sticky=tk.W)

        placeholder_label = ttk.Label(
            tab_frame,
            text=placeholder_text,
            wraplength=720,
            justify="left",
        )
        placeholder_label.grid(row=1, column=0, sticky=tk.W, pady=(8, 0))

        self.notebook.add(tab_frame, text=tab_text)
        self.tab_hosts[key] = tab_frame
        self.placeholder_labels[key] = placeholder_label

    def _run_shell_action(self, callback: ShellActionCallback | None) -> None:
        if callback is None:
            return

        status_message = callback()
        if status_message is not None:
            self.set_status_message(status_message)

    def _apply_window_config(self, window_config: MainWindowConfig) -> None:
        screen_width = max(1, self.root.winfo_screenwidth())
        screen_height = max(1, self.root.winfo_screenheight())
        minimum_width = min(800, screen_width)
        minimum_height = min(600, screen_height)
        self.root.minsize(minimum_width, minimum_height)

        width = min(max(window_config.window_width, minimum_width), screen_width)
        height = min(max(window_config.window_height, minimum_height), screen_height)
        x_position = min(max(window_config.window_x, 0), max(screen_width - width, 0))
        y_position = min(max(window_config.window_y, 0), max(screen_height - height, 0))

        self.root.geometry(f"{width}x{height}+{x_position}+{y_position}")

        try:
            self.root.state(
                "zoomed" if window_config.window_state == "zoomed" else "normal"
            )
        except tk.TclError:
            self.root.state("normal")


__all__ = ["MainWindowShellView"]


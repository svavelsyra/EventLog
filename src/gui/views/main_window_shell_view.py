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


ShellActionCallback = Callable[[], str | None]


class MainWindowShellView:
    """Render the minimal production-owned main window shell on the Tk root."""

    _DEFAULT_STATUS_TEXT = "Statusyta - loggning och operatörsstatus kommer senare."

    def __init__(
        self,
        root: tk.Tk,
        *,
        reset_callback: ShellActionCallback | None = None,
        close_callback: ShellActionCallback | None = None,
    ) -> None:
        self.root = root
        self._reset_callback = reset_callback
        self._close_callback = close_callback
        self.root.title("EventLog - Pluton Event Logger")
        self.root.minsize(800, 600)
        self.root.geometry("1200x700")
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
            relief=tk.RAISED,
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

    def handle_close_requested(self) -> None:
        """Trigger the app-owned close callback when available."""
        self._run_shell_action(self._close_callback)

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


__all__ = ["MainWindowShellView"]


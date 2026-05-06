"""Minimal visible main-window shell for the first production GUI scaffold.

This view intentionally owns only the top-level shell structure needed for the
first visible GUI slice: toolbar area, tab container, and status area. Real tab
workflows, destructive actions, and richer status behavior remain later stories.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk


class MainWindowShellView:
    """Render the minimal production-owned main window shell on the Tk root."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
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
            text="Statusyta - loggning och operatörsstatus kommer senare.",
            anchor="w",
        )
        self.status_label.grid(row=0, column=0, sticky=tk.W)

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


__all__ = ["MainWindowShellView"]


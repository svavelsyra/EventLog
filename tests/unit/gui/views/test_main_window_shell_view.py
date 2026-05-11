import tkinter as tk

import pytest

from src.config import MainWindowConfig
from src.core.app_runtime_state import AppRuntimeState
from src.gui.views.main_window_shell_view import MainWindowShellView


pytestmark = pytest.mark.unit


def _scenario_render_main_window_shell(root: tk.Tk) -> dict[str, object]:
    app_runtime_state = AppRuntimeState(active_operator="Sgt Example")
    view = MainWindowShellView(root, app_runtime_state=app_runtime_state)
    root.update_idletasks()

    selected_tab = view.notebook.select()
    return {
        "title": root.title(),
        "has_menu": bool(str(root.cget("menu"))),
        "tools_menu_entry_count": view.tools_menu.index("end"),
        "template_menu_label": view.tools_menu.entrycget(0, "label"),
        "toolbar_manager": view.toolbar_frame.winfo_manager(),
        "toolbar_text": view.toolbar_label.cget("text"),
        "reset_button_text": view.reset_button.cget("text"),
        "reset_button_class": view.reset_button.winfo_class(),
        "reset_button_background": view.reset_button.cget("background"),
        "reset_button_relief": view.reset_button.cget("relief"),
        "notebook_manager": view.notebook.winfo_manager(),
        "status_manager": view.status_frame.winfo_manager(),
        "status_text": view.status_label.cget("text"),
        "tab_texts": [view.notebook.tab(tab_id, "text") for tab_id in view.notebook.tabs()],
        "selected_tab_text": view.notebook.tab(selected_tab, "text"),
        "tab_host_keys": list(view.tab_hosts),
        "placeholder_texts": {
            key: label.cget("text")
            for key, label in view.placeholder_labels.items()
        },
        "active_operator": view.app_runtime_state.active_operator,
    }


def _scenario_invoke_shell_callbacks(root: tk.Tk) -> dict[str, object]:
    events: list[str] = []
    view = MainWindowShellView(
        root,
        app_runtime_state=AppRuntimeState(),
        template_callback=lambda: events.append("template") or "Skrev config.ini.template.",
        reset_callback=lambda: events.append("reset") or "Reset misslyckades.",
        close_callback=lambda: events.append("close") or "Stängning misslyckades.",
    )
    root.update_idletasks()

    close_command = root.protocol("WM_DELETE_WINDOW")
    assert close_command

    view.tools_menu.invoke(0)
    view.reset_button.invoke()
    root.tk.call(close_command)
    return {
        "events": events,
        "status_text": view.status_label.cget("text"),
        "close_command": close_command,
    }


def _scenario_apply_clamped_window_config(root: tk.Tk) -> dict[str, object]:
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    view = MainWindowShellView(
        root,
        app_runtime_state=AppRuntimeState(),
        window_config=MainWindowConfig(
            window_state="normal",
            window_width=screen_width + 500,
            window_height=screen_height + 500,
            window_x=-120,
            window_y=screen_height + 250,
        ),
    )
    root.update_idletasks()
    snapshot = view.snapshot_window_config()
    return {
        "screen_width": screen_width,
        "screen_height": screen_height,
        "snapshot": snapshot,
    }


def test_main_window_shell_renders_toolbar_notebook_status_and_placeholder_tabs(run_tk_scenario) -> None:
    result = run_tk_scenario(_scenario_render_main_window_shell)

    assert result["title"] == "EventLog - Pluton Event Logger"
    assert result["has_menu"] is True
    assert result["tools_menu_entry_count"] == 0
    assert result["template_menu_label"] == "Skriv configmall"
    assert result["toolbar_manager"] == "grid"
    assert result["toolbar_text"] == "Verktygsfält - shell för kommande kommandon."
    assert result["reset_button_text"] == "Nollställ"
    assert result["reset_button_class"] == "Button"
    assert result["reset_button_background"] == "#c62828"
    assert result["reset_button_relief"] == "raised"
    assert result["notebook_manager"] == "grid"
    assert result["status_manager"] == "grid"
    assert result["status_text"] == "Statusyta - loggning och operatörsstatus kommer senare."
    assert result["tab_texts"] == ["Kommunikation", "Händelser", "Personal"]
    assert result["selected_tab_text"] == "Kommunikation"
    assert result["tab_host_keys"] == ["communication", "event", "personnel"]
    assert result["active_operator"] == "Sgt Example"
    assert result["placeholder_texts"] == {
        "communication": "Platshållare för kommande kommunikationsflöde.",
        "event": "Platshållare för kommande händelseflöde.",
        "personnel": "Platshållare för kommande personalflöde.",
    }


def test_main_window_shell_invokes_reset_button_and_close_protocol_callbacks(run_tk_scenario) -> None:
    result = run_tk_scenario(_scenario_invoke_shell_callbacks)

    assert result["events"] == ["template", "reset", "close"]
    assert result["status_text"] == "Stängning misslyckades."
    assert result["close_command"]


def test_main_window_shell_clamps_out_of_bounds_window_geometry(run_tk_scenario) -> None:
    result = run_tk_scenario(_scenario_apply_clamped_window_config)
    snapshot = result["snapshot"]

    assert isinstance(snapshot, MainWindowConfig)
    assert snapshot.window_state == "normal"
    assert 1 <= snapshot.window_width <= result["screen_width"]
    assert 1 <= snapshot.window_height <= result["screen_height"]
    assert snapshot.window_x >= 0
    assert snapshot.window_y >= 0



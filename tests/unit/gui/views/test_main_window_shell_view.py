import tkinter as tk
import logging

import pytest

import src.gui.views.main_window_shell_view as main_window_shell_view_module
from src.config import MainWindowConfig
from src.core.app_runtime_state import AppRuntimeState
from src.gui.views.main_window_shell_view import MainWindowShellView


pytestmark = pytest.mark.unit


def _scenario_render_main_window_shell(root: tk.Tk) -> dict[str, object]:
    app_runtime_state = AppRuntimeState(active_operator="Sgt Example")
    view = MainWindowShellView(
        root,
        app_runtime_state=app_runtime_state,
        window_config=MainWindowConfig(),
        status_bar_log_level="WARNING",
    )
    root.update_idletasks()

    selected_tab = view.notebook.select()
    return {
        "title": root.title(),
        "has_menu": bool(str(root.cget("menu"))),
        "tools_menu_entry_count": view.tools_menu.index("end"),
        "tools_menu_labels": [view.tools_menu.entrycget(index, "label") for index in range(4)],
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
        "communication_entry_section_text": view.communication_tab_view.entry_section.cget("text"),
        "communication_filter_section_text": view.communication_tab_view.filter_section.cget("text"),
        "communication_log_section_text": view.communication_tab_view.log_section.cget("text"),
        "communication_log_columns": list(view.communication_tab_view.log_table["columns"]),
        "placeholder_texts": {
            key: label.cget("text")
            for key, label in view.placeholder_labels.items()
        },
        "active_operator": view.app_runtime_state.active_operator,
    }


def _scenario_invoke_shell_callbacks(root: tk.Tk) -> dict[str, object]:
    events: list[object] = []
    original_asksaveasfilename = main_window_shell_view_module.filedialog.asksaveasfilename
    original_askopenfilename = main_window_shell_view_module.filedialog.askopenfilename
    view = MainWindowShellView(
        root,
        app_runtime_state=AppRuntimeState(),
        window_config=MainWindowConfig(),
        status_bar_log_level="WARNING",
        app_config_template_callback=lambda path: events.append(("app_config_template", path))
        or f"Skrev {path}.",
        communication_template_callback=lambda path: events.append(("communication_template", path))
        or f"Skrev {path}.",
        communication_export_callback=lambda path: events.append(("communication_export", path))
        or f"Skrev {path}.",
        communication_import_callback=lambda path: events.append(("communication_import", path))
        or f"Importerade {path}.",
        reset_callback=lambda: events.append("reset") or "Reset misslyckades.",
        close_callback=lambda: events.append("close") or "Stängning misslyckades.",
    )
    selected_paths = {
        "config.ini.template": "C:/Exports/config.ini.template",
        "communication_config.template.json": "C:/Exports/communication_config.template.json",
        "communication_config.export.json": "C:/Exports/communication_config.export.json",
    }

    try:
        main_window_shell_view_module.filedialog.asksaveasfilename = (
            lambda **kwargs: selected_paths[kwargs["initialfile"]]
        )
        main_window_shell_view_module.filedialog.askopenfilename = (
            lambda **_kwargs: "C:/Imports/communication_config.custom.json"
        )
        root.update_idletasks()

        close_command = root.protocol("WM_DELETE_WINDOW")
        assert close_command

        view.tools_menu.invoke(0)
        view.tools_menu.invoke(1)
        view.tools_menu.invoke(2)
        view.tools_menu.invoke(3)
        view.reset_button.invoke()
        root.tk.call(close_command)
        return {
            "events": events,
            "status_text": view.status_label.cget("text"),
            "close_command": close_command,
        }
    finally:
        main_window_shell_view_module.filedialog.asksaveasfilename = original_asksaveasfilename
        main_window_shell_view_module.filedialog.askopenfilename = original_askopenfilename


def _scenario_cancel_save_dialog_does_not_invoke_template_callback(root: tk.Tk) -> dict[str, object]:
    events: list[object] = []
    original_asksaveasfilename = main_window_shell_view_module.filedialog.asksaveasfilename
    view = MainWindowShellView(
        root,
        app_runtime_state=AppRuntimeState(),
        window_config=MainWindowConfig(),
        status_bar_log_level="WARNING",
        app_config_template_callback=lambda path: events.append(("app_config_template", path))
        or f"Skrev {path}.",
    )
    try:
        main_window_shell_view_module.filedialog.asksaveasfilename = lambda **_kwargs: ""
        root.update_idletasks()

        view.tools_menu.invoke(0)
        return {
            "events": events,
            "status_text": view.status_label.cget("text"),
        }
    finally:
        main_window_shell_view_module.filedialog.asksaveasfilename = original_asksaveasfilename


def _scenario_apply_clamped_window_config(root: tk.Tk) -> dict[str, object]:
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    view = MainWindowShellView(
        root,
        app_runtime_state=AppRuntimeState(),
        status_bar_log_level="WARNING",
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


def _scenario_status_bar_log_level_controls_visible_messages(root: tk.Tk) -> dict[str, str]:
    info_view = MainWindowShellView(
        root,
        app_runtime_state=AppRuntimeState(),
        window_config=MainWindowConfig(),
        status_bar_log_level="INFO",
    )
    info_logger = logging.getLogger("eventlog.tests.communication.info")
    info_logger.setLevel(logging.INFO)
    info_logger.info("Informationsmeddelande visas.")
    root.update_idletasks()
    info_text = info_view.status_label.cget("text")
    info_view.dispose()

    warning_view = MainWindowShellView(
        root,
        app_runtime_state=AppRuntimeState(),
        window_config=MainWindowConfig(),
        status_bar_log_level="ERROR",
    )
    warning_logger = logging.getLogger("eventlog.tests.communication.warning")
    warning_logger.setLevel(logging.WARNING)
    warning_logger.warning("Varning ska inte visas.")
    root.update_idletasks()
    warning_text = warning_view.status_label.cget("text")
    error_logger = logging.getLogger("eventlog.tests.communication.error")
    error_logger.setLevel(logging.ERROR)
    error_logger.error("Fel ska visas.")
    root.update_idletasks()
    error_text = warning_view.status_label.cget("text")
    warning_view.dispose()

    return {
        "info_text": info_text,
        "warning_text": warning_text,
        "error_text": error_text,
    }


def test_main_window_shell_renders_toolbar_notebook_status_and_communication_scaffold(run_tk_scenario) -> None:
    result = run_tk_scenario(_scenario_render_main_window_shell)

    assert result["title"] == "EventLog - Pluton Event Logger"
    assert result["has_menu"] is True
    assert result["tools_menu_entry_count"] == 3
    assert result["tools_menu_labels"] == [
        "Skriv app-configmall",
        "Skriv kommunikationsmall",
        "Exportera kommunikationskonfiguration",
        "Importera kommunikationskonfiguration",
    ]
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
    assert result["communication_entry_section_text"] == "Ny kommunikationspost"
    assert result["communication_filter_section_text"] == "Filter"
    assert result["communication_log_section_text"] == "Kommunikationslogg"
    assert result["communication_log_columns"] == [
        "status",
        "time",
        "from",
        "to",
        "method",
        "message",
        "confirmed",
        "edited",
        "operator",
    ]
    assert result["active_operator"] == "Sgt Example"
    assert result["placeholder_texts"] == {
        "event": "Platshållare för kommande händelseflöde.",
        "personnel": "Platshållare för kommande personalflöde.",
    }


def test_main_window_shell_invokes_reset_button_and_close_protocol_callbacks(run_tk_scenario) -> None:
    result = run_tk_scenario(_scenario_invoke_shell_callbacks)

    assert result["events"] == [
        ("app_config_template", "C:/Exports/config.ini.template"),
        ("communication_template", "C:/Exports/communication_config.template.json"),
        ("communication_export", "C:/Exports/communication_config.export.json"),
        ("communication_import", "C:/Imports/communication_config.custom.json"),
        "reset",
        "close",
    ]
    assert result["status_text"] == "Stängning misslyckades."
    assert result["close_command"]


def test_main_window_shell_skips_file_action_when_save_dialog_is_cancelled(run_tk_scenario) -> None:
    result = run_tk_scenario(_scenario_cancel_save_dialog_does_not_invoke_template_callback)

    assert result == {
        "events": [],
        "status_text": "Statusyta - loggning och operatörsstatus kommer senare.",
    }


def test_main_window_shell_clamps_out_of_bounds_window_geometry(run_tk_scenario) -> None:
    result = run_tk_scenario(_scenario_apply_clamped_window_config)
    snapshot = result["snapshot"]

    assert isinstance(snapshot, MainWindowConfig)
    assert snapshot.window_state == "normal"
    assert 1 <= snapshot.window_width <= result["screen_width"]
    assert 1 <= snapshot.window_height <= result["screen_height"]
    assert snapshot.window_x >= 0
    assert snapshot.window_y >= 0


def test_main_window_shell_status_bar_obeys_configured_log_level(run_tk_scenario) -> None:
    result = run_tk_scenario(_scenario_status_bar_log_level_controls_visible_messages)

    assert result == {
        "info_text": "Last log: Informationsmeddelande visas.",
        "warning_text": "Statusyta - loggning och operatörsstatus kommer senare.",
        "error_text": "Last log: Fel ska visas.",
    }



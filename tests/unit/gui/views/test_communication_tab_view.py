import tkinter as tk
from types import SimpleNamespace
from tkinter import ttk
from typing import cast

import pytest

import src.gui.views.communication_tab_view as communication_tab_view_module
from src.gui.presenters.communication_presenter import (
    CommunicationEditorState,
    CommunicationEntryDetailState,
    CommunicationFormData,
    CommunicationFormState,
    CommunicationLogFilterData,
    CommunicationLogRow,
    CommunicationLogState,
    CommunicationPathChoice,
    CommunicationPathFieldState,
    CommunicationQualifierFieldState,
)
from src.gui.views.communication_tab_view import CommunicationTabView


pytestmark = pytest.mark.unit


def _scenario_render_communication_tab_view(root: tk.Tk) -> dict[str, object]:
    host = ttk.Frame(root)
    host.grid(row=0, column=0, sticky=tk.NSEW)
    host.columnconfigure(0, weight=1)
    host.rowconfigure(0, weight=1)

    view = CommunicationTabView(host)
    view.frame.grid(row=0, column=0, sticky=tk.NSEW)
    root.update_idletasks()

    return {
        "entry_section_text": view.entry_section.cget("text"),
        "filter_section_text": view.filter_section.cget("text"),
        "log_section_text": view.log_section.cget("text"),
        "entry_label_texts": [
            view.time_label.cget("text"),
            view.system_label.cget("text"),
            view.from_label.cget("text"),
            view.to_label.cget("text"),
            view.message_label.cget("text"),
        ],
        "entry_hint_text": view.entry_hint_label.cget("text"),
        "filter_label_texts": [
            view.filter_time_from_label.cget("text"),
            view.filter_time_to_label.cget("text"),
            view.filter_from_label.cget("text"),
            view.filter_to_label.cget("text"),
            view.filter_system_label.cget("text"),
            view.filter_text_label.cget("text"),
        ],
        "log_hint_text": view.log_hint_label.cget("text"),
        "button_texts": [
            view.swap_button.cget("text"),
            view.clear_button.cget("text"),
            view.save_button.cget("text"),
            view.apply_filters_button.cget("text"),
            view.clear_filters_button.cget("text"),
            view.open_selected_button.cget("text"),
            view.edit_selected_button.cget("text"),
            view.delete_selected_button.cget("text"),
            view.configure_columns_button.cget("text"),
        ],
        "participant_entry_widths": [
            int(view.from_entry.cget("width")),
            int(view.to_entry.cget("width")),
        ],
        "filter_field_widths": {
            "time_from": int(view.filter_time_from_entry.cget("width")),
            "time_to": int(view.filter_time_to_entry.cget("width")),
            "from": int(view.filter_from_entry.cget("width")),
            "to": int(view.filter_to_entry.cget("width")),
            "system": int(view.filter_system_combobox.cget("width")),
            "text": int(view.filter_text_entry.cget("width")),
        },
        "message_height": int(view.message_text.cget("height")),
        "time_entry_width": int(view.time_entry.cget("width")),
        "message_widget_class": view.message_text.winfo_class(),
        "log_widget_class": view.log_table.winfo_class(),
        "entry_section_rows": {
            "metadata": int(view.metadata_frame.grid_info()["row"]),
            "message": int(view.message_field_frame.grid_info()["row"]),
            "actions": int(view.entry_actions_frame.grid_info()["row"]),
        },
        "metadata_columns": {
            "time": int(view.time_field_frame.grid_info()["column"]),
            "participants": int(view.participants_frame.grid_info()["column"]),
            "route": int(view.route_section.grid_info()["column"]),
        },
        "log_section_rows": {
            "hint": int(view.log_hint_label.grid_info()["row"]),
            "filter": int(view.filter_section.grid_info()["row"]),
            "table": int(view.log_table.grid_info()["row"]),
        },
        "log_column_headings": {
            column_name: view.log_table.heading(column_name, "text")
            for column_name in view.log_table["columns"]
        },
    }


def test_communication_tab_view_renders_visible_entry_filter_and_log_regions(run_tk_scenario) -> None:
    result = run_tk_scenario(_scenario_render_communication_tab_view)

    assert result["entry_section_text"] == "Ny kommunikationspost"
    assert result["filter_section_text"] == "Filter"
    assert result["log_section_text"] == "Kommunikationslogg"
    assert result["entry_label_texts"] == ["Tid", "System", "Från", "Till", "Meddelande"]
    assert result["entry_hint_text"] == "Formbeteende kopplas in i senare stories."
    assert result["filter_label_texts"] == ["Tid från", "Tid till", "Från", "Till", "System", "Text"]
    assert result["log_hint_text"] == "Tabellinnehåll och interaktion kopplas in i senare stories."
    assert result["button_texts"] == [
        "⇄",
        "Rensa",
        "Spara",
        "Filtrera",
        "Rensa filter",
        "Öppna",
        "Redigera",
        "Ta bort",
        "Kolumner...",
    ]
    assert result["time_entry_width"] == 10
    assert result["participant_entry_widths"] == [8, 8]
    assert result["filter_field_widths"] == {
        "time_from": 16,
        "time_to": 16,
        "from": 12,
        "to": 12,
        "system": 18,
        "text": 18,
    }
    assert result["message_height"] == 4
    assert result["entry_section_rows"] == {"metadata": 0, "message": 1, "actions": 2}
    assert result["metadata_columns"] == {"time": 0, "participants": 1, "route": 2}
    assert result["log_section_rows"] == {"hint": 0, "filter": 1, "table": 2}
    assert result["message_widget_class"] == "Text"
    assert result["log_widget_class"] == "Treeview"
    assert result["log_column_headings"] == {
        "status": "Status",
        "time": "Tid ▼",
        "from": "Från",
        "to": "Till",
        "method": "Metod",
        "message": "Meddelande",
        "confirmed": "Bekr",
        "edited": "Redigerad",
        "operator": "Operatör",
    }


def _scenario_use_passive_communication_view_contract(root: tk.Tk) -> dict[str, object]:
    host = ttk.Frame(root)
    host.grid(row=0, column=0, sticky=tk.NSEW)
    host.columnconfigure(0, weight=1)
    host.rowconfigure(0, weight=1)

    events: list[str] = []
    view = CommunicationTabView(host)
    view.frame.grid(row=0, column=0, sticky=tk.NSEW)
    view.set_save_handler(lambda: events.append("save"))
    view.set_clear_handler(lambda: events.append("clear"))
    view.set_swap_handler(lambda: events.append("swap"))
    view.set_config_change_handler(lambda: events.append("config"))
    view.set_log_interaction_handlers(
        on_apply_filters=lambda: events.append("apply_filters"),
        on_clear_filters=lambda: events.append("clear_filters"),
        on_open_selected=lambda: events.append("open"),
        on_edit_selected=lambda: events.append("edit"),
        on_delete_selected=lambda: events.append("delete"),
        on_sort_requested=lambda column_name: events.append(f"sort:{column_name}"),
        on_selection_changed=lambda entry_id: events.append(f"select:{entry_id}"),
    )
    view.render_form_state(
        CommunicationFormState(
            system_choices=("Layered Radio", "Kurir"),
            selected_system="Layered Radio",
            path_fields=(
                CommunicationPathFieldState(
                    label="Nät",
                    options=(
                        CommunicationPathChoice(value="PRIMARY", label="Primärnät"),
                        CommunicationPathChoice(value="SECONDARY", label="Reservnät"),
                    ),
                    selected_value="PRIMARY",
                ),
                CommunicationPathFieldState(
                    label="Rutt",
                    options=(
                        CommunicationPathChoice(value="VOICE", label="Talväg"),
                        CommunicationPathChoice(value="DATA", label="Dataväg"),
                    ),
                    selected_value="DATA",
                ),
            ),
            qualifier_fields=(
                CommunicationQualifierFieldState(
                    qualifier_key="encrypted",
                    label="Krypterad",
                    field_type="boolean",
                    value=True,
                    visible=True,
                ),
                CommunicationQualifierFieldState(
                    qualifier_key="mode",
                    label="Driftläge",
                    field_type="enum",
                    value="data",
                    visible=True,
                    valid_values=("voice", "data"),
                ),
                CommunicationQualifierFieldState(
                    qualifier_key="forced",
                    label="Låst läge",
                    field_type="boolean",
                    value=True,
                    visible=True,
                    read_only=True,
                ),
                CommunicationQualifierFieldState(
                    qualifier_key="hidden",
                    label="Dold",
                    field_type="boolean",
                    value=False,
                    visible=False,
                ),
            ),
        )
    )
    view.set_form_data(
        CommunicationFormData(
            time_text="120945",
            from_field="Alpha",
            to_field="Bravo",
            message_content="Kort meddelande",
            communication_system="Layered Radio",
            communication_path=("PRIMARY", "DATA"),
            communication_qualifiers={
                "encrypted": True,
                "mode": "data",
                "forced": True,
            },
        )
    )
    view.render_log_state(
        CommunicationLogState(
            filter_data=CommunicationLogFilterData(
                time_from_text="2026-05-12 10:00",
                time_to_text="2026-05-12 11:00",
                from_text="Alpha",
                to_text="Bravo",
                system_text="Layered Radio",
                message_text="Kort",
            ),
            rows=(
                CommunicationLogRow(
                    entry_id=7,
                    status_text="SE ÖVER",
                    time_text="OGILTIG TID",
                    from_text="Alpha",
                    to_text="Bravo",
                    method_text="RA180",
                    message_text="Kort meddelande",
                    confirmed_text="✓",
                    edited_text="",
                    operator_text="Operatör Ett",
                    needs_review=True,
                    is_selected=True,
                ),
            ),
            sort_column="from",
            sort_descending=False,
            system_filter_choices=("Layered Radio", "Kurir"),
        )
    )
    view.render_editor_state(
        CommunicationEditorState(
            section_title="Redigera kommunikationspost",
            save_button_text="Uppdatera",
            clear_button_text="Avbryt redigering",
            selection_actions_enabled=True,
            is_edit_mode=True,
        )
    )
    view.set_feedback_message("Post sparad, men behöver ses över.")
    root.update_idletasks()

    view.system_combobox.set("Layered Radio")
    view.system_combobox.event_generate("<<ComboboxSelected>>")
    view.path_comboboxes[0].set("Reservnät")
    view.path_comboboxes[0].event_generate("<<ComboboxSelected>>")
    view.apply_filters_button.invoke()
    view.clear_filters_button.invoke()
    view._handle_sort_requested("from")
    view.log_table.selection_set(("7",))
    view.log_table.event_generate("<<TreeviewSelect>>")
    root.update_idletasks()
    view.open_selected_button.invoke()
    view.edit_selected_button.invoke()
    view.delete_selected_button.invoke()
    view.swap_button.invoke()
    view.clear_button.invoke()
    view.save_button.invoke()

    return {
        "events": events,
        "form_data": view.get_form_data(),
        "log_filter_data": view.get_log_filter_data(),
        "feedback_text": view.entry_hint_label.cget("text"),
        "entry_section_text": view.entry_section.cget("text"),
        "save_button_text": view.save_button.cget("text"),
        "clear_button_text": view.clear_button.cget("text"),
        "table_values": view.log_table.item("7", "values"),
        "table_tags": view.log_table.item("7", "tags"),
        "selected_items": view.log_table.selection(),
        "visible_path_labels": [
            label.cget("text")
            for index, label in enumerate(view.path_labels)
            if view._path_label_to_value_maps[index]
        ],
        "path_display_values": [
            combobox.get()
            for index, combobox in enumerate(view.path_comboboxes)
            if view._path_label_to_value_maps[index]
        ],
        "qualifier_keys": sorted(view.qualifier_widgets.keys()),
        "forced_state": str(view.qualifier_widgets["forced"].cget("state")),
        "selected_action_states": [
            str(view.open_selected_button.cget("state")),
            str(view.edit_selected_button.cget("state")),
            str(view.delete_selected_button.cget("state")),
        ],
        "heading_texts": {
            column_name: view.log_table.heading(column_name, "text")
            for column_name in view.log_table["columns"]
        },
    }


def test_communication_tab_view_supports_presenter_read_write_render_and_callbacks(run_tk_scenario) -> None:
    result = run_tk_scenario(_scenario_use_passive_communication_view_contract)

    non_selection_events = [event for event in result["events"] if event != "select:7"]
    selection_events = [event for event in result["events"] if event == "select:7"]

    assert non_selection_events == [
        "config",
        "config",
        "apply_filters",
        "clear_filters",
        "sort:from",
        "open",
        "edit",
        "delete",
        "swap",
        "clear",
        "save",
    ]
    assert selection_events
    assert all(event == "select:7" for event in selection_events)
    assert result["form_data"] == CommunicationFormData(
        time_text="120945",
        from_field="Alpha",
        to_field="Bravo",
        message_content="Kort meddelande",
        communication_system="Layered Radio",
        communication_path=("SECONDARY", "DATA"),
        communication_qualifiers={
            "encrypted": True,
            "forced": True,
            "mode": "data",
        },
    )
    assert result["log_filter_data"] == CommunicationLogFilterData(
        time_from_text="2026-05-12 10:00",
        time_to_text="2026-05-12 11:00",
        from_text="Alpha",
        to_text="Bravo",
        system_text="Layered Radio",
        message_text="Kort",
    )
    assert result["feedback_text"] == "Post sparad, men behöver ses över."
    assert result["entry_section_text"] == "Redigera kommunikationspost"
    assert result["save_button_text"] == "Uppdatera"
    assert result["clear_button_text"] == "Avbryt redigering"
    assert result["table_values"] == (
        "SE ÖVER",
        "OGILTIG TID",
        "Alpha",
        "Bravo",
        "RA180",
        "Kort meddelande",
        "✓",
        "",
        "Operatör Ett",
    )
    assert result["table_tags"] == ("needs_review",)
    assert result["selected_items"] == ("7",)
    assert result["visible_path_labels"] == ["Nät", "Rutt"]
    assert result["path_display_values"] == ["Reservnät", "Dataväg"]
    assert result["qualifier_keys"] == ["encrypted", "forced", "mode"]
    assert result["forced_state"] == "disabled"
    assert result["selected_action_states"] == ["normal", "normal", "normal"]
    assert result["heading_texts"] == {
        "status": "Status",
        "time": "Tid",
        "from": "Från ▲",
        "to": "Till",
        "method": "Metod",
        "message": "Meddelande",
        "confirmed": "Bekr",
        "edited": "Redigerad",
        "operator": "Operatör",
    }


def _scenario_detail_dialog_contract(root: tk.Tk) -> dict[str, object]:
    host = ttk.Frame(root)
    host.grid(row=0, column=0, sticky=tk.NSEW)
    host.columnconfigure(0, weight=1)
    host.rowconfigure(0, weight=1)

    view = CommunicationTabView(host)
    view.frame.grid(row=0, column=0, sticky=tk.NSEW)
    view.show_entry_details(
        CommunicationEntryDetailState(
            title="Kommunikationspost #7",
            status_text="SE ÖVER",
            time_text="2026-05-12 10:05",
            from_text="Alpha",
            to_text="Bravo",
            method_text="RA180",
            confirmed_text="Nej",
            edited_text="Ja",
            operator_text="Operatör Ett",
            message_text="Fullständigt meddelande i detaljvyn.",
            review_notes=("Tid – kunde inte tolkas",),
        )
    )
    root.update_idletasks()

    dialog = view._detail_dialog
    assert dialog is not None
    labels = [
        widget.cget("text")
        for widget in dialog.winfo_children()[0].winfo_children()
        if isinstance(widget, ttk.Label)
    ]

    return {
        "dialog_title": dialog.title(),
        "labels": labels,
    }


def _scenario_confirm_delete_contract(root: tk.Tk) -> bool:
    host = ttk.Frame(root)
    host.grid(row=0, column=0, sticky=tk.NSEW)
    host.columnconfigure(0, weight=1)
    host.rowconfigure(0, weight=1)

    view = CommunicationTabView(host)
    view.frame.grid(row=0, column=0, sticky=tk.NSEW)
    communication_tab_view_module.messagebox.askyesno = lambda *args, **kwargs: True
    return view.confirm_delete_entry("Ta bort", "Fråga")


def test_communication_tab_view_shows_detail_dialog_and_delete_confirmation(run_tk_scenario) -> None:
    result = run_tk_scenario(_scenario_detail_dialog_contract)

    assert result["dialog_title"] == "Kommunikationspost #7"
    assert "Meddelande" in result["labels"]
    assert run_tk_scenario(_scenario_confirm_delete_contract) is True


def _scenario_tab_navigation_contract(root: tk.Tk) -> dict[str, object]:
    host = ttk.Frame(root)
    host.grid(row=0, column=0, sticky=tk.NSEW)
    host.columnconfigure(0, weight=1)
    host.rowconfigure(0, weight=1)

    view = CommunicationTabView(host)
    view.frame.grid(row=0, column=0, sticky=tk.NSEW)
    view.render_form_state(
        CommunicationFormState(
            system_choices=("Layered Radio",),
            selected_system="Layered Radio",
            path_fields=(
                CommunicationPathFieldState(
                    label="Nät",
                    options=(
                        CommunicationPathChoice(value="PRIMARY", label="Primärnät"),
                        CommunicationPathChoice(value="SECONDARY", label="Reservnät"),
                    ),
                    selected_value="PRIMARY",
                ),
                CommunicationPathFieldState(
                    label="Rutt",
                    options=(
                        CommunicationPathChoice(value="VOICE", label="Talväg"),
                        CommunicationPathChoice(value="DATA", label="Dataväg"),
                    ),
                    selected_value="DATA",
                ),
            ),
            qualifier_fields=(
                CommunicationQualifierFieldState(
                    qualifier_key="encrypted",
                    label="Krypterad",
                    field_type="boolean",
                    value=True,
                    visible=True,
                ),
                CommunicationQualifierFieldState(
                    qualifier_key="mode",
                    label="Driftläge",
                    field_type="enum",
                    value="data",
                    visible=True,
                    valid_values=("voice", "data"),
                ),
                CommunicationQualifierFieldState(
                    qualifier_key="forced",
                    label="Låst läge",
                    field_type="boolean",
                    value=True,
                    visible=True,
                    read_only=True,
                ),
            ),
        )
    )
    view.render_editor_state(
        CommunicationEditorState(
            selection_actions_enabled=True,
        )
    )
    root.update_idletasks()

    view._is_tab_stop = staticmethod(
        lambda widget: (str(widget.cget("state")) if "state" in widget.keys() else "normal") != "disabled"
    )

    named_widgets = {
        "time": view.time_entry,
        "from": view.from_entry,
        "swap": view.swap_button,
        "to": view.to_entry,
        "system": view.system_combobox,
        "path_0": view.path_comboboxes[0],
        "path_1": view.path_comboboxes[1],
        "encrypted": view.qualifier_widgets["encrypted"],
        "mode": view.qualifier_widgets["mode"],
        "message": view.message_text,
        "clear": view.clear_button,
        "save": view.save_button,
        "filter_time_from": view.filter_time_from_entry,
        "filter_time_to": view.filter_time_to_entry,
        "filter_from": view.filter_from_entry,
        "filter_to": view.filter_to_entry,
        "filter_system": view.filter_system_combobox,
        "filter_text": view.filter_text_entry,
        "apply_filters": view.apply_filters_button,
        "clear_filters": view.clear_filters_button,
        "open_selected": view.open_selected_button,
        "edit_selected": view.edit_selected_button,
        "delete_selected": view.delete_selected_button,
        "configure_columns": view.configure_columns_button,
        "log_table": view.log_table,
    }
    traversal_order = [
        name for name, widget in named_widgets.items() if widget in view._get_tab_traversal_widgets()
    ]

    move_calls: list[tuple[str, bool]] = []

    def _record_move_focus(current_widget: tk.Misc, *, forward: bool) -> None:
        for name, widget in named_widgets.items():
            if widget is current_widget:
                move_calls.append((name, forward))
                return
        move_calls.append(("unknown", forward))

    view._move_focus = _record_move_focus
    forward_result = view._handle_forward_tab_navigation(
        cast(tk.Event[tk.Misc], cast(object, SimpleNamespace(widget=view.message_text)))
    )
    reverse_result = view._handle_reverse_tab_navigation(
        cast(tk.Event[tk.Misc], cast(object, SimpleNamespace(widget=view.message_text)))
    )

    return {
        "traversal_order": traversal_order,
        "forward_result": forward_result,
        "reverse_result": reverse_result,
        "move_calls": move_calls,
    }


def test_communication_tab_view_tab_navigation_follows_visual_order_and_message_is_not_a_tab_trap(
    run_tk_scenario,
) -> None:
    result = run_tk_scenario(_scenario_tab_navigation_contract)

    assert result["traversal_order"] == [
        "time",
        "from",
        "swap",
        "to",
        "system",
        "path_0",
        "path_1",
        "encrypted",
        "mode",
        "message",
        "clear",
        "save",
        "filter_time_from",
        "filter_time_to",
        "filter_from",
        "filter_to",
        "filter_system",
        "filter_text",
        "apply_filters",
        "clear_filters",
        "open_selected",
        "edit_selected",
        "delete_selected",
        "configure_columns",
        "log_table",
    ]
    assert result["forward_result"] == "break"
    assert result["reverse_result"] == "break"
    assert result["move_calls"] == [("message", True), ("message", False)]



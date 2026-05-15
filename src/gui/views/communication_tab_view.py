"""Production-owned structural Communication tab scaffold.

This view intentionally stops at the visible layout seam needed by the first
Communication-tab story: entry form region, filter region, and log/table host.
Presenter behavior, configuration-driven interaction, and repository-backed data
loading follow in later stories.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from src.gui.presenters.communication_presenter import (
        CommunicationEditorState,
        CommunicationFormData,
        CommunicationFormState,
        CommunicationEntryDetailState,
        CommunicationLogFilterData,
        CommunicationLogState,
        CommunicationQualifierFieldState,
    )


class CommunicationTabView:
    """Render the first passive Communication-tab scaffold."""

    _DEFAULT_FEEDBACK_TEXT = "Formbeteende kopplas in i senare stories."
    _MAX_VISIBLE_PATH_LEVELS = 3
    _LOG_COLUMN_HEADINGS = {
        "status": "Status",
        "time": "Tid",
        "from": "Från",
        "to": "Till",
        "method": "Metod",
        "message": "Meddelande",
        "confirmed": "Bekr",
        "edited": "Redigerad",
        "operator": "Operatör",
    }

    def __init__(self, parent: tk.Misc) -> None:
        self._config_change_handler: Callable[[], None] | None = None
        self._apply_filters_handler: Callable[[], None] | None = None
        self._clear_filters_handler: Callable[[], None] | None = None
        self._open_selected_handler: Callable[[], None] | None = None
        self._edit_selected_handler: Callable[[], None] | None = None
        self._delete_selected_handler: Callable[[], None] | None = None
        self._sort_requested_handler: Callable[[str], None] | None = None
        self._selection_changed_handler: Callable[[int | None], None] | None = None
        self._suppress_config_change_notifications = False
        self._suppress_selection_notifications = False
        self._detail_dialog: tk.Toplevel | None = None
        self.path_field_frames: list[ttk.Frame] = []
        self._path_label_to_value_maps: list[dict[str, str]] = []
        self._path_value_to_label_maps: list[dict[str, str]] = []
        self._qualifier_variables: dict[str, tk.Variable] = {}
        self.qualifier_widgets: dict[str, tk.Widget] = {}
        self._static_tab_order_widgets: list[tk.Misc] = []

        self.frame = ttk.Frame(parent, padding=16)
        self.frame.columnconfigure(0, weight=1)
        self.frame.rowconfigure(1, weight=1)

        self.entry_section = ttk.LabelFrame(self.frame, text="Ny kommunikationspost", padding=12)
        self.entry_section.grid(row=0, column=0, sticky=tk.EW, pady=(0, 16))
        self.entry_section.columnconfigure(0, weight=1)
        self.entry_section.rowconfigure(1, weight=1)

        self.metadata_frame = ttk.Frame(self.entry_section)
        self.metadata_frame.grid(row=0, column=0, sticky=tk.EW, pady=(0, 8))
        self.metadata_frame.columnconfigure(2, weight=1)

        self.time_field_frame = ttk.Frame(self.metadata_frame)
        self.time_field_frame.grid(row=0, column=0, sticky=tk.W, padx=(0, 16))
        self.time_label = ttk.Label(self.time_field_frame, text="Tid")
        self.time_label.grid(row=0, column=0, sticky=tk.W, pady=(0, 4))
        self.time_entry = ttk.Entry(self.time_field_frame, width=10)
        self.time_entry.grid(row=1, column=0, sticky=tk.W)

        self.route_section = ttk.Frame(self.metadata_frame)
        self.route_section.grid(row=0, column=2, sticky=tk.EW, padx=(16, 0))
        self.route_section.columnconfigure(0, weight=1)

        self.route_controls_frame = ttk.Frame(self.route_section)
        self.route_controls_frame.grid(row=0, column=0, sticky=tk.EW)
        self.route_controls_frame.columnconfigure(0, weight=2)
        for column_index in range(1, self._MAX_VISIBLE_PATH_LEVELS + 1):
            self.route_controls_frame.columnconfigure(column_index, weight=1)
        self.route_controls_frame.columnconfigure(self._MAX_VISIBLE_PATH_LEVELS + 1, weight=2)

        self.system_field_frame = ttk.Frame(self.route_controls_frame)
        self.system_field_frame.grid(row=0, column=0, sticky=tk.EW, padx=(0, 8))
        self.system_field_frame.columnconfigure(0, weight=1)
        self.system_label = ttk.Label(self.system_field_frame, text="System")
        self.system_label.grid(row=0, column=0, sticky=tk.W, pady=(0, 4))
        self.system_combobox = ttk.Combobox(self.system_field_frame, values=(), state="readonly")
        self.system_combobox.grid(row=1, column=0, sticky=tk.EW)

        self.participants_frame = ttk.Frame(self.metadata_frame)
        self.participants_frame.grid(row=0, column=1, sticky=tk.W)

        self.from_field_frame = ttk.Frame(self.participants_frame)
        self.from_field_frame.grid(row=0, column=0, sticky=tk.W)
        self.from_label = ttk.Label(self.from_field_frame, text="Från")
        self.from_label.grid(row=0, column=0, sticky=tk.W, pady=(0, 4))
        self.from_entry = ttk.Entry(self.from_field_frame, width=8)
        self.from_entry.grid(row=1, column=0, sticky=tk.W)

        self.swap_button = ttk.Button(self.participants_frame, text="⇄", width=3)
        self.swap_button.grid(row=0, column=1, rowspan=2, sticky=tk.S, padx=(10, 10))

        self.to_field_frame = ttk.Frame(self.participants_frame)
        self.to_field_frame.grid(row=0, column=2, sticky=tk.W)
        self.to_label = ttk.Label(self.to_field_frame, text="Till")
        self.to_label.grid(row=0, column=0, sticky=tk.W, pady=(0, 4))
        self.to_entry = ttk.Entry(self.to_field_frame, width=8)
        self.to_entry.grid(row=1, column=0, sticky=tk.W)

        self.path_labels: list[ttk.Label] = []
        self.path_comboboxes: list[ttk.Combobox] = []
        for column_index in range(self._MAX_VISIBLE_PATH_LEVELS):
            path_field_frame = ttk.Frame(self.route_controls_frame)
            path_field_frame.grid(row=0, column=column_index + 1, sticky=tk.EW, padx=(0, 8))
            path_field_frame.columnconfigure(0, weight=1)
            path_field_frame.grid_remove()
            self.path_field_frames.append(path_field_frame)

            label = ttk.Label(path_field_frame, text=f"Val {column_index + 1}")
            label.grid(row=0, column=0, sticky=tk.W, pady=(0, 4))
            self.path_labels.append(label)

            combobox = ttk.Combobox(path_field_frame, values=(), state="readonly")
            combobox.grid(row=1, column=0, sticky=tk.EW)
            self.path_comboboxes.append(combobox)
            self._path_label_to_value_maps.append({})
            self._path_value_to_label_maps.append({})

        self.qualifier_section = ttk.Frame(self.route_controls_frame)
        self.qualifier_section.grid(row=0, column=self._MAX_VISIBLE_PATH_LEVELS + 1, sticky=tk.NW)
        self.qualifier_section.columnconfigure(0, weight=1)
        self.qualifier_section_label = ttk.Label(self.qualifier_section, text="Egenskaper")
        self.qualifier_section_label.grid(row=0, column=0, sticky=tk.W, pady=(0, 4))
        self.qualifier_section.grid_remove()

        self.message_field_frame = ttk.Frame(self.entry_section)
        self.message_field_frame.grid(row=1, column=0, sticky=tk.NSEW, pady=(0, 8))
        self.message_field_frame.columnconfigure(0, weight=1)
        self.message_field_frame.rowconfigure(1, weight=1)
        self.message_label = ttk.Label(self.message_field_frame, text="Meddelande")
        self.message_label.grid(row=0, column=0, sticky=tk.W, pady=(0, 4))
        self.message_text = tk.Text(self.message_field_frame, height=4, wrap="word")
        self.message_text.grid(row=1, column=0, sticky=tk.NSEW)
        self.message_scrollbar = ttk.Scrollbar(
            self.message_field_frame,
            orient="vertical",
            command=self.message_text.yview,
        )
        self.message_scrollbar.grid(row=1, column=1, sticky=tk.NS, padx=(8, 0))
        self.message_text.configure(yscrollcommand=self.message_scrollbar.set)

        self.entry_actions_frame = ttk.Frame(self.entry_section)
        self.entry_actions_frame.grid(row=2, column=0, sticky=tk.EW, pady=(2, 0))
        self.entry_actions_frame.columnconfigure(0, weight=1)
        self.entry_hint_label = ttk.Label(
            self.entry_actions_frame,
            text=self._DEFAULT_FEEDBACK_TEXT,
            anchor="w",
        )
        self.entry_hint_label.grid(row=0, column=0, sticky=tk.W)
        self.clear_button = ttk.Button(self.entry_actions_frame, text="Rensa")
        self.clear_button.grid(row=0, column=1, sticky=tk.E, padx=(8, 0))
        self.save_button = ttk.Button(self.entry_actions_frame, text="Spara")
        self.save_button.grid(row=0, column=2, sticky=tk.E, padx=(8, 0))

        self.log_section = ttk.LabelFrame(self.frame, text="Kommunikationslogg", padding=12)
        self.log_section.grid(row=1, column=0, sticky=tk.NSEW)
        self.log_section.columnconfigure(0, weight=1)
        self.log_section.rowconfigure(2, weight=1)

        self.log_hint_label = ttk.Label(
            self.log_section,
            text="Tabellinnehåll och interaktion kopplas in i senare stories.",
            anchor="w",
        )
        self.log_hint_label.grid(row=0, column=0, sticky=tk.W)

        self.log_controls_frame = ttk.Frame(self.log_section)
        self.log_controls_frame.grid(row=0, column=1, sticky=tk.E, padx=(12, 0))
        self.open_selected_button = ttk.Button(self.log_controls_frame, text="Öppna", state="disabled")
        self.open_selected_button.grid(row=0, column=0, sticky=tk.E)
        self.edit_selected_button = ttk.Button(self.log_controls_frame, text="Redigera", state="disabled")
        self.edit_selected_button.grid(row=0, column=1, sticky=tk.E, padx=(8, 0))
        self.delete_selected_button = ttk.Button(self.log_controls_frame, text="Ta bort", state="disabled")
        self.delete_selected_button.grid(row=0, column=2, sticky=tk.E, padx=(8, 0))
        self.configure_columns_button = ttk.Button(self.log_controls_frame, text="Kolumner...")
        self.configure_columns_button.grid(row=0, column=3, sticky=tk.E, padx=(8, 0))

        self.filter_section = ttk.LabelFrame(self.log_section, text="Filter", padding=8)
        self.filter_section.grid(row=1, column=0, columnspan=2, sticky=tk.EW, pady=(10, 0))
        self.filter_section.columnconfigure(0, weight=1)

        self.filter_fields_frame = ttk.Frame(self.filter_section)
        self.filter_fields_frame.grid(row=0, column=0, sticky=tk.EW)
        self.filter_fields_frame.columnconfigure(5, weight=1)

        self.filter_time_from_field_frame = ttk.Frame(self.filter_fields_frame)
        self.filter_time_from_field_frame.grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        self.filter_time_from_label = ttk.Label(self.filter_time_from_field_frame, text="Tid från")
        self.filter_time_from_label.grid(row=0, column=0, sticky=tk.W, pady=(0, 4))
        self.filter_time_from_entry = ttk.Entry(self.filter_time_from_field_frame, width=16)
        self.filter_time_from_entry.grid(row=1, column=0, sticky=tk.W)

        self.filter_time_to_field_frame = ttk.Frame(self.filter_fields_frame)
        self.filter_time_to_field_frame.grid(row=0, column=1, sticky=tk.W, padx=(0, 10))
        self.filter_time_to_label = ttk.Label(self.filter_time_to_field_frame, text="Tid till")
        self.filter_time_to_label.grid(row=0, column=0, sticky=tk.W, pady=(0, 4))
        self.filter_time_to_entry = ttk.Entry(self.filter_time_to_field_frame, width=16)
        self.filter_time_to_entry.grid(row=1, column=0, sticky=tk.W)

        self.filter_from_field_frame = ttk.Frame(self.filter_fields_frame)
        self.filter_from_field_frame.grid(row=0, column=2, sticky=tk.W, padx=(0, 10))
        self.filter_from_label = ttk.Label(self.filter_from_field_frame, text="Från")
        self.filter_from_label.grid(row=0, column=0, sticky=tk.W, pady=(0, 4))
        self.filter_from_entry = ttk.Entry(self.filter_from_field_frame, width=12)
        self.filter_from_entry.grid(row=1, column=0, sticky=tk.W)

        self.filter_to_field_frame = ttk.Frame(self.filter_fields_frame)
        self.filter_to_field_frame.grid(row=0, column=3, sticky=tk.W, padx=(0, 10))
        self.filter_to_label = ttk.Label(self.filter_to_field_frame, text="Till")
        self.filter_to_label.grid(row=0, column=0, sticky=tk.W, pady=(0, 4))
        self.filter_to_entry = ttk.Entry(self.filter_to_field_frame, width=12)
        self.filter_to_entry.grid(row=1, column=0, sticky=tk.W)

        self.filter_system_field_frame = ttk.Frame(self.filter_fields_frame)
        self.filter_system_field_frame.grid(row=0, column=4, sticky=tk.W, padx=(0, 10))
        self.filter_system_label = ttk.Label(self.filter_system_field_frame, text="System")
        self.filter_system_label.grid(row=0, column=0, sticky=tk.W, pady=(0, 4))
        self.filter_system_combobox = ttk.Combobox(self.filter_system_field_frame, values=(), width=18)
        self.filter_system_combobox.grid(row=1, column=0, sticky=tk.W)

        self.filter_text_field_frame = ttk.Frame(self.filter_fields_frame)
        self.filter_text_field_frame.grid(row=0, column=5, sticky=tk.EW, padx=(0, 10))
        self.filter_text_field_frame.columnconfigure(0, weight=1)
        self.filter_text_label = ttk.Label(self.filter_text_field_frame, text="Text")
        self.filter_text_label.grid(row=0, column=0, sticky=tk.W, pady=(0, 4))
        self.filter_text_entry = ttk.Entry(self.filter_text_field_frame, width=18)
        self.filter_text_entry.grid(row=1, column=0, sticky=tk.EW)

        self.filter_actions_frame = ttk.Frame(self.filter_section)
        self.filter_actions_frame.grid(row=0, column=1, sticky=tk.SE, padx=(12, 0))
        self.apply_filters_button = ttk.Button(self.filter_actions_frame, text="Filtrera")
        self.apply_filters_button.grid(row=0, column=0, sticky=tk.E, pady=(0, 8))
        self.clear_filters_button = ttk.Button(self.filter_actions_frame, text="Rensa filter")
        self.clear_filters_button.grid(row=1, column=0, sticky=tk.E)

        self.log_table = ttk.Treeview(
            self.log_section,
            columns=("status", "time", "from", "to", "method", "message", "confirmed", "edited", "operator"),
            show="headings",
            height=10,
        )
        self.log_table.grid(row=2, column=0, sticky=tk.NSEW, pady=(10, 0))
        self.log_vertical_scrollbar = ttk.Scrollbar(
            self.log_section,
            orient="vertical",
            command=self.log_table.yview,
        )
        self.log_vertical_scrollbar.grid(row=2, column=1, sticky=tk.NS, pady=(10, 0), padx=(8, 0))
        self.log_horizontal_scrollbar = ttk.Scrollbar(
            self.log_section,
            orient="horizontal",
            command=self.log_table.xview,
        )
        self.log_horizontal_scrollbar.grid(row=3, column=0, sticky=tk.EW, pady=(8, 0))
        self.log_table.configure(
            yscrollcommand=self.log_vertical_scrollbar.set,
            xscrollcommand=self.log_horizontal_scrollbar.set,
        )

        self._configure_log_table_columns()
        self.log_table.tag_configure("needs_review", background="#fff0b3")
        self._initialize_tab_navigation()

    def set_save_handler(self, callback: Callable[[], None]) -> None:
        """Bind the save button to the presenter-owned save callback."""
        self.save_button.configure(command=callback)

    def set_clear_handler(self, callback: Callable[[], None]) -> None:
        """Bind the clear button to the presenter-owned clear callback."""
        self.clear_button.configure(command=callback)

    def set_swap_handler(self, callback: Callable[[], None]) -> None:
        """Bind the swap button to the presenter-owned swap callback."""
        self.swap_button.configure(command=callback)

    def set_config_change_handler(self, callback: Callable[[], None]) -> None:
        """Bind system/path selection changes to one presenter-owned callback."""
        self._config_change_handler = callback
        self.system_combobox.bind("<<ComboboxSelected>>", self._handle_config_selection_changed)
        for combobox in self.path_comboboxes:
            combobox.bind("<<ComboboxSelected>>", self._handle_config_selection_changed)

    def set_log_interaction_handlers(
        self,
        *,
        on_apply_filters: Callable[[], None],
        on_clear_filters: Callable[[], None],
        on_open_selected: Callable[[], None],
        on_edit_selected: Callable[[], None],
        on_delete_selected: Callable[[], None],
        on_sort_requested: Callable[[str], None],
        on_selection_changed: Callable[[int | None], None],
    ) -> None:
        """Bind log-filter, selected-entry, sort, and selection interactions."""
        self._apply_filters_handler = on_apply_filters
        self._clear_filters_handler = on_clear_filters
        self._open_selected_handler = on_open_selected
        self._edit_selected_handler = on_edit_selected
        self._delete_selected_handler = on_delete_selected
        self._sort_requested_handler = on_sort_requested
        self._selection_changed_handler = on_selection_changed
        self.apply_filters_button.configure(command=on_apply_filters)
        self.clear_filters_button.configure(command=on_clear_filters)
        self.open_selected_button.configure(command=on_open_selected)
        self.edit_selected_button.configure(command=on_edit_selected)
        self.delete_selected_button.configure(command=on_delete_selected)
        for widget in (
            self.filter_time_from_entry,
            self.filter_time_to_entry,
            self.filter_from_entry,
            self.filter_to_entry,
            self.filter_system_combobox,
            self.filter_text_entry,
        ):
            widget.bind("<Return>", self._handle_filter_submit_requested, add="+")
        self.log_table.bind("<<TreeviewSelect>>", self._handle_log_selection_changed)
        self.log_table.bind("<Return>", self._handle_open_selected_requested, add="+")

    def get_log_filter_data(self) -> CommunicationLogFilterData:
        """Return the current Communication log filter submission payload."""
        from src.gui.presenters.communication_presenter import CommunicationLogFilterData

        return CommunicationLogFilterData(
            time_from_text=self.filter_time_from_entry.get(),
            time_to_text=self.filter_time_to_entry.get(),
            from_text=self.filter_from_entry.get(),
            to_text=self.filter_to_entry.get(),
            system_text=self.filter_system_combobox.get(),
            message_text=self.filter_text_entry.get(),
        )

    def get_form_data(self) -> CommunicationFormData:
        """Return the current Communication form data for the presenter."""
        from src.gui.presenters.communication_presenter import CommunicationFormData

        return CommunicationFormData(
            time_text=self.time_entry.get(),
            from_field=self.from_entry.get(),
            to_field=self.to_entry.get(),
            message_content=self.message_text.get("1.0", tk.END).rstrip("\n"),
            communication_system=self.system_combobox.get(),
            communication_path=self._read_path_values(),
            communication_qualifiers=self._read_qualifier_values(),
        )

    def set_form_data(self, form_data: CommunicationFormData) -> None:
        """Render the presenter-provided Communication form state."""
        self._suppress_config_change_notifications = True
        try:
            self._replace_entry_value(self.time_entry, form_data.time_text)
            self._replace_entry_value(self.from_entry, form_data.from_field)
            self._replace_entry_value(self.to_entry, form_data.to_field)
            self.system_combobox.set(form_data.communication_system)
            self._write_path_values(form_data.communication_path)
            self._write_qualifier_values(form_data.communication_qualifiers)
            self.message_text.delete("1.0", tk.END)
            if form_data.message_content:
                self.message_text.insert("1.0", form_data.message_content)
        finally:
            self._suppress_config_change_notifications = False

    def render_form_state(self, form_state: CommunicationFormState) -> None:
        """Render config-driven system/path/qualifier structure from the presenter."""
        self._suppress_config_change_notifications = True
        try:
            self.system_combobox.configure(values=form_state.system_choices)
            self._render_path_fields(form_state.path_fields)
            self._render_qualifier_fields(form_state.qualifier_fields)
        finally:
            self._suppress_config_change_notifications = False

    def render_editor_state(self, editor_state: CommunicationEditorState) -> None:
        """Render whether the Communication form is in create or edit mode."""
        self.entry_section.configure(text=editor_state.section_title)
        self.save_button.configure(text=editor_state.save_button_text)
        self.clear_button.configure(text=editor_state.clear_button_text)
        selected_state = "normal" if editor_state.selection_actions_enabled else "disabled"
        self.open_selected_button.configure(state=selected_state)
        self.edit_selected_button.configure(state=selected_state)
        self.delete_selected_button.configure(state=selected_state)

    def render_log_state(self, log_state: CommunicationLogState) -> None:
        """Render the current presenter-provided Communication log state."""
        self.filter_system_combobox.configure(values=log_state.system_filter_choices)
        self._replace_entry_value(self.filter_time_from_entry, log_state.filter_data.time_from_text)
        self._replace_entry_value(self.filter_time_to_entry, log_state.filter_data.time_to_text)
        self._replace_entry_value(self.filter_from_entry, log_state.filter_data.from_text)
        self._replace_entry_value(self.filter_to_entry, log_state.filter_data.to_text)
        self.filter_system_combobox.set(log_state.filter_data.system_text)
        self._replace_entry_value(self.filter_text_entry, log_state.filter_data.message_text)
        self._configure_log_table_columns(
            sort_column=log_state.sort_column,
            sort_descending=log_state.sort_descending,
        )

        self._suppress_selection_notifications = True
        try:
            for item_id in self.log_table.get_children():
                self.log_table.delete(item_id)

            selected_item_id = ""
            for row in log_state.rows:
                tags = ("needs_review",) if row.needs_review else ()
                item_id = str(row.entry_id)
                self.log_table.insert(
                    "",
                    "end",
                    iid=item_id,
                    values=(
                        row.status_text,
                        row.time_text,
                        row.from_text,
                        row.to_text,
                        row.method_text,
                        row.message_text,
                        row.confirmed_text,
                        row.edited_text,
                        row.operator_text,
                    ),
                    tags=tags,
                )
                if row.is_selected:
                    selected_item_id = item_id

            if selected_item_id:
                self.log_table.selection_set((selected_item_id,))
                self.log_table.focus(selected_item_id)
                self.log_table.see(selected_item_id)
            else:
                self.log_table.selection_set(())
                first_item = self.log_table.get_children()
                if first_item:
                    self.log_table.focus(first_item[0])
        finally:
            self._suppress_selection_notifications = False

    def set_feedback_message(self, message: str, *, is_error: bool = False) -> None:
        """Show coarse presenter feedback inside the Communication form area."""
        del is_error
        self.entry_hint_label.configure(text=message or self._DEFAULT_FEEDBACK_TEXT)

    def show_warning_dialog(self, title: str, message: str) -> None:
        """Show the soft-warning acknowledgement dialog for presenter saves."""
        messagebox.showwarning(title, message, parent=self.frame)

    def show_entry_details(self, detail_state: CommunicationEntryDetailState) -> None:
        """Show a simple read-only detail dialog for the selected Communication entry."""
        if self._detail_dialog is not None and self._detail_dialog.winfo_exists():
            self._detail_dialog.destroy()

        dialog = tk.Toplevel(self.frame)
        self._detail_dialog = dialog
        dialog.title(detail_state.title)
        dialog.transient(self.frame.winfo_toplevel())

        container = ttk.Frame(dialog, padding=12)
        container.pack(fill=tk.BOTH, expand=True)

        for label_text, value_text in (
            ("Status", detail_state.status_text),
            ("Tid", detail_state.time_text),
            ("Från", detail_state.from_text),
            ("Till", detail_state.to_text),
            ("Metod", detail_state.method_text),
            ("Bekräftad", detail_state.confirmed_text),
            ("Redigerad", detail_state.edited_text),
            ("Operatör", detail_state.operator_text),
        ):
            if not value_text:
                continue
            row = ttk.Frame(container)
            row.pack(fill=tk.X, anchor=tk.W, pady=(0, 4))
            ttk.Label(row, text=f"{label_text}:").pack(side=tk.LEFT)
            ttk.Label(row, text=value_text).pack(side=tk.LEFT, padx=(6, 0))

        if detail_state.review_notes:
            review_frame = ttk.LabelFrame(container, text="Behöver ses över", padding=8)
            review_frame.pack(fill=tk.X, expand=False, pady=(4, 8))
            for review_note in detail_state.review_notes:
                ttk.Label(review_frame, text=f"• {review_note}").pack(anchor=tk.W)

        ttk.Label(container, text="Meddelande").pack(anchor=tk.W, pady=(4, 4))
        message_frame = ttk.Frame(container)
        message_frame.pack(fill=tk.BOTH, expand=True)
        message_text = tk.Text(message_frame, height=8, wrap="word")
        message_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        message_scrollbar = ttk.Scrollbar(message_frame, orient="vertical", command=message_text.yview)
        message_scrollbar.pack(side=tk.RIGHT, fill=tk.Y, padx=(8, 0))
        message_text.configure(yscrollcommand=message_scrollbar.set)
        if detail_state.message_text:
            message_text.insert("1.0", detail_state.message_text)
        message_text.configure(state="disabled")

        button_frame = ttk.Frame(container)
        button_frame.pack(fill=tk.X, pady=(12, 0))
        ttk.Button(button_frame, text="Stäng", command=dialog.destroy).pack(side=tk.RIGHT)

    def confirm_delete_entry(self, title: str, message: str) -> bool:
        """Ask the operator to confirm deleting the selected Communication entry."""
        return bool(messagebox.askyesno(title, message, parent=self.frame))

    def _configure_log_table_columns(self, *, sort_column: str = "time", sort_descending: bool = True) -> None:
        widths = {
            "status": 90,
            "time": 100,
            "from": 120,
            "to": 120,
            "method": 140,
            "message": 320,
            "confirmed": 60,
            "edited": 90,
            "operator": 120,
        }
        for column_name in self.log_table["columns"]:
            heading_text = self._LOG_COLUMN_HEADINGS[column_name]
            if column_name == sort_column:
                direction_indicator = "▼" if sort_descending else "▲"
                heading_text = f"{heading_text} {direction_indicator}"
            self.log_table.heading(
                column_name,
                text=heading_text,
                command=lambda selected_column=column_name: self._handle_sort_requested(selected_column),
            )
            self.log_table.column(column_name, width=widths[column_name], minwidth=60, stretch=True)

    def _initialize_tab_navigation(self) -> None:
        self._static_tab_order_widgets = [
            self.time_entry,
            self.from_entry,
            self.swap_button,
            self.to_entry,
            self.system_combobox,
            self.message_text,
            self.clear_button,
            self.save_button,
            self.filter_time_from_entry,
            self.filter_time_to_entry,
            self.filter_from_entry,
            self.filter_to_entry,
            self.filter_system_combobox,
            self.filter_text_entry,
            self.apply_filters_button,
            self.clear_filters_button,
            self.open_selected_button,
            self.edit_selected_button,
            self.delete_selected_button,
            self.configure_columns_button,
            self.log_table,
        ]
        for widget in self._static_tab_order_widgets:
            self._bind_tab_navigation(widget)
        for combobox in self.path_comboboxes:
            self._bind_tab_navigation(combobox)

    def _bind_tab_navigation(self, widget: tk.Misc) -> None:
        widget.bind("<Tab>", self._handle_forward_tab_navigation, add="+")
        widget.bind("<Shift-Tab>", self._handle_reverse_tab_navigation, add="+")
        widget.bind("<ISO_Left_Tab>", self._handle_reverse_tab_navigation, add="+")

    def _handle_forward_tab_navigation(self, event: tk.Event[tk.Misc]) -> str:
        self._move_focus(event.widget, forward=True)
        return "break"

    def _handle_reverse_tab_navigation(self, event: tk.Event[tk.Misc]) -> str:
        self._move_focus(event.widget, forward=False)
        return "break"

    def _move_focus(self, current_widget: tk.Misc, *, forward: bool) -> None:
        traversal_widgets = self._get_tab_traversal_widgets()
        if not traversal_widgets:
            return

        try:
            current_index = traversal_widgets.index(current_widget)
        except ValueError:
            target_widget = traversal_widgets[0 if forward else -1]
        else:
            step = 1 if forward else -1
            target_widget = traversal_widgets[(current_index + step) % len(traversal_widgets)]

        target_widget.focus_set()
        if isinstance(target_widget, tk.Text):
            target_widget.mark_set(tk.INSERT, target_widget.index(tk.INSERT))
            target_widget.see(tk.INSERT)

    def _get_tab_traversal_widgets(self) -> list[tk.Misc]:
        traversal_widgets: list[tk.Misc] = []
        for widget in self._static_tab_order_widgets[:5]:
            if self._is_tab_stop(widget):
                traversal_widgets.append(widget)

        for combobox in self.path_comboboxes:
            if self._is_tab_stop(combobox):
                traversal_widgets.append(combobox)

        for widget in self.qualifier_widgets.values():
            if self._is_tab_stop(widget):
                traversal_widgets.append(widget)

        for widget in self._static_tab_order_widgets[5:]:
            if self._is_tab_stop(widget):
                traversal_widgets.append(widget)

        return traversal_widgets

    @staticmethod
    def _is_tab_stop(widget: tk.Misc) -> bool:
        if not widget.winfo_exists() or not widget.winfo_viewable():
            return False
        state = str(widget.cget("state")) if "state" in widget.keys() else "normal"
        return state != "disabled"

    @staticmethod
    def _replace_entry_value(widget: ttk.Entry, value: str) -> None:
        widget.delete(0, tk.END)
        if value:
            widget.insert(0, value)

    def _render_path_fields(self, path_fields: Sequence[object]) -> None:
        from src.gui.presenters.communication_presenter import CommunicationPathFieldState

        typed_path_fields = tuple(
            path_field
            for path_field in path_fields
            if isinstance(path_field, CommunicationPathFieldState)
        )
        for index, (path_field_frame, label_widget, combobox_widget) in enumerate(
            zip(self.path_field_frames, self.path_labels, self.path_comboboxes)
        ):
            if index >= len(typed_path_fields):
                path_field_frame.grid_remove()
                combobox_widget.set("")
                combobox_widget.configure(values=())
                self._path_label_to_value_maps[index] = {}
                self._path_value_to_label_maps[index] = {}
                continue

            path_field = typed_path_fields[index]
            label_widget.configure(text=path_field.label)
            label_values = tuple(option.label for option in path_field.options)
            label_to_value = {option.label: option.value for option in path_field.options}
            value_to_label = {option.value: option.label for option in path_field.options}
            self._path_label_to_value_maps[index] = label_to_value
            self._path_value_to_label_maps[index] = value_to_label
            combobox_widget.configure(values=label_values)
            combobox_widget.set(value_to_label.get(path_field.selected_value, ""))
            path_field_frame.grid()

    def _render_qualifier_fields(
        self,
        qualifier_fields: Sequence[CommunicationQualifierFieldState],
    ) -> None:
        for child in self.qualifier_section.winfo_children():
            if child is self.qualifier_section_label:
                continue
            child.destroy()
        self._qualifier_variables = {}
        self.qualifier_widgets = {}

        visible_fields = [field for field in qualifier_fields if field.visible]
        if not visible_fields:
            self.qualifier_section.grid_remove()
            return

        self.qualifier_section.grid()
        for row_index, qualifier_field in enumerate(visible_fields):
            widget, variable = self._build_qualifier_widget(qualifier_field, row_index)
            self._qualifier_variables[qualifier_field.qualifier_key] = variable
            self.qualifier_widgets[qualifier_field.qualifier_key] = widget
            self._bind_tab_navigation(widget)

    def _build_qualifier_widget(
        self,
        qualifier_field: CommunicationQualifierFieldState,
        row_index: int,
    ) -> tuple[tk.Widget, tk.Variable]:
        if qualifier_field.field_type == "boolean":
            variable = tk.BooleanVar(value=bool(qualifier_field.value))
            widget = ttk.Checkbutton(
                self.qualifier_section,
                text=qualifier_field.label,
                variable=variable,
            )
            if qualifier_field.read_only:
                widget.configure(state="disabled")
            widget.grid(row=1, column=row_index, sticky=tk.W, padx=(0, 10))
            return widget, variable

        qualifier_field_frame = ttk.Frame(self.qualifier_section)
        qualifier_field_frame.grid(row=1, column=row_index, sticky=tk.NW, padx=(0, 10))
        qualifier_field_frame.columnconfigure(0, weight=1)
        label = ttk.Label(qualifier_field_frame, text=qualifier_field.label)
        label.grid(row=0, column=0, sticky=tk.W, pady=(0, 4))

        if qualifier_field.field_type == "enum":
            variable = tk.StringVar(value="" if qualifier_field.value is None else str(qualifier_field.value))
            widget = ttk.Combobox(
                qualifier_field_frame,
                textvariable=variable,
                values=qualifier_field.valid_values or (),
                state="readonly" if not qualifier_field.read_only else "disabled",
            )
            widget.grid(row=1, column=0, sticky=tk.EW)
            return widget, variable

        variable = tk.StringVar(value="" if qualifier_field.value is None else str(qualifier_field.value))
        widget = ttk.Entry(
            qualifier_field_frame,
            textvariable=variable,
            state="readonly" if qualifier_field.read_only else "normal",
        )
        widget.grid(row=1, column=0, sticky=tk.EW)
        return widget, variable

    def _read_path_values(self) -> tuple[str, ...]:
        selected_values: list[str] = []
        for index, combobox in enumerate(self.path_comboboxes):
            if not self._path_label_to_value_maps[index]:
                continue
            selected_label = combobox.get()
            if not selected_label:
                break
            selected_value = self._path_label_to_value_maps[index].get(selected_label)
            if selected_value is None:
                break
            selected_values.append(selected_value)
        return tuple(selected_values)

    def _write_path_values(self, selected_values: Sequence[str]) -> None:
        for index, combobox in enumerate(self.path_comboboxes):
            selected_value = selected_values[index] if index < len(selected_values) else ""
            combobox.set(self._path_value_to_label_maps[index].get(selected_value, ""))

    def _read_qualifier_values(self) -> dict[str, bool | str | None]:
        return {
            qualifier_key: variable.get()
            for qualifier_key, variable in self._qualifier_variables.items()
        }

    def _write_qualifier_values(self, qualifier_values: dict[str, bool | str | None]) -> None:
        for qualifier_key, variable in self._qualifier_variables.items():
            value = qualifier_values.get(qualifier_key)
            if isinstance(variable, tk.BooleanVar):
                variable.set(bool(value))
                continue
            variable.set("" if value is None else str(value))

    def _handle_config_selection_changed(self, _event: tk.Event[tk.Misc]) -> None:
        if self._suppress_config_change_notifications or self._config_change_handler is None:
            return
        self._config_change_handler()

    def _handle_filter_submit_requested(self, _event: tk.Event[tk.Misc]) -> str:
        if self._apply_filters_handler is not None:
            self._apply_filters_handler()
        return "break"

    def _handle_open_selected_requested(self, _event: tk.Event[tk.Misc]) -> str:
        if self._open_selected_handler is not None:
            self._open_selected_handler()
        return "break"

    def _handle_sort_requested(self, column_name: str) -> None:
        if self._sort_requested_handler is None:
            return
        self._sort_requested_handler(column_name)

    def _handle_log_selection_changed(self, _event: tk.Event[tk.Misc]) -> None:
        if self._suppress_selection_notifications or self._selection_changed_handler is None:
            return
        selection = self.log_table.selection()
        if not selection:
            self._selection_changed_handler(None)
            return
        try:
            self._selection_changed_handler(int(selection[0]))
        except ValueError:
            self._selection_changed_handler(None)


__all__ = ["CommunicationTabView"]


"""Tkinter startup dialog view for encrypted create and unlock flows.

This view deliberately stays thin: it renders presenter-provided state,
captures widget input, and exposes callback seams for a later app-shell wiring
step. Validation, secure-bootstrap decisions, and error mapping remain in the
presenter layer.
"""

from __future__ import annotations

from dataclasses import dataclass
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk
from typing import Callable

from src.db.repositories.startup_selection import (
    StartupFieldKind,
    StartupFieldName,
    StartupFieldRequirement,
)
from src.gui.presenters.startup_dialog_presenter import (
    StartupDialogMode,
    StartupDialogState,
    StartupDialogSubmission,
)

VoidCallback = Callable[[], None]


@dataclass(slots=True)
class _StartupFieldWidgets:
    """Tk widgets and variable for one backend-driven startup field."""

    requirement: StartupFieldRequirement
    row: ttk.Frame
    label: ttk.Label
    entry: ttk.Entry
    variable: tk.StringVar
    browse_button: ttk.Button | None = None


@dataclass(slots=True, frozen=True)
class StartupDialogActionCallbacks:
    """Action-oriented callbacks used by the startup dialog."""

    submit: VoidCallback | None = None
    cancel: VoidCallback | None = None
    migrate: VoidCallback | None = None
    emergency_reset: VoidCallback | None = None
    browse_key_file: VoidCallback | None = None


class StartupDialogView:
    """Render the startup dialog and expose user-entered values."""

    def __init__(
        self,
        master: tk.Misc,
        *,
        dialect_options: Sequence[str] = ("sqlite",),
    ) -> None:
        self.window = tk.Toplevel(master)
        self._minimum_width = 640
        self._minimum_height = 360
        self.window.resizable(True, True)
        self.window.minsize(self._minimum_width, self._minimum_height)

        self._action_callbacks = StartupDialogActionCallbacks()
        self._submission_changed_callback: VoidCallback | None = None
        self._field_widgets: dict[StartupFieldName, _StartupFieldWidgets] = {}
        self._visible_field_names: tuple[StartupFieldName, ...] = ()
        self._has_rendered_state = False

        self.mode_var = tk.StringVar(master=self.window, value=StartupDialogMode.CREATE.value)
        self.use_remembered_target_var = tk.BooleanVar(master=self.window, value=False)
        self.dialect_var = tk.StringVar(master=self.window)
        self.operator_var = tk.StringVar(master=self.window)
        self.status_message_var = tk.StringVar(master=self.window)
        self.error_message_var = tk.StringVar(master=self.window)
        self.managed_database_message_var = tk.StringVar(master=self.window)

        self.window.columnconfigure(0, weight=1)
        self.window.rowconfigure(0, weight=1)

        self.scrollable_content_frame = ttk.Frame(self.window)
        self.scrollable_content_frame.grid(row=0, column=0, sticky=tk.NSEW)
        self.scrollable_content_frame.columnconfigure(0, weight=1)
        self.scrollable_content_frame.rowconfigure(0, weight=1)

        self.content_canvas = tk.Canvas(
            self.scrollable_content_frame,
            highlightthickness=0,
            borderwidth=0,
        )
        self.content_canvas.grid(row=0, column=0, sticky=tk.NSEW)
        self.content_vertical_scrollbar = ttk.Scrollbar(
            self.scrollable_content_frame,
            orient="vertical",
            command=self.content_canvas.yview,
        )
        self.content_canvas.configure(yscrollcommand=self.content_vertical_scrollbar.set)

        self.container = ttk.Frame(self.content_canvas, padding=12)
        self.container.columnconfigure(0, weight=1)
        self._container_window = self.content_canvas.create_window(
            (0, 0),
            window=self.container,
            anchor="nw",
        )
        self.container.bind("<Configure>", self._handle_content_configure, add="+")
        self.content_canvas.bind("<Configure>", self._handle_canvas_configure, add="+")

        self.container.columnconfigure(0, weight=1)

        self.summary_label = ttk.Label(
            self.container,
            text="EventLog använder en apphanterad databas. Ange operatör och åtkomstuppgifter för att fortsätta.",
            wraplength=560,
            justify="left",
        )
        self.summary_label.grid(row=0, column=0, sticky=tk.EW, pady=(0, 10))

        self.user_section = ttk.LabelFrame(self.container, text="Användare", padding=12)
        self.user_section.grid(row=1, column=0, sticky=tk.EW, pady=(0, 10))
        self.user_section.columnconfigure(1, weight=1)
        self.operator_label = ttk.Label(self.user_section, text="Operatör:", width=18)
        self.operator_label.grid(row=0, column=0, sticky=tk.W, padx=(0, 8))
        self.operator_entry = ttk.Entry(self.user_section, textvariable=self.operator_var)
        self.operator_entry.grid(row=0, column=1, sticky=tk.EW)

        self.database_section = ttk.LabelFrame(self.container, text="Databas", padding=12)
        self.database_section.grid(row=2, column=0, sticky=tk.EW, pady=(0, 10))
        self.database_section.columnconfigure(0, weight=1)

        self.access_section = ttk.LabelFrame(self.container, text="Åtkomst", padding=12)
        self.access_section.grid(row=3, column=0, sticky=tk.EW, pady=(0, 8))
        self.access_section.columnconfigure(0, weight=1)

        self.managed_database_hint_label = ttk.Label(
            self.database_section,
            textvariable=self.managed_database_message_var,
            foreground="#555555",
            justify="left",
            wraplength=560,
        )
        self.managed_database_hint_label.grid(row=0, column=0, sticky=tk.EW, pady=(0, 8))
        self.managed_database_hint_label.grid_remove()

        self.dialect_row = ttk.Frame(self.database_section)
        self.dialect_row.grid(row=1, column=0, sticky=tk.EW, pady=(0, 6))
        self.dialect_row.columnconfigure(1, weight=1)
        self.dialect_label = ttk.Label(self.dialect_row, text="Databastyp:", width=18)
        self.dialect_label.grid(row=0, column=0, sticky=tk.W, padx=(0, 8))
        self.dialect_combobox = ttk.Combobox(
            self.dialect_row,
            textvariable=self.dialect_var,
            values=tuple(dialect_options),
            state="readonly",
        )
        self.dialect_combobox.grid(row=0, column=1, sticky=tk.EW)
        self.dialect_combobox.bind("<<ComboboxSelected>>", self._notify_submission_changed)

        self.database_fields_container = ttk.Frame(self.database_section)
        self.database_fields_container.grid(row=2, column=0, sticky=tk.EW)
        self.database_fields_container.columnconfigure(0, weight=1)

        self.access_fields_container = ttk.Frame(self.access_section)
        self.access_fields_container.grid(row=0, column=0, sticky=tk.EW)
        self.access_fields_container.columnconfigure(0, weight=1)

        self.password_policy_hint_label = ttk.Label(
            self.access_section,
            foreground="#555555",
            justify="left",
            wraplength=560,
        )
        self.password_policy_hint_label.grid(row=1, column=0, sticky=tk.W, pady=(0, 2))

        self.error_label = ttk.Label(
            self.container,
            textvariable=self.error_message_var,
            foreground="#b00020",
        )
        self.error_label.grid(row=4, column=0, sticky=tk.W, pady=(0, 8))
        self.error_label.grid_remove()

        self.status_label = ttk.Label(
            self.container,
            textvariable=self.status_message_var,
            foreground="#1b5e20",
        )
        self.status_label.grid(row=5, column=0, sticky=tk.W, pady=(0, 8))
        self.status_label.grid_remove()

        self.button_separator = ttk.Separator(self.window, orient="horizontal")
        self.button_separator.grid(row=1, column=0, sticky=tk.EW, pady=(4, 10))

        self.button_row = ttk.Frame(self.window, padding=(12, 0, 12, 12))
        self.button_row.grid(row=2, column=0, sticky=tk.EW)
        self.button_row.columnconfigure(1, weight=1)
        self.danger_action_frame = ttk.Frame(self.button_row, padding=(0, 2, 0, 0))
        self.danger_action_frame.grid(row=0, column=0, sticky=tk.W)
        self.primary_action_frame = ttk.Frame(self.button_row)
        self.primary_action_frame.grid(row=0, column=2, sticky=tk.E)
        reset_button_font = tkfont.nametofont("TkDefaultFont").copy()
        reset_button_font.configure(weight="bold")
        self._emergency_reset_button_font = reset_button_font
        self.emergency_reset_button = tk.Button(
            self.danger_action_frame,
            text="Nollställ",
            command=self._handle_emergency_reset,
            font=self._emergency_reset_button_font,
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
            padx=10,
            pady=5,
        )
        self.emergency_reset_button.grid(row=0, column=0, sticky=tk.W)
        self.cancel_button = ttk.Button(self.primary_action_frame, text="Avbryt", command=self._handle_cancel)
        self.migrate_button = ttk.Button(self.primary_action_frame, text="Migrera", command=self._handle_migrate)
        self.migrate_button.grid(row=0, column=0, sticky=tk.E, padx=(0, 8))
        self.migrate_button.grid_remove()
        self.cancel_button.grid(row=0, column=1, sticky=tk.E, padx=(0, 8))
        self.submit_button = ttk.Button(self.primary_action_frame, text="OK", command=self._handle_submit)
        self.submit_button.grid(row=0, column=2, sticky=tk.E)

        self.window.bind("<Return>", self._handle_submit_keypress)
        self.window.bind("<KP_Enter>", self._handle_submit_keypress)
        self.window.bind("<Configure>", self._handle_window_configure, add="+")

        self.window.protocol("WM_DELETE_WINDOW", self.handle_close_requested)
        self.window.update_idletasks()
        self._apply_responsive_geometry()

        for field_name in StartupFieldName:
            self._ensure_field_widgets(field_name)

    def render_state(self, state: StartupDialogState) -> None:
        """Render presenter-owned state into the dialog widgets."""
        self.window.title(state.title)
        self.submit_button.configure(text=state.submit_label)
        self.summary_label.configure(text=self._build_summary_text(state))
        self.mode_var.set(state.mode.value)
        self.use_remembered_target_var.set(state.uses_remembered_target)
        self.dialect_var.set(state.dialect)
        if self.operator_var.get() != state.operator:
            self.operator_var.set(state.operator)
        self._sync_state_field_value(StartupFieldName.DATABASE_PATH, state.database_path)
        self._sync_state_field_value(StartupFieldName.KEY_FILE_PATH, state.key_file_path)
        self.password_policy_hint_label.configure(text=state.password_policy_hint)
        self._set_row_visibility(self.dialect_row, visible=state.show_dialect_picker)

        visible_database_fields: list[_StartupFieldWidgets] = []
        visible_access_fields: list[_StartupFieldWidgets] = []
        visible_field_names: list[StartupFieldName] = []

        for requirement in state.backend_fields:
            widgets = self._ensure_field_widgets(requirement.field_name)
            widgets.requirement = requirement
            widgets.label.configure(text=self._field_label(requirement))
            widgets.entry.configure(state="normal" if requirement.editable else "readonly")
            if widgets.browse_button is not None:
                widgets.browse_button.configure(
                    state="normal" if requirement.editable else "disabled"
                )

            visible_field_names.append(requirement.field_name)
            if self._field_belongs_in_database_section(requirement.field_name):
                visible_database_fields.append(widgets)
            else:
                visible_access_fields.append(widgets)

        for field_name, widgets in self._field_widgets.items():
            self._set_row_visibility(widgets.row, visible=field_name in visible_field_names)

        for index, widgets in enumerate(visible_database_fields):
            widgets.row.grid(row=index, column=0, sticky=tk.EW, pady=(0, 6))

        for index, widgets in enumerate(visible_access_fields):
            widgets.row.grid(row=index, column=0, sticky=tk.EW, pady=(0, 6))

        self._visible_field_names = tuple(visible_field_names)
        managed_database_message = self._build_managed_database_hint(
            database_path=state.database_path,
            visible_field_names=self._visible_field_names,
        )
        self.managed_database_message_var.set(managed_database_message)
        self._set_row_visibility(
            self.managed_database_hint_label,
            visible=bool(managed_database_message),
        )
        self._set_row_visibility(self.error_label, visible=bool(self.error_message_var.get()))

        has_password_field = StartupFieldName.PASSWORD in visible_field_names
        self.password_policy_hint_label.grid_configure(row=len(visible_access_fields), column=0)
        self._set_row_visibility(
            self.password_policy_hint_label,
            visible=has_password_field and bool(state.password_policy_hint),
        )
        self._set_row_visibility(
            self.emergency_reset_button,
            visible=state.allow_emergency_reset,
        )
        self.submit_button.configure(state="normal" if state.submit_enabled else "disabled")
        self.migrate_button.configure(
            text=state.migration_action_label,
            state="normal" if state.migration_action_enabled else "disabled",
        )
        self._set_row_visibility(self.migrate_button, visible=state.show_migration_action)
        self.window.update_idletasks()
        self._apply_responsive_geometry(preserve_existing_size=self._has_rendered_state)
        self._has_rendered_state = True

    def get_submission(self) -> StartupDialogSubmission:
        """Return the current dialog values as a presenter submission."""
        return StartupDialogSubmission(
            mode=StartupDialogMode(self.mode_var.get()),
            dialect=self.dialect_var.get(),
            operator=self.operator_var.get(),
            uses_remembered_target=self.use_remembered_target_var.get(),
            field_values={
                field_name: self._get_field_value(field_name)
                for field_name in StartupFieldName
            },
        )

    def _get_field_value(self, field_name: StartupFieldName) -> str:
        """Return the current text value for one backend-driven field."""
        return self._ensure_field_widgets(field_name).variable.get()

    def _set_field_value(self, field_name: StartupFieldName, value: str) -> None:
        """Store a text value for one backend-driven field."""
        self._ensure_field_widgets(field_name).variable.set(value)

    def _sync_state_field_value(self, field_name: StartupFieldName, value: str) -> None:
        if self._get_field_value(field_name) != value:
            self._set_field_value(field_name, value)

    def set_action_callbacks(self, callbacks: StartupDialogActionCallbacks) -> None:
        """Register action-oriented UI callbacks."""
        self._action_callbacks = callbacks


    def set_submission_changed_callback(self, callback: VoidCallback) -> None:
        """Register callback for submission-changing UI events."""
        self._submission_changed_callback = callback

    def set_error_message(self, message: str) -> None:
        """Show a presenter-provided error message in the dialog."""
        self.error_message_var.set(message)
        self._set_row_visibility(self.error_label, visible=bool(message))

    def clear_error_message(self) -> None:
        """Clear the current dialog error message."""
        self.error_message_var.set("")
        self._set_row_visibility(self.error_label, visible=False)

    def set_status_message(self, message: str) -> None:
        """Show a neutral status message in the dialog."""
        self.status_message_var.set(message)
        self._set_row_visibility(self.status_label, visible=bool(message))

    def clear_status_message(self) -> None:
        """Clear the current neutral status message."""
        self.status_message_var.set("")
        self._set_row_visibility(self.status_label, visible=False)

    def clear_sensitive_fields(self, *, clear_password_confirmation: bool = False) -> None:
        """Clear password fields after retryable credential failures."""
        self._set_field_value(StartupFieldName.PASSWORD, "")
        if clear_password_confirmation:
            self._set_field_value(StartupFieldName.PASSWORD_CONFIRMATION, "")

    def focus_primary_input(self) -> None:
        """Focus the most relevant primary input for the current dialog state."""
        if not self.operator_var.get().strip():
            self._focus_widget(self.operator_entry)
            return

        if self.dialect_row.winfo_manager() and not self.dialect_var.get().strip():
            self._focus_widget(self.dialect_combobox)
            return

        for field_name in self._visible_field_names:
            widgets = self._ensure_field_widgets(field_name)
            if not widgets.row.winfo_manager():
                continue
            if str(widgets.entry.cget("state")) == "readonly":
                continue
            self._focus_widget(widgets.entry)
            return

        if self.dialect_row.winfo_manager():
            self._focus_widget(self.dialect_combobox)
            return

        self._focus_widget(self.submit_button)

    def destroy(self) -> None:
        """Destroy the dialog window."""
        self.window.destroy()

    def handle_close_requested(self) -> None:
        """Handle the window-manager close action like a normal cancel."""
        self._handle_cancel()

    def _handle_submit(self) -> None:
        if str(self.submit_button.cget("state")) == "disabled":
            return
        if self._action_callbacks.submit is not None:
            self._action_callbacks.submit()

    def _handle_submit_keypress(self, _event: tk.Event[tk.Misc]) -> str:
        self._handle_submit()
        return "break"

    def _handle_window_configure(self, _event: tk.Event[tk.Misc]) -> None:
        self._update_wrap_lengths()
        self._refresh_scroll_state()

    def _handle_content_configure(self, _event: tk.Event[tk.Misc]) -> None:
        self._refresh_scroll_state()

    def _handle_canvas_configure(self, event: tk.Event[tk.Misc]) -> None:
        self.content_canvas.itemconfigure(self._container_window, width=event.width)
        self._update_wrap_lengths()
        self._refresh_scroll_state()

    def _handle_cancel(self) -> None:
        if self._action_callbacks.cancel is not None:
            self._action_callbacks.cancel()

    def _handle_migrate(self) -> None:
        if self._action_callbacks.migrate is not None:
            self._action_callbacks.migrate()

    def _handle_emergency_reset(self) -> None:
        if self._action_callbacks.emergency_reset is not None:
            self._action_callbacks.emergency_reset()

    def _handle_browse_key_file(self) -> None:
        if self._action_callbacks.browse_key_file is not None:
            self._action_callbacks.browse_key_file()

    def _notify_submission_changed(self, _event: object | None = None) -> None:
        if self._submission_changed_callback is not None:
            self._submission_changed_callback()


    def _ensure_field_widgets(self, field_name: StartupFieldName) -> _StartupFieldWidgets:
        widgets = self._field_widgets.get(field_name)
        if widgets is not None:
            return widgets

        parent = (
            self.database_fields_container
            if self._field_belongs_in_database_section(field_name)
            else self.access_fields_container
        )
        row = ttk.Frame(parent)
        row.columnconfigure(1, weight=1)
        variable = tk.StringVar(master=self.window)
        label = ttk.Label(row, text=self._field_default_label(field_name), width=18)
        label.grid(row=0, column=0, sticky=tk.W, padx=(0, 8))

        entry = ttk.Entry(
            row,
            textvariable=variable,
            show="*" if self._field_uses_password_mask(field_name) else "",
        )
        entry.grid(row=0, column=1, sticky=tk.EW, padx=(0, 6))
        if field_name is StartupFieldName.DATABASE_PATH:
            entry.bind("<KeyRelease>", self._notify_submission_changed)

        browse_button: ttk.Button | None = None
        if field_name is StartupFieldName.KEY_FILE_PATH:
            browse_button = ttk.Button(
                row,
                text="Välj...",
                command=self._handle_browse_key_file,
            )
            browse_button.grid(row=0, column=2, sticky=tk.E)

        widgets = _StartupFieldWidgets(
            requirement=StartupFieldRequirement(
                field_name=field_name,
                kind=self._field_kind(field_name),
            ),
            row=row,
            label=label,
            entry=entry,
            variable=variable,
            browse_button=browse_button,
        )
        self._field_widgets[field_name] = widgets
        return widgets

    @staticmethod
    def _field_label(field: StartupFieldRequirement) -> str:
        if field.field_name is StartupFieldName.DATABASE_PATH:
            return "Databasfil:"

        if field.field_name is StartupFieldName.PASSWORD:
            return "Lösenord:"

        if field.field_name is StartupFieldName.PASSWORD_CONFIRMATION:
            return "Upprepa lösenord:"

        if field.field_name is StartupFieldName.KEY_FILE_PATH:
            return "Nyckelfil:" if field.required else "Nyckelfil (valfritt):"

        return StartupDialogView._field_default_label(field.field_name)

    @staticmethod
    def _field_default_label(field_name: StartupFieldName) -> str:
        labels = {
            StartupFieldName.DATABASE_PATH: "Databasfil:",
            StartupFieldName.PASSWORD: "Lösenord:",
            StartupFieldName.PASSWORD_CONFIRMATION: "Upprepa lösenord:",
            StartupFieldName.KEY_FILE_PATH: "Nyckelfil:",
        }
        return labels[field_name]

    @staticmethod
    def _field_kind(field_name: StartupFieldName) -> StartupFieldKind:
        if field_name in {StartupFieldName.DATABASE_PATH, StartupFieldName.KEY_FILE_PATH}:
            return StartupFieldKind.FILE_PATH

        return StartupFieldKind.PASSWORD

    @staticmethod
    def _field_belongs_in_database_section(field_name: StartupFieldName) -> bool:
        return field_name is StartupFieldName.DATABASE_PATH

    @staticmethod
    def _field_uses_password_mask(field_name: StartupFieldName) -> bool:
        return field_name in {
            StartupFieldName.PASSWORD,
            StartupFieldName.PASSWORD_CONFIRMATION,
        }

    def _focus_widget(self, widget: tk.Widget) -> None:
        self.window.focus_force()
        widget.focus_force()

    def _apply_responsive_geometry(self, *, preserve_existing_size: bool = False) -> None:
        screen_width = max(1, self.window.winfo_screenwidth())
        screen_height = max(1, self.window.winfo_screenheight())
        maximum_width = max(320, int(screen_width * 0.8))
        maximum_height = max(240, int(screen_height * 0.8))
        minimum_width = min(self._minimum_width, maximum_width)
        minimum_height = min(self._minimum_height, maximum_height)
        current_width = max(1, self.window.winfo_width())
        current_height = max(1, self.window.winfo_height())
        requested_width = self.window.winfo_reqwidth()
        target_width = max(requested_width, minimum_width)
        if preserve_existing_size:
            target_width = max(target_width, current_width)

        width = min(target_width, maximum_width)
        measured_height = self._measure_desired_height_for_width(width, minimum_height)
        if measured_height > maximum_height and width < maximum_width:
            width = maximum_width
            measured_height = self._measure_desired_height_for_width(width, minimum_height)

        target_height = max(measured_height, minimum_height)
        if preserve_existing_size:
            target_height = max(target_height, current_height)

        height = min(target_height, maximum_height)
        x_position, y_position = self._resolve_geometry_position(
            width=width,
            height=height,
            screen_width=screen_width,
            screen_height=screen_height,
            preserve_existing_position=preserve_existing_size,
        )
        self.window.geometry(f"{width}x{height}+{x_position}+{y_position}")
        self.window.update_idletasks()
        self.window.minsize(minimum_width, minimum_height)
        self._update_wrap_lengths()
        self._refresh_scroll_state()

    def _measure_desired_height_for_width(self, width: int, minimum_height: int) -> int:
        provisional_height = max(minimum_height, self.window.winfo_height(), self.window.winfo_reqheight())
        self.window.geometry(f"{width}x{provisional_height}")
        self.window.update_idletasks()
        self._update_wrap_lengths()
        self.window.update_idletasks()
        content_height = self.container.winfo_reqheight()
        footer_reserved_height = max(0, self.window.winfo_height() - self.content_canvas.winfo_height())
        return content_height + footer_reserved_height

    def _resolve_geometry_position(
        self,
        *,
        width: int,
        height: int,
        screen_width: int,
        screen_height: int,
        preserve_existing_position: bool,
    ) -> tuple[int, int]:
        maximum_x = max(screen_width - width, 0)
        maximum_y = max(screen_height - height, 0)
        if not preserve_existing_position:
            return maximum_x // 2, maximum_y // 2

        current_x = self.window.winfo_x()
        current_y = self.window.winfo_y()
        return (
            min(max(current_x, 0), maximum_x),
            min(max(current_y, 0), maximum_y),
        )

    def _update_wrap_lengths(self) -> None:
        available_width = max(self.content_canvas.winfo_width(), self.window.winfo_width(), 320)
        wraplength = max(320, available_width - 80)
        self.summary_label.configure(wraplength=wraplength)
        self.managed_database_hint_label.configure(wraplength=wraplength)
        self.password_policy_hint_label.configure(wraplength=wraplength)

    def _refresh_scroll_state(self) -> None:
        content_bbox = self.content_canvas.bbox(self._container_window)
        if content_bbox is None:
            return

        self.content_canvas.configure(scrollregion=content_bbox)
        content_height = content_bbox[3] - content_bbox[1]
        canvas_height = max(1, self.content_canvas.winfo_height())
        needs_vertical_scrollbar = content_height > canvas_height
        if needs_vertical_scrollbar:
            if self.content_vertical_scrollbar.winfo_manager() != "grid":
                self.content_vertical_scrollbar.grid(row=0, column=1, sticky=tk.NS, padx=(8, 0))
            return

        if self.content_vertical_scrollbar.winfo_manager():
            self.content_vertical_scrollbar.grid_remove()

    @staticmethod
    def _build_summary_text(state: StartupDialogState) -> str:
        if state.mode is StartupDialogMode.CREATE:
            return "EventLog använder en apphanterad databas. Ange operatör och åtkomstuppgifter för att skapa eller återställa den lokala databasen."

        return "EventLog använder en apphanterad databas. Ange operatör och åtkomstuppgifter för att låsa upp den lokala databasen."

    @staticmethod
    def _build_managed_database_hint(
        *,
        database_path: str,
        visible_field_names: Sequence[StartupFieldName],
    ) -> str:
        normalized_database_path = database_path.strip()
        if not normalized_database_path:
            return ""
        if StartupFieldName.DATABASE_PATH in visible_field_names:
            return ""

        return f"Apphanterad databassökväg:\n{normalized_database_path}"

    @staticmethod
    def _set_row_visibility(widget: tk.Widget, *, visible: bool) -> None:
        if visible:
            if not widget.winfo_manager():
                widget.grid()
            return

        if widget.winfo_manager():
            widget.grid_remove()


__all__ = [
    "StartupDialogActionCallbacks",
    "StartupDialogView",
    "VoidCallback",
]


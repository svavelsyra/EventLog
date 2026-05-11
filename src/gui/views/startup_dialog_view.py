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
from typing import Callable, Sequence

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
    browse_database: VoidCallback | None = None
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
        self.window.resizable(False, False)
        self.window.minsize(640, 360)

        self._action_callbacks = StartupDialogActionCallbacks()
        self._submission_changed_callback: VoidCallback | None = None
        self._field_widgets: dict[StartupFieldName, _StartupFieldWidgets] = {}
        self._visible_field_names: tuple[StartupFieldName, ...] = ()

        self.mode_var = tk.StringVar(master=self.window, value=StartupDialogMode.CREATE.value)
        self.use_remembered_target_var = tk.BooleanVar(master=self.window, value=False)
        self.dialect_var = tk.StringVar(master=self.window)
        self.operator_var = tk.StringVar(master=self.window)
        self.status_message_var = tk.StringVar(master=self.window)
        self.error_message_var = tk.StringVar(master=self.window)

        self.window.columnconfigure(0, weight=1)

        self.container = ttk.Frame(self.window, padding=12)
        self.container.grid(row=0, column=0, sticky=tk.NSEW)
        self.container.columnconfigure(0, weight=1)

        self.summary_label = ttk.Label(
            self.container,
            text="Välj eller ange databas. Dialogen anpassar sig efter vald teknik och om databasen redan finns.",
            wraplength=560,
            justify="left",
        )
        self.summary_label.grid(row=0, column=0, sticky=tk.W, pady=(0, 10))

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

        self.mode_row = ttk.LabelFrame(self.database_section, text="Startläge", padding=8)
        self.mode_row.grid(row=0, column=0, sticky=tk.EW, pady=(0, 8))
        self.create_mode_button = ttk.Radiobutton(
            self.mode_row,
            text="Skapa ny databas",
            value=StartupDialogMode.CREATE.value,
            variable=self.mode_var,
            command=self._notify_submission_changed,
        )
        self.create_mode_button.grid(row=0, column=0, sticky=tk.W, padx=(0, 12))
        self.unlock_mode_button = ttk.Radiobutton(
            self.mode_row,
            text="Öppna befintlig databas",
            value=StartupDialogMode.UNLOCK.value,
            variable=self.mode_var,
            command=self._notify_submission_changed,
        )
        self.unlock_mode_button.grid(row=0, column=1, sticky=tk.W)
        self.mode_row.grid_remove()

        self.target_source_row = ttk.LabelFrame(self.database_section, text="Databasval", padding=8)
        self.target_source_row.grid(row=1, column=0, sticky=tk.EW, pady=(0, 8))
        self.target_source_row.columnconfigure(0, weight=1)
        self.use_remembered_target_button = ttk.Radiobutton(
            self.target_source_row,
            text="Använd senast ihågkommen databas",
            value=True,
            variable=self.use_remembered_target_var,
            command=self._notify_submission_changed,
        )
        self.use_remembered_target_button.grid(row=0, column=0, sticky=tk.W, pady=(0, 4))
        self.use_manual_target_button = ttk.Radiobutton(
            self.target_source_row,
            text="Välj eller ange databas manuellt",
            value=False,
            variable=self.use_remembered_target_var,
            command=self._notify_submission_changed,
        )
        self.use_manual_target_button.grid(row=1, column=0, sticky=tk.W)

        self.dialect_row = ttk.Frame(self.database_section)
        self.dialect_row.grid(row=2, column=0, sticky=tk.EW, pady=(0, 6))
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
        self.database_fields_container.grid(row=3, column=0, sticky=tk.EW)
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

        self.status_label = ttk.Label(
            self.container,
            textvariable=self.status_message_var,
            foreground="#1b5e20",
        )
        self.status_label.grid(row=5, column=0, sticky=tk.W, pady=(0, 8))
        self.status_label.grid_remove()

        self.button_separator = ttk.Separator(self.container, orient="horizontal")
        self.button_separator.grid(row=6, column=0, sticky=tk.EW, pady=(4, 10))

        self.button_row = ttk.Frame(self.container)
        self.button_row.grid(row=7, column=0, sticky=tk.EW)
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

        self.window.protocol("WM_DELETE_WINDOW", self.handle_close_requested)
        self.window.update_idletasks()
        fixed_width = max(640, self.window.winfo_reqwidth())
        fixed_height = max(360, self.window.winfo_reqheight())
        self.window.geometry(f"{fixed_width}x{fixed_height}")
        self.window.minsize(fixed_width, fixed_height)
        self.window.maxsize(fixed_width, fixed_height)

        for field_name in StartupFieldName:
            self._ensure_field_widgets(field_name)

    def render_state(self, state: StartupDialogState) -> None:
        """Render presenter-owned state into the dialog widgets."""
        self.window.title(state.title)
        self.submit_button.configure(text=state.submit_label)
        self.summary_label.configure(text=state.title)
        self.mode_var.set(state.mode.value)
        self.use_remembered_target_var.set(state.uses_remembered_target)
        self.dialect_var.set(state.dialect)
        if self.operator_var.get() != state.operator:
            self.operator_var.set(state.operator)
        self._sync_state_field_value(StartupFieldName.DATABASE_PATH, state.database_path)
        self._sync_state_field_value(StartupFieldName.KEY_FILE_PATH, state.key_file_path)
        self.password_policy_hint_label.configure(text=state.password_policy_hint)
        self._set_modes(state.available_modes)

        self._set_row_visibility(self.mode_row, visible=state.show_mode_selector)
        self._set_row_visibility(
            self.target_source_row,
            visible=state.show_target_source_selector,
        )
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

    def get_submission(self) -> StartupDialogSubmission:
        """Return the current dialog values as a presenter submission."""
        return StartupDialogSubmission(
            mode=StartupDialogMode(self.mode_var.get()),
            dialect=self.dialect_var.get(),
            operator=self.operator_var.get(),
            uses_remembered_target=self.use_remembered_target_var.get(),
            field_values={
                field_name: self.get_field_value(field_name)
                for field_name in StartupFieldName
            },
        )

    def get_field_value(self, field_name: StartupFieldName) -> str:
        """Return the current text value for one backend-driven field."""
        return self._ensure_field_widgets(field_name).variable.get()

    def set_field_value(self, field_name: StartupFieldName, value: str) -> None:
        """Store a text value for one backend-driven field."""
        self._ensure_field_widgets(field_name).variable.set(value)

    def _sync_state_field_value(self, field_name: StartupFieldName, value: str) -> None:
        if self.get_field_value(field_name) != value:
            self.set_field_value(field_name, value)

    def set_action_callbacks(self, callbacks: StartupDialogActionCallbacks) -> None:
        """Register action-oriented UI callbacks."""
        self._action_callbacks = callbacks


    def set_submission_changed_callback(self, callback: VoidCallback) -> None:
        """Register callback for submission-changing UI events."""
        self._submission_changed_callback = callback

    def set_error_message(self, message: str) -> None:
        """Show a presenter-provided error message in the dialog."""
        self.error_message_var.set(message)

    def clear_error_message(self) -> None:
        """Clear the current dialog error message."""
        self.error_message_var.set("")

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
        self.set_field_value(StartupFieldName.PASSWORD, "")
        if clear_password_confirmation:
            self.set_field_value(StartupFieldName.PASSWORD_CONFIRMATION, "")

    def focus_primary_input(self) -> None:
        """Focus the most relevant primary input for the current dialog state."""
        if not self.operator_var.get().strip():
            self.operator_entry.focus_set()
            return

        if self.dialect_row.winfo_manager() and not self.dialect_var.get().strip():
            self.dialect_combobox.focus_set()
            return

        for field_name in self._visible_field_names:
            widgets = self._ensure_field_widgets(field_name)
            if not widgets.row.winfo_manager():
                continue
            if str(widgets.entry.cget("state")) == "readonly":
                continue
            widgets.entry.focus_set()
            return

        if self.dialect_row.winfo_manager():
            self.dialect_combobox.focus_set()
            return

        self.submit_button.focus_set()

    def destroy(self) -> None:
        """Destroy the dialog window."""
        self.window.destroy()

    def handle_close_requested(self) -> None:
        """Handle the window-manager close action like a normal cancel."""
        self._handle_cancel()

    def _handle_submit(self) -> None:
        if self._action_callbacks.submit is not None:
            self._action_callbacks.submit()

    def _handle_cancel(self) -> None:
        if self._action_callbacks.cancel is not None:
            self._action_callbacks.cancel()

    def _handle_migrate(self) -> None:
        if self._action_callbacks.migrate is not None:
            self._action_callbacks.migrate()

    def _handle_emergency_reset(self) -> None:
        if self._action_callbacks.emergency_reset is not None:
            self._action_callbacks.emergency_reset()

    def _handle_browse_database(self) -> None:
        if self._action_callbacks.browse_database is not None:
            self._action_callbacks.browse_database()

    def _handle_browse_key_file(self) -> None:
        if self._action_callbacks.browse_key_file is not None:
            self._action_callbacks.browse_key_file()

    def _notify_submission_changed(self, _event: object | None = None) -> None:
        if self._submission_changed_callback is not None:
            self._submission_changed_callback()

    def _set_modes(self, available_modes: Sequence[StartupDialogMode]) -> None:
        create_enabled = StartupDialogMode.CREATE in available_modes
        unlock_enabled = StartupDialogMode.UNLOCK in available_modes
        self.create_mode_button.configure(state="normal" if create_enabled else "disabled")
        self.unlock_mode_button.configure(state="normal" if unlock_enabled else "disabled")

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
        if field_name in {StartupFieldName.DATABASE_PATH, StartupFieldName.KEY_FILE_PATH}:
            browse_button = ttk.Button(
                row,
                text="Välj...",
                command=(
                    self._handle_browse_database
                    if field_name is StartupFieldName.DATABASE_PATH
                    else self._handle_browse_key_file
                ),
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


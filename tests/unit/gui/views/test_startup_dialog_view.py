import tkinter as tk

import pytest

from src.db.repositories.startup_selection import (
    StartupFieldKind,
    StartupFieldName,
    StartupFieldRequirement,
)
from src.gui.presenters.startup_dialog_presenter import (
    StartupDialogMode,
    StartupDialogState,
)
from src.gui.views.startup_dialog_view import StartupDialogActionCallbacks, StartupDialogView


pytestmark = pytest.mark.unit

TARGET_LAPTOP_SCREEN_WIDTH = 1024
TARGET_LAPTOP_SCREEN_HEIGHT = 600
TARGET_LAPTOP_DIALOG_MAX_WIDTH = int(TARGET_LAPTOP_SCREEN_WIDTH * 0.8)
TARGET_LAPTOP_DIALOG_MAX_HEIGHT = int(TARGET_LAPTOP_SCREEN_HEIGHT * 0.8)


def _make_state(
    *,
    mode: StartupDialogMode,
    title: str,
    submit_label: str,
    password_policy_hint: str = "Minst 8 tecken för nytt lösenord.",
    allow_emergency_reset: bool,
    uses_remembered_target: bool = False,
    show_dialect_picker: bool = True,
    include_database_path_field: bool = True,
    database_path_is_editable: bool = True,
    include_password_confirmation_field: bool = False,
    include_key_file_field: bool = False,
    key_file_is_required: bool = False,
    key_file_path: str = "",
    database_path: str = "eventlog.db",
    operator: str = "",
) -> StartupDialogState:
    backend_fields: list[StartupFieldRequirement] = [
        StartupFieldRequirement(
            field_name=StartupFieldName.PASSWORD,
            kind=StartupFieldKind.PASSWORD,
        )
    ]

    if include_database_path_field:
        backend_fields.insert(
            0,
            StartupFieldRequirement(
                field_name=StartupFieldName.DATABASE_PATH,
                kind=StartupFieldKind.FILE_PATH,
                required=True,
                editable=database_path_is_editable,
            ),
        )

    if include_password_confirmation_field:
        backend_fields.append(
            StartupFieldRequirement(
                field_name=StartupFieldName.PASSWORD_CONFIRMATION,
                kind=StartupFieldKind.PASSWORD,
            )
        )

    if include_key_file_field:
        backend_fields.append(
            StartupFieldRequirement(
                field_name=StartupFieldName.KEY_FILE_PATH,
                kind=StartupFieldKind.FILE_PATH,
                required=key_file_is_required,
            )
        )

    return StartupDialogState(
        mode=mode,
        title=title,
        submit_label=submit_label,
        dialect="sqlite",
        database_path=database_path,
        min_password_length=8,
        password_policy_hint=password_policy_hint,
        allow_emergency_reset=allow_emergency_reset,
        key_file_path=key_file_path,
        uses_remembered_target=uses_remembered_target,
        operator=operator,
        show_dialect_picker=show_dialect_picker,
        backend_fields=tuple(backend_fields),
    )


def _field_row(view: StartupDialogView, field_name: StartupFieldName):
    return view._field_widgets[field_name].row


def _field_label(view: StartupDialogView, field_name: StartupFieldName) -> str:
    return str(view._field_widgets[field_name].label.cget("text"))


def _field_entry_state(view: StartupDialogView, field_name: StartupFieldName) -> str:
    return str(view._field_widgets[field_name].entry.cget("state"))


def _field_has_browse_button(view: StartupDialogView, field_name: StartupFieldName) -> bool:
    return view._field_widgets[field_name].browse_button is not None


def _get_field_value(view: StartupDialogView, field_name: StartupFieldName) -> str:
    return view._field_widgets[field_name].variable.get()


def _set_field_value(view: StartupDialogView, field_name: StartupFieldName, value: str) -> None:
    view._field_widgets[field_name].variable.set(value)


def _resizable_flags(view: StartupDialogView) -> tuple[bool, bool]:
    horizontal, vertical = view.window.resizable()
    return bool(horizontal), bool(vertical)


def _apply_target_laptop_screen_metrics(view: StartupDialogView) -> None:
    view.window.winfo_screenwidth = lambda: TARGET_LAPTOP_SCREEN_WIDTH
    view.window.winfo_screenheight = lambda: TARGET_LAPTOP_SCREEN_HEIGHT


def _scenario_render_state_for_create(root: tk.Tk) -> dict[str, object]:
    view = StartupDialogView(root)
    try:
        view.render_state(
            _make_state(
                mode=StartupDialogMode.CREATE,
                title="EventLog - Skapa krypterad databas",
                submit_label="Skapa",
                include_password_confirmation_field=True,
                include_key_file_field=True,
                key_file_is_required=False,
                key_file_path="C:/keys/startup.key",
                allow_emergency_reset=False,
                operator="Sgt Example",
            )
        )
        view.window.update_idletasks()
        return {
            "title": view.window.title(),
            "summary_text": view.summary_label.cget("text"),
            "user_section_manager": view.user_section.winfo_manager(),
            "operator_label": view.operator_label.cget("text"),
            "operator_value": view.operator_var.get(),
            "submit_label": view.submit_button.cget("text"),
            "dialect_manager": view.dialect_row.winfo_manager(),
            "database_path_manager": _field_row(view, StartupFieldName.DATABASE_PATH).winfo_manager(),
            "database_path_state": _field_entry_state(view, StartupFieldName.DATABASE_PATH),
            "database_path_has_browse_button": _field_has_browse_button(
                view,
                StartupFieldName.DATABASE_PATH,
            ),
            "password_confirmation_manager": _field_row(
                view,
                StartupFieldName.PASSWORD_CONFIRMATION,
            ).winfo_manager(),
            "password_policy_hint_visible": bool(view.password_policy_hint_label.winfo_ismapped()),
            "password_policy_hint_text": view.password_policy_hint_label.cget("text"),
            "key_file_manager": _field_row(view, StartupFieldName.KEY_FILE_PATH).winfo_manager(),
            "key_file_label": _field_label(view, StartupFieldName.KEY_FILE_PATH),
            "key_file_has_browse_button": _field_has_browse_button(view, StartupFieldName.KEY_FILE_PATH),
            "key_file_value": _get_field_value(view, StartupFieldName.KEY_FILE_PATH),
            "managed_database_hint_visible": bool(view.managed_database_hint_label.winfo_ismapped()),
            "visible_field_names": [
                widgets.requirement.field_name
                for widgets in view._field_widgets.values()
                if widgets.row.winfo_manager()
            ],
            "emergency_reset_manager": view.emergency_reset_button.winfo_manager(),
            "has_target_source_row": hasattr(view, "target_source_row"),
            "has_manual_target_button": hasattr(view, "use_manual_target_button"),
            "resizable": _resizable_flags(view),
        }
    finally:
        view.destroy()


def _scenario_render_state_for_managed_unlock(root: tk.Tk) -> dict[str, object]:
    view = StartupDialogView(root)
    try:
        view.render_state(
            _make_state(
                mode=StartupDialogMode.UNLOCK,
                title="EventLog - Lås upp",
                submit_label="Lås upp",
                allow_emergency_reset=True,
                uses_remembered_target=True,
                show_dialect_picker=False,
                include_database_path_field=False,
                database_path="C:/Ops/eventlog.db",
                password_policy_hint="",
            )
        )
        view.window.update_idletasks()
        return {
            "title": view.window.title(),
            "summary_text": view.summary_label.cget("text"),
            "submit_label": view.submit_button.cget("text"),
            "dialect_manager": view.dialect_row.winfo_manager(),
            "database_path_manager": _field_row(view, StartupFieldName.DATABASE_PATH).winfo_manager(),
            "managed_database_hint_visible": bool(view.managed_database_hint_label.winfo_ismapped()),
            "managed_database_hint_text": view.managed_database_message_var.get(),
            "password_policy_hint_visible": bool(view.password_policy_hint_label.winfo_ismapped()),
            "key_file_manager": _field_row(view, StartupFieldName.KEY_FILE_PATH).winfo_manager(),
            "emergency_reset_manager": view.emergency_reset_button.winfo_manager(),
            "emergency_reset_class": view.emergency_reset_button.winfo_class(),
            "emergency_reset_background": view.emergency_reset_button.cget("background"),
            "danger_action_frame_manager": view.danger_action_frame.winfo_manager(),
            "button_separator_manager": view.button_separator.winfo_manager(),
        }
    finally:
        view.destroy()


def _scenario_render_state_for_neutral_create(root: tk.Tk) -> dict[str, object]:
    view = StartupDialogView(root)
    try:
        view.render_state(
            StartupDialogState(
                mode=StartupDialogMode.CREATE,
                title="EventLog - Välj eller skapa databas",
                submit_label="Skapa",
                dialect="sqlite",
                database_path="",
                min_password_length=8,
                password_policy_hint="Minst 8 tecken för nytt lösenord.",
                allow_emergency_reset=False,
                key_file_path="",
                backend_fields=(
                    StartupFieldRequirement(
                        field_name=StartupFieldName.DATABASE_PATH,
                        kind=StartupFieldKind.FILE_PATH,
                        required=True,
                        editable=True,
                    ),
                ),
            )
        )
        view.window.update_idletasks()
        return {
            "title": view.window.title(),
            "summary_text": view.summary_label.cget("text"),
            "database_path_manager": _field_row(view, StartupFieldName.DATABASE_PATH).winfo_manager(),
            "database_path_has_browse_button": _field_has_browse_button(
                view,
                StartupFieldName.DATABASE_PATH,
            ),
            "password_manager": _field_row(view, StartupFieldName.PASSWORD).winfo_manager(),
            "password_confirmation_manager": _field_row(
                view,
                StartupFieldName.PASSWORD_CONFIRMATION,
            ).winfo_manager(),
            "key_file_manager": _field_row(view, StartupFieldName.KEY_FILE_PATH).winfo_manager(),
            "managed_database_hint_visible": bool(view.managed_database_hint_label.winfo_ismapped()),
        }
    finally:
        view.destroy()


def _scenario_get_submission(root: tk.Tk) -> dict[str, object]:
    view = StartupDialogView(root)
    try:
        view.mode_var.set(StartupDialogMode.UNLOCK.value)
        view.use_remembered_target_var.set(True)
        view.operator_var.set("Sgt Example")
        view.dialect_var.set("sqlite")
        _set_field_value(view, StartupFieldName.DATABASE_PATH, "C:/data/eventlog.db")
        _set_field_value(view, StartupFieldName.PASSWORD, "lösenord123")
        _set_field_value(view, StartupFieldName.PASSWORD_CONFIRMATION, "lösenord123")
        _set_field_value(view, StartupFieldName.KEY_FILE_PATH, "   ")

        submission = view.get_submission()
        return {
            "mode": submission.mode,
            "dialect": submission.dialect,
            "operator": submission.operator,
            "uses_remembered_target": submission.uses_remembered_target,
            "field_values": dict(submission.field_values),
        }
    finally:
        view.destroy()


def _scenario_invoke_callbacks(root: tk.Tk) -> dict[str, object]:
    view = StartupDialogView(root)
    try:
        events: list[str] = []
        view.render_state(
            StartupDialogState(
                mode=StartupDialogMode.CREATE,
                title="EventLog - Skapa krypterad databas",
                submit_label="Skapa",
                dialect="sqlite",
                database_path="eventlog.db",
                min_password_length=8,
                password_policy_hint="Minst 8 tecken för nytt lösenord.",
                allow_emergency_reset=True,
                key_file_path="",
                backend_fields=(
                    StartupFieldRequirement(
                        field_name=StartupFieldName.DATABASE_PATH,
                        kind=StartupFieldKind.FILE_PATH,
                        required=True,
                        editable=True,
                    ),
                    StartupFieldRequirement(
                        field_name=StartupFieldName.KEY_FILE_PATH,
                        kind=StartupFieldKind.FILE_PATH,
                        required=False,
                        editable=True,
                    ),
                ),
            )
        )
        view.set_action_callbacks(
            StartupDialogActionCallbacks(
                submit=lambda: events.append("submit"),
                cancel=lambda: events.append("cancel"),
                emergency_reset=lambda: events.append("reset"),
                browse_key_file=lambda: events.append("browse-key-file"),
            )
        )
        view.set_submission_changed_callback(lambda: events.append("submission-changed"))

        view.submit_button.invoke()
        view.cancel_button.invoke()
        view.emergency_reset_button.invoke()
        view._field_widgets[StartupFieldName.KEY_FILE_PATH].browse_button.invoke()
        view.dialect_combobox.event_generate("<<ComboboxSelected>>")
        database_path_entry = view._field_widgets[StartupFieldName.DATABASE_PATH].entry
        database_path_entry.focus_set()
        view.window.update()
        database_path_entry.event_generate("<KeyRelease>", when="tail")
        view.window.update()
        view.handle_close_requested()
        return {
            "events": events,
            "database_path_has_browse_button": _field_has_browse_button(
                view,
                StartupFieldName.DATABASE_PATH,
            ),
        }
    finally:
        view.destroy()


def _scenario_press_enter_in_password_field(root: tk.Tk) -> dict[str, object]:
    view = StartupDialogView(root)
    try:
        events: list[str] = []
        view.render_state(
            StartupDialogState(
                mode=StartupDialogMode.CREATE,
                title="EventLog - Skapa krypterad databas",
                submit_label="Skapa",
                dialect="sqlite",
                database_path="eventlog.db",
                min_password_length=8,
                password_policy_hint="Minst 8 tecken för nytt lösenord.",
                allow_emergency_reset=False,
                key_file_path="",
                backend_fields=(
                    StartupFieldRequirement(
                        field_name=StartupFieldName.DATABASE_PATH,
                        kind=StartupFieldKind.FILE_PATH,
                        required=True,
                        editable=True,
                    ),
                    StartupFieldRequirement(
                        field_name=StartupFieldName.PASSWORD,
                        kind=StartupFieldKind.PASSWORD,
                    ),
                ),
            )
        )
        view.set_action_callbacks(
            StartupDialogActionCallbacks(
                submit=lambda: events.append("submit"),
            )
        )

        password_entry = view._field_widgets[StartupFieldName.PASSWORD].entry
        password_entry.focus_set()
        view.window.update()
        password_entry.event_generate("<Return>")
        view.window.update()

        view.submit_button.configure(state="disabled")
        password_entry.event_generate("<Return>")
        view.window.update()

        return {
            "events": events,
            "focused_widget_class": (
                view.window.focus_get().winfo_class() if view.window.focus_get() is not None else None
            ),
        }
    finally:
        view.destroy()


def _scenario_clear_sensitive_fields(root: tk.Tk) -> dict[str, str]:
    view = StartupDialogView(root)
    try:
        _set_field_value(view, StartupFieldName.PASSWORD, "lösenord123")
        _set_field_value(view, StartupFieldName.PASSWORD_CONFIRMATION, "upprepat")
        view.clear_sensitive_fields(clear_password_confirmation=False)
        after_first_clear = {
            "password": _get_field_value(view, StartupFieldName.PASSWORD),
            "password_confirmation": _get_field_value(view, StartupFieldName.PASSWORD_CONFIRMATION),
        }

        view.clear_sensitive_fields(clear_password_confirmation=True)
        after_second_clear = {
            "password": _get_field_value(view, StartupFieldName.PASSWORD),
            "password_confirmation": _get_field_value(view, StartupFieldName.PASSWORD_CONFIRMATION),
        }

        return {
            "after_first_password": after_first_clear["password"],
            "after_first_confirmation": after_first_clear["password_confirmation"],
            "after_second_password": after_second_clear["password"],
            "after_second_confirmation": after_second_clear["password_confirmation"],
        }
    finally:
        view.destroy()


def _scenario_render_state_without_selected_dialect(root: tk.Tk) -> dict[str, object]:
    view = StartupDialogView(root)
    try:
        empty_state = StartupDialogState(
            mode=StartupDialogMode.CREATE,
            title="EventLog - Välj eller skapa databas",
            submit_label="Skapa",
            dialect="",
            database_path="",
            min_password_length=8,
            password_policy_hint="Minst 8 tecken för nytt lösenord.",
            allow_emergency_reset=False,
            key_file_path="",
            backend_fields=(),
        )
        full_state = _make_state(
            mode=StartupDialogMode.CREATE,
            title="EventLog - Skapa krypterad databas",
            submit_label="Skapa",
            include_password_confirmation_field=True,
            include_key_file_field=True,
            key_file_is_required=False,
            allow_emergency_reset=False,
        )

        view.render_state(empty_state)
        view.window.update_idletasks()
        title_without_dialect = view.window.title()
        summary_without_dialect = view.summary_label.cget("text")
        size_without_dialect = (view.window.winfo_width(), view.window.winfo_height())
        view.focus_primary_input()
        focused_widget = view.window.focus_get()
        focus_without_dialect = focused_widget.winfo_class() if focused_widget is not None else None
        managers_without_dialect = {
            "database_path": _field_row(view, StartupFieldName.DATABASE_PATH).winfo_manager(),
            "password": _field_row(view, StartupFieldName.PASSWORD).winfo_manager(),
            "key_file": _field_row(view, StartupFieldName.KEY_FILE_PATH).winfo_manager(),
        }
        password_policy_hint_visible_without_dialect = bool(
            view.password_policy_hint_label.winfo_ismapped()
        )
        resizable = _resizable_flags(view)

        view.render_state(full_state)
        view.window.update_idletasks()
        size_with_sqlite = (view.window.winfo_width(), view.window.winfo_height())

        return {
            "title_without_dialect": title_without_dialect,
            "summary_without_dialect": summary_without_dialect,
            "dialect_value": view.dialect_var.get(),
            "size_without_dialect": size_without_dialect,
            "size_with_sqlite": size_with_sqlite,
            "focus_without_dialect": focus_without_dialect,
            "managers_without_dialect": managers_without_dialect,
            "password_policy_hint_visible_without_dialect": password_policy_hint_visible_without_dialect,
            "database_path_manager_with_sqlite": _field_row(
                view,
                StartupFieldName.DATABASE_PATH,
            ).winfo_manager(),
            "password_manager_with_sqlite": _field_row(view, StartupFieldName.PASSWORD).winfo_manager(),
            "password_policy_hint_visible_with_sqlite": bool(
                view.password_policy_hint_label.winfo_ismapped()
            ),
            "password_policy_hint_text_with_sqlite": view.password_policy_hint_label.cget("text"),
            "key_file_manager_with_sqlite": _field_row(view, StartupFieldName.KEY_FILE_PATH).winfo_manager(),
            "resizable": resizable,
        }
    finally:
        view.destroy()


def _scenario_render_state_preserves_visible_field_values_across_rerenders(root: tk.Tk) -> dict[str, object]:
    view = StartupDialogView(root)
    try:
        create_state = _make_state(
            mode=StartupDialogMode.CREATE,
            title="EventLog - Skapa krypterad databas",
            submit_label="Skapa",
            include_password_confirmation_field=True,
            include_key_file_field=True,
            key_file_is_required=False,
            key_file_path="C:/keys/startup.key",
            allow_emergency_reset=False,
        )
        unlock_state = _make_state(
            mode=StartupDialogMode.UNLOCK,
            title="EventLog - Lås upp",
            submit_label="Lås upp",
            include_database_path_field=False,
            include_key_file_field=True,
            key_file_is_required=False,
            allow_emergency_reset=True,
            uses_remembered_target=True,
            show_dialect_picker=False,
            database_path="C:/Ops/eventlog.db",
            key_file_path="C:/keys/startup.key",
            password_policy_hint="",
        )

        view.render_state(create_state)
        _set_field_value(view, StartupFieldName.PASSWORD, "lösenord123")
        _set_field_value(view, StartupFieldName.PASSWORD_CONFIRMATION, "lösenord123")

        view.render_state(unlock_state)
        unlock_submission = view.get_submission()

        view.render_state(create_state)
        create_submission = view.get_submission()

        return {
            "unlock_password": unlock_submission.field_values[StartupFieldName.PASSWORD],
            "unlock_key_file_path": unlock_submission.field_values[StartupFieldName.KEY_FILE_PATH],
            "unlock_managed_database_hint": view.managed_database_message_var.get(),
            "create_password": create_submission.field_values[StartupFieldName.PASSWORD],
            "create_password_confirmation": create_submission.field_values[
                StartupFieldName.PASSWORD_CONFIRMATION
            ],
            "create_key_file_path": create_submission.field_values[StartupFieldName.KEY_FILE_PATH],
        }
    finally:
        view.destroy()


def _scenario_render_state_syncs_hidden_database_path_across_rerenders(root: tk.Tk) -> dict[str, object]:
    view = StartupDialogView(root)
    try:
        manual_state = StartupDialogState(
            mode=StartupDialogMode.UNLOCK,
            title="EventLog - Öppna befintlig databas",
            submit_label="Lås upp",
            dialect="sqlite",
            database_path="C:/manual/manual.db",
            min_password_length=8,
            password_policy_hint="",
            allow_emergency_reset=True,
            key_file_path="",
            uses_remembered_target=False,
            show_dialect_picker=True,
            backend_fields=(
                StartupFieldRequirement(
                    field_name=StartupFieldName.DATABASE_PATH,
                    kind=StartupFieldKind.FILE_PATH,
                    required=True,
                    editable=True,
                ),
                StartupFieldRequirement(
                    field_name=StartupFieldName.PASSWORD,
                    kind=StartupFieldKind.PASSWORD,
                ),
            ),
        )
        managed_state = StartupDialogState(
            mode=StartupDialogMode.UNLOCK,
            title="EventLog - Lås upp",
            submit_label="Lås upp",
            dialect="sqlite",
            database_path="C:/remembered/remembered.db",
            min_password_length=8,
            password_policy_hint="",
            allow_emergency_reset=True,
            key_file_path="",
            uses_remembered_target=True,
            show_dialect_picker=False,
            backend_fields=(
                StartupFieldRequirement(
                    field_name=StartupFieldName.PASSWORD,
                    kind=StartupFieldKind.PASSWORD,
                ),
            ),
        )

        view.render_state(manual_state)
        _set_field_value(view, StartupFieldName.DATABASE_PATH, "C:/stale/stale.db")

        view.render_state(managed_state)
        submission = view.get_submission()

        return {
            "database_path_manager": _field_row(view, StartupFieldName.DATABASE_PATH).winfo_manager(),
            "submission_database_path": submission.field_values[StartupFieldName.DATABASE_PATH],
            "uses_remembered_target": submission.uses_remembered_target,
            "managed_database_hint_text": view.managed_database_message_var.get(),
        }
    finally:
        view.destroy()


def _scenario_render_state_clamps_dialog_back_on_screen(root: tk.Tk) -> dict[str, object]:
    view = StartupDialogView(root)
    try:
        _apply_target_laptop_screen_metrics(view)
        view.window.geometry("640x360-180-140")
        view.window.update_idletasks()
        view.render_state(
            _make_state(
                mode=StartupDialogMode.CREATE,
                title="EventLog - Skapa krypterad databas",
                submit_label="Skapa",
                include_password_confirmation_field=True,
                include_key_file_field=True,
                allow_emergency_reset=False,
                operator="Sgt Example",
            )
        )
        view.window.update_idletasks()
        return {
            "window_x": view.window.winfo_x(),
            "window_y": view.window.winfo_y(),
            "window_width": view.window.winfo_width(),
            "window_height": view.window.winfo_height(),
            "screen_width": view.window.winfo_screenwidth(),
            "screen_height": view.window.winfo_screenheight(),
            "expected_center_x": max(view.window.winfo_screenwidth() - view.window.winfo_width(), 0) // 2,
            "expected_center_y": max(view.window.winfo_screenheight() - view.window.winfo_height(), 0) // 2,
        }
    finally:
        view.destroy()


def _scenario_small_screen_keeps_footer_visible_and_uses_scrollbar(root: tk.Tk) -> dict[str, object]:
    view = StartupDialogView(root)
    try:
        view.render_state(
            _make_state(
                mode=StartupDialogMode.CREATE,
                title="EventLog - Skapa krypterad databas",
                submit_label="Skapa",
                include_password_confirmation_field=True,
                include_key_file_field=True,
                key_file_is_required=False,
                key_file_path="C:/keys/startup.key",
                allow_emergency_reset=True,
                operator="Sgt Example",
            )
        )
        view.set_error_message("Förhandsvisning av felrad som gör dialogen högre.")
        view.set_status_message("Statusrad som också ska rymmas utan att knapparna försvinner.")
        view.window.minsize(1, 1)
        view.window.geometry("512x192")
        view.window.update_idletasks()
        view.window.update()

        submit_button_bottom = (
            view.submit_button.winfo_rooty()
            + view.submit_button.winfo_height()
            - view.window.winfo_rooty()
        )
        footer_bottom = (
            view.button_row.winfo_rooty()
            + view.button_row.winfo_height()
            - view.window.winfo_rooty()
        )

        return {
            "window_height": view.window.winfo_height(),
            "canvas_height": view.content_canvas.winfo_height(),
            "content_height": view.container.winfo_reqheight(),
            "scrollbar_manager": view.content_vertical_scrollbar.winfo_manager(),
            "submit_button_bottom": submit_button_bottom,
            "footer_bottom": footer_bottom,
            "button_separator_manager": view.button_separator.winfo_manager(),
        }
    finally:
        view.destroy()


def _scenario_target_laptop_create_fits_without_scrollbar(root: tk.Tk) -> dict[str, object]:
    view = StartupDialogView(root)
    try:
        _apply_target_laptop_screen_metrics(view)
        view.render_state(
            _make_state(
                mode=StartupDialogMode.CREATE,
                title="EventLog - Skapa krypterad databas",
                submit_label="Skapa",
                include_password_confirmation_field=True,
                include_key_file_field=True,
                key_file_is_required=False,
                allow_emergency_reset=False,
                operator="Sgt Example",
            )
        )
        view.window.update_idletasks()
        view.window.update()

        submit_button_bottom = (
            view.submit_button.winfo_rooty()
            + view.submit_button.winfo_height()
            - view.window.winfo_rooty()
        )
        footer_bottom = (
            view.button_row.winfo_rooty()
            + view.button_row.winfo_height()
            - view.window.winfo_rooty()
        )

        return {
            "window_width": view.window.winfo_width(),
            "window_height": view.window.winfo_height(),
            "canvas_height": view.content_canvas.winfo_height(),
            "content_height": view.container.winfo_reqheight(),
            "scrollbar_manager": view.content_vertical_scrollbar.winfo_manager(),
            "submit_button_bottom": submit_button_bottom,
            "footer_bottom": footer_bottom,
        }
    finally:
        view.destroy()


def _scenario_target_laptop_unlock_fits_without_scrollbar(root: tk.Tk) -> dict[str, object]:
    view = StartupDialogView(root)
    try:
        _apply_target_laptop_screen_metrics(view)
        view.render_state(
            _make_state(
                mode=StartupDialogMode.UNLOCK,
                title="EventLog - Lås upp",
                submit_label="Lås upp",
                allow_emergency_reset=True,
                uses_remembered_target=True,
                show_dialect_picker=False,
                include_database_path_field=False,
                include_key_file_field=True,
                key_file_is_required=False,
                database_path="C:/Ops/eventlog.db",
                password_policy_hint="",
            )
        )
        view.window.update_idletasks()
        view.window.update()

        submit_button_bottom = (
            view.submit_button.winfo_rooty()
            + view.submit_button.winfo_height()
            - view.window.winfo_rooty()
        )
        footer_bottom = (
            view.button_row.winfo_rooty()
            + view.button_row.winfo_height()
            - view.window.winfo_rooty()
        )

        return {
            "window_width": view.window.winfo_width(),
            "window_height": view.window.winfo_height(),
            "canvas_height": view.content_canvas.winfo_height(),
            "content_height": view.container.winfo_reqheight(),
            "scrollbar_manager": view.content_vertical_scrollbar.winfo_manager(),
            "submit_button_bottom": submit_button_bottom,
            "footer_bottom": footer_bottom,
        }
    finally:
        view.destroy()


def test_render_state_for_create_shows_managed_database_create_flow(run_tk_scenario) -> None:
    result = run_tk_scenario(_scenario_render_state_for_create)

    assert result["title"] == "EventLog - Skapa krypterad databas"
    assert result["summary_text"] == (
        "EventLog använder en apphanterad databas. Ange operatör och åtkomstuppgifter "
        "för att skapa eller återställa den lokala databasen."
    )
    assert result["user_section_manager"] == "grid"
    assert result["operator_label"] == "Operatör:"
    assert result["operator_value"] == "Sgt Example"
    assert result["submit_label"] == "Skapa"
    assert result["dialect_manager"] == "grid"
    assert result["database_path_manager"] == "grid"
    assert result["database_path_state"] == "normal"
    assert result["database_path_has_browse_button"] is False
    assert result["password_confirmation_manager"] == "grid"
    assert result["password_policy_hint_visible"] is True
    assert result["password_policy_hint_text"] == "Minst 8 tecken för nytt lösenord."
    assert result["key_file_manager"] == "grid"
    assert result["key_file_label"] == "Nyckelfil (valfritt):"
    assert result["key_file_has_browse_button"] is True
    assert result["key_file_value"] == "C:/keys/startup.key"
    assert result["managed_database_hint_visible"] is False
    assert result["visible_field_names"] == [
        StartupFieldName.DATABASE_PATH,
        StartupFieldName.PASSWORD,
        StartupFieldName.PASSWORD_CONFIRMATION,
        StartupFieldName.KEY_FILE_PATH,
    ]
    assert result["emergency_reset_manager"] == ""
    assert result["has_target_source_row"] is False
    assert result["has_manual_target_button"] is False
    assert result["resizable"] == (True, True)


def test_render_state_for_managed_unlock_shows_locked_database_hint_and_hides_target_selection(
    run_tk_scenario,
) -> None:
    result = run_tk_scenario(_scenario_render_state_for_managed_unlock)

    assert result["title"] == "EventLog - Lås upp"
    assert result["summary_text"] == (
        "EventLog använder en apphanterad databas. Ange operatör och åtkomstuppgifter "
        "för att låsa upp den lokala databasen."
    )
    assert result["submit_label"] == "Lås upp"
    assert result["dialect_manager"] == ""
    assert result["database_path_manager"] == ""
    assert result["managed_database_hint_visible"] is True
    assert result["managed_database_hint_text"] == "Apphanterad databassökväg:\nC:/Ops/eventlog.db"
    assert result["password_policy_hint_visible"] is False
    assert result["key_file_manager"] == ""
    assert result["emergency_reset_manager"] == "grid"
    assert result["emergency_reset_class"] == "Button"
    assert result["emergency_reset_background"] == "#c62828"
    assert result["danger_action_frame_manager"] == "grid"
    assert result["button_separator_manager"] == "grid"


def test_render_state_for_neutral_create_keeps_only_database_path_field_without_browse_button(
    run_tk_scenario,
) -> None:
    result = run_tk_scenario(_scenario_render_state_for_neutral_create)

    assert result["title"] == "EventLog - Välj eller skapa databas"
    assert result["summary_text"] == (
        "EventLog använder en apphanterad databas. Ange operatör och åtkomstuppgifter "
        "för att skapa eller återställa den lokala databasen."
    )
    assert result["database_path_manager"] == "grid"
    assert result["database_path_has_browse_button"] is False
    assert result["password_manager"] == ""
    assert result["password_confirmation_manager"] == ""
    assert result["key_file_manager"] == ""
    assert result["managed_database_hint_visible"] is False


def test_get_submission_returns_current_field_values(run_tk_scenario) -> None:
    result = run_tk_scenario(_scenario_get_submission)

    assert result["mode"] is StartupDialogMode.UNLOCK
    assert result["dialect"] == "sqlite"
    assert result["operator"] == "Sgt Example"
    assert result["uses_remembered_target"] is True
    assert result["field_values"] == {
        StartupFieldName.DATABASE_PATH: "C:/data/eventlog.db",
        StartupFieldName.PASSWORD: "lösenord123",
        StartupFieldName.PASSWORD_CONFIRMATION: "lösenord123",
        StartupFieldName.KEY_FILE_PATH: "   ",
    }


def test_callbacks_are_invoked_by_visible_buttons_and_submission_events(run_tk_scenario) -> None:
    result = run_tk_scenario(_scenario_invoke_callbacks)

    assert result["database_path_has_browse_button"] is False
    assert result["events"] == [
        "submit",
        "cancel",
        "reset",
        "browse-key-file",
        "submission-changed",
        "submission-changed",
        "cancel",
    ]


def test_pressing_enter_in_password_field_invokes_submit_when_enabled(run_tk_scenario) -> None:
    result = run_tk_scenario(_scenario_press_enter_in_password_field)

    assert result["events"] == ["submit"]
    assert result["focused_widget_class"] == "TEntry"


def test_clear_sensitive_fields_only_clears_confirmation_when_requested(run_tk_scenario) -> None:
    result = run_tk_scenario(_scenario_clear_sensitive_fields)

    assert result["after_first_password"] == ""
    assert result["after_first_confirmation"] == "upprepat"
    assert result["after_second_confirmation"] == ""


def test_render_state_without_selected_dialect_hides_backend_fields_and_remains_resizable(
    run_tk_scenario,
) -> None:
    result = run_tk_scenario(_scenario_render_state_without_selected_dialect)

    assert result["title_without_dialect"] == "EventLog - Välj eller skapa databas"
    assert result["summary_without_dialect"] == (
        "EventLog använder en apphanterad databas. Ange operatör och åtkomstuppgifter "
        "för att skapa eller återställa den lokala databasen."
    )
    assert result["dialect_value"] == "sqlite"
    assert result["managers_without_dialect"] == {
        "database_path": "",
        "password": "",
        "key_file": "",
    }
    assert result["password_policy_hint_visible_without_dialect"] is False
    assert result["database_path_manager_with_sqlite"] == "grid"
    assert result["password_manager_with_sqlite"] == "grid"
    assert result["password_policy_hint_visible_with_sqlite"] is True
    assert result["password_policy_hint_text_with_sqlite"] == "Minst 8 tecken för nytt lösenord."
    assert result["key_file_manager_with_sqlite"] == "grid"
    assert result["size_without_dialect"][0] >= 640
    assert result["size_without_dialect"][1] >= 360
    assert result["size_with_sqlite"][0] >= 640
    assert result["size_with_sqlite"][1] >= 360
    assert result["focus_without_dialect"] in {"TEntry", "Toplevel"}
    assert result["resizable"] == (True, True)


def test_render_state_preserves_visible_field_values_across_rerenders(run_tk_scenario) -> None:
    result = run_tk_scenario(_scenario_render_state_preserves_visible_field_values_across_rerenders)

    assert result["unlock_password"] == "lösenord123"
    assert result["unlock_key_file_path"] == "C:/keys/startup.key"
    assert result["unlock_managed_database_hint"] == ""
    assert result["create_password"] == "lösenord123"
    assert result["create_password_confirmation"] == "lösenord123"
    assert result["create_key_file_path"] == "C:/keys/startup.key"


def test_render_state_syncs_hidden_database_path_across_rerenders(run_tk_scenario) -> None:
    result = run_tk_scenario(_scenario_render_state_syncs_hidden_database_path_across_rerenders)

    assert result["database_path_manager"] == ""
    assert result["submission_database_path"] == "C:/remembered/remembered.db"
    assert result["uses_remembered_target"] is True
    assert result["managed_database_hint_text"] == "Apphanterad databassökväg:\nC:/remembered/remembered.db"


def test_render_state_clamps_dialog_back_on_screen(run_tk_scenario) -> None:
    result = run_tk_scenario(_scenario_render_state_clamps_dialog_back_on_screen)

    assert result["window_x"] >= 0
    assert result["window_y"] >= 0
    assert result["window_x"] + result["window_width"] <= result["screen_width"]
    assert result["window_y"] + result["window_height"] <= result["screen_height"]
    assert result["window_x"] == result["expected_center_x"]
    assert result["window_y"] == result["expected_center_y"]


def test_small_screen_keeps_footer_visible_and_uses_scrollbar_fallback(run_tk_scenario) -> None:
    result = run_tk_scenario(_scenario_small_screen_keeps_footer_visible_and_uses_scrollbar)

    assert result["window_height"] <= 192
    assert result["content_height"] > result["canvas_height"]
    assert result["scrollbar_manager"] == "grid"
    assert result["submit_button_bottom"] <= result["window_height"]
    assert result["footer_bottom"] <= result["window_height"]
    assert result["button_separator_manager"] == "grid"


def test_target_laptop_create_flow_fits_without_scrollbar(run_tk_scenario) -> None:
    result = run_tk_scenario(_scenario_target_laptop_create_fits_without_scrollbar)

    assert result["window_width"] <= TARGET_LAPTOP_DIALOG_MAX_WIDTH
    assert result["window_height"] <= TARGET_LAPTOP_DIALOG_MAX_HEIGHT
    assert result["content_height"] <= result["canvas_height"]
    assert result["scrollbar_manager"] == ""
    assert result["submit_button_bottom"] <= result["window_height"]
    assert result["footer_bottom"] <= result["window_height"]


def test_target_laptop_unlock_flow_fits_without_scrollbar(run_tk_scenario) -> None:
    result = run_tk_scenario(_scenario_target_laptop_unlock_fits_without_scrollbar)

    assert result["window_width"] <= TARGET_LAPTOP_DIALOG_MAX_WIDTH
    assert result["window_height"] <= TARGET_LAPTOP_DIALOG_MAX_HEIGHT
    assert result["content_height"] <= result["canvas_height"]
    assert result["scrollbar_manager"] == ""
    assert result["submit_button_bottom"] <= result["window_height"]
    assert result["footer_bottom"] <= result["window_height"]



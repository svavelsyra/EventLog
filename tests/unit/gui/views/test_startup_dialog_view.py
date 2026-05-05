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
from src.gui.views.startup_dialog_view import StartupDialogView


pytestmark = pytest.mark.unit


def _make_state(
    *,
    mode: StartupDialogMode,
    title: str,
    submit_label: str,
    password_policy_hint: str = "Minst 8 tecken för nytt lösenord.",
    allow_emergency_reset: bool,
    uses_remembered_target: bool = False,
    remembered_target_is_available: bool = False,
    show_target_source_selector: bool = False,
    show_dialect_picker: bool = True,
    include_database_path_field: bool = True,
    database_path_is_editable: bool = True,
    include_password_confirmation_field: bool = False,
    include_key_file_field: bool = False,
    key_file_is_required: bool = False,
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
        database_path="eventlog.db",
        min_password_length=8,
        password_policy_hint=password_policy_hint,
        allow_emergency_reset=allow_emergency_reset,
        uses_remembered_target=uses_remembered_target,
        remembered_target_is_available=remembered_target_is_available,
        show_target_source_selector=show_target_source_selector,
        show_dialect_picker=show_dialect_picker,
        backend_fields=tuple(backend_fields),
    )


def _field_row(view: StartupDialogView, field_name: StartupFieldName):
    return view._field_widgets[field_name].row


def _field_label(view: StartupDialogView, field_name: StartupFieldName) -> str:
    return str(view._field_widgets[field_name].label.cget("text"))


def _field_entry_state(view: StartupDialogView, field_name: StartupFieldName) -> str:
    return str(view._field_widgets[field_name].entry.cget("state"))


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
                allow_emergency_reset=False,
            )
        )
        view.window.update_idletasks()
        return {
            "title": view.window.title(),
            "summary_text": view.summary_label.cget("text"),
            "submit_label": view.submit_button.cget("text"),
            "mode_manager": view.mode_row.winfo_manager(),
            "mode_value": view.mode_var.get(),
            "target_source_manager": view.target_source_row.winfo_manager(),
            "target_source_value": view.use_remembered_target_var.get(),
            "dialect_manager": view.dialect_row.winfo_manager(),
            "database_path_manager": _field_row(view, StartupFieldName.DATABASE_PATH).winfo_manager(),
            "database_path_state": _field_entry_state(view, StartupFieldName.DATABASE_PATH),
            "password_confirmation_manager": _field_row(
                view,
                StartupFieldName.PASSWORD_CONFIRMATION,
            ).winfo_manager(),
            "password_policy_hint_visible": bool(view.password_policy_hint_label.winfo_ismapped()),
            "password_policy_hint_text": view.password_policy_hint_label.cget("text"),
            "key_file_manager": _field_row(view, StartupFieldName.KEY_FILE_PATH).winfo_manager(),
            "key_file_label": _field_label(view, StartupFieldName.KEY_FILE_PATH),
            "visible_field_names": [
                widgets.requirement.field_name
                for widgets in view._field_widgets.values()
                if widgets.row.winfo_manager()
            ],
            "emergency_reset_manager": view.emergency_reset_button.winfo_manager(),
        }
    finally:
        view.destroy()



def _scenario_render_state_for_unlock_using_remembered_target(root: tk.Tk) -> dict[str, object]:
    view = StartupDialogView(root)
    try:
        view.render_state(
            _make_state(
                mode=StartupDialogMode.UNLOCK,
                title="EventLog - Lås upp",
                submit_label="Lås upp",
                allow_emergency_reset=True,
                uses_remembered_target=True,
                remembered_target_is_available=True,
                show_target_source_selector=True,
                show_dialect_picker=False,
                include_database_path_field=False,
                database_path_is_editable=False,
                password_policy_hint="",
            )
        )
        view.window.update_idletasks()
        return {
            "title": view.window.title(),
            "summary_text": view.summary_label.cget("text"),
            "submit_label": view.submit_button.cget("text"),
            "mode_value": view.mode_var.get(),
            "target_source_manager": view.target_source_row.winfo_manager(),
            "target_source_value": view.use_remembered_target_var.get(),
            "dialect_manager": view.dialect_row.winfo_manager(),
            "database_path_manager": _field_row(view, StartupFieldName.DATABASE_PATH).winfo_manager(),
            "password_confirmation_manager": _field_row(
                view,
                StartupFieldName.PASSWORD_CONFIRMATION,
            ).winfo_manager(),
            "password_policy_hint_visible": bool(view.password_policy_hint_label.winfo_ismapped()),
            "key_file_manager": _field_row(view, StartupFieldName.KEY_FILE_PATH).winfo_manager(),
            "emergency_reset_manager": view.emergency_reset_button.winfo_manager(),
        }
    finally:
        view.destroy()



def _scenario_render_state_for_manual_unlock(root: tk.Tk) -> dict[str, object]:
    view = StartupDialogView(root)
    try:
        view.render_state(
            _make_state(
                mode=StartupDialogMode.UNLOCK,
                title="EventLog - Öppna befintlig databas",
                submit_label="Lås upp",
                include_key_file_field=True,
                key_file_is_required=False,
                allow_emergency_reset=True,
                uses_remembered_target=False,
                remembered_target_is_available=True,
                show_target_source_selector=True,
                show_dialect_picker=True,
                database_path_is_editable=True,
                password_policy_hint="",
            )
        )
        view.window.update_idletasks()
        return {
            "title": view.window.title(),
            "summary_text": view.summary_label.cget("text"),
            "mode_value": view.mode_var.get(),
            "target_source_manager": view.target_source_row.winfo_manager(),
            "target_source_value": view.use_remembered_target_var.get(),
            "dialect_manager": view.dialect_row.winfo_manager(),
            "database_path_manager": _field_row(view, StartupFieldName.DATABASE_PATH).winfo_manager(),
            "database_path_state": _field_entry_state(view, StartupFieldName.DATABASE_PATH),
            "password_policy_hint_visible": bool(view.password_policy_hint_label.winfo_ismapped()),
            "password_policy_hint_text": view.password_policy_hint_label.cget("text"),
            "key_file_manager": _field_row(view, StartupFieldName.KEY_FILE_PATH).winfo_manager(),
            "key_file_label": _field_label(view, StartupFieldName.KEY_FILE_PATH),
        }
    finally:
        view.destroy()



def _scenario_get_submission(root: tk.Tk) -> dict[str, object]:
    view = StartupDialogView(root)
    try:
        view.dialect_var.set("sqlite")
        view.set_field_value(StartupFieldName.DATABASE_PATH, "C:/data/eventlog.db")
        view.set_field_value(StartupFieldName.PASSWORD, "lösenord123")
        view.set_field_value(StartupFieldName.PASSWORD_CONFIRMATION, "lösenord123")
        view.set_field_value(StartupFieldName.KEY_FILE_PATH, "   ")

        submission = view.get_submission(mode=StartupDialogMode.CREATE)
        return {
            "mode": submission.mode,
            "dialect": submission.dialect,
            "uses_remembered_target": submission.uses_remembered_target,
            "field_values": dict(submission.field_values),
        }
    finally:
        view.destroy()



def _scenario_invoke_callbacks(root: tk.Tk) -> list[str]:
    view = StartupDialogView(root)
    try:
        events: list[str] = []
        view.set_submit_callback(lambda: events.append("submit"))
        view.set_cancel_callback(lambda: events.append("cancel"))
        view.set_emergency_reset_callback(lambda: events.append("reset"))
        view.set_browse_database_callback(lambda: events.append("browse-database"))
        view.set_browse_key_file_callback(lambda: events.append("browse"))

        view.submit_button.invoke()
        view.cancel_button.invoke()
        view.emergency_reset_button.invoke()
        view._field_widgets[StartupFieldName.DATABASE_PATH].browse_button.invoke()
        view._field_widgets[StartupFieldName.KEY_FILE_PATH].browse_button.invoke()
        view.handle_close_requested()
        return events
    finally:
        view.destroy()



def _scenario_clear_sensitive_fields(root: tk.Tk) -> dict[str, str]:
    view = StartupDialogView(root)
    try:
        view.set_field_value(StartupFieldName.PASSWORD, "lösenord123")
        view.set_field_value(StartupFieldName.PASSWORD_CONFIRMATION, "upprepat")
        view.clear_sensitive_fields(clear_password_confirmation=False)
        after_first_clear = {
            "password": view.get_field_value(StartupFieldName.PASSWORD),
            "password_confirmation": view.get_field_value(StartupFieldName.PASSWORD_CONFIRMATION),
        }

        view.clear_sensitive_fields(clear_password_confirmation=True)
        after_second_clear = {
            "password": view.get_field_value(StartupFieldName.PASSWORD),
            "password_confirmation": view.get_field_value(StartupFieldName.PASSWORD_CONFIRMATION),
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
            title="EventLog - Skapa krypterad databas",
            submit_label="Skapa",
            dialect="",
            database_path="",
            min_password_length=8,
            password_policy_hint="Minst 8 tecken för nytt lösenord.",
            allow_emergency_reset=False,
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

        view.render_state(full_state)
        view.window.update_idletasks()
        size_with_sqlite = (view.window.winfo_width(), view.window.winfo_height())

        return {
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
            allow_emergency_reset=False,
        )
        manual_unlock_state = _make_state(
            mode=StartupDialogMode.UNLOCK,
            title="EventLog - Öppna befintlig databas",
            submit_label="Lås upp",
            include_key_file_field=True,
            key_file_is_required=False,
            allow_emergency_reset=True,
            uses_remembered_target=False,
            remembered_target_is_available=True,
            show_target_source_selector=True,
            show_dialect_picker=True,
            password_policy_hint="",
        )

        view.render_state(create_state)
        view.set_field_value(StartupFieldName.PASSWORD, "lösenord123")
        view.set_field_value(StartupFieldName.PASSWORD_CONFIRMATION, "lösenord123")
        view.set_field_value(StartupFieldName.KEY_FILE_PATH, "C:/keys/startup.key")

        view.render_state(manual_unlock_state)
        unlock_submission = view.get_submission(mode=StartupDialogMode.UNLOCK)

        view.render_state(create_state)
        create_submission = view.get_submission(mode=StartupDialogMode.CREATE)

        return {
            "unlock_password": unlock_submission.field_values[StartupFieldName.PASSWORD],
            "unlock_key_file_path": unlock_submission.field_values[StartupFieldName.KEY_FILE_PATH],
            "create_password": create_submission.field_values[StartupFieldName.PASSWORD],
            "create_password_confirmation": create_submission.field_values[
                StartupFieldName.PASSWORD_CONFIRMATION
            ],
            "create_key_file_path": create_submission.field_values[StartupFieldName.KEY_FILE_PATH],
        }
    finally:
        view.destroy()


def test_render_state_for_create_shows_confirmation_and_optional_key_file(
    run_tk_scenario,
) -> None:
    result = run_tk_scenario(_scenario_render_state_for_create)

    assert result["title"] == "EventLog - Skapa krypterad databas"
    assert result["summary_text"] == "EventLog - Skapa krypterad databas"
    assert result["submit_label"] == "Skapa"
    assert result["mode_manager"] == ""
    assert result["mode_value"] == StartupDialogMode.CREATE.value
    assert result["target_source_manager"] == ""
    assert result["target_source_value"] is False
    assert result["dialect_manager"] == "grid"
    assert result["database_path_manager"] == "grid"
    assert result["database_path_state"] == "normal"
    assert result["password_confirmation_manager"] == "grid"
    assert result["password_policy_hint_visible"] is True
    assert result["password_policy_hint_text"] == "Minst 8 tecken för nytt lösenord."
    assert result["key_file_manager"] == "grid"
    assert result["key_file_label"] == "Nyckelfil (valfritt):"
    assert result["visible_field_names"] == [
        StartupFieldName.DATABASE_PATH,
        StartupFieldName.PASSWORD,
        StartupFieldName.PASSWORD_CONFIRMATION,
        StartupFieldName.KEY_FILE_PATH,
    ]
    assert result["emergency_reset_manager"] == ""


def test_render_state_for_unlock_using_remembered_target_hides_manual_target_fields(
    run_tk_scenario,
) -> None:
    result = run_tk_scenario(_scenario_render_state_for_unlock_using_remembered_target)

    assert result["title"] == "EventLog - Lås upp"
    assert result["summary_text"] == "EventLog - Lås upp"
    assert result["submit_label"] == "Lås upp"
    assert result["mode_value"] == StartupDialogMode.UNLOCK.value
    assert result["target_source_manager"] == "grid"
    assert result["target_source_value"] is True
    assert result["dialect_manager"] == ""
    assert result["database_path_manager"] == ""
    assert result["password_confirmation_manager"] == ""
    assert result["password_policy_hint_visible"] is False
    assert result["key_file_manager"] == ""
    assert result["emergency_reset_manager"] == "grid"


def test_render_state_for_manual_unlock_shows_database_target_fields(run_tk_scenario) -> None:
    result = run_tk_scenario(_scenario_render_state_for_manual_unlock)

    assert result["title"] == "EventLog - Öppna befintlig databas"
    assert result["summary_text"] == "EventLog - Öppna befintlig databas"
    assert result["mode_value"] == StartupDialogMode.UNLOCK.value
    assert result["target_source_manager"] == "grid"
    assert result["target_source_value"] is False
    assert result["dialect_manager"] == "grid"
    assert result["database_path_manager"] == "grid"
    assert result["database_path_state"] == "normal"
    assert result["password_policy_hint_visible"] is False
    assert result["password_policy_hint_text"] == ""
    assert result["key_file_manager"] == "grid"
    assert result["key_file_label"] == "Nyckelfil (valfritt):"


def test_get_submission_returns_current_field_values_and_blank_key_file_as_none(
    run_tk_scenario,
) -> None:
    result = run_tk_scenario(_scenario_get_submission)

    assert result["mode"] is StartupDialogMode.CREATE
    assert result["dialect"] == "sqlite"
    assert result["uses_remembered_target"] is False
    assert result["field_values"] == {
        StartupFieldName.DATABASE_PATH: "C:/data/eventlog.db",
        StartupFieldName.PASSWORD: "lösenord123",
        StartupFieldName.PASSWORD_CONFIRMATION: "lösenord123",
        StartupFieldName.KEY_FILE_PATH: "   ",
    }


def test_callbacks_are_invoked_by_buttons_and_close_protocol(run_tk_scenario) -> None:
    events = run_tk_scenario(_scenario_invoke_callbacks)

    assert events == ["submit", "cancel", "reset", "browse-database", "browse", "cancel"]


def test_clear_sensitive_fields_only_clears_confirmation_when_requested(run_tk_scenario) -> None:
    result = run_tk_scenario(_scenario_clear_sensitive_fields)

    assert result["after_first_password"] == ""
    assert result["after_first_confirmation"] == "upprepat"
    assert result["after_second_confirmation"] == ""


def test_render_state_without_selected_dialect_hides_backend_fields_and_keeps_fixed_size(
    run_tk_scenario,
) -> None:
    result = run_tk_scenario(_scenario_render_state_without_selected_dialect)

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
    assert result["size_without_dialect"] == result["size_with_sqlite"]
    assert result["focus_without_dialect"] == "TCombobox"


def test_render_state_preserves_visible_field_values_across_rerenders(run_tk_scenario) -> None:
    result = run_tk_scenario(_scenario_render_state_preserves_visible_field_values_across_rerenders)

    assert result["unlock_password"] == "lösenord123"
    assert result["unlock_key_file_path"] == "C:/keys/startup.key"
    assert result["create_password"] == "lösenord123"
    assert result["create_password_confirmation"] == "lösenord123"
    assert result["create_key_file_path"] == "C:/keys/startup.key"







from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
import json
from pathlib import Path
from typing import cast

import pytest

from src.core import CommunicationConfigLoader, CommunicationEntry
from src.core.app_runtime_state import AppRuntimeState
from src.core.communication_config import CommunicationConfigSource
from src.core.communication_portability import import_communication_portability_payload
from src.gui.presenters.communication_presenter import (
    CommunicationEditorState,
    CommunicationEntryDetailState,
    CommunicationFormData,
    CommunicationLogFilterData,
    CommunicationFormState,
    CommunicationLogRow,
    CommunicationLogState,
    CommunicationPresenter,
)
from src.db.repositories.sqlite.event_log_repository import EventLogRepository
from tests.unit.db.db_test_utils import set_communication_logged_time


pytestmark = pytest.mark.unit


_UI_VARIANT_PAYLOAD_PATH = Path(__file__).resolve().parents[3] / "data" / "communication_ui_variants.json"


def _as_config_source(repository: EventLogRepository) -> CommunicationConfigSource:
    return cast(CommunicationConfigSource, cast(object, repository))


def _load_ui_variant_payload() -> dict[str, object]:
    with _UI_VARIANT_PAYLOAD_PATH.open("r", encoding="utf-8") as payload_file:
        return cast(dict[str, object], json.load(payload_file))


def _replace_runtime_config_with_ui_variants(repository: EventLogRepository) -> None:
    import_communication_portability_payload(
        _load_ui_variant_payload(),
        import_target=repository,
        config_loader=CommunicationConfigLoader(_as_config_source(repository)),
    )


class MockCommunicationView:
    def __init__(
        self,
        form_data: CommunicationFormData | None = None,
        log_filter_data: CommunicationLogFilterData | None = None,
    ) -> None:
        self.form_data = form_data or CommunicationFormData()
        self.log_filter_data = log_filter_data or CommunicationLogFilterData()
        self.save_handler: Callable[[], None] | None = None
        self.clear_handler: Callable[[], None] | None = None
        self.swap_handler: Callable[[], None] | None = None
        self.config_change_handler: Callable[[], None] | None = None
        self.apply_filters_handler: Callable[[], None] | None = None
        self.clear_filters_handler: Callable[[], None] | None = None
        self.open_selected_handler: Callable[[], None] | None = None
        self.edit_selected_handler: Callable[[], None] | None = None
        self.delete_selected_handler: Callable[[], None] | None = None
        self.sort_requested_handler: Callable[[str], None] | None = None
        self.selection_changed_handler: Callable[[int | None], None] | None = None
        self.rendered_rows: list[CommunicationLogRow] = []
        self.rendered_log_state: CommunicationLogState | None = None
        self.rendered_form_state: CommunicationFormState | None = None
        self.rendered_editor_state: CommunicationEditorState | None = None
        self.feedback_messages: list[tuple[str, bool]] = []
        self.warning_dialogs: list[tuple[str, str]] = []
        self.detail_states: list[CommunicationEntryDetailState] = []
        self.delete_confirmation_calls: list[tuple[str, str]] = []
        self.confirm_delete_result = True

    def set_save_handler(self, callback: Callable[[], None]) -> None:
        self.save_handler = callback

    def set_clear_handler(self, callback: Callable[[], None]) -> None:
        self.clear_handler = callback

    def set_swap_handler(self, callback: Callable[[], None]) -> None:
        self.swap_handler = callback

    def set_config_change_handler(self, callback: Callable[[], None]) -> None:
        self.config_change_handler = callback

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
        self.apply_filters_handler = on_apply_filters
        self.clear_filters_handler = on_clear_filters
        self.open_selected_handler = on_open_selected
        self.edit_selected_handler = on_edit_selected
        self.delete_selected_handler = on_delete_selected
        self.sort_requested_handler = on_sort_requested
        self.selection_changed_handler = on_selection_changed

    def get_form_data(self) -> CommunicationFormData:
        return self.form_data

    def get_log_filter_data(self) -> CommunicationLogFilterData:
        return self.log_filter_data

    def set_form_data(self, form_data: CommunicationFormData) -> None:
        self.form_data = form_data

    def render_form_state(self, form_state: CommunicationFormState) -> None:
        self.rendered_form_state = form_state

    def render_editor_state(self, editor_state: CommunicationEditorState) -> None:
        self.rendered_editor_state = editor_state

    def render_log_state(self, log_state: CommunicationLogState) -> None:
        self.rendered_log_state = log_state
        self.rendered_rows = list(log_state.rows)
        self.log_filter_data = log_state.filter_data

    def set_feedback_message(self, message: str, *, is_error: bool = False) -> None:
        self.feedback_messages.append((message, is_error))

    def show_warning_dialog(self, title: str, message: str) -> None:
        self.warning_dialogs.append((title, message))

    def show_entry_details(self, detail_state: CommunicationEntryDetailState) -> None:
        self.detail_states.append(detail_state)

    def confirm_delete_entry(self, title: str, message: str) -> bool:
        self.delete_confirmation_calls.append((title, message))
        return self.confirm_delete_result


def test_attach_binds_callbacks_and_loads_existing_rows(repository) -> None:
    repository.create_communication_entry(
        CommunicationEntry(
            message_content="Lägesrapport mottagen.",
            operator="Operatör Ett",
            event_time=datetime(2026, 5, 12, 9, 15),
            from_field="Alpha",
            to_field="GC",
            communication_system="RA180",
        )
    )
    repository.create_communication_entry(
        CommunicationEntry(
            message_content="",
            operator="",
            event_time=None,
            from_field="Bravo",
            to_field="GC",
            communication_system="Telefon",
        )
    )
    view = MockCommunicationView()
    presenter = CommunicationPresenter(repository, view, AppRuntimeState(active_operator="Sgt Example"))

    presenter.attach()

    assert view.save_handler is not None
    assert view.clear_handler is not None
    assert view.swap_handler is not None
    assert view.config_change_handler is not None
    assert view.apply_filters_handler is not None
    assert view.clear_filters_handler is not None
    assert view.open_selected_handler is not None
    assert view.edit_selected_handler is not None
    assert view.delete_selected_handler is not None
    assert view.sort_requested_handler is not None
    assert view.selection_changed_handler is not None
    assert view.save_handler == presenter.on_save_clicked
    assert view.clear_handler == presenter.on_clear_clicked
    assert view.swap_handler == presenter.on_swap_clicked
    assert view.config_change_handler == presenter.on_config_changed
    assert view.rendered_form_state is not None
    assert view.rendered_editor_state is not None
    assert view.rendered_log_state is not None
    assert view.rendered_form_state.system_choices == ("RA180", "Motorola", "Rakel", "Kurir", "Telefon")
    assert view.rendered_form_state.path_fields == ()
    assert view.rendered_log_state.filter_data == CommunicationLogFilterData()
    assert view.rendered_log_state.sort_column == "time"
    assert view.rendered_log_state.sort_descending is True
    assert view.rendered_log_state.system_filter_choices == ("RA180", "Motorola", "Rakel", "Kurir", "Telefon")
    assert view.rendered_editor_state == CommunicationEditorState()
    assert len(view.rendered_rows) == 2
    assert view.rendered_rows[0].message_text == "Lägesrapport mottagen."
    assert view.rendered_rows[1].needs_review is True
    assert view.rendered_rows[1].status_text == "SE ÖVER"
    assert view.rendered_rows[1].time_text == "OGILTIG TID"


def test_on_save_clicked_saves_entry_and_preserves_only_approved_carry_forward_fields(repository) -> None:
    view = MockCommunicationView(
        CommunicationFormData(
            time_text="",
            from_field="Ledning",
            to_field="1. pluton",
            message_content="Bekräfta framryckning.",
            communication_system="RA180",
        )
    )
    fixed_now = datetime(2026, 5, 12, 14, 30)
    presenter = CommunicationPresenter(
        repository,
        view,
        AppRuntimeState(active_operator="  Sgt Example  "),
        now_provider=lambda: fixed_now,
    )

    presenter.on_save_clicked()

    entries = repository.get_all_communication_entries()
    assert len(entries) == 1
    entry = entries[0]
    assert entry.event_time == fixed_now
    assert entry.message_content == "Bekräfta framryckning."
    assert entry.operator == "Sgt Example"
    assert entry.from_field == "Ledning"
    assert entry.to_field == "1. pluton"
    assert entry.communication_system == "RA180"
    assert entry.system_capabilities == {
        "communication_path": [],
        "communication_qualifiers": {
            "data": True,
            "encrypted": True,
        },
    }
    assert view.form_data == CommunicationFormData(
        from_field="Ledning",
        to_field="1. pluton",
        communication_system="RA180",
        communication_qualifiers={
            "data": True,
            "encrypted": True,
        },
    )
    assert view.warning_dialogs == []
    assert view.feedback_messages[-1] == ("Kommunikationspost sparad.", False)
    assert view.rendered_log_state is not None
    assert len(view.rendered_rows) == 1
    assert view.rendered_rows[0].needs_review is False


def test_on_save_clicked_soft_saves_invalid_time_and_blank_message_and_operator(repository, caplog) -> None:
    view = MockCommunicationView(
        CommunicationFormData(
            time_text="inte en tid",
            from_field="Alpha",
            to_field="Bravo",
            message_content="   ",
            communication_system="RA146",
        )
    )
    presenter = CommunicationPresenter(
        repository,
        view,
        AppRuntimeState(active_operator="   "),
        now_provider=lambda: datetime(2026, 5, 12, 16, 45),
    )

    with caplog.at_level("WARNING"):
        presenter.on_save_clicked()

    entries = repository.get_all_communication_entries()
    assert len(entries) == 1
    entry = entries[0]
    assert entry.event_time is None
    assert entry.message_content == ""
    assert entry.operator == ""
    assert entry.communication_system is None
    assert view.feedback_messages[-1] == ("Post sparad, men behöver ses över.", False)
    assert view.warning_dialogs == [
        (
            "Post sparad, men behöver ses över",
            "Post sparad, men behöver ses över.\n\n"
            "Följande fält kan behöva granskas senare:\n"
            "- Tid – kunde inte tolkas\n"
            "- Meddelande – saknar innehåll\n"
            "- Operatör – saknar värde",
        )
    ]
    assert (
        "Kommunikationspost sparad men behöver ses över: ogiltig tid; meddelande saknar innehåll; operatör saknar värde"
        in caplog.text
    )
    assert len(view.rendered_rows) == 1
    assert view.rendered_rows[0].needs_review is True
    assert view.rendered_rows[0].status_text == "SE ÖVER"
    assert view.rendered_rows[0].time_text == "OGILTIG TID"


def test_on_swap_clicked_swaps_from_and_to_without_touching_other_fields(repository) -> None:
    view = MockCommunicationView(
        CommunicationFormData(
            time_text="120945",
            from_field="Alpha",
            to_field="Bravo",
            message_content="Svara.",
            communication_system="RA180",
        )
    )
    presenter = CommunicationPresenter(repository, view, AppRuntimeState(active_operator="Sgt Example"))

    presenter.on_swap_clicked()

    assert view.form_data == CommunicationFormData(
        time_text="120945",
        from_field="Bravo",
        to_field="Alpha",
        message_content="Svara.",
        communication_system="RA180",
        communication_qualifiers={
            "data": True,
            "encrypted": True,
        },
    )
    assert view.feedback_messages[-1] == ("Från och Till bytte plats.", False)


def test_on_filters_applied_uses_and_based_sender_recipient_time_system_and_text_filters(repository) -> None:
    repository.create_communication_entry(
        CommunicationEntry(
            message_content="Framryckning klar.",
            operator="Operatör Ett",
            event_time=datetime(2026, 5, 12, 10, 15),
            from_field="Alpha",
            to_field="GC",
            communication_system="RA180",
        )
    )
    repository.create_communication_entry(
        CommunicationEntry(
            message_content="Framryckning stoppad.",
            operator="Operatör Två",
            event_time=datetime(2026, 5, 12, 10, 20),
            from_field="Alpha",
            to_field="Stab",
            communication_system="RA180",
        )
    )
    repository.create_communication_entry(
        CommunicationEntry(
            message_content="Framryckning klar.",
            operator="Operatör Tre",
            event_time=datetime(2026, 5, 12, 12, 0),
            from_field="Alpha",
            to_field="GC",
            communication_system="Telefon",
        )
    )
    view = MockCommunicationView()
    presenter = CommunicationPresenter(repository, view, AppRuntimeState(active_operator="Sgt Example"))

    presenter.attach()
    view.log_filter_data = CommunicationLogFilterData(
        time_from_text="2026-05-12 10:00",
        time_to_text="26-05-12 11:00",
        from_text="alp",
        to_text="gc",
        system_text="ra180",
        message_text="klar",
    )

    presenter.on_filters_applied()

    assert view.rendered_log_state is not None
    assert view.rendered_log_state.filter_data == CommunicationLogFilterData(
        time_from_text="2026-05-12 10:00",
        time_to_text="26-05-12 11:00",
        from_text="alp",
        to_text="gc",
        system_text="ra180",
        message_text="klar",
    )
    assert [row.from_text for row in view.rendered_rows] == ["Alpha"]
    assert [row.to_text for row in view.rendered_rows] == ["GC"]
    assert [row.method_text for row in view.rendered_rows] == ["RA180"]
    assert view.feedback_messages[-1] == ("Filter uppdaterade.", False)

    presenter.on_filters_cleared()

    assert view.rendered_log_state is not None
    assert view.rendered_log_state.filter_data == CommunicationLogFilterData()
    assert len(view.rendered_rows) == 3
    assert view.feedback_messages[-1] == ("Filter rensade.", False)


def test_on_filters_applied_rejects_invalid_exact_datetime_without_replacing_active_filters(repository) -> None:
    repository.create_communication_entry(
        CommunicationEntry(
            message_content="Lägesrapport.",
            operator="Operatör Ett",
            event_time=datetime(2026, 5, 12, 10, 15),
            from_field="Alpha",
            to_field="GC",
            communication_system="RA180",
        )
    )
    view = MockCommunicationView()
    presenter = CommunicationPresenter(repository, view, AppRuntimeState(active_operator="Sgt Example"))

    presenter.attach()
    original_rows = list(view.rendered_rows)
    view.log_filter_data = CommunicationLogFilterData(time_from_text="2026/05/12 10:00")

    presenter.on_filters_applied()

    assert view.rendered_rows == original_rows
    assert view.rendered_log_state is not None
    assert view.rendered_log_state.filter_data == CommunicationLogFilterData()
    assert view.feedback_messages[-1] == (
        "Tid från måste anges som YYYY-MM-DD HH:MM eller YY-MM-DD HH:MM.",
        True,
    )


def test_sort_and_selection_preserve_selected_entry_until_the_entry_is_filtered_out(repository) -> None:
    selected_entry_id = repository.create_communication_entry(
        CommunicationEntry(
            message_content="Alpha entry.",
            operator="Operatör Ett",
            event_time=datetime(2026, 5, 12, 10, 15),
            from_field="Alpha",
            to_field="GC",
            communication_system="RA180",
        )
    )
    repository.create_communication_entry(
        CommunicationEntry(
            message_content="Bravo entry.",
            operator="Operatör Två",
            event_time=datetime(2026, 5, 12, 10, 20),
            from_field="Bravo",
            to_field="GC",
            communication_system="RA180",
        )
    )
    view = MockCommunicationView()
    presenter = CommunicationPresenter(repository, view, AppRuntimeState(active_operator="Sgt Example"))

    presenter.attach()
    presenter.on_selection_changed(selected_entry_id)

    presenter.on_sort_requested("from")

    assert [row.from_text for row in view.rendered_rows] == ["Alpha", "Bravo"]
    assert [row.entry_id for row in view.rendered_rows if row.is_selected] == [selected_entry_id]
    assert view.rendered_log_state is not None
    assert view.rendered_log_state.sort_column == "from"
    assert view.rendered_log_state.sort_descending is False

    presenter.on_sort_requested("from")

    assert [row.from_text for row in view.rendered_rows] == ["Bravo", "Alpha"]
    assert [row.entry_id for row in view.rendered_rows if row.is_selected] == [selected_entry_id]
    assert view.rendered_log_state is not None
    assert view.rendered_log_state.sort_descending is True

    view.log_filter_data = CommunicationLogFilterData(from_text="Alpha")
    presenter.on_filters_applied()

    assert [row.entry_id for row in view.rendered_rows if row.is_selected] == [selected_entry_id]

    view.log_filter_data = CommunicationLogFilterData(from_text="Bravo")
    presenter.on_filters_applied()

    assert [row.from_text for row in view.rendered_rows] == ["Bravo"]
    assert [row.entry_id for row in view.rendered_rows if row.is_selected] == []


def test_on_open_selected_requested_shows_full_detail_for_the_selected_entry(repository) -> None:
    entry_id = repository.create_communication_entry(
        CommunicationEntry(
            message_content="Det här är hela meddelandet utan trunkering för detaljvyn.",
            operator="Operatör Ett",
            event_time=datetime(2026, 5, 12, 14, 5),
            from_field="Alpha",
            to_field="Bravo",
            communication_system="RA180",
            edited=True,
        )
    )
    view = MockCommunicationView()
    presenter = CommunicationPresenter(repository, view, AppRuntimeState(active_operator="Sgt Example"))

    presenter.attach()
    presenter.on_selection_changed(entry_id)

    presenter.on_open_selected_requested()

    assert view.detail_states == [
        CommunicationEntryDetailState(
            title=f"Kommunikationspost #{entry_id}",
            time_text="2026-05-12 14:05",
            from_text="Alpha",
            to_text="Bravo",
            method_text="RA180",
            confirmed_text="Nej",
            edited_text="Ja",
            operator_text="Operatör Ett",
            message_text="Det här är hela meddelandet utan trunkering för detaljvyn.",
        )
    ]


def test_edit_mode_updates_existing_entry_and_rerenders_stored_edited_state(repository: EventLogRepository) -> None:
    entry_id = repository.create_communication_entry(
        CommunicationEntry(
            message_content="Första versionen.",
            operator="Operatör Ett",
            event_time=datetime(2026, 5, 12, 9, 0),
            from_field="Alpha",
            to_field="Bravo",
            communication_system="RA180",
        )
    )
    set_communication_logged_time(repository, entry_id, datetime(2026, 5, 12, 8, 0))
    view = MockCommunicationView()
    presenter = CommunicationPresenter(repository, view, AppRuntimeState(active_operator="Sgt Example"))

    presenter.attach()
    presenter.on_selection_changed(entry_id)

    presenter.on_edit_selected_requested()

    assert view.form_data == CommunicationFormData(
        time_text="2026-05-12 09:00",
        from_field="Alpha",
        to_field="Bravo",
        message_content="Första versionen.",
        communication_system="RA180",
        communication_qualifiers={
            "data": True,
            "encrypted": True,
        },
    )
    assert view.rendered_editor_state == CommunicationEditorState(
        section_title="Redigera kommunikationspost",
        save_button_text="Uppdatera",
        clear_button_text="Avbryt redigering",
        selection_actions_enabled=True,
        is_edit_mode=True,
    )

    view.form_data = CommunicationFormData(
        time_text="2026-05-12 09:07",
        from_field="Alpha",
        to_field="GC",
        message_content="Uppdaterad version.",
        communication_system="RA180",
        communication_qualifiers={
            "data": True,
            "encrypted": True,
        },
    )

    presenter.on_save_clicked()

    entries = repository.get_all_communication_entries()
    assert len(entries) == 1
    updated_entry = entries[0]
    assert updated_entry.id == entry_id
    assert updated_entry.message_content == "Uppdaterad version."
    assert updated_entry.to_field == "GC"
    assert updated_entry.event_time == datetime(2026, 5, 12, 9, 7)
    assert updated_entry.edited is True
    assert view.rendered_rows[0].entry_id == entry_id
    assert view.rendered_rows[0].edited_text == "✓"
    assert view.feedback_messages[-1] == ("Kommunikationspost uppdaterad.", False)
    assert view.rendered_editor_state == CommunicationEditorState(selection_actions_enabled=True)
    assert view.form_data == CommunicationFormData()


def test_on_delete_selected_requested_handles_cancel_then_confirm(repository) -> None:
    entry_id = repository.create_communication_entry(
        CommunicationEntry(
            message_content="Felregistrerad post.",
            operator="Operatör Ett",
            event_time=datetime(2026, 5, 12, 9, 15),
            from_field="Alpha",
            to_field="Bravo",
            communication_system="RA180",
        )
    )
    view = MockCommunicationView()
    presenter = CommunicationPresenter(repository, view, AppRuntimeState(active_operator="Sgt Example"))

    presenter.attach()
    presenter.on_selection_changed(entry_id)

    view.confirm_delete_result = False
    presenter.on_delete_selected_requested()

    assert repository.get_communication_entry(entry_id) is not None
    assert view.feedback_messages[-1] == ("Borttagning avbröts.", False)
    assert len(view.delete_confirmation_calls) == 1

    view.confirm_delete_result = True
    presenter.on_delete_selected_requested()

    assert repository.get_communication_entry(entry_id) is None
    assert view.feedback_messages[-1] == ("Kommunikationspost borttagen.", False)
    assert view.rendered_editor_state == CommunicationEditorState()
    assert len(view.delete_confirmation_calls) == 2


def test_on_config_changed_uses_json_variants_for_bounded_path_depth_and_downstream_reset(
    repository: EventLogRepository,
) -> None:
    _replace_runtime_config_with_ui_variants(repository)
    view = MockCommunicationView(
        CommunicationFormData(
            communication_system="Layered Radio",
            communication_path=("PRIMARY", "VOICE", "RELAY"),
            communication_qualifiers={
                "encrypted": True,
                "mode": "data",
            },
        )
    )
    presenter = CommunicationPresenter(repository, view, AppRuntimeState(active_operator="Sgt Example"))

    presenter.on_config_changed()

    assert view.rendered_form_state is not None
    assert tuple(path_field.label for path_field in view.rendered_form_state.path_fields) == (
        "Nät",
        "Rutt",
        "Läge",
    )
    assert view.form_data.communication_path == ("PRIMARY", "VOICE", "RELAY")

    view.form_data = CommunicationFormData(
        communication_system="Layered Radio",
        communication_path=("SECONDARY", "VOICE", "RELAY"),
        communication_qualifiers={
            "encrypted": True,
            "mode": "data",
        },
    )

    presenter.on_config_changed()

    assert view.rendered_form_state is not None
    assert len(view.rendered_form_state.path_fields) == 1
    assert view.rendered_form_state.path_fields[0].label == "Nät"
    assert view.form_data.communication_path == ("SECONDARY",)
    assert view.form_data.communication_qualifiers == {
        "encrypted": True,
        "mode": "data",
    }


def test_on_config_changed_applies_editable_forced_and_hidden_qualifier_behavior_from_runtime_config(
    repository: EventLogRepository,
) -> None:
    _replace_runtime_config_with_ui_variants(repository)
    view = MockCommunicationView(
        CommunicationFormData(
            communication_system="Layered Radio",
            communication_qualifiers={
                "encrypted": True,
                "mode": "data",
            },
        )
    )
    presenter = CommunicationPresenter(repository, view, AppRuntimeState(active_operator="Sgt Example"))

    presenter.on_config_changed()

    assert view.rendered_form_state is not None
    layered_fields = {
        field.qualifier_key: field
        for field in view.rendered_form_state.qualifier_fields
    }
    assert layered_fields["encrypted"].visible is True
    assert layered_fields["encrypted"].read_only is False
    assert layered_fields["encrypted"].value is True
    assert layered_fields["mode"].visible is True
    assert layered_fields["mode"].read_only is False
    assert layered_fields["mode"].value == "data"

    view.form_data = CommunicationFormData(
        communication_system="Forced Net",
        communication_qualifiers={"encrypted": False},
    )

    presenter.on_config_changed()

    assert view.rendered_form_state is not None
    forced_field = view.rendered_form_state.qualifier_fields[0]
    assert forced_field.qualifier_key == "encrypted"
    assert forced_field.visible is True
    assert forced_field.read_only is True
    assert forced_field.value is True
    assert view.form_data.communication_qualifiers == {"encrypted": True}

    view.form_data = CommunicationFormData(communication_system="Kurir")

    presenter.on_config_changed()

    assert view.rendered_form_state is not None
    hidden_field = view.rendered_form_state.qualifier_fields[0]
    assert hidden_field.qualifier_key == "encrypted"
    assert hidden_field.visible is False
    assert hidden_field.read_only is False
    assert hidden_field.value is False
    assert view.form_data.communication_qualifiers == {"encrypted": False}


def test_on_save_clicked_persists_config_driven_selection_snapshot_and_table_method_text(
    repository: EventLogRepository,
) -> None:
    _replace_runtime_config_with_ui_variants(repository)
    view = MockCommunicationView(
        CommunicationFormData(
            from_field="Ledning",
            to_field="1. pluton",
            message_content=(
                "Byt till reservväg och fortsätt med utdragen sambandstjänst genom nästa punkt "
                "utan att stanna för omgruppering."
            ),
            communication_system="Layered Radio",
            communication_path=("PRIMARY", "VOICE", "RELAY"),
            communication_qualifiers={
                "encrypted": True,
                "mode": "data",
            },
        )
    )
    presenter = CommunicationPresenter(
        repository,
        view,
        AppRuntimeState(active_operator="Sgt Example"),
        now_provider=lambda: datetime(2026, 5, 12, 18, 10),
    )

    presenter.on_save_clicked()

    entry = repository.get_all_communication_entries()[0]
    assert entry.communication_system == "Layered Radio"
    assert entry.method_channel == "RELAY"
    assert entry.channel_designation == "Reläläge"
    assert entry.system_capabilities == {
        "communication_path": [
            {"value": "PRIMARY", "label": "Primärnät"},
            {"value": "VOICE", "label": "Talväg"},
            {"value": "RELAY", "label": "Reläläge"},
        ],
        "communication_qualifiers": {
            "encrypted": True,
            "mode": "data",
        },
    }
    assert view.rendered_rows[0].method_text == "Layered Radio > Primärnät > Talväg > Reläläge"
    assert view.rendered_rows[0].message_text == "Byt till reservväg och fortsätt med utdragen sambandstjänst genom nästa..."
    assert view.form_data.communication_path == ("PRIMARY", "VOICE", "RELAY")
    assert view.form_data.communication_qualifiers == {
        "encrypted": True,
        "mode": "data",
    }


@pytest.mark.parametrize(
    ("time_text", "expected"),
    [
        ("2026-05-11 21:04", datetime(2026, 5, 11, 21, 4)),
        ("26-05-11 21:04", datetime(2026, 5, 11, 21, 4)),
    ],
)
def test_parse_exact_datetime_accepts_approved_formats(time_text: str, expected: datetime) -> None:
    parsed = CommunicationPresenter._parse_exact_datetime(time_text)

    assert parsed == expected


def test_parse_tnr_backtracks_by_date_only_and_ignores_later_clock_time_same_day() -> None:
    reference_time = datetime(2026, 5, 12, 0, 5)

    same_day_later_clock = CommunicationPresenter._parse_tnr("120600", reference_time=reference_time)
    previous_month_backtrack = CommunicationPresenter._parse_tnr("130005", reference_time=reference_time)

    assert same_day_later_clock == datetime(2026, 5, 12, 6, 0)
    assert previous_month_backtrack == datetime(2026, 4, 13, 0, 5)



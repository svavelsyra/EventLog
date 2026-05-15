"""Presenter-owned Communication tab save/load behavior for the first MVP slice."""

from __future__ import annotations

from calendar import monthrange
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
import logging
import re
from typing import Protocol

from src.core import CommunicationConfigLoader, CommunicationEntry, SystemConfig
from src.core.app_runtime_state import AppRuntimeState
from src.core.communication_config import (
    CommunicationOptionDefinition,
    CommunicationQualifierDefinition,
    CommunicationSystemDefinition,
)
from src.db.adapters.event_log_adapter import EventLogAdapter


LOGGER = logging.getLogger(__name__)
_TNR_PATTERN = re.compile(r"^\d{6}$")
_EXACT_DATETIME_PATTERN = re.compile(
    r"^(?P<year>\d{2}|\d{4})-(?P<month>\d{2})-(?P<day>\d{2}) (?P<hour>\d{2}):(?P<minute>\d{2})$"
)
_REVIEW_ROW_STATUS = "SE ÖVER"
_INVALID_TIME_LABEL = "OGILTIG TID"
_MAX_VISIBLE_PATH_LEVELS = 3
_DEFAULT_SORT_COLUMN = "time"
_DEFAULT_SORT_DESCENDING = True
_MESSAGE_TRUNCATION_LIMIT = 80
_SORTABLE_LOG_COLUMNS = (
    "status",
    "time",
    "from",
    "to",
    "method",
    "message",
    "confirmed",
    "edited",
    "operator",
)
QualifierValue = bool | str | None


@dataclass(frozen=True, slots=True)
class CommunicationPathChoice:
    """One presenter-owned visible path choice for a dynamic selector."""

    value: str
    label: str


@dataclass(frozen=True, slots=True)
class CommunicationPathFieldState:
    """One presenter-owned visible Communication path selector."""

    label: str
    options: tuple[CommunicationPathChoice, ...]
    selected_value: str = ""


@dataclass(frozen=True, slots=True)
class CommunicationQualifierFieldState:
    """One presenter-owned qualifier control description."""

    qualifier_key: str
    label: str
    field_type: str
    value: QualifierValue = None
    visible: bool = True
    read_only: bool = False
    valid_values: tuple[str, ...] | None = None
    help_text: str | None = None


@dataclass(frozen=True, slots=True)
class CommunicationFormState:
    """Presenter-owned config-driven Communication form rendering state."""

    system_choices: tuple[str, ...] = ()
    selected_system: str = ""
    path_fields: tuple[CommunicationPathFieldState, ...] = ()
    qualifier_fields: tuple[CommunicationQualifierFieldState, ...] = ()


@dataclass(frozen=True, slots=True)
class CommunicationFormData:
    """Presenter-owned normalized Communication form payload."""

    time_text: str = ""
    from_field: str = ""
    to_field: str = ""
    message_content: str = ""
    communication_system: str = ""
    communication_path: tuple[str, ...] = ()
    communication_qualifiers: dict[str, QualifierValue] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CommunicationLogFilterData:
    """Presenter-owned Communication log filter submission/readback contract."""

    time_from_text: str = ""
    time_to_text: str = ""
    from_text: str = ""
    to_text: str = ""
    system_text: str = ""
    message_text: str = ""


@dataclass(frozen=True, slots=True)
class CommunicationLogRow:
    """Simple presenter-to-view table contract for one Communication row."""

    entry_id: int
    status_text: str
    time_text: str
    from_text: str
    to_text: str
    method_text: str
    message_text: str
    confirmed_text: str
    edited_text: str
    operator_text: str
    needs_review: bool = False
    is_selected: bool = False


@dataclass(frozen=True, slots=True)
class CommunicationLogState:
    """Presenter-owned render state for the Communication log filter/table slice."""

    filter_data: CommunicationLogFilterData = CommunicationLogFilterData()
    rows: tuple[CommunicationLogRow, ...] = ()
    sort_column: str = _DEFAULT_SORT_COLUMN
    sort_descending: bool = _DEFAULT_SORT_DESCENDING
    system_filter_choices: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CommunicationEntryDetailState:
    """Presenter-owned read-only detail contract for one selected Communication entry."""

    title: str
    status_text: str = ""
    time_text: str = ""
    from_text: str = ""
    to_text: str = ""
    method_text: str = ""
    confirmed_text: str = ""
    edited_text: str = ""
    operator_text: str = ""
    message_text: str = ""
    review_notes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CommunicationEditorState:
    """Presenter-owned create-vs-edit render state for the Communication form."""

    section_title: str = "Ny kommunikationspost"
    save_button_text: str = "Spara"
    clear_button_text: str = "Rensa"
    selection_actions_enabled: bool = False
    is_edit_mode: bool = False


@dataclass(frozen=True, slots=True)
class _ReviewIssue:
    """One presenter-derived soft-review issue."""

    field_name: str
    popup_reason: str
    log_reason: str


@dataclass(frozen=True, slots=True)
class _TimeParseResult:
    """Outcome for the current save's operator-entered time text."""

    event_time: datetime | None
    review_issue: _ReviewIssue | None = None


class CommunicationViewProtocol(Protocol):
    """Minimal passive view seam consumed by the Communication presenter."""

    def set_save_handler(self, callback: Callable[[], None]) -> None:
        """Bind the save action to a presenter callback."""

    def set_clear_handler(self, callback: Callable[[], None]) -> None:
        """Bind the clear action to a presenter callback."""

    def set_swap_handler(self, callback: Callable[[], None]) -> None:
        """Bind the sender/receiver swap action to a presenter callback."""

    def set_config_change_handler(self, callback: Callable[[], None]) -> None:
        """Bind config-driven system/path change actions to one presenter callback."""

    def get_form_data(self) -> CommunicationFormData:
        """Return the current Communication form payload."""

    def set_form_data(self, form_data: CommunicationFormData) -> None:
        """Render the provided form payload into the Communication inputs."""

    def render_form_state(self, form_state: CommunicationFormState) -> None:
        """Render config-driven system/path/qualifier form structure."""

    def render_editor_state(self, editor_state: CommunicationEditorState) -> None:
        """Render whether the Communication form is in create or edit mode."""

    def get_log_filter_data(self) -> CommunicationLogFilterData:
        """Return the current Communication log filter submission payload."""

    def render_log_state(self, log_state: CommunicationLogState) -> None:
        """Render the current Communication log filter/table state."""

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

    def set_feedback_message(self, message: str, *, is_error: bool = False) -> None:
        """Display coarse presenter feedback without owning business logic."""

    def show_warning_dialog(self, title: str, message: str) -> None:
        """Show a warning-style acknowledgement dialog for soft-save issues."""

    def show_entry_details(self, detail_state: CommunicationEntryDetailState) -> None:
        """Show full detail for one selected Communication entry."""

    def confirm_delete_entry(self, title: str, message: str) -> bool:
        """Return whether the operator confirmed deleting the selected entry."""


class CommunicationPresenter:
    """Coordinate Communication save/load behavior between the passive view and repository."""

    def __init__(
        self,
        repository: EventLogAdapter,
        view: CommunicationViewProtocol,
        app_runtime_state: AppRuntimeState,
        *,
        config_loader: CommunicationConfigLoader | None = None,
        now_provider: Callable[[], datetime] = datetime.now,
        logger: logging.Logger | None = None,
    ) -> None:
        self._repository = repository
        self._view = view
        self._app_runtime_state = app_runtime_state
        self._config_loader = config_loader or CommunicationConfigLoader(repository)
        self._now_provider = now_provider
        self._logger = LOGGER if logger is None else logger
        self._current_log_filter_data = CommunicationLogFilterData()
        self._active_time_from_filter: datetime | None = None
        self._active_time_to_filter: datetime | None = None
        self._sort_column = _DEFAULT_SORT_COLUMN
        self._sort_descending = _DEFAULT_SORT_DESCENDING
        self._selected_entry_id: int | None = None
        self._editing_entry_id: int | None = None

    def attach(self) -> None:
        """Connect the presenter to the view and load the first Communication rows."""
        self._view.set_save_handler(self.on_save_clicked)
        self._view.set_clear_handler(self.on_clear_clicked)
        self._view.set_swap_handler(self.on_swap_clicked)
        self._view.set_config_change_handler(self.on_config_changed)
        self._view.set_log_interaction_handlers(
            on_apply_filters=self.on_filters_applied,
            on_clear_filters=self.on_filters_cleared,
            on_open_selected=self.on_open_selected_requested,
            on_edit_selected=self.on_edit_selected_requested,
            on_delete_selected=self.on_delete_selected_requested,
            on_sort_requested=self.on_sort_requested,
            on_selection_changed=self.on_selection_changed,
        )
        self._refresh_config_driven_form(CommunicationFormData())
        self.load_entries()

    def load_entries(self) -> None:
        """Load Communication entries from the repository and render them into the view."""
        try:
            entries = self._repository.get_all_communication_entries()
        except Exception:
            self._logger.exception("Kunde inte läsa kommunikationsposter.")
            self._view.set_feedback_message("Kunde inte läsa kommunikationsloggen.", is_error=True)
            return

        runtime_config = self._get_runtime_config()
        filtered_entries = [entry for entry in entries if self._entry_matches_active_filters(entry)]
        sorted_entries = self._sort_entries(filtered_entries)
        visible_entry_ids = {entry.id for entry in sorted_entries if entry.id is not None}
        if self._selected_entry_id not in visible_entry_ids:
            self._selected_entry_id = None

        rows = tuple(
            self._build_log_row(
                entry,
                is_selected=entry.id is not None and entry.id == self._selected_entry_id,
            )
            for entry in sorted_entries
        )
        self._view.render_log_state(
            CommunicationLogState(
                filter_data=self._current_log_filter_data,
                rows=rows,
                sort_column=self._sort_column,
                sort_descending=self._sort_descending,
                system_filter_choices=runtime_config.system_names,
            )
        )
        self._render_editor_state()

    def on_filters_applied(self) -> None:
        """Validate and apply the current log filters, then reload the Communication rows."""
        filter_data = self._normalize_log_filter_data(self._view.get_log_filter_data())
        invalid_fields: list[str] = []
        time_from = self._parse_exact_datetime(filter_data.time_from_text) if filter_data.time_from_text else None
        if filter_data.time_from_text and time_from is None:
            invalid_fields.append("Tid från")
        time_to = self._parse_exact_datetime(filter_data.time_to_text) if filter_data.time_to_text else None
        if filter_data.time_to_text and time_to is None:
            invalid_fields.append("Tid till")
        if invalid_fields:
            self._view.set_feedback_message(
                f"{' och '.join(invalid_fields)} måste anges som YYYY-MM-DD HH:MM eller YY-MM-DD HH:MM.",
                is_error=True,
            )
            return
        if time_from is not None and time_to is not None and time_from > time_to:
            self._view.set_feedback_message("Tid från måste vara tidigare än eller lika med Tid till.", is_error=True)
            return

        self._current_log_filter_data = filter_data
        self._active_time_from_filter = time_from
        self._active_time_to_filter = time_to
        self.load_entries()
        self._view.set_feedback_message("Filter uppdaterade.")

    def on_filters_cleared(self) -> None:
        """Reset the active Communication log filters to a deliberate blank state."""
        self._current_log_filter_data = CommunicationLogFilterData()
        self._active_time_from_filter = None
        self._active_time_to_filter = None
        self.load_entries()
        self._view.set_feedback_message("Filter rensade.")

    def on_sort_requested(self, column_name: str) -> None:
        """Toggle or replace the active table sort column and rerender the log."""
        if column_name not in _SORTABLE_LOG_COLUMNS:
            return
        if column_name == self._sort_column:
            self._sort_descending = not self._sort_descending
        else:
            self._sort_column = column_name
            self._sort_descending = False
        self.load_entries()

    def on_selection_changed(self, entry_id: int | None) -> None:
        """Track the currently selected Communication entry for passive table selection."""
        self._selected_entry_id = entry_id
        self._render_editor_state()

    def on_open_selected_requested(self) -> None:
        """Show full read-only detail for the currently selected Communication entry."""
        selected_entry = self._get_selected_entry()
        if selected_entry is None:
            return
        self._view.show_entry_details(self._build_detail_state(selected_entry))

    def on_edit_selected_requested(self) -> None:
        """Load the selected Communication entry back into the form for editing."""
        selected_entry = self._get_selected_entry()
        if selected_entry is None:
            return

        self._editing_entry_id = selected_entry.id
        self._refresh_config_driven_form(self._build_form_data_from_entry(selected_entry))
        self._render_editor_state()

        review_issues = self._derive_review_issues(selected_entry)
        if review_issues:
            self._view.set_feedback_message("Redigerar vald kommunikationspost. Posten behöver ses över.")
            return
        self._view.set_feedback_message("Redigerar vald kommunikationspost.")

    def on_delete_selected_requested(self) -> None:
        """Delete the currently selected Communication entry after explicit confirmation."""
        selected_entry = self._get_selected_entry()
        if selected_entry is None:
            return

        delete_summary = self._build_delete_summary(selected_entry)
        confirmed = self._view.confirm_delete_entry(
            "Ta bort kommunikationspost",
            "Vill du ta bort den valda kommunikationsposten?\n\n"
            f"{delete_summary}",
        )
        if not confirmed:
            self._view.set_feedback_message("Borttagning avbröts.")
            return

        entry_id = selected_entry.id
        if entry_id is None:
            self._view.set_feedback_message("Den valda kommunikationsposten kunde inte tas bort.", is_error=True)
            return

        try:
            deleted = self._repository.delete_communication_entry(entry_id)
        except Exception:
            self._logger.exception("Kunde inte ta bort kommunikationspost.")
            self._view.set_feedback_message("Kunde inte ta bort kommunikationsposten.", is_error=True)
            return

        if not deleted:
            self._view.set_feedback_message("Den valda kommunikationsposten kunde inte tas bort.", is_error=True)
            return

        if self._editing_entry_id == entry_id:
            self._editing_entry_id = None
            self._refresh_config_driven_form(CommunicationFormData())

        self._selected_entry_id = None
        self.load_entries()
        self._view.set_feedback_message("Kommunikationspost borttagen.")

    def on_save_clicked(self) -> None:
        """Read the form, save a Communication entry, and update the passive view."""
        form_data = self._refresh_config_driven_form(self._view.get_form_data())
        save_time = self._now_provider()
        time_result = self._parse_event_time(form_data.time_text, reference_time=save_time)
        runtime_config = self._get_runtime_config()
        is_edit_mode = self._editing_entry_id is not None

        review_issues: list[_ReviewIssue] = []
        if time_result.review_issue is not None:
            review_issues.append(time_result.review_issue)
        if not form_data.message_content:
            review_issues.append(
                _ReviewIssue(
                    field_name="Meddelande",
                    popup_reason="saknar innehåll",
                    log_reason="meddelande saknar innehåll",
                )
            )

        operator = self._app_runtime_state.active_operator.strip()
        if not operator:
            review_issues.append(
                _ReviewIssue(
                    field_name="Operatör",
                    popup_reason="saknar värde",
                    log_reason="operatör saknar värde",
                )
            )

        entry = CommunicationEntry(
            message_content=form_data.message_content,
            operator=operator,
            id=self._editing_entry_id,
            event_time=time_result.event_time,
            from_field=form_data.from_field or None,
            to_field=form_data.to_field or None,
            communication_system=form_data.communication_system or None,
            method_channel=self._get_last_path_value(form_data),
            channel_designation=self._get_last_path_label(form_data, runtime_config),
            system_capabilities=self._build_selection_snapshot(form_data, runtime_config),
        )

        try:
            if is_edit_mode:
                saved = self._repository.update_communication_entry(entry)
                if not saved:
                    self._view.set_feedback_message("Kunde inte uppdatera kommunikationsposten.", is_error=True)
                    return
            else:
                self._repository.create_communication_entry(entry)
        except Exception:
            action_name = "uppdatera" if is_edit_mode else "spara"
            self._logger.exception("Kunde inte %s kommunikationspost.", action_name)
            self._view.set_feedback_message(
                "Kunde inte uppdatera kommunikationsposten." if is_edit_mode else "Kunde inte spara kommunikationsposten.",
                is_error=True,
            )
            return

        if is_edit_mode:
            self._editing_entry_id = None
            self._refresh_config_driven_form(CommunicationFormData())
        else:
            self._refresh_config_driven_form(
                CommunicationFormData(
                    from_field=form_data.from_field,
                    to_field=form_data.to_field,
                    communication_system=form_data.communication_system,
                    communication_path=form_data.communication_path,
                    communication_qualifiers=form_data.communication_qualifiers,
                )
            )
        self.load_entries()

        if review_issues:
            self._emit_soft_warning(review_issues)
            self._view.set_feedback_message(
                "Post uppdaterad, men behöver ses över." if is_edit_mode else "Post sparad, men behöver ses över."
            )
            return

        self._view.set_feedback_message(
            "Kommunikationspost uppdaterad." if is_edit_mode else "Kommunikationspost sparad."
        )

    def on_clear_clicked(self) -> None:
        """Reset the Communication form to a deliberate blank state."""
        was_editing = self._editing_entry_id is not None
        self._editing_entry_id = None
        self._refresh_config_driven_form(CommunicationFormData())
        self._render_editor_state()
        self._view.set_feedback_message("Redigering avbröts." if was_editing else "Formuläret rensades.")

    def on_swap_clicked(self) -> None:
        """Swap sender and receiver values through the presenter-owned form flow."""
        current = self._refresh_config_driven_form(self._view.get_form_data())
        self._refresh_config_driven_form(
            CommunicationFormData(
                time_text=current.time_text,
                from_field=current.to_field,
                to_field=current.from_field,
                message_content=current.message_content,
                communication_system=current.communication_system,
                communication_path=current.communication_path,
                communication_qualifiers=current.communication_qualifiers,
            )
        )
        self._view.set_feedback_message("Från och Till bytte plats.")

    def on_config_changed(self) -> None:
        """Recompute config-driven path and qualifier controls from current selections."""
        self._refresh_config_driven_form(self._view.get_form_data())

    def reload_runtime_config(self) -> None:
        """Reload cached runtime Communication config and refresh the current form state."""
        self._config_loader.reload_config()
        self._refresh_config_driven_form(self._view.get_form_data())
        self.load_entries()

    def _render_editor_state(self) -> None:
        self._view.render_editor_state(
            CommunicationEditorState(
                section_title=(
                    "Redigera kommunikationspost"
                    if self._editing_entry_id is not None
                    else "Ny kommunikationspost"
                ),
                save_button_text="Uppdatera" if self._editing_entry_id is not None else "Spara",
                clear_button_text="Avbryt redigering" if self._editing_entry_id is not None else "Rensa",
                selection_actions_enabled=self._selected_entry_id is not None,
                is_edit_mode=self._editing_entry_id is not None,
            )
        )

    def _get_selected_entry(self) -> CommunicationEntry | None:
        entry_id = self._selected_entry_id
        if entry_id is None:
            self._view.set_feedback_message("Välj en kommunikationspost först.", is_error=True)
            return None

        try:
            selected_entry = self._repository.get_communication_entry(entry_id)
        except Exception:
            self._logger.exception("Kunde inte läsa vald kommunikationspost.")
            self._view.set_feedback_message("Kunde inte läsa den valda kommunikationsposten.", is_error=True)
            return None

        if selected_entry is not None:
            return selected_entry

        if self._editing_entry_id == entry_id:
            self._editing_entry_id = None
            self._refresh_config_driven_form(CommunicationFormData())
        self._selected_entry_id = None
        self.load_entries()
        self._view.set_feedback_message("Den valda kommunikationsposten finns inte längre.", is_error=True)
        return None

    def _build_detail_state(self, entry: CommunicationEntry) -> CommunicationEntryDetailState:
        review_issues = self._derive_review_issues(entry)
        invalid_time = any(issue.field_name == "Tid" for issue in review_issues)
        return CommunicationEntryDetailState(
            title=(f"Kommunikationspost #{entry.id}" if entry.id is not None else "Kommunikationspost"),
            status_text=_REVIEW_ROW_STATUS if review_issues else "",
            time_text=self._format_event_time(entry.event_time, invalid_time=invalid_time),
            from_text=entry.from_field or "",
            to_text=entry.to_field or "",
            method_text=self._format_method_text(entry),
            confirmed_text="Ja" if entry.confirmed else "Nej",
            edited_text="Ja" if entry.edited else "Nej",
            operator_text=entry.operator,
            message_text=entry.message_content,
            review_notes=tuple(f"{issue.field_name} – {issue.popup_reason}" for issue in review_issues),
        )

    def _build_form_data_from_entry(self, entry: CommunicationEntry) -> CommunicationFormData:
        path_snapshot = self._extract_path_snapshot(entry)
        return CommunicationFormData(
            time_text=self._format_event_time(entry.event_time, invalid_time=False) if entry.event_time is not None else "",
            from_field=entry.from_field or "",
            to_field=entry.to_field or "",
            message_content=entry.message_content,
            communication_system=entry.communication_system or "",
            communication_path=tuple(item["value"] for item in path_snapshot),
            communication_qualifiers=self._extract_qualifier_snapshot(entry),
        )

    def _build_delete_summary(self, entry: CommunicationEntry) -> str:
        summary_lines = [
            f"Tid: {self._format_event_time(entry.event_time, invalid_time=entry.event_time is None) or '—'}",
            f"Från: {entry.from_field or '—'}",
            f"Till: {entry.to_field or '—'}",
            f"Metod: {self._format_method_text(entry) or '—'}",
            f"Meddelande: {self._format_message_text(entry.message_content) or '—'}",
        ]
        return "\n".join(summary_lines)

    def _build_log_row(self, entry: CommunicationEntry, *, is_selected: bool) -> CommunicationLogRow:
        review_issues = self._derive_review_issues(entry)
        invalid_time = any(issue.field_name == "Tid" for issue in review_issues)
        return CommunicationLogRow(
            entry_id=entry.id or 0,
            status_text=_REVIEW_ROW_STATUS if review_issues else "",
            time_text=self._format_event_time(entry.event_time, invalid_time=invalid_time),
            from_text=entry.from_field or "",
            to_text=entry.to_field or "",
            method_text=self._format_method_text(entry),
            message_text=self._format_message_text(entry.message_content),
            confirmed_text="✓" if entry.confirmed else "",
            edited_text="✓" if entry.edited else "",
            operator_text=entry.operator,
            needs_review=bool(review_issues),
            is_selected=is_selected,
        )

    @staticmethod
    def _normalize_form_data(form_data: CommunicationFormData) -> CommunicationFormData:
        return CommunicationFormData(
            time_text=form_data.time_text.strip(),
            from_field=form_data.from_field.strip(),
            to_field=form_data.to_field.strip(),
            message_content=form_data.message_content.strip(),
            communication_system=form_data.communication_system.strip(),
            communication_path=tuple(option_value.strip() for option_value in form_data.communication_path if option_value.strip()),
            communication_qualifiers={
                qualifier_key.strip(): CommunicationPresenter._normalize_qualifier_value(raw_value)
                for qualifier_key, raw_value in form_data.communication_qualifiers.items()
                if qualifier_key.strip()
            },
        )

    @staticmethod
    def _normalize_qualifier_value(value: QualifierValue) -> QualifierValue:
        if isinstance(value, str):
            return value.strip()
        return value

    @staticmethod
    def _normalize_log_filter_data(filter_data: CommunicationLogFilterData) -> CommunicationLogFilterData:
        return CommunicationLogFilterData(
            time_from_text=filter_data.time_from_text.strip(),
            time_to_text=filter_data.time_to_text.strip(),
            from_text=filter_data.from_text.strip(),
            to_text=filter_data.to_text.strip(),
            system_text=filter_data.system_text.strip(),
            message_text=filter_data.message_text.strip(),
        )

    def _refresh_config_driven_form(self, form_data: CommunicationFormData) -> CommunicationFormData:
        normalized_form_data, form_state = self._build_form_state(self._normalize_form_data(form_data))
        self._view.render_form_state(form_state)
        self._view.set_form_data(normalized_form_data)
        return normalized_form_data

    def _build_form_state(
        self,
        form_data: CommunicationFormData,
    ) -> tuple[CommunicationFormData, CommunicationFormState]:
        runtime_config = self._get_runtime_config()
        selected_system = (
            form_data.communication_system
            if form_data.communication_system in runtime_config.system_names
            else ""
        )
        system_definition = runtime_config.get_system(selected_system) if selected_system else None
        normalized_path, path_fields = self._build_path_fields(
            system_definition,
            form_data.communication_path,
        )
        normalized_qualifiers, qualifier_fields = self._build_qualifier_fields(
            system_definition,
            form_data.communication_qualifiers,
        )
        normalized_form_data = CommunicationFormData(
            time_text=form_data.time_text,
            from_field=form_data.from_field,
            to_field=form_data.to_field,
            message_content=form_data.message_content,
            communication_system=selected_system,
            communication_path=normalized_path,
            communication_qualifiers=normalized_qualifiers,
        )
        return normalized_form_data, CommunicationFormState(
            system_choices=runtime_config.system_names,
            selected_system=selected_system,
            path_fields=path_fields,
            qualifier_fields=qualifier_fields,
        )

    def _get_runtime_config(self) -> SystemConfig:
        try:
            return self._config_loader.get_config()
        except Exception:
            self._logger.exception("Kunde inte läsa kommunikationskonfiguration.")
            self._view.set_feedback_message(
                "Kunde inte läsa kommunikationskonfigurationen.",
                is_error=True,
            )
            return SystemConfig()

    def _build_path_fields(
        self,
        system_definition: CommunicationSystemDefinition | None,
        selected_path: Sequence[str],
    ) -> tuple[tuple[str, ...], tuple[CommunicationPathFieldState, ...]]:
        if system_definition is None:
            return (), ()

        normalized_path: list[str] = []
        path_fields: list[CommunicationPathFieldState] = []
        current_options = system_definition.options
        current_label = system_definition.child_label

        for level_index in range(_MAX_VISIBLE_PATH_LEVELS):
            if not current_options:
                break

            options = tuple(
                CommunicationPathChoice(value=option.option_value, label=option.option_label)
                for option in current_options
            )
            selected_value = selected_path[level_index] if level_index < len(selected_path) else ""
            matching_option = self._find_option_by_value(current_options, selected_value)
            path_fields.append(
                CommunicationPathFieldState(
                    label=current_label or f"Val {level_index + 1}",
                    options=options,
                    selected_value=matching_option.option_value if matching_option is not None else "",
                )
            )
            if matching_option is None:
                break

            normalized_path.append(matching_option.option_value)
            current_label = matching_option.child_label
            current_options = matching_option.children

        return tuple(normalized_path), tuple(path_fields)

    def _build_qualifier_fields(
        self,
        system_definition: CommunicationSystemDefinition | None,
        submitted_qualifiers: dict[str, QualifierValue],
    ) -> tuple[dict[str, QualifierValue], tuple[CommunicationQualifierFieldState, ...]]:
        if system_definition is None:
            return {}, ()

        normalized_qualifiers: dict[str, QualifierValue] = {}
        qualifier_fields: list[CommunicationQualifierFieldState] = []
        for qualifier_definition in system_definition.qualifiers:
            qualifier_value = self._resolve_qualifier_value(
                qualifier_definition,
                submitted_qualifiers.get(qualifier_definition.qualifier_key),
            )
            normalized_qualifiers[qualifier_definition.qualifier_key] = qualifier_value
            qualifier_fields.append(
                CommunicationQualifierFieldState(
                    qualifier_key=qualifier_definition.qualifier_key,
                    label=qualifier_definition.label,
                    field_type=qualifier_definition.field_type,
                    value=qualifier_value,
                    visible=qualifier_definition.visibility_mode != "hidden",
                    read_only=qualifier_definition.visibility_mode == "forced",
                    valid_values=qualifier_definition.valid_values,
                    help_text=qualifier_definition.help_text,
                )
            )

        return normalized_qualifiers, tuple(qualifier_fields)

    def _resolve_qualifier_value(
        self,
        qualifier_definition: CommunicationQualifierDefinition,
        submitted_value: QualifierValue,
    ) -> QualifierValue:
        if qualifier_definition.visibility_mode in {"forced", "hidden"}:
            return qualifier_definition.default_value

        if qualifier_definition.field_type == "boolean":
            if isinstance(submitted_value, bool):
                return submitted_value
            if isinstance(qualifier_definition.default_value, bool):
                return qualifier_definition.default_value
            return None

        if qualifier_definition.field_type == "enum":
            valid_values = qualifier_definition.valid_values or ()
            if isinstance(submitted_value, str) and submitted_value in valid_values:
                return submitted_value
            if isinstance(qualifier_definition.default_value, str) and qualifier_definition.default_value in valid_values:
                return qualifier_definition.default_value
            return None

        if isinstance(submitted_value, str) and submitted_value:
            return submitted_value
        if isinstance(qualifier_definition.default_value, str):
            return qualifier_definition.default_value
        return None

    @staticmethod
    def _find_option_by_value(
        options: Sequence[CommunicationOptionDefinition],
        option_value: str,
    ) -> CommunicationOptionDefinition | None:
        for option in options:
            if option.option_value == option_value:
                return option
        return None

    def _build_selection_snapshot(
        self,
        form_data: CommunicationFormData,
        runtime_config: SystemConfig,
    ) -> dict[str, object] | None:
        if not form_data.communication_system:
            return None

        system_definition = runtime_config.get_system(form_data.communication_system)
        path_snapshot = self._build_path_snapshot(system_definition, form_data.communication_path)
        return {
            "communication_path": path_snapshot,
            "communication_qualifiers": dict(form_data.communication_qualifiers),
        }

    def _build_path_snapshot(
        self,
        system_definition: CommunicationSystemDefinition | None,
        selected_path: Sequence[str],
    ) -> list[dict[str, str]]:
        if system_definition is None:
            return []

        snapshot: list[dict[str, str]] = []
        current_options = system_definition.options
        for option_value in selected_path:
            option = self._find_option_by_value(current_options, option_value)
            if option is None:
                break
            snapshot.append({"value": option.option_value, "label": option.option_label})
            current_options = option.children
        return snapshot

    @staticmethod
    def _get_last_path_value(form_data: CommunicationFormData) -> str | None:
        if not form_data.communication_path:
            return None
        return form_data.communication_path[-1]

    def _get_last_path_label(
        self,
        form_data: CommunicationFormData,
        runtime_config: SystemConfig,
    ) -> str | None:
        path_snapshot = self._build_path_snapshot(
            runtime_config.get_system(form_data.communication_system),
            form_data.communication_path,
        )
        if not path_snapshot:
            return None
        return path_snapshot[-1]["label"]

    def _format_method_text(self, entry: CommunicationEntry) -> str:
        base_text = entry.communication_system or entry.method_type or ""
        path_snapshot = self._extract_path_snapshot(entry)
        if not path_snapshot:
            return base_text

        path_labels = [path_item["label"] for path_item in path_snapshot if path_item.get("label")]
        if not path_labels:
            return base_text
        if not base_text:
            return " > ".join(path_labels)
        return " > ".join((base_text, *path_labels))

    def _entry_matches_active_filters(self, entry: CommunicationEntry) -> bool:
        filter_data = self._current_log_filter_data
        if filter_data.from_text and filter_data.from_text.casefold() not in (entry.from_field or "").casefold():
            return False
        if filter_data.to_text and filter_data.to_text.casefold() not in (entry.to_field or "").casefold():
            return False
        if filter_data.system_text:
            system_text = (entry.communication_system or entry.method_type or "").casefold()
            if filter_data.system_text.casefold() not in system_text:
                return False
        if filter_data.message_text and filter_data.message_text.casefold() not in entry.message_content.casefold():
            return False
        if self._active_time_from_filter is not None:
            if entry.event_time is None or entry.event_time < self._active_time_from_filter:
                return False
        if self._active_time_to_filter is not None:
            if entry.event_time is None or entry.event_time > self._active_time_to_filter:
                return False
        return True

    def _sort_entries(self, entries: Sequence[CommunicationEntry]) -> list[CommunicationEntry]:
        sortable_entries: list[tuple[datetime | int | str, CommunicationEntry]] = []
        missing_entries: list[CommunicationEntry] = []
        for entry in entries:
            sort_value = self._sort_value_for_entry(entry)
            if sort_value is None:
                missing_entries.append(entry)
                continue
            sortable_entries.append((sort_value, entry))
        sortable_entries.sort(key=lambda item: item[0], reverse=self._sort_descending)
        return [entry for _, entry in sortable_entries] + missing_entries

    def _sort_value_for_entry(self, entry: CommunicationEntry) -> datetime | int | str | None:
        match self._sort_column:
            case "status":
                return int(bool(self._derive_review_issues(entry)))
            case "time":
                return entry.event_time
            case "from":
                return (entry.from_field or "").casefold() or None
            case "to":
                return (entry.to_field or "").casefold() or None
            case "method":
                return self._format_method_text(entry).casefold() or None
            case "message":
                return self._collapse_message_whitespace(entry.message_content).casefold() or None
            case "confirmed":
                return int(entry.confirmed)
            case "edited":
                return int(entry.edited)
            case "operator":
                return entry.operator.casefold() or None
        return None

    @staticmethod
    def _format_message_text(message_content: str) -> str:
        collapsed_message = CommunicationPresenter._collapse_message_whitespace(message_content)
        if len(collapsed_message) <= _MESSAGE_TRUNCATION_LIMIT:
            return collapsed_message
        truncated = collapsed_message[: _MESSAGE_TRUNCATION_LIMIT - 3].rstrip()
        last_space = truncated.rfind(" ")
        if last_space >= max(0, _MESSAGE_TRUNCATION_LIMIT // 2):
            truncated = truncated[:last_space]
        return f"{truncated}..."

    @staticmethod
    def _collapse_message_whitespace(message_content: str) -> str:
        return " ".join(message_content.split())

    @staticmethod
    def _extract_path_snapshot(entry: CommunicationEntry) -> list[dict[str, str]]:
        raw_capabilities = entry.system_capabilities
        if not isinstance(raw_capabilities, dict):
            return []

        raw_path = raw_capabilities.get("communication_path")
        if not isinstance(raw_path, list):
            return []

        snapshot: list[dict[str, str]] = []
        for raw_item in raw_path:
            if not isinstance(raw_item, dict):
                continue
            value = raw_item.get("value")
            label = raw_item.get("label")
            if isinstance(value, str) and isinstance(label, str):
                snapshot.append({"value": value, "label": label})
        return snapshot

    @staticmethod
    def _extract_qualifier_snapshot(entry: CommunicationEntry) -> dict[str, QualifierValue]:
        raw_capabilities = entry.system_capabilities
        if not isinstance(raw_capabilities, dict):
            return {}

        raw_qualifiers = raw_capabilities.get("communication_qualifiers")
        if not isinstance(raw_qualifiers, dict):
            return {}

        snapshot: dict[str, QualifierValue] = {}
        for qualifier_key, raw_value in raw_qualifiers.items():
            if not isinstance(qualifier_key, str):
                continue
            if isinstance(raw_value, bool) or isinstance(raw_value, str) or raw_value is None:
                snapshot[qualifier_key] = raw_value
        return snapshot

    @staticmethod
    def _parse_event_time(time_text: str, *, reference_time: datetime) -> _TimeParseResult:
        if not time_text:
            return _TimeParseResult(event_time=reference_time)

        if _TNR_PATTERN.fullmatch(time_text):
            parsed_tnr = CommunicationPresenter._parse_tnr(time_text, reference_time=reference_time)
            if parsed_tnr is not None:
                return _TimeParseResult(event_time=parsed_tnr)
            return _TimeParseResult(
                event_time=None,
                review_issue=_ReviewIssue(
                    field_name="Tid",
                    popup_reason="kunde inte tolkas",
                    log_reason="ogiltig tid",
                ),
            )

        parsed_exact = CommunicationPresenter._parse_exact_datetime(time_text)
        if parsed_exact is not None:
            return _TimeParseResult(event_time=parsed_exact)

        return _TimeParseResult(
            event_time=None,
            review_issue=_ReviewIssue(
                field_name="Tid",
                popup_reason="kunde inte tolkas",
                log_reason="ogiltig tid",
            ),
        )

    @staticmethod
    def _parse_exact_datetime(time_text: str) -> datetime | None:
        match = _EXACT_DATETIME_PATTERN.fullmatch(time_text)
        if match is None:
            return None

        try:
            year_text = match.group("year")
            year = int(year_text)
            if len(year_text) == 2:
                year += 2000
            return datetime(
                year,
                int(match.group("month")),
                int(match.group("day")),
                int(match.group("hour")),
                int(match.group("minute")),
            )
        except ValueError:
            return None

    @staticmethod
    def _parse_tnr(time_text: str, *, reference_time: datetime) -> datetime | None:
        day = int(time_text[:2])
        hour = int(time_text[2:4])
        minute = int(time_text[4:6])
        if not 1 <= day <= 31 or hour > 23 or minute > 59:
            return None

        candidate_year = reference_time.year
        candidate_month = reference_time.month
        reference_date = reference_time.date()
        for _ in range(24):
            last_day_in_month = monthrange(candidate_year, candidate_month)[1]
            if day <= last_day_in_month:
                candidate = datetime(candidate_year, candidate_month, day, hour, minute)
                if candidate.date() <= reference_date:
                    return candidate

            candidate_year, candidate_month = CommunicationPresenter._previous_month(
                candidate_year,
                candidate_month,
            )

        return None

    @staticmethod
    def _previous_month(year: int, month: int) -> tuple[int, int]:
        if month == 1:
            return year - 1, 12
        return year, month - 1

    @staticmethod
    def _derive_review_issues(entry: CommunicationEntry) -> list[_ReviewIssue]:
        review_issues: list[_ReviewIssue] = []
        if entry.event_time is None:
            review_issues.append(
                _ReviewIssue(
                    field_name="Tid",
                    popup_reason="kunde inte tolkas",
                    log_reason="ogiltig tid",
                )
            )
        if not entry.message_content:
            review_issues.append(
                _ReviewIssue(
                    field_name="Meddelande",
                    popup_reason="saknar innehåll",
                    log_reason="meddelande saknar innehåll",
                )
            )
        if not entry.operator:
            review_issues.append(
                _ReviewIssue(
                    field_name="Operatör",
                    popup_reason="saknar värde",
                    log_reason="operatör saknar värde",
                )
            )
        return review_issues

    @staticmethod
    def _format_event_time(event_time: datetime | None, *, invalid_time: bool) -> str:
        if event_time is None:
            return _INVALID_TIME_LABEL if invalid_time else ""
        return event_time.strftime("%Y-%m-%d %H:%M")

    def _emit_soft_warning(self, review_issues: Sequence[_ReviewIssue]) -> None:
        issue_lines = "\n".join(
            f"- {issue.field_name} – {issue.popup_reason}"
            for issue in review_issues
        )
        self._view.show_warning_dialog(
            "Post sparad, men behöver ses över",
            "Post sparad, men behöver ses över.\n\n"
            "Följande fält kan behöva granskas senare:\n"
            f"{issue_lines}",
        )
        log_reasons = "; ".join(issue.log_reason for issue in review_issues)
        self._logger.warning("Kommunikationspost sparad men behöver ses över: %s", log_reasons)


__all__ = [
    "CommunicationEditorState",
    "CommunicationEntryDetailState",
    "CommunicationFormState",
    "CommunicationFormData",
    "CommunicationLogFilterData",
    "CommunicationLogRow",
    "CommunicationLogState",
    "CommunicationPathChoice",
    "CommunicationPathFieldState",
    "CommunicationPresenter",
    "CommunicationQualifierFieldState",
    "CommunicationViewProtocol",
]

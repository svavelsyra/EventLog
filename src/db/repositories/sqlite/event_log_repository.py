"""Adapter-backed SQLite repository for EventLog.

This is the primary concrete SQLite repository under the approved repository
package layout. It owns repository behavior directly while delegating low-level
database mechanics to the injected ``SQLiteAdapter``.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
import sqlite3
from types import TracebackType
from typing import Callable, cast

from src.db.adapters.event_log_adapter import (
    CommunicationEntry,
    CommunicationOptionConfig,
    CommunicationOptionMutationResult,
    CommunicationQualifierConfig,
    CommunicationSystemConfig,
    EntryFilters,
    EventEntry,
    EventLogAdapter,
    PersonnelEntry,
)
from src.db.repositories.base_repository import BaseRepository
from src.db.sqlite_adapter import SQLiteAdapter
from src.core.communication_portability import (
    CommunicationPortabilityBundle,
    PortableCommunicationOption,
    PortableCommunicationQualifier,
    PortableCommunicationSystem,
)


LOGGER = logging.getLogger(__name__)

EDITED_FLAG_GRACE_PERIOD_SECONDS_KEY = "edited_flag_grace_period_seconds"
DEFAULT_EDITED_FLAG_GRACE_PERIOD_SECONDS = 300


class EventLogRepository(EventLogAdapter, BaseRepository):
    """Primary SQLite repository backed by an injected SQLite adapter."""

    def __init__(self, adapter: SQLiteAdapter) -> None:
        """Create a repository backed by an already-constructed SQLite adapter."""
        BaseRepository.__init__(self, adapter)
        self.initialize_schema()

    @property
    def adapter(self) -> SQLiteAdapter:
        """Return the injected SQLite adapter with its concrete type."""
        return cast(SQLiteAdapter, self._adapter)

    def __enter__(self) -> EventLogRepository:
        """Return the repository instance for ``with`` statement usage."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Roll back on exception and always close via adapter-backed hooks."""
        if exc_type is not None:
            self.rollback()
        self.close()

    def initialize_schema(self) -> None:
        """Ensure the adapter has completed SQLite schema initialization."""
        self.adapter.initialize_schema()
        self._bind_adapter_state()

    def begin_transaction(self) -> None:
        """Start an explicit transaction through the adapter."""
        self.adapter.begin_transaction()
        self._bind_adapter_state()

    def commit(self) -> None:
        """Commit the current transaction through the adapter."""
        self.adapter.commit_transaction()
        self._bind_adapter_state()

    def commit_transaction(self) -> None:
        """Commit the current transaction through the adapter."""
        self.commit()

    def rollback(self) -> None:
        """Roll back the current transaction through the adapter."""
        self.adapter.rollback_transaction()
        self._bind_adapter_state()

    def rollback_transaction(self) -> None:
        """Roll back the current transaction through the adapter."""
        self.rollback()

    def close(self) -> None:
        """Close the underlying adapter and its database resources."""
        self.adapter.close()

    def _commit_if_needed(self) -> None:
        """Commit writes that are not part of an explicit transaction."""
        if not self.adapter._explicit_transaction_active:
            self.commit()

    def get_active_communication_system_configs(self) -> list[CommunicationSystemConfig]:
        """Return all active communication systems with assembled options and qualifiers."""
        system_rows = self.adapter.fetch(
            """
            SELECT id, system_name, system_type, child_label, sort_order
            FROM communication_systems
            WHERE is_active = 1
            ORDER BY sort_order IS NULL, sort_order, system_name, id
            """
        )
        if not system_rows:
            return []

        options_by_system = self._get_active_communication_options_by_system()
        qualifiers_by_system = self._get_active_communication_qualifiers_by_system()

        return [
            self._row_to_communication_system_config(
                row,
                options_by_system.get(int(row["id"]), ()),
                qualifiers_by_system.get(int(row["id"]), ()),
            )
            for row in system_rows
        ]

    def get_active_communication_system_config(
        self,
        system_name: str,
    ) -> CommunicationSystemConfig | None:
        """Return one active communication system config by name, or ``None``."""
        for system_config in self.get_active_communication_system_configs():
            if system_config.system_name == system_name:
                return system_config
        return None

    def add_communication_option(
        self,
        *,
        system_name: str,
        option_value: str,
        option_label: str,
        parent_option_id: int | None = None,
        child_label: str | None = None,
        sort_order: int | None = None,
    ) -> CommunicationOptionMutationResult:
        """Create or reactivate one communication option beneath a chosen parent."""
        normalized_value = self._normalize_required_config_text(option_value, "option_value")
        normalized_label = self._normalize_required_config_text(option_label, "option_label")

        system_row = self.adapter.fetchone(
            "SELECT id FROM communication_systems WHERE system_name = ? AND is_active = 1",
            (system_name,),
        )
        if system_row is None:
            return CommunicationOptionMutationResult(status="not_found")

        system_id = int(system_row["id"])

        if parent_option_id is not None:
            parent_row = self.adapter.fetchone(
                """
                SELECT id
                FROM communication_options
                WHERE id = ?
                  AND communication_system_id = ?
                  AND is_active = 1
                """,
                (parent_option_id, system_id),
            )
            if parent_row is None:
                return CommunicationOptionMutationResult(status="not_found")

        existing_row = self.adapter.fetchone(
            """
            SELECT id, is_active
            FROM communication_options
            WHERE communication_system_id = ?
              AND COALESCE(parent_option_id, 0) = COALESCE(?, 0)
              AND option_value = ?
            """,
            (system_id, parent_option_id, normalized_value),
        )
        if existing_row is not None:
            existing_option_id = int(existing_row["id"])
            if bool(existing_row["is_active"]):
                return CommunicationOptionMutationResult(
                    status="already_exists",
                    option_id=existing_option_id,
                )

            self.adapter.execute(
                """
                UPDATE communication_options
                SET option_label = ?,
                    child_label = ?,
                    sort_order = ?,
                    is_active = 1
                WHERE id = ?
                """,
                (normalized_label, child_label, sort_order, existing_option_id),
            )
            self._commit_if_needed()
            self._bind_adapter_state()
            return CommunicationOptionMutationResult(
                status="reactivated",
                option_id=existing_option_id,
                changed=True,
            )

        cursor = self.adapter.execute(
            """
            INSERT INTO communication_options (
                communication_system_id,
                option_value,
                option_label,
                parent_option_id,
                child_label,
                sort_order,
                is_active
            )
            VALUES (?, ?, ?, ?, ?, ?, 1)
            """,
            (system_id, normalized_value, normalized_label, parent_option_id, child_label, sort_order),
        )
        self._commit_if_needed()
        self._bind_adapter_state()

        inserted_option_id = cursor.lastrowid
        if inserted_option_id is None:
            raise RuntimeError("SQLite did not return a row ID for the inserted communication option.")

        return CommunicationOptionMutationResult(
            status="created",
            option_id=inserted_option_id,
            changed=True,
        )

    def rename_communication_option(
        self,
        *,
        option_id: int,
        option_label: str,
    ) -> CommunicationOptionMutationResult:
        """Rename one communication option row without rewriting saved entries."""
        normalized_label = self._normalize_required_config_text(option_label, "option_label")
        existing_row = self.adapter.fetchone(
            "SELECT id, option_label, is_active FROM communication_options WHERE id = ?",
            (option_id,),
        )
        if existing_row is None:
            return CommunicationOptionMutationResult(status="not_found")
        if not bool(existing_row["is_active"]):
            return CommunicationOptionMutationResult(status="already_inactive", option_id=option_id)
        if str(existing_row["option_label"]) == normalized_label:
            return CommunicationOptionMutationResult(status="unchanged", option_id=option_id)

        self.adapter.execute(
            "UPDATE communication_options SET option_label = ? WHERE id = ?",
            (normalized_label, option_id),
        )
        self._commit_if_needed()
        self._bind_adapter_state()
        return CommunicationOptionMutationResult(
            status="updated",
            option_id=option_id,
            changed=True,
        )

    def deactivate_communication_option(
        self,
        *,
        option_id: int,
    ) -> CommunicationOptionMutationResult:
        """Soft-deactivate one communication option subtree for future use only."""
        existing_row = self.adapter.fetchone(
            "SELECT id, is_active FROM communication_options WHERE id = ?",
            (option_id,),
        )
        if existing_row is None:
            return CommunicationOptionMutationResult(status="not_found")
        if not bool(existing_row["is_active"]):
            return CommunicationOptionMutationResult(status="already_inactive", option_id=option_id)

        self.adapter.execute(
            """
            WITH RECURSIVE option_subtree(id) AS (
                SELECT id
                FROM communication_options
                WHERE id = ?

                UNION ALL

                SELECT child.id
                FROM communication_options AS child
                JOIN option_subtree AS parent
                    ON child.parent_option_id = parent.id
            )
            UPDATE communication_options
            SET is_active = 0
            WHERE id IN (SELECT id FROM option_subtree)
            """,
            (option_id,),
        )
        self._commit_if_needed()
        self._bind_adapter_state()
        return CommunicationOptionMutationResult(
            status="deactivated",
            option_id=option_id,
            changed=True,
        )

    def replace_communication_portability_bundle(
        self,
        bundle: CommunicationPortabilityBundle,
    ) -> None:
        """Replace active communication config exactly to match one validated bundle."""
        started_transaction = not self.adapter._explicit_transaction_active
        if started_transaction:
            self.begin_transaction()

        try:
            imported_system_names = tuple(
                system.system_name
                for system in bundle.communication_systems
            )

            for system in bundle.communication_systems:
                system_id = self._upsert_communication_system(system)
                self._replace_communication_option_branch(
                    system_id=system_id,
                    parent_option_id=None,
                    options=system.options,
                )
                self._replace_communication_qualifiers(
                    system_id=system_id,
                    qualifiers=system.qualifiers,
                )

            self._deactivate_missing_communication_systems(imported_system_names)

            if started_transaction:
                self.commit()
        except Exception:
            if started_transaction:
                self.rollback()
            raise
        finally:
            self._bind_adapter_state()

    def create_communication_entry(self, entry: CommunicationEntry) -> int:
        """Persist a communication entry and return its database-assigned ID."""
        logged_time = datetime.now()

        cursor = self.adapter.execute(
            """
            INSERT INTO communication_entries (
                event_time,
                logged_time,
                message_content,
                from_field,
                to_field,
                operator,
                confirmed,
                edited,
                communication_system,
                method_type,
                method_channel,
                channel_designation,
                system_capabilities
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                self._serialize_datetime(entry.event_time),
                logged_time.isoformat(),
                entry.message_content,
                entry.from_field,
                entry.to_field,
                entry.operator,
                int(entry.confirmed),
                int(entry.edited),
                entry.communication_system,
                entry.method_type,
                entry.method_channel,
                entry.channel_designation,
                self._serialize_system_capabilities(entry.system_capabilities),
            ),
        )

        self._commit_if_needed()
        self._bind_adapter_state()

        inserted_entry_id = cursor.lastrowid
        if inserted_entry_id is None:
            raise RuntimeError("SQLite did not return a row ID for the inserted communication entry.")

        return inserted_entry_id

    def get_communication_entry(self, entry_id: int) -> CommunicationEntry | None:
        """Return one communication entry by ID, or ``None`` if it is missing."""
        row = self.adapter.fetchone(
            "SELECT * FROM communication_entries WHERE id = ?",
            (entry_id,),
        )

        if row is None:
            return None

        return self._row_to_communication_entry(row)

    def get_all_communication_entries(
        self,
        filters: EntryFilters | None = None,
    ) -> list[CommunicationEntry]:
        """Return communication entries matching optional filters."""
        where_clauses, params = self._build_communication_filter_clauses(filters)
        query = "SELECT * FROM communication_entries"
        if where_clauses:
            query = f"{query} WHERE {' AND '.join(where_clauses)}"

        query = f"{query} ORDER BY event_time DESC, id DESC"
        rows = self.adapter.fetch(query, tuple(params))
        return [self._row_to_communication_entry(row) for row in rows]

    def update_communication_entry(self, entry: CommunicationEntry) -> bool:
        """Update an existing communication entry and report success."""
        if entry.id is None:
            return False

        existing_entry = self.get_communication_entry(entry.id)
        if existing_entry is None or existing_entry.logged_time is None:
            return False

        edited_flag = self._resolve_edited_flag(existing_entry)

        cursor = self.adapter.execute(
            """
            UPDATE communication_entries
            SET event_time = ?,
                message_content = ?,
                from_field = ?,
                to_field = ?,
                operator = ?,
                confirmed = ?,
                edited = ?,
                communication_system = ?,
                method_type = ?,
                method_channel = ?,
                channel_designation = ?,
                system_capabilities = ?
            WHERE id = ?
            """,
            (
                self._serialize_datetime(entry.event_time),
                entry.message_content,
                entry.from_field,
                entry.to_field,
                entry.operator,
                int(entry.confirmed),
                int(edited_flag),
                entry.communication_system,
                entry.method_type,
                entry.method_channel,
                entry.channel_designation,
                self._serialize_system_capabilities(entry.system_capabilities),
                entry.id,
            ),
        )

        self._commit_if_needed()
        self._bind_adapter_state()
        return cursor.rowcount > 0

    def delete_communication_entry(self, entry_id: int) -> bool:
        """Delete a communication entry by ID and report success."""
        cursor = self.adapter.execute(
            "DELETE FROM communication_entries WHERE id = ?",
            (entry_id,),
        )

        self._commit_if_needed()
        self._bind_adapter_state()
        return cursor.rowcount > 0

    def search_communication_entries(
        self,
        search_text: str,
        filters: EntryFilters | None = None,
    ) -> list[CommunicationEntry]:
        """Search communication entries by message content plus optional filters."""
        where_clauses, params = self._build_communication_filter_clauses(filters)
        where_clauses.insert(0, "LOWER(message_content) LIKE LOWER(?)")
        params.insert(0, f"%{search_text}%")

        query = (
            "SELECT * FROM communication_entries "
            f"WHERE {' AND '.join(where_clauses)} "
            "ORDER BY event_time DESC, id DESC"
        )
        rows = self.adapter.fetch(query, tuple(params))
        return [self._row_to_communication_entry(row) for row in rows]

    def create_event_entry(self, entry: EventEntry) -> int:
        """Persist an event entry and return its database-assigned ID."""
        logged_time = datetime.now()
        priority = entry.priority if entry.priority is not None else "Normal"

        cursor = self.adapter.execute(
            """
            INSERT INTO event_entries (
                event_description,
                whom,
                event_time,
                logged_time,
                operator,
                priority,
                category,
                edited
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry.event_description,
                entry.whom,
                self._serialize_datetime(entry.event_time),
                logged_time.isoformat(),
                entry.operator,
                priority,
                entry.category,
                int(entry.edited),
            ),
        )

        self._commit_if_needed()
        self._bind_adapter_state()

        inserted_entry_id = cursor.lastrowid
        if inserted_entry_id is None:
            raise RuntimeError("SQLite did not return a row ID for the inserted event entry.")

        return inserted_entry_id

    def get_event_entry(self, entry_id: int) -> EventEntry | None:
        """Return one event entry by ID, or ``None`` if it is missing."""
        row = self.adapter.fetchone(
            "SELECT * FROM event_entries WHERE id = ?",
            (entry_id,),
        )

        if row is None:
            return None

        return self._row_to_event_entry(row)

    def get_all_event_entries(
        self,
        filters: EntryFilters | None = None,
    ) -> list[EventEntry]:
        """Return event entries matching optional filters."""
        where_clauses, params = self._build_event_filter_clauses(filters)
        query = "SELECT * FROM event_entries"
        if where_clauses:
            query = f"{query} WHERE {' AND '.join(where_clauses)}"

        query = f"{query} ORDER BY event_time DESC, id DESC"
        rows = self.adapter.fetch(query, tuple(params))
        return [self._row_to_event_entry(row) for row in rows]

    def update_event_entry(self, entry: EventEntry) -> bool:
        """Update an existing event entry and report success."""
        if entry.id is None:
            return False

        existing_entry = self.get_event_entry(entry.id)
        if existing_entry is None or existing_entry.logged_time is None:
            return False

        edited_flag = self._resolve_edited_flag(existing_entry)
        priority = entry.priority if entry.priority is not None else "Normal"

        cursor = self.adapter.execute(
            """
            UPDATE event_entries
            SET event_description = ?,
                whom = ?,
                event_time = ?,
                operator = ?,
                priority = ?,
                category = ?,
                edited = ?
            WHERE id = ?
            """,
            (
                entry.event_description,
                entry.whom,
                self._serialize_datetime(entry.event_time),
                entry.operator,
                priority,
                entry.category,
                int(edited_flag),
                entry.id,
            ),
        )

        self._commit_if_needed()
        self._bind_adapter_state()
        return cursor.rowcount > 0

    def delete_event_entry(self, entry_id: int) -> bool:
        """Delete an event entry by ID and report success."""
        cursor = self.adapter.execute(
            "DELETE FROM event_entries WHERE id = ?",
            (entry_id,),
        )

        self._commit_if_needed()
        self._bind_adapter_state()
        return cursor.rowcount > 0

    def search_event_entries(
        self,
        search_text: str,
        filters: EntryFilters | None = None,
    ) -> list[EventEntry]:
        """Search event entries by description text plus optional filters."""
        where_clauses, params = self._build_event_filter_clauses(filters)
        where_clauses.insert(0, "LOWER(event_description) LIKE LOWER(?)")
        params.insert(0, f"%{search_text}%")

        query = (
            "SELECT * FROM event_entries "
            f"WHERE {' AND '.join(where_clauses)} "
            "ORDER BY event_time DESC, id DESC"
        )
        rows = self.adapter.fetch(query, tuple(params))
        return [self._row_to_event_entry(row) for row in rows]

    def create_personnel_entry(self, entry: PersonnelEntry) -> int:
        """Persist a personnel entry and return its database-assigned ID."""
        self._validate_personnel_alarm_fields(entry.alarm_enabled, entry.expected_checkin_time)

        logged_time = datetime.now()
        last_contact_time = entry.last_contact_time or logged_time

        cursor = self.adapter.execute(
            """
            INSERT INTO personnel_entries (
                who,
                status,
                location,
                last_contact_time,
                mission_notes,
                logged_time,
                operator,
                edited,
                active,
                supersedes,
                alarm_enabled,
                expected_checkin_time,
                alarm_triggered
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry.who,
                entry.status,
                entry.location,
                self._serialize_datetime(last_contact_time),
                entry.mission_notes,
                logged_time.isoformat(),
                entry.operator,
                int(entry.edited),
                int(entry.active),
                entry.supersedes,
                int(entry.alarm_enabled),
                self._serialize_datetime(entry.expected_checkin_time),
                int(entry.alarm_triggered),
            ),
        )

        self._commit_if_needed()
        self._bind_adapter_state()

        inserted_entry_id = cursor.lastrowid
        if inserted_entry_id is None:
            raise RuntimeError("SQLite did not return a row ID for the inserted personnel entry.")

        return inserted_entry_id

    def get_personnel_entry(self, entry_id: int) -> PersonnelEntry | None:
        """Return one personnel entry by ID, or ``None`` if it is missing."""
        row = self.adapter.fetchone(
            "SELECT * FROM personnel_entries WHERE id = ?",
            (entry_id,),
        )

        if row is None:
            return None

        return self._row_to_personnel_entry(row)

    def get_all_personnel_entries(
        self,
        filters: EntryFilters | None = None,
    ) -> list[PersonnelEntry]:
        """Return personnel entries matching optional filters."""
        where_clauses, params = self._build_personnel_filter_clauses(filters)
        query = "SELECT * FROM personnel_entries"
        if where_clauses:
            query = f"{query} WHERE {' AND '.join(where_clauses)}"

        query = f"{query} ORDER BY logged_time DESC, id DESC"
        rows = self.adapter.fetch(query, tuple(params))
        return [self._row_to_personnel_entry(row) for row in rows]

    def update_personnel_entry(self, entry: PersonnelEntry) -> bool:
        """Update an existing personnel entry and report success."""
        if entry.id is None:
            return False

        existing_entry = self.get_personnel_entry(entry.id)
        if existing_entry is None or existing_entry.logged_time is None:
            return False

        self._validate_personnel_alarm_fields(entry.alarm_enabled, entry.expected_checkin_time)
        edited_flag = self._resolve_edited_flag(existing_entry)

        cursor = self.adapter.execute(
            """
            UPDATE personnel_entries
            SET who = ?,
                status = ?,
                location = ?,
                last_contact_time = ?,
                mission_notes = ?,
                operator = ?,
                edited = ?,
                active = ?,
                supersedes = ?,
                alarm_enabled = ?,
                expected_checkin_time = ?,
                alarm_triggered = ?
            WHERE id = ?
            """,
            (
                entry.who,
                entry.status,
                entry.location,
                self._serialize_datetime(entry.last_contact_time),
                entry.mission_notes,
                entry.operator,
                int(edited_flag),
                int(entry.active),
                entry.supersedes,
                int(entry.alarm_enabled),
                self._serialize_datetime(entry.expected_checkin_time),
                int(entry.alarm_triggered),
                entry.id,
            ),
        )

        self._commit_if_needed()
        self._bind_adapter_state()
        return cursor.rowcount > 0

    def delete_personnel_entry(self, entry_id: int) -> bool:
        """Delete a personnel entry by ID and report success."""
        cursor = self.adapter.execute(
            "DELETE FROM personnel_entries WHERE id = ?",
            (entry_id,),
        )

        self._commit_if_needed()
        self._bind_adapter_state()
        return cursor.rowcount > 0

    def search_personnel_entries(
        self,
        search_text: str,
        filters: EntryFilters | None = None,
    ) -> list[PersonnelEntry]:
        """Search personnel entries by text plus optional filters."""
        where_clauses, params = self._build_personnel_filter_clauses(filters)
        search_pattern = f"%{search_text}%"
        where_clauses.insert(
            0,
            "("
            "LOWER(COALESCE(who, '')) LIKE LOWER(?) OR "
            "LOWER(COALESCE(status, '')) LIKE LOWER(?) OR "
            "LOWER(COALESCE(location, '')) LIKE LOWER(?) OR "
            "LOWER(COALESCE(mission_notes, '')) LIKE LOWER(?)"
            ")",
        )
        params[0:0] = [search_pattern, search_pattern, search_pattern, search_pattern]

        query = (
            "SELECT * FROM personnel_entries "
            f"WHERE {' AND '.join(where_clauses)} "
            "ORDER BY logged_time DESC, id DESC"
        )
        rows = self.adapter.fetch(query, tuple(params))
        return [self._row_to_personnel_entry(row) for row in rows]

    def get_active_personnel_entries(self) -> list[PersonnelEntry]:
        """Return personnel entries marked as active, sorted by last contact."""
        rows = self.adapter.fetch(
            """
            SELECT * FROM personnel_entries
            WHERE active = 1
            ORDER BY last_contact_time DESC, logged_time DESC, id DESC
            """
        )
        return [self._row_to_personnel_entry(row) for row in rows]

    def get_personnel_history(self, who: str) -> list[PersonnelEntry]:
        """Return all personnel history rows for the given person or group."""
        rows = self.adapter.fetch(
            """
            SELECT * FROM personnel_entries
            WHERE who = ?
            ORDER BY logged_time DESC, id DESC
            """,
            (who,),
        )
        return [self._row_to_personnel_entry(row) for row in rows]

    def get_overdue_alarms(self) -> list[PersonnelEntry]:
        """Return overdue, enabled, not-yet-triggered personnel alarms."""
        rows = self.adapter.fetch(
            """
            SELECT * FROM personnel_entries
            WHERE alarm_enabled = 1
              AND alarm_triggered = 0
              AND expected_checkin_time < ?
            ORDER BY expected_checkin_time ASC, id ASC
            """,
            (datetime.now().isoformat(),),
        )
        return [self._row_to_personnel_entry(row) for row in rows]

    def _get_setting(
        self,
        key: str,
        default: object = None,
        validator: Callable[[str], object] | None = None,
    ) -> object:
        """Return a setting value or a default for non-critical settings faults."""
        try:
            row = self.adapter.fetchone(
                "SELECT value FROM settings WHERE key = ?",
                (key,),
            )
        except sqlite3.OperationalError:
            LOGGER.warning(
                "Could not read setting %s because the settings table is unavailable; using default %r.",
                key,
                default,
            )
            return default

        if row is None:
            LOGGER.warning("Setting %s is missing; using default %r.", key, default)
            return default

        raw_value = str(row["value"])
        if validator is None:
            return raw_value

        try:
            return validator(raw_value)
        except (TypeError, ValueError):
            LOGGER.warning("Invalid setting %s value %r; using default %r.", key, raw_value, default)
            return default

    def _upsert_communication_system(
        self,
        system: PortableCommunicationSystem,
    ) -> int:
        existing_row = self.adapter.fetchone(
            "SELECT id FROM communication_systems WHERE system_name = ?",
            (system.system_name,),
        )
        if existing_row is None:
            cursor = self.adapter.execute(
                """
                INSERT INTO communication_systems (
                    system_name,
                    system_type,
                    child_label,
                    sort_order,
                    is_active
                )
                VALUES (?, ?, ?, ?, 1)
                """,
                (
                    system.system_name,
                    system.system_type,
                    system.child_label,
                    system.sort_order,
                ),
            )
            inserted_system_id = cursor.lastrowid
            if inserted_system_id is None:
                raise RuntimeError("SQLite did not return a row ID for the inserted communication system.")
            return int(inserted_system_id)

        system_id = int(existing_row["id"])
        self.adapter.execute(
            """
            UPDATE communication_systems
            SET system_type = ?,
                child_label = ?,
                sort_order = ?,
                is_active = 1
            WHERE id = ?
            """,
            (
                system.system_type,
                system.child_label,
                system.sort_order,
                system_id,
            ),
        )
        return system_id

    def _replace_communication_option_branch(
        self,
        *,
        system_id: int,
        parent_option_id: int | None,
        options: tuple[PortableCommunicationOption, ...],
    ) -> None:
        existing_rows = self.adapter.fetch(
            """
            SELECT id, option_value
            FROM communication_options
            WHERE communication_system_id = ?
              AND COALESCE(parent_option_id, 0) = COALESCE(?, 0)
            ORDER BY id
            """,
            (system_id, parent_option_id),
        )
        existing_rows_by_value = {
            str(row["option_value"]): row
            for row in existing_rows
        }
        imported_option_values: set[str] = set()

        for option in options:
            imported_option_values.add(option.option_value)
            existing_row = existing_rows_by_value.get(option.option_value)
            if existing_row is None:
                cursor = self.adapter.execute(
                    """
                    INSERT INTO communication_options (
                        communication_system_id,
                        option_value,
                        option_label,
                        parent_option_id,
                        child_label,
                        sort_order,
                        is_active
                    )
                    VALUES (?, ?, ?, ?, ?, ?, 1)
                    """,
                    (
                        system_id,
                        option.option_value,
                        option.option_label,
                        parent_option_id,
                        option.child_label,
                        option.sort_order,
                    ),
                )
                option_id = cursor.lastrowid
                if option_id is None:
                    raise RuntimeError(
                        "SQLite did not return a row ID for the inserted communication option during portability import."
                    )
                current_option_id = int(option_id)
            else:
                current_option_id = int(existing_row["id"])
                self.adapter.execute(
                    """
                    UPDATE communication_options
                    SET option_label = ?,
                        parent_option_id = ?,
                        child_label = ?,
                        sort_order = ?,
                        is_active = 1
                    WHERE id = ?
                    """,
                    (
                        option.option_label,
                        parent_option_id,
                        option.child_label,
                        option.sort_order,
                        current_option_id,
                    ),
                )

            self._replace_communication_option_branch(
                system_id=system_id,
                parent_option_id=current_option_id,
                options=option.children,
            )

        for row in existing_rows:
            if str(row["option_value"]) not in imported_option_values:
                self._deactivate_communication_option_subtree(int(row["id"]))

    def _replace_communication_qualifiers(
        self,
        *,
        system_id: int,
        qualifiers: tuple[PortableCommunicationQualifier, ...],
    ) -> None:
        self.adapter.execute(
            "DELETE FROM communication_qualifiers_config WHERE communication_system_id = ?",
            (system_id,),
        )
        for qualifier in qualifiers:
            self.adapter.execute(
                """
                INSERT INTO communication_qualifiers_config (
                    communication_system_id,
                    qualifier_key,
                    label,
                    field_type,
                    valid_values,
                    default_value,
                    help_text,
                    visibility_mode
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    system_id,
                    qualifier.qualifier_key,
                    qualifier.label,
                    qualifier.field_type,
                    self._serialize_communication_qualifier_valid_values(qualifier.valid_values),
                    self._serialize_communication_qualifier_default_value(qualifier.default_value),
                    qualifier.help_text,
                    qualifier.visibility_mode,
                ),
            )

    def _deactivate_missing_communication_systems(
        self,
        imported_system_names: tuple[str, ...],
    ) -> None:
        if imported_system_names:
            placeholders = ", ".join("?" for _ in imported_system_names)
            self.adapter.execute(
                f"UPDATE communication_systems SET is_active = 0 WHERE system_name NOT IN ({placeholders})",
                imported_system_names,
            )
            self.adapter.execute(
                f"""
                UPDATE communication_options
                SET is_active = 0
                WHERE communication_system_id IN (
                    SELECT id
                    FROM communication_systems
                    WHERE system_name NOT IN ({placeholders})
                )
                """,
                imported_system_names,
            )
            return

        self.adapter.execute("UPDATE communication_systems SET is_active = 0")
        self.adapter.execute("UPDATE communication_options SET is_active = 0")

    def _deactivate_communication_option_subtree(self, option_id: int) -> None:
        self.adapter.execute(
            """
            WITH RECURSIVE option_subtree(id) AS (
                SELECT id
                FROM communication_options
                WHERE id = ?

                UNION ALL

                SELECT child.id
                FROM communication_options AS child
                JOIN option_subtree AS parent
                    ON child.parent_option_id = parent.id
            )
            UPDATE communication_options
            SET is_active = 0
            WHERE id IN (SELECT id FROM option_subtree)
            """,
            (option_id,),
        )

    def _get_active_communication_options_by_system(
        self,
    ) -> dict[int, tuple[CommunicationOptionConfig, ...]]:
        """Return recursive active option trees keyed by communication-system ID."""
        option_rows = self.adapter.fetch(
            """
            SELECT
                co.id,
                co.communication_system_id,
                co.option_value,
                co.option_label,
                co.parent_option_id,
                co.child_label,
                co.sort_order
            FROM communication_options AS co
            JOIN communication_systems AS cs
                ON cs.id = co.communication_system_id
            WHERE cs.is_active = 1
              AND co.is_active = 1
            ORDER BY
                co.communication_system_id,
                co.parent_option_id IS NOT NULL,
                COALESCE(co.parent_option_id, 0),
                co.sort_order IS NULL,
                co.sort_order,
                co.option_label,
                co.option_value,
                co.id
            """
        )

        rows_by_system: dict[int, dict[int | None, list[sqlite3.Row]]] = {}
        for row in option_rows:
            system_id = int(row["communication_system_id"])
            parent_option_id = cast(int | None, row["parent_option_id"])
            rows_by_parent = rows_by_system.setdefault(system_id, {})
            rows_by_parent.setdefault(parent_option_id, []).append(row)

        option_trees: dict[int, tuple[CommunicationOptionConfig, ...]] = {}
        for system_id, rows_by_parent in rows_by_system.items():
            option_trees[system_id] = self._build_communication_option_branch(
                rows_by_parent,
                parent_option_id=None,
            )
        return option_trees

    def _build_communication_option_branch(
        self,
        rows_by_parent: dict[int | None, list[sqlite3.Row]],
        parent_option_id: int | None,
    ) -> tuple[CommunicationOptionConfig, ...]:
        """Recursively assemble child options beneath one parent option ID."""
        return tuple(
            CommunicationOptionConfig(
                option_id=int(row["id"]),
                option_value=str(row["option_value"]),
                option_label=str(row["option_label"]),
                child_label=cast(str | None, row["child_label"]),
                sort_order=cast(int | None, row["sort_order"]),
                children=self._build_communication_option_branch(
                    rows_by_parent,
                    parent_option_id=int(row["id"]),
                ),
            )
            for row in rows_by_parent.get(parent_option_id, [])
        )

    def _get_active_communication_qualifiers_by_system(
        self,
    ) -> dict[int, tuple[CommunicationQualifierConfig, ...]]:
        """Return active-system qualifier definitions keyed by system ID."""
        qualifier_rows = self.adapter.fetch(
            """
            SELECT
                cqc.communication_system_id,
                cqc.qualifier_key,
                cqc.label,
                cqc.field_type,
                cqc.valid_values,
                cqc.default_value,
                cqc.help_text,
                cqc.visibility_mode
            FROM communication_qualifiers_config AS cqc
            JOIN communication_systems AS cs
                ON cs.id = cqc.communication_system_id
            WHERE cs.is_active = 1
            ORDER BY
                cqc.communication_system_id,
                cqc.qualifier_key,
                cqc.id
            """
        )

        qualifiers_by_system: dict[int, list[CommunicationQualifierConfig]] = {}
        for row in qualifier_rows:
            system_id = int(row["communication_system_id"])
            qualifiers_by_system.setdefault(system_id, []).append(
                self._row_to_communication_qualifier_config(row)
            )

        return {
            system_id: tuple(qualifiers)
            for system_id, qualifiers in qualifiers_by_system.items()
        }

    @staticmethod
    def _row_to_communication_system_config(
        row: sqlite3.Row,
        options: tuple[CommunicationOptionConfig, ...],
        qualifiers: tuple[CommunicationQualifierConfig, ...],
    ) -> CommunicationSystemConfig:
        """Convert one communication-system row plus related data into a read model."""
        return CommunicationSystemConfig(
            system_id=int(row["id"]),
            system_name=str(row["system_name"]),
            system_type=str(row["system_type"]),
            child_label=cast(str | None, row["child_label"]),
            sort_order=cast(int | None, row["sort_order"]),
            options=options,
            qualifiers=qualifiers,
        )

    def _row_to_communication_qualifier_config(
        self,
        row: sqlite3.Row,
    ) -> CommunicationQualifierConfig:
        """Convert one qualifier row into a caller-facing config shape."""
        field_type = str(row["field_type"])
        raw_default_value = cast(str | None, row["default_value"])

        return CommunicationQualifierConfig(
            qualifier_key=str(row["qualifier_key"]),
            label=str(row["label"]),
            field_type=field_type,
            valid_values=self._deserialize_valid_values(cast(str | None, row["valid_values"])),
            default_value=self._deserialize_qualifier_default_value(field_type, raw_default_value),
            help_text=cast(str | None, row["help_text"]),
            visibility_mode=str(row["visibility_mode"]),
        )

    @staticmethod
    def _deserialize_valid_values(raw_value: str | None) -> tuple[str, ...] | None:
        """Convert stored JSON arrays for qualifier valid-values into Python tuples."""
        if raw_value is None:
            return None

        decoded_value = json.loads(raw_value)
        if not isinstance(decoded_value, list):
            raise ValueError("Qualifier valid_values must decode to a JSON array.")

        return tuple(str(value) for value in decoded_value)

    @staticmethod
    def _deserialize_qualifier_default_value(
        field_type: str,
        raw_value: str | None,
    ) -> bool | str | None:
        """Convert stored qualifier defaults into stable Python values."""
        if raw_value is None:
            return None

        if field_type != "boolean":
            return raw_value

        normalized_value = raw_value.strip().lower()
        if normalized_value == "true":
            return True
        if normalized_value == "false":
            return False

        raise ValueError(f"Unsupported boolean default value: {raw_value!r}")

    @staticmethod
    def _serialize_communication_qualifier_valid_values(
        valid_values: tuple[str, ...] | None,
    ) -> str | None:
        """Convert qualifier valid-values into the SQLite JSON text representation."""
        if valid_values is None:
            return None
        return json.dumps(list(valid_values))

    @staticmethod
    def _serialize_communication_qualifier_default_value(
        default_value: bool | str | None,
    ) -> str | None:
        """Convert stable qualifier defaults into the SQLite text representation."""
        if default_value is None:
            return None
        if isinstance(default_value, bool):
            return "true" if default_value else "false"
        return default_value

    @staticmethod
    def _normalize_required_config_text(value: str, field_name: str) -> str:
        """Trim and validate required communication-config text inputs."""
        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError(f"{field_name} must not be empty.")
        return normalized_value

    def _resolve_edited_flag(
        self,
        existing_entry: CommunicationEntry | EventEntry | PersonnelEntry,
    ) -> bool:
        """Return whether an update should mark an entry as edited."""
        if existing_entry.edited:
            return True

        if existing_entry.logged_time is None:
            return False

        return datetime.now() - existing_entry.logged_time > timedelta(
            seconds=self._get_edited_flag_grace_period_seconds()
        )

    def _get_edited_flag_grace_period_seconds(self) -> int:
        """Return the configured edited-flag grace period in seconds."""
        return cast(
            int,
            self._get_setting(
                EDITED_FLAG_GRACE_PERIOD_SECONDS_KEY,
                default=DEFAULT_EDITED_FLAG_GRACE_PERIOD_SECONDS,
                validator=self._validate_non_negative_integer_setting,
            ),
        )

    @staticmethod
    def _validate_non_negative_integer_setting(raw_value: str) -> int:
        """Parse a setting value as a non-negative integer."""
        value = int(raw_value)
        if value < 0:
            raise ValueError("Setting value must be non-negative.")
        return value

    def _row_to_event_entry(self, row) -> EventEntry:
        """Convert a SQLite row into an event entry domain model."""
        return EventEntry(
            id=row["id"],
            event_description=row["event_description"],
            operator=row["operator"],
            whom=row["whom"],
            event_time=(
                datetime.fromisoformat(row["event_time"])
                if row["event_time"] is not None
                else None
            ),
            logged_time=datetime.fromisoformat(row["logged_time"]),
            priority=row["priority"],
            category=row["category"],
            edited=bool(row["edited"]),
        )

    def _row_to_communication_entry(self, row) -> CommunicationEntry:
        """Convert a SQLite row into a communication entry domain model."""
        system_capabilities = row["system_capabilities"]

        return CommunicationEntry(
            id=row["id"],
            message_content=row["message_content"],
            operator=row["operator"],
            event_time=(
                datetime.fromisoformat(row["event_time"])
                if row["event_time"] is not None
                else None
            ),
            logged_time=datetime.fromisoformat(row["logged_time"]),
            from_field=row["from_field"],
            to_field=row["to_field"],
            confirmed=bool(row["confirmed"]),
            edited=bool(row["edited"]),
            communication_system=row["communication_system"],
            method_type=row["method_type"],
            method_channel=row["method_channel"],
            channel_designation=row["channel_designation"],
            system_capabilities=(
                json.loads(system_capabilities)
                if system_capabilities is not None
                else None
            ),
        )

    def _row_to_personnel_entry(self, row) -> PersonnelEntry:
        """Convert a SQLite row into a personnel entry domain model."""
        return PersonnelEntry(
            id=row["id"],
            who=row["who"],
            operator=row["operator"],
            status=row["status"],
            location=row["location"],
            last_contact_time=(
                datetime.fromisoformat(row["last_contact_time"])
                if row["last_contact_time"] is not None
                else None
            ),
            mission_notes=row["mission_notes"],
            logged_time=datetime.fromisoformat(row["logged_time"]),
            edited=bool(row["edited"]),
            active=bool(row["active"]),
            supersedes=row["supersedes"],
            alarm_enabled=bool(row["alarm_enabled"]),
            expected_checkin_time=(
                datetime.fromisoformat(row["expected_checkin_time"])
                if row["expected_checkin_time"] is not None
                else None
            ),
            alarm_triggered=bool(row["alarm_triggered"]),
        )

    @staticmethod
    def _build_communication_filter_clauses(
        filters: EntryFilters | None,
    ) -> tuple[list[str], list[object]]:
        """Build reusable WHERE clauses and parameters for communication filters."""
        where_clauses: list[str] = []
        params: list[object] = []

        if not filters:
            return where_clauses, params

        exact_match_filters = (
            "operator",
            "communication_system",
            "method_type",
            "from_field",
            "to_field",
        )
        for field_name in exact_match_filters:
            if field_name in filters:
                where_clauses.append(f"{field_name} = ?")
                params.append(filters[field_name])

        if "participants" in filters:
            where_clauses.append("(from_field = ? OR to_field = ?)")
            params.extend([filters["participants"], filters["participants"]])

        if "date_from" in filters:
            where_clauses.append("event_time >= ?")
            params.append(EventLogRepository._normalize_filter_value(filters["date_from"]))

        if "date_to" in filters:
            where_clauses.append("event_time <= ?")
            params.append(EventLogRepository._normalize_filter_value(filters["date_to"]))

        return where_clauses, params

    @staticmethod
    def _build_event_filter_clauses(
        filters: EntryFilters | None,
    ) -> tuple[list[str], list[object]]:
        """Build reusable WHERE clauses and parameters for event filters."""
        where_clauses: list[str] = []
        params: list[object] = []

        if not filters:
            return where_clauses, params

        exact_match_filters = (
            "operator",
            "priority",
            "category",
            "whom",
        )
        for field_name in exact_match_filters:
            if field_name in filters:
                where_clauses.append(f"{field_name} = ?")
                params.append(filters[field_name])

        if "date_from" in filters:
            where_clauses.append("event_time >= ?")
            params.append(EventLogRepository._normalize_filter_value(filters["date_from"]))

        if "date_to" in filters:
            where_clauses.append("event_time <= ?")
            params.append(EventLogRepository._normalize_filter_value(filters["date_to"]))

        return where_clauses, params

    @staticmethod
    def _build_personnel_filter_clauses(
        filters: EntryFilters | None,
    ) -> tuple[list[str], list[object]]:
        """Build reusable WHERE clauses and parameters for personnel filters."""
        where_clauses: list[str] = []
        params: list[object] = []

        if not filters:
            return where_clauses, params

        exact_match_filters = (
            "who",
            "operator",
            "status",
            "location",
            "active",
            "alarm_enabled",
            "alarm_triggered",
        )
        for field_name in exact_match_filters:
            if field_name in filters:
                where_clauses.append(f"{field_name} = ?")
                params.append(filters[field_name])

        if "date_from" in filters:
            where_clauses.append("logged_time >= ?")
            params.append(EventLogRepository._normalize_filter_value(filters["date_from"]))

        if "date_to" in filters:
            where_clauses.append("logged_time <= ?")
            params.append(EventLogRepository._normalize_filter_value(filters["date_to"]))

        return where_clauses, params

    @staticmethod
    def _normalize_filter_value(value: object) -> object:
        """Normalize filter values for SQLite parameter binding."""
        if isinstance(value, datetime):
            return value.isoformat()
        return value

    @staticmethod
    def _serialize_datetime(value: datetime | None) -> str | None:
        """Convert an optional datetime to ISO 8601 text for SQLite."""
        if value is None:
            return None
        return value.isoformat()

    @staticmethod
    def _serialize_system_capabilities(
        value: dict[str, object] | None,
    ) -> str | None:
        """Convert optional structured communication metadata to JSON text."""
        if value is None:
            return None
        return json.dumps(value)

    @staticmethod
    def _validate_personnel_alarm_fields(
        alarm_enabled: bool,
        expected_checkin_time: datetime | None,
    ) -> None:
        """Reject invalid personnel alarm states before SQLite constraint failures."""
        if alarm_enabled and expected_checkin_time is None:
            raise ValueError(
                "Personnel entries with alarm_enabled=True must provide expected_checkin_time."
            )

    def _bind_adapter_state(self) -> None:
        """Mirror adapter-managed SQLite state onto the legacy repository API."""
        self.database_path = self.adapter.database_path
        self.connection = self.adapter.connection
        self.cursor = self.adapter.cursor
        self._explicit_transaction_active = self.adapter._explicit_transaction_active


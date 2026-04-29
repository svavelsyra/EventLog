"""Abstract database adapter contract for EventLog repositories.

This interface defines the repository surface for the three primary Epic 001
Core entry models used by the SQLite repository and later CRUD stories.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TypeAlias

from src.core import CommunicationEntry, EventEntry, PersonnelEntry

EntryFilters: TypeAlias = dict[str, object]


class EventLogAdapter(ABC):
    """Abstract interface for EventLog database operations."""

    # ========== CommunicationEntry Operations ==========

    @abstractmethod
    def create_communication_entry(self, entry: CommunicationEntry) -> int:
        """Persist a new communication entry and return its database ID."""

    @abstractmethod
    def get_communication_entry(self, entry_id: int) -> CommunicationEntry | None:
        """Return one communication entry by ID, or ``None`` if it is missing."""

    @abstractmethod
    def get_all_communication_entries(
        self,
        filters: EntryFilters | None = None,
    ) -> list[CommunicationEntry]:
        """Return all communication entries matching the optional filters."""

    @abstractmethod
    def update_communication_entry(self, entry: CommunicationEntry) -> bool:
        """Update an existing communication entry and report success."""

    @abstractmethod
    def delete_communication_entry(self, entry_id: int) -> bool:
        """Delete a communication entry by ID and report success."""

    @abstractmethod
    def search_communication_entries(
        self,
        search_text: str,
        filters: EntryFilters | None = None,
    ) -> list[CommunicationEntry]:
        """Search communication entries using text plus optional filters."""

    # ========== EventEntry Operations ==========

    @abstractmethod
    def create_event_entry(self, entry: EventEntry) -> int:
        """Persist a new event entry and return its database ID."""

    @abstractmethod
    def get_event_entry(self, entry_id: int) -> EventEntry | None:
        """Return one event entry by ID, or ``None`` if it is missing."""

    @abstractmethod
    def get_all_event_entries(
        self,
        filters: EntryFilters | None = None,
    ) -> list[EventEntry]:
        """Return all event entries matching the optional filters."""

    @abstractmethod
    def update_event_entry(self, entry: EventEntry) -> bool:
        """Update an existing event entry and report success."""

    @abstractmethod
    def delete_event_entry(self, entry_id: int) -> bool:
        """Delete an event entry by ID and report success."""

    @abstractmethod
    def search_event_entries(
        self,
        search_text: str,
        filters: EntryFilters | None = None,
    ) -> list[EventEntry]:
        """Search event entries using text plus optional filters."""

    # ========== PersonnelEntry Operations ==========

    @abstractmethod
    def create_personnel_entry(self, entry: PersonnelEntry) -> int:
        """Persist a new personnel entry and return its database ID."""

    @abstractmethod
    def get_personnel_entry(self, entry_id: int) -> PersonnelEntry | None:
        """Return one personnel entry by ID, or ``None`` if it is missing."""

    @abstractmethod
    def get_all_personnel_entries(
        self,
        filters: EntryFilters | None = None,
    ) -> list[PersonnelEntry]:
        """Return all personnel entries matching the optional filters."""

    @abstractmethod
    def update_personnel_entry(self, entry: PersonnelEntry) -> bool:
        """Update an existing personnel entry and report success."""

    @abstractmethod
    def delete_personnel_entry(self, entry_id: int) -> bool:
        """Delete a personnel entry by ID and report success."""

    @abstractmethod
    def search_personnel_entries(
        self,
        search_text: str,
        filters: EntryFilters | None = None,
    ) -> list[PersonnelEntry]:
        """Search personnel entries using text plus optional filters."""

    @abstractmethod
    def get_active_personnel_entries(self) -> list[PersonnelEntry]:
        """Return all personnel entries marked as currently active."""

    @abstractmethod
    def get_personnel_history(self, who: str) -> list[PersonnelEntry]:
        """Return all personnel history rows for the given person or group."""

    @abstractmethod
    def get_overdue_alarms(self) -> list[PersonnelEntry]:
        """Return personnel entries with overdue, unacknowledged alarms."""

    # ========== Transaction Management ==========

    @abstractmethod
    def begin_transaction(self) -> None:
        """Start an explicit database transaction."""

    @abstractmethod
    def commit(self) -> None:
        """Commit the current database transaction."""

    @abstractmethod
    def rollback(self) -> None:
        """Rollback the current database transaction."""

    @abstractmethod
    def close(self) -> None:
        """Close the database connection and release resources."""


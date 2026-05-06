"""Abstract database adapter contract for EventLog repositories.

This interface defines the repository surface for the three primary Epic 001
Core entry models used by the SQLite repository and later CRUD stories.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TypeAlias

from src.core import (
    CommunicationEntry,
    CommunicationOptionMutationResult,
    CommunicationPortabilityBundle,
    EventEntry,
    PersonnelEntry,
)

EntryFilters: TypeAlias = dict[str, object]
QualifierDefaultValue: TypeAlias = bool | str | None


@dataclass(frozen=True, slots=True)
class CommunicationOptionConfig:
    """Caller-facing recursive communication option shape."""

    option_id: int
    option_value: str
    option_label: str
    child_label: str | None
    sort_order: int | None
    children: tuple[CommunicationOptionConfig, ...] = ()


@dataclass(frozen=True, slots=True)
class CommunicationQualifierConfig:
    """Caller-facing qualifier definition for one communication system."""

    qualifier_key: str
    label: str
    field_type: str
    valid_values: tuple[str, ...] | None
    default_value: QualifierDefaultValue
    help_text: str | None
    visibility_mode: str


@dataclass(frozen=True, slots=True)
class CommunicationSystemConfig:
    """Caller-facing assembled communication system configuration."""

    system_id: int
    system_name: str
    system_type: str
    child_label: str | None
    sort_order: int | None
    options: tuple[CommunicationOptionConfig, ...] = ()
    qualifiers: tuple[CommunicationQualifierConfig, ...] = ()


class EventLogAdapter(ABC):
    """Abstract interface for EventLog database operations."""

    # ========== Communication Configuration Reads ==========

    @abstractmethod
    def get_active_communication_system_configs(self) -> list[CommunicationSystemConfig]:
        """Return assembled active communication-system configuration for runtime use."""

    @abstractmethod
    def get_active_communication_system_config(
        self,
        system_name: str,
    ) -> CommunicationSystemConfig | None:
        """Return one active communication-system configuration by name."""

    @abstractmethod
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

    @abstractmethod
    def rename_communication_option(
        self,
        *,
        option_id: int,
        option_label: str,
    ) -> CommunicationOptionMutationResult:
        """Rename one communication option row without rewriting historical entries."""

    @abstractmethod
    def deactivate_communication_option(
        self,
        *,
        option_id: int,
    ) -> CommunicationOptionMutationResult:
        """Soft-deactivate one communication option subtree for future use only."""

    @abstractmethod
    def replace_communication_portability_bundle(
        self,
        bundle: CommunicationPortabilityBundle,
    ) -> None:
        """Replace active communication configuration exactly to match one bundle."""

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


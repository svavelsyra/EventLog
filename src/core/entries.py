"""Core entry models used by Epic 001 database stories.

These dataclasses represent the persistence-facing shape of the three primary
EventLog entry types. They intentionally stay lightweight for now: no database
logic, no GUI concerns, and no validation behavior bundled into the models.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class CommunicationEntry:
    """Domain model for communication log entries."""

    message_content: str
    operator: str
    id: int | None = None
    event_time: datetime | None = None
    logged_time: datetime | None = None
    from_field: str | None = None
    to_field: str | None = None
    confirmed: bool = False
    edited: bool = False
    communication_system: str | None = None
    method_type: str | None = None
    method_channel: str | None = None
    channel_designation: str | None = None
    system_capabilities: dict[str, object] | None = None


@dataclass(slots=True)
class EventEntry:
    """Domain model for operational event log entries."""

    event_description: str
    operator: str
    id: int | None = None
    whom: str | None = None
    event_time: datetime | None = None
    logged_time: datetime | None = None
    priority: str | None = "Normal"
    category: str | None = None
    edited: bool = False


@dataclass(slots=True)
class PersonnelEntry:
    """Domain model for personnel status and check-in tracking entries."""

    who: str
    operator: str
    id: int | None = None
    status: str | None = None
    location: str | None = None
    last_contact_time: datetime | None = None
    mission_notes: str | None = None
    logged_time: datetime | None = None
    edited: bool = False
    active: bool = True
    supersedes: str | None = None
    alarm_enabled: bool = False
    expected_checkin_time: datetime | None = None
    alarm_triggered: bool = False


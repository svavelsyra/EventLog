from dataclasses import is_dataclass
from datetime import datetime

import pytest

from src.core import CommunicationEntry, EventEntry, PersonnelEntry


pytestmark = pytest.mark.unit


def test_core_entry_models_are_importable_from_package_root() -> None:
    assert is_dataclass(CommunicationEntry)
    assert is_dataclass(EventEntry)
    assert is_dataclass(PersonnelEntry)


def test_communication_entry_supports_minimum_construction_and_defaults() -> None:
    entry = CommunicationEntry(
        message_content="Radio check complete.",
        operator="Operator One",
    )

    assert entry.id is None
    assert entry.message_content == "Radio check complete."
    assert entry.operator == "Operator One"
    assert entry.event_time is None
    assert entry.logged_time is None
    assert entry.from_field is None
    assert entry.to_field is None
    assert entry.confirmed is False
    assert entry.edited is False
    assert entry.communication_system is None
    assert entry.method_type is None
    assert entry.method_channel is None
    assert entry.channel_designation is None
    assert entry.system_capabilities is None


def test_event_entry_supports_minimum_construction_and_defaults() -> None:
    entry = EventEntry(
        event_description="Suspicious movement observed.",
        operator="Operator Two",
    )

    assert entry.id is None
    assert entry.event_description == "Suspicious movement observed."
    assert entry.operator == "Operator Two"
    assert entry.whom is None
    assert entry.event_time is None
    assert entry.logged_time is None
    assert entry.priority == "Normal"
    assert entry.category is None
    assert entry.edited is False


def test_personnel_entry_supports_minimum_construction_and_defaults() -> None:
    entry = PersonnelEntry(
        who="Alpha 1",
        operator="Operator Three",
    )

    assert entry.id is None
    assert entry.who == "Alpha 1"
    assert entry.operator == "Operator Three"
    assert entry.status is None
    assert entry.location is None
    assert entry.last_contact_time is None
    assert entry.mission_notes is None
    assert entry.logged_time is None
    assert entry.edited is False
    assert entry.active is True
    assert entry.supersedes is None
    assert entry.alarm_enabled is False
    assert entry.expected_checkin_time is None
    assert entry.alarm_triggered is False


def test_entry_models_support_saved_instances_with_datetime_fields() -> None:
    timestamp = datetime(2026, 4, 27, 12, 30, 0)

    communication_entry = CommunicationEntry(
        id=1,
        message_content="Message received.",
        operator="Operator One",
        event_time=timestamp,
        logged_time=timestamp,
        confirmed=True,
        system_capabilities={"encryption": True},
    )
    event_entry = EventEntry(
        id=2,
        event_description="Event logged.",
        operator="Operator Two",
        event_time=timestamp,
        logged_time=timestamp,
        priority="High",
    )
    personnel_entry = PersonnelEntry(
        id=3,
        who="Bravo 2",
        operator="Operator Three",
        logged_time=timestamp,
        last_contact_time=timestamp,
        alarm_enabled=True,
        expected_checkin_time=timestamp,
    )

    assert communication_entry.id == 1
    assert communication_entry.confirmed is True
    assert communication_entry.system_capabilities == {"encryption": True}

    assert event_entry.id == 2
    assert event_entry.priority == "High"
    assert event_entry.logged_time == timestamp

    assert personnel_entry.id == 3
    assert personnel_entry.last_contact_time == timestamp
    assert personnel_entry.alarm_enabled is True
    assert personnel_entry.expected_checkin_time == timestamp


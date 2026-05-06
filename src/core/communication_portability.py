"""Versioned communication portability contract for approved non-secret config.

This module defines which communication configuration domains are portable,
which neighboring data classes are excluded, what bundle shape later
export/import stories must honor, the pure export builder that maps
core-owned runtime communication configuration into that approved bundle shape,
and the core-side import orchestration that validates/parses approved payloads
before delegating database apply work to a repository-owned seam.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol, cast

from src.core.communication_config import (
    CommunicationConfigLoader,
    CommunicationOptionDefinition,
    CommunicationQualifierDefinition,
    CommunicationSystemDefinition,
    SystemConfig,
)

COMMUNICATION_PORTABILITY_BUNDLE_KIND = "eventlog.communication_config"
COMMUNICATION_PORTABILITY_BUNDLE_VERSION = 1
PORTABLE_COMMUNICATION_DOMAINS = (
    "communication_systems",
    "communication_options",
    "communication_qualifiers",
)
EXCLUDED_COMMUNICATION_PORTABILITY_DOMAINS = (
    "bootstrap_security_material",
    "secrets",
    "user_preferences",
    "event_metadata",
    "structured_report_templates",
    "logs",
    "entry_records",
    "communication_entries",
    "event_entries",
    "personnel_entries",
)

_BUNDLE_KEYS = frozenset(
    {
        "bundle_kind",
        "bundle_version",
        "portable_domains",
        "communication_systems",
    }
)
_SYSTEM_KEYS = frozenset(
    {
        "system_name",
        "system_type",
        "child_label",
        "sort_order",
        "options",
        "qualifiers",
    }
)
_OPTION_KEYS = frozenset(
    {
        "option_value",
        "option_label",
        "child_label",
        "sort_order",
        "children",
    }
)
_QUALIFIER_KEYS = frozenset(
    {
        "qualifier_key",
        "label",
        "field_type",
        "valid_values",
        "default_value",
        "help_text",
        "visibility_mode",
    }
)
_ALLOWED_QUALIFIER_FIELD_TYPES = frozenset({"enum", "boolean", "text"})
_ALLOWED_QUALIFIER_VISIBILITY_MODES = frozenset({"editable", "forced", "hidden"})


class CommunicationPortabilityContractError(ValueError):
    """Raised when a portability bundle falls outside the approved contract."""


class CommunicationPortabilityImportTarget(Protocol):
    """Repository-facing apply seam for approved communication bundles."""

    def replace_communication_portability_bundle(
        self,
        bundle: "CommunicationPortabilityBundle",
    ) -> None:
        """Apply one validated portability bundle to the database-owned config."""


@dataclass(frozen=True, slots=True)
class PortableCommunicationQualifier:
    """Allowlisted qualifier contract for one communication system."""

    qualifier_key: str
    label: str
    field_type: str
    valid_values: tuple[str, ...] | None
    default_value: bool | str | None
    help_text: str | None
    visibility_mode: str

    def to_payload(self) -> dict[str, object]:
        """Return the stable qualifier payload shape for portability bundles."""
        return {
            "qualifier_key": self.qualifier_key,
            "label": self.label,
            "field_type": self.field_type,
            "valid_values": list(self.valid_values) if self.valid_values is not None else None,
            "default_value": self.default_value,
            "help_text": self.help_text,
            "visibility_mode": self.visibility_mode,
        }


@dataclass(frozen=True, slots=True)
class PortableCommunicationOption:
    """Allowlisted recursive option-tree contract for one communication system."""

    option_value: str
    option_label: str
    child_label: str | None
    sort_order: int | None
    children: tuple["PortableCommunicationOption", ...] = ()

    def to_payload(self) -> dict[str, object]:
        """Return the stable recursive option payload for portability bundles."""
        return {
            "option_value": self.option_value,
            "option_label": self.option_label,
            "child_label": self.child_label,
            "sort_order": self.sort_order,
            "children": [child.to_payload() for child in self.children],
        }


@dataclass(frozen=True, slots=True)
class PortableCommunicationSystem:
    """Allowlisted communication-system contract for portability bundles."""

    system_name: str
    system_type: str
    child_label: str | None
    sort_order: int | None
    options: tuple[PortableCommunicationOption, ...] = ()
    qualifiers: tuple[PortableCommunicationQualifier, ...] = ()

    def to_payload(self) -> dict[str, object]:
        """Return the stable system payload for portability bundles."""
        return {
            "system_name": self.system_name,
            "system_type": self.system_type,
            "child_label": self.child_label,
            "sort_order": self.sort_order,
            "options": [option.to_payload() for option in self.options],
            "qualifiers": [qualifier.to_payload() for qualifier in self.qualifiers],
        }


@dataclass(frozen=True, slots=True)
class CommunicationPortabilityBundle:
    """Versioned bundle contract for approved communication configuration only."""

    communication_systems: tuple[PortableCommunicationSystem, ...] = ()
    bundle_kind: str = COMMUNICATION_PORTABILITY_BUNDLE_KIND
    bundle_version: int = COMMUNICATION_PORTABILITY_BUNDLE_VERSION
    portable_domains: tuple[str, ...] = PORTABLE_COMMUNICATION_DOMAINS

    def to_payload(self) -> dict[str, object]:
        """Return the stable top-level payload shape for later export stories."""
        return {
            "bundle_kind": self.bundle_kind,
            "bundle_version": self.bundle_version,
            "portable_domains": list(self.portable_domains),
            "communication_systems": [
                system.to_payload()
                for system in self.communication_systems
            ],
        }


@dataclass(frozen=True, slots=True)
class CommunicationPortabilityImportResult:
    """Result of validating and applying one portability payload."""

    bundle: CommunicationPortabilityBundle
    config: SystemConfig


def build_communication_portability_bundle(
    config: SystemConfig,
) -> CommunicationPortabilityBundle:
    """Build an approved portability bundle from runtime communication config."""
    return CommunicationPortabilityBundle(
        communication_systems=tuple(
            _build_portable_system_definition(system)
            for system in config.systems
        )
    )


def export_communication_portability_payload(
    config: SystemConfig,
) -> dict[str, object]:
    """Return the approved portability payload for runtime communication config."""
    return build_communication_portability_bundle(config).to_payload()


def parse_communication_portability_payload(
    payload: Mapping[str, object],
) -> CommunicationPortabilityBundle:
    """Validate and parse one portability payload into the frozen bundle model."""
    validate_communication_portability_payload(payload)

    return CommunicationPortabilityBundle(
        bundle_kind=cast(str, payload["bundle_kind"]),
        bundle_version=cast(int, payload["bundle_version"]),
        portable_domains=_coerce_string_sequence(
            payload["portable_domains"],
            field_name="portable_domains",
        ),
        communication_systems=tuple(
            _parse_system_payload(system_payload)
            for system_payload in _coerce_object_sequence(
                payload["communication_systems"],
                field_name="communication_systems",
            )
        ),
    )


def import_communication_portability_payload(
    payload: Mapping[str, object],
    *,
    import_target: CommunicationPortabilityImportTarget,
    config_loader: CommunicationConfigLoader,
) -> CommunicationPortabilityImportResult:
    """Validate, apply, and reload approved communication portability payloads."""
    bundle = parse_communication_portability_payload(payload)
    import_target.replace_communication_portability_bundle(bundle)
    return CommunicationPortabilityImportResult(
        bundle=bundle,
        config=config_loader.reload_config(),
    )


def _build_portable_system_definition(
    system: CommunicationSystemDefinition,
) -> PortableCommunicationSystem:
    return PortableCommunicationSystem(
        system_name=system.system_name,
        system_type=system.system_type,
        child_label=system.child_label,
        sort_order=system.sort_order,
        options=tuple(
            _build_portable_option_definition(option)
            for option in system.options
        ),
        qualifiers=tuple(
            _build_portable_qualifier_definition(qualifier)
            for qualifier in system.qualifiers
        ),
    )


def _build_portable_option_definition(
    option: CommunicationOptionDefinition,
) -> PortableCommunicationOption:
    return PortableCommunicationOption(
        option_value=option.option_value,
        option_label=option.option_label,
        child_label=option.child_label,
        sort_order=option.sort_order,
        children=tuple(
            _build_portable_option_definition(child)
            for child in option.children
        ),
    )


def _build_portable_qualifier_definition(
    qualifier: CommunicationQualifierDefinition,
) -> PortableCommunicationQualifier:
    return PortableCommunicationQualifier(
        qualifier_key=qualifier.qualifier_key,
        label=qualifier.label,
        field_type=qualifier.field_type,
        valid_values=qualifier.valid_values,
        default_value=qualifier.default_value,
        help_text=qualifier.help_text,
        visibility_mode=qualifier.visibility_mode,
    )


def _parse_system_payload(payload: object) -> PortableCommunicationSystem:
    system_payload = _require_mapping(payload, field_name="communication_systems[]")
    return PortableCommunicationSystem(
        system_name=cast(str, system_payload["system_name"]),
        system_type=cast(str, system_payload["system_type"]),
        child_label=cast(str | None, system_payload["child_label"]),
        sort_order=cast(int | None, system_payload["sort_order"]),
        options=tuple(
            _parse_option_payload(option_payload)
            for option_payload in _coerce_object_sequence(
                system_payload["options"],
                field_name="options",
            )
        ),
        qualifiers=tuple(
            _parse_qualifier_payload(qualifier_payload)
            for qualifier_payload in _coerce_object_sequence(
                system_payload["qualifiers"],
                field_name="qualifiers",
            )
        ),
    )


def _parse_option_payload(payload: object) -> PortableCommunicationOption:
    option_payload = _require_mapping(payload, field_name="options[]")
    return PortableCommunicationOption(
        option_value=cast(str, option_payload["option_value"]),
        option_label=cast(str, option_payload["option_label"]),
        child_label=cast(str | None, option_payload["child_label"]),
        sort_order=cast(int | None, option_payload["sort_order"]),
        children=tuple(
            _parse_option_payload(child_payload)
            for child_payload in _coerce_object_sequence(
                option_payload["children"],
                field_name="children",
            )
        ),
    )


def _parse_qualifier_payload(payload: object) -> PortableCommunicationQualifier:
    qualifier_payload = _require_mapping(payload, field_name="qualifiers[]")
    return PortableCommunicationQualifier(
        qualifier_key=cast(str, qualifier_payload["qualifier_key"]),
        label=cast(str, qualifier_payload["label"]),
        field_type=cast(str, qualifier_payload["field_type"]),
        valid_values=(
            _coerce_string_sequence(
                qualifier_payload["valid_values"],
                field_name="valid_values",
            )
            if qualifier_payload["valid_values"] is not None
            else None
        ),
        default_value=cast(bool | str | None, qualifier_payload["default_value"]),
        help_text=cast(str | None, qualifier_payload["help_text"]),
        visibility_mode=cast(str, qualifier_payload["visibility_mode"]),
    )


def validate_communication_portability_payload(payload: Mapping[str, object]) -> None:
    """Reject payloads that fall outside the approved communication contract."""
    bundle_payload = _require_mapping(payload, field_name="bundle")
    _validate_mapping_keys("bundle", bundle_payload, _BUNDLE_KEYS)

    bundle_kind = bundle_payload.get("bundle_kind")
    if bundle_kind != COMMUNICATION_PORTABILITY_BUNDLE_KIND:
        raise CommunicationPortabilityContractError(
            "Unsupported communication portability bundle_kind."
        )

    bundle_version = bundle_payload.get("bundle_version")
    if not isinstance(bundle_version, int) or isinstance(bundle_version, bool):
        raise CommunicationPortabilityContractError(
            "Unsupported or missing communication portability bundle_version."
        )
    if bundle_version != COMMUNICATION_PORTABILITY_BUNDLE_VERSION:
        raise CommunicationPortabilityContractError(
            "Unsupported or missing communication portability bundle_version."
        )

    portable_domains = bundle_payload.get("portable_domains")
    if _coerce_string_sequence(portable_domains, field_name="portable_domains") != PORTABLE_COMMUNICATION_DOMAINS:
        raise CommunicationPortabilityContractError(
            "portable_domains must exactly match the approved communication allowlist."
        )

    communication_systems = _coerce_object_sequence(
        bundle_payload.get("communication_systems"),
        field_name="communication_systems",
    )
    system_names = tuple(
        _validate_system_payload(system_payload)
        for system_payload in communication_systems
    )
    _validate_unique_values(system_names, field_name="communication_systems system_name")


def _validate_system_payload(payload: object) -> str:
    system_payload = _require_mapping(payload, field_name="communication_systems[]")
    _validate_mapping_keys("communication_system", system_payload, _SYSTEM_KEYS)

    _require_string(system_payload.get("system_name"), field_name="system_name")
    _require_string(system_payload.get("system_type"), field_name="system_type")
    _require_nullable_string(system_payload.get("child_label"), field_name="child_label")
    _require_nullable_int(system_payload.get("sort_order"), field_name="sort_order")

    option_payloads = _coerce_object_sequence(system_payload.get("options"), field_name="options")
    option_values = tuple(
        _validate_option_payload(option_payload)
        for option_payload in option_payloads
    )
    _validate_unique_values(option_values, field_name="options option_value")

    qualifier_payloads = _coerce_object_sequence(
        system_payload.get("qualifiers"),
        field_name="qualifiers",
    )
    qualifier_keys = tuple(
        _validate_qualifier_payload(qualifier_payload)
        for qualifier_payload in qualifier_payloads
    )
    _validate_unique_values(qualifier_keys, field_name="qualifiers qualifier_key")
    return cast(str, system_payload["system_name"])


def _validate_option_payload(payload: object) -> str:
    option_payload = _require_mapping(payload, field_name="options[]")
    _validate_mapping_keys("communication_option", option_payload, _OPTION_KEYS)

    _require_string(option_payload.get("option_value"), field_name="option_value")
    _require_string(option_payload.get("option_label"), field_name="option_label")
    _require_nullable_string(option_payload.get("child_label"), field_name="child_label")
    _require_nullable_int(option_payload.get("sort_order"), field_name="sort_order")

    child_payloads = _coerce_object_sequence(option_payload.get("children"), field_name="children")
    child_option_values = tuple(
        _validate_option_payload(child_payload)
        for child_payload in child_payloads
    )
    _validate_unique_values(child_option_values, field_name="children option_value")
    return cast(str, option_payload["option_value"])


def _validate_qualifier_payload(payload: object) -> str:
    qualifier_payload = _require_mapping(payload, field_name="qualifiers[]")
    _validate_mapping_keys("communication_qualifier", qualifier_payload, _QUALIFIER_KEYS)

    _require_string(qualifier_payload.get("qualifier_key"), field_name="qualifier_key")
    _require_string(qualifier_payload.get("label"), field_name="label")
    _require_string(qualifier_payload.get("field_type"), field_name="field_type")
    _require_nullable_string(qualifier_payload.get("help_text"), field_name="help_text")
    _require_string(qualifier_payload.get("visibility_mode"), field_name="visibility_mode")

    field_type = cast(str, qualifier_payload["field_type"])
    if field_type not in _ALLOWED_QUALIFIER_FIELD_TYPES:
        raise CommunicationPortabilityContractError(
            "field_type must be one of the approved qualifier field types."
        )

    visibility_mode = cast(str, qualifier_payload["visibility_mode"])
    if visibility_mode not in _ALLOWED_QUALIFIER_VISIBILITY_MODES:
        raise CommunicationPortabilityContractError(
            "visibility_mode must be one of the approved qualifier visibility modes."
        )

    valid_values = qualifier_payload.get("valid_values")
    default_value = qualifier_payload.get("default_value")
    if field_type == "enum":
        enum_values = _coerce_string_sequence(valid_values, field_name="valid_values")
        _require_non_empty_string_sequence(enum_values, field_name="valid_values")
        if isinstance(default_value, bool) or not isinstance(default_value, (str, type(None))):
            raise CommunicationPortabilityContractError(
                "default_value must be str or None for enum qualifiers."
            )
        if default_value is not None and default_value not in enum_values:
            raise CommunicationPortabilityContractError(
                "default_value must be one of valid_values for enum qualifiers."
            )
    elif field_type == "boolean":
        if valid_values is not None:
            raise CommunicationPortabilityContractError(
                "valid_values must be None for boolean qualifiers."
            )
        if default_value is not None and not isinstance(default_value, bool):
            raise CommunicationPortabilityContractError(
                "default_value must be bool or None for boolean qualifiers."
            )
    else:
        if valid_values is not None:
            raise CommunicationPortabilityContractError(
                "valid_values must be None for text qualifiers."
            )
        if isinstance(default_value, bool) or not isinstance(default_value, (str, type(None))):
            raise CommunicationPortabilityContractError(
                "default_value must be str or None for text qualifiers."
            )

    return cast(str, qualifier_payload["qualifier_key"])


def _validate_mapping_keys(
    mapping_name: str,
    payload: Mapping[str, object],
    allowed_keys: frozenset[str],
) -> None:
    payload_keys = set(payload.keys())
    missing_keys = allowed_keys - payload_keys
    unexpected_keys = payload_keys - allowed_keys
    if missing_keys or unexpected_keys:
        details: list[str] = []
        if missing_keys:
            details.append(f"missing={sorted(missing_keys)!r}")
        if unexpected_keys:
            details.append(f"unexpected={sorted(unexpected_keys)!r}")
        raise CommunicationPortabilityContractError(
            f"{mapping_name} keys must match the approved contract exactly ({', '.join(details)})."
        )


def _require_mapping(payload: object, field_name: str) -> Mapping[str, object]:
    if not isinstance(payload, Mapping):
        raise CommunicationPortabilityContractError(f"{field_name} must be a mapping.")
    return payload


def _coerce_object_sequence(payload: object, field_name: str) -> tuple[object, ...]:
    if isinstance(payload, (str, bytes, bytearray)) or not isinstance(payload, Sequence):
        raise CommunicationPortabilityContractError(f"{field_name} must be a sequence.")
    return tuple(payload)


def _coerce_string_sequence(payload: object, field_name: str) -> tuple[str, ...]:
    items = _coerce_object_sequence(payload, field_name=field_name)
    if not all(isinstance(item, str) for item in items):
        raise CommunicationPortabilityContractError(f"{field_name} must contain only strings.")
    return tuple(item for item in items if isinstance(item, str))


def _validate_unique_values(values: Sequence[str], field_name: str) -> None:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)

    if duplicates:
        raise CommunicationPortabilityContractError(
            f"{field_name} must be unique within the approved portability contract: {sorted(duplicates)!r}."
        )


def _require_non_empty_string_sequence(values: Sequence[str], field_name: str) -> None:
    if any(not value for value in values):
        raise CommunicationPortabilityContractError(
            f"{field_name} must contain only non-empty strings."
        )


def _require_string(value: object, field_name: str) -> None:
    if not isinstance(value, str) or not value:
        raise CommunicationPortabilityContractError(f"{field_name} must be a non-empty string.")


def _require_nullable_string(value: object, field_name: str) -> None:
    if value is not None and not isinstance(value, str):
        raise CommunicationPortabilityContractError(f"{field_name} must be a string or None.")


def _require_nullable_int(value: object, field_name: str) -> None:
    if value is not None and (not isinstance(value, int) or isinstance(value, bool)):
        raise CommunicationPortabilityContractError(f"{field_name} must be an int or None.")


__all__ = [
    "build_communication_portability_bundle",
    "COMMUNICATION_PORTABILITY_BUNDLE_KIND",
    "COMMUNICATION_PORTABILITY_BUNDLE_VERSION",
    "PORTABLE_COMMUNICATION_DOMAINS",
    "EXCLUDED_COMMUNICATION_PORTABILITY_DOMAINS",
    "CommunicationPortabilityBundle",
    "CommunicationPortabilityContractError",
    "CommunicationPortabilityImportResult",
    "CommunicationPortabilityImportTarget",
    "export_communication_portability_payload",
    "import_communication_portability_payload",
    "parse_communication_portability_payload",
    "PortableCommunicationOption",
    "PortableCommunicationQualifier",
    "PortableCommunicationSystem",
    "validate_communication_portability_payload",
]




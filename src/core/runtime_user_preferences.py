"""Core-owned runtime user-preference definitions and storage rules.

This module centralizes the approved runtime `user_preferences` keys, their
stored-value kinds, and the parsing/serialization helpers used by the
repository-owned persistence seam. Bootstrap `config.ini` ownership stays in the
bootstrap/config layer; this module covers only database-backed runtime
preferences loaded after the repository is ready.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import json
from typing import Literal, Protocol, TypeAlias

PreferenceValueKind: TypeAlias = Literal["text", "json"]
JsonScalar: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]
RuntimePreferenceValue: TypeAlias = str | JsonValue

TAB_UI_RUNTIME_PREFERENCE_NAMES = (
    "communication",
    "event",
    "personnel",
)
TAB_UI_RUNTIME_PREFERENCE_CATEGORIES = (
    "columns",
    "filters",
    "display",
)


class UnknownRuntimePreferenceKeyError(KeyError):
    """Raised when callers request a runtime preference key not in the registry."""


@dataclass(frozen=True, slots=True)
class RuntimePreferenceDefinition:
    """Definition for one approved runtime preference key."""

    key: str
    value_kind: PreferenceValueKind
    default_value: RuntimePreferenceValue
    description: str

    def clone_default_value(self) -> RuntimePreferenceValue:
        """Return a defensive copy of the approved default value."""
        return deepcopy(self.default_value)


class RuntimeUserPreferenceStore(Protocol):
    """Minimal runtime-preference read/write seam for later consumers."""

    def read_runtime_preference(self, key: str) -> RuntimePreferenceValue:
        """Return a parsed runtime preference value or its approved default."""

    def write_runtime_preference(self, key: str, value: RuntimePreferenceValue) -> None:
        """Persist one runtime preference value through the shared storage seam."""

    def clear_runtime_preference(self, key: str) -> None:
        """Remove one stored runtime preference so reads fall back to the default."""


_TAB_UI_CATEGORY_DEFAULTS = {
    "columns": {
        "visible": [],
        "order": [],
        "widths": {},
    },
    "filters": {
        "values": {},
    },
    "display": {
        "sort": {
            "column": "",
            "direction": "desc",
        },
        "toggles": {},
    },
}

_TAB_UI_CATEGORY_DESCRIPTIONS = {
    "columns": "column visibility, order, and width preferences",
    "filters": "filter-default values and lightweight filter state",
    "display": "display-state preferences such as sort state and simple view toggles",
}


def get_tab_ui_runtime_preference_key(
    tab_name: str,
    category: str,
) -> str:
    """Return the shared runtime-preference key for one tab UI-state category."""
    if tab_name not in TAB_UI_RUNTIME_PREFERENCE_NAMES:
        raise ValueError(
            f"Unknown tab UI runtime preference name {tab_name!r}. "
            f"Expected one of {TAB_UI_RUNTIME_PREFERENCE_NAMES!r}."
        )
    if category not in TAB_UI_RUNTIME_PREFERENCE_CATEGORIES:
        raise ValueError(
            f"Unknown tab UI runtime preference category {category!r}. "
            f"Expected one of {TAB_UI_RUNTIME_PREFERENCE_CATEGORIES!r}."
        )
    return f"ui.tab.{tab_name}.{category}"


def _build_tab_ui_runtime_preference_definition(
    tab_name: str,
    category: str,
) -> RuntimePreferenceDefinition:
    """Return the approved runtime-preference definition for one tab/category pair."""
    return RuntimePreferenceDefinition(
        key=get_tab_ui_runtime_preference_key(tab_name, category),
        value_kind="json",
        default_value=deepcopy(_TAB_UI_CATEGORY_DEFAULTS[category]),
        description=f"{tab_name.capitalize()}-tab {_TAB_UI_CATEGORY_DESCRIPTIONS[category]}.",
    )

RUNTIME_PREFERENCE_DEFINITIONS = {
    definition.key: definition
    for definition in (
        _build_tab_ui_runtime_preference_definition(tab_name, category)
        for tab_name in TAB_UI_RUNTIME_PREFERENCE_NAMES
        for category in TAB_UI_RUNTIME_PREFERENCE_CATEGORIES
    )
}

COMMUNICATION_TAB_COLUMNS_RUNTIME_PREFERENCE = RUNTIME_PREFERENCE_DEFINITIONS[
    get_tab_ui_runtime_preference_key("communication", "columns")
]


def get_runtime_preference_definition(key: str) -> RuntimePreferenceDefinition:
    """Return the approved definition for one runtime preference key."""
    try:
        return RUNTIME_PREFERENCE_DEFINITIONS[key]
    except KeyError as exc:
        raise UnknownRuntimePreferenceKeyError(key) from exc


def get_tab_ui_runtime_preference_definition(
    tab_name: str,
    category: str,
) -> RuntimePreferenceDefinition:
    """Return the approved per-tab UI-state definition for one tab/category pair."""
    return get_runtime_preference_definition(
        get_tab_ui_runtime_preference_key(tab_name, category),
    )


def serialize_runtime_preference_value(
    definition: RuntimePreferenceDefinition,
    value: RuntimePreferenceValue,
) -> str:
    """Serialize one runtime preference value according to its approved definition."""
    if definition.value_kind == "text":
        if not isinstance(value, str):
            raise TypeError(f"Runtime preference {definition.key!r} must be stored as text.")
        return value

    _validate_runtime_preference_value(definition, value)
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    except TypeError as exc:
        raise TypeError(f"Runtime preference {definition.key!r} must be JSON-serializable.") from exc


def parse_runtime_preference_value(
    definition: RuntimePreferenceDefinition,
    stored_value: str,
) -> RuntimePreferenceValue:
    """Parse one stored runtime preference value according to its definition."""
    if definition.value_kind == "text":
        return stored_value

    try:
        parsed_value = json.loads(stored_value)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Runtime preference {definition.key!r} contains invalid JSON.") from exc

    _validate_runtime_preference_value(definition, parsed_value)
    return parsed_value


def _validate_runtime_preference_value(
    definition: RuntimePreferenceDefinition,
    value: RuntimePreferenceValue,
) -> None:
    """Validate known runtime preference shapes that later consumers rely on."""
    if not definition.key.startswith("ui.tab."):
        return

    parts = definition.key.split(".")
    if len(parts) != 4:
        return

    category = parts[3]
    if category == "columns":
        _validate_tab_columns_preference(definition.key, value)
        return
    if category == "filters":
        _validate_tab_filters_preference(definition.key, value)
        return
    if category == "display":
        _validate_tab_display_preference(definition.key, value)


def _require_mapping(key: str, value: RuntimePreferenceValue, *, field_name: str) -> dict[str, object]:
    """Return a dict value for structured preferences or raise a stable contract error."""
    if not isinstance(value, dict):
        raise ValueError(f"Runtime preference {key!r} must store {field_name} as a JSON object.")
    return value


def _validate_tab_columns_preference(key: str, value: RuntimePreferenceValue) -> None:
    """Require the shared columns contract used by later tab consumers."""
    mapping = _require_mapping(key, value, field_name="column state")
    visible = mapping.get("visible")
    order = mapping.get("order")
    widths = mapping.get("widths")

    if not isinstance(visible, list) or any(not isinstance(item, str) for item in visible):
        raise ValueError(f"Runtime preference {key!r} must store 'visible' as a list of strings.")
    if not isinstance(order, list) or any(not isinstance(item, str) for item in order):
        raise ValueError(f"Runtime preference {key!r} must store 'order' as a list of strings.")
    if not isinstance(widths, dict):
        raise ValueError(f"Runtime preference {key!r} must store 'widths' as an object.")

    for column_name, column_width in widths.items():
        if not isinstance(column_name, str):
            raise ValueError(f"Runtime preference {key!r} must use string keys in 'widths'.")
        if not isinstance(column_width, int) or column_width <= 0:
            raise ValueError(
                f"Runtime preference {key!r} must store positive integer widths in 'widths'."
            )


def _validate_tab_filters_preference(key: str, value: RuntimePreferenceValue) -> None:
    """Require the shared filter-state container used by later tab consumers."""
    mapping = _require_mapping(key, value, field_name="filter state")
    values = mapping.get("values")
    if not isinstance(values, dict):
        raise ValueError(f"Runtime preference {key!r} must store 'values' as an object.")
    if any(not isinstance(filter_name, str) for filter_name in values):
        raise ValueError(f"Runtime preference {key!r} must use string keys in 'values'.")


def _validate_tab_display_preference(key: str, value: RuntimePreferenceValue) -> None:
    """Require the shared display-state container used by later tab consumers."""
    mapping = _require_mapping(key, value, field_name="display state")
    sort = mapping.get("sort")
    toggles = mapping.get("toggles")

    if not isinstance(sort, dict):
        raise ValueError(f"Runtime preference {key!r} must store 'sort' as an object.")
    if not isinstance(sort.get("column"), str):
        raise ValueError(f"Runtime preference {key!r} must store 'sort.column' as a string.")
    if sort.get("direction") not in {"asc", "desc"}:
        raise ValueError(
            f"Runtime preference {key!r} must store 'sort.direction' as 'asc' or 'desc'."
        )
    if not isinstance(toggles, dict):
        raise ValueError(f"Runtime preference {key!r} must store 'toggles' as an object.")

    for toggle_name, toggle_enabled in toggles.items():
        if not isinstance(toggle_name, str):
            raise ValueError(f"Runtime preference {key!r} must use string keys in 'toggles'.")
        if not isinstance(toggle_enabled, bool):
            raise ValueError(f"Runtime preference {key!r} must store boolean values in 'toggles'.")



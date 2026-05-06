"""Core-owned runtime communication configuration models and loader support.

This module keeps higher layers insulated from repository/storage details by
mapping repository-facing communication configuration reads into immutable,
core-owned runtime objects. The loader uses instance-local memoization only;
callers must explicitly request a refresh when they need a fresh view after
configuration updates.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal, Protocol, Sequence, TypeAlias

QualifierValue: TypeAlias = bool | str | None
CommunicationOptionMutationStatus: TypeAlias = Literal[
    "created",
    "reactivated",
    "already_exists",
    "updated",
    "unchanged",
    "deactivated",
    "already_inactive",
    "not_found",
]


class CommunicationQualifierConfigLike(Protocol):
    """Repository-facing qualifier shape required by the core loader."""

    qualifier_key: str
    label: str
    field_type: str
    valid_values: tuple[str, ...] | None
    default_value: QualifierValue
    help_text: str | None
    visibility_mode: str


class CommunicationOptionConfigLike(Protocol):
    """Repository-facing recursive option shape required by the core loader."""

    option_id: int
    option_value: str
    option_label: str
    child_label: str | None
    sort_order: int | None
    children: tuple["CommunicationOptionConfigLike", ...]


class CommunicationSystemConfigLike(Protocol):
    """Repository-facing system configuration shape required by the core loader."""

    system_id: int
    system_name: str
    system_type: str
    child_label: str | None
    sort_order: int | None
    options: tuple[CommunicationOptionConfigLike, ...]
    qualifiers: tuple[CommunicationQualifierConfigLike, ...]


class CommunicationConfigSource(Protocol):
    """Minimal repository-facing read contract used by the loader."""

    def get_active_communication_system_configs(self) -> Sequence[CommunicationSystemConfigLike]:
        """Return active communication-system configuration for runtime use."""


@dataclass(frozen=True, slots=True)
class CommunicationOptionMutationResult:
    """Caller-visible outcome for one targeted communication-option mutation."""

    status: CommunicationOptionMutationStatus
    option_id: int | None = None
    changed: bool = False
    config: "SystemConfig | None" = None

    @property
    def requires_reload(self) -> bool:
        """Return whether callers should refresh runtime config after this mutation."""
        return self.changed


class CommunicationConfigMutator(Protocol):
    """Minimal repository-facing mutation contract used by the core manager."""

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

    def rename_communication_option(
        self,
        *,
        option_id: int,
        option_label: str,
    ) -> CommunicationOptionMutationResult:
        """Update the operator-facing label for one communication option."""

    def deactivate_communication_option(
        self,
        *,
        option_id: int,
    ) -> CommunicationOptionMutationResult:
        """Soft-deactivate one communication option and its descendants."""


@dataclass(frozen=True, slots=True)
class CommunicationQualifierDefinition:
    """Immutable runtime qualifier definition for one communication system."""

    qualifier_key: str
    label: str
    field_type: str
    valid_values: tuple[str, ...] | None
    default_value: QualifierValue
    help_text: str | None
    visibility_mode: str


@dataclass(frozen=True, slots=True)
class CommunicationOptionDefinition:
    """Immutable runtime communication path option with recursive children."""

    option_id: int
    option_value: str
    option_label: str
    child_label: str | None
    sort_order: int | None
    children: tuple["CommunicationOptionDefinition", ...] = ()

    def get_child(self, option_value: str) -> CommunicationOptionDefinition | None:
        """Return a direct child option by stored value, if present."""
        for child in self.children:
            if child.option_value == option_value:
                return child
        return None

    def find_option_by_id(self, option_id: int) -> CommunicationOptionDefinition | None:
        """Return this option or one descendant that matches the stored ID."""
        if self.option_id == option_id:
            return self

        for child in self.children:
            matching_option = child.find_option_by_id(option_id)
            if matching_option is not None:
                return matching_option
        return None


@dataclass(frozen=True, slots=True)
class CommunicationSystemDefinition:
    """Immutable runtime communication system definition."""

    system_id: int
    system_name: str
    system_type: str
    child_label: str | None
    sort_order: int | None
    options: tuple[CommunicationOptionDefinition, ...] = ()
    qualifiers: tuple[CommunicationQualifierDefinition, ...] = ()

    def get_option(self, option_value: str) -> CommunicationOptionDefinition | None:
        """Return a direct top-level option by stored value, if present."""
        for option in self.options:
            if option.option_value == option_value:
                return option
        return None

    def find_option_by_path(
        self,
        option_values: Sequence[str],
    ) -> CommunicationOptionDefinition | None:
        """Return a nested option resolved from an ordered path of values."""
        if not option_values:
            return None

        current_option = self.get_option(option_values[0])
        if current_option is None:
            return None

        for option_value in option_values[1:]:
            current_option = current_option.get_child(option_value)
            if current_option is None:
                return None

        return current_option

    def find_option_by_id(self, option_id: int) -> CommunicationOptionDefinition | None:
        """Return a top-level or nested option that matches the stored ID."""
        for option in self.options:
            matching_option = option.find_option_by_id(option_id)
            if matching_option is not None:
                return matching_option
        return None

    def get_qualifier(self, qualifier_key: str) -> CommunicationQualifierDefinition | None:
        """Return a qualifier definition by key, if present."""
        for qualifier in self.qualifiers:
            if qualifier.qualifier_key == qualifier_key:
                return qualifier
        return None


@dataclass(frozen=True, slots=True)
class SystemConfig:
    """Immutable runtime communication-system configuration collection."""

    systems: tuple[CommunicationSystemDefinition, ...] = ()

    @property
    def system_names(self) -> tuple[str, ...]:
        """Return configured system names in deterministic runtime order."""
        return tuple(system.system_name for system in self.systems)

    def get_system(self, system_name: str) -> CommunicationSystemDefinition | None:
        """Return one configured system by name, if present."""
        for system in self.systems:
            if system.system_name == system_name:
                return system
        return None

    @property
    def is_empty(self) -> bool:
        """Return ``True`` when no active communication systems are configured."""
        return not self.systems


class CommunicationConfigLoader:
    """Load and cache runtime communication configuration for one caller scope.

    The loader memoizes per instance only. Callers that need a fresh view after
    configuration changes must call :meth:`reload_config` or request
    ``force_reload=True`` when retrieving the configuration.
    """

    def __init__(self, config_source: CommunicationConfigSource) -> None:
        self._config_source = config_source
        self._cached_config: SystemConfig | None = None

    @property
    def has_cached_config(self) -> bool:
        """Return whether this loader instance currently holds a cached config."""
        return self._cached_config is not None

    def get_config(self, *, force_reload: bool = False) -> SystemConfig:
        """Return runtime communication configuration.

        By default, a previously loaded config is reused. Callers can request a
        fresh view explicitly by passing ``force_reload=True``.
        """
        if force_reload or self._cached_config is None:
            self._cached_config = self._load_config()
        assert self._cached_config is not None
        return self._cached_config

    def reload_config(self) -> SystemConfig:
        """Reload runtime communication configuration from the repository seam."""
        return self.get_config(force_reload=True)

    def _load_config(self) -> SystemConfig:
        systems = tuple(
            self._build_system_definition(system_config)
            for system_config in self._config_source.get_active_communication_system_configs()
        )
        return SystemConfig(systems=systems)

    def _build_system_definition(
        self,
        system_config: CommunicationSystemConfigLike,
    ) -> CommunicationSystemDefinition:
        return CommunicationSystemDefinition(
            system_id=system_config.system_id,
            system_name=system_config.system_name,
            system_type=system_config.system_type,
            child_label=system_config.child_label,
            sort_order=system_config.sort_order,
            options=tuple(
                self._build_option_definition(option)
                for option in system_config.options
            ),
            qualifiers=tuple(
                self._build_qualifier_definition(qualifier)
                for qualifier in system_config.qualifiers
            ),
        )

    def _build_option_definition(
        self,
        option_config: CommunicationOptionConfigLike,
    ) -> CommunicationOptionDefinition:
        return CommunicationOptionDefinition(
            option_id=option_config.option_id,
            option_value=option_config.option_value,
            option_label=option_config.option_label,
            child_label=option_config.child_label,
            sort_order=option_config.sort_order,
            children=tuple(
                self._build_option_definition(child_option)
                for child_option in option_config.children
            ),
        )

    def _build_qualifier_definition(
        self,
        qualifier_config: CommunicationQualifierConfigLike,
    ) -> CommunicationQualifierDefinition:
        return CommunicationQualifierDefinition(
            qualifier_key=qualifier_config.qualifier_key,
            label=qualifier_config.label,
            field_type=qualifier_config.field_type,
            valid_values=qualifier_config.valid_values,
            default_value=qualifier_config.default_value,
            help_text=qualifier_config.help_text,
            visibility_mode=qualifier_config.visibility_mode,
        )


class CommunicationConfigManager:
    """Coordinate targeted communication-config writes with explicit reloads."""

    def __init__(
        self,
        config_loader: CommunicationConfigLoader,
        config_mutator: CommunicationConfigMutator,
    ) -> None:
        self._config_loader = config_loader
        self._config_mutator = config_mutator

    def get_config(self, *, force_reload: bool = False) -> SystemConfig:
        """Return the current runtime configuration via the managed loader."""
        return self._config_loader.get_config(force_reload=force_reload)

    def add_option(
        self,
        *,
        system_name: str,
        option_value: str,
        option_label: str,
        parent_option_id: int | None = None,
        child_label: str | None = None,
        sort_order: int | None = None,
    ) -> CommunicationOptionMutationResult:
        """Create or reactivate one communication option and reload on change."""
        result = self._config_mutator.add_communication_option(
            system_name=system_name,
            option_value=option_value,
            option_label=option_label,
            parent_option_id=parent_option_id,
            child_label=child_label,
            sort_order=sort_order,
        )
        return self._attach_reloaded_config(result)

    def rename_option(
        self,
        *,
        option_id: int,
        option_label: str,
    ) -> CommunicationOptionMutationResult:
        """Rename one communication option and reload on change."""
        result = self._config_mutator.rename_communication_option(
            option_id=option_id,
            option_label=option_label,
        )
        return self._attach_reloaded_config(result)

    def deactivate_option(self, *, option_id: int) -> CommunicationOptionMutationResult:
        """Deactivate one communication option subtree and reload on change."""
        result = self._config_mutator.deactivate_communication_option(option_id=option_id)
        return self._attach_reloaded_config(result)

    def _attach_reloaded_config(
        self,
        result: CommunicationOptionMutationResult,
    ) -> CommunicationOptionMutationResult:
        if not result.requires_reload:
            return result

        return replace(result, config=self._config_loader.reload_config())



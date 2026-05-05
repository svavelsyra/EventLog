"""Reusable application configuration loading helpers for EventLog."""

from __future__ import annotations

from collections.abc import Mapping
from configparser import ConfigParser
from dataclasses import dataclass
import logging
from os import PathLike
from pathlib import Path

LOGGER = logging.getLogger(__name__)

DEFAULT_REQUIRE_KEY_FILE = False
DEFAULT_REQUIRE_KEY_FILE_FOR_CREATION = False
DEFAULT_MIN_PASSWORD_LENGTH = 8
DEFAULT_SECURE_DELETE_PASSES = 3
DEFAULT_KDF_ITERATIONS = 100_000


@dataclass(frozen=True, slots=True)
class BootstrapTargetConfig:
    """Remembered startup target and unlock hints from convenience config state."""

    dialect: str = ""
    database_path: str = ""
    require_key_file: bool = DEFAULT_REQUIRE_KEY_FILE

    @property
    def has_any_remembered_values(self) -> bool:
        """Return whether any remembered bootstrap hint is currently available."""
        return bool(self.dialect or self.database_path or self.require_key_file)

    @property
    def can_attempt_auto_open(self) -> bool:
        """Return whether bootstrap memory is complete enough for automatic open attempt."""
        return bool(self.dialect and self.database_path)

    @property
    def has_partial_remembered_values(self) -> bool:
        """Return whether remembered bootstrap hints exist but are incomplete."""
        return self.has_any_remembered_values and not self.can_attempt_auto_open


@dataclass(frozen=True, slots=True)
class DatabaseCreationDefaults:
    """Creation-time defaults and policy inputs loaded from convenience config state."""

    require_key_file_for_creation: bool = DEFAULT_REQUIRE_KEY_FILE_FOR_CREATION
    min_password_length: int = DEFAULT_MIN_PASSWORD_LENGTH
    secure_delete_passes: int = DEFAULT_SECURE_DELETE_PASSES
    kdf_iterations: int = DEFAULT_KDF_ITERATIONS


@dataclass(frozen=True, slots=True)
class DatabaseConfig:
    """Normalized bootstrap configuration for selecting the current database target.

    ``dialect``, ``database_path``, and ``require_key_file`` are remembered bootstrap
    selectors needed before the encrypted database can be opened. ``require_key_file_for_creation``,
    ``min_password_length``, ``secure_delete_passes``, and ``kdf_iterations`` are
    create-time defaults or operational convenience values; they are not authoritative
    runtime security values for already-created encrypted databases.
    """

    dialect: str = ""
    database_path: str = ""
    require_key_file: bool = DEFAULT_REQUIRE_KEY_FILE
    require_key_file_for_creation: bool = DEFAULT_REQUIRE_KEY_FILE_FOR_CREATION
    min_password_length: int = DEFAULT_MIN_PASSWORD_LENGTH
    secure_delete_passes: int = DEFAULT_SECURE_DELETE_PASSES
    kdf_iterations: int = DEFAULT_KDF_ITERATIONS

    @property
    def bootstrap_target(self) -> BootstrapTargetConfig:
        """Return the remembered startup target/hints separate from creation defaults."""
        return BootstrapTargetConfig(
            dialect=self.dialect,
            database_path=self.database_path,
            require_key_file=self.require_key_file,
        )

    @property
    def creation_defaults(self) -> DatabaseCreationDefaults:
        """Return creation-time defaults and policy inputs separate from bootstrap memory."""
        return DatabaseCreationDefaults(
            require_key_file_for_creation=self.require_key_file_for_creation,
            min_password_length=self.min_password_length,
            secure_delete_passes=self.secure_delete_passes,
            kdf_iterations=self.kdf_iterations,
        )

    @property
    def can_attempt_auto_open(self) -> bool:
        """Return whether remembered bootstrap memory is complete enough to try auto-open."""
        return self.bootstrap_target.can_attempt_auto_open

    @property
    def has_partial_bootstrap_memory(self) -> bool:
        """Return whether remembered bootstrap memory exists but needs recovery UI."""
        return self.bootstrap_target.has_partial_remembered_values


def load_app_config(config_path: str | PathLike[str]) -> ConfigParser:
    """Read an INI configuration file and return the parsed config object."""
    parser = ConfigParser(inline_comment_prefixes=("#", ";"))
    normalized_path = Path(config_path).expanduser()

    if not normalized_path.exists():
        return parser

    loaded_paths = parser.read(normalized_path, encoding="utf-8")

    if not loaded_paths:
        raise FileNotFoundError(f"Could not read configuration file: {normalized_path}")

    return parser



def save_bootstrap_section_options(
    config_path: str | PathLike[str],
    *,
    dialect: str,
    remembered_section_options: Mapping[str, str],
    cleared_section_options: Mapping[str, tuple[str, ...]] | None = None,
) -> None:
    """Persist selected dialect plus remembered per-dialect option strings.

    The config layer owns INI mechanics only: it updates ``[DEFAULT].db_type`` and
    writes exactly the provided remembered option strings into the selected
    technology section. Callers may also request explicit removal of specific
    remembered option names from named sections while unrelated sections and
    policy values remain preserved.
    """
    parser = load_app_config(config_path)
    normalized_path = Path(config_path).expanduser()
    normalized_path.parent.mkdir(parents=True, exist_ok=True)

    normalized_dialect = dialect.strip().lower()

    for section_name, option_names in (cleared_section_options or {}).items():
        if not parser.has_section(section_name):
            continue

        for option_name in option_names:
            parser.remove_option(section_name, option_name)

    if normalized_dialect:
        parser[parser.default_section]["db_type"] = normalized_dialect

        if remembered_section_options:
            if not parser.has_section(normalized_dialect):
                parser.add_section(normalized_dialect)

            target_section = parser[normalized_dialect]
            for option_name, option_value in remembered_section_options.items():
                target_section[option_name] = option_value.strip()
    else:
        parser.remove_option(parser.default_section, "db_type")

    with normalized_path.open("w", encoding="utf-8") as config_file:
        parser.write(config_file)




def _resolve_lookup_section(parser: ConfigParser, section: str | None) -> str:
    """Return the section name used for lookups, falling back to DEFAULT."""
    if section is not None and parser.has_section(section):
        return section

    return parser.default_section


def _get_stripped_option(
    parser: ConfigParser,
    section: str | None,
    option: str,
) -> str:
    """Return a stripped option using normal section lookup plus DEFAULT inheritance."""
    return parser.get(_resolve_lookup_section(parser, section), option, fallback="").strip()


def _get_bool_option(
    parser: ConfigParser,
    section: str | None,
    option: str,
    *,
    default: bool,
) -> bool:
    """Return a bool option using section lookup with DEFAULT fallback semantics."""
    lookup_section = _resolve_lookup_section(parser, section)

    try:
        return parser.getboolean(lookup_section, option, fallback=default)
    except ValueError:
        LOGGER.warning(
            "Invalid config value for %s.%s; using default %r.",
            lookup_section,
            option,
            default,
        )
        return default


def _get_int_option(
    parser: ConfigParser,
    section: str | None,
    option: str,
    *,
    default: int,
) -> int:
    """Return an int option using section lookup with DEFAULT fallback semantics."""
    lookup_section = _resolve_lookup_section(parser, section)

    try:
        return parser.getint(lookup_section, option, fallback=default)
    except ValueError:
        LOGGER.warning(
            "Invalid config value for %s.%s; using default %r.",
            lookup_section,
            option,
            default,
        )
        return default


def _get_selected_dialect(parser: ConfigParser) -> str:
    """Return the explicitly remembered/selected startup dialect from config."""
    return _get_stripped_option(parser, None, "db_type").lower()


def parse_database_config(parser: ConfigParser) -> DatabaseConfig | None:
    """Extract bootstrap/security config while leaving unrelated INI sections untouched.

    New-style config uses ``[DEFAULT]`` for shared fallback values and one section
    per technology for remembered target details plus optional technology-specific
    overrides. Ordinary unrelated sections such as ``[Logging]`` and
    ``[Application]`` are intentionally ignored by this bootstrap parser.
    """
    dialect = _get_selected_dialect(parser)
    technology_section = dialect or None
    defaults = parser.defaults()

    has_default_policy_values = any(
        defaults.get(option, "").strip()
        for option in (
            "db_type",
            "require_key_file_for_creation",
            "min_password_length",
            "secure_delete_passes",
            "kdf_iterations",
        )
    )
    has_technology_values = technology_section is not None and parser.has_section(technology_section)

    if not has_default_policy_values and not has_technology_values:
        return None

    database_path = _get_stripped_option(parser, technology_section, "database_path")

    require_key_file = _get_bool_option(
        parser,
        technology_section,
        "require_key_file",
        default=DEFAULT_REQUIRE_KEY_FILE,
    )
    require_key_file_for_creation = _get_bool_option(
        parser,
        technology_section,
        "require_key_file_for_creation",
        default=DEFAULT_REQUIRE_KEY_FILE_FOR_CREATION,
    )
    min_password_length = _get_int_option(
        parser,
        technology_section,
        "min_password_length",
        default=DEFAULT_MIN_PASSWORD_LENGTH,
    )
    secure_delete_passes = _get_int_option(
        parser,
        technology_section,
        "secure_delete_passes",
        default=DEFAULT_SECURE_DELETE_PASSES,
    )
    kdf_iterations = _get_int_option(
        parser,
        technology_section,
        "kdf_iterations",
        default=DEFAULT_KDF_ITERATIONS,
    )

    if secure_delete_passes > 10:
        LOGGER.warning(
            "Out-of-range config value for %s.%s; using default %r.",
            _resolve_lookup_section(parser, technology_section),
            "secure_delete_passes",
            DEFAULT_SECURE_DELETE_PASSES,
        )
        secure_delete_passes = DEFAULT_SECURE_DELETE_PASSES

    if not dialect and not database_path and not has_default_policy_values:
        return None

    return DatabaseConfig(
        dialect=dialect,
        database_path=database_path,
        require_key_file=require_key_file,
        require_key_file_for_creation=require_key_file_for_creation,
        min_password_length=min_password_length,
        secure_delete_passes=secure_delete_passes,
        kdf_iterations=kdf_iterations,
    )



def load_database_config(config_path: str | PathLike[str]) -> DatabaseConfig | None:
    """Load and normalize optional bootstrap database settings from an INI file path."""
    return parse_database_config(load_app_config(config_path))


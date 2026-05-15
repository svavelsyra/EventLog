"""Reusable application configuration loading helpers for EventLog."""

from __future__ import annotations

from collections.abc import Mapping
from configparser import ConfigParser
from dataclasses import dataclass, field
import logging
from os import PathLike
from pathlib import Path

LOGGER = logging.getLogger(__name__)

DEFAULT_REQUIRE_KEY_FILE = False
DEFAULT_REQUIRE_KEY_FILE_FOR_CREATION = False
DEFAULT_MIN_PASSWORD_LENGTH = 8
DEFAULT_SECURE_DELETE_PASSES = 3
DEFAULT_KDF_ITERATIONS = 100_000
DEFAULT_LANGUAGE = "sv"
DEFAULT_WINDOW_STATE = "normal"
DEFAULT_WINDOW_WIDTH = 1200
DEFAULT_WINDOW_HEIGHT = 700
DEFAULT_WINDOW_X = 100
DEFAULT_WINDOW_Y = 100
DEFAULT_TEMPLATE_DIALECT = "sqlite"
APP_RUNTIME_DATA_DIRECTORY_NAME = "data"
DEFAULT_CONFIG_FILENAME = "config.ini"
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_FILE_LOGGING_ENABLED = True
DEFAULT_LOG_DIRECTORY_NAME = "logs"
DEFAULT_LOG_FILE_NAME = "eventlog.log"
DEFAULT_LOG_FILE_PATH = (Path(DEFAULT_LOG_DIRECTORY_NAME) / DEFAULT_LOG_FILE_NAME).as_posix()
DEFAULT_LOG_FILE_MAX_BYTES = 10_485_760
DEFAULT_LOG_FILE_BACKUP_COUNT = 5
DEFAULT_CONSOLE_LOGGING_ENABLED = True
DEFAULT_CONSOLE_LOG_LEVEL = "WARNING"
DEFAULT_STATUS_BAR_LOG_LEVEL = "WARNING"
DEFAULT_LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
DEFAULT_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
CONFIG_TEMPLATE_FILENAME = "config.ini.template"

_SUPPORTED_WINDOW_STATES = frozenset({"normal", "zoomed"})
_SUPPORTED_LOG_LEVEL_NAMES = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})


def _escape_template_option_value(value: str) -> str:
    """Return a config-template-safe literal string for ConfigParser-based INI files."""
    return value.replace("%", "%%")


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


@dataclass(frozen=True, slots=True)
class MainWindowConfig:
    """Bootstrap-owned main-window geometry and supported top-level state."""

    window_state: str = DEFAULT_WINDOW_STATE
    window_width: int = DEFAULT_WINDOW_WIDTH
    window_height: int = DEFAULT_WINDOW_HEIGHT
    window_x: int = DEFAULT_WINDOW_X
    window_y: int = DEFAULT_WINDOW_Y


@dataclass(frozen=True, slots=True)
class BootstrapUiConfig:
    """Bootstrap-owned app UI and startup-user convenience settings."""

    main_window: MainWindowConfig = field(default_factory=MainWindowConfig)
    language: str = DEFAULT_LANGUAGE
    last_operator: str = ""
    status_bar_log_level: str = DEFAULT_STATUS_BAR_LOG_LEVEL


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


def _get_positive_int_option(
    parser: ConfigParser,
    section: str | None,
    option: str,
    *,
    default: int,
) -> int:
    """Return a strictly positive int option or the provided default."""
    value = _get_int_option(parser, section, option, default=default)
    if value > 0:
        return value

    lookup_section = _resolve_lookup_section(parser, section)
    LOGGER.warning(
        "Out-of-range config value for %s.%s; using default %r.",
        lookup_section,
        option,
        default,
    )
    return default


def _get_supported_window_state_option(
    parser: ConfigParser,
    section: str | None,
    option: str,
    *,
    default: str,
) -> str:
    """Return a supported persisted window state or the provided default."""
    lookup_section = _resolve_lookup_section(parser, section)
    resolved_value = parser.get(lookup_section, option, fallback=default).strip().lower()
    if resolved_value in _SUPPORTED_WINDOW_STATES:
        return resolved_value

    LOGGER.warning(
        "Invalid config value for %s.%s; using default %r.",
        lookup_section,
        option,
        default,
    )
    return default


def _normalize_language(value: str) -> str:
    """Return normalized bootstrap language with fallback to the code default."""
    normalized_value = value.strip().lower()
    return normalized_value or DEFAULT_LANGUAGE


def _normalize_log_level_name(value: str) -> str:
    """Return a normalized supported log-level name or the code default."""
    normalized_value = value.strip().upper()
    if normalized_value in _SUPPORTED_LOG_LEVEL_NAMES:
        return normalized_value

    return DEFAULT_STATUS_BAR_LOG_LEVEL


def _get_supported_log_level_option(
    parser: ConfigParser,
    section: str | None,
    option: str,
    *,
    default: str,
) -> str:
    """Return a supported uppercase log-level name or the provided default."""
    lookup_section = _resolve_lookup_section(parser, section)
    resolved_value = parser.get(lookup_section, option, fallback=default).strip().upper()
    if resolved_value in _SUPPORTED_LOG_LEVEL_NAMES:
        return resolved_value

    LOGGER.warning(
        "Invalid config value for %s.%s; using default %r.",
        lookup_section,
        option,
        default,
    )
    return default


def _normalize_window_state(value: str) -> str:
    """Return a supported persisted window state for storage."""
    normalized_value = value.strip().lower()
    if normalized_value in _SUPPORTED_WINDOW_STATES:
        return normalized_value

    return DEFAULT_WINDOW_STATE


def _get_selected_dialect(parser: ConfigParser) -> str:
    """Return the explicitly remembered/selected startup dialect from config."""
    return _get_stripped_option(parser, None, "db_type").lower()


def parse_bootstrap_ui_config(parser: ConfigParser) -> BootstrapUiConfig:
    """Extract bootstrap-owned UI settings plus selected shell logging display policy."""
    return BootstrapUiConfig(
        main_window=MainWindowConfig(
            window_state=_get_supported_window_state_option(
                parser,
                "Application",
                "window_state",
                default=DEFAULT_WINDOW_STATE,
            ),
            window_width=_get_positive_int_option(
                parser,
                "Application",
                "window_width",
                default=DEFAULT_WINDOW_WIDTH,
            ),
            window_height=_get_positive_int_option(
                parser,
                "Application",
                "window_height",
                default=DEFAULT_WINDOW_HEIGHT,
            ),
            window_x=_get_int_option(
                parser,
                "Application",
                "window_x",
                default=DEFAULT_WINDOW_X,
            ),
            window_y=_get_int_option(
                parser,
                "Application",
                "window_y",
                default=DEFAULT_WINDOW_Y,
            ),
        ),
        language=_normalize_language(_get_stripped_option(parser, "Application", "language")),
        last_operator=_get_stripped_option(parser, "User", "last_operator"),
        status_bar_log_level=_get_supported_log_level_option(
            parser,
            "Logging",
            "status_bar_log_level",
            default=DEFAULT_STATUS_BAR_LOG_LEVEL,
        ),
    )


def load_bootstrap_ui_config(config_path: str | PathLike[str]) -> BootstrapUiConfig:
    """Load bootstrap-owned main-window and startup-user settings from an INI path."""
    return parse_bootstrap_ui_config(load_app_config(config_path))


def save_bootstrap_ui_config(
    config_path: str | PathLike[str],
    bootstrap_ui_config: BootstrapUiConfig,
) -> None:
    """Persist bootstrap-owned UI/user settings while preserving unrelated sections."""
    parser = load_app_config(config_path)
    normalized_path = Path(config_path).expanduser()
    normalized_path.parent.mkdir(parents=True, exist_ok=True)

    if not parser.has_section("Application"):
        parser.add_section("Application")
    if not parser.has_section("User"):
        parser.add_section("User")

    main_window = bootstrap_ui_config.main_window
    parser["Application"]["window_state"] = _normalize_window_state(main_window.window_state)
    parser["Application"]["window_width"] = str(max(1, int(main_window.window_width)))
    parser["Application"]["window_height"] = str(max(1, int(main_window.window_height)))
    parser["Application"]["window_x"] = str(int(main_window.window_x))
    parser["Application"]["window_y"] = str(int(main_window.window_y))
    parser["Application"]["language"] = _normalize_language(bootstrap_ui_config.language)
    parser["User"]["last_operator"] = bootstrap_ui_config.last_operator.strip()

    with normalized_path.open("w", encoding="utf-8") as config_file:
        parser.write(config_file)


def render_config_template() -> str:
    """Return the canonical reference ``config.ini.template`` text.

    The generated content is code-owned and deterministic so the checked-in
    template can be regenerated without treating that checked-in file as the
    runtime authority.
    """
    bootstrap_ui_defaults = BootstrapUiConfig()
    main_window_defaults = bootstrap_ui_defaults.main_window

    template_lines = [
        "# EventLog Application Configuration Template",
        "# Copy this to data/config.ini and customize for your installation",
        "# The default live runtime config is app-local under the data/ folder.",
        "",
        "[DEFAULT]",
        "# Shared fallback values for bootstrap/security-related settings.",
        "# Regular sections such as [sqlite], [Logging], and [Application] remain valid;",
        "# values placed here are simply inherited unless a section overrides them.",
        "# These values are convenience state only; existing encrypted databases remain",
        "# authoritative for their own runtime security values.",
        "",
        "# Selected database technology.",
        "# Startup resolves technology first, then uses that technology section for its",
        "# remembered target details and any technology-specific overrides.",
        "# sqlite is the only supported runtime today.",
        f"db_type = {DEFAULT_TEMPLATE_DIALECT}",
        "",
        "# Whether NEW databases created on this machine must use a key file.",
        "# This is separate from the technology section's `require_key_file`, which only remembers whether",
        "# the last already-created database used key-file mode at unlock time.",
        f"require_key_file_for_creation = {str(DEFAULT_REQUIRE_KEY_FILE_FOR_CREATION).lower()}",
        "",
        "# Minimum password length used when creating a NEW database.",
        f"min_password_length = {DEFAULT_MIN_PASSWORD_LENGTH}",
        "",
        "# Best-effort overwrite passes for emergency Nollställ cleanup.",
        f"secure_delete_passes = {DEFAULT_SECURE_DELETE_PASSES}",
        "",
        "# PBKDF2 iteration default used when creating a NEW encrypted database.",
        "# Existing encrypted databases must not silently inherit later config changes here.",
        f"kdf_iterations = {DEFAULT_KDF_ITERATIONS}",
        "",
        "# NEVER store passwords, derived keys, raw key-file content, or remembered key-file paths",
        "# in config.ini, logs, or database tables.",
        "",
        "[sqlite]",
        "# Remembered startup hints for the selected SQLite target.",
        "# SQLite-specific overrides for shared [DEFAULT] values may also be added here if needed.",
        "# These values help prefill the startup UI, but they are not authoritative and",
        "# must never prevent recovery-capable startup if they are missing or malformed.",
        "# With the default live config at data/config.ini, the managed runtime SQLite",
        "# database lives beside it as data/eventlog.db.",
        "",
        "# Remembered last-used SQLite database target/path.",
        "database_path = eventlog.db",
        "",
        "# Remembered last-used unlock mode hint for this SQLite target.",
        "# This is startup memory for opening an already-created database, not the admin",
        "# policy for whether NEW databases must use a key file.",
        "# Do NOT store any key-file path here.",
        f"require_key_file = {str(DEFAULT_REQUIRE_KEY_FILE).lower()}",
        "",
        "# Optional SQLite-specific override examples:",
        "# min_password_length = 10",
        "# require_key_file_for_creation = true",
        "",
        "[Logging]",
        "# Log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL",
        f"log_level = {DEFAULT_LOG_LEVEL}",
        "",
        "# File logging",
        f"file_logging_enabled = {str(DEFAULT_FILE_LOGGING_ENABLED).lower()}",
        "# With the default live config at data/config.ini, this relative path resolves",
        "# to data/logs/eventlog.log.",
        f"log_file_path = {DEFAULT_LOG_FILE_PATH}",
        f"log_file_max_bytes = {DEFAULT_LOG_FILE_MAX_BYTES}  # 10 MB per file",
        f"log_file_backup_count = {DEFAULT_LOG_FILE_BACKUP_COUNT}  # Keep {DEFAULT_LOG_FILE_BACKUP_COUNT} old log files (total ~50 MB)",
        "",
        "# Console logging (for development/debugging)",
        f"console_logging_enabled = {str(DEFAULT_CONSOLE_LOGGING_ENABLED).lower()}",
        f"console_log_level = {DEFAULT_CONSOLE_LOG_LEVEL}  # Less verbose for console",
        "",
        "# Status bar logging (GUI - shows in status bar)",
        f"status_bar_log_level = {DEFAULT_STATUS_BAR_LOG_LEVEL}  # Default: WARNING+ (WARNING, ERROR, CRITICAL)",
        "",
        "# Log format",
        f"log_format = {_escape_template_option_value(DEFAULT_LOG_FORMAT)}",
        f"date_format = {_escape_template_option_value(DEFAULT_DATE_FORMAT)}",
        "",
        "[Application]",
        "# Application window settings (managed by app, modify with caution)",
        f"window_state = {main_window_defaults.window_state}",
        f"window_width = {main_window_defaults.window_width}",
        f"window_height = {main_window_defaults.window_height}",
        f"window_x = {main_window_defaults.window_x}",
        f"window_y = {main_window_defaults.window_y}",
        "",
        "# Language (sv = Swedish, en = English)",
        f"language = {bootstrap_ui_defaults.language}",
        "",
        "[User]",
        "# Bootstrap-only user convenience values.",
        "# This section must never contain secrets; it only helps prefill startup UI.",
        "last_operator =",
        "",
    ]
    return "\n".join(template_lines)


def write_config_template(template_path: str | PathLike[str]) -> Path:
    """Write the canonical reference ``config.ini.template`` to disk and return its path."""
    normalized_path = Path(template_path).expanduser()
    normalized_path.parent.mkdir(parents=True, exist_ok=True)
    normalized_path.write_text(render_config_template(), encoding="utf-8")
    return normalized_path


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


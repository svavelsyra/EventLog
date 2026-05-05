# Core Architecture (AI)

**Layer**: Business Logic  
**Last Updated**: 2026-04-19

## Overview
The Core layer contains all business logic and domain models. It has no dependencies on GUI or database layers.

**Architecture Decision**: Three specialized domain entities instead of one generic entity.

**Reasoning**: Different information types (communications, events, personnel) have different business rules and validation requirements. Specialized entities provide cleaner separation and type-specific logic.

## Domain Models

### CommunicationEntry
Domain entity representing radio/phone/in-person communications and written orders.

**Purpose**: Log communications with system-centric hierarchy (System → Method → Channel → Capabilities).

**Key Architectural Patterns**:
- Immutable ID (set by database)
- Auto-fill defaults (logged_time, operator)
- System-centric validation (system defines supported methods)
- Configuration-driven capabilities (JSON metadata)

**See**: `ai_instructions/design/core_design.md` for complete field definitions.

### EventEntry
Domain entity representing operational events, incidents, and status changes.

**Purpose**: Log events with optional structured report attachments.

**Key Architectural Patterns**:
- Minimal required fields (only description, timing, accountability)
- Priority/category tagging (user-configurable)
- Relationship to StructuredReport entities (one-to-many)

**See**: `ai_instructions/design/core_design.md` for complete field definitions.

### PersonnelEntry
Domain entity representing personnel and group tracking with historical status changes.

**Purpose**: Track personnel status, location, and check-in alarms.

**Key Architectural Patterns**:
- Historical tracking (active flag + supersedes relationships)
- Check-in alarm management (conditional validation)
- Status change workflow (create new entry, mark old inactive)

**See**: `ai_instructions/design/core_design.md` for complete field definitions.

### StructuredReport
Domain entity representing structured military report formats (7S, 9-liner, etc.) attached to EventEntry.

**Purpose**: Separate entity to avoid field duplication and support multiple report templates.

**Key Architectural Patterns**:
- Template-driven fields (JSON storage with type-specific validation)
- Auto-summary generation (configuration defines format)
- Parent relationship (foreign key to EventEntry)

**See**: `ai_instructions/design/core_design.md` for complete field definitions.

## Validation Architecture

### Separate Validators Per Entity Type

**Pattern**: Static methods in dedicated validator classes (no shared state).

**Validators**:
- `CommunicationEntryValidator` - System/method hierarchy, capabilities validation
- `EventEntryValidator` - Priority, category, content validation
- `PersonnelEntryValidator` - Alarm fields, supersedes, active flag validation
- `StructuredReportValidator` - Template-driven validation, report type checking

**Location**: `src/core/validators/` (one file per validator)

**Behavior**:
- All raise `ValidationError` with descriptive messages
- Used before creating/updating entities
- No GUI logic (presenters handle error display)
- No database logic (validators are pure business rules)

**Example Structure**:
```python
from datetime import datetime


class SystemConfig:
    ...


class CommunicationEntryValidator:
    @staticmethod
    def validate_event_time(dt: datetime) -> None:
        # Business rule: cannot be in future
        ...

    @staticmethod
    def validate_required_field(value: str, field_name: str, max_length: int | None = None) -> None:
        # Business rule: non-empty, max length
        ...

    @staticmethod
    def validate_communication_selection(communication_system: str | None,
                                         communication_path: list[dict] | None,
                                         communication_qualifiers: dict | None,
                                         config: SystemConfig) -> None:
        # Business rule: system, recursive path, and qualifiers must fit configured rules
        ...
```

### Configuration-Driven Validation

**Pattern**: Validators accept configuration objects to validate against dynamic rules.

**Configuration Sources** (loaded from database):
- `SystemConfig`: Which communication systems/ways exist, which recursive options exist beneath them, and which top-level qualifiers/capabilities apply
- `ReportTemplateConfig`: Which report types exist, required/optional fields
- `CategoryConfig`: Valid categories for events
- `PriorityConfig`: Valid priorities for events

**Rationale**: Business rules depend on user-configured data (e.g., which communication systems exist, which configured paths/options are available beneath a system, and whether qualifiers such as `encrypted` are selectable, forced, or hidden). Validators validate against current configuration state.

**Example**:
```python
class ValidationError(Exception):
    ...


class CapabilityDefinition:
    def __init__(self, field_type: str, valid_values: list[str]) -> None:
        self.field_type = field_type
        self.valid_values = valid_values


class SystemDefinition:
    def get_capability(self, key: str) -> CapabilityDefinition:
        return CapabilityDefinition("enum", [])


class SystemConfig:
    def get_system(self, system_name: str) -> SystemDefinition:
        return SystemDefinition()


# Validator receives configuration
def validate_system_capabilities(system_name: str, 
                                 capabilities: dict,
                                 config: SystemConfig) -> None:
    system = config.get_system(system_name)
    for key, value in capabilities.items():
        capability_def = system.get_capability(key)
        if capability_def.field_type == "enum":
            if value not in capability_def.valid_values:
                raise ValidationError(f"Invalid {key}: {value}")
```

## Entity Creation Patterns

### Option 1: Simple Class Constructors (Recommended)

**Pattern**: Entities are simple dataclasses/classes with `__init__`.

**Creation**:
```python
class CommunicationEntry:
    def __init__(self, message_content: str, from_field: str) -> None:
        self.message_content = message_content
        self.from_field = from_field


class CommunicationEntryValidator:
    @staticmethod
    def validate_all(entry: CommunicationEntry, config: object) -> None:
        ...


class Repository:
    def create(self, entry: CommunicationEntry) -> None:
        ...


config = object()
repository = Repository()

# Presenters create entities directly
entry = CommunicationEntry(
    message_content="...",
    from_field="...",
    # ... other fields
)

# Validate before saving
CommunicationEntryValidator.validate_all(entry, config)
repository.create(entry)
```

**Pros**: Simple, explicit, no magic
**Cons**: Presenters must know all fields

### Option 2: Factory Pattern (If Needed Later)

**Pattern**: Factory methods encapsulate creation logic.

**When to use**: If creation logic becomes complex (e.g., deriving fields, multiple creation scenarios).

**Example**:
```python
class SystemConfig:
    ...


class CommunicationEntry:
    def __init__(self) -> None:
        ...


class CommunicationEntryValidator:
    @staticmethod
    def validate_all(entry: CommunicationEntry, config: SystemConfig) -> None:
        ...


class CommunicationEntryFactory:
    @staticmethod
    def create_from_user_input(data: dict, config: SystemConfig) -> CommunicationEntry:
        # Apply defaults, derive fields, validate
        entry = CommunicationEntry()
        CommunicationEntryValidator.validate_all(entry, config)
        return entry
```

**Decision**: Start with Option 1 (simple). Introduce factories only if complexity warrants it.

## Business Rules

### Auto-Fill Rules (Applied by Presenters or Repositories)

**Pattern**: Default values set before validation.

**Common auto-fills**:
- `logged_time`: `datetime.now()` if not provided
- `event_time`: Copy from `logged_time` if not provided (EventEntry, PersonnelEntry)
- `operator`: Prefill from last operator used (from user_preferences)
- `confirmed`: `False` (CommunicationEntry)
- `priority`: `"Normal"` (EventEntry)
- `active`: `True` (PersonnelEntry)
- `edited`: `False` (all entities)

**Implementation Location**: Presenters apply defaults before calling validators.

### Required vs Optional Fields Philosophy

**Minimal Required Fields** (enforced by validators):
- Content field (message_content, event_description, who)
- Timing field (event_time or logged_time)
- Accountability field (operator)

**Everything Else Optional** (better empty than garbage):
- from_field, to_field (CommunicationEntry)
- whom (EventEntry)
- status, location (PersonnelEntry)
- communication system / path / qualifiers (CommunicationEntry - may be empty when not captured, but should come from runtime config when used)

**Rationale**: Fast operational tempo - capture what you have, fill details later during review.

### Communication Configuration Validation Ownership

**Business Rule**: Communication meaning is owned by configuration, not by hardcoded radio-shaped assumptions.

**Validation Flow** (Configuration-Driven):
1. If `communication_system` is set (e.g., "RA180"):
   - the system must exist in runtime configuration
   - top-level qualifier values must match the qualifier rules configured for that system
2. If a recursive `communication_path` is present:
   - each selected step must correspond to a valid configured option beneath the chosen system or parent option
   - ordering/parent-child meaning comes from configuration, not from hardcoded tier semantics
3. If the selected system exposes no child options:
   - the path may be empty
4. If qualifier behavior is forced or hidden by configuration:
   - caller-provided values must be normalized or rejected according to the runtime contract

**Configuration Integration**: 
- Validators accept `SystemConfig` to check current system definitions
- Visible child selections are determined by configured recursive options, not by hardcoded `method` or `channel` fields
- Top-level qualifier behavior is determined by configuration, not by presenter-local assumptions
- The GUI may present only a bounded number of visible selection controls, but Core should treat the underlying structure as a configured path rather than a permanently fixed hierarchy

**See**: `ai_instructions/design/core_design.md` for complete validation rules.

### Historical Tracking (PersonnelEntry)

**Business Rule**: Only one active entry per "who" value.

**Pattern**: When creating new status entry via "Update Status":
1. Create new PersonnelEntry with `active=True`
2. Set `supersedes` field to old entry ID
3. Mark old entry as `active=False` (update in database)

**Validation**: Validator warns (not errors) if multiple active=True entries for same "who".

### Structured Report Attachment

**Business Rule**: StructuredReport must reference existing EventEntry.

**Pattern**: 
1. Create/save EventEntry first
2. Create StructuredReport with `parent_event_id` = EventEntry.id
3. Generate `auto_summary` from report_data based on template config
4. Save StructuredReport

**Validation**: `parent_event_id` must exist (validator checks against repository/config).

## Configuration Management

**Pattern**: Configuration objects loaded from database, passed to validators and presenters.

**Configuration Types**:
- `SystemConfig`: Communication systems/ways, recursive option structures, qualifier behavior
- `ReportTemplateConfig`: Structured report templates, field definitions, summary formats
- `CategoryConfig`: Valid event categories
- `PriorityConfig`: Valid event priorities

**Loading**: Configuration manager in core layer loads from database via adapter.

**Caching**: Configuration cached in memory (reloaded on settings change).

**Usage**: Presenters fetch configuration, pass to validators and UI builders. Core remains responsible for interpreting the configured communication path and qualifier rules; GUI should render from config without inventing communication semantics locally.

## Dependencies
- **None** - Core layer has no dependencies on other application layers
- Standard library only (datetime, json, etc.)

## Testing

### Unit Tests
- Test each validator independently
- Test with valid and invalid inputs
- Test configuration-driven validation (mock configs)
- Test auto-fill logic
- No database needed (pure business logic)

### Test Organization
- `tests/unit/core/validators/` - Validator tests
- `tests/unit/core/entities/` - Entity creation tests
- Fixtures for common configurations

---

**Related**:
- Human version: `docs/architecture/root_architecture.md`
- Core design: `ai_instructions/design/core_design.md`
- Database architecture: `ai_instructions/architecture/db_architecture.md`



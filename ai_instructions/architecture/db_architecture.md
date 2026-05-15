# Database Architecture (AI)

**Layer**: Data Access  
**Last Updated**: 2026-05-07 (Session 100 - Clarified startup field-contract boundary versus GUI state ownership)

## Overview
Database layer provides data persistence through a clear split between low-level database adapters and higher-level repositories. SQLite is the current concrete dialect, but the architecture is still shaped so additional backends can be introduced later without rewriting higher layers.

**Architecture Decision**: Use a low-level `DatabaseAdapter`, a concrete `SQLiteAdapter`, a generic `BaseRepository`, dialect-specific repositories under `src/db/repositories/sqlite/`, and a `RepositoryFactory` for construction.

**Reasoning**:
- Separate low-level database mechanics from repository/business-rule logic
- Keep the current single repository viable now while making future splits easier
- Preserve future database/dialect flexibility without overbuilding today
- Give tests a cleaner seam: adapter mechanics vs repository behavior

**Status Note**: The current code now follows the approved repository/adpater split for active SQLite runtime paths: `RepositoryFactory` constructs `EventLogRepository` with a `SQLiteAdapter`, and the earlier legacy compatibility repository file has been retired.

## CRITICAL: Bootstrap Architecture and Startup Invariants

This section is intentionally prominent because future AI sessions must not infer bootstrap rules only from the current SQLite implementation details.

### Core Bootstrap Rule

**Bootstrap is backend-agnostic orchestration. Readiness is backend-specific adapter behavior.**

That means:
- Startup/bootstrap decides **what kind of backend** the application is trying to use and whether that backend profile is supported.
- The concrete adapter decides **how that backend becomes ready** for repository use.
- Repository code must not own startup identity/version/migration logic.

### Generic Bootstrap Phases

The long-term bootstrap flow must stay generic enough to support:
- local embedded databases
- encrypted local databases
- remote databases
- service-backed persistence
- future providers or implementations written in other languages

The generic bootstrap phases are:

1. **Target resolution** - Normalize the requested database target/profile from UI/config/bootstrap input.
2. **Profile validation** - Confirm the requested backend kind, dialect, and provider are supported by the current runtime.
3. **Adapter construction** - Create the concrete low-level adapter.
4. **Adapter readiness** - Let the adapter perform backend-specific open/auth/init/version/migration work.
5. **Repository construction** - Build repositories only after adapter readiness succeeds.

### Required Separation of Concerns

#### Bootstrap / Factory Owns
- target/profile resolution
- support validation
- centralized backend-policy ownership for startup field requirements, remembered-target persistence/normalization, and coarse startup capabilities
- adapter selection/creation
- high-level orchestration
- returning only ready-to-use repositories

#### Adapter Owns
- backend-specific open/connect logic
- authentication/unlock behavior
- identity validation
- schema version inspection
- initialization and migrations
- backend-specific readiness checks

#### Repository Owns
- CRUD workflows
- query construction
- row/entity mapping
- repository-level business rules

### Startup Field Requirement Seam

- When persistence/startup code needs to tell higher layers which startup inputs are required for a backend, it should expose only a stable technical contract: field identity, input kind, and required/editable flags.
- Persistence/startup seams must not carry presenter-flavored labels, browse-button actions, or other GUI presentation metadata.
- GUI code may derive labels, browse-button wiring, and other display behavior from the stable field identities without reintroducing backend-specific branching.
- The current ownership seam for those backend startup facts is `src/db/repositories/bootstrap_backend_policy.py`; shared startup field/profile types may still live separately, but the policy decisions themselves should not be split back across app wiring, factory helpers, and ad-hoc wrapper modules.
- Persistence does **not** own when the dialog re-renders, how remembered values are shown, or how operator-entered values are read back during interaction.
- Those higher-level interaction concerns belong to the presenter/controller/view loop, which should exchange whole startup state and structured submissions rather than inventing new persistence-facing field accessors.
- If future startup UI needs another display label, hint, browse action, or focus rule, add it in GUI-owned state/design layers unless the requirement is truly a backend capability fact.

### Do Not Hardcode SQLite Assumptions into Bootstrap

Even though SQLite is the only supported backend today, the architecture must not assume that all future backends:
- are file based
- expose SQLite headers
- use SQL directly
- support direct local schema inspection

So, rules like **"check whether a DB file exists"** are valid only inside the SQLite adapter path, not as the general bootstrap architecture.

### Current SQLite Startup Policy

For the current SQLite backend, the approved startup/readiness direction is:
- missing file => create a new database, initialize schema, and stamp required identity/version metadata
- existing file => open existing database flow, then validate it after open/unlock
- use SQLite header metadata as the authoritative startup identity/version source when available:
  - `PRAGMA application_id` => database identity
  - `PRAGMA user_version` => schema/migration version
- do **not** use repository/business-settings tables as the authoritative startup version source
- because released databases are expected to include version metadata from the start, missing/invalid version metadata should be treated as an error rather than a legacy compatibility path

### Transitional Warning for Current Refactor Work

The current SQLite bootstrap path may still contain heuristics such as table-existence checks. Those are scaffolding only.

**They are not the long-term startup architecture.**

The long-term architecture remains:
- generic bootstrap outside the adapter
- backend-specific readiness inside the adapter
- version/identity-based startup decisions rather than core-table heuristics

## Patterns

### Database Adapter Pattern
Abstract base class defines the low-level database interface.

**Location**: `src/db/database_adapter.py`

**Purpose**:
- Encapsulate connection and transaction primitives
- Support multiple backends in the future
- Centralize database-specific exceptions
- Keep repositories focused on query intent instead of driver mechanics

**Key Module**:
- `database_adapter.py` - Abstract adapter contract plus shared exceptions such as `DatabaseNewer`, `MigrationNeeded`, and `WrongDatabaseAdapter`

**Design Note**: The adapter layer is intentionally low-level. It should expose operations like connect, initialize schema, execute, fetch, fetchone, and transaction control, not domain CRUD workflows.

### Concrete SQLite Adapter
Concrete SQLite implementation of `DatabaseAdapter`.

**Location**: `src/db/sqlite_adapter.py`

**Purpose**:
- Open and close SQLite connections
- Initialize schema and apply SQLite bootstrap logic
- Execute SQL and return rows/results
- Handle transaction primitives and low-level SQLite behavior

**Design Note**: Repositories prepare SQL and delegate execution downward into the adapter.

### Repository Pattern
Repositories provide the application-facing persistence API.

**Location**: `src/db/repositories/`

**Purpose**:
- Own CRUD-style persistence workflows
- Build SQL queries and define filtering/search behavior
- Apply repository-level business rules
- Translate between rows and domain entities
- Delegate execution and transaction mechanics to the adapter layer

**Key Modules**:
- `base_repository.py` - Generic repository base class; dialect-agnostic
- `bootstrap_backend_policy.py` - Centralized backend-policy registry for startup/bootstrap support facts, remembered-target behavior, and repository creation dispatch
- `repository_factory.py` - Constructs repositories from adapter + dialect context
- `sqlite/event_log_repository.py` - Main concrete SQLite repository for the application

**Current Runtime Shape**:
- `bootstrap_backend_policy.py` owns startup/bootstrap backend policy facts and the per-dialect repository-construction dispatch
- `RepositoryFactory` delegates to that centralized backend-policy seam and returns a ready repository
- `EventLogRepository` owns CRUD/query behavior, repository-level business rules, and row mapping
- `SQLiteAdapter` owns SQLite connection lifecycle, schema initialization, execution primitives, and transaction primitives

**Design Note**: For now, one public repository is enough. It should still be structured so communication, event, and personnel logic can be split into smaller repository files later if growth or test scope demands it.

**Planned Repository Boundary Direction**:
- The long-term preferred split is by the application's main operational areas: `CommunicationRepository`, `EventRepository`, and `PersonnelRepository`.
- If `EventLogRepository` remains after that split, it should become a deliberately small shared/configuration seam rather than a second catch-all CRUD repository.
- That shared/configuration seam may own cross-cutting runtime metadata such as communication configuration reads, low-level repository `settings`, and similarly shared operational metadata that does not belong cleanly to one main tab/workflow area.
- Startup/bootstrap backend policy does **not** move into that shared/configuration seam; `bootstrap_backend_policy.py` remains the ownership boundary for startup/backend-policy facts and repository-construction dispatch.
- Future refactors should avoid ending up with both three domain repositories **and** a still-large `EventLogRepository`; either the shared repository stays thin or it should be renamed to match its narrowed role.

### Dialect-Specific Repository Packages
Concrete repositories live in dialect-specific subpackages.

**Location**: `src/db/repositories/sqlite/`

**Purpose**:
- Keep dialect-specific SQL isolated
- Make future backend-specific repositories easy to add
- Allow one repository today while keeping clean split points for tomorrow

**Current SQLite package state**:
- `src/db/repositories/sqlite/event_log_repository.py` is the only active concrete SQLite repository module in runtime use
- The earlier legacy top-level SQLite repository compatibility file has been removed

**Expected SQLite package shape**:
- `event_log_repository.py` - Single concrete repository returned publicly for now; if retained later, it should narrow toward shared/configuration concerns or a thin facade role
- `communication_repository.py` - Extracted communication persistence logic when needed
- `event_repository.py` - Extracted event persistence logic when needed
- `personnel_repository.py` - Extracted personnel persistence logic when needed
- `configuration_repository.py` - Optional future home for shared runtime metadata/configuration if that role becomes large enough to deserve a clearer name than `EventLogRepository`

## Target Package Layout

```text
src/db/
├── database_adapter.py
├── sqlite_adapter.py
├── repositories/
│   ├── base_repository.py
│   ├── bootstrap_backend_policy.py
│   ├── repository_factory.py
│   └── sqlite/
│       ├── event_log_repository.py
│       ├── communication_repository.py
│       ├── event_repository.py
│       ├── personnel_repository.py
│       └── configuration_repository.py
└── schema/
    ├── schema_executor.py
    └── sqlite/
        └── initial_schema.sql
```

## Interface Organization

### Database Adapter Structure

```text
class DatabaseAdapter(ABC):
    @abstractmethod
    def connect() -> None:
        ...

    @abstractmethod
    def initialize_schema() -> None:
        ...

    @abstractmethod
    def execute(query: str, params: tuple[object, ...] = ()) -> object:
        ...

    @abstractmethod
    def fetch(query: str, params: tuple[object, ...] = ()) -> list[object]:
        ...

    @abstractmethod
    def fetchone(query: str, params: tuple[object, ...] = ()) -> object | None:
        ...

    @abstractmethod
    def begin_transaction() -> None:
        ...

    @abstractmethod
    def commit_transaction() -> None:
        ...

    @abstractmethod
    def rollback_transaction() -> None:
        ...

    @abstractmethod
    def close() -> None:
        ...
```

**Rationale**:
- Keeps adapter responsibilities low-level and backend-oriented
- Prevents domain CRUD methods from leaking into the wrong abstraction
- Makes future dialect additions much easier

### Generic Repository Base Structure

```text
class BaseRepository(ABC):
    @abstractmethod
    def begin_transaction() -> None:
        ...

    @abstractmethod
    def commit_transaction() -> None:
        ...

    @abstractmethod
    def rollback_transaction() -> None:
        ...

    @abstractmethod
    def close() -> None:
        ...

    # Concrete repositories then define their CRUD and utility methods.
```

**Rationale**:
- Repository base stays dialect-agnostic
- CRUD-heavy repositories can share expectations without embedding SQLite details
- Utility methods can be added here later if they become consistently cross-repository

### Concrete Repository Structure

```text
class EventLogRepository(BaseRepository):
    def create_communication_entry(self, entry: CommunicationEntry) -> int: ...
    def update_event_entry(self, entry: EventEntry) -> bool: ...
    def get_active_personnel_entries(self) -> list[PersonnelEntry]: ...
```

**Design Note**: The repository builds SQL queries and applies repository/business rules, then delegates query execution and transaction mechanics to the injected adapter.

**Current Implementation Note**: The codebase now matches this structure for active SQLite repository paths; remaining transition work is primarily about startup/version policy refinement and future repository splitting, not about preserving the removed legacy repository shell.

## Factory Pattern
**Pattern**: Factory creates repository instances from adapter and dialect context.

```text
class RepositoryFactory:
    def __init__(self, adapter: DatabaseAdapter, dialect: DatabaseDialect) -> None:
        self._adapter = adapter
        self._dialect = dialect

    def get_event_log_repository(self) -> BaseRepository:
        if self._dialect is DatabaseDialect.SQLITE:
            return EventLogRepository(self._adapter)

        raise WrongDatabaseAdapter(f"Unsupported dialect: {self._dialect}")
```

**Usage**:
```text
# At application startup
adapter = SQLiteAdapter(database_path)
factory = RepositoryFactory(adapter, DatabaseDialect.SQLITE)
repository = factory.get_event_log_repository()

# Pass to presenters/services
comm_presenter = CommunicationPresenter(repository)
```

**Design Note**: Even with one dialect today, the factory is still valuable because it centralizes construction and keeps future backend growth from leaking into higher layers.

**Current SQLite construction path**:
```text
adapter = SQLiteAdapter(database_path)
repository = EventLogRepository(adapter)
```

## Backend and Dialect Considerations

### Current Backend
- SQLite is the currently supported backend
- The adapter/repository split should still be treated as backend-agnostic architecture, not SQLite-only architecture

### Connection Management
- File-based and in-memory databases are both valid runtime modes
- One connection per adapter instance is sufficient for the current single-user local application
- Connection lifecycle belongs to the adapter layer

### Transactions
- Manual transaction control is required for multi-step operations
- Repositories delegate transaction handling to the adapter
- Typical method names: `begin_transaction()`, `commit_transaction()`, `rollback_transaction()`
- Transactions are especially important for grouped writes, status transitions, and test isolation

### Physical Storage Representation
- Exact storage representation for booleans, datetimes, JSON-like structures, and similar values is dialect dependent
- Those choices belong to the concrete dialect design, not to the general architecture contract
- Repositories and adapters must cooperate so domain models remain stable even if physical storage differs by backend

**Current policy**: document exact SQLite type mappings in `ai_instructions/design/db_design.md`, not here.

## Schema

**See**: `ai_instructions/design/db_design.md` for complete schema definitions.

**Architecture note**: schema ownership is dialect specific. General architecture defines who is responsible for initialization and access boundaries; exact table definitions, column types, and storage formats belong in design documentation.

### Main Entity Tables
- `communication_entries` - Communications, messages, orders
- `event_entries` - Events, incidents, observations
- `personnel_entries` - Personnel tracking with historical status
- `structured_reports` - 7S, 9-liner, etc. (foreign key to `event_entries`)

### Configuration Tables
- `communication_systems` - Top-level communication ways/systems such as RA180, Motorola, Rakel, Kurir
- `communication_options` - Recursive configured child options beneath each top-level system
- `communication_qualifiers_config` - Top-level qualifier definitions/behavior per system
- `report_templates` - 7S template, 9-liner template, etc.
- `categories` - Event categories
- `priorities` or equivalent runtime-source table - Valid event priorities if priority configuration is database-backed
- `settings` - Repository/runtime settings and migration metadata
- `user_preferences` - Last operator, column configs, etc.

### Attachment Table
- `file_attachments` - Generic attachments for any entry type, with Phase 1 attachment content stored inside the encrypted database boundary rather than as plaintext filesystem files

### Indexes
- Chronological queries: `event_time`, `logged_time`
- Filtering: `operator`, `priority`, `category`, `communication_system`
- Personnel queries: `who`, `active`, `last_contact_time`, `alarm_enabled`
- Relationships: `parent_event_id`, `communication_system_id`, `parent_option_id`

## Repository Implementation Notes

### Responsibility Split

#### Adapter Owns
- Connection lifecycle
- Schema initialization
- SQL execution primitives (`execute`, `fetch`, `fetchone`)
- Transaction primitives
- Backend-specific error handling

#### Repository Owns
- CRUD workflows
- Query construction
- Row-to-entity mapping
- Filter/search behavior
- Repository-level business rules

#### Deferred Split Strategy
- Keep one public repository now
- Extract communication/event/personnel logic into separate repository files when size or test scope becomes painful
- Only expose multiple public repositories later if the application actually benefits from that split

### Business Rules Enforced at Repository Layer

#### Edited Flag Grace Period (Communication/Event/Personnel Entries)
**Rule**: The `edited` flag is only set to `1` if an update occurs more than the configured grace period after `logged_time`.

**Configuration**:
- Stored in `settings.key = "edited_flag_grace_period_seconds"`
- Value stored in seconds for easier tuning
- Default value: `300`

**Rationale**: During active operations (for example combat), operators often:
1. Rapidly log messages during actual radio calls
2. Immediately fix typos and add details within minutes
3. That immediate cleanup is part of the original logging moment, not a post-event edit

**Implementation**: When updating entries:
```text
time_since_logged = current_time - entry.logged_time
grace_period_seconds = repository_setting("edited_flag_grace_period_seconds", default=300)
if time_since_logged > timedelta(seconds=grace_period_seconds):
    edited = 1
else:
    edited = entry.edited
```

**Benefit**: Filtering by `edited = 1` shows only entries modified after the initial event period, reducing false positives from rapid typo fixes.

**Applies to**:
- `communication_entries.edited`
- `event_entries.edited`
- `personnel_entries.edited`
- `structured_reports.edited`

### Row-to-Entity Mapping

**Pattern**: Repository-private helper methods convert DB rows to domain entities.

```text
class EventLogRepository(BaseRepository):
    def _row_to_communication_entry(self, row: dict) -> CommunicationEntry:
        return CommunicationEntry(
            id=row["id"],
            message_content=row["message_content"],
            from_field=row["from_field"],
            communication_system=row["communication_system"],
            communication_path=json.loads(row["communication_path"]) if row["communication_path"] else None,
            communication_qualifiers=json.loads(row["communication_qualifiers"]) if row["communication_qualifiers"] else None,
            event_time=datetime.fromisoformat(row["event_time"]) if row["event_time"] else None,
        )
```

**Rationale**: Isolates DB format from domain model and handles type conversions.

### Query Builders

**Pattern**: Build SQL queries dynamically based on filter dictionaries.

```text
def get_all_communication_entries(self, filters: dict | None = None) -> list[CommunicationEntry]:
    query = "SELECT * FROM communication_entries WHERE 1=1"
    params = []

    if filters:
        if "operator" in filters:
            query += " AND operator = ?"
            params.append(filters["operator"])
        if "communication_system" in filters:
            query += " AND communication_system = ?"
            params.append(filters["communication_system"])

    query += " ORDER BY event_time DESC"
    rows = self._adapter.fetch(query, tuple(params))
    return [self._row_to_communication_entry(row) for row in rows]
```

**Rationale**: Flexible filtering without explosion of methods.

### Batch Operations (If Needed)

**Pattern**: Accept lists of entities for bulk insert/update.

**Use case**: Loading seed data, importing historical logs.

**Implementation**: Use adapter-level bulk execution support when it becomes necessary.

## Testing Strategy

### In-Memory Database for All Tests
- Use `:memory:` SQLite for all tests
- Fast, isolated, no file system pollution
- Create schema fresh for each test

### Fixtures
```text
@pytest.fixture
def repository():
    adapter = SQLiteAdapter(":memory:")
    repo = EventLogRepository(adapter)
    yield repo
    repo.close()

@pytest.fixture
def repository_with_data(repository):
    repository.create_communication_entry(sample_comm_entry())
    repository.create_event_entry(sample_event_entry())
    return repository
```

### No Mocking
- Test against real SQLite when repository behavior depends on actual SQL
- Use adapter/repository boundaries to keep tests focused
- Catches schema mismatches and SQL regressions

### Test Organization
- `tests/unit/db/` - Adapter and repository unit tests
- `tests/integration/db/` - Multi-table transaction tests

## Dependencies
- Core layer domain models
- Current SQLite implementation depends on `sqlite3` from the standard library
- Serialization/conversion helpers depend on standard-library modules as needed by the concrete dialect implementation

## Migration Strategy

**See**: `ai_instructions/design/db_design.md` for complete migration architecture.

**Summary**:
- Initial schema: `schema/sqlite/initial_schema.sql`
- Migrations: `migrations/NNN_description/sqlite.sql`
- Adapter method: `initialize_schema()` runs initial schema or applies migrations

---

**Related**:
- Human version: `docs/architecture/root_architecture.md`
- Core architecture: `ai_instructions/architecture/core_architecture.md`
- Database design: `ai_instructions/design/db_design.md`


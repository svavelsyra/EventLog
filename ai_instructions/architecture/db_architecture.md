# Database Architecture (AI)

**Layer**: Data Access  
**Last Updated**: 2026-04-25 (Session 015 - Added edited flag grace period business rule)

## Overview
Database layer provides data persistence using SQLite3. Implements Adapter and Repository patterns.

**Architecture Decision**: Separate repository methods (or repositories) for three specialized entity types.

**Reasoning**: Different entities have different query patterns and relationships. Specialized methods provide cleaner API and type safety.

## Patterns

### Adapter Pattern
Abstract base class defines ALL database operations as interfaces.

**Location**: `src/db/adapters/`

**Purpose**:
- Enable swapping database implementations
- Facilitate testing with in-memory databases
- Decouple core logic from database specifics

**Key Classes**:
- `EventLogAdapter` - Abstract base class with all DB methods for all entity types

**Design Note**: Single adapter with methods for all entity types (not three separate adapters). Simplifies factory pattern and connection management.

### Repository Pattern
Concrete implementations of adapters.

**Location**: `src/db/repositories/`

**Purpose**:
- Hide database-specific query details
- Provide collection-like interface
- Handle connection management
- Translate between DB rows and domain entities

**Key Classes**:
- `SQLiteEventLogRepository` - SQLite implementation for all entity types

**Design Note**: Single repository implementation with organized methods by entity type.

## Repository Interface Organization

### Adapter Interface Structure

```python
class EventLogAdapter(ABC):
    # ========== CommunicationEntry Operations ==========
    @abstractmethod
    def create_communication_entry(entry: CommunicationEntry) -> int
    
    @abstractmethod
    def get_communication_entry(id: int) -> CommunicationEntry | None
    
    @abstractmethod
    def get_all_communication_entries(filters: dict | None = None) -> list[CommunicationEntry]
    
    @abstractmethod
    def update_communication_entry(entry: CommunicationEntry) -> bool
    
    @abstractmethod
    def delete_communication_entry(id: int) -> bool
    
    @abstractmethod
    def search_communication_entries(search_text: str, filters: dict | None = None) -> list[CommunicationEntry]
    
    # ========== EventEntry Operations ==========
    @abstractmethod
    def create_event_entry(entry: EventEntry) -> int
    
    @abstractmethod
    def get_event_entry(id: int) -> EventEntry | None
    
    @abstractmethod
    def get_all_event_entries(filters: dict | None = None) -> list[EventEntry]
    
    @abstractmethod
    def update_event_entry(entry: EventEntry) -> bool
    
    @abstractmethod
    def delete_event_entry(id: int) -> bool
    
    @abstractmethod
    def search_event_entries(search_text: str, filters: dict | None = None) -> list[EventEntry]
    
    # ========== PersonnelEntry Operations ==========
    @abstractmethod
    def create_personnel_entry(entry: PersonnelEntry) -> int
    
    @abstractmethod
    def get_personnel_entry(id: int) -> PersonnelEntry | None
    
    @abstractmethod
    def get_all_personnel_entries(filters: dict | None = None) -> list[PersonnelEntry]
    
    @abstractmethod
    def update_personnel_entry(entry: PersonnelEntry) -> bool
    
    @abstractmethod
    def delete_personnel_entry(id: int) -> bool
    
    @abstractmethod
    def get_active_personnel_entries() -> list[PersonnelEntry]  # Convenience method
    
    @abstractmethod
    def get_personnel_history(who: str) -> list[PersonnelEntry]  # All entries for specific "who"
    
    @abstractmethod
    def get_overdue_alarms() -> list[PersonnelEntry]  # Alarm enabled, past due, not triggered
    
    # ========== StructuredReport Operations ==========
    @abstractmethod
    def create_structured_report(report: StructuredReport) -> int
    
    @abstractmethod
    def get_structured_report(id: int) -> StructuredReport | None
    
    @abstractmethod
    def get_reports_for_event(event_id: int) -> list[StructuredReport]
    
    @abstractmethod
    def update_structured_report(report: StructuredReport) -> bool
    
    @abstractmethod
    def delete_structured_report(id: int) -> bool
    
    # ========== Configuration Operations ==========
    @abstractmethod
    def get_communication_systems() -> list[CommunicationSystem]
    
    @abstractmethod
    def get_system_capabilities(system_id: int) -> list[SystemCapability]
    
    @abstractmethod
    def get_channel_designations(system_id: int) -> list[ChannelDesignation]
    
    @abstractmethod
    def get_report_templates() -> list[ReportTemplate]
    
    @abstractmethod
    def get_categories() -> list[str]
    
    @abstractmethod
    def get_priorities() -> list[str]
    
    # ========== User Preferences ==========
    @abstractmethod
    def get_preference(key: str) -> str | None
    
    @abstractmethod
    def set_preference(key: str, value: str) -> None
    
    # ========== File Attachments ==========
    @abstractmethod
    def create_file_attachment(attachment: FileAttachment) -> int
    
    @abstractmethod
    def get_attachments_for_entry(parent_table: str, parent_id: int) -> list[FileAttachment]
    
    @abstractmethod
    def delete_file_attachment(id: int) -> bool
    
    # ========== Transaction Management ==========
    @abstractmethod
    def begin_transaction() -> None
    
    @abstractmethod
    def commit() -> None
    
    @abstractmethod
    def rollback() -> None
    
    @abstractmethod
    def close() -> None
```

**Rationale**: 
- Clear grouping by entity type (easy to find methods)
- Single connection/transaction context for all operations
- Specialized methods with type hints (better IDE support)
- Convenience methods for common queries (active personnel, overdue alarms)

## Factory Pattern
**Pattern**: Factory creates repository instance based on configuration.

```python
class RepositoryFactory:
    @staticmethod
    def get_repository(config: AppConfig) -> EventLogAdapter:
        db_type = config.get('db_type', 'sqlite')
        
        if db_type == 'sqlite':
            db_path = config.get('db_file_path', 'eventlog.db')
            return SQLiteEventLogRepository(db_path)
        elif db_type == 'sqlite_memory':
            return SQLiteEventLogRepository(':memory:')
        else:
            raise ValueError(f"Unsupported database type: {db_type}")
```

**Usage**:
```python
# At application startup
config = load_config()
repository = RepositoryFactory.get_repository(config)

# Pass to presenters
comm_presenter = CommunicationPresenter(repository)
```

## Database: SQLite3

### Connection Management
- File-based: `eventlog.db` in app directory (or user-configured path)
- In-memory: `:memory:` for tests
- Connection pooling not needed (single user, local, single-threaded)
- One connection per repository instance

### Transactions
- Manual transaction control for multi-step operations
- `begin_transaction()`, `commit()`, `rollback()`
- Used for:
  - Personnel status updates (create new + mark old inactive)
  - Bulk operations
  - Test isolation

### JSON Storage
- System capabilities stored as JSON TEXT
- Report data stored as JSON TEXT
- Parse with `json.loads()` when loading from DB
- Serialize with `json.dumps()` when saving to DB

### DateTime Storage
- Store as ISO 8601 TEXT format: "2026-04-19T14:30:00"
- Python: `datetime.isoformat()` and `datetime.fromisoformat()`
- Sortable as text in SQL queries

### Boolean Storage
- Store as INTEGER (0 = false, 1 = true)
- Python: Convert with `bool(value)` and `int(value)`

## Schema

**See**: `ai_instructions/design/db_design.md` for complete schema definitions.

### Main Entity Tables
- `communication_entries` - Communications, messages, orders
- `event_entries` - Events, incidents, observations
- `personnel_entries` - Personnel tracking with historical status
- `structured_reports` - 7S, 9-liner, etc. (foreign key to event_entries)

### Configuration Tables
- `communication_systems` - RA180, RA146, email systems, etc.
- `system_capabilities_config` - What capabilities each system supports
- `channel_designations` - Channel numbers and human-readable names per system
- `report_templates` - 7S template, 9-liner template, etc.
- `categories` - Event categories
- `user_preferences` - Last operator, column configs, etc.

### Attachment Table
- `file_attachments` - Generic attachments for any entry type

### Indexes
- Chronological queries: `event_time`, `logged_time`
- Filtering: `operator`, `priority`, `category`, `communication_system`, `method_type`
- Personnel queries: `who`, `active`, `last_contact_time`, `alarm_enabled`
- Relationships: `parent_event_id`, `communication_system_id`

## Repository Implementation Notes

### Business Rules Enforced at Repository Layer

#### Edited Flag Grace Period (Communication/Event/Personnel Entries)
**Rule**: The `edited` flag is only set to 1 if an update occurs MORE than 5 minutes after `logged_time`.

**Rationale**: During active operations (e.g., combat), operators often:
1. Rapidly log messages during actual radio calls
2. Immediately fix typos and add details (within minutes)
3. This immediate cleanup is part of the "logging event," not a "post-event edit"

**Implementation**: When updating entries:
```python
# Pseudo-logic in update methods
time_since_logged = current_time - entry.logged_time
if time_since_logged > timedelta(minutes=5):
    edited = 1  # Set edited flag
else:
    edited = entry.edited  # Preserve existing value (don't force to 1)
```

**Benefit**: Filtering by `edited=1` flag shows only entries modified after the initial event period, reducing false positives from rapid typo fixes.

**Applies to**: 
- `communication_entries.edited`
- `event_entries.edited`
- `personnel_entries.edited`
- `structured_reports.edited`

### Row-to-Entity Mapping

**Pattern**: Private helper methods convert DB rows to domain entities.

```python
class SQLiteEventLogRepository(EventLogAdapter):
    def _row_to_communication_entry(self, row: dict) -> CommunicationEntry:
        return CommunicationEntry(
            id=row['id'],
            message_content=row['message_content'],
            from_field=row['from_field'],
            # ... parse JSON fields, convert datetimes, etc.
            system_capabilities=json.loads(row['system_capabilities']) if row['system_capabilities'] else None,
            event_time=datetime.fromisoformat(row['event_time']) if row['event_time'] else None,
        )
```

**Rationale**: Isolates DB format from domain model, handles type conversions.

### Query Builders (If Needed)

**Pattern**: Build SQL queries dynamically based on filter dictionaries.

```python
def get_all_communication_entries(self, filters: dict | None = None) -> list[CommunicationEntry]:
    query = "SELECT * FROM communication_entries WHERE 1=1"
    params = []
    
    if filters:
        if 'operator' in filters:
            query += " AND operator = ?"
            params.append(filters['operator'])
        if 'method_type' in filters:
            query += " AND method_type = ?"
            params.append(filters['method_type'])
        # ... etc.
    
    query += " ORDER BY event_time DESC"
    rows = self.cursor.execute(query, params).fetchall()
    return [self._row_to_communication_entry(row) for row in rows]
```

**Rationale**: Flexible filtering without explosion of methods.

### Batch Operations (If Needed)

**Pattern**: Accept lists of entities for bulk insert/update.

**Use case**: Loading seed data, importing historical logs.

**Implementation**: Use `executemany()` for performance.

## Testing Strategy

### In-Memory Database for All Tests
- Use `:memory:` SQLite for all tests
- Fast, isolated, no file system pollution
- Create schema fresh for each test

### Fixtures
```python
@pytest.fixture
def repository():
    repo = SQLiteEventLogRepository(':memory:')
    repo.initialize_schema()  # Create tables
    yield repo
    repo.close()

@pytest.fixture
def repository_with_data(repository):
    # Add seed data
    repository.create_communication_entry(sample_comm_entry())
    repository.create_event_entry(sample_event_entry())
    # ... etc.
    return repository
```

### No Mocking
- Test against real SQLite (fast enough)
- Validates actual SQL queries work
- Catches schema mismatches

### Test Organization
- `tests/unit/db/` - Repository method tests
- `tests/integration/db/` - Multi-table transaction tests

## Dependencies
- `sqlite3` (stdlib)
- `json` (stdlib)
- `datetime` (stdlib)
- Core layer (domain models: CommunicationEntry, EventEntry, PersonnelEntry, StructuredReport)

## Migration Strategy

**See**: `ai_instructions/design/db_design.md` for complete migration architecture.

**Summary**:
- Initial schema: `schema/sqlite/initial_schema.sql`
- Migrations: `migrations/NNN_description/sqlite.sql`
- Repository method: `initialize_schema()` runs initial schema or applies migrations

---

**Related**:
- Human version: `docs/architecture/root_architecture.md`
- Core architecture: `ai_instructions/architecture/core_architecture.md`
- Database design: `ai_instructions/design/db_design.md`


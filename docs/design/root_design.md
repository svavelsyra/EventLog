# EventLog - Root Design Document

**Project**: Platoon Event Logger  
**Version**: 1.0.0
**Last Updated**: 2026-04-28  

## Domain Model

### Core Entry Types

The application is no longer designed around one generic message-log entry. The root design now assumes separate entry types for the main operational use cases:

- `CommunicationEntry` - radio messages, phone calls, written orders, and similar communications
- `EventEntry` - operational events, incidents, observations, and status changes
- `PersonnelEntry` - personnel/group tracking, location, and check-in management

#### Required Fields
1. **Primary content field** (free text field)
   - The actual message, event description, or status/notes field depending on entry type
   - Type: String (unlimited length)

2. **From** (sender/source)
   - Relevant for communication entries
   - Type: String

3. **To** (recipient/destination)
   - Relevant for communication entries
   - Type: String

4. **Event Time** (when it happened)
   - Actual time of the communication or event when that field is applicable
   - Type: DateTime

5. **Logged Time** (when it was logged)
   - When the operator entered it into the system
   - Type: DateTime (auto-populated)

6. **Communication Method** (how it was sent/received)
   - Radio, phone, in-person, written order, etc. for communication entries
   - Type: String (or enumeration)

7. **Operator** (who logged it)
   - The operator who made the log entry
   - Type: String

8. **Confirmed** (was it acknowledged?)
   - Whether the recipient confirmed receipt
   - Type: Boolean

#### Additional Fields
- ID (primary key)
- Type-specific metadata as needed
- Edited-flag behavior should use a configurable grace period stored in the database `settings` table (default: 300 seconds)
- Event entries may include `priority`, `category`, and `whom`
- Personnel entries may include `status`, `location`, `active`, and check-in alarm fields

## User Interface Design

### Main Window Layout
- **Message log table/list** - displays all entries
- **Entry form** - for creating new log entries
- **Filter/search** - for finding specific entries
- **Export functionality** - for reporting (future)

### Entry Form Fields
All fields from the MessageLogEntry entity, with:
- Auto-populated logged time
- Date/time pickers for event time
- Dropdown for communication method
- Checkbox for confirmed status

## Database Design

### Tables
- **communication_entries** - communication log entries
- **event_entries** - operational event log entries
- **personnel_entries** - personnel status/history entries
- **structured_reports** - report templates attached to events
- **communication_systems** / **channel_designations** / **system_capabilities_config** - communication configuration
- **report_templates** / **categories** / **user_preferences** - runtime configuration and user-managed metadata
- **settings** - low-level repository settings such as the edited-flag grace period in seconds

### Persistence Layer Design

#### Database Adapter Interface
Low-level database adapter must provide operations such as:
- `initialize_schema()`
- `execute()`
- `fetch()`
- `fetchone()`
- `begin_transaction()`, `commit_transaction()`, `rollback_transaction()`
- `close()`

#### Repository Layer
Application-facing repositories provide CRUD and query operations such as:
- create/get/list/update/delete entry operations per entry type
- search/filter functionality
- row-to-entity mapping
- repository business rules such as the edited-flag grace period

#### Repository Factory
- `RepositoryFactory` constructs repositories from adapter + dialect context
- One concrete repository is enough for now
- SQLite-specific repositories live under `src/db/repositories/sqlite/`

## Testing Strategy

### Test Database
- Use SQLite `:memory:` for tests
- Create fixtures for common test scenarios
- Use transactions or function scoped fixtures for test isolation
- Maintain a script to generate a file-based test database for manual testing.

### Test Coverage Areas
1. **Core business logic** - validation, calculations
2. **Database operations** - CRUD operations, queries
3. **Presenter logic** - user interaction handling
4. **Integration scenarios** - end-to-end workflows

## Further Design Documentation
- Detailed split-out human design documents are not yet created.
- This root document is currently the human-facing design summary.
- The AI-maintained database design detail currently lives in `ai_instructions/design/db_design.md` until the human design docs are split further.

## Open Questions
- Should communication methods be enumerated or free text?
  Decision: Enumerated with option for "Other" and free text if "Other" is selected.
- Do we need operator management (list of operators)?
  Decision: No, but maybe keep last operator in the field with possibility for operator to change when logging.
- Should we support message priorities or categories?
  Decision: Yes both priorities as Enumeration and categories as tags (tags selected from user managed list)
- Archive/export functionality requirements?
  Decision: Export as CSV, database backup and restore, PDF export.

## Next Steps
1. Further refinement of Architecture and Design
2. Create detailed design documents for data model, GUI, and database schema
3. User stories and acceptance criteria definition.
4. Create implementation plan.

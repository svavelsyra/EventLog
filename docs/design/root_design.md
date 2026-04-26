# MessageLog - Root Design Document

**Project**: Radio Communication Message Logger  
**Version**: 1.0.0
**Last Updated**: 2026-04-17  

## Domain Model

### Core Entity: MessageLogEntry

A message log entry represents a single event in radio communication operations.

#### Required Fields
1. **Message Content** (free text field)
   - The actual message or event description
   - Type: String (unlimited length)

2. **From** (sender/source)
   - Who sent the message or initiated the event
   - Type: String

3. **To** (recipient/destination)
   - Who received the message or was affected by the event
   - Type: String

4. **Event Time** (when it happened)
   - Actual time of the event/message
   - Type: DateTime

5. **Logged Time** (when it was logged)
   - When the operator entered it into the system
   - Type: DateTime (auto-populated)

6. **Communication Method** (how it was sent/received)
   - Radio, phone, in-person, written order, etc.
   - Type: String (or enumeration)

7. **Operator** (who logged it)
   - The radio operator who made the log entry
   - Type: String

8. **Confirmed** (was it acknowledged?)
   - Whether the recipient confirmed receipt
   - Type: Boolean

#### Additional Fields (TBD)
- ID (primary key)
- Additional metadata as needed

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
- **event_log_entries** - main table for log entries
- Additional tables as needed (operators, communication methods, etc.)

### Database Adapter Interface
Abstract base class must provide:
- `create_entry()` - Add new log entry
- `get_entry(id)` - Retrieve single entry
- `get_all_entries()` - Retrieve all entries
- `update_entry()` - Modify existing entry
- `delete_entry()` - Remove entry
- `search_entries()` - Filter/search functionality
- `begin_transaction()`, `commit()`, `rollback()` - Transaction support

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
- **Data Model Design**: See `docs/design/data_model_design.md` (to be created)
- **GUI Design**: See `docs/design/gui_design.md` (to be created)
- **Database Schema**: See `docs/design/database_schema.md` (to be created)

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

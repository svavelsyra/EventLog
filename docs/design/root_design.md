# EventLog - Root Design Document

**Project**: Platoon Event Logger  
**Version**: 1.0.0
**Last Updated**: 2026-04-30  

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

### Startup and Bootstrap UX
- `config.ini` is a convenience layer only. It may remember UI state, creation defaults, and last-used bootstrap hints, but it is not security authority.
- For bootstrap/security-related config, `[DEFAULT]` is the shared inherited fallback layer. Ordinary sections still exist alongside it; technology sections hold remembered target details and may override shared values when needed.
- Remembered startup hints for an existing database target must stay separate from create-time admin policy inputs for new databases. Example: whether the last-used database needed a key file is bootstrap memory, while whether new databases must use a key file is a creation-time policy/default.
- Startup must always reach a usable recovery-capable create/select flow, even when remembered bootstrap values are missing or malformed.
- Startup is technology-first: the user resolves or selects the database technology before backend-specific input fields are finalized.
- After a technology is selected, the startup UI becomes dynamic and shows only the fields relevant for that technology.
- In the current SQLite realization, create versus open is inferred from whether the selected target already exists, so the generic startup shell should not expose a separate global new/load selector.
- Remembered values may prefill the startup UI, but the user must be able to change them or ignore them.
- Current SQLite/file-path/key-file behavior is a Phase 1 realization of this UX, not the universal rule for all future backends.
- Emergency `Nollställ` in the startup/unlock path is immediate; it must not require a secondary confirmation dialog or typed confirmation phrase.

### Security Helper and Ownership Design
- Shared security code should stay small, explicit, and auditable.
- Shared security helpers are for cross-technology concerns only: generic key-derivation primitives, shared security exceptions, generic credential/file validation, and secure-deletion utilities.
- Backend-specific security behavior should be owned by the backend that needs it. If SQLite/SQLCipher requires a special salt contract, key formatting rule, metadata lookup, or unlock verification step, that belongs with the SQLite implementation rather than in the shared helper layer.
- Startup/presenter code may collect secrets and surface generic user-facing failures, but it should call into security and backend-owned logic rather than containing backend-specific cryptographic rules itself.

### Password and Credential Policy
- Password policy is intentionally minimal.
- The administrator-configured minimum password length is a policy input, not a hard-coded universal rule baked into every low-level helper.
- The design does not require character-composition rules such as uppercase, digits, or symbols.
- Low-level helpers should reject structurally invalid inputs and clearly abusive bounds, but they should not silently enforce narrow recommended ranges where the caller or administrator is expected to own the policy decision.
- Generic key derivation should remain portable across future backends by accepting caller-supplied policy inputs such as salt, iterations, and output-length expectations where appropriate; backend-owned wrappers can then apply technology-specific rules on top.

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
- **file_attachments** - generic attachments whose content is stored inside the encrypted database in Phase 1
- **structured_reports** - report templates attached to events
- **communication_systems** / **channel_designations** / **system_capabilities_config** - communication configuration
- **report_templates** / **categories** / **user_preferences** - runtime configuration and user-managed metadata
- **settings** - low-level repository settings such as the edited-flag grace period in seconds

### Attachment Storage Policy
- Phase 1 attachment content is stored inside the encrypted database together with its metadata.
- Plaintext filesystem attachment directories are not part of the approved secure design.
- Future support for large attachments is optional future work and, if ever approved, must use separately encrypted external storage rather than normal readable files.

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

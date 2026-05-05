# Database Design (AI)

**Database Schema & Data Access**  
**Last Updated**: 2026-05-05 (Session 081 - Synced communication-config storage model to refined Epic 003 design)

## Database Technology

### Configurable Backend
User selects database technology on first launch (stored in `config.ini`).

**Default**: SQLite3 (file-based or in-memory)

**Future options**: Other databases via the same `DatabaseAdapter` + `RepositoryFactory` architecture

### Persistence Module Layout

Current active structure for the persistence layer:

```text
src/db/
├── database_adapter.py
├── sqlite_adapter.py
├── repositories/
│   ├── base_repository.py
│   ├── repository_factory.py
│   └── sqlite/
│       ├── event_log_repository.py
│       ├── communication_repository.py
│       ├── event_repository.py
│       └── personnel_repository.py
└── schema/
    ├── schema_executor.py
    └── sqlite/
        └── initial_schema.sql
```

**Design responsibilities**:
- `database_adapter.py` defines low-level database operations and database-specific exceptions
- `sqlite_adapter.py` handles SQLite connection lifecycle, schema initialization, execution, fetch helpers, and transaction primitives
- `repositories/base_repository.py` defines the generic repository base class and stays dialect-agnostic
- `repositories/repository_factory.py` constructs repositories from adapter + dialect context
- `repositories/sqlite/event_log_repository.py` is the sole active concrete SQLite repository in runtime use today
- `repositories/sqlite/` remains the location for SQLite-specific repository implementations and future internal split points

**Current runtime note**:
- `RepositoryFactory` currently creates `SQLiteAdapter(database_path)` and returns `EventLogRepository(adapter)`
- The earlier legacy top-level SQLite repository compatibility file has been removed

### Encryption Support
- Optional database encryption
- Encryption handled at adapter level (transparent to Core/GUI)
- User prompted for password on launch if encrypted database selected
- Different adapters may use different encryption solutions:
  - SQLite → SQLCipher (encrypted SQLite variant)
  - Other databases → Their native encryption mechanisms

## Configuration (config.ini)

Application uses ConfigParser with `config.ini` for global settings.

### Database Settings
- `db_type` - Database technology / dialect selector (e.g., "sqlite", future encrypted or other backend variants)
- technology-specific target field such as `[sqlite].database_path` - Path/target for the selected backend
- `db_in_memory` - Use in-memory database (for SQLite, testing)
- Future: `db_url`, `db_username`, etc. for remote databases

### Other Settings
- Logging configuration
- Application preferences

## Database: SQLite3

File-based: `eventlog.db` in application directory (or user-configured path)
In-memory for tests: `:memory:`

This document records the current SQLite dialect design. The adapter/repository architecture is defined in `ai_instructions/architecture/db_architecture.md`; exact storage formats and schema details are defined here.

## Tables

**Design Decision**: Three specialized tables instead of one generic table.

**Reasoning**: 
- Different information types have different fields
- Cleaner schema (no unused nullable fields)
- Better data integrity and type-specific constraints
- Easier querying and indexing

### communication_entries
Stores radio messages, phone calls, written orders, and other communications.

**Fields**:
- `id` INTEGER PRIMARY KEY AUTOINCREMENT - Unique identifier
- `message_content` TEXT NOT NULL - The actual message (max 5000 chars, enforced by app and db(?))
- `from_field` TEXT NULL - Sender/source (optional)
- `to_field` TEXT NULL - Recipient/destination (optional)
- `event_time` TEXT NULL - When communication occurred (ISO 8601 format, optional - defaults to logged_time)
- `logged_time` TEXT NOT NULL - When entered into system (ISO 8601 format, auto)
- `operator` TEXT NOT NULL - Who logged it (person at terminal)
- `confirmed` INTEGER NOT NULL DEFAULT 0 - Receipt acknowledged (0=false, 1=true)
- `edited` INTEGER NOT NULL DEFAULT 0 - Entry was modified after save (0=false, 1=true)
  - **Business Rule**: Only set to 1 if update occurs more than the configured grace period after `logged_time`
  - **Configuration**: `settings.edited_flag_grace_period_seconds` (default `300`)
  - **Rationale**: Allows grace period for immediate typo fixes during active logging while keeping the threshold adjustable
  - **Implementation**: Repository layer reads the setting in seconds and checks the time delta before setting the flag

**Communication Selection Snapshot Fields**:
- `communication_system` TEXT NULL - Selected top-level communication way/system snapshot (e.g., "RA180", "Motorola", "Courier")
- `communication_path` TEXT NULL - JSON array describing the selected recursive option path beneath the top-level system
  - Example: `[ {"value": "5", "label": "Company Net"} ]`
  - Deeper future example: `[ {"value": "5", "label": "Company Net"}, {"value": "DATA", "label": "Data Route"} ]`
- `communication_qualifiers` TEXT NULL - JSON dict with chosen top-level qualifier values (e.g., `{"encrypted": true, "data": true}`)

**Recursive structure note**:
- The underlying configuration model may be recursive / tree-shaped beneath the top-level communication system.
- The current operator-facing UI may still stop at three visible levels for practical use, but that is a UI/runtime limit rather than a storage-limit assumption.
- If a future fourth visible level is needed, the recursive storage shape should already support it without redesigning the schema.

**Attachments** (stored as references):
- Handled via separate `file_attachments` and `structured_reports` tables (see below)

**Indexes**:
- `idx_comm_event_time` ON event_time - Chronological queries
- `idx_comm_logged_time` ON logged_time - Recent entries
- `idx_comm_operator` ON operator - Filtering by operator
- `idx_comm_system` ON communication_system - Filtering by system

**Constraints**:
- `message_content` cannot be empty string (CHECK constraint)
- `event_time` cannot be in future (app validation, not DB constraint - allows late logging)
- `communication_path` and `communication_qualifiers` must be valid JSON if present (app validation)
- Selected system/path/qualifier relationship validated by app/core against the configuration tree and qualifier definitions

### event_entries
Stores operational events, incidents, status changes, and observations.

**Fields**:
- `id` INTEGER PRIMARY KEY AUTOINCREMENT - Unique identifier
- `event_description` TEXT NOT NULL - What happened (max 5000 chars, enforced by app)
- `whom` TEXT NULL - Who is involved/affected (optional, free text)
- `event_time` TEXT NULL - When event occurred (ISO 8601 format, optional - defaults to logged_time)
- `logged_time` TEXT NOT NULL - When entered into system (ISO 8601 format, auto)
- `operator` TEXT NOT NULL - Who logged it (person at terminal)
- `priority` TEXT NULL DEFAULT 'Normal' - Priority level ("Low", "Normal", "High", "Critical")
- `category` TEXT NULL - Event category/type (optional)
- `edited` INTEGER NOT NULL DEFAULT 0 - Entry was modified after save (0=false, 1=true)
  - **Business Rule**: Only set to 1 if update occurs more than the configured grace period after `logged_time`
  - **Configuration**: `settings.edited_flag_grace_period_seconds` (default `300`)
  - **Rationale**: Allows grace period for immediate corrections during active logging while keeping the threshold adjustable
  - **Implementation**: Repository layer reads the setting in seconds and checks the time delta before setting the flag

**Attachments** (stored as references):
- Handled via separate `file_attachments` and `structured_reports` tables (see below)

**Indexes**:
- `idx_event_event_time` ON event_time - Chronological queries
- `idx_event_logged_time` ON logged_time - Recent entries
- `idx_event_operator` ON operator - Filtering by operator
- `idx_event_priority` ON priority - Filtering by priority
- `idx_event_category` ON category - Filtering by category

**Constraints**:
- `event_description` cannot be empty string (CHECK constraint)
- `priority` should be from valid list (app validation)

### personnel_entries
Stores personnel and group tracking - status, location, check-in management.

**Fields**:
- `id` INTEGER PRIMARY KEY AUTOINCREMENT - Unique identifier
- `who` TEXT NOT NULL - Person/group callsign (free text with autocomplete)
- `status` TEXT NULL - Current status description (optional, free text)
- `location` TEXT NULL - Where they are (optional, free text)
- `last_contact_time` TEXT NULL - When we last heard from them (ISO 8601, defaults to logged_time)
- `mission_notes` TEXT NULL - Mission details, notes (max 5000 chars, enforced by app)
- `logged_time` TEXT NOT NULL - When this status was created (ISO 8601 format, auto)
- `operator` TEXT NOT NULL - Who logged it (person at terminal)
- `edited` INTEGER NOT NULL DEFAULT 0 - Entry was modified after save (0=false, 1=true)
  - **Business Rule**: Only set to 1 if update occurs more than the configured grace period after `logged_time`
  - **Configuration**: `settings.edited_flag_grace_period_seconds` (default `300`)
  - **Rationale**: Allows grace period for immediate status corrections during active logging while keeping the threshold adjustable
  - **Implementation**: Repository layer reads the setting in seconds and checks the time delta before setting the flag

**Historical Tracking Fields**:
- `active` INTEGER NOT NULL DEFAULT 1 - Current status (1) or historical (0)
- `supersedes` TEXT NULL - Comma-separated entry IDs this entry replaces

**Check-in Alarm Fields**:
- `alarm_enabled` INTEGER NOT NULL DEFAULT 0 - Reminder set (0=false, 1=true)
- `expected_checkin_time` TEXT NULL - When to expect check-in (ISO 8601, only if alarm_enabled=1)
- `alarm_triggered` INTEGER NOT NULL DEFAULT 0 - Alarm acknowledged (0=false, 1=true)

**Indexes**:
- `idx_personnel_who` ON who - Filtering by person/group
- `idx_personnel_active` ON active - Quick filter for active entries
- `idx_personnel_logged_time` ON logged_time - Recent entries
- `idx_personnel_last_contact` ON last_contact_time - Sorting by last contact
- `idx_personnel_alarm` ON (alarm_enabled, expected_checkin_time) - Finding overdue alarms

**Constraints**:
- `who` cannot be empty string (CHECK constraint)
- If `alarm_enabled` = 1, then `expected_checkin_time` must not be NULL (CHECK constraint)
- Only one active=1 entry per unique "who" value (soft constraint, app guidance)

### structured_reports
Stores structured military report templates (7S, 9-liner, etc.) attached to event_entries.

**Fields**:
- `id` INTEGER PRIMARY KEY AUTOINCREMENT - Unique identifier
- `parent_event_id` INTEGER NOT NULL - Foreign key to event_entries.id
- `report_type` TEXT NOT NULL - Type of report ("7S", "9-liner", etc.)
- `report_data` TEXT NOT NULL - JSON dict with structured fields
- `auto_summary` TEXT NOT NULL - Generated summary for table display
- `logged_time` TEXT NOT NULL - When report was created (ISO 8601 format, auto)
- `operator` TEXT NOT NULL - Who created this report
- `edited` INTEGER NOT NULL DEFAULT 0 - Report modified after save (0=false, 1=true)
  - **Business Rule**: Only set to 1 if update occurs more than the configured grace period after `logged_time`
  - **Configuration**: `settings.edited_flag_grace_period_seconds` (default `300`)
  - **Rationale**: Allows grace period for immediate corrections during active logging while keeping the threshold adjustable
  - **Implementation**: Repository layer reads the setting in seconds and checks the time delta before setting the flag

**Indexes**:
- `idx_report_parent_event` ON parent_event_id - Find reports for an event
- `idx_report_type` ON report_type - Filter by report type

**Constraints**:
- FOREIGN KEY (parent_event_id) REFERENCES event_entries(id) ON DELETE CASCADE
- `report_data` must be valid JSON (app validation)
- `report_type` must be from configured templates (app validation)

### communication_systems
Stores configured communication ways/systems and their top-level shared behavior.

**Child linkage rule**:
- A system row does **not** store a denormalized list of child IDs.
- Its immediate child options are the `communication_options` rows where:
  - `communication_system_id = communication_systems.id`
  - `parent_option_id IS NULL`
- This keeps one source of truth for the tree instead of duplicating child references on the parent.

**Fields**:
- `id` INTEGER PRIMARY KEY AUTOINCREMENT - Unique identifier
- `system_name` TEXT NOT NULL UNIQUE - System/way name (e.g., "RA180", "Motorola", "Rakel", "Courier")
- `system_type` TEXT NOT NULL - Category/type of system (e.g., "Radio System", "Courier", "In Person")
- `child_label` TEXT NULL - Label for the next visible selection level beneath this system (e.g., "Channel")
- `sort_order` INTEGER - Display order in UI
- `is_active` INTEGER NOT NULL DEFAULT 1 - Soft delete flag (0=inactive, 1=active)

**Default data** (Phase 1 - for your unit):
```
system_name="RA180", system_type="Radio System", child_label="Channel"
system_name="Motorola", system_type="Radio System", child_label="Channel"
system_name="Rakel", system_type="Radio System", child_label="Channel"
system_name="Courier", system_type="Courier", child_label=NULL
```

**Indexes**:
- `idx_comm_systems_active` ON is_active - Filter active systems
- `idx_comm_systems_type` ON system_type - Filter by system type
- UNIQUE index on system_name

### communication_options
Stores configured recursive option rows beneath a top-level communication system.

This is the actual data behind the current tiered UI. The first option level under a system may appear as `tier_2` today, and its children may appear as `tier_3`, but the storage itself is recursive so future deeper structures do not require a new schema.

**Fields**:
- `id` INTEGER PRIMARY KEY AUTOINCREMENT - Unique identifier
- `communication_system_id` INTEGER NOT NULL - Foreign key to communication_systems.id
- `option_value` TEXT NOT NULL - Stable stored value / technical identifier (e.g., "5", "A", "DATA")
- `option_label` TEXT NOT NULL - Human-readable label shown to the operator (e.g., "Company Net", "Channel A")
- `parent_option_id` INTEGER NULL - Optional parent option row when this option belongs beneath another option
- `child_label` TEXT NULL - Label to show for the next visible level beneath this option, if children exist
- `sort_order` INTEGER NULL - Display order in UI
- `is_active` INTEGER NOT NULL DEFAULT 1 - Soft delete flag (0=inactive, 1=active)

**Default data** (Phase 1 - for your unit):
- **RA180 root children**: Company Net (Ch 5), Platoon 1 Net (Ch 7), Platoon 2 Net (Ch 9)
- **Motorola root children**: locally meaningful channel selections for close-range group/platoon communication
- **Rakel root children**: selected operational channel set for the simplified first-pass radio use
- **Courier**: no child option rows by default in Phase 1
- Deeper child rows may remain empty in Phase 1 for many systems even though the recursive storage supports them

**Indexes**:
- `idx_comm_option_system` ON communication_system_id - Find options for a system
- `idx_comm_option_parent` ON parent_option_id - Find child options for a parent option
- `idx_comm_option_active` ON is_active - Filter active options
- UNIQUE index on (communication_system_id, option_value, parent_option_id)

**Constraints**:
- FOREIGN KEY (communication_system_id) REFERENCES communication_systems(id) ON DELETE CASCADE
- FOREIGN KEY (parent_option_id) REFERENCES communication_options(id) ON DELETE CASCADE

**Recursive structure note**:
- Top-level systems are stored in `communication_systems`.
- Options beneath a system are stored recursively in `communication_options`.
- A node's direct children are found by querying `communication_options` where `parent_option_id = this_option.id`.
- The current UI may choose to render only the first three visible levels, but repository/core traversal may still treat the structure as a general tree with a runtime `max_recursion_depth` safeguard.

### communication_qualifiers_config
Stores configuration for top-level qualifiers and other simple operator-visible options that belong to a system.

**Fields**:
- `id` INTEGER PRIMARY KEY AUTOINCREMENT - Unique identifier
- `communication_system_id` INTEGER NOT NULL - Foreign key to communication_systems.id
- `qualifier_key` TEXT NOT NULL - Key name in JSON (e.g., "encrypted", "data")
- `label` TEXT NOT NULL - UI label (e.g., "Transmissionslägen")
- `field_type` TEXT NOT NULL - Data type ("enum", "boolean", "text")
- `valid_values` TEXT NULL - JSON array of valid values (for type="enum")
- `default_value` TEXT NULL - Default value (string representation)
- `help_text` TEXT NULL - UI tooltip/help text
- `visibility_mode` TEXT NOT NULL DEFAULT 'editable' - How the option behaves for the operator (`editable`, `forced`, `hidden`)

**Default data** (Phase 1 - key-system qualifiers):
```
communication_system_id=1 (RA180), qualifier_key="encrypted", label="Krypterad", 
  field_type="boolean", valid_values=NULL, default_value="false", visibility_mode="editable"

communication_system_id=1 (RA180), qualifier_key="data", label="Data", 
  field_type="boolean", valid_values=NULL, default_value="false", visibility_mode="editable"

communication_system_id=2 (Motorola), qualifier_key="encrypted", label="Krypterad", 
  field_type="boolean", valid_values=NULL, default_value="false", visibility_mode="forced"

communication_system_id=3 (Rakel), qualifier_key="encrypted", label="Krypterad", 
  field_type="boolean", valid_values=NULL, default_value="true", visibility_mode="forced"
```

**Qualifier / capability notes**:
- The initial refined model favors simple top-level qualifiers over a large method/capability hierarchy.
- Qualifiers may be operator-editable, forced to a value, or hidden for a given system.
- Later work may still introduce more complex selector/qualifier structures if operational value justifies it.

**Channel-Specific Capability Restrictions**:
- **Real-world constraint**: Some channels may have capability restrictions (e.g., Ch1=DART only, Ch2=DART+Speech, Ch3=Speech only)
- **Design decision**: App does NOT enforce channel-level capability restrictions
- **Reasoning**: 
  - Operator knows what's allowed on each net (operational training)
  - App logs what operator actually used (captures reality, not theoretical limits)
  - Over-engineering: Too granular for operational benefit
  - If needed later: Phase 3+ could add channel-specific capability overrides

**Indexes**:
- `idx_comm_qualifiers_system` ON communication_system_id - Find qualifier definitions for a system
- UNIQUE index on (communication_system_id, qualifier_key)

**Constraints**:
- FOREIGN KEY (communication_system_id) REFERENCES communication_systems(id) ON DELETE CASCADE

**Reasoning**: System-specific option configuration tells GUI what top-level controls to render and how they behave for the selected system.

### report_templates
Stores configuration for structured report templates (7S, 9-liner, etc.).

**Fields**:
- `id` INTEGER PRIMARY KEY AUTOINCREMENT - Unique identifier
- `template_name` TEXT NOT NULL UNIQUE - Display name (e.g., "7S Report")
- `report_type` TEXT NOT NULL UNIQUE - Internal type identifier (e.g., "7S")
- `template_config` TEXT NOT NULL - JSON with field definitions and summary config
- `is_active` INTEGER NOT NULL DEFAULT 1 - Soft delete flag

**Default data** (Phase 1 - 7S template):
```json
{
  "template_name": "7S Report",
  "report_type": "7S",
  "template_config": {
    "fields": {
      "s1_stund": {"label": "Stund (När)", "type": "datetime", "required": false, "help_text": "När observationen gjordes"},
      "s2_stalle": {"label": "Ställe (Var)", "type": "text", "required": false, "help_text": "Grid, plats, landmärke"},
      "s3_styrka": {"label": "Styrka (Hur många)", "type": "text", "required": false, "help_text": "Antal personer/fordon"},
      "s4_slag": {"label": "Slag (Typ)", "type": "text", "required": false, "autocomplete": true, "help_text": "Soldater, fordon, civila"},
      "s5_sysselsattning": {"label": "Sysselsättning (Aktivitet)", "type": "text", "required": false, "autocomplete": true, "help_text": "Vad de gjorde"},
      "s6_symbol": {"label": "Symbol (Kännetecken)", "type": "text", "required": false, "help_text": "Märkning, uniformer"},
      "s7_sagesman": {"label": "Sågesman (Observatör)", "type": "text", "required": false, "help_text": "Vem såg det"}
    },
    "summary_format": "s1_stund, s2_stalle, s3_styrka, s4_slag, s5_sysselsattning",
    "summary_labels": false
  }
}
```

**Indexes**:
- `idx_template_type` ON report_type - Find template by type

**Reasoning**: Configuration-driven report forms - tells GUI what fields to show and how to generate summary.

### file_attachments
File attachments for any entry type (communication, event, or personnel).

**Fields**:
- `id` INTEGER PRIMARY KEY AUTOINCREMENT - Unique identifier
- `parent_table` TEXT NOT NULL - Which table this is attached to ("communication_entries", "event_entries", "personnel_entries")
- `parent_id` INTEGER NOT NULL - ID in parent table
- `file_name` TEXT NOT NULL - Original file name
- `file_content` BLOB NOT NULL - Encrypted attachment content stored inside the encrypted database boundary for Phase 1
- `file_size` INTEGER - Size in bytes
- `file_type` TEXT - File extension or MIME type
- `uploaded_time` TEXT NOT NULL - When attached (ISO 8601 format)
- `operator` TEXT NOT NULL - Who attached the file

**Allowed file types**: txt, pdf, doc, docx, xls, xlsx, jpg, png, gif

**Indexes**:
- `idx_attachment_parent` ON (parent_table, parent_id) - Find attachments for an entry

**Reasoning**: Generic attachment table that can serve all three entry types while keeping attachment content inside the same encrypted-at-rest boundary as the rest of the operational data.

### categories
User-configurable category/tag list for events.

**Fields**:
- `id` INTEGER PRIMARY KEY AUTOINCREMENT - Unique identifier
- `category_name` TEXT NOT NULL UNIQUE - Category name
- `is_active` INTEGER NOT NULL DEFAULT 1 - Soft delete flag (0=inactive, 1=active)

**Default data** (Phase 1 - for your unit):
- "7S", "Kontakt", "Förflyttning", "Underhåll", "Rapport"

**Indexes**:
- `idx_category_active` ON is_active - Filter active categories

### user_preferences
Application runtime configuration and user preferences (loaded after database connection).

**Fields**:
- `key` TEXT PRIMARY KEY - Setting name (e.g., "last_operator", "comm_tab_columns")
- `value` TEXT NOT NULL - Setting value (text, JSON for complex data)
- `description` TEXT NULL - Optional description of setting
- `modified_time` TEXT NOT NULL - When setting was last changed (ISO 8601 format)

**Purpose**: Store user preferences that need database (distinct from bootstrap config.ini):
- Last operator used
- Column configuration per tab (show/hide, order, widths)
- Filter defaults per tab
- Color coding preferences
- Language preference (future)

**Example data**:
```
key="last_operator", value="Sgt. Andersson"
key="comm_tab_columns", value='{"visible": ["time", "from", "to", "method", "message"], "order": [...], "widths": {...}}'
key="personnel_color_code_overdue", value="true"
```

### settings
Repository-managed runtime settings.

**Fields**:
- `key` TEXT PRIMARY KEY - Setting name (e.g., `edited_flag_grace_period_seconds`, `db_migration_level`)
- `value` TEXT NOT NULL - Setting value stored as text and parsed by the repository/app
- `description` TEXT NULL - Optional description of the setting
- `modified_time` TEXT NOT NULL - When the setting was last changed (ISO 8601 format)

**Current default data**:
```
key="edited_flag_grace_period_seconds", value="300"
```

**Purpose**:
- Repository business-rule configuration
- Other low-level settings that should exist before user preferences are loaded

**Boundary note**:
- Repository settings stored here are valid for repository/runtime behavior such as the edited-flag grace period
- SQLite startup identity/version metadata should not treat this table as the authoritative source; that responsibility belongs to SQLite-specific adapter/bootstrap mechanisms

## Data Storage Decisions

### DateTime Storage
Store as ISO 8601 text format (e.g., "2026-04-19T14:30:00")
- Python: `datetime.isoformat()` and `datetime.fromisoformat()`
- Sortable as text
- Human-readable in database

### Boolean Storage
Store as INTEGER (0 = false, 1 = true)
- SQLite doesn't have native boolean type
- Use CHECK constraints: `CHECK (field IN (0, 1))`

### JSON Storage
Store as TEXT with JSON format
- Used for: communication_path, communication_qualifiers, report_data, template_config, complex user_preferences
- Python: `json.dumps()` and `json.loads()`
- Validate before storing (must be valid JSON)

### Comma-Separated IDs
Store as TEXT (e.g., "123,124,125")
- Used for: supersedes field in personnel_entries
- Simple queries with LIKE
- Parse in Python: `ids.split(',')`

### File Storage
Phase 1 attachment content is stored inside the encrypted database
- Attachment metadata and binary content share the same encrypted-at-rest boundary
- Plaintext filesystem attachment directories are not acceptable for security-sensitive attachment content
- Future large-attachment support, if ever approved, would require separately encrypted external storage rather than a fallback to normal readable files

## Required Operations

**Boundary note**:
- Repositories define CRUD workflows, query construction, row mapping, and repository business rules
- The SQLite adapter executes SQL, fetches rows, initializes schema, and owns transaction primitives
- The repository factory chooses which concrete repository implementation to construct for the active dialect

### CommunicationEntry Operations
- CRUD for communication_entries
- Search/filter by date range, operator, from/to, communication_system, and selected communication qualifiers/path where practical
- Full-text search in message_content
- List entries with optional filters (system, date range, qualifier state, etc.)

### EventEntry Operations
- CRUD for event_entries
- Search/filter by date range, operator, whom, priority, category
- Full-text search in event_description
- List entries with optional filters
- Attach/detach structured reports
- Generate auto-summary when structured report attached

### PersonnelEntry Operations
- CRUD for personnel_entries
- Search/filter by who, status, location, active/inactive
- List active entries (default view)
- List all entries for specific "who" (historical view)
- Update status (create new entry, mark old as inactive, set supersedes)
- Set/update supersedes relationships retroactively
- Find overdue alarms (alarm_enabled=1 AND expected_checkin_time < now AND alarm_triggered=0)
- Acknowledge alarms (set alarm_triggered=1)

### StructuredReport Operations
- CRUD for structured_reports
- Find reports for specific event_entry
- Generate auto-summary from report_data based on template config
- Validate report_data against template schema

### Configuration Management
- Get/set communication systems (communication_systems table)
- Get child-label behavior for a system or option-node when rendering the next visible level
- Get/set recursive option rows (`communication_options` table) - linked to specific systems and parented for deeper option paths
- Get/set top-level qualifier config (`communication_qualifiers_config` table) - linked to specific systems
- Get/set report templates (report_templates table)
- Get/set categories (categories table)
- Get/set user preferences (user_preferences table)

### File Attachment Operations
- Add file attachment (any entry type)
- List attachments for entry
- Remove attachment
- Retrieve attachment content for controlled open/export handling

### General Operations
- Export to CSV, PDF (per entry type)
- Database backup/restore
- Database migrations: Apply schema updates based on migration files
- Version management: Track app version, db version, migration level

## Database Migrations

### Migration Strategy (Hybrid Approach)

**Initial Schema** (special case):
```
schema/
├── sqlite/
│   └── initial_schema.sql    (complete schema for new installations)
└── postgres/  (future)
    └── initial_schema.sql
```
- Run only once when creating new database
- Contains complete schema up to current version
- Never run on existing databases

**Migrations** (for upgrading existing databases):
```
migrations/
├── 001_add_attachments/
│   ├── sqlite.sql
│   ├── postgres.sql  (future)
│   └── migration.py  (if complex data migration needed)
├── 002_add_encryption_support/
│   ├── sqlite.sql
│   └── migration.py
└── 003_add_feature_x/
    └── ...
```
- Only run on existing databases
- Applied sequentially to bring old DB up to current version
- **Old migrations can be deleted** once all users are past that version
  (initial schema is updated to include those changes)

### Migration Process

**New Database**:
1. Detect no database exists
2. Create the active adapter and let it run `schema/{dialect}/initial_schema.sql`
3. Stamp required backend-specific identity/version metadata for the new database
4. Set any non-authoritative support state required by the current runtime

**Existing Database**:
1. On app startup, adapter checks authoritative backend-specific identity/version metadata
2. Find all migrations > current level
3. For each migration (in order):
   - Execute SQL file for current dialect
   - Execute Python migration script if present
   - Update backend-specific migration/version state as needed
4. Update any supporting runtime metadata as needed

### Versioning
- **app_version**: Application code version (major.minor.patch)
- **db_version**: Database schema version (major.minor.patch)
- **db_migration_level**: Latest applied migration number (e.g., "003")

For SQLite, the architecture direction is to treat adapter-managed backend metadata (for example `PRAGMA application_id` and `PRAGMA user_version`) as authoritative. If mirrored runtime values are stored elsewhere, they are supportive rather than authoritative.

### Migration Cleanup
When releasing new version, old migrations can be removed:
1. Update `schema/*/initial_schema.sql` to include old migration changes
2. Delete old migration folders
3. Document minimum supported upgrade version

---

**Related**:
- Human version: `docs/design/root_design.md`
- Core design: `ai_instructions/design/core_design.md`
- Database architecture: `ai_instructions/architecture/db_architecture.md`




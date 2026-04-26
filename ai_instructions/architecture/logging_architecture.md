# Logging Architecture (AI)

**Layer**: Infrastructure (Cross-Cutting Concern)  
**Last Updated**: 2026-04-21

## Overview

Logging provides debugging and operational insights without compromising user data privacy.

**Critical Requirements**:
1. ❌ **NO USER DATA IN LOGS** - Privacy/security requirement
2. ✅ File logging with rotation (prevent infinite growth)
3. ✅ Console logging for development
4. ✅ GUI feature to clear all user data
5. ✅ Configuration via config.ini

## Logging Configuration

### Config File (config.ini)

**Location**: Application root directory (same level as src/)

**Logging Section**:
```ini
[Logging]
# Log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
log_level = INFO

# File logging
file_logging_enabled = true
log_file_path = logs/eventlog.log
log_file_max_bytes = 10485760  # 10 MB
log_file_backup_count = 5  # Keep 5 old log files

# Console logging
console_logging_enabled = true
console_log_level = WARNING  # Less verbose for console

# Status bar logging (GUI)
status_bar_log_level = WARNING  # Default: WARNING+, shows in GUI status bar

# Log format
log_format = %%(asctime)s - %%(name)s - %%(levelname)s - %%(message)s
date_format = %%Y-%%m-%%d %%H:%%M:%%S
```

**Rotation Behavior**:
- When `eventlog.log` reaches 10 MB, rename to `eventlog.log.1`
- Previous `eventlog.log.1` → `eventlog.log.2`, etc.
- Keep 5 backup files (total ~50 MB max)
- Oldest file deleted when limit reached

### Logging Setup (Python)

**Location**: `src/logging_config.py`

**Responsibilities**:
- Read logging configuration from config.ini
- Configure Python's logging module
- Set up file handler with rotation (RotatingFileHandler)
- Set up console handler with different log level
- Create logs/ directory if needed

**Pattern**: Single setup function called at application startup (main.py)

**Key Components**:
- File handler: `logging.handlers.RotatingFileHandler` with maxBytes and backupCount
- Console handler: `logging.StreamHandler` with separate log level
- **Status bar handler**: Custom handler for GUI status bar (configurable level, default: WARNING+)
- Formatter: Configurable format and date format
- Root logger: Configured once for entire application

**Three Handlers Pattern**:
1. **File handler**: All INFO+ messages to log files (debugging, audit trail)
2. **Console handler**: WARNING+ messages to console (development)
3. **Status bar handler**: Configurable level (default: WARNING+) messages to GUI status bar (operator awareness)

**Configuration-Driven**: All settings read from config.ini (levels, paths, rotation, format)

## What TO Log

### Application Events (Safe to Log)

**Pattern**: Log metadata and operations, not user content.

✅ **Startup/Shutdown**: Application lifecycle events
✅ **Errors and Exceptions**: Exception type and generic message (no user data)
✅ **Validation Failures**: Field name only, not field content
✅ **Performance Metrics**: Duration, count, sizes
✅ **Configuration Changes**: What changed, not user data

## What NOT TO Log

### User Data (NEVER Log)

**Pattern**: If it's user-entered or operational data, DO NOT log it.

❌ **Message Content**: Communication message text
❌ **Personal Information**: Names, callsigns, who/from/to
❌ **System/Channel Details**: Operational security (which radio, which channel)
❌ **Event Descriptions**: What happened operationally
❌ **Personnel Details**: Location, status, mission notes

### Sanitization Pattern

**Log metadata, not content**:
- ✅ GOOD: "Saved CommunicationEntry with ID: 123"
- ❌ BAD: "Saved message: 'Attack at dawn'"

**Log exception type, not message**:
- ✅ GOOD: "Unexpected error: ValueError"
- ❌ BAD: "Unexpected error: Invalid location 'Grid 12345'"

**Log counts and statistics**:
- ✅ GOOD: "Loaded 42 entries from database"
- ❌ BAD: "Loaded entries for Pluton 2"

## Log Levels

### When to Use Each Level

**DEBUG** (Development only):
- Function entry/exit
- Variable states (sanitized)
- Query execution details
- UI event handling

**INFO** (Normal operations):
- Application lifecycle (start, stop)
- Major operations (save, delete, query)
- Configuration changes
- User actions (generic, no content)

**WARNING** (Potential issues):
- Validation failures
- Slow queries (> threshold)
- Deprecated feature usage
- Recoverable errors

**ERROR** (Actual problems):
- Database errors
- File I/O failures
- Repository operation failures
- Unhandled exceptions

**CRITICAL** (System failures):
- Database corruption
- Cannot start application
- Data integrity issues

## User Data Management

### Clear All Data Feature (GUI)

**Requirement**: User must be able to delete ALL application data from GUI.

**Security Rationale**: Even though logs should not contain user data, clearing them ensures NO trace of operational data remains. This is a security/privacy feature for sensitive operations.

**Location**: Toolbar → "Nollställ" button (Swedish, always visible)

**Pattern**: Instant destructive operation - NO CONFIRMATION DIALOG.

**Operational Rationale**: Used in emergency situations (e.g., about to be overrun by enemy). Must execute instantly - confirmation dialogs waste critical seconds. Visual design (red/orange color, warning icon, isolated placement) prevents accidental clicks.

**What Gets Deleted**:
1. ✅ **Database** - All user entries, reports, operational configuration
2. ✅ **Log Files** - All application logs (including rotated backups)

**What Gets Preserved**:
- ✅ `config.ini` - Application configuration (user's logging/window preferences)

**Implementation Components**:

**Presenter** (`src/gui/presenters/settings_presenter.py`):
- `on_nollstall_clicked()` - Main handler (called from toolbar button)
  - **NO CONFIRMATION** - Executes immediately
  - Call repository delete methods
  - Call log file deletion
  - Reload default seed data
  - Show brief success notification (non-blocking) ("NOLLSTÄLLD!")
  - Refresh UI
- `_delete_all_log_files()` - Helper to delete all *.log* files
  - Read log directory from config.ini
  - Delete all files matching `*.log*` pattern
  - Use print() not logger (deleting logger's files!)

**Repository** (`src/db/repositories/`):
- `delete_all_communication_entries()` - DELETE FROM communication_entries
- `delete_all_event_entries()` - DELETE FROM event_entries
- `delete_all_personnel_entries()` - DELETE FROM personnel_entries
- `delete_all_structured_reports()` - DELETE FROM structured_reports
- `delete_all_configuration()` - DELETE FROM configuration tables
- `load_default_configuration()` - Re-insert default seed data

**UI Flow**:
1. User clicks "Nollställ" button in toolbar
2. Execute deletions immediately (database then logs)
3. Show brief success message (non-blocking toast/status bar update)
4. Refresh all tabs (empty state)

**No Confirmation**: Speed is critical in emergency situations.

### What's NOT Cleared

**Preserved**:
- ✅ `config.ini` - Application configuration (user's log settings, window preferences, etc.)

**Deleted** (for security):
- ❌ Database - All operational data
- ❌ Log files - Even though they shouldn't contain user data, delete for security

**Reasoning**: 
- Config.ini contains user preferences for how the app works (not operational data)
- Database must be cleared (contains all user data)
- Logs must be cleared (safety measure - ensures no leaked data remains)
- After clearing, app can start fresh with default seed data

## Testing

### Logging Tests

**Location**: `tests/unit/test_logging_config.py`

**Test Areas**:
- **Configuration Loading**: Verify config.ini values read correctly
- **File Creation**: Log file and directory created on first run
- **Rotation**: Log file rotates at max size, old files renamed
- **Backup Count**: Only specified number of backups kept
- **Console Output**: Console handler shows correct log level
- **File Output**: File handler shows correct log level
- **User Data Sanitization**: Automated checks that no user data appears in logs

**Pattern**: Use temporary directories and config files for isolation

### Manual Testing

**Checklist**:
- [ ] Log file created on first run
- [ ] Log file rotates at 10 MB
- [ ] Old log files renamed (.1, .2, etc.)
- [ ] Only 5 backup files kept
- [ ] Console shows WARNING+ messages
- [ ] File shows INFO+ messages
- [ ] No user data in any log file
- [ ] "Clear All Data" removes all database entries
- [ ] "Clear All Data" removes all log files (*.log*)
- [ ] "Clear All Data" preserves config.ini
- [ ] "Clear All Data" allows app to restart with seed data
- [ ] Logging works after clearing (creates new log file)

## Dependencies

- `logging` (stdlib) - Core logging
- `logging.handlers` (stdlib) - RotatingFileHandler
- `configparser` (stdlib) - Read config.ini

## Related Files

- `config.ini` - Logging configuration
- `src/logging_config.py` - Logging setup
- `src/gui/status_bar_handler.py` - Custom logging handler for GUI status bar
- `src/gui/presenters/settings_presenter.py` - Clear data feature
- `tests/unit/test_logging_config.py` - Logging tests

## Status Bar Integration

**Pattern**: Custom logging handler displays WARNING+ messages in GUI.

**Location**: `src/gui/status_bar_handler.py`

**Architecture**:
- Custom `logging.Handler` subclass
- Configurable log level (default: WARNING, reads from config.ini)
- Filters to configured level and above (e.g., WARNING, ERROR, CRITICAL)
- Thread-safe: Updates GUI from main thread
- Holds reference to status bar label widget
- Truncates long messages (full message in tooltip)

**Integration with GUI**:
- Created during application startup
- Added to root logger alongside file and console handlers
- Updates status bar in real-time as logs are emitted
- Provides immediate operator feedback for warnings/errors

**See**: `gui_architecture.md` for status bar layout and design.

---

**Related**:
- Core architecture: `ai_instructions/architecture/core_architecture.md`
- Database architecture: `ai_instructions/architecture/db_architecture.md`
- Dependency philosophy: `docs/DEPENDENCY_PHILOSOPHY.md`









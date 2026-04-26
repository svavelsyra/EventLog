# Security Design (AI)

**Domain Models & Configuration**  
**Last Updated**: 2026-04-22

## Overview

Security design details for database encryption, key management, and secure deletion.

**Critical Architecture Decision**: **Single Database Only**
- Application supports ONLY ONE database at a time (security requirement)
- **Reasoning**: Nollställ must be able to clear database AND key file safely
- Cannot know key file paths for unopened databases (key files hidden for steganographic security)
- Multiple database support would create security vulnerability (cannot fully clear all data)
- User must Nollställ current database before creating new one

**See**: `security_architecture.md` for overall security system architecture.

---

## Security Configuration Schema

**Architecture Decision**: Database bootstrap settings in **config.ini** [DB] section.

**Reasoning**: 
- Bootstrap problem: Need to know database path and whether key file required BEFORE opening database
- Cannot open database to read config if we don't know HOW to open it
- config.ini is trusted local file (same security as database file)
- Other settings are defaults/UX helpers, not security enforcement

### Config.ini Settings

**Location**: Application root directory

**SECURITY NOTE**: Config.ini is **completely unprotected**. Any attacker with physical access can read/modify it. Python source code is also readable, so code-based limits provide no real security. Config values here are either:
1. **Bootstrapping info** (needed to open DB)
2. **Defaults for creating NEW databases** (actual values stored in DB header)
3. **UX conveniences** (not security enforcement)

**DB Section** (Bootstrap - required to open database):
```ini
[DB]
# Database file path (for THIS instantiated database)
db_file_path = eventlog.db

# Whether key file required to unlock THIS database instance (set during first setup)
# NOTE: This is about THIS specific database, not a general setting
require_key_file = false  # or "true"
```

**Security Section** (Defaults for creating NEW databases):
```ini
[Security]
# Minimum password length when creating database (UI validation helper)
# NOT cryptographic enforcement - just prevents user mistakes
min_password_length = 8

# Secure deletion passes (operational default)
# Attacker with physical access could change this, but won't bother anyway
secure_delete_passes = 3

# PBKDF2 iterations DEFAULT for NEW databases
# When creating a new database, this value is used
# Actual iterations are stored IN THE DATABASE HEADER (SQLCipher)
# Opening existing database reads iterations from DB, not from config.ini
kdf_iterations = 100000
```

**REMOVED SETTINGS** (Provide no real security):
- ~~`max_login_attempts`~~: REMOVED - Attacker can modify code/config to bypass. Provides no security against competent attacker. Incompetent attacker won't get past encryption anyway.

**Important Notes**:
- **`kdf_iterations` in config.ini**: Default for creating NEW databases only. When database is created, this value is written to the SQLCipher database header. When opening existing database, iterations are read FROM THE DATABASE, not from config.ini.
- **`min_password_length`**: UI validation helper when creating database. Not cryptographic enforcement - just prevents user fat-fingering during setup.
- **`secure_delete_passes`**: Operational setting for convenience. Attacker with physical access has access to entire system anyway.

---

### security_config Table (Database)

**Purpose**: Store security-related configuration flags and settings (EXCEPT require_key_file which is in config.ini for bootstrapping).

**DESIGN PHILOSOPHY**: 
- **Settings stored in DATABASE** = Actually matter for security (read by encrypted DB)  
- **Settings in config.ini** = Defaults for creating NEW databases OR bootstrap info needed to OPEN the database

**Schema**:
```sql
CREATE TABLE security_config (
    key TEXT PRIMARY KEY NOT NULL,
    value TEXT NOT NULL,
    description TEXT,
    last_modified TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX idx_security_config_key ON security_config(key);
```

**Configuration Keys**:

| Key | Type | Description | Default | Notes |
|-----|------|-------------|---------|-------|
| `min_password_length` | integer | Minimum password length | "8" | UI validation only, not cryptographic |
| `secure_delete_passes` | integer | Overwrite passes for Nollställ | "3" | Operational setting |

**REMOVED KEYS** (Don't provide real security):
- ~~`max_login_attempts`~~: REMOVED - Attacker can bypass by modifying code. Provides no security.
- ~~`kdf_iterations`~~: REMOVED from table - Stored in SQLCipher database header instead (cannot be tampered with)

**Bootstrap Settings** (In config.ini, not database):
- `require_key_file`: Needed to know HOW to open database (bootstrap problem - can't read DB to know if key file needed)

**Security Settings NOT Stored** (Never stored anywhere):
- ~~`last_key_file_path`~~: **Never stored** - would leak key file location if device captured. Steganographic security requires key file to remain unknown.

**Examples**:
```sql
-- Database security_config examples:

-- Operational mode (stricter password requirements)
INSERT INTO security_config (key, value, description) VALUES
    ('min_password_length', '12', 'Minimum 12 character password'),
    ('secure_delete_passes', '3', 'Three-pass secure deletion');

-- Training mode (relaxed)
INSERT INTO security_config (key, value, description) VALUES
    ('min_password_length', '8', 'Minimum 8 character password'),
    ('secure_delete_passes', '1', 'Single-pass deletion for speed');
```

**Config.ini Examples**:
```ini
# Operational mode (maximum security)
[DB]
db_file_path = eventlog.db
require_key_file = true

[Security]
# Defaults for NEW databases
min_password_length = 12
secure_delete_passes = 3
kdf_iterations = 100000

# Training mode (simplified)
[DB]
db_file_path = eventlog_training.db
require_key_file = false

[Security]
# Defaults for NEW databases
min_password_length = 8
secure_delete_passes = 1
kdf_iterations = 100000  # Minimum enforced
```

**Validation**:
- `min_password_length`: Must be >= 8
- `secure_delete_passes`: Must be >= 1, <= 10
- `kdf_iterations` (in config.ini): Must be >= 100000 (lower values too weak)

**Config.ini Validation**:
- `require_key_file`: Must be "true" or "false" (case-insensitive, parsed as boolean)
- `db_file_path`: Must be non-empty string

**Access Pattern**:
```python
def get_security_config(key: str, default: str = None) -> str:
    """Get security configuration value"""
    cursor.execute("SELECT value FROM security_config WHERE key = ?", (key,))
    row = cursor.fetchone()
    return row[0] if row else default

def set_security_config(key: str, value: str) -> None:
    """Set security configuration value"""
    cursor.execute("""
        INSERT INTO security_config (key, value, last_modified)
        VALUES (?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(key) DO UPDATE SET
            value = excluded.value,
            last_modified = CURRENT_TIMESTAMP
    """, (key, value))
```

---

## Key File Requirements

### File Selection Criteria

**Any File Type Supported**:
- Images: JPEG, PNG, GIF, BMP, etc.
- Documents: PDF, DOCX, TXT, etc.
- Archives: ZIP, 7Z, TAR, etc.
- Binary: Any file readable as binary

**Restrictions**:
- **Minimum size**: 1 KB (small files provide weak salt)
- **Maximum size**: 100 MB (reading huge files slows startup)
- **Must be readable**: User must have read permission

**Validation**:
```python
def validate_and_open_key_file(file_path: str) -> tuple[BinaryIO | None, str]:
    """
    Validate key file and open it for reading
    
    Opening the file:
    - Verifies read access (file lock acquired on most OS)
    - Ensures file is "owned and readable" by us
    - Most OS will restrict writes while we hold read lock
    
    Returns:
        (file_handle, error_message)
        - file_handle: Open binary file if valid, None if invalid
        - error_message: Empty string if valid, error description if invalid
    """
    # Check existence
    if not os.path.exists(file_path):
        return (None, "Fil finns inte")
    
    # Check it's a file
    if not os.path.isfile(file_path):
        return (None, "Måste vara en fil, inte katalog")
    
    # Check size before opening (avoid opening huge files)
    try:
        file_size = os.path.getsize(file_path)
    except OSError as e:
        return (None, f"Kan inte läsa filstorlek: {e}")
    
    if file_size < 1024:  # 1 KB
        return (None, "Fil för liten (minimum 1 KB)")
    
    if file_size > 100 * 1024 * 1024:  # 100 MB
        return (None, "Fil för stor (maximum 100 MB)")
    
    # Attempt to open file (validates read access + acquires file lock)
    try:
        f = open(file_path, 'rb')
        return (f, "")  # Success - caller must close file
    except PermissionError:
        return (None, "Kan inte läsa fil (behörighet saknas)")
    except OSError as e:
        return (None, f"Kan inte öppna fil: {e}")
```

**Usage**:
```python
# Caller must close file when done
file_handle, error = validate_and_open_key_file(user_selected_path)
if file_handle is None:
    show_error(error)
    return

# File is open and locked - read it
try:
    key_data = file_handle.read()
    # Use key_data for key derivation
finally:
    file_handle.close()  # Release lock
```

**Security Considerations**:
- **File modification**: If key file is edited (e.g., photo rotated), key changes, database becomes inaccessible
- **Recommendation**: Use read-only copy on USB, never edit key files
- **Warning**: Show warning when selecting common file types (JPEG, PNG) to not edit them

---

## Password Requirements

### Password Policy

**Minimum Length**: 8 characters (configurable via `min_password_length`)

**Recommended**: 12+ characters for operational mode

**No Complexity Requirements** (Phase 1):
- No uppercase/lowercase/digit/symbol requirements
- Long passphrase better than complex short password
- Example: "GrönaVagnarRullar2026" > "P@ssw0rd!"

**Why No Complexity**:
- Passphrases easier to remember
- Length more important than character variety
- PBKDF2 iterations protect against brute-force

**Phase 2 Enhancement** (Optional):
- Password strength indicator (zxcvbn algorithm)
- Suggestions for strong passwords
- Password manager integration

**Validation**:
```python
def validate_password(password: str, min_length: int = 8) -> tuple[bool, str]:
    """
    Validate password meets requirements
    
    Returns:
        (is_valid, error_message)
    """
    if len(password) < min_length:
        return (False, f"Lösenord måste vara minst {min_length} tecken")
    
    # Phase 1: Only length check
    # Phase 2: Add strength estimation here
    
    return (True, "")
```

---

## Error Messages

### User-Facing Error Messages (Swedish)

**Authentication Errors**:
- Wrong password/key: `"Ogiltigt lösenord eller nyckelfil. Försök igen."`
- File not found: `"Nyckelfilen kunde inte hittas: {path}"`
- File unreadable: `"Kan inte läsa nyckelfilen (behörighet saknas)"`
- Database corrupted: `"Databasen är skadad och kan inte öppnas."`

**Key File Selection Errors**:
- File too small: `"Fil för liten (minimum 1 KB)"`
- File too large: `"Fil för stor (maximum 100 MB)"`
- Not a file: `"Måste vara en fil, inte katalog"`

**Password Errors**:
- Too short: `"Lösenord måste vara minst {min} tecken"`
- Empty: `"Lösenord får inte vara tomt"`

**Success Messages**:
- Nollställ complete: `"NOLLSTÄLLD!"`
- Database unlocked: (no message, proceed to main window)

---

## Startup Dialog Design

**Architecture Note**: Application supports **single database only** (security decision). 
- If we need to Nollställ (clear database + key file), we can only clear one database safely.
- Cannot know key files for unopened databases.
- Multiple database support would create security vulnerability.

### Key Entry Dialog - Three Cases

**Case 1: First Run (No Database Exists)**

**Layout**:
```
┌──────────────────────────────────────────┐
│  EventLog - Skapa krypterad databas      │
├──────────────────────────────────────────┤
│                                           │
│  Nyckelfil (valfritt):                    │
│  [/path/to/file.jpg          ] [Välj...] │ <- Optional key file
│  [  ] Hoppa över nyckelfil                │ <- Checkbox to skip key file
│                                           │
│  Lösenord:                                │
│  [************************  ]             │ <- Password entry
│                                           │
│  Upprepa lösenord:                        │
│  [************************  ]             │ <- Password confirmation
│  [✓] Visa lösenord                        │ <- Optional toggle
│                                           │
│         [Avbryt]      [Skapa]             │
│                                           │
└──────────────────────────────────────────┘
```

**Behavior**:
- No database file exists yet
- User must choose: key file + password OR password only
- If key file field left empty OR checkbox checked → password-only mode
- Password confirmation required (must match)
- [Skapa] button creates new encrypted database
- Saves `require_key_file` flag to config.ini (true if key file provided, false otherwise)

**Validation**:
- Password and confirmation must match
- Password must meet minimum length
- If key file provided: Validate file exists, readable, size limits
- On success: Create encrypted database with entered credentials

---

**Case 2: Existing Database (Unlock)**

**Layout**:
```
┌──────────────────────────────────────────┐
│  EventLog - Lås upp                      │
├──────────────────────────────────────────┤
│                                           │
│  Nyckelfil:                               │ <- Only shown if require_key_file=true
│  [/path/to/file.jpg          ] [Välj...] │ <- in config.ini
│                                           │
│  Lösenord:                                │
│  [************************  ]             │ <- Password entry (always shown)
│  [✓] Visa lösenord                        │ <- Optional toggle
│                                           │
│    [Nollställ] [Avbryt]      [OK]         │ <- Nollställ button added
│                                           │
└──────────────────────────────────────────┘
```

**Behavior**:
- Database exists, config.ini exists
- Read `require_key_file` from config.ini
- If `require_key_file=true`: Show key file picker (required)
- If `require_key_file=false`: Hide key file picker (password only)
- **[Nollställ] button**: Allows emergency data destruction without login (see below)
- Password field accepts any characters (Unicode supported)
- Escape key disabled (must click Avbryt to exit)
- Enter key submits (attempts unlock)

**Validation**:
- On [OK] click:
  - If require_key_file: Validate key file exists and readable
  - Validate password meets minimum length
  - If validation passes: Attempt database unlock
  
- On database unlock failure:
  - Show error: "Ogiltigt lösenord eller nyckelfil"
  - Clear password field, allow unlimited retries
  - **NO attempt counter** - provides no real security (attacker can modify code)
  - User can retry until they get it right OR click [Avbryt] to exit

**Close Handling**:
- [Avbryt] button: Exit application (cannot proceed without unlock)
- Window close (X): Same as [Avbryt] (exit application)

---

**Case 3: Emergency Nollställ (No Login Required)**

**Critical Feature**: User must be able to destroy data even if password/key forgotten or device about to be captured.

**Trigger**: [Nollställ] button on unlock dialog (Case 2)

**Confirmation Dialog**:
```
┌──────────────────────────────────────────┐
│  ⚠️  VARNING: NOLLSTÄLL                  │
├──────────────────────────────────────────┤
│                                           │
│  Detta kommer PERMANENT radera:           │
│  • Databasen och alla loggar              │
│  • Alla loggfiler                         │
│  • Nyckelfil (om tillgänglig)             │
│                                           │
│  INGEN INLOGGNING KRÄVS                   │
│  DATA KAN EJ ÅTERSTÄLLAS                  │
│                                           │
│  Skriv "RADERA" för att bekräfta:         │
│  [____________________]                   │
│                                           │
│           [Avbryt]      [NOLLSTÄLL]       │
│                                           │
└──────────────────────────────────────────┘
```

**Behavior**:
- User must type "RADERA" (exact match, case-sensitive)
- [NOLLSTÄLL] button enabled only when "RADERA" entered correctly
- On confirmation:
  1. Secure delete database file (if exists)
  2. Secure delete all log files
  3. Secure delete key file (if path in config.ini and writable)
  4. Delete config.ini (removes require_key_file flag)
  5. Show success: "NOLLSTÄLLD!"
  6. Exit application (user restarts for fresh setup)

**Security Benefit**: Even if password/key forgotten or device captured, operator can destroy all data without authentication.

**No Login Required**: This is intentional - emergency destruction more important than authentication in this scenario.

---

## Nollställ Enhancement Design

### Secure Deletion Pattern

**Algorithm**: Overwrite with random data, multiple passes

**Implementation** (`src/security/secure_delete.py`):
```python
import os
import secrets

def secure_delete_file(file_path: str, passes: int = 3) -> bool:
    """
    Securely delete file with overwrite
    
    Args:
        file_path: Path to file to delete
        passes: Number of overwrite passes
    
    Returns:
        True if successful, False otherwise
    """
    try:
        if not os.path.exists(file_path):
            return False
        
        file_size = os.path.getsize(file_path)
        
        with open(file_path, 'r+b') as f:
            for pass_num in range(passes):
                f.seek(0)
                # Write random data
                f.write(secrets.token_bytes(file_size))
                f.flush()
                os.fsync(f.fileno())  # Force write to disk
        
        # Finally, delete file
        os.remove(file_path)
        return True
        
    except (IOError, OSError, PermissionError):
        # Best effort - continue even if fails
        return False
```

**Files to Secure Delete** (in Nollställ):
1. Database file: `eventlog.db`
2. Log files: `logs/*.log*`
3. Key file: If path known and writable

**Execution Order**:
1. Log attempt (before log deletion for debugging)
2. Delete database content (SQL DELETE)
3. Overwrite database file
4. Delete database file
5. Overwrite log files
6. Delete log files
7. Overwrite key file (best effort)
8. Delete key file (best effort)

**Error Handling**:
- Continue on error (don't fail entire Nollställ if one file fails)
- Log errors (before log deletion)
- Show success message even if some files failed (best effort)

---

## Key Derivation Implementation Details

### PBKDF2 Parameters

**Standard**: PBKDF2-HMAC-SHA256

**Iteration Count**: 100,000 (configurable via `kdf_iterations`)

**Why 100,000 Iterations**:
- ~100ms on typical laptop (acceptable startup delay)
- OWASP recommendation: minimum 100,000 for PBKDF2-SHA256
- Higher is better (slows brute-force) but impacts startup time

**Salt Generation**:
- **With key file**: SHA-256 hash of file contents
- **Without key file**: Hardcoded salt `b'EventLog-Default-Salt-v1'`

**Key Rotation** (Phase 2):
- Change salt version: `b'EventLog-Default-Salt-v2'`
- Migration tool re-derives keys with new salt
- Requires old password to decrypt, new password to re-encrypt

**Implementation**:
```python
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
import hashlib

def derive_encryption_key(
    password: str,
    key_file_path: str | None = None,
    iterations: int = 100000
) -> bytes:
    """
    Derive 256-bit encryption key from password and optional key file
    
    Args:
        password: User password
        key_file_path: Optional path to key file
        iterations: PBKDF2 iteration count (minimum 100000 enforced)
    
    Returns:
        32-byte key for AES-256
    
    Raises:
        ValueError: If iterations < 100000 (security minimum)
    """
    # Enforce minimum iterations (OWASP recommendation)
    if iterations < 100000:
        raise ValueError(f"KDF iterations must be >= 100000 (got {iterations})")
    
    # Enforce maximum iterations (practical limit)
    if iterations > 10000000:
        raise ValueError(f"KDF iterations must be <= 10000000 (got {iterations})")
    
    # Determine salt
    if key_file_path:
        with open(key_file_path, 'rb') as f:
            file_data = f.read()
        salt = hashlib.sha256(file_data).digest()
    else:
        salt = b'EventLog-Default-Salt-v1'
    
    # Derive key
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,  # 256 bits
        salt=salt,
        iterations=iterations,
    )
    
    return kdf.derive(password.encode('utf-8'))
```

---

## Database Connection Implementation

### SQLite Repository with Encryption

**Location**: `src/db/repositories/sqlite_eventlog_repository.py`

**Pattern**:
```python
from pysqlcipher3 import dbapi2 as sqlite

class SQLiteEventLogRepository(EventLogAdapter):
    def __init__(self, db_path: str, encryption_key: bytes):
        self.db_path = db_path
        self.encryption_key = encryption_key
        self._connect()
    
    def _connect(self):
        self.connection = sqlite.connect(self.db_path)
        
        # Set encryption key
        self.connection.execute(f"PRAGMA key='{self.encryption_key.hex()}'")
        
        # Verify key is correct (will fail if wrong key)
        try:
            self.connection.execute("SELECT count(*) FROM sqlite_master")
        except sqlite.DatabaseError:
            raise ValueError("Invalid encryption key")
        
        self.cursor = self.connection.cursor()
```

**Key Points**:
- Import `pysqlcipher3` not `sqlite3`
- Set PRAGMA key immediately after connection
- Verify with simple query (fails if wrong key)
- After this point, all SQLite operations work normally (transparent encryption)

---

## Secure Deletion Implementation

### Secure File Deletion

**Location**: `src/security/secure_delete.py`

**Implementation**:
```python
import os
import secrets

def secure_delete_file(file_path: str, passes: int = 3) -> bool:
    """
    Best-effort secure file deletion
    
    Args:
        file_path: Path to file to securely delete
        passes: Number of overwrite passes (default 3)
    
    Returns:
        True if successful, False otherwise
        
    Note: File system journaling may keep copies.
          This is "best effort" not "guaranteed secure".
    """
    try:
        if not os.path.exists(file_path):
            return False
        
        file_size = os.path.getsize(file_path)
        
        with open(file_path, 'r+b') as f:
            for _ in range(passes):
                f.seek(0)
                f.write(secrets.token_bytes(file_size))
                f.flush()
                os.fsync(f.fileno())  # Force write to disk
        
        os.remove(file_path)
        return True
        
    except (IOError, OSError, PermissionError):
        # Best effort - continue even if fails
        return False

def secure_delete_directory(dir_path: str) -> None:
    """Securely delete all files in directory"""
    for file in os.listdir(dir_path):
        file_path = os.path.join(dir_path, file)
        if os.path.isfile(file_path):
            secure_delete_file(file_path)
```

**Usage**:
```python
# In Nollställ handler
secure_delete_file('eventlog.db')
secure_delete_directory('logs/')
if key_file_path:
    secure_delete_file(key_file_path)
```

---

## Repository Factory Pattern

### Factory with Encryption Key

**Location**: `src/db/repositories/repository_factory.py`

**Implementation**:
```python
from src.db.adapters.eventlog_adapter import EventLogAdapter
from src.db.repositories.sqlite_eventlog_repository import SQLiteEventLogRepository
from src.config import AppConfig

def create_repository(config: AppConfig, encryption_key: bytes) -> EventLogAdapter:
    """
    Create repository instance with encryption key
    
    Args:
        config: Application configuration
        encryption_key: 32-byte encryption key from key derivation
    
    Returns:
        Repository instance ready to use
    """
    db_type = config.get('db_type', 'sqlite')
    
    if db_type == 'sqlite':
        db_path = config.get('db_file_path', 'eventlog.db')
        return SQLiteEventLogRepository(db_path, encryption_key)
    elif db_type == 'sqlite_memory':
        return SQLiteEventLogRepository(':memory:', encryption_key)
    else:
        raise ValueError(f"Unsupported database type: {db_type}")
```

**Startup Integration**:
```python
# In main.py startup
from src.security.key_derivation import derive_encryption_key
from src.db.repositories.repository_factory import create_repository

# After user enters credentials in key dialog
key = derive_encryption_key(
    password=user_password,
    key_file_path=user_key_file,  # or None
    iterations=kdf_iterations  # from config
)

# Create repository with key
repository = create_repository(config, key)

# Repository is now ready - database is decrypted
```

---

## Testing Requirements

### Unit Tests

**Location**: `tests/unit/security/`

**Test Files**:
- `test_key_derivation.py` - Key derivation function
- `test_secure_delete.py` - Secure file deletion
- `test_security_config.py` - Configuration validation

**Test Cases**:

**Key Derivation**:
- Same password + same file → Same key (consistency)
- Different password + same file → Different key
- Same password + different file → Different key
- Password only (no file) → Deterministic key
- Empty password → Raises error
- Non-existent file → Raises error

**Secure Deletion**:
- File overwritten before deletion (verify with hexdump)
- Multiple passes work correctly
- Missing file → Returns False (no exception)
- Read-only file → Returns False (best effort)
- Directory instead of file → Returns False

**Security Config**:
- Get/set configuration values
- Default values work
- Boolean parsing ("true"/"false")
- Integer parsing with validation

---

## Migration Notes

### Existing Installations (Phase 2)

If unencrypted databases exist in the wild (Phase 1 without encryption):

**Migration Tool**: `python -m eventlog.tools.encrypt_database`

**Process**:
1. Backup original database
2. Read plaintext database
3. Prompt for new key file + password
4. Create new encrypted database
5. Copy all data
6. Verify integrity (row counts match)
7. User manually validates
8. User manually deletes old plaintext database

**Not Implemented in Phase 1**: All new installations start encrypted.

---

## Related Files

- Security architecture: `ai_instructions/architecture/security_architecture.md`
- Database design: `ai_instructions/design/db_design.md`
- Database architecture: `ai_instructions/architecture/db_architecture.md`

---

**Last Updated**: 2026-04-22 - Initial security design






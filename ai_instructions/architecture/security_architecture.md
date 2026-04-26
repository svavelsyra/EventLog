# Security Architecture (AI)

**Layer**: Infrastructure (Cross-Cutting Concern)  
**Last Updated**: 2026-04-22

## Overview

Security architecture for EventLog application focusing on data-at-rest protection and emergency data destruction.

**Primary Security Goals**:
1. ✅ Protect operational data if device captured
2. ✅ Enable instant data destruction in emergency
3. ✅ Support flexible deployment scenarios (training vs operational)
4. ✅ Maintain operational effectiveness (security doesn't impede mission)

**Security Model**: Defense in depth with multiple independent layers.

---

## Encryption Architecture

### Database Encryption - SQLCipher

**Decision**: Use SQLCipher for SQL-level database encryption.

**Rationale**:
- **Transparent encryption**: Entire database encrypted, zero code changes to queries
- **Maintains search capability**: SQL queries work normally (critical for operational use)
- **Battle-tested**: Used by WhatsApp, Signal, enterprise applications
- **Performance**: Hardware AES acceleration when available
- **Standard SQLite API**: Minimal integration effort

**Alternative Considered**: Python-layer encryption (encrypt fields before INSERT)
- **Rejected**: Breaks SQL search capability, complex code, slower performance

**Dependency Exception**: SQLCipher (`pysqlcipher3`) added to requirements.txt
- Justification: Security-critical code - don't roll your own crypto
- Aligns with dependency philosophy exception policy
- Well-established, widely-used library

**See**: `docs/DEPENDENCY_PHILOSOPHY.md` for updated dependency policy

### Encryption Algorithm

**Standard**: AES-256 (SQLCipher default)

**Why**:
- Industry standard for symmetric encryption
- Hardware acceleration available on modern CPUs
- No known practical attacks on AES-256
- NIST approved

**Key Size**: 256 bits (32 bytes)

---

## Key Management Architecture

### Two-Factor Key Derivation

**Security Model**: Combine "something you have" + "something you know"

**Components**:
1. **Key File** (optional, something you have):
   - Any file readable as binary (image, document, etc.)
   - Stored on USB stick, network drive, or local filesystem
   - Can be disguised as innocent file (e.g., vacation photo amongst thousands)
   - Steganographic security
   
2. **Password** (something you know):
   - User-entered at startup
   - Minimum 8 characters (enforced)
   - Combined with key file (or used alone if file disabled)

**Modes**:
- **Operational Mode** (maximum security): Key file + password required
- **Training Mode** (simplified): Password only

**Configuration**: Database flag `security_config.require_key_file` controls mode

### Key Derivation Function (KDF)

**Algorithm**: PBKDF2-HMAC-SHA256

**Parameters**:
- Salt: SHA-256 hash of key file (or hardcoded salt if password-only)
- Iterations: 100,000 (computational cost to resist brute-force)
- Output: 32 bytes (256 bits for AES-256)

**Pattern**:
```python
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
import hashlib

def derive_encryption_key(file_path: str | None, password: str) -> bytes:
    """Derive SQLCipher key from file + password"""
    
    if file_path:
        # Operational mode: file + password
        with open(file_path, 'rb') as f:
            file_data = f.read()
        salt = hashlib.sha256(file_data).digest()
    else:
        # Training mode: password only with hardcoded salt
        salt = b'EventLog-Default-Salt-v1'  # Version for key rotation
    
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    return kdf.derive(password.encode('utf-8'))
```

**Why PBKDF2**:
- Standard KDF algorithm (NIST approved)
- Computationally expensive (configurable iterations, default 100k = ~100ms)
- Available in `cryptography` library (Python + Rust, portable)
- Brute-force resistant
- Configurable iteration count allows future-proofing as hardware improves

**Alternatives Considered**:
- Argon2: Better resistance, but less portable (C library)
- Scrypt: Memory-hard, but PBKDF2 sufficient with configurable iterations

**Future-Proofing Note**: 
- OWASP recommends 100,000 iterations as minimum (2023)
- As computers get faster, this minimum will increase
- Configurable iterations allow users on faster hardware to increase security
- Example: Fast server (2030): 500,000+ iterations still acceptable startup delay

---

## Application Startup Flow

### Key Loading Sequence

```
App Startup
    ↓
Load security_config from database
    ↓
Check: require_key_file flag?
    ↓                    ↓
  YES                   NO
    ↓                    ↓
Show Key Dialog:      Show Password Dialog:
 - File picker         - Password entry
 - Password entry      
    ↓                    ↓
Derive encryption key from:
 file + password        password only
    ↓
Attempt database connection
    ↓
conn.execute("PRAGMA key=?", (key.hex(),))
    ↓
Try simple query to verify key
    ↓
Success?              Failure?
    ↓                    ↓
Continue loading     Show error:
application          "Ogiltigt lösenord eller nyckelfil"
                     Clear password, allow retry (unlimited)
```

**Key Dialog Location**: `src/gui/dialogs/key_dialog.py`
- Modal dialog, blocks application startup
- Cannot be closed without providing credentials or exiting
- Shows password strength indicator (Phase 2)
- File picker DOES NOT remembers last directory (security)

**Error Handling**:
- Wrong password/file: Clear error message, allow unlimited retries
- File not found: Specific error, allow file selection again
- File unreadable: Permission error shown
- **NO attempt limiting** - Provides no real security (attacker can modify code/config)

**Security Note**: Database must be opened to read unencrypted schema metadata (like table names)
- Bootstrap problem: Need to know if key file required BEFORE opening database
- **Solution**: Store `require_key_file` flag in config.ini (trusted local file, same security as database file)

**See**: `security_design.md` for security_config schema details

---

## Database Connection Pattern

### Standard Connection (with Encryption)

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

**All Queries Work Normally**:
- No changes to SELECT, INSERT, UPDATE, DELETE
- Indexes work
- Foreign keys work
- Full-text search works (if added later)
- Database is encrypted on disk, decrypted in memory

**See**: `db_architecture.md` for repository pattern details

---

## Emergency Data Destruction - Nollställ Enhancement

### Enhanced Nollställ Features

**Current** (Session 005): Delete database + logs
**Enhancement** (This session): Add key file clearing + secure overwrite

**Execution Flow**:
```
User clicks [Nollställ] button
    ↓
1. Delete ALL database entries
   - DELETE FROM communication_entries
   - DELETE FROM event_entries
   - DELETE FROM personnel_entries
   - DELETE FROM structured_reports
   - DELETE FROM configuration tables
   ↓
2. Overwrite database file (best effort)
   - Write random data over file
   - 3 passes (good balance of speed vs security)
   - File system journaling may keep copies
   ↓
3. Delete database file
   ↓
4. Delete ALL log files
   - logs/*.log*
   - Overwrite before delete (best effort)
   ↓
5. Clear encryption key file (if accessible)
   - If key file path known and writable
   - Overwrite with random data (3 passes)
   - Delete key file
   - If on USB: Try to safely eject (best effort)
   ↓
6. Clear key from memory
   - Overwrite key variable with zeros
   - Python garbage collection
   ↓
7. Show brief success message
   ↓
8. Reload default seed data
   ↓
9. Refresh UI (empty state)

Total time: < 3 seconds (security > complexity)
```

**Secure Deletion Pattern**:

**Algorithm**:
```
For each pass (default 3):
  1. Seek to start of file
  2. Write random bytes (same size as file)
  3. Flush buffers
  4. Sync to disk (fsync)
Finally: Delete file
```

**Implementation Location**: `src/security/secure_delete.py`

**See**: `security_design.md` for complete implementation code.

**Key File Clearing Considerations**:
- **If on USB**: May be read-only, may be ejected, may be in use
- **If on network**: May not be writable, network may be down
- **Best effort**: Try to clear, don't fail if inaccessible
- **Logging**: Log attempt status (before log deletion for debugging)

**File System Limitations**:
- **Journaling** (NTFS, ext4): May keep copies in journal
- **SSD wear leveling**: Physical location may change
- **Flash media**: Overwrite may not physically overwrite
- **Mitigation**: Do our best, understand limitations

**Security Benefit**: Even if forensically recoverable, significantly raises difficulty.

**See**: `logging_architecture.md` for existing Nollställ implementation

---

## Performance Considerations

### Encryption Overhead

**SQLCipher Performance**:
- Encryption: ~5-10% CPU overhead on fast machines
- Decryption: ~5-10% CPU overhead
- Hardware AES: Close to zero overhead on modern CPUs

**Key Derivation**:
- PBKDF2 100k iterations: ~100ms on typical laptop
- Happens once at startup (acceptable)

**Startup Time**:
- Without encryption: ~200ms (database open + schema check)
- With encryption: ~300ms (key derivation + database open)
- Additional 100ms is acceptable

**Query Performance**:
- SELECT: Negligible difference (encrypted pages cached in memory)
- INSERT: Negligible difference
- Large queries: ~5% slower (decryption of many pages)

**Operational Impact**: Minimal - encryption overhead is imperceptible for typical usage.

---

## Security Threat Model

### Threats Mitigated

1. ✅ **Device Capture (Powered Off)**:
   - Encrypted database unreadable without key file + password
   - Attacker needs BOTH factors to decrypt
   
2. ✅ **Device Capture (Powered On, Nollställ Executed)**:
   - Database deleted + overwritten
   - Logs deleted + overwritten
   - Key file deleted + overwritten
   - Data unrecoverable (best effort)
   
3. ✅ **Lost/Stolen USB Stick (with key file)**:
   - Key file alone insufficient (needs password)
   - Disguised as innocent file (steganographic security)
   
4. ✅ **Password Compromise** (weak password guessed):
   - Still need key file
   - PBKDF2 iterations slow brute-force
   
5. ✅ **Database File Extraction**:
   - Encrypted database is useless without key
   - AES-256 is not practically breakable

### Threats NOT Mitigated

1. ⚠️ **Memory Forensics (Device Running)**:
   - Key is in memory while application running
   - Cold boot attack possible (rare)
   - **Mitigation**: Nollställ clears key from memory, power off device
   
2. ⚠️ **Shoulder Surfing** (password entry observed):
   - Attacker sees password being entered
   - **Mitigation**: Physical security, screen privacy filters
   
3. ⚠️ **Keylogger/Malware**:
   - Compromised OS-level security
   - **Mitigation**: Trusted hardware, no network (reduces malware risk)
   
4. ⚠️ **Forensic Recovery** (after Nollställ):
   - File system journaling, SSD wear leveling may keep copies
   - **Mitigation**: Best-effort secure delete, physical destruction of media (final option)

### Accepted Risks

**Physical Security Assumed**:
- Application has no user authentication (anyone can use if key entered)
- Key dialog can be photographed
- Physical access to running system = full access

**Rationale**: Military operational environment has physical security. Adding user authentication would slow operational tempo.

**Future Enhancement** (Phase 2): Operator PIN after key entry for multi-user scenarios.

---

## Integration with Other Layers

### Core Layer Integration

**Location**: `src/core/` (no changes needed)

**Pattern**: Core layer remains encryption-agnostic
- Entities don't know about encryption
- Validators don't know about encryption
- Business logic unchanged

**Separation of Concerns**: Encryption is database layer concern, not business logic.

**See**: `core_architecture.md` for business logic

### Database Layer Integration

**Location**: `src/db/repositories/`

**Changes Required**:
- Repository constructor accepts `encryption_key` parameter
- Connection setup includes `PRAGMA key` statement
- Factory pattern updated to handle key derivation

**Pattern**:
```
Startup Flow:
  1. User enters password (+ optional key file)
  2. Derive encryption key from inputs
  3. Factory creates repository with key
  4. Repository sets PRAGMA key on connection
  5. Normal operation begins
```

**See**: `db_architecture.md` for repository factory pattern details.

**See**: `db_architecture.md` for repository pattern

### GUI Layer Integration

**Location**: `src/gui/dialogs/key_dialog.py` (new)

**Integration Points**:
- Startup: Show key dialog before main window
- Settings: Allow changing password (Phase 2)
- Nollställ: Enhanced clearing (database layer calls secure_delete)

**Minimal GUI Impact**: One dialog at startup, rest handled in database layer.

**See**: GUI architecture not updated - security architecture documents GUI needs.

---

## Dependencies

### New Dependencies (When Implemented)

**Application** (add to requirements.txt during implementation):
- `pysqlcipher3>=1.0.0` - SQLCipher bindings for Python
- `cryptography>=41.0.0` - PBKDF2 key derivation

**Justification**: Security-critical functionality per dependency philosophy.

**Status**: NOT YET ADDED - Designed in Session 006, will be added when implementing encryption.

**See**: `docs/DEPENDENCY_PHILOSOPHY.md` for updated policy

### Dependency Security

**Supply Chain Risk Mitigation**:
- Both libraries well-established, widely used
- `cryptography`: 10,000+ GitHub stars, used by major projects
- `pysqlcipher3`: Battle-tested, used in production applications
- Pin versions in requirements.txt (avoid auto-updates)

---

## Testing Strategy

### Encryption Testing

**Location**: `tests/unit/security/`

**Test Areas**:
- Key derivation produces consistent keys
- Different files produce different keys
- Different passwords produce different keys
- Same file + password produces same key
- Database opens with correct key
- Database fails with wrong key
- Secure deletion overwrites files

**Integration Testing**:
- Full startup flow with key dialog
- Nollställ with key file clearing
- Key file on USB (mock USB path)

**Manual Testing**:
- Actual USB stick with key file
- Remove USB during operation (error handling)
- Wrong password recovery flow
- Secure deletion verification (hexdump file after)

---

## Configuration

### Security Configuration Philosophy

**CRITICAL**: Config.ini and Python source code are **completely unprotected**. Any attacker with physical access can read/modify them. Therefore:

**Settings in config.ini**:
1. **Bootstrapping info** - Needed to open database (db_file_path, require_key_file)
2. **Defaults for NEW databases** - Used when creating database (kdf_iterations written to DB header)
3. **Operational conveniences** - NOT security enforcement (secure_delete_passes)

**Settings in database**:
- Values that actually matter (read from encrypted database)
- Cannot be tampered with without knowing encryption key

**Settings NEVER stored**:
- Anything that would leak security info (last_key_file_path)

### Config.ini Settings

**See**: `security_design.md` for complete config.ini schema

**Highlights**:
```ini
[DB]
# Path to THIS database instance
db_file_path = eventlog.db

# Whether THIS database requires key file (bootstrap info)
require_key_file = false

[Security]
# Defaults for creating NEW databases
kdf_iterations = 100000  # Written to DB header when creating DB

# Operational settings
secure_delete_passes = 3  # Convenience, not security enforcement
```

**REMOVED SETTINGS** (Provide no real security):
- ~~`max_login_attempts`~~: REMOVED - Attacker can bypass by modifying code. No value against competent attacker.

**Important**: `kdf_iterations` in config.ini is **default for NEW databases only**. Actual iterations stored in SQLCipher database header (cannot be read or modified without decryption key).

---

## Migration Strategy

### Existing Plaintext Databases

**Challenge**: How to encrypt existing database?

**Phase 1**: No migration (new installations only)
- Encryption required from first run
- No plaintext databases created

**Phase 2** (If Needed): Migration tool
- Command-line tool: `python -m eventlog.tools.encrypt_database`
- Reads plaintext database, writes encrypted copy
- Prompts for key file + password
- Verifies encrypted database integrity
- User manually deletes old plaintext database

**Pattern**:
```bash
# Encrypt existing database
python -m eventlog.tools.encrypt_database \
    --input eventlog.db \
    --output eventlog_encrypted.db \
    --key-file vacation.jpg \
    --password

# Prompts for password
# Creates encrypted copy
# User manually verifies and replaces
```

---

## Related Files

- Security design: `ai_instructions/design/security_design.md`
- Database architecture: `ai_instructions/architecture/db_architecture.md`
- Dependency philosophy: `docs/DEPENDENCY_PHILOSOPHY.md`
- Logging architecture: `ai_instructions/architecture/logging_architecture.md` (Nollställ)

---

**Last Updated**: 2026-04-22 - Initial encryption architecture design









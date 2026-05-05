# Security Design (AI)

**Domain Models & Configuration**  
**Last Updated**: 2026-04-30

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

**Architecture Decision**: Remembered bootstrap hints and creation defaults live in `config.ini`, using `[DEFAULT]` as the shared inherited fallback for bootstrap/security-related values and one section per technology for technology-owned remembered target details plus optional overrides.

**Reasoning**:
- Startup benefits from remembering the last-used database technology/target and related unlock hints
- The application must still be able to start when that remembered data is missing or malformed
- `config.ini` is untrusted convenience state, not security authority
- Other settings here are creation defaults, administrator-controlled policy inputs, or UX helpers, not security enforcement

### Policy Ownership Philosophy

- The application should guide users toward sensible and safer choices, but it should not hard-code one universal workflow that ignores operational reality.
- Administrators define the allowed policy envelope for new database creation, such as minimum password length, key-file-related minimums/limits, and which database technologies are allowed to be selected.
- Current shared/create-time inputs belong in `[DEFAULT]`, but that does not remove ordinary sections such as `[Logging]`, `[Application]`, or technology sections that may override shared values when needed.
- Operators then create a database within that allowed envelope.
- Once a database is created, the effective rules for that database belong to that database's own authoritative state, not to later changes in `config.ini`.
- This means an administrator may create a database with a stricter or simpler rule set first, and operators who later use that database are constrained by the database-owned rules rather than by whatever convenience defaults happen to be in local config afterward.
- This is also a realistic-threat-model rule: local config and Python source can be changed by anyone with machine access, so only protected database state can meaningfully hold authoritative security rules after creation and unlock.
- Result: the application guides, administrators define creation-time policy, operators choose within that policy, and the created database becomes the authoritative source for its own effective rules.
- If a future technology needs a different concept than `min_password_length` or `require_key_file_for_creation`, that rule should be added as backend-owned or technology-scoped policy rather than forcing every technology into one fake global truth.

### Security Boundary Design Rule

- Shared security design should stay small, explicit, and audit-friendly.
- Shared security helpers should contain only cross-technology concerns such as generic KDF primitives, generic credential/file validation, shared security exceptions, and secure-deletion behavior.
- Backend-specific security behavior belongs with the backend that owns it. If SQLite/SQLCipher needs a particular salt contract, key formatting rule, metadata source, or unlock verification behavior, that design belongs with the SQLite implementation rather than in the shared security helper layer.
- Startup/presenter/factory code may orchestrate the sequence, but they should not silently absorb backend-specific cryptographic rules.

### Config.ini Settings

**Location**: Application root directory

**SECURITY NOTE**: `config.ini` is **completely unprotected**. Any attacker with physical access can read/modify it. Python source code is also readable, so code-based limits provide no real security. Config values here are either:
1. **Bootstrap memory** used to prefill the startup UI
2. **Defaults for creating NEW databases** (actual values stored in DB/SQLCipher state)
3. **Administrator-controlled policy inputs** such as minimum password length, key-file-related limits, and allowed database technologies for creation-time validation
4. **UX conveniences** (not security enforcement)

**Default Section** (Shared inherited fallback values for bootstrap/security-related settings):
```ini
[DEFAULT]
# Remembered last-used database technology / selected startup technology
db_type = sqlite

# Whether NEW databases must use a key file at creation time.
require_key_file_for_creation = false

# Minimum password length when creating database (UI validation helper)
min_password_length = 8

# Secure deletion passes (operational default)
secure_delete_passes = 3

# PBKDF2 iterations DEFAULT for NEW databases
kdf_iterations = 100000
```

**Technology Section** (Remembered startup hints plus optional overrides; section shape may differ by technology):
```ini
[sqlite]
# Remembered last-used SQLite database target/path for startup convenience
database_path = eventlog.db

# Whether the remembered last-used SQLite database used key-file mode
# NOTE: This is startup memory, not security authority
require_key_file = false  # or "true"

# Optional SQLite-specific override of a shared DEFAULT value when needed
# min_password_length = 10
```

**REMOVED SETTINGS** (Provide no real security):
- ~~`max_login_attempts`~~: REMOVED - Attacker can modify code/config to bypass. Provides no security against competent attacker. Incompetent attacker won't get past encryption anyway.

**Important Notes**:
- **`kdf_iterations` in config.ini**: Default for creating NEW databases only. When a database is created, this value is written into SQLCipher-managed state. Opening an existing database must not treat config.ini as authoritative.
- **`min_password_length`**: UI validation helper when creating a NEW database. Not cryptographic enforcement - just prevents user mistakes during setup.
- **`secure_delete_passes`**: Operational setting for convenience. Attacker with physical access has access to the entire system anyway.
- **Bootstrap memory**: Missing or malformed remembered values must not prevent startup. They only affect how much the startup UI can prefill automatically.
- **Allowed technology list / credential policy in config**: These are creation-time policy inputs and convenience guidance. They can shape what the create flow allows on this machine, but they are not retroactive authority over an already-created database.
- **Key-file split**: the selected technology section's `require_key_file` is remembered startup memory for an already-created target, while `[DEFAULT].require_key_file_for_creation` is the create-time admin policy input for new databases.
- **Current-phase scope**: settings such as `require_key_file_for_creation` and `min_password_length` are current shared/create-time inputs, not a promise that all present or future technologies will use exactly those same policy fields.

---

### security_config Table (Database)

**Purpose**: Store security-related configuration flags and settings that are authoritative after the encrypted database is available.

**DESIGN PHILOSOPHY**:
- **Settings stored in DATABASE** = Actually matter for security after unlock and are authoritative for the current database
- **Settings in config.ini** = Defaults for creating NEW databases or remembered startup hints used to prefill recovery-capable UI
- **Practical consequence** = Admin policy may shape what can be created next, but once a database exists, that database's own protected state is the only meaningful place to keep its effective rules

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

**Bootstrap Memory Settings** (In config.ini, not database):
- `[DEFAULT].db_type`: Remembered/selected database technology for startup prefill
- technology-section target field such as `[sqlite].database_path`: Remembered last-used target/path for startup prefill
- technology-section `require_key_file`: Remembered last-used unlock mode hint for startup prefill

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
[DEFAULT]
db_type = sqlite
require_key_file_for_creation = true
min_password_length = 12
secure_delete_passes = 3
kdf_iterations = 100000

[sqlite]
database_path = eventlog.db
require_key_file = true

# Training mode (simplified)
[DEFAULT]
db_type = sqlite
require_key_file_for_creation = false
min_password_length = 8
secure_delete_passes = 1
kdf_iterations = 100000  # Current recommended default

[sqlite]
database_path = eventlog_training.db
require_key_file = false
```

**Validation**:
- `min_password_length`: Must be >= 0
- `secure_delete_passes`: Must be >= 1, <= 10
- `kdf_iterations` (in config.ini): Must be a positive integer; `100000` remains the current recommended default for new databases

**Config.ini Validation**:
- `[DEFAULT].db_type` and the selected technology section's remembered target fields are startup hints, not application-start prerequisites
- `[DEFAULT].require_key_file_for_creation` is a create-time policy/default input, not remembered startup memory for existing databases
- Missing remembered bootstrap values => startup falls back to manual create/select flow
- Partially malformed remembered bootstrap values => preserve usable values, discard invalid ones, keep startup UI usable
- Completely unusable remembered bootstrap values => ignore them and fall back to manual create/select flow

**Access Pattern**:
- Read by key, returning a caller-supplied default when the key is absent.
- Write by key using an upsert-style update so the key remains unique and `last_modified` changes on every update.
- This is an authoritative encrypted-database configuration surface after unlock; callers should not mirror these values back into `config.ini` unless the value is explicitly part of remembered bootstrap memory.

---

## Key File Requirements

### File Selection Criteria

**Any File Type Supported**:
- Images: JPEG, PNG, GIF, BMP, etc.
- Documents: PDF, DOCX, TXT, etc.
- Archives: ZIP, 7Z, TAR, etc.
- Binary: Any file readable as binary

**Restrictions**:
- **Recommended minimum size**: 1 KB (smaller files may still work technically, but are discouraged as a quality recommendation rather than a universal protocol rule)
- **Maximum size**: 100 MB (reading huge files slows startup and creates avoidable abuse/performance risk)
- **Must be readable**: User must have read permission

**Validation Contract**:
- Input: a caller-supplied file path.
- Checks, in order (Or maybe try open() and catch exceptions, then we implicitly knows several of these checks. The exact implementation can vary, but the validation must cover these concerns):
  1. path exists
  2. path is a file, not a directory
  3. file size can be read
  4. file size does not exceed the configured abuse/performance cap
  5. file can be opened for binary reading
- Success result:
  - caller receives readable binary content or an opened readable handle, depending on the helper shape chosen during implementation
  - caller is responsible for closing any opened handle
- Failure result:
  - caller receives a clear, user-mappable validation failure without exposing unrelated internal details
- Design rule:
  - keep the helper generic to file usability and abuse bounds
  - backend-specific interpretation of the file contents belongs in the backend-owned security path

**Usage Shape**:
- startup or create/unlock orchestration requests validation of the selected file
- on failure, UI maps the failure to a user-visible message and remains in the recovery-capable flow
- on success, the validated file content is passed into backend-owned salt/key preparation logic

**Security Considerations**:
- **File modification**: If key file is edited (e.g., photo rotated), key changes, database becomes inaccessible
- **Recommendation**: Use read-only copy on USB, never edit key files
- **Warning**: Show warning when selecting common file types (JPEG, PNG) to not edit them

---

## Password Requirements

### Password Policy

**Minimum Length**: Administrator-configured via `min_password_length`

**Recommended**: 12+ characters for operational mode

**Allowed Credential Combinations**:
- no password, no key file
- password only
- key file only
- password + key file

Which combinations are allowed should be decided by administrator-controlled creation policy and by backend support for the selected technology.
Other technologies may have different allowed combinations or different credential types entirely, but the architecture should support that flexibility without hard-coding assumptions about composition rules or required credential types.

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

**Validation Contract**:
- Input: user-entered password plus administrator-controlled `min_password_length`.
- Empty password may be allowed if the selected credential combination is permitted by the current admin policy and the selected backend supports that combination.
- This may include convenience/training-oriented setups such as key-file-only mode or even no-password/no-key-file mode when explicitly allowed.
- Reject passwords shorter than the configured minimum.
- Do not require uppercase/lowercase/digit/symbol composition rules in Phase 1.
- Return a caller-visible success/failure shape that higher layers can map to UI feedback.

**Guidance vs Enforcement**:
- The GUI should indicate what is allowed, what is recommended, and which choices provide weak or no meaningful protection.
- The application should help users make better choices, but actual enforcement should come from the configured/admin-defined rule set and backend support rather than from hidden hard-coded assumptions in the UI.

---

## Error Messages

### User-Facing Error Messages (Swedish)

**Authentication Errors**:
- Wrong password/key: `"Ogiltigt lösenord eller nyckelfil. Försök igen."`
- File not found: `"Nyckelfilen kunde inte hittas: {path}"`
- File unreadable: `"Kan inte läsa nyckelfilen (behörighet saknas)"`
- Database corrupted: `"Databasen är skadad och kan inte öppnas."`

**Key File Selection Errors**:
- File too large: `"Fil för stor (maximum 100 MB)"`
- Not a file: `"Måste vara en fil, inte katalog"`

**Key File Selection Warnings / Guidance**:
- Very small files may be discouraged by UI guidance, but they are not a universal protocol error if the selected backend accepts them.

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
- Single-database scope does **not** mean the startup UI is permanently SQLite-shaped; technology selection still happens first and the UI then adapts to the selected technology.

### Startup / Unlock Dialog Flow

The startup UI must always provide a recovery-capable path. Remembered values from `config.ini` are prefill hints only.

### Generic Startup Shell Contract

These rules are generic and apply regardless of which backend technology is selected:
- Startup begins by resolving or selecting the database technology.
- Remembered config values may prefill the startup UI, but they are not authoritative.
- Once the technology is selected, the UI becomes dynamic and shows only the fields relevant for that technology.
- The selected technology defines which target fields, file pickers, credential inputs, and readiness checks are required.
- Missing or malformed remembered bootstrap memory must fall back to a usable create/select recovery path.
- The create flow should validate the operator's selected setup against admin-defined policy for allowed technologies and credential combinations.
- The GUI should clearly distinguish between what is allowed and what is merely recommended.

### Current SQLite/SQLCipher Realization

The detailed dialog layouts below are **current-phase SQLite/SQLCipher examples**, not the universal startup UI contract for all future backends.

**Case 1: Current SQLite/SQLCipher Example - Create New Database**

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
- No remembered database target exists, or the user intentionally starts from an empty create/select flow
- Startup UI begins with safe defaults or empty selections
- After the user selects the current SQLite technology, the SQLite/SQLCipher-specific create fields below become relevant
- For SQLite, create versus unlock is inferred from whether the selected target already exists; the generic startup shell must not show a separate global create/open mode selector
- User may choose no credentials, password only, key file only, or key file + password, subject to current admin policy and SQLite support
- Password confirmation required (must match)
- [Skapa] button creates new encrypted database
- On success, save remembered startup hints in `config.ini` so the next startup can prefill the UI

**Validation**:
- Password and confirmation must match when a password is being used
- Password must meet the configured minimum when a password is required by the selected setup
- If key file provided: Validate file exists, readable, size limits
- If the selected setup is allowed but weak, the UI may warn or guide without blocking
- On success: Create encrypted database with entered credentials

---

**Case 2: Current SQLite/SQLCipher Example - Existing Database Unlock**

**Layout**:
```
┌──────────────────────────────────────────┐
│  EventLog - Lås upp                      │
├──────────────────────────────────────────┤
│                                           │
│  Nyckelfil:                               │ <- Only shown if remembered/selected require_key_file=true
│  [/path/to/file.jpg          ] [Välj...] │ <- user provides path at unlock time, not persisted
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
- Remembered startup hints may preselect database technology/path and whether key-file mode was used last time
- User may keep the prefilled values, change them, or manually select another database target
- These controls are shown because the currently selected technology is SQLite/SQLCipher; another backend may use different fields entirely
- For SQLite, unlock mode is reached when the selected target already exists rather than by a separate operator-picked global mode toggle
- If the selected or remembered target uses key-file mode: Show key file picker (required)
- If the selected or remembered target does not use key-file mode: Hide key file picker (password only)
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

**Case 3: Malformed Remembered Bootstrap Memory**

**Behavior**:
- Startup still reaches the create/select database UI
- Usable remembered values may still prefill the UI
- Malformed remembered values are discarded rather than treated as authoritative
- The application must not crash or become unusable merely because bootstrap memory is stale or malformed
- UX details for how warnings are surfaced can evolve later, but recovery path is mandatory
- In the current SQLite/SQLCipher path, that may mean clearing remembered path or key-file-mode hints while still letting the user select SQLite manually and continue

---

**Case 4: Emergency Nollställ (No Login Required)**

**Critical Feature**: User must be able to destroy data even if password/key forgotten or device about to be captured.

**Trigger**: [Nollställ] button on unlock dialog (Case 2)

**Interaction Model**:
- `Nollställ` is an immediate emergency action in the unlock/startup path.
- No secondary confirmation dialog, typed phrase, or extra approval step is allowed in this emergency flow.
- Rationale: in the intended threat scenario, the operator may have only seconds and must be able to reset immediately and return attention to the situation.

**Behavior**:
- When the user triggers `Nollställ`, reset begins immediately.
- Execution order:
  0. Clear UI state.
  1. Lock DB.
  2. Secure delete database file (if exists)
  3. Secure delete all log files
  4. Delete config.ini (removes remembered bootstrap memory such as `require_key_file`)
  6. Show success: "NOLLSTÄLLD OK!" or "MISSLYCKADES NOLLSTÄLLA!" (+ Sanitized list of failures)
  6. Exit application (user restarts for fresh setup)

**Security Benefit**: Even if password/key forgotten or device captured, operator can destroy all data without authentication.

**No Login Required**: This is intentional - emergency destruction more important than authentication in this scenario.

---

## Nollställ Enhancement Design

### Secure Deletion Pattern

**Algorithm**: Overwrite with random data, multiple passes

**Implementation Contract** (`src/security/secure_delete.py`):
- Input: file path plus overwrite-pass count.
- Sequence:
  1. confirm the file exists
  2. determine file size
  3. overwrite the file contents for the requested number of passes
  4. flush/sync best effort between passes
  5. delete the file
- Return shape:
  - boolean success/failure, with failure treated as best-effort rather than fatal to the whole reset flow
- Design rule:
  - exact helper shape may vary, but the behavior must remain best-effort, local-only, and safe to call repeatedly

**Files to Secure Delete** (in Nollställ):
1. Database file: `eventlog.db`
2. Log files: `logs/*.log*`

**Files NOT Automatically Deleted**:
- External key files selected by the user during bootstrap/unlock. A key-file path may point to any user-owned file, so `Nollställ` must not assume the app owns it.

**Execution Order**:
1. Log attempt (before log deletion for debugging)
2. Delete database content (SQL DELETE)
3. Overwrite database file
4. Delete database file
5. Overwrite log files
6. Delete log files

**Error Handling**:
- Continue on error (don't fail entire Nollställ if one file fails)
- Log errors (before log deletion)
- Show success message even if some files failed (best effort)

---

## Key Derivation Implementation Details

### PBKDF2 Parameters

**Standard**: PBKDF2-HMAC-SHA256

**Iteration Count**: Caller-supplied, typically sourced from creation defaults for new databases or backend-authoritative metadata for existing databases

**Why 100,000 Iterations as the Current Default**:
- ~100ms on typical laptop (acceptable startup delay)
- OWASP recommendation: minimum 100,000 for PBKDF2-SHA256
- Higher is better (slows brute-force) but impacts startup time

**Shared Primitive Contract**:
- password is encoded as UTF-8
- salt is caller-supplied
- iteration count is caller-supplied
- output length is caller-supplied

**Backend-Owned Responsibilities**:
- decide how salt is obtained for that backend
- decide whether key-file bytes are hashed first or otherwise transformed
- decide the output length expected by that backend
- decide where authoritative iteration values come from for existing databases

**Key Rotation** (Phase 2):
- Change salt version: `b'EventLog-Default-Salt-v2'`
- Migration tool re-derives keys with new salt
- Requires old password to decrypt, new password to re-encrypt

**Shared Primitive Contract**:
- Input:
  - password string
  - caller-supplied salt bytes
  - caller-supplied iteration count
  - caller-supplied output length
- Output:
  - deterministic derived key bytes for the same exact inputs
- Required behavior:
  - encode password as UTF-8
  - use PBKDF2-HMAC-SHA256
  - reject structurally invalid values such as non-positive lengths or non-positive iterations
  - allow caller/backend policy to choose the actual recommended iteration value
- Design rule:
  - this helper stays backend-agnostic and must not silently inject SQLite-owned salt or output rules

**Current SQLite/SQLCipher Example**:
- password-only mode uses the current SQLite-owned default salt contract
- key-file mode hashes the key-file bytes with SHA-256 before using the result as salt
- SQLite currently requests a 32-byte derived key
- SQLite then passes that derived key into its own readiness/open flow

This is current backend-owned behavior, not the permanent generic KDF contract.

---

## Database Connection Implementation

### SQLite Repository with Encryption

**Location**: `src/db/repositories/sqlite_eventlog_repository.py`

**Pattern**:
- open SQLCipher-backed connection using the selected SQLite target
- apply the backend-owned key/open command immediately after connection
- run a lightweight verification query to confirm the key is valid
- only after successful verification does normal repository work continue

**Key Points**:
- Import `pysqlcipher3` not `sqlite3`
- Set PRAGMA key immediately after connection
- Verify with simple query (fails if wrong key)
- After this point, all SQLite operations work normally (transparent encryption)

---

## Secure Deletion Implementation

### Secure File Deletion

**Location**: `src/security/secure_delete.py`

**Implementation Contract**:
- file deletion remains best-effort, not guaranteed forensic erasure
- single-file helper overwrites and deletes one file path
- directory helper iterates ordinary files and applies the single-file helper to each one
- missing/inaccessible files return failure information to the caller without aborting the whole reset sequence

**Usage Shape**:
- reset flow calls the single-file helper for the database file
- reset flow calls the directory helper for logs
- reset flow attempts best-effort deletion of reachable key material if a path is known

---

## Repository Factory Pattern

### Factory with Encryption Key

This subsection shows the **current SQLite/SQLCipher-oriented factory example**.

The generic rule is:
- startup resolves or confirms a technology-specific target first
- backend-specific readiness happens next
- repository creation happens only after that selected target is ready

**Location**: `src/db/repositories/repository_factory.py`

**Implementation Contract**:
- Input:
  - user-confirmed/resolved startup target
  - backend-ready encryption key material
- Behavior:
  - inspect the resolved database technology/dialect
  - dispatch to the matching backend-owned repository constructor
  - reject unsupported dialects explicitly
- Design rule:
  - backend selection belongs here, but backend-specific credential derivation logic does not

**Startup Integration**:
- validate password against the administrator-controlled minimum length
- if a key file is provided, validate/load it through the shared helper boundary
- let the selected backend resolve its own salt/output/iteration rules as needed
- call the shared KDF primitive with those backend-selected inputs
- pass the backend-ready key into repository creation

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






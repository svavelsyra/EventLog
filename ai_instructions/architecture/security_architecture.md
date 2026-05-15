# Security Architecture (AI)

**Layer**: Infrastructure (Cross-Cutting Concern)  
**Last Updated**: 2026-04-30

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

**Dependency Exception**: SQLCipher (`sqlcipher3`) added to requirements.txt
- Justification: Security-critical code - don't roll your own crypto
- Aligns with dependency philosophy exception policy
- Well-established SQLCipher binding with a working Windows CPython 3.14 wheel in the current EventLog environment

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
   - Minimum length comes from administrator-controlled policy/defaults rather than a universal hard-coded rule in the low-level primitive
   - Combined with key file (or used alone if file disabled)

**Allowed Credential Combinations**:
- no password, no key file
- password only
- key file only
- password + key file

Which combinations are allowed is an administrator-defined creation-time policy decision, constrained by backend support for the selected technology.
A specific technology may require completely different credential types or combinations, and the architecture must allow that flexibility without hard-coding one universal workflow.

### Policy Ownership and Authority

- The application should guide users toward stronger choices, but it should not hard-code one universal credential workflow for every operational context.
- Administrators define the creation-time policy envelope, such as allowed database technologies, minimum password length, and allowed credential combinations.
- Operators then choose a concrete setup within that envelope during database creation.
- Once a database exists, that database's own protected state becomes the authoritative source for its effective rules.
- Later changes to `config.ini` may affect future database creation on the local machine, but they are not retroactive authority over already-created databases.
- This follows the realistic threat model: local config and Python source can be modified by anyone with machine access, while only protected database state can meaningfully hold authoritative rules after creation and unlock.

### Security Boundary and Audit Scope

The security architecture should remain reviewable as a deliberate boundary.

**Shared security boundary**:
- cross-technology key-derivation primitives
- secret-material handling helpers
- generic credential/file validation helpers
- shared security exceptions and generic failure contracts
- secure-deletion behavior

**Backend-owned security behavior**:
- backend-specific salt contracts
- backend-specific key formatting or encoding rules
- backend-specific metadata/header rules
- backend-specific unlock/readiness verification

Architecture rule:
- if a security behavior exists only because SQLite/SQLCipher needs it, that behavior belongs with the SQLite implementation rather than in the shared security boundary
- startup/UI/factory code may orchestrate the flow, but should not become the home of backend-specific cryptographic behavior

### Key Derivation Function (KDF)

**Algorithm**: PBKDF2-HMAC-SHA256

**Shared Primitive Contract**:
- password bytes are derived from UTF-8 encoded user input
- salt is a caller-supplied input
- iteration count is a caller-supplied input
- output length is a caller-supplied input

This keeps the shared primitive portable across future backends. The shared primitive should validate structural correctness and clearly abusive bounds, but it should not silently hard-code backend-specific salt policy or narrow recommended ranges as if they were universal protocol rules.

The shared primitive also should not assume that password material is always present. Credential presence requirements are policy-driven and backend-dependent, not universal architectural truth.

**Backend-Owned Responsibilities**:
- decide how salt is obtained for that backend
- decide whether key-file bytes are hashed first or used in another backend-approved way
- decide the output length expected by that backend
- decide where authoritative iteration values come from for existing databases

**Pattern**:
```python
import hashlib

def derive_key(password: str, *, salt: bytes, iterations: int, length: int) -> bytes:
    """Portable PBKDF2 primitive used by backend-owned wrappers."""
    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        iterations,
        dklen=length,
    )
```

**Current SQLite/SQLCipher Example**:
- key-file mode may hash the selected key-file bytes with SHA-256 and use that digest as the salt
- password-only mode may use a SQLite-owned default salt contract
- SQLite/SQLCipher currently expects a 32-byte output suitable for AES-256-backed database encryption
- those rules are current backend-owned behavior, not the permanent generic KDF contract

**Why PBKDF2**:
- Standard KDF algorithm (NIST approved)
- Computationally expensive (configurable iterations, default 100k = ~100ms)
- Available through Python stdlib `hashlib.pbkdf2_hmac`, keeping the shared primitive dependency-light and portable
- Brute-force resistant
- Configurable iteration count allows future-proofing as hardware improves

**Alternatives Considered**:
- Argon2: Better resistance, but less portable (C library)
- Scrypt: Memory-hard, but PBKDF2 sufficient with configurable iterations

**Future-Proofing Note**: 
- Recommended iteration defaults can rise over time as hardware changes
- As computers get faster, recommended defaults should be revisited
- Configurable iterations allow administrators and future backends to increase cost where appropriate
- The architectural rule is that recommendation/policy and backend authority should stay explicit rather than being hidden inside a supposedly generic primitive

---

## Application Startup Flow

### Generic Startup Sequence

```
App Startup
    ↓
Load config.ini convenience state + bootstrap memory (if present)
    ↓
Resolve startup UI state:
 - no remembered DB => show empty create/select flow
 - remembered DB valid => prefill create/select flow
 - remembered DB malformed => drop bad values, keep startup UI usable
    ↓
User confirms or edits selected database technology
    ↓
Startup UI becomes technology-specific
 - visible fields depend on chosen technology
 - file pickers may exist or not
 - auth inputs may differ by technology
 - target/connection entries may differ by technology
    ↓
Create flow validates chosen setup against:
 - allowed technologies
 - admin-defined credential policy envelope
 - selected backend support
    ↓
If allowed but weak => UI may warn/guidance without blocking
    ↓
User confirms target + required readiness inputs for selected technology
    ↓
Selected backend readiness/open flow runs
    ↓
Success?                         Failure?
    ↓                               ↓
Create repositories            Return to recovery-capable
and continue loading           startup UI with useful feedback
application
```

### Current SQLite/SQLCipher Example

The following is a **current-phase example**, not the universal startup contract for all future backends.

For the current SQLite/SQLCipher path:
- remembered `[DEFAULT].db_type=sqlite` and `[sqlite].database_path` may prefill the startup UI
- remembered `[sqlite].require_key_file` may affect which unlock controls are shown
- the UI may allow no credentials, password only, key file only, or password + key file, depending on current admin policy and SQLite support
- for SQLite, create versus unlock is inferred from whether the selected target already exists, rather than chosen through a separate global mode selector
- after the user confirms the target and credentials, SQLCipher-specific readiness happens via `PRAGMA key` and a simple verification query

**Current SQLite unlock UI location**: `src/gui/dialogs/key_dialog.py`
- Modal dialog, blocks application startup
- Cannot be closed without providing credentials or exiting
- Shows password strength indicator (Phase 2)
- File picker DOES NOT remembers last directory (security)

**Current SQLite error handling**:
- Wrong password/file: Clear error message, allow unlimited retries
- File not found: Specific error, allow file selection again
- File unreadable: Permission error shown
- **NO attempt limiting** - Provides no real security (attacker can modify code/config)

### Bootstrap Memory Contract

`config.ini` is a **convenience layer**, not an authority layer.

It exists for three reasons only:
1. **UI/app convenience state** - window position, size, and similar non-critical UX memory
2. **Security creation defaults / policy inputs** - admin-overridden defaults and allowed-policy inputs for creating NEW encrypted databases
3. **Bootstrap memory** - remembered last-used database technology/target and related startup hints used to prefill the startup UI

This means:
- the application must still be able to start when bootstrap memory is missing
- the application must still be able to start when bootstrap memory is malformed
- remembered bootstrap values are **prefill hints for the startup UX**, not mandatory truth
- the startup UI must always provide a recovery path where the user can create a new database or manually select an existing one
- remembered bootstrap values must not hardcode one backend's field set into the generic startup contract
- creation-time policy inputs in config may shape what can be created next on this machine, but they are not the authoritative rules for an already-created database

### Startup Recovery States

The approved recovery model is:

1. **No remembered database**
   - Show startup/bootstrap UI with empty or safe default selections
2. **Remembered database values are valid**
   - Prefill the startup/bootstrap UI from config
3. **Remembered database values are partially malformed**
   - Keep usable remembered values, discard malformed ones, still show the startup/bootstrap UI
4. **Remembered database values are unusable**
   - Fall back to manual create/select flow without preventing application startup

Architecture consequence:
- malformed bootstrap memory may block automatic repository creation
- malformed bootstrap memory must **not** block the application from reaching a usable recovery/startup UI
- the generic startup contract chooses technology first, then allows that technology to define the relevant UI inputs and readiness flow

**Security Note**: Database must be opened to read unencrypted schema metadata (like table names)
- Bootstrap problem: The startup shell needs remembered hints before backend-specific readiness can begin
- **Solution**: Store bootstrap memory in `config.ini` as convenience-only startup hints, select the technology first, then let the chosen backend/UI flow determine which target details and credential inputs are relevant

**See**: `security_design.md` for security_config schema details

---

## Database Connection Pattern

### Standard Connection (with Encryption)

**Location**: `src/db/repositories/sqlite_eventlog_repository.py`

**Pattern**:
- Open a SQLCipher-backed connection for the selected SQLite target.
- Apply the backend-owned key/open command immediately after connecting.
- Run a lightweight verification query so wrong key material fails before normal repository work begins.
- Only after successful verification should the repository expose normal CRUD/query behavior.

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
5. Preserve external key files
   - Key files are user-owned external inputs, not reset-managed app artifacts
   - `Nollställ` must not delete an arbitrary file just because it was selected during bootstrap
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
- Factory pattern updated to consume shared security helpers and backend-owned security wrappers

**Pattern**:
```
Startup Flow:
  1. User enters password (+ optional key file)
  2. Shared helpers validate generic credential/file inputs
  3. Selected backend resolves its own salt/metadata rules and calls the shared KDF primitive
  4. Factory creates repository with the backend-ready key
  5. Repository applies backend-specific open/readiness steps (for SQLite/SQLCipher: `PRAGMA key` + verification query)
  6. Normal operation begins
```

**See**: `db_architecture.md` for repository factory pattern details.

**See**: `db_architecture.md` for repository pattern

### GUI Layer Integration

**Location**: `src/gui/dialogs/key_dialog.py` (new)

**Integration Points**:
- Startup: Show key dialog before main window
- Settings: Allow changing password (Phase 2)
- Nollställ: Enhanced clearing (database layer calls secure_delete)

**Minimal GUI Impact**: One dialog at startup, with GUI limited to collecting inputs and showing generic feedback while shared security and backend-owned layers perform the actual security work.

**See**: GUI architecture not updated - security architecture documents GUI needs.

---

## Dependencies

### New Dependencies

**Application**:
- `sqlcipher3>=0.6.2` - SQLCipher bindings for Python

**Shared Primitive Note**:
- The shared PBKDF2 primitive can be implemented with Python stdlib `hashlib.pbkdf2_hmac`, so a separate application dependency is not required just for generic key derivation.
- Additional crypto dependencies should only be added later if a backend-specific integration need cannot be satisfied safely with stdlib.

**Justification**: Security-critical functionality per dependency philosophy.

**Status**: Added during Epic `002` dependency bring-up after installability verification on Windows/Python 3.14.

**See**: `docs/DEPENDENCY_PHILOSOPHY.md` for updated policy

### Dependency Security

**Supply Chain Risk Mitigation**:
- Keep the dependency set minimal and justify each non-stdlib package explicitly.
- `sqlcipher3`: selected because it provides a working SQLCipher wheel for the current Windows/Python 3.14 environment.
- `cryptography`: still a strong future candidate if a backend-specific crypto need appears that stdlib cannot satisfy safely.
- Keep the shared KDF primitive stdlib-based unless a future backend-specific requirement proves that an additional dependency is necessary
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
1. **Bootstrap memory** - Remembered last-used database technology/target and related startup hints for prefilled recovery UX
2. **Defaults for NEW databases** - Used when creating databases (for example `kdf_iterations` written during creation)
3. **Administrative policy/default inputs** - Such as minimum password length, allowed credential combinations, and allowed database technologies for creation-time validation
4. **Operational conveniences** - NOT security enforcement (for example `secure_delete_passes`)

For bootstrap/security-related values, `[DEFAULT]` acts as the shared inherited fallback layer. Ordinary sections such as `[sqlite]`, `[Logging]`, and `[Application]` remain normal sections; technology sections may override shared bootstrap/security values when needed.

**Settings in database**:
- Values that actually matter (read from encrypted database)
- Cannot be tampered with without knowing encryption key
- Effective rules for an already-created database belong here rather than in later local config changes

**Settings NEVER stored**:
- Anything that would leak security info (last_key_file_path)

### Config.ini Settings

**See**: `security_design.md` for complete config.ini schema

**Highlights**:
```ini
[DEFAULT]
# Remembered/selected database technology for startup convenience
db_type = sqlite

# Whether NEW databases must use a key file when created on this machine
require_key_file_for_creation = false

# Defaults for creating NEW databases
kdf_iterations = 100000  # Written to DB header when creating DB

# Operational settings
secure_delete_passes = 3  # Convenience, not security enforcement

[sqlite]
# With the default live config at data/config.ini, the managed runtime
# SQLite database resolves beside it as data/eventlog.db.
# Remembered last-used SQLite target for startup convenience
database_path = eventlog.db

# Whether the remembered last-used SQLite target used key file mode
require_key_file = false
```

**REMOVED SETTINGS** (Provide no real security):
- ~~`max_login_attempts`~~: REMOVED - Attacker can bypass by modifying code. No value against competent attacker.

**Important**:
- `kdf_iterations` in config.ini is a **default for NEW databases only**. Actual iterations are stored in SQLCipher metadata/header state.
- `min_password_length` in config.ini is an administrator-controlled policy input used by higher layers and shared validation helpers; it is not a cryptographic protocol rule.
- the selected technology section's `require_key_file` is remembered startup memory for existing-database unlock UX, while `[DEFAULT].require_key_file_for_creation` is the create-time policy input for new databases.
- The current shared `[DEFAULT]` create-time inputs are not a guarantee that every future backend will use the same policy names or one universal global schema.
- Bootstrap memory in config.ini is a **startup convenience**. If it is missing or malformed, startup must recover through the create/select database UI rather than treating config as authoritative.

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









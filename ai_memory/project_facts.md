# Project Facts - Technical Context

**Purpose**: Technical facts about the project. Read when you need context about stack, architecture, or constraints.

---

## Project Identity

- **Name**: EventLog
- **Type**: Platoon/Company staff event logger (military operations)
- **Primary users**: Squad/platoon/company staff logging radio communications, operations, personnel
- **Environment**: Offline, local computer only, NO internet, NO cloud, NO external services

---

## Technical Stack

### Language & Version
- **Python 3.14** - Use latest stdlib features

### Dependencies
- **Application dependencies**: ZERO third-party dependencies (stdlib only!)
- **Testing dependencies**: pytest, pytest-rerunfailures
- **Rationale**: Offline environment, minimize attack surface, reduce complexity

### Separate Requirements Files
- `requirements.txt` - App dependencies (currently empty - stdlib only)
- `requirements-test.txt` - Testing/dev dependencies only
- Users shouldn't need test dependencies to run the app

### Version Specification Philosophy
- Use `>=` not `==` for versions
- Reason: No git means can't rollback, need flexibility for bug fixes
- Avoid version locking unless absolutely necessary

---

## Architecture Pattern

**Layered architecture with clear separation**:

```
GUI Layer (Tkinter)
  ↓ (Views + Presenters)
Core Layer (Business Logic)
  ↓ (Pure Python, no UI/DB knowledge)
Repository / Factory Layer
  ↓ (CRUD workflows + construction)
Database Adapter Layer
  ↓ (low-level DB mechanics)
SQLite Dialect Implementation
```

### Key Patterns
- **Adapter pattern** - Low-level database abstraction (`database_adapter.py` + `sqlite_adapter.py`)
- **Repository pattern** - Application-facing data access (`base_repository.py` + SQLite repositories)
- **Factory pattern** - Repository construction from adapter + dialect context (`repository_factory.py`)
- **View-Presenter pattern** - GUI testability (separate UI from logic)

### Layer Rules
- NO mixing of concerns
- GUI doesn't know about database
- Core doesn't know about GUI or database
- Repositories build queries and apply repository business rules
- Adapters own connection lifecycle, schema initialization, execution/fetch helpers, and transaction primitives

---

## Technology Choices

### GUI: Tkinter
- Python stdlib, no installation needed
- Lightweight, works on old hardware
- Adequate for operational needs

### Database: SQLite3
- Local file-based database
- No server needed (offline requirement)
- Python stdlib, no dependencies
- Supports encryption (when needed)
- Current concrete backend/dialect, with architecture prepared for future backends

### Database Module Direction
- `src/db/database_adapter.py` - Low-level abstract database contract and database exceptions
- `src/db/sqlite_adapter.py` - Concrete SQLite adapter for connection, schema, execution, and transactions
- `src/db/repositories/base_repository.py` - Generic repository base class, dialect-agnostic
- `src/db/repositories/repository_factory.py` - Constructs repositories from adapter + dialect context
- `src/db/repositories/sqlite/` - SQLite-specific repositories and future split points

### Testing: pytest
- Standard Python testing framework
- Supports fixtures, parameterization
- Good integration test support

### Test Strategy
- **Avoid mocking** - Use real implementations when possible
- **In-memory databases** - Tests use `:memory:` instead of mocks
- **Fixtures pattern**: conftest.py in tests/, tests/unit/, tests/integration/
- **NO separate fixtures/ folder** - That's not the pytest way

---

## Key Constraints

### No Git - Changes are Permanent
- Cannot revert mistakes
- Must be extra careful with changes
- Read before edit, validate after edit
- Think before acting

### Small Screens - Limited Display Space
- Target: Netbooks with ~1024x600 resolution
- Must support small, old hardware
- UI must be compact and efficient

### Offline Operation - No External Services
- No internet connectivity
- No cloud services
- No external APIs
- Everything must work standalone

### Field Use - Operational Tempo
- Fast data entry critical
- Real-world military operations
- Users under stress/time pressure
- UI must be efficient and clear

---

## Security Philosophy

### Realistic Threat Model
- Don't pretend plaintext files are secure
- Accept what you cannot protect (config.ini, Python source are readable)
- Remove fake security (code-based limits can be bypassed)

### Focus on Real Security
- Encryption: AES-256
- Key derivation: PBKDF2
- Key files (separate from database)
- Secure deletion when needed

### Config vs Database
- **config.ini** - Bootstrapping and defaults only (NOT security enforcement)
- **Database header** - Actual security parameters (self-describing, tamper-proof when encrypted)
- `require_key_file` in config is an administrator-defined creation/startup policy input, not a free operator preference to toggle arbitrarily in the startup UI.

### Reset Ownership Boundary
- User-selected key files are treated as external/user-owned inputs, not app-owned reset artifacts. `Nollställ` may remove app-owned database/log/bootstrap data, but it must not automatically delete an arbitrary external file just because it was used as a key file.

---

## Testing Philosophy

### Minimize Mocking
- Use real implementations when available
- In-memory databases instead of mocks
- Document all mocks with justification

### Test Types
- **Unit tests** - Can mock more, but still minimize
- **Integration tests** - Should rarely mock, use real DB/fixtures

### Fixture Organization (pytest pattern)
- `tests/conftest.py` - Global fixtures
- `tests/unit/conftest.py` - Unit test specific fixtures
- `tests/integration/conftest.py` - Integration test specific fixtures

### Flaky Tests
- Use pytest-rerunfailures for flaky tests
- Better to retry than false negatives

---

## Code Organization Principles

### Testability Priority
- Design for testability
- Separate concerns to enable testing
- Avoid tight coupling

### Clean Architecture
- Clear layer boundaries
- Dependency injection where appropriate
- Abstract interfaces for flexibility

### Explicit Over Implicit
- Clear, obvious code preferred
- Don't hide complexity
- Obvious > clever

### Configuration-Driven
- Use configuration for extensibility
- Example: method_metadata pattern
- Avoid hardcoding when config makes sense

---

## Documentation System

### Dual Documentation Strategy

**AI Documentation** (`ai_instructions/architecture/`, `ai_instructions/design/`):
- Aggressively subdivided into smaller files
- Purpose: Efficient token usage - AI reads only what it needs
- Organized by layer/component (core, db, gui, etc.)
- `ai_instructions/` belongs with the project and should stay in Git

**AI Memory** (`ai_memory/`):
- Stores persistent AI-facing project rules, learnings, and preferences
- `ai_memory/` belongs with the project and should stay in Git

**Human Documentation** (`docs/architecture/`, `docs/design/`):
- Fewer, larger, comprehensive documents
- Purpose: Easier for humans to read and understand
- Overview style with complete context

**Both must be maintained and synchronized**

### User Stories & Epics
- Location: `user_stories/ToDo/` and `user_stories/Done/`
- Framework: Goal, Limitations, Purpose
- **Purpose is most important** - The WHY enables alternatives
- Versioning: MAJOR.MINOR.MICRO (e.g., 001.001.001.md)
- Supports splitting when scope grows

### Session Logs
- One per AI session
- Incremental index: session_001.md, session_002.md, etc.
- Documents what was done, decisions made, learnings
- Local working notes only; keep `session_logs/` out of Git/deployment

### Local Config Files
- Keep `config.ini.template` tracked as the example/default shape
- Keep a machine-specific `config.ini` out of Git/deployment

---

**Last Updated**: 2026-05-04 (Session 064 - Clarified config-owned key-file policy)


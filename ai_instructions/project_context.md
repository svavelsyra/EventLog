# Project Context - AI Instructions

**When to read**: At session start for general project understanding.

---

## Project Overview

**Name**: EventLog (formerly MessageLog)  
**Type**: Desktop application for platoon staff event logging  
**Purpose**: Log radio communications, operational events, personnel tracking  
**Environment**: Offline only, single computer, NO GIT

---

## Critical Constraints

### NO GIT Repository ⚠️
- **Changes are permanent** - cannot revert
- Be extra careful before editing
- Always read files before modifying
- Validate changes after editing
- Think before acting

### Offline Only
- No internet connectivity
- No external services
- No cloud features
- All data local
- Must work on crappy hardware (old netbooks ~1024x600 resolution)

---

## Technology Stack

### Application (ZERO third-party dependencies!)
- **Python**: 3.14
- **GUI**: Tkinter (stdlib)
- **Database**: SQLite3 (stdlib)
- **Everything else**: Python stdlib only

### Testing & Development Only
- **pytest** (>=8.1.1) - Test framework
- **pytest-cov** (>=4.1.0) - Coverage reporting
- **pytest-rerunfailures** (>=14.0) - Flaky test retries

---

## Dependency Philosophy - CRITICAL!

### Core Principle: Minimize Third-Party Dependencies

**Always ask FIRST**:
1. Can Python stdlib do this?
2. Can we implement it ourselves?
3. Is it absolutely necessary?
4. Is it widely used and stable?
5. Does it have minimal dependencies itself?

### Good Reasons to Add Dependency
✅ Complex functionality (image processing, PDF generation)  
✅ Security-critical code (cryptography)  
✅ Testing tools (in requirements-test.txt only)  
✅ Well-established, widely-used libraries  
✅ Saves significant development time without adding risk

### Bad Reasons to Add Dependency
❌ "I'm used to this library"  
❌ Saves 5 lines of code  
❌ "Everyone uses it" (but stdlib can do it)  
❌ Trendy/new/exciting library  
❌ Library does 100 things but we only need 1

### Context Matters!
**Question isn't "Is this a good library?" but "Do we need it?"**

Examples:
- **Requests**: Fantastic library! But we're offline-only (no HTTP needed)
- **NumPy/Pandas**: Powerful! But overkill for our use case
- **Pillow**: Excellent! But we don't handle images

### Decision Criterion
**Decision criterion**: "Do we need it?" not "Is it good?"

See `docs/DEPENDENCY_PHILOSOPHY.md` for full details.

---

## Architecture Pattern

**Layered Architecture**: GUI → Core → DB Adapters → DB Repositories

```
GUI Layer (Tkinter)
├── Views (pure UI, no business logic)
└── Presenters (MVP pattern, coordinates between view and core)
    ↓
Core Layer (Business Logic)
├── Domain models
├── Validation rules
└── Business operations
    ↓
DB Adapter Layer (Abstract Interface)
└── Abstract base classes defining data operations
    ↓
DB Repository Layer (SQLite Implementation)
└── Concrete SQLite implementations
```

### Key Patterns
- **MVP (Model-View-Presenter)** - For GUI testability
- **Adapter Pattern** - Abstract database interface
- **Repository Pattern** - Concrete data access
- **Factory Pattern** - Creating connections and repositories

---

## Project Structure

```
src/
├── gui/              # GUI layer (Views + Presenters)
│   ├── views/        # Pure UI components
│   └── presenters/   # MVP presenters
├── core/             # Business logic (domain models, rules)
└── db/               # Database layer
    ├── adapters/     # Abstract base classes
    └── repositories/ # SQLite implementations

tests/
├── conftest.py       # Global pytest fixtures
├── unit/             # Unit tests
│   └── conftest.py   # Unit-specific fixtures
└── integration/      # Integration tests
    └── conftest.py   # Integration-specific fixtures
```

---

## Testing Philosophy

### Minimize Mocking
- ✅ Avoid mocking whenever possible
- ✅ Use **in-memory SQLite databases** for tests instead
- ✅ Use fixtures and transactions for test data
- ✅ Unit tests can mock minimally
- ✅ Integration tests should rarely mock
- ✅ **Document all mocks** with justification

### Fixture Organization (pytest pattern)
- `tests/conftest.py` - Global fixtures
- `tests/unit/conftest.py` - Unit test specific
- `tests/integration/conftest.py` - Integration test specific
- ❌ **NO separate fixtures/ folder** - not the pytest way

---

## Domain Context (Military Operations)

### Swedish Military Terms
- **7S Report** (SjuSrapport) - Standard observation report:
  - Stund (When), Ställe (Where), Styrka (Strength), Slag (Type)
  - Sysselsättning (Activity), Symbol (Markings), Sagesman (Observer)
- **Radio procedures**: DART (data messages) vs Speech transmission
- **Unit designations**: Pluton, Grupp, Kompani, callsigns

### Operational Context
- **Fast data entry is critical** - Operational tempo
- **Small screens** - Netbooks ~1024x600 resolution support required
- **Field use** - Practical, real-world constraints
- **Check-in tracking** - Personnel away need regular contact monitoring
- **Historical accuracy** - Logs preserve what was configured at time of logging

---

## Demo Application

**Location**: `Demo/demo_app.py`

### ⚠️ Important: Demo is UI Mockup Only!

**Purpose**:
- Visual layout reference
- Swedish terminology
- Field naming examples

**DO**:
✅ Reference demo for visual layout  
✅ Use demo for Swedish field naming  
✅ Follow architecture/design docs for implementation

**DO NOT**:
❌ Copy demo code (monolithic, no architecture)  
❌ Use demo's hardcoded values literally  
❌ Treat demo as implementation specification

**See**: `Demo/UI_REFERENCE.md` for mapping demo UI to actual implementation specs

---

## Swedish UI Terms (From Demo)

- **Kommunikation** - Communications
- **Händelser** - Events
- **Personal** - Personnel
- **Nollställ** - Emergency data clear
- **Lås upp** - Unlock
- **Bläddra** - Browse
- **Spara** - Save
- **Rensa** - Clear
- **Operatör** - Operator
- **TNR** - Tid (Time) in DDHHMM format

---

## Configuration Philosophy

### config.ini (Bootstrapping ONLY)
- Window position/size
- Last used database path
- **NOT for security enforcement**
- **NOT for functional requirements**

### Database (Everything Else)
- Unit call sign
- Communication systems, methods, channels
- Frequent contacts
- User preferences
- Security parameters (self-describing, tamper-proof)
- **Database header stores actual security parameters**

---

## Key Project Files

### Human Documentation
- `README.md` - Project overview
- `docs/architecture/root_architecture.md` - Full architecture
- `docs/design/root_design.md` - Full design
- `docs/DEPENDENCY_PHILOSOPHY.md` - Dependency decisions

### Demo & Reference
- `Demo/demo_app.py` - UI mockup (visual reference only!)
- `Demo/README.md` - Demo explanation
- `Demo/UI_REFERENCE.md` - Maps demo to implementation specs

---

## Remember

- **NO GIT** - Changes are permanent!
- **Offline only** - No network functionality
- **ZERO third-party dependencies** for app
- **Minimize mocking** in tests
- **Demo is UI reference only** - not implementation specification
- **Small, iterative patches** - User preference
- **Aggressively suggest story splitting** - Core user preference


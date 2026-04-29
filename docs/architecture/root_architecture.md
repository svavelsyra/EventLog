# EventLog - Root Architecture Document

**Project**: Platoon Event Logger  
**Version**: 1.0  
**Last Updated**: 2026-04-28  

## Purpose
A desktop application for logging events during platoon staff operations. This includes:
- Radio communication (messages sent/received)
- Operational events (patrols departing/returning, orders given)
- Personnel tracking (location and activity of personnel and groups)
- Other significant events requiring documentation

Radio communication logging is a major use case, but the application serves as a general event logger for maintaining situational awareness and operational records.

## Architectural Principles

### 1. Layered Architecture
The application follows a strict layered architecture with clear separation of concerns:

```
┌─────────────────────────────────────┐
│         GUI Layer (Tkinter)         │
│    Views + Presenters (MVP)         │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│         Core/Business Layer         │
│     (Business Logic & Rules)        │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│      Repository / Factory Layer     │
│  (BaseRepository + concrete repos)  │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│       Database Adapter Layer        │
│ (DatabaseAdapter + SQLiteAdapter)   │
└─────────────────────────────────────┘
```

### 2. Dependency Rule
- **Higher layers depend on lower layers**, never the reverse
- **Lower layers know nothing about higher layers**
- Communication upward through **callbacks/observers** if needed

### 3. Design Patterns

#### Adapter Pattern
- Low-level abstract database adapter defines connection, schema, execution, fetch, and transaction operations
- Enables swapping database implementations
- Centralizes database-specific exceptions and backend mechanics
- Concrete adapter handles backend-specific details such as SQLite connection lifecycle and schema initialization

#### Repository Pattern
- Encapsulates data access logic
- Provides the application-facing CRUD-style interface for data operations
- Builds SQL queries and applies repository business rules
- Delegates SQL execution and transaction mechanics downward to the adapter
- Current SQLite runtime path uses `EventLogRepository` as the single active concrete repository implementation
- One concrete repository is enough for now, but it should be easy to split by area later if growth or test scope requires it
- Repository business rules may read low-level configuration from the database `settings` table (for example the edited-flag grace period stored in seconds)

#### Factory Pattern
- `RepositoryFactory` currently constructs `EventLogRepository` with a `SQLiteAdapter`
- Keeps backend selection and repository construction out of higher layers
- Creates a future extension point even while SQLite is the only current dialect
- Current factory/bootstrap wiring is still transitional at the startup-policy level, but the legacy SQLite repository compatibility shell is no longer part of the active architecture

#### Model-View-Presenter (MVP)
- **View**: Pure UI, no business logic
- **Presenter**: Handles user interactions, coordinates Model and View
- **Model**: Business objects and logic (Core layer)
- Enables testing presenters without GUI

## Technology Stack
- **Language**: Python 3.14
- **GUI**: Tkinter (standard library)
- **Database**: SQLite3 currently, with architecture prepared for future backends
- **Testing**: pytest (unit + integration)
- **Deployment**: Single machine, offline, no Git

## Current Database Runtime Shape
- `RepositoryFactory` is the current construction seam for repository creation
- `SQLiteAdapter` owns connection lifecycle, schema initialization, SQL execution primitives, and transaction primitives
- `EventLogRepository` owns CRUD workflows, query behavior, row mapping, and repository-level business rules
- Remaining transition work is primarily about startup/version policy refinement and future repository splitting, not legacy repository compatibility

## Key Constraints
- ✅ Offline only - no network dependencies
- ✅ Local database - single user
- ✅ No version control - careful change management required
- ✅ Desktop application - not web-based

## Further Architecture Documentation
- Detailed split-out human architecture documents are not yet created.
- This root document is currently the human-facing architecture summary.
- The AI-maintained database architecture detail currently lives in `ai_instructions/architecture/db_architecture.md` until the human architecture docs are split further.

## Design Documents
See `docs/design/root_design.md` for design decisions and detailed designs.


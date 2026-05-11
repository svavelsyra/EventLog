# EventLog - Root Architecture Document

**Project**: Platoon Event Logger  
**Version**: 1.0  
**Last Updated**: 2026-05-07  

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

**Planned long-term direction**:
- The preferred long-term split is one repository for communications, one for events, and one for personnel because those are the main operational areas and the main GUI workflow areas.
- If `EventLogRepository` remains after that split, it should become a deliberately small shared/configuration repository or thin facade rather than staying a fourth large catch-all CRUD surface.
- Shared/configuration ownership may include communication configuration, repository `settings`, and other cross-cutting operational metadata that does not belong cleanly to only one of the three main workflow repositories.
- Startup/bootstrap backend-policy ownership remains outside that shared/configuration role and stays with `src/db/repositories/bootstrap_backend_policy.py`.

#### Factory Pattern
- `src/db/repositories/bootstrap_backend_policy.py` is the centralized startup/bootstrap backend-policy seam
- It owns supported-dialect facts, startup field requirements, remembered-target normalization/persistence behavior, coarse startup capability facts, and per-dialect repository creation dispatch
- `RepositoryFactory` now stays a thinner construction facade over that centralized policy seam
- Creates a future extension point even while SQLite is the only current dialect
- The earlier temporary bootstrap target wrapper modules are no longer part of the active architecture

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
- `bootstrap_backend_policy.py` is the current ownership seam for startup/bootstrap backend policy and repository-creation dispatch
- `RepositoryFactory` is the thin construction facade used by higher-level bootstrap orchestration
- `SQLiteAdapter` owns connection lifecycle, schema initialization, SQL execution primitives, and transaction primitives
- `EventLogRepository` owns CRUD workflows, query behavior, row mapping, and repository-level business rules
- Remaining transition work is primarily about startup/version policy refinement and future repository splitting, not legacy repository compatibility

## Planned Repository Boundary Direction
- **Current implementation**: one concrete SQLite repository (`EventLogRepository`) still owns the application's CRUD/query behavior.
- **Preferred future split**:
  - `CommunicationRepository` - communication entries plus communication-specific configuration reads/writes
  - `EventRepository` - event entries and closely related event-owned persistence behavior
  - `PersonnelRepository` - personnel history, active-state, and alarm workflows
  - `EventLogRepository` only if kept as a thin shared/configuration seam or facade
- The shared/configuration role should stay intentionally narrow and must not become a second monolithic repository after the split.
- If that shared role grows beyond a small cross-cutting seam, it should be renamed more explicitly (for example toward a configuration-focused repository name) rather than leaving a misleading broad `EventLogRepository` name in place.

## Startup and Bootstrap Contract

- `config.ini` is a convenience layer, not an authority layer.
- The application must always be able to start even when remembered bootstrap values are missing or malformed.
- Startup begins by resolving the selected database technology, using remembered values only as prefill hints.
- The startup UI is dynamic: once a technology is selected, the UI decides which target fields, selectors, file pickers, and authentication inputs are relevant for that technology.
- Persistence-owned startup capability seams may expose only stable technical startup requirements such as field identity, input kind, and required/editable flags.
- The centralized persistence-owned startup policy seam is `src/db/repositories/bootstrap_backend_policy.py`; app wiring and presenters should depend on that seam instead of splitting startup facts across multiple helper modules.
- GUI code owns display labels, button wording, and browse-button behavior derived from those stable startup field identities; presenter-facing field-label metadata must not leak downward into persistence contracts.
- Startup dialog interaction is GUI-owned above that persistence seam: presenters recompute dialog state, views render that state, and controller/app wiring read one structured submission back from the view.
- The preferred startup GUI boundary is state-driven rendering plus structured submission readback, not per-field getter/setter or callback growth as each dynamic field is added.
- The create flow validates the operator's selected setup against the administrator-defined creation-time policy envelope, including allowed technologies and allowed credential combinations.
- Repository creation happens only after the selected technology-specific startup flow has collected and validated enough information to proceed.
- Malformed bootstrap memory may prevent automatic repository creation, but it must not prevent the application from reaching a usable recovery/startup UI.

### Startup GUI Ownership

- The startup presenter owns dynamic decisions such as remembered-target use, visible startup fields, allowed modes, and presenter-controlled prefill values.
- The startup view stays thin: it renders presenter state, captures operator input, manages focus/layout/widgets, and exposes structured readback.
- The startup controller stays a thin adapter that wires callbacks, requests submissions, asks the presenter for recomputed state, and re-renders.
- This split keeps backend-policy facts technical and stable while allowing the startup UI to remain dynamic without pushing Tk details into persistence.

### Policy Ownership

- The application should guide users toward sensible and safer choices, but it should not hard-code one universal workflow that ignores operational reality.
- Administrators define the allowed policy envelope for creating new databases, including allowed technologies and minimum credential requirements.
- Operators then choose a concrete setup within that envelope.
- Once a database has been created, that database's own protected state becomes the authoritative source for its effective rules.
- Later changes to local config may affect future database creation on that machine, but they are not retroactive authority over already-created databases.

## Security Boundary and Ownership

- Security-relevant code should remain reviewable as a deliberate boundary rather than being scattered across GUI, repository, and configuration code.
- Shared security code exists to make future audit scope obvious: reviewers should be able to inspect the common security primitives without also tracing unrelated application behavior.
- The shared security boundary should contain only cross-technology security concerns such as generic key-derivation primitives, secret-material handling helpers, generic credential/file validation helpers, shared security exceptions, and secure-deletion behavior.
- Backend-specific security behavior belongs with the backend that owns it. If SQLite/SQLCipher requires a particular salt contract, key formatting rule, metadata rule, or unlock/readiness check, that behavior should live with the SQLite implementation rather than in the shared security boundary.
- GUI and startup orchestration may collect credentials and display generic error messages, but they should not own backend-specific cryptographic behavior.
- Configuration parsing may supply policy inputs and defaults, but it should not silently become the place where backend-specific security behavior is defined.

### Primitive vs Policy Split

- Low-level shared security helpers should enforce structural validity and abuse-protection limits only.
- Higher layers may still define recommended defaults and administrative policy, but those policies should be passed into helpers explicitly rather than being hidden as hard-coded assumptions in low-level primitives.
- Password policy remains intentionally minimal: administrators may define a minimum length in configuration, but the architecture does not require composition rules such as uppercase, digits, or symbols.
- Allowed credential combinations are policy-driven rather than hard-coded: depending on admin policy and backend support, a database may be created with no credential material, password only, key file only, or password + key file.
- Generic key derivation should stay portable so future backends can reuse the primitive while still owning their own backend-specific salt, metadata, and readiness rules.

### Remembered Config Roles

- **UI/app convenience state**: window size, position, and similar non-critical memory
- **Security creation defaults / policy inputs**: admin-overridden defaults and allowed-policy guidance used when creating NEW encrypted databases
- **Bootstrap memory**: remembered last-used database technology/target and related startup hints used to prefill the startup UI

### Recovery States

- **No remembered database**: show startup UI with empty or safe defaults
- **Remembered values valid**: prefill startup UI from config
- **Remembered values partially malformed**: keep usable values, discard invalid ones, keep startup UI usable
- **Remembered values unusable**: fall back to manual create/select flow without blocking startup

### Current Phase Note

- SQLite is the only currently implemented backend, so some current startup examples naturally mention file paths, SQLCipher, and key-file-driven unlock behavior.
- Those are current-technology details, not universal startup rules for all future backends.
- Architecture must keep the technology-selection step generic so a different backend can later provide a different startup form and readiness flow.
- The same rule applies to security documentation and implementation ownership: SQLite-specific security behavior is allowed, but it should be labeled and located as SQLite-owned behavior rather than being presented as the permanent generic security contract.

## Attachment Security Boundary
- Phase 1 attachment content belongs inside the encrypted database boundary, together with its attachment metadata.
- Plaintext filesystem attachment directories are not part of the approved secure architecture.
- If large-attachment support is ever approved later, it must use separately encrypted external storage rather than a fallback to normal readable files.

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


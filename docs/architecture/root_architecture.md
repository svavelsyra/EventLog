# EventLog - Root Architecture Document

**Project**: Platoon Event Logger  
**Version**: 1.0  
**Last Updated**: 2026-04-17  

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
│      Database Adapter Layer         │
│   (Abstract Base Classes/Interfaces)│
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│    Database Implementation Layer    │
│   (SQLite Repository Pattern)       │
└─────────────────────────────────────┘
```

### 2. Dependency Rule
- **Higher layers depend on lower layers**, never the reverse
- **Lower layers know nothing about higher layers**
- Communication upward through **callbacks/observers** if needed

### 3. Design Patterns

#### Adapter Pattern
- Abstract base class defines ALL database operations
- Enables swapping database implementations
- Facilitates testing with in-memory implementations
- Factory method to get concrete implementation (e.g., SQLite)

#### Repository Pattern
- Encapsulates data access logic
- Provides collection-like interface for data operations
- Hides database-specific query details
- Factory method to get repository instance (e.g., SQLiteRepository)

#### Model-View-Presenter (MVP)
- **View**: Pure UI, no business logic
- **Presenter**: Handles user interactions, coordinates Model and View
- **Model**: Business objects and logic (Core layer)
- Enables testing presenters without GUI

## Technology Stack
- **Language**: Python 3.14
- **GUI**: Tkinter (standard library)
- **Database**: SQLite3 (file-based, local)
- **Testing**: pytest (unit + integration)
- **Deployment**: Single machine, offline, no Git

## Key Constraints
- ✅ Offline only - no network dependencies
- ✅ Local database - single user
- ✅ No version control - careful change management required
- ✅ Desktop application - not web-based

## Further Architecture Documentation
- **GUI Architecture**: See `docs/architecture/gui_architecture.md`
- **Core Architecture**: See `docs/architecture/core_architecture.md`
- **Database Architecture**: See `docs/architecture/database_architecture.md`
- **Testing Architecture**: See `docs/architecture/testing_architecture.md`

## Design Documents
See `docs/design/root_design.md` for design decisions and detailed designs.


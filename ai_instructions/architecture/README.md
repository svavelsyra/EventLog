# AI Architecture Index

**For AI Use Only** - This architecture documentation is subdivided for efficient token usage.

## Purpose
These documents provide architecture information for AI assistants working on the EventLog project. They are intentionally split into smaller, focused documents so AI can read only what it needs for the current task.

## Architecture Documents

### Core Architecture
- `core_architecture.md` - Business logic layer architecture
  - Domain models
  - Business rules
  - Validation logic

### Database Architecture  
- `db_architecture.md` - Data access layer architecture
  - Adapter pattern details
  - Repository pattern details
  - Database schema
  - Transaction management

### GUI Architecture
- `gui_architecture.md` - User interface layer architecture
  - MVP (Model-View-Presenter) pattern
  - View components
  - Presenter components
  - Event handling

### Testing Architecture
- `testing_architecture.md` - Test organization and patterns
  - Test structure
  - Fixture organization
  - In-memory database strategy
  - Test isolation patterns

### Logging Architecture
- `logging_architecture.md` - Logging infrastructure and privacy
  - Configuration (config.ini)
  - File rotation setup
  - Privacy requirements (NO user data)
  - Clear all data feature

## When to Read What

| Working on... | Read... |
|---------------|---------|
| Domain models, business logic | `core_architecture.md` |
| Database operations, queries | `db_architecture.md` |
| GUI, user interactions | `gui_architecture.md` |
| Writing tests | `testing_architecture.md` |
| Logging, config, clear data | `logging_architecture.md` |
| General overview | All files (but start with what you need) |

## Related Documentation
- **Human architecture docs**: `docs/architecture/root_architecture.md` (comprehensive overview for humans)
- **Design docs**: `ai_instructions/design/` (AI-specific design docs)

---

**Note**: AI should keep both AI docs (this folder) AND human docs (`docs/architecture/`) up to date.


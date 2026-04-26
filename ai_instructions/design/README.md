# AI Design Index

**For AI Use Only** - This design documentation is subdivided for efficient token usage.

## Purpose
These documents provide design information for AI assistants working on the EventLog project. They are intentionally split into smaller, focused documents so AI can read only what it needs for the current task.

## Design Documents

### Core Design
- `core_design.md` - Domain model and business logic design
  - EventLogEntry entity
  - Field definitions
  - Business rules
  - Validation logic

### Database Design
- `db_design.md` - Database schema and data access design
  - Table structures
  - Indexes
  - Relationships
  - Query patterns
  - CRUD operations

### GUI Design
- `gui_design.md` - User interface design
  - Window layout
  - Form design
  - List/table views
  - User interactions
  - Dialogs

## When to Read What

| Working on... | Read... |
|---------------|---------|
| Domain entities, validation | `core_design.md` |
| Database schema, queries | `db_design.md` |
| UI components, forms | `gui_design.md` |
| General overview | All files (but start with what you need) |

## Related Documentation
- **Human design docs**: `docs/design/root_design.md` (comprehensive overview for humans)
- **Architecture docs**: `ai_instructions/architecture/` (AI-specific architecture docs)

---

**Note**: AI should keep both AI docs (this folder) AND human docs (`docs/design/`) up to date.


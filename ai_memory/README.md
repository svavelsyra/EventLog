# AI Memory Structure

**Purpose**: Efficient token usage - AI reads only what it needs for current task.

## File Organization

### `user_preferences.md` - General AI Behavior
**Read**: At start of every session

**Contains**:
- How AI should communicate with user
- When to act vs ask
- Safety and care guidelines
- Documentation preferences
- Domain knowledge (Swedish military, operational context)
- General DO's and DON'Ts

**Does NOT contain**:
- Architecture decisions → go in `ai_instructions/architecture/`
- Design specifications → go in `ai_instructions/design/`
- Implementation patterns → go in specialized learning files below

### `gui_learnings.md` - GUI Implementation Lessons
**Read**: When working on GUI implementation

**Contains**:
- Tkinter-specific patterns and pitfalls
- Layout lessons (grid, pack, place)
- Widget-specific gotchas
- Common mistakes and fixes
- UI implementation patterns

### `core_learnings.md` - Business Logic Lessons
**Read**: When working on core/business logic

**Contains**:
- Validation patterns
- Business rule implementation
- Entity handling patterns
- Common logic mistakes
- Error handling approaches

### `db_learnings.md` - Database Implementation Lessons
**Read**: When working on database layer

**Contains**:
- SQLite-specific patterns
- Query optimization
- Transaction handling
- Migration patterns
- Connection management

## Usage Pattern

**At session start**:
1. Always read `user_preferences.md`
2. Check latest `session_logs/session_XXX.md`

**During implementation**:
- Working on GUI? Read `gui_learnings.md`
- Working on core logic? Read `core_learnings.md`
- Working on database? Read `db_learnings.md`

**After learning something new**:
- Update appropriate specialized file
- Keep lessons focused on implementation, not architecture

## Philosophy

**Token Efficiency**: Same principle as architecture/design docs - subdivide by layer/component so AI only reads what's needed.

**Clear Separation**:
- **Architecture** (`ai_instructions/architecture/`) - What and why
- **Design** (`ai_instructions/design/`) - Detailed how
- **Memory** (`ai_memory/`) - Lessons learned and AI behavior

**Keep it Focused**: If `user_preferences.md` is growing with technical details, move them to specialized learning files.


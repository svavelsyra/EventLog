# AI Instructions - EventLog Project

**Read this file first when starting any session on this project.**

## Project Quick Facts
- **Name**: EventLog (Platoon Event Logger)
- **Type**: Python 3.14 desktop application
- **Status**: Structure complete, implementation pending
- **Environment**: Offline only, NO GIT (changes are permanent!)

## Critical Context Files

### Always Read First
1. **Behavioral Rules**: `ai_memory/behavioral_rules.md` - Critical decision-making rules and workflow constraints
2. **Latest Session**: `session_logs/session_XXX.md` - What happened in the last session

### Read When Needed
- **Testing**: `ai_instructions/testing.md` - When writing or discussing tests
- **Architecture**: `docs/architecture/root_architecture.md` - For architecture questions
- **Design**: `docs/design/root_design.md` - For design decisions
- **Dependency Philosophy**: `docs/DEPENDENCY_PHILOSOPHY.md` - Before adding dependencies

## Session Protocol
1. Create new session log: `session_logs/session_XXX.md` (increment number)
2. Read `ai_memory/behavioral_rules.md`
3. Check last session log to understand recent work
4. Update the appropriate `ai_memory/*.md` file when you learn new preferences or patterns

## Key Rules
- ⚠️ **NO GIT** - Changes are permanent, validate everything
- ✅ **Update AI memory aggressively** - Document user preferences immediately
- ✅ **Architecture/Design docs are NOT AI memory** - Keep them separate
- ✅ **Read before editing** - Always read files before making changes
- ✅ **Validate after editing** - Use get_errors to check your work

## File Organization

### AI-Specific Files (For AI Context Management)
- `.ai/instructions.md` - This file (main AI entry point)
- `ai_instructions/*.md` - Specialized AI instructions
- `ai_memory/*.md` - AI learnings and user preferences
- `session_logs/*.md` - Session history

### Human Documentation (For Developers)
- `README.md` - Project overview for humans
- `docs/` - All human-readable documentation
- Configuration files in root

## Where Information Lives
| What | AI Version (Subdivided) | Human Version (Comprehensive) |
|------|------------------------|-------------------------------|
| Architecture | `ai_instructions/architecture/*.md` | `docs/architecture/root_architecture.md` |
| Design | `ai_instructions/design/*.md` | `docs/design/root_design.md` |
| Behavioral rules / AI memory | `ai_memory/*.md` | N/A |
| Session history | `session_logs/session_XXX.md` | N/A |
| Testing (AI) | `ai_instructions/testing.md` | N/A |

## Tech Stack
- Python 3.14 (stdlib only, zero third-party dependencies for app)
- Tkinter (GUI)
- SQLite3 (database)
- pytest (testing only)

## Architecture Pattern
**GUI (Views + Presenters) → Core (Business Logic) → Repository / Factory Layer → Database Adapter Layer → SQLite dialect implementation**

---

**Remember**: 
1. AI documentation is **subdivided for efficiency** - read only what you need for the current task.
2. Human documentation (`docs/`) is **comprehensive for readability** - fewer, larger files.
3. **Keep BOTH synchronized** - update both AI and human docs when making architecture/design changes.





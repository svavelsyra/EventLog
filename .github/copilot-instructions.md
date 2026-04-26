# AI Instructions - EventLog Project

**This file is automatically read by GitHub Copilot on every session.**

## Project Overview
- **Name**: EventLog (Platoon Event Logger)
- **Type**: Python 3.14 desktop application
- **Status**: Structure complete, implementation pending
- **Environment**: Offline only, NO GIT (changes are permanent!)

## Critical: Read These Files First

### Always Read At Session Start
1. **Behavioral Rules**: `ai_memory/behavioral_rules.md` - **CRITICAL** decision-making rules, MUST READ FIRST
2. **Latest Session Log**: Check `session_logs/` for most recent session

### Session Protocol
**Session definition**: A session lasts from when the current AI instance starts until the user starts a new instance. Topic changes or side tracks within the same instance are still part of that same session.

1. Read `ai_memory/behavioral_rules.md` (REQUIRED - contains decision tree for all AI actions)
2. Check latest session log in `session_logs/` to understand recent work
3. Create new session log: `session_logs/session_XXX.md` (increment number)
4. Update appropriate AI memory file when you learn new patterns

### AI Memory Files (Read Based on Need)
- `behavioral_rules.md` - **READ FIRST EVERY SESSION** - How to make decisions, when to act vs ask
- `project_facts.md` - Read when needing technical context (stack, architecture, constraints)
- `domain_knowledge.md` - Read when working on features (military context, operational requirements)
- `story_writing_rules.md` - Read when creating/editing user stories
- `gui_learnings.md` - Read when implementing GUI (Tkinter patterns)
- `core_learnings.md` - Read when implementing business logic
- `db_learnings.md` - Read when implementing database layer

## Read When Needed
- **User Stories**: `ai_instructions/user_stories.md` - When creating or implementing user stories/epics
- **Testing**: `ai_instructions/testing.md` - When writing or discussing tests
- **Architecture**: Use files in `ai_instructions/architecture/` based on what you're working on:
  - `core_architecture.md` - For business logic work
  - `db_architecture.md` - For database work
  - `gui_architecture.md` - For GUI work
  - `testing_architecture.md` - For test organization
- **Design**: Use files in `ai_instructions/design/` based on what you're working on:
  - `core_design.md` - For domain models
  - `db_design.md` - For database schema
  - `gui_design.md` - For UI layout
- **Human Docs**: `docs/architecture/root_architecture.md` and `docs/design/root_design.md` for comprehensive overview

## Critical Rules
- ⚠️ **NO GIT** - Changes are permanent, validate everything before acting
- ✅ **Read before editing** - Always read files before making changes
- ✅ **Validate after editing** - Use get_errors to check your work
- ✅ **Update AI memory aggressively** - Document user preferences immediately
- ✅ **Architecture/Design docs are NOT AI memory** - Keep them separate
- ❌ **Don't make massive changes without discussion**
- ❌ **Don't invent designs/implementations without user input**

## Tech Stack
- Python 3.14 (stdlib only for app, zero third-party dependencies)
- Tkinter (GUI)
- SQLite3 (database)
- pytest (testing only)

## Architecture Pattern
**GUI (Views + Presenters) → Core (Business Logic) → DB Adapters (Interface) → DB Repositories (SQLite)**

## Documentation Philosophy

### AI Documentation (Subdivided for Efficiency)
- `ai_instructions/architecture/*.md` - Read only what you need for current task
- `ai_instructions/design/*.md` - Read only what you need for current task
- `ai_memory/*.md` - User preferences and learnings
- `session_logs/*.md` - Session history

### Human Documentation (Comprehensive for Readability)
- `docs/architecture/root_architecture.md` - Full architecture overview
- `docs/design/root_design.md` - Full design overview
- `README.md` - Project overview

**Remember**: Keep BOTH AI and human docs synchronized when making changes.

---

**Start every session by reading `ai_memory/behavioral_rules.md` - it contains the decision tree for all AI actions!**


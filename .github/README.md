# GitHub Copilot Configuration

## Auto-Load File
**File**: `.github/copilot-instructions.md`

This file is **automatically read by GitHub Copilot** when starting a session in this workspace.

## How It Works

GitHub Copilot in JetBrains IDEs (PyCharm) automatically reads `.github/copilot-instructions.md` at the start of each session, providing the AI with:
- Project overview and context
- Critical files to read first
- Session protocols
- Key rules and constraints
- Architecture patterns

## What This File Does

The `copilot-instructions.md` file serves as the **main entry point** that:
1. Directs the AI to read `ai_memory/user_preferences.md` (critical user preferences)
2. Tells the AI to check the latest session log
3. Provides on-demand reading strategy for architecture/design docs
4. Lists critical rules (NO GIT, read before editing, etc.)

## File Organization

### Always Auto-Loaded
- `.github/copilot-instructions.md` ← GitHub Copilot reads this automatically

### AI Should Read Every Session
- `ai_memory/user_preferences.md` ← Critical user preferences
- Latest file in `session_logs/` ← Recent work context

### AI Should Read On-Demand
- `ai_instructions/testing.md` ← When writing tests
- `ai_instructions/architecture/*.md` ← When working on specific layers
- `ai_instructions/design/*.md` ← When working on specific components
- `docs/` ← Comprehensive human documentation

## Migration from Previous Structure

### What Changed
Previously we had:
- `.ai/instructions.md` - Attempted main entry point (not auto-loaded)
- `ai_instructions/README.md` - Root instructions (not auto-loaded)

Now we have:
- `.github/copilot-instructions.md` - **Actually auto-loaded by Copilot**
- Other files remain as on-demand reading

### Status of Old Files
- `.ai/instructions.md` - Can be removed (superseded)
- `ai_instructions/README.md` - Keep as reference/backup

## Verification

To verify GitHub Copilot is reading this file:
1. Start a new Copilot chat session
2. Ask: "What files should you read at the start of every session?"
3. The AI should mention `ai_memory/user_preferences.md` and session logs

## Documentation Structure

```
EventLog/
├── .github/
│   └── copilot-instructions.md    ← AUTO-LOADED by Copilot ⭐
├── ai_instructions/
│   ├── testing.md                 ← Read when writing tests
│   ├── architecture/              ← Read based on what you're working on
│   │   ├── core_architecture.md
│   │   ├── db_architecture.md
│   │   ├── gui_architecture.md
│   │   └── testing_architecture.md
│   └── design/                    ← Read based on what you're working on
│       ├── core_design.md
│       ├── db_design.md
│       └── gui_design.md
├── ai_memory/
│   └── user_preferences.md        ← READ EVERY SESSION
├── session_logs/
│   └── session_XXX.md             ← READ LATEST SESSION
└── docs/                          ← Read for comprehensive overview
```

## Benefits

✅ **Automatic loading** - No manual configuration needed  
✅ **Efficient context** - AI reads only what it needs, when it needs it  
✅ **Consistent sessions** - Every session starts with the same context  
✅ **Scalable** - Can add more docs without overwhelming initial context  

---

**Note**: This is the **correct** way to provide instructions to GitHub Copilot in JetBrains IDEs.


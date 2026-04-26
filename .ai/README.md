# AI Auto-Load Configuration Guide

## What Was Set Up

### Main AI Entry Point
**File**: `.ai/instructions.md`

This is the **main file** that AI assistants should automatically read when starting a session on this project.

### How It Works

1. **AI reads `.ai/instructions.md` first** (on session start)
2. This file tells the AI:
   - What the project is
   - What files to read always (user preferences, last session)
   - What files to read when needed (architecture, design, testing)
   - Key rules and constraints

3. **AI then reads files on-demand**:
   - Architecture docs when working on architecture
   - Testing docs when writing tests
   - Design docs when implementing features

### Benefits

- **Reduces token usage**: AI doesn't load everything upfront
- **Better context management**: AI knows what to read and when
- **Clear entry point**: No confusion about where to start
- **Scalable**: Can add more specialized docs without overwhelming AI

## For IDE/Editor Configuration

To make this work automatically, configure your IDE to:
1. Auto-load `.ai/instructions.md` when AI starts
2. OR include it in the system prompt for the AI
3. OR set it as a "workspace context" file

### Example Configuration
```json
{
  "ai.autoLoadFiles": [
    ".ai/instructions.md"
  ]
}
```

## File Structure

```
EventLog/
├── .ai/
│   └── instructions.md          ← MAIN AI ENTRY POINT (auto-load this)
├── ai_instructions/
│   ├── README.md               ← Legacy, read when needed
│   └── testing.md              ← Read when writing tests
├── ai_memory/
│   └── user_preferences.md     ← Read every session (per instructions.md)
├── session_logs/
│   └── session_XXX.md          ← Read latest session (per instructions.md)
└── docs/                        ← Read when needed for context
```

## What AI Does Each Session

1. **Automatically reads**: `.ai/instructions.md`
2. **Then follows instructions to read**:
   - `ai_memory/user_preferences.md`
   - Latest `session_logs/session_XXX.md`
3. **Creates new**: `session_logs/session_XXX.md` for this session
4. **Reads on-demand**: Architecture, design, testing docs as needed

## Difference from Previous Approach

### Before (Session 001)
- No clear entry point
- AI had to guess what to read
- All files seemed equally important
- Human and AI docs were confused

### Now (Session 002)
- Clear main entry point (`.ai/instructions.md`)
- AI knows what to read and when
- Clear separation: AI docs vs human docs
- Efficient context management

---

**Note**: The `.ai/instructions.md` file is designed to be read by AI at the start of EVERY session. It's brief and tells the AI everything it needs to know to get started.


# EventLog GUI Demo

This folder contains a standalone GUI demo for the EventLog application.

## What's Included

- **demo_app.py** - Complete demo with login and main GUI

## Features Demonstrated

### Login Window
- File selection for key file (accepts any file)
- Password input field (accepts any password)
- No actual validation - just UI demonstration
- Swedish UI text

### Main Application
- **Toolbar** with Nollställ button
- **Three tabs**:
  - **Kommunikation** - Radio/phone communications with static demo data
  - **Händelser** - Events with priority/category and static demo data
  - **Personal** - Personnel tracking with status and static demo data
- **Status bar** showing operator and last log message
- Tab switching with preserved state

## How to Run

```bash
python demo_app.py
```

Or just double-click `demo_app.py` in Windows Explorer.

## Requirements

- Python 3.x (uses only stdlib tkinter)
- No external dependencies

## Demo Flow

1. **Login window appears**
   - Optionally click "Bläddra..." to select a keyfile (any file)
   - Enter any password
   - Click "Lås upp"

2. **Main window appears**
   - Explore the three tabs
   - See static demo data in tables
   - Forms are functional but don't save (demo only)

## Notes

**This is a UI mockup only** - No actual functionality:
- Login accepts any password
- Buttons don't save data
- Data is static (hardcoded examples)
- No database, no validation

**Purpose**: Visual layout reference and Swedish terminology for the actual application.

---

⚠️ **IMPORTANT**: This demo is a **UI/UX prototype**, not production code!

### Purpose of Demo
- **Rapid prototyping** - Quickly test layout ideas
- **Visual reference** - See how forms and tables should look
- **Swedish terminology** - Field names and labels

### For Implementation

See **[UI_REFERENCE.md](UI_REFERENCE.md)** - Maps demo UI to actual implementation docs.

**Quick Reference**:
- Demo shows the **LAYOUT** → Implement per `gui_design.md`
- Demo shows the **FIELDS** → Implement per `core_design.md` entities
- Demo shows the **STORAGE** → Implement per `db_design.md` schema
- Demo values are **EXAMPLES** → Actual values from database (NOT hardcoded)

❌ **DO NOT**:
- Copy demo code (no architecture, monolithic)
- Use demo's hardcoded values literally
- Recreate info already in architecture/design docs

✅ **DO**:
- Reference demo for visual layout
- Use demo for Swedish field naming
- Follow architecture/design docs for implementation
- Question if demo differs from design docs (ask for clarification)
## Swedish UI Terms

- **Kommunikation** - Communications
- **Händelser** - Events
- **Personal** - Personnel
- **Nollställ** - Emergency data clear
- **Lås upp** - Unlock
- **Bläddra** - Browse
- **Spara** - Save
- **Rensa** - Clear
- **Operatör** - Operator


# EventLog - Platoon Staff Event Logger

A desktop application for logging events during platoon staff operations, including radio communications, operational events, personnel tracking, and other significant events requiring documentation.

## Overview
This application allows staff to log:
- Radio messages (sent/received)
- Operational events (patrols departing/returning, orders given)
- Personnel tracking (location and activity of personnel/groups)
- Other significant events

## Technology
- **Python**: 3.14
- **GUI**: Tkinter
- **Database**: SQLite3 (local file)
- **Testing**: pytest

## Project Structure
```
MessageLog/
├── src/              # Source code
│   ├── gui/          # GUI layer (Views + Presenters)
│   ├── core/         # Business logic
│   └── db/           # Database layer (Adapters + Repositories)
├── tests/            # Test suite
│   ├── conftest.py   # Global test fixtures (pytest)
│   ├── unit/         # Unit tests
│   └── integration/  # Integration tests
├── docs/             # Architecture and Design documentation
├── ai_instructions/  # AI agent guidance
├── ai_memory/        # AI learnings and preferences
└── session_logs/     # AI session history
```

## Setup

### Install Dependencies

**For running the application:**
```bash
pip install -r requirements.txt
```
(Currently no third-party dependencies - uses Python stdlib only!)

**For development and testing:**
```bash
pip install -r requirements-test.txt
```

### Run the Application
(Instructions to be added once implemented)

### Run Tests
```bash
pytest
```

## Documentation

### For Developers
- **Getting Started**: This file (README.md)
- **Architecture**: `docs/architecture/root_architecture.md`
- **Design**: `docs/design/root_design.md`
- **All Documentation**: `docs/` folder

### For AI Assistants
- **Start Here**: `.ai/instructions.md` (main AI entry point)
- AI-specific files are in `.ai/`, `ai_instructions/`, `ai_memory/`, and `session_logs/`

## Important Notes
⚠️ **This project has NO GIT repository** - changes cannot be reverted. Please be careful when modifying files.

This project is designed to run completely offline on a single computer.


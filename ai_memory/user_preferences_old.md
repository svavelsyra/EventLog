# User Preferences & Learnings

**Last Updated**: 2026-04-23 (Session 012 - Added user story writing preferences)

**Purpose**: General AI behavior, communication preferences, and domain knowledge. For technical implementation lessons, see specialized files.

## Memory File Structure

**This file** (`user_preferences.md`): General AI behavior and domain knowledge (read at every session start)

**Specialized implementation learnings** (read only when working on that layer):
- `gui_learnings.md` - Tkinter patterns, layout lessons, UI pitfalls
- `core_learnings.md` - Business logic patterns, validation lessons
- `db_learnings.md` - SQLite patterns, query lessons, database pitfalls

**See**: `ai_memory/README.md` for complete structure explanation

## Project Context
- **Project Name**: EventLog
- **Project Type**: Platoon staff event logger (radio communications, operational events, personnel tracking)
- **Environment**: Offline, local computer only, NO GIT
- **Python Version**: 3.14

## User Preferences

### Code Organization
- ✅ **Layered architecture**: GUI → Core → DB → Implementation
- ✅ **Clear separation of concerns**: No mixing of layers
- ✅ **Adapter pattern** for database abstraction
- ✅ **Repository pattern** for data access
- ✅ **View-Presenter pattern** for GUI testability

### Testing Philosophy
- ✅ **Avoid mocking** as much as possible
- ✅ Use **in-memory databases** for tests instead of mocks
- ✅ Use **fixtures and transactions** for test data
- ✅ **Document all mocks** with justification in integration tests
- ✅ Unit tests can mock more, but still minimize
- ✅ Integration tests should rarely mock
- ✅ **Use pytest's conftest.py pattern** for fixtures:
  - `tests/conftest.py` - Global fixtures
  - `tests/unit/conftest.py` - Unit test specific fixtures
  - `tests/integration/conftest.py` - Integration test specific fixtures
- ✅ **NO separate fixtures/ folder** - that's not the pytest way

### Technology Choices
- ✅ **GUI**: Tkinter
- ✅ **Database**: SQLite3 (local file)
- ✅ **Testing**: pytest (unit + integration)
- ✅ **Test retries**: pytest-rerunfailures for flaky tests
- ✅ **No external services** - fully offline
- ✅ **AVOID THIRD-PARTY DEPENDENCIES** - use Python stdlib when possible
- ✅ **Context matters**: Quality libraries (like requests) are still good libraries, just not needed for this app

### Security Philosophy
- ✅ **Be realistic about threat model** - Don't pretend plaintext files are secure
- ✅ **Accept what you cannot protect** - config.ini and Python source are readable by attacker
- ✅ **Remove fake security** - Code-based limits (like max_login_attempts) can be bypassed
- ✅ **Focus on real security** - Encryption (AES-256), KDF (PBKDF2), key files, secure deletion
- ✅ **Simplicity is security** - Remove complexity that doesn't actually provide security
- ✅ **Config.ini is for bootstrapping and defaults** - NOT for security enforcement
- ✅ **Database header stores actual security parameters** - Self-describing, tamper-proof (encrypted)

### Dependency Management
- ✅ **Use `>=` not `==`** for version specifications
- ✅ Reason: No Git means can't rollback, need flexibility for bug fixes
- ✅ Avoid version locking unless absolutely necessary
- ✅ Keep dependencies minimal
- ✅ **Separate requirements files**: 
  - `requirements.txt` - app dependencies only (currently ZERO third-party!)
  - `requirements-test.txt` - testing/development dependencies only
- ✅ Users shouldn't need test dependencies to run the app
- ✅ **Decision criteria**: "Do we need it?" not "Is it good?"
- ✅ Recognize good libraries (like requests) even if we don't need them here


### Documentation Preferences
- ✅ **Dual documentation system**: Separate docs for AI vs humans
  - **AI documentation** (`ai_instructions/architecture/`, `ai_instructions/design/`):
    - **Aggressively subdivided** into smaller files (core, db, gui, etc.)
    - Purpose: Efficient token usage - AI reads only what it needs
    - Organized by layer/component
  - **Human documentation** (`docs/architecture/`, `docs/design/`):
    - **Fewer, larger, comprehensive** documents
    - Purpose: Easier for humans to read and understand
    - Overview style with complete context
  - **AI must maintain BOTH** - keep them synchronized!
- ✅ **GitHub Copilot auto-loading**: `.github/copilot-instructions.md` - **auto-loaded** by Copilot
  - Session 001: No entry point ❌
  - Session 002: Created `.ai/instructions.md` (not auto-loaded) ❌
  - Session 003: Created `.github/copilot-instructions.md` (correct!) ✅
- ✅ **Separate Architecture and Design docs** - keep distinct from AI memory
- ✅ **Session logs** - incremental index, one per AI session
- ✅ **AI memory** - aggressively update user preferences and learnings
- ✅ **Incremental design approach** - small changes discussed and synced across documents
- ✅ **Sync as you go** - keep gui_design.md and core_design.md aligned during design work
- ✅ **User Stories & Epics** (`user_stories/`) - Purpose-driven requirements tracking
  - Use Goal, Limitations, Purpose framework
  - **Purpose is MOST important** - enables intelligent problem-solving when plans change
  - Separate `ToDo/` and `Done/` folders for active work vs archive
  - Templates: `EPIC_TEMPLATE.md` and `USER_STORY_TEMPLATE.md`
  - **Versioning schema**: MAJOR.MINOR.MICRO (e.g., `001.001.001.md`)
  - Supports splitting stories when scope grows too large

### Work Style Preferences
- ✅ **Iterative development** - User prefers small, incremental changes
- ✅ **Small patches** - Keep changes focused and manageable
- ✅ **Aggressive story splitting** - AI should actively suggest splitting stories:
  - If >3-4 acceptance criteria → suggest split
  - If touching >2-3 components → suggest split
  - If will take >1 focused session → suggest split
  - Better to split too much than too little
  - Expected lines of code > 300 → suggest split
- ✅ **Fast feedback loops** - Small stories enable quicker validation

### User Story Writing Preferences (Session 012)
- ✅ **Purpose section is MOST IMPORTANT** - The WHY enables alternatives when HOW is blocked
- ✅ **Remove detailed code examples** - Use numbered high-level steps, not 30+ line code blocks
- ✅ **Reference architecture docs, don't repeat** - Say "See db_architecture.md section X"
- ✅ **Trust the developer** - Don't prescribe formatting, comment styles, or common sense
- ⚠️ **Some "formatting" is architectural**: `pass` vs `raise NotImplementedError` affects debugging
- ✅ **Specify architectural/contractual** - Method signatures, return types, business rules
- ❌ **Don't specify formatting** - Comment formats, variable names, docstring structure (within reason)
- ✅ **Keep architecture docs example-light** - Short examples for general decisions OK, full method implementations belong elsewhere
- ✅ **Implementation notes**: Numbered high-level steps + method signatures with purpose (no implementation code)

**What to specify in stories**:
- Inheritance relationships (e.g., "inherits from ABC")
- Method signatures with type hints
- Return types and meaning (e.g., "returns None if not found")
- Business rules (e.g., "sets edited=1 automatically")
- Test requirements (e.g., "unit tests: round-trip test")

**What NOT to specify**:
- Comment formats or styles (unless architectural like TODO vs FIXME conventions)
- Code organization details (unless pattern-mandated)
- How to name variables
- Docstring structure (as long as Args/Returns explained)

### Safety & Care
- ⚠️ **NO GIT** - Cannot revert mistakes, be extra careful
- ⚠️ Read files before editing
- ⚠️ Validate changes after editing
- ⚠️ Think before acting

## Communication Preferences (CRITICAL!)

### When User Says "I changed..." - It's FYI, Not a Request!
- ✅ **"I changed X"** (past tense) = User ALREADY did it, they're informing you
- ✅ **"I updated Y"** (past tense) = User ALREADY did it, they're explaining their change
- ❌ **DON'T automatically change other files** - User must verify your changes take significant time
- ✅ **Ask first**: "I see you updated X. Would you like me to sync Y and Z to match, or will you handle that?"
- ✅ **Respect their time**: Every file you change = they must re-read and verify = wasted time if unasked

**Example (Session 006)**:
- User: "I changed in the security architecture, that the file picker DOES NOT remember last used directory, security issue..."
- WRONG: Immediately update security_design.md, session_006.md, etc. ❌
- RIGHT: "Good security decision! I see you updated security_architecture.md. Would you like me to update the related documents to match?" ✅

### When to Act vs Ask
- ✅ **Act immediately**: User says "do X", "update Y", "fix Z" (imperative/future tense)
- ✅ **Act immediately**: Clear bug or error that needs fixing
- ❌ **ASK FIRST**: User says "I did X" (informational, past tense)
- ❌ **ASK FIRST**: Anything that modifies multiple files based on inference

## DO's
- ✅ Update this file aggressively when learning user preferences
- ✅ Create session log at start of each AI session
- ✅ Write tests before or alongside implementation
- ✅ Use abstract base classes for interfaces
- ✅ Keep layers separate and well-defined
- ✅ Sync design documents as changes are made (work incrementally)
- ✅ Use configuration-driven approaches for extensibility (method_metadata example)
- ✅ **Read carefully**: Past tense ("I changed") ≠ request for action
- ✅ **Ask before syncing**: If user updated one file, ask before updating related files
- ✅ **Add dependencies to requirements.txt when implementing, NOT when designing**

## DON'Ts
- ❌ Don't store Architecture/Design decisions in AI memory (use architecture/design docs instead)
- ❌ Don't put technical specifications in user_preferences.md (GUI layouts, screen sizes, etc.)
- ❌ Don't mix layer concerns (GUI knowing about DB, etc.)
- ❌ Don't mock when a real implementation is available
- ❌ Don't make changes without reading the file first
- ❌ Don't assume Git exists for reverting changes
- ❌ **Don't create massive changes without discussion (1600+ lines!)**
- ❌ **Don't invent designs/implementations without user input**
- ❌ **Don't jump straight to action - discuss first**
- ❌ **Don't auto-update files when user says "I changed" - ASK FIRST!**
- ❌ **Don't add dependencies to requirements.txt during design - wait for implementation**
- ❌ **Don't put implementation code in architecture documents - use design docs instead**

## Notes
- User values **testability** and **clean architecture**
- User prefers **explicit over implicit**
- User wants **documentation to be discoverable** (layered approach)
- User has **real military operational experience** (7S reports, radio procedures, personnel tracking)
- User appreciates **incremental collaborative design** approach
- User wants **documents synchronized** as design evolves (not "fix it all at the end")

## Domain-Specific Knowledge Learned

### Swedish Military
- **7S Report** (SjuSrapport) - Standard observation report format:
  - Stund (When), Ställe (Where), Styrka (Strength), Slag (Type), Sysselsättning (Activity), Symbol (Markings), Sagesman (Observer)
  - Used for reporting observed enemy/outside forces/civilians
  - Needs structured fields in EventEntry
- **Radio procedures**: DART (data messages) vs Speech transmission modes
- **Unit designations**: Pluton, Grupp, Kompani, callsigns
- **Operational tempo**: Fast data entry is critical

### Operational Context
- **Offline operations**: No internet, no cloud, no external dependencies
- **Small screens**: Netbooks with ~1024x600 resolution must be supported
- **Field use**: Practical, real-world constraints (crappy hardware, operational tempo)
- **Check-in tracking**: Personnel away from camp need regular contact monitoring
- **Historical accuracy**: Logs must preserve what was configured at time of logging (channel designations change)


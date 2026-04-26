# Dependency Philosophy

## Core Principle: Minimize Third-Party Dependencies

This project **avoids third-party dependencies** whenever possible.

## Why Avoid Third-Party Dependencies?

### For This Project Specifically
1. **Offline-only** - No network means harder to update dependencies
2. **No Git** - Can't easily rollback if a dependency breaks
3. **Simplicity** - Fewer dependencies = fewer things that can break
4. **Security** - Smaller attack surface
5. **Maintainability** - Python stdlib is stable and well-documented

### General Benefits
- **Reliability** - stdlib is battle-tested
- **Portability** - Works everywhere Python works
- **Long-term stability** - stdlib rarely breaks backwards compatibility
- **No dependency hell** - No conflicts with other packages

## Current Dependencies

### Application Dependencies
**ZERO third-party dependencies!**

```
- tkinter (GUI) - Python standard library
- sqlite3 (Database) - Python standard library
```

### Testing Dependencies Only
```
- pytest>=8.1.1 - Test framework
- pytest-cov>=4.1.0 - Coverage reporting
- pytest-rerunfailures>=14.0 - Flaky test retries
```

## Installation

### For Users (Running the App)
```bash
pip install -r requirements.txt
```
(Currently installs nothing - all stdlib!)

### For Developers (Running Tests)
```bash
pip install -r requirements-test.txt
```
(Installs testing tools only)

## When to Add a Dependency?

Ask these questions FIRST:

1. **Can Python stdlib do this?** - Check the docs!
2. **Can we implement it ourselves?** - Simple features don't need libraries
3. **Is it absolutely necessary?** - Nice-to-have ≠ necessary
4. **Is it widely used and stable?** - Avoid obscure packages
5. **Does it have minimal dependencies itself?** - Avoid dependency chains

### Good Reasons to Add a Dependency
- ✅ Complex functionality (e.g., image processing, PDF generation)
- ✅ Security-critical code (e.g., cryptography)
- ✅ Testing tools (in requirements-test.txt only)
- ✅ Well-established, widely-used libraries
- ✅ Saves significant development time without adding risk

### Bad Reasons to Add a Dependency
- ❌ "I'm used to this library"
- ❌ Saves 5 lines of code
- ❌ "Everyone uses it" (but stdlib can do it)
- ❌ Trendy/new/exciting library
- ❌ Library does 100 things but we only need 1

## Decision Template

When considering a new dependency, document:

```
Proposed Dependency: [package-name]
Purpose: [what it does]
Alternatives Considered:
  - Python stdlib: [why not sufficient]
  - Implement ourselves: [why too complex/risky]
  - Other libraries: [why this one is best]
Justification: [why it's worth the cost]
Stability: [maintenance status, last update, popularity]
Dependencies: [list its dependencies]
```

## Examples

### ✅ Good: Keeping stdlib
- **GUI**: Using tkinter (stdlib) instead of PyQt/wxPython
- **Database**: Using sqlite3 (stdlib) instead of ORMs
- **Testing**: Minimal pytest (necessary for good tests)

### ✅ Good: Designed for Security (Session 006, not yet implemented)
- **Database encryption**: pysqlcipher3
  - DESIGNED for database encryption at rest (see security_architecture.md)
  - Security-critical: Don't roll your own encryption
  - Battle-tested: Used by WhatsApp, Signal, enterprise apps
  - Transparent: Minimal code changes, full SQL functionality
  - **Status**: Designed, will be added to requirements.txt during implementation
  
- **Cryptography**: cryptography library
  - DESIGNED for PBKDF2 key derivation (see security_architecture.md)
  - Security-critical: Cryptographic primitives
  - Well-maintained: Industry standard for Python
  - Portable: Pure Python + Rust, cross-platform
  - **Status**: Designed, will be added to requirements.txt during implementation

### ✅ Good: Would Add If Needed (Future)
- **Cryptography**: cryptography library (also designed for database encryption above)
  - Security-critical code (encryption, hashing, key derivation)
  - Don't roll your own crypto!
  - Useful for: Python-layer encryption if SQLCipher unavailable, secure deletion, key derivation
- **PDF reports**: ReportLab (complex format, hard to do manually)
- **Data validation**: pydantic (if complex validation needed)
- **HTTP requests**: requests library (excellent API, much better than urllib)
  - Note: Our app doesn't need HTTP (offline-only), but if we did, requests is a great choice!

### ❌ Bad: Don't Add (For This Project)
- **Arrow/Pendulum**: Use datetime (stdlib) - it's sufficient for our needs
- **Click**: Use argparse (stdlib) - we don't have a complex CLI
- **Rich**: Plain output is fine for this offline app
- **Any HTTP library**: We're offline-only, no network functionality needed

### 🤔 Context Matters!
Some libraries are excellent but **not needed for this specific project**:
- **Requests**: Fantastic library! But we're offline-only (no HTTP needed)
- **Flask/FastAPI**: Great for web apps, but we're building a desktop app
- **NumPy/Pandas**: Powerful for data analysis, but overkill for our use case
- **Pillow**: Excellent for images, but we don't handle images

**The question isn't "Is this a good library?" but "Do we need it?"**

## Maintenance

### Review dependencies regularly
- Are they still needed?
- Are there stdlib alternatives now?
- Can we remove any?

### Before updating
- Check changelog for breaking changes
- Test thoroughly (we have no Git!)
- Update in requirements.txt or requirements-test.txt first

---

**Remember**: Every dependency is a long-term commitment. Choose wisely!



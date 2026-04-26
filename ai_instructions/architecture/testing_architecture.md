# Testing Architecture (AI)

**Last Updated**: 2026-04-17

## Overview
Testing strategy emphasizing real implementations over mocks.

## Testing Philosophy

### Avoid Mocking
- Use real objects whenever possible
- Use in-memory SQLite instead of mocking database
- Only mock external dependencies when necessary

### When to Mock
**Unit tests** - Can mock minimally when needed

**Integration tests** - Rarely mock, document justification when mocking

## Test Database Strategy

### In-Memory SQLite
- Fast (no disk I/O)
- Isolated (each test gets fresh DB)
- Real database (no mocking)

### Test Isolation
- Each test should be independent
- No test interdependencies

## Test Categories

### Unit Tests
- Single class/function testing
- In-memory SQLite when database needed
- Minimal mocking

### Integration Tests
- Multiple components working together
- In-memory SQLite
- Rare mocking, documented

### End-to-End Tests
- Full user scenarios
- In-memory SQLite
- Avoid mocking

## Handling Flaky Tests

### Common Causes
- Tkinter threading/timing
- Event loop interactions
- Window manager dependencies

### Strategy
- Fix flaky tests, don't just retry forever
- Document why test is flaky
- Use retry mechanism as temporary solution

## Dependencies
- `pytest>=8.1.1`
- `pytest-cov>=4.1.0`
- `pytest-rerunfailures>=14.0`

---

**Related**:
- Human version: `docs/architecture/root_architecture.md`
- Testing guidelines: `ai_instructions/testing.md`



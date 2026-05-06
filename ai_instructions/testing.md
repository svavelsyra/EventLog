# Testing Guidelines

## Testing Framework
- **pytest** for all tests
- Both **unit tests** and **integration tests** required

## Approved Test Command Policy
- Use `python -m pytest` as the default validation command.
- A focused test rerun may use exactly one file under `tests/` in this canonical form: `python -m pytest .\tests\<relative-path-to-single-test-file>.py`
- Prefer reusing one of those two command shapes over inventing narrower or more specialized variants.
- Rely on `pytest.ini` for normal verbosity, traceback, and coverage defaults instead of adding extra flags during routine validation.

### Not Allowed Without Explicit User Approval
- Extra pytest flags beyond the approved command shapes above
- Multiple test files in one command
- Reordered multi-file combinations
- Node selectors like `::TestClass::test_name`
- Expression filters like `-k`
- Switching between `pytest` and `python -m pytest`; use `python -m pytest` consistently

## Testing Philosophy: Avoid Mocking

### Unit Tests
- **Minimize mocking** - only mock when absolutely necessary
- Use real objects and in-memory databases when possible
- Mock external dependencies only (network, file system, etc.)

### Integration Tests
- **Avoid mocking** unless absolutely necessary
- Use in-memory SQLite databases for testing
- Use fixtures and transactions for test data setup
- **Document all mocks** with:
  - WHY the mock is necessary
  - WHAT needs to be tested elsewhere to compensate

### Test Database Strategy
- SQLite supports **in-memory databases** (`:memory:`)
- Use **fixtures** to create fresh test databases
- Use **transactions** and **fixtures** for test isolation
- No need to mock the database - it's local and fast

## Test Structure
```
tests/
├── conftest.py        # Global fixtures (available to all tests)
├── unit/              # Fast, isolated tests
│   ├── conftest.py    # Unit test specific fixtures
│   ├── test_core/     # Business logic tests
│   ├── test_db/       # DB adapter/repository tests
│   └── test_gui/      # Presenter tests (views may need mocks)
└── integration/       # End-to-end tests
    ├── conftest.py    # Integration test specific fixtures
    └── test_scenarios/ # Real-world usage scenarios
```

## Pytest Fixtures
- **Global fixtures**: Define in `tests/conftest.py` (auto-discovered)
- **Unit test fixtures**: Define in `tests/unit/conftest.py` (only for unit tests)
- **Integration test fixtures**: Define in `tests/integration/conftest.py` (only for integration tests)
- Fixtures automatically available to tests in their scope

## Writing Tests
1. **Arrange**: Set up test data (use fixtures)
2. **Act**: Execute the code being tested
3. **Assert**: Verify the results

Note: Setup is usually the expensive part so better an extra cheap assertion than 
      missing something, even thought it might be covered by another test as well.

## Coverage
- Aim for high test coverage
- All business logic must be tested
- Critical paths must have integration tests

## Handling Flaky Tests
- Prefer fixing flaky tests over introducing retry-command variants.
- If a test is flaky, document why it is flaky and what makes it non-deterministic.
- If retry behavior is ever needed, ask the user before introducing any non-approved pytest flags or plugin-dependent commands.
- **Document why a test is flaky** and what makes it non-deterministic
- **Goal**: Fix flaky tests, don't just retry them forever
- Common flaky causes: timing issues, external state, threading, tkinter startup/shutdown (prefer a stable fix but can be complicated.)


# User Story Writing Rules

**Purpose**: Guidelines for creating and editing user stories. Read when working with user stories/epics.

---

## Story Structure

### Three Core Sections

1. **Purpose (WHY)** - ⭐ MOST IMPORTANT
2. **Goal (WHAT)** - What we're delivering
3. **Limitations (CONSTRAINTS)** - What we must/must not do

**Why Purpose is most important**: The WHY enables alternatives when HOW is blocked. If you understand the purpose, you can find different solutions when the planned approach hits obstacles.

---

## What to Specify in Stories

### DO Specify (Architectural/Contractual)

✅ **Method signatures with type hints**
```
get_communication_entry(entry_id: int) -> CommunicationEntry | None
```

✅ **Return types and their meaning**
- "Returns None if not found"
- "Returns database-generated ID"
- "Returns bool indicating success"

✅ **Business rules**
- "Sets edited=1 automatically"
- "Defaults priority to 'Normal'"
- "Preserves logged_time on update"

✅ **Inheritance relationships**
- "Inherits from ABC"
- "Implements EventLogAdapter interface"

✅ **Test requirements**
- "Unit tests: round-trip test (create then retrieve)"
- "Integration tests: transaction rollback"

✅ **Error handling expectations**
- "Raises ValueError if invalid"
- "Returns empty list if no matches"

---

## What NOT to Specify

### DON'T Specify (Formatting/Common Sense)

❌ **Comment formats or styles**
- Don't dictate: `# ========== Section ==========`
- Developer will use appropriate comments

❌ **Variable naming conventions**
- Don't prescribe: "use `comm_id` for communication ID"
- Developer will choose clear names

❌ **Code organization details**
- Don't specify: "Put helper methods at bottom of class"
- Unless pattern-mandated (e.g., abstract methods together)

❌ **Docstring structure**
- Don't prescribe exact format
- As long as Args/Returns are explained, format is developer choice

❌ **Implementation code in stories**
- Don't include 30+ line code blocks
- Use high-level numbered steps instead

---

## When Revising Existing Stories

### Prioritize Structural Improvement Over Cosmetic Rewording

When a story already communicates its intent clearly enough, do **not** spend a cleanup pass on synonym swaps or sentence polishing alone.

Focus revisions on meaningful structural issues such as:
- scope that is too broad or mixed
- unclear responsibility boundaries between related stories
- acceptance criteria that overlap or are not independently verifiable
- implementation notes that prescribe too much low-level detail

If the structure is already sound, it is acceptable to leave the story unchanged and simply record that assessment.

---

## Epic Planning Preference

### Define Epics Before Sub-Stories

When planning a new area of work, prefer getting the epic structure approved before creating the epic's child stories.

Default workflow:
- define or review the epic first
- stop for user review of that epic boundary
- only create 00X.YYY stories after the epic itself is accepted

### One Epic at a Time

When the user is in an epic-definition phase, do not draft multiple epics in one pass.

Instead:
- work on a single epic
- keep scope focused enough for structural review
- use the epic pass to catch boundary problems early before story creation fans out underneath it

### Finalize the Chosen Design, Don't Keep Temporary Option Labels

When an epic records a chosen design direction, write the final decision directly instead of keeping temporary labels like "Option 1" or "Option 2" in the epic text.

Only reference discarded or alternate options if the document is intentionally comparing alternatives or preserving a decision record where those alternatives matter.

---

## Testing Work in Story Structure

### Tests Belong to Delivery Stories by Default

Do not create a standalone testing story just because implementation work needs unit tests or integration tests.

By default:
- each feature or technical delivery story should include its own testing expectations
- tests are treated as part of normal development quality, not as a separate user-facing deliverable
- acceptance criteria may mention required test coverage, but the story should still be about the capability being delivered

### Standalone Testing Stories Need Strong Justification

A dedicated testing story is justified only when it delivers shared, reusable testing infrastructure with independent planning value, such as:
- cross-cutting pytest/bootstrap setup
- reusable fixtures used by many later stories
- test harness support that multiple stories depend on

If the work is mainly "write the tests that should already accompany these stories," that is not a good standalone story.

### Fixture Scope and Placement Rules

When test support is needed:
- check for existing reusable fixtures before creating a new one
- keep only truly local fixtures in the individual test file
- place reusable fixtures in the nearest appropriate shared `conftest.py`
- think about project-wide reuse early instead of letting each test file invent parallel setup helpers

Shared fixture creation should be deliberate and justified by reuse, not done automatically for every test setup pattern.

### Epic Placement Guidance

If the testing work is framework/bootstrap infrastructure rather than domain delivery, it may belong in a separate support/testing epic instead of being attached to a feature epic.

If a feature epic still needs a testing-related item, prefer something like gap review or shared support that directly serves that epic rather than a broad catch-all testing story.

---

## Exception: When "Formatting" is Actually Architectural

⚠️ **Some formatting affects behavior**:

**Example: `pass` vs `raise NotImplementedError`**
- This is NOT formatting - it's architectural
- Affects runtime behavior (silent vs explicit error)
- Affects debugging (clear message vs mystery failure)
- Affects API contract (optional vs required to override)

**When to specify**:
- If it affects runtime behavior → specify
- If it affects debugging/testing → specify
- If it's pure style/cosmetics → don't specify

---

## Implementation Notes Section

### Format: High-Level Steps + Signatures

**Good example**:
```markdown
## Implementation Notes

1. Create helper method `_row_to_communication_entry(row)` for type conversion
2. Implement `create_communication_entry(entry)` method:
   - Insert all fields using parameterized query
   - Convert datetime → ISO 8601, dict → JSON, bool → INTEGER
   - Return database-generated ID
3. Add unit tests for create and round-trip validation
```

**Bad example** (too much detail):
```text
def create_communication_entry(self, entry: CommunicationEntry) -> int:
    cursor = self.conn.cursor()
    cursor.execute("""
        INSERT INTO communication_entries (message_content, from_field, ...)
        VALUES (?, ?, ...)
    """, (entry.message_content, entry.from_field, ...))
    return cursor.lastrowid
```

**Why bad**: That's full implementation code. Story should explain WHAT and WHY, not provide copy-paste code.

---

## Reference Architecture Docs, Don't Repeat

### Good Approach
```markdown
See `db_architecture.md` section on "Repository Pattern" for details on 
how repositories implement adapter interfaces.
```

### Bad Approach
```markdown
Repositories implement the adapter pattern by inheriting from the abstract
EventLogAdapter class and implementing all abstract methods. The repository
uses dependency injection to receive a database connection...
(200 lines of architecture lecture)
```

**Why bad**: Wastes tokens, duplicates architecture docs, makes story hard to read.

---

## Trust the Developer

### Assume Developer Competence

✅ Developer knows:
- How to write clear variable names
- When to add comments
- How to structure docstrings
- Common Python patterns
- How to organize code clearly

❌ Don't patronize:
- "Make sure to use meaningful variable names"
- "Remember to add comments explaining complex logic"
- "Use proper indentation"

**Exception**: When there's a project-specific convention that differs from standard practice, DO specify it.

---

## Story Size Guidelines

### Triggers for Splitting

Split story into smaller stories when:
- **>4 acceptance criteria**
- **>300 expected lines of code**
- **Touches >2-3 components**
- **Takes >1 focused session (2 hours)**

### Philosophy
- Better to split too much than too little
- Small stories = faster feedback
- Small stories = easier to review
- Small stories = less risk per change

---

## Acceptance Criteria Best Practices

### Clear and Testable

✅ **Good acceptance criteria**:
- "Method returns None if entry not found"
- "Helper handles NULL values for optional fields"
- "Unit test validates type conversion (datetime → ISO 8601)"

❌ **Vague acceptance criteria**:
- "Method works correctly"
- "Code is well documented"
- "Tests pass"

### Keep Count Reasonable
- Aim for 3-4 criteria per story
- If >4 criteria, consider splitting
- Each criterion should be independently verifiable

---

## Story Versioning

### MAJOR.MINOR.MICRO Schema

**Format**: `001.002.003.md`
- **MAJOR** (001) - Epic number
- **MINOR** (002) - Story number within epic
- **MICRO** (003) - Sub-story number (when split)

**Examples**:
- `001.001.md` - Epic 001, Story 001 (not split)
- `001.002.001.md` - Epic 001, Story 002, Sub-story 001 (split)
- `001.002.002.md` - Epic 001, Story 002, Sub-story 002 (split)

**When to split**: When story grows too large (see triggers above)

---

## Story Status and Organization

### Folders
- `user_stories/ToDo/` - Active stories to implement
- `user_stories/Done/` - Completed/archived stories

### Status Values
- **ToDo** - Not started
- **In Progress** - Currently being implemented
- **Done** - Completed and verified
- **Split** - Story was split into sub-stories (parent is archived)

---

## Keep Architecture Docs Example-Light

### In Architecture/Design Docs

**Short examples for general decisions**: OK ✅
```text
# Example: Abstract method pattern
@abstractmethod
def get_entry(self, entry_id: int) -> Entry | None:
    """Get entry by ID."""
    raise NotImplementedError("Subclass must implement")
```

**Full method implementations**: WRONG ❌
```text
# Don't put this in architecture docs:
def get_communication_entry(self, entry_id: int) -> CommunicationEntry | None:
    cursor = self.conn.cursor()
    cursor.execute("SELECT * FROM communication_entries WHERE id = ?", (entry_id,))
    row = cursor.fetchone()
    if row is None:
        return None
    return CommunicationEntry(
        id=row['id'],
        message_content=row['message_content'],
        # ... 30 more lines ...
    )
```

**Better**: "Repository implements get_X methods by querying database and using _row_to_X helper for type conversion."

---

**Last Updated**: 2026-04-23 (Session 013 - Created during AI memory refactor)


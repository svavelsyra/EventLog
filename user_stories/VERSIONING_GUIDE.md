# User Story Versioning Guide

## Quick Reference

### Format: MAJOR.MINOR.MICRO

```
001.md              → Epic 001
001.001.md          → First story in Epic 001
001.001.001.md      → First sub-story (story was split)
001.001.002.md      → Second sub-story
```

### Optional Descriptive Suffixes

```
001-event-logging.md          → Epic with description
001.001-basic-fields.md       → Story with description
001.001.001-validation.md     → Sub-story with description
```

Numeric prefix is **required**, descriptive suffix is **optional**.

---

## When to Split Stories

### Red Flags (Suggest Split!)

🚨 **>3-4 acceptance criteria** → Too many concerns  
🚨 **Touches >2-3 components** → Too broad  
🚨 **>1 focused session** → Too much work  
🚨 **Complexity emerging** → Scope creeping  

### How to Split

1. Identify logical boundaries based on **Purpose**
2. Create sub-stories: `XXX.YYY.001.md`, `XXX.YYY.002.md`, etc.
3. Move original `XXX.YYY.md` to `Done/` with status: "Split"
4. Document which sub-stories it was split into
5. Distribute acceptance criteria across sub-stories

---

## Examples

### Before Split

**File**: `ToDo/001.001-user-authentication.md`

- Has 8 acceptance criteria
- Touches GUI, Core, and DB layers
- Estimated 3+ sessions of work

### After Split

**Original**: `Done/001.001-user-authentication.md` (Status: Split)

**Sub-stories**:
- `ToDo/001.001.001-login-ui.md` - GUI components only
- `ToDo/001.001.002-auth-logic.md` - Core validation & password handling
- `ToDo/001.001.003-user-storage.md` - Database schema & queries

Each sub-story:
- 2-3 acceptance criteria
- Single layer focus
- ~1 session of work

---

## Philosophy

**Better to split too much than too little**

- Small stories are easier to implement
- Small stories are easier to test
- Small stories reduce risk
- Small stories enable faster feedback
- Combining is rare, splitting is common

**The versioning system makes splitting natural and trackable**

You don't need to predict the perfect scope upfront. Start with a story, and if it grows, split it. The numbering makes the relationship clear.

---

## Capacity Planning

### Will 999 be enough?

- **Epics (001-999)**: Likely sufficient for most projects
- **Stories (001-999 per epic)**: Very generous
- **Sub-stories (001-999 per story)**: Extremely generous

If you hit 999 epics, you probably need to reconsider your epic granularity! 😄

**Total capacity**: 999 epics × 999 stories × 999 sub-stories = ~1 billion possible story units

(You'll be fine.)



# User Stories & Requirements - AI Instructions

**When to read**: When creating, reviewing, or implementing user stories and requirements.

---

## Overview

User stories and epics are tracked in `user_stories/` folder with `ToDo/` and `Done/` subfolders.

---

## Versioning Schema: MAJOR.MINOR.MICRO

### Format
- **Epics**: `001-descriptive-name.md`
- **Stories**: `001.001-descriptive-name.md`
- **Sub-stories**: `001.001.001-descriptive-name.md`

Numeric prefix is **required**, descriptive suffix is **required**.

### Capacity
- 001-999 for each level (999 epics × 999 stories × 999 sub-stories)

---

## Framework: Goal, Limitations, Purpose

Every story/epic must have three elements:

### 1. Purpose (WHY) ⭐ **MOST IMPORTANT**
- **Why does this exist?**
- Enables intelligent problem-solving when obstacles arise
- Allows finding alternative solutions when plans change
- **Always fill this out first and most thoroughly**

### 2. Goal (WHAT)
- **What are we trying to accomplish?**
- Clear, concrete desired outcome
- May have multiple valid paths to achievement

### 3. Limitations (CONSTRAINTS)
- **Hard constraints** (MUST do)
- **Negative constraints** (MUST NOT do) - Often more valuable than prescribing methods
- Sometimes defining boundaries gives more freedom than prescribing solutions

---

## Story Scope Management - CRITICAL! 🚨

**YOU MUST AGGRESSIVELY SUGGEST SPLITTING STORIES** - This is core user preference!

### When to Suggest Splitting

🚨 **>3-4 acceptance criteria** → Too many concerns - Suggest splitting  
🚨 **Touches >2-3 components** → Too broad - Suggest splitting  
🚨 **Will take >1 focused session** → Too much work - Suggest splitting  
🚨 **Complexity is emerging** → Scope creeping - Suggest splitting
🚨 **Many rows** 300 row limit → Too much detail - Suggest splitting

### Why Split?
User prefers **small, iterative patches**:
- Small stories are easier to implement
- Small stories are easier to test
- Small stories reduce risk
- Small stories enable faster feedback
- **Better to split too much than too little** - Combining is rare, splitting is common

### How to Suggest Splits
1. Point out the complexity/size concern
2. Propose logical split points based on **Purpose**
3. Suggest sub-story numbers (XXX.YYY.001, XXX.YYY.002, etc.)
4. Show how each sub-story still serves the original Purpose

### Splitting Workflow
1. Create sub-stories: `XXX.YYY.001.md`, `XXX.YYY.002.md`, etc.
2. Move original `XXX.YYY.md` to `Done/` with status: "Split"
3. Document which sub-stories it was split into
4. Distribute acceptance criteria across sub-stories
5. Each sub-story should be implementable in one focused session

---

## Templates

Templates are in:
- `user_stories/EPIC_TEMPLATE.md`
- `user_stories/USER_STORY_TEMPLATE.md`

Use these as starting points. Adapt when it makes sense, but always include Goal, Limitations, Purpose.

---

## Workflow

### Creating New Work
1. Copy template to `ToDo/XXX.md` or `ToDo/XXX.YYY.md`
2. Fill out **Purpose first** (most important!)
3. Then Goal and Limitations
4. Link stories to parent epic

### During Implementation
- Update status as work progresses
- Document decisions in Notes & Decisions section
- Update acceptance criteria if they evolve
- **If stuck, re-read Purpose** - may suggest alternatives

### Completing Work
1. Mark status as "Done"
2. Verify all acceptance criteria met
3. Move from `ToDo/` to `Done/`
4. Update parent Epic's checklist

---

## Bridge Capture Analogy (Why Purpose Matters)

**Without Purpose**: Team told to "capture bridge before 221500, stay between roads X/Y"
- Bridge is destroyed, radio broken
- Team is stuck - can't get new orders

**With Purpose**: Team knows "battalion must cross river with vehicles at 221600"
- Bridge destroyed? Team can:
  - Assess if temporary repairs feasible
  - Look for fording point
  - Find alternative crossing methods
  - Make intelligent on-site decisions

**This is why Purpose is most important** - enables autonomous problem-solving when plans fall apart (and they always do).

---

## AI Responsibilities

1. **Always read Purpose first** - it's most important
2. **Respect Limitations** - they define solution space
3. **Goals are targets** - multiple valid paths exist
4. **Update Notes & Decisions** - document what you learn
5. **When stuck, re-read Purpose** - may suggest alternatives
6. **Move completed work to Done/** - keep archive updated
7. **AGGRESSIVELY SUGGEST SPLITTING** - Core user preference!

---

## Remember

- Templates are guidelines, not rigid requirements
- Purpose enables intelligent decision-making
- Better to split too much than too little
- User prefers small, iterative, focused patches
- Versioning system makes splitting natural and trackable


# User Stories & Epics

**Purpose**: Track features, requirements, and implementation decisions for the EventLog project.

---

## Philosophy: Goal, Limitations, Purpose

This project uses a **Purpose-driven approach** to requirements, inspired by military mission planning:

### The Three Elements

1. **Purpose (WHY)** ⭐ **MOST IMPORTANT**
   - Why does this need to exist?
   - What problem are we solving?
   - Enables intelligent decision-making when obstacles arise
   
2. **Goal (WHAT)**
   - What are we trying to accomplish?
   - Clear, concrete desired outcome
   - The "capture the bridge" - specific but may have multiple paths
   
3. **Limitations (CONSTRAINTS)**
   - Hard constraints (MUST do)
   - Negative constraints (MUST NOT do)
   - Sometimes defining what NOT to do is more valuable than prescribing exact methods

### The Bridge Capture Analogy

Imagine telling a team to **capture a bridge** (Goal) before 221500, staying between roads X and Y (Limitations).

**Without Purpose**: If they arrive and find the bridge destroyed, with broken radio comms, they're stuck. They can't contact command for new orders.

**With Purpose**: If they know the purpose is "the battalion must cross the river with all vehicles at 221600", they can:
- Assess if temporary repairs are feasible
- Look for a suitable fording point
- Find alternative crossing methods
- Make intelligent decisions on-site

**This is why Purpose is the most important element** - it enables autonomous problem-solving when plans fall apart (and they always do).

---

## Folder Structure

```
user_stories/
├── README.md              # This file
├── EPIC_TEMPLATE.md       # Template for new epics
├── USER_STORY_TEMPLATE.md # Template for new user stories
├── ToDo/                  # Active work and planned work
│   ├── 001.md             # Epic 001
│   ├── 001.001.md         # Story 1 of Epic 001
│   ├── 001.002.001.md     # Sub-story (Story 002 was split)
│   └── 002.md             # Epic 002
└── Done/                  # Completed work (archive)
    ├── 001.002.md         # Original story before split (archived)
    └── 001.003.md         # Completed story
```

---

## Workflow

### Creating New Work

1. **For an Epic**: Copy `EPIC_TEMPLATE.md` to `ToDo/XXX.md` (e.g., `001.md`)
2. **For a User Story**: Copy `USER_STORY_TEMPLATE.md` to `ToDo/XXX.YYY.md` (e.g., `001.001.md`)
3. Fill out the template, **starting with Purpose**
4. Link related stories to their parent epic

### Splitting Stories

When a story's scope is too large (discovered during implementation):

1. Create sub-stories: `XXX.YYY.001.md`, `XXX.YYY.002.md`, etc.
2. Move original `XXX.YYY.md` to `Done/` with status note: "Split into XXX.YYY.001, XXX.YYY.002, ..."
3. Distribute acceptance criteria across sub-stories
4. Each sub-story should be implementable in a small, focused iteration

**Philosophy**: Better to split early than struggle with large scope. The versioning system makes splitting natural and trackable.

### During Implementation

- Update status as work progresses
- Document decisions in the Notes & Decisions section
- Update acceptance criteria if they evolve
- **If you encounter obstacles, refer to the Purpose** - it may guide alternative solutions

### Completing Work

1. Mark status as "Done"
2. Verify all acceptance criteria are met
3. Move the file from `ToDo/` to `Done/`
4. Update the parent Epic's checklist if applicable

### Archive Benefits

The `Done/` folder serves as:
- **Implementation history** - What was built when
- **Decision log** - Why choices were made
- **Learning reference** - Patterns that worked or didn't
- **Progress tracking** - Visible accomplishment

---

## Naming Conventions

### Versioning Schema: MAJOR.MINOR.MICRO

Stories use a **three-level versioning system** that supports splitting stories when scope grows too large:

- **MAJOR** (001-999): Epic number
- **MINOR** (001-999): User story within epic  
- **MICRO** (001-999): Sub-story when a story needs splitting

### Epics
- Format: `MAJOR.md`
- Example: `001.md` (Event Logging Epic)
- Example: `002.md` (7S Reports Epic)

### User Stories
- Format: `MAJOR.MINOR.md`
- Example: `001.001.md` (First story in Epic 001)
- Example: `002.003.md` (Third story in Epic 002)

### Sub-Stories (When Splitting Needed)
- Format: `MAJOR.MINOR.MICRO.md`
- Example: `001.001.001.md` (First sub-story of story 001.001)
- Example: `001.001.002.md` (Second sub-story of story 001.001)

### Why Versioning?
Real-world experience shows that stories often need splitting when implementation begins and scope becomes clearer. The versioning system makes this natural:
- Start with `001.001.md`
- Realize it's too big during implementation
- Split into `001.001.001.md`, `001.001.002.md`, etc.
- Move original `001.001.md` to `Done/` with note about split

### Descriptive Names (Optional Suffix)
For human readability, you can add descriptive suffixes:
- `001-event-logging.md` (Epic 001)
- `001.001-basic-fields.md` (Story with description)
- `001.001.001-validation.md` (Sub-story with description)

The numeric prefix is required; the descriptive suffix is optional.

---

## Tips for Writing Good Stories

### Focus on Purpose
- Don't just describe what to build
- Explain WHY it matters
- Help implementers understand the underlying need

### Embrace Negative Constraints
- "Don't use external dependencies" is often clearer than "Use only stdlib"
- "Don't make it modal" gives more freedom than "Use a sidebar"
- Defining boundaries can be more powerful than prescribing solutions

### Keep Goals Concrete
- "Users can log radio messages" ✅
- "Improve the UX" ❌ (too vague)

### Write Testable Acceptance Criteria
- "When X happens, Y should occur" ✅
- "It should be good" ❌ (not testable)

---

## For AI Assistants

When working with these files:

1. **Always read the Purpose first** - it's the most important section
2. **Respect Limitations** - they define the solution space
3. **Goals are targets** - there may be multiple valid paths
4. **Update Notes & Decisions** - document what you learn during implementation
5. **When stuck, re-read Purpose** - it may suggest alternatives
6. **Move completed work to Done/** - keep the archive updated

### Story Scope Management (CRITICAL!)

**Aggressively suggest splitting stories** - this is a core user preference:

- 🚨 **If a story has >3-4 acceptance criteria** → Suggest splitting
- 🚨 **If a story touches >2-3 components** → Suggest splitting
- 🚨 **If implementation will take >1 focused session** → Suggest splitting
- 🚨 **If you see complexity emerging** → Suggest splitting
- 🚨 **If the story is becoming unwieldy** → Suggest splitting
- 🚨 **If expected lines of code > 300** → Suggest splitting

**User prefers small, iterative patches**:
- Small stories are easier to implement
- Small stories are easier to test
- Small stories reduce risk
- Small stories enable faster feedback

**How to suggest splits**:
1. Point out the complexity/size concern
2. Propose logical split points based on Purpose
3. Suggest sub-story numbers (XXX.YYY.001, XXX.YYY.002, etc.)
4. Show how each sub-story still serves the original Purpose

**Better to split too much than too little** - combining is rare, splitting is common.

Remember: The templates are guidelines, not rigid requirements. Adapt them when it makes sense, but always include the three core elements: Purpose, Goal, and Limitations.








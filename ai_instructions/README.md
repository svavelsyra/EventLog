# AI Instructions Index

**Purpose**: This folder contains AI-specific instruction files organized by topic for efficient reading.

---

## General Project Understanding

- **`project_context.md`** - Project overview, tech stack, constraints, Git availability, dependency philosophy
- **`user_stories.md`** - User story framework, versioning, Goal/Limitations/Purpose, splitting guidelines

---

## Specialized Instructions (Read Based on Task)

### Testing
- **`testing.md`** - Testing philosophy, minimize mocking, fixture patterns

### Architecture (Subdivided by Layer)
- **`architecture/core_architecture.md`** - Business logic architecture
- **`architecture/db_architecture.md`** - Database architecture
- **`architecture/gui_architecture.md`** - GUI architecture
- **`architecture/testing_architecture.md`** - Testing organization
- **`architecture/security_architecture.md`** - Security architecture
- **`architecture/logging_architecture.md`** - Logging architecture

### Design (Subdivided by Layer)
- **`design/core_design.md`** - Domain model design
- **`design/db_design.md`** - Database schema design
- **`design/gui_design.md`** - UI layout design
- **`design/security_design.md`** - Security design

---

## AI Memory & Learning

Located in `../ai_memory/`:
- **`behavioral_rules.md`** - **READ EVERY SESSION** - Critical decision-making and workflow rules
- **`project_facts.md`** - Technical project facts, stack, architecture, constraints
- **`gui_learnings.md`** - GUI implementation patterns learned
- **`core_learnings.md`** - Core business logic patterns learned
- **`db_learnings.md`** - Database patterns learned

---

## Session History

Located in `../session_logs/`:
- **`session_XXX.md`** - Check latest for recent work context

---

## Human Documentation (For Reference)

Located in `../docs/`:
- **`architecture/root_architecture.md`** - Comprehensive architecture overview
- **`design/root_design.md`** - Comprehensive design overview
- **`DEPENDENCY_PHILOSOPHY.md`** - Why we minimize dependencies (reference copy in project_context.md)

---

## Demo & Reference

Located in `../Demo/`:
- **`demo_app.py`** - UI mockup (visual reference only, NOT implementation spec!)
- **`UI_REFERENCE.md`** - Maps demo to actual implementation specs

---

## Reading Strategy

1. **Every session start**: Read `ai_memory/behavioral_rules.md`
2. **Check context**: Read latest `session_logs/session_XXX.md`
3. **General understanding**: Read `project_context.md` if new to project
4. **User stories**: Read `user_stories.md` when creating/implementing stories
5. **Specific work**: Read only the architecture/design files you need for current task
6. **Before adding dependencies**: Re-read dependency philosophy in `project_context.md`

---

## Key Principles

- **Git is available** - Prefer the approved low-churn Git command family from `ai_memory/behavioral_rules.md`
- **Offline only** - No network functionality
- **ZERO third-party app dependencies** - Use Python stdlib
- **Minimize mocking** - Use in-memory databases for tests
- **Small, iterative patches** - User preference
- **Aggressively suggest story splitting** - Core user preference


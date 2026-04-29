# Database Implementation Learnings

**Purpose**: SQLite-specific lessons, query patterns, and database implementation pitfalls learned during development.

**Last Updated**: 2026-04-28 (Session 037 - Added personnel repository query/validation learning)

## Session 032 - Repository Settings Bootstrap

- When a new repository-level business rule needs database-backed configuration, prefer a small `settings` table over hardcoding values in Python.
- Repository initialization should not stop after detecting core tables; it must also ensure new support tables/default rows exist so older file-backed databases upgrade safely.
- Store tunable timing rules in seconds (`edited_flag_grace_period_seconds`) instead of larger units to make future adjustments more precise without changing code.

## Session 037 - Personnel Repository Query and Validation Patterns

- When a SQLite `CHECK` constraint maps directly to a repository-facing invalid state, validate it in the repository first so callers get a clear Python error instead of a lower-level SQLite failure.
- For personnel data, treat `logged_time` as the authoritative recency field for general list/history views, while `last_contact_time` drives active operational-awareness ordering and `expected_checkin_time` drives overdue-alarm urgency ordering.

## Expected Content Areas

- SQLite-specific patterns and gotchas
- Transaction handling lessons
- Query optimization patterns
- Migration patterns
- Connection management
- Parametrized query patterns
- Common SQL mistakes and fixes

---

**Note**: Keep architecture decisions in `ai_instructions/architecture/db_architecture.md`. This file is for implementation lessons and pitfalls.


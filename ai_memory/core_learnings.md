# Core/Business Logic Implementation Learnings

**Purpose**: Business logic patterns, validation lessons, and implementation pitfalls learned during core development.

**Last Updated**: 2026-05-05 (Session 081 - Added recursive communication-model summary)

## Session 081 - Communication Model Should Be Recursive Under a Top-Level System

- Treat the communication selection as:
  - top-level `communication_system`
  - recursive `communication_path` beneath that system
  - top-level `communication_qualifiers`
- Do not fall back to the older fixed `system/method/channel` shape in core contracts just because current UI still shows only a few visible dropdowns.
- The user explicitly prefers a recursive/tree-like model when the domain is naturally hierarchical; the current three visible levels are a practical UI limit, not a hard domain-model limit.
- Historical communication entries should snapshot the chosen system, path, and qualifiers so later config changes do not rewrite past meaning.
- Phase 1 should preserve meaningful structure while avoiding heavy enforcement of every real-world operational rule such as channel-specific voice/data restrictions.

## Expected Content Areas

- Entity validation patterns and common mistakes
- Configuration-driven validation lessons
- Business rule implementation patterns
- Error handling approaches
- Data transformation patterns

---

**Note**: Keep architecture decisions in `ai_instructions/architecture/core_architecture.md`. This file is for implementation lessons and pitfalls.


# Core/Business Logic Implementation Learnings

**Purpose**: Business logic patterns, validation lessons, and implementation pitfalls learned during core development.

**Last Updated**: 2026-05-06 (Session 089 - Added malformed portability bundle validation lesson)

## Session 081 - Communication Model Should Be Recursive Under a Top-Level System

- Treat the communication selection as:
  - top-level `communication_system`
  - recursive `communication_path` beneath that system
  - top-level `communication_qualifiers`
- Do not fall back to the older fixed `system/method/channel` shape in core contracts just because current UI still shows only a few visible dropdowns.
- The user explicitly prefers a recursive/tree-like model when the domain is naturally hierarchical; the current three visible levels are a practical UI limit, not a hard domain-model limit.
- Historical communication entries should snapshot the chosen system, path, and qualifiers so later config changes do not rewrite past meaning.
- Phase 1 should preserve meaningful structure while avoiding heavy enforcement of every real-world operational rule such as channel-specific voice/data restrictions.

## Session 089 - Portability Contract Validators Should Fail Malformed Bundles with Domain Errors

- When a versioned core-owned payload validator is meant to be the public guardrail for importable data, it should reject malformed top-level bundle shapes with the domain-specific contract error instead of leaking incidental Python errors such as missing `.keys()`.
- For communication portability specifically, validate that the top-level payload is a mapping before comparing exact keys so malformed recovery bundles fail predictably and reviewably.

## Expected Content Areas

- Entity validation patterns and common mistakes
- Configuration-driven validation lessons
- Business rule implementation patterns
- Error handling approaches
- Data transformation patterns

---

**Note**: Keep architecture decisions in `ai_instructions/architecture/core_architecture.md`. This file is for implementation lessons and pitfalls.


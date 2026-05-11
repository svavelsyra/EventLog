# Core/Business Logic Implementation Learnings

**Purpose**: Business logic patterns, validation lessons, and implementation pitfalls learned during core development.

**Last Updated**: 2026-05-11 (Session 106 - Simplified app-owned runtime state shape for active operator)

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

## Session 105 - Active Operator State Should Stay App-Owned, Not Database-Owned, By Default

- Treat the currently active operator as app/session context: it represents who is using the computer right now, not something inherently owned by a specific database file.
- Keep live active-operator state in application memory during runtime unless a later approved design says otherwise.
- If the app remembers the operator across restarts, prefer saving that remembered value through configuration/app-owned persistence timing rather than treating it as database-owned runtime preference by default.
- Historical saved entries may still snapshot their own `operator` values in the database; that audit/history data is separate from the app's current active-operator state.
- Avoid dual ownership where both `config.ini` and database-backed runtime preferences try to be authoritative for the same active-operator concept.

## Session 106 - Prefer Plain App Runtime State Over Tiny Getter/Setter Wrapper Objects

- When app-owned runtime state currently holds only one value, prefer a broader plain state holder such as `AppRuntimeState` with direct attributes instead of a hyper-specific wrapper like `ActiveOperatorContext` with dedicated getter/setter/clear methods.
- Keep normalization at clear boundaries rather than inventing ceremony just to mutate one string in memory.
- For the active operator specifically:
  - seed `AppRuntimeState.active_operator` from startup success
  - let the running app/shell keep that live value in memory
  - strip at persistence boundaries such as saving `last_operator` back to `config.ini`
- If a second real app-owned runtime value appears later, extend the same runtime-state holder rather than creating another single-purpose context object by default.

## Expected Content Areas

- Entity validation patterns and common mistakes
- Configuration-driven validation lessons
- Business rule implementation patterns
- Error handling approaches
- Data transformation patterns

---

**Note**: Keep architecture decisions in `ai_instructions/architecture/core_architecture.md`. This file is for implementation lessons and pitfalls.


# Database Implementation Learnings

**Purpose**: SQLite-specific lessons, query patterns, and database implementation pitfalls learned during development.

**Last Updated**: 2026-05-05 (Session 088 - Added communication portability import/apply ownership lesson)

## Session 032 - Repository Settings Bootstrap

- When a new repository-level business rule needs database-backed configuration, prefer a small `settings` table over hardcoding values in Python.
- Repository initialization should not stop after detecting core tables; it must also ensure new support tables/default rows exist so older file-backed databases upgrade safely.
- Store tunable timing rules in seconds (`edited_flag_grace_period_seconds`) instead of larger units to make future adjustments more precise without changing code.

## Session 037 - Personnel Repository Query and Validation Patterns

- When a SQLite `CHECK` constraint maps directly to a repository-facing invalid state, validate it in the repository first so callers get a clear Python error instead of a lower-level SQLite failure.
- For personnel data, treat `logged_time` as the authoritative recency field for general list/history views, while `last_contact_time` drives active operational-awareness ordering and `expected_checkin_time` drives overdue-alarm urgency ordering.

## Session 053 - Reset Flow Must Stay Backend-Aware

- Shared reset coordination should stay technology-neutral at the sequencing level only; actual lock/close/delete work must remain backend-owned because different technologies have different active handles, sidecar artifacts, bootstrap traces, and deletion requirements.
- Do not let one backend's current artifact set become the implied generic reset contract in shared modules. Shared code may coordinate phases and neutral outcomes, but backend-specific reset/invalidation and artifact cleanup should plug in from backend-owned seams.

## Session 064 - Startup Requirement Contracts Must Stay Technical

- A persistence-owned startup capability seam should expose only stable technical startup requirements such as field identity, input kind, and required/editable flags.
- Do not push presenter-flavored metadata like labels or browse-button actions down into `src/db/repositories/startup_selection.py`; that leaks GUI concerns into the persistence contract and creates duplicate mapping layers.

## Session 069 - Startup Backend Policy Should Have One Authoritative Owner

- When startup/bootstrap backend facts are split across factory helpers, remembered-target serializers/resolvers, app wiring, and startup-selection helpers, future work tends to grow around the split and creates immediate refactor pressure.
- Prefer one centralized backend-policy seam that owns supported dialects, startup field requirements, remembered-target normalization/persistence behavior, cleanup metadata dispatch, coarse capability facts, and per-dialect repository construction dispatch.
- Shared startup field/profile types may remain in a small separate module, but policy decisions themselves should not be duplicated across multiple startup modules.

## Session 081 - Bounded Recursion Can Be Better Than Ad Hoc Hierarchy Handling

- When the domain is naturally hierarchical, do not reject recursive storage/reading patterns just because they look abstract at first glance.
- The user explicitly prefers a recursive or tree-like structure over sprawling special-case `if/else` handling when it makes the model cleaner and more uniform.
- For communication configuration, a recursive shape may still be desirable even if the current operator-facing UI caps depth at three tiers.
- The real design question is not “avoid recursion?” but rather “how much recursion should the business rules permit, and where should the current UI/runtime place its practical depth limit?”

## Session 088 - Whole-Bundle Communication Portability Apply Should Stay Repository-Owned and Exact

- When importing approved communication portability bundles, keep contract validation and payload parsing in Core, but keep the actual database replacement/deactivation work in a repository-owned seam.
- Prefer one exact-replace apply method for active communication configuration over stitching together many smaller targeted mutations from Core; it is more deterministic, more reviewable, and easier to keep transactional.
- A practical SQLite policy is:
  - upsert/reactivate imported systems by stable `system_name`
  - recursively upsert imported options within each parent scope by stable `option_value`
  - soft-deactivate missing systems/options via `is_active`
  - replace qualifier rows exactly per system because they are runtime metadata rather than historical entry snapshots
- Validate the full bundle before entering the repository apply path so malformed payloads fail before any partial import writes occur.

## Session 054 - Reset Integration Tests Need Real On-Disk SQLite Targets

- For reset-flow integration coverage, prefer temporary on-disk SQLite databases over `:memory:` so the test can exercise the real close/invalidate/delete sequence and confirm file-backed cleanup behavior.
- Cover credential-mode combinations explicitly in reset integration tests: no password/no key file, password only, password plus key file, and key-file only.

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


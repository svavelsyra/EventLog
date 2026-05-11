# Getter/Setter Refactor Plan

**Status:** Living review document with approved startup-direction guardrails  
**Purpose:** Prevent trivial getter/setter and one-callback-per-setter patterns from expanding further in the GUI layer, starting with the startup dialog seam.

---

## Why this plan exists

The current startup dialog seam is accumulating more fine-grained accessor and callback-registration methods than is desirable for idiomatic Python and for this project's preference for small, meaningful interfaces.

This document exists to:
- stop the current pattern from spreading,
- define what kinds of seams are acceptable,
- plan a small-step refactor path,
- and provide a place for later method-by-method classification.

This is a **plan only** document. It does not approve immediate refactoring by itself.

However, one direction is now approved and should be treated as the default for startup-dialog work:
- presenter-owned whole-state rendering,
- structured submission readback,
- thin controller orchestration,
- and skepticism toward new per-field accessor/callback seams.

---

## Problem Statement

The startup GUI seam currently includes several methods that appear to be simple pass-throughs for widget state rather than meaningful behavior-oriented UI operations.

This creates several risks:
- future AI may treat the current shape as the preferred pattern and add more of the same,
- controller/view contracts may become increasingly chatty,
- low-value abstraction may replace directness without clear benefit,
- review churn increases because every new field may invite another getter/setter pair or callback setter.

---

## Refactor Goals

1. Preserve clear ownership between presenter, controller, and view.
2. Prefer **state-based**, **submission-based**, and **intent-based** seams over field-by-field plumbing.
3. Keep GUI seams thin and testable without becoming ceremony-heavy.
4. Avoid unnecessary review churn and avoid refactors that merely rename methods without reducing coupling.
5. Create explicit guardrails so future work does not continue this pattern by default.

---

## Scope

### In Scope
- `src/gui/startup_dialog_controller.py`
- `src/gui/views/startup_dialog_view.py`
- `tests/unit/gui/test_startup_dialog_controller.py`
- `tests/unit/gui/views/test_startup_dialog_view.py`

### Reference-Only for Comparison
- `src/gui/app_shell.py`
- `src/gui/views/main_window_shell_view.py`

### Out of Scope for the First Pass
- presenter behavior changes in `src/gui/presenters/startup_dialog_presenter.py`
- broad app-wide GUI API redesign
- Tk layout redesign
- unrelated cleanup or wording changes with no clear structural win

---

## Design Principles

### 1. Behavior beats plumbing
Keep methods that represent meaningful UI behavior, lifecycle, or intent.
Avoid methods that only forward one value with no additional meaning.

### 2. Prefer state objects and submissions
If data is already naturally represented by `StartupDialogState` or `StartupDialogSubmission`, prefer extending those instead of adding new getter/setter methods.

### 3. Thin seams, not chatty seams
A seam should hide toolkit details where helpful, but it should not expand into a one-method-per-widget-variable interface.

### 4. Preserve behavior before simplifying shape
The first refactor goal is not beauty by itself. The goal is to simplify the seam while keeping behavior unchanged.

### 5. No churn without a clear win
Do not refactor purely for taste. Any retained or removed method should have a clear rationale.

---

## Decision Criteria: Keep vs Refactor

### Keep a method if it:
- expresses a meaningful UI action,
- manages lifecycle behavior,
- hides real Tk-specific complexity,
- operates on whole state or submission objects,
- or clearly improves testability without adding ceremony.

### Refactor or remove a method if it:
- only mirrors `.get()` or `.set()` for a single value,
- exists only because a previous seam exposed one field too directly,
- pushes the controller into field-by-field orchestration,
- or encourages future additions of the same low-level pattern.

### Defer a decision if:
- removal would force a worse design,
- the method participates in a broader pattern not yet classified,
- or the team first needs to agree on the preferred seam shape.

---

## Current Candidate Areas of Concern

### Likely trivial accessor candidates
- `get_field_value(...)`
- `set_field_value(...)`
- `get_operator_value()`
- `set_operator_value(...)`

### Likely callback registration growth area
- `set_submit_callback(...)`
- `set_cancel_callback(...)`
- `set_migrate_callback(...)`
- `set_emergency_reset_callback(...)`
- `set_browse_database_callback(...)`
- `set_browse_key_file_callback(...)`
- `set_database_path_changed_callback(...)`
- `set_mode_changed_callback(...)`
- `set_target_source_changed_callback(...)`
- `set_dialect_changed_callback(...)`

### Likely behavior-oriented methods that are probably fine
- `render_state(...)`
- `get_submission(...)`
- `clear_sensitive_fields(...)`
- `focus_primary_input()`
- `set_error_message(...)`
- `clear_error_message()`
- `set_status_message(...)`
- `clear_status_message()`
- `destroy()`

These are initial impressions only. Final classification belongs in the later classification section.

---

## Preferred Direction of Travel

### Prefer
- state-driven rendering,
- submission-driven reads,
- intent-level methods,
- small callback bundles or consolidated callback binding,
- directness where abstraction adds no value.

### Avoid
- one getter or setter per field,
- one callback setter per event by default,
- growing protocols just because a new widget variable exists,
- introducing interface ceremony that looks more like Java/C# than Python.

## Approved Startup Dialog Default Direction

For the startup dialog specifically, future work should assume this seam unless there is a documented reason to do otherwise:

1. Presenter computes and returns `StartupDialogState`.
2. View applies that state with `render_state(...)`.
3. Controller reads current operator input through `StartupDialogSubmission`.
4. Presenter recomputes the next state from that submission.

### What this resolves now

- Prefill should normally flow through state, not dedicated per-field setters.
- Ordinary operator input reads should normally flow through submission objects, not dedicated per-field getters.
- Dynamic field visibility/requiredness should continue to come from the presenter plus backend field contract, not hidden duplicated booleans.
- New callback seams should be justified as intent-level UI actions, not created automatically for each widget event.

### What still remains reviewable

- Whether some existing helper methods still earn their keep because they hide real Tk complexity.
- Whether callback registration should later be consolidated into a bundle or another smaller mechanism.
- Exact sequencing for later code refactor slices.

---

## Proposed Refactor Sequence

### Phase 1 - Freeze and classify the seam
Objective:
- Stop accidental expansion of the current pattern.
- Decide what kinds of methods are acceptable.

Deliverable:
- Method-by-method classification of the current startup dialog seam.

### Phase 2 - Reduce callback registration sprawl
Objective:
- Review whether one-callback-per-setter is still justified.
- Consider consolidating callback registration into a smaller, more meaningful mechanism.

Possible replacement directions:
- one `bind_callbacks(...)` style method,
- one callback bundle/dataclass,
- or constructor-time callback injection if appropriate.

### Phase 3 - Remove trivial value accessors
Objective:
- Replace fine-grained field getter/setter methods with state/submission/intention-based flow where practical.

Focus areas:
- operator prefill,
- direct field mutation from controller code,
- field-by-field view reads outside `get_submission(...)`.

### Phase 4 - Simplify controller/view interaction
Objective:
- Ensure the controller orchestrates behavior rather than managing widget traffic.

Desired controller role:
- request submission,
- render presenter state,
- react to user intent,
- show error/status/focus changes.

### Phase 5 - Update tests to reinforce the better pattern
Objective:
- Make sure tests guide future work toward the desired seam shape rather than preserving the current accessor-heavy direction by inertia.

---

## Risks and Things to Watch

- Replacing trivial accessors with a worse abstraction is not a win.
- Over-abstracting callback binding may make the view harder to understand.
- Removing methods too early may create noisy intermediate states in tests.
- Presenter ownership must remain intact; this refactor must not move business decisions into the controller or view.

---

## Non-Goals

This plan does **not** assume that:
- every getter/setter is automatically wrong,
- every callback setter must disappear,
- the startup dialog must be rewritten wholesale,
- the entire GUI layer must follow one single pattern immediately.

The goal is to remove **trivial** or **pattern-creep** seams, not to chase purity.

---

## Guardrails for Future Work

Future changes in this area should follow these rules:

1. Do not add a new one-field getter/setter unless there is a strong, explicit reason.
2. Do not add a new callback setter by default; first consider whether it belongs in a higher-level registration mechanism.
3. Prefer extending `StartupDialogState` before adding a new setter.
4. Prefer extending `StartupDialogSubmission` before adding a new getter.
5. Ask: "Is this behavior, or just plumbing?" before expanding the seam.
6. Avoid review churn that does not produce a clear structural or behavioral win.

---

## Open Questions

1. How much callback consolidation is desirable before readability suffers?
2. Which remaining helper methods hide enough Tk-specific behavior to stay public?
3. How much should test seams influence the final public protocol shape?

---

## Future Classification Section

This section is intentionally left as a placeholder for the next review step.

### Classification table template

| Method / Seam | File | Current Role | Initial Classification | Proposed Action | Rationale | Dependencies / Notes |
|---|---|---|---|---|---|---|
| `get_operator_value()` | `src/gui/startup_dialog_controller.py` / `src/gui/views/startup_dialog_view.py` | Dedicated operator read seam between controller and view | Refactor | Remove dedicated accessor and rely on `StartupDialogSubmission.operator` for reads | This was a thin wrapper around one value and duplicated existing submission flow | Completed in first refactor slice |
| `set_operator_value(...)` | `src/gui/startup_dialog_controller.py` / `src/gui/views/startup_dialog_view.py` | Dedicated operator prefill seam between controller and view | Refactor | Remove dedicated accessor and carry operator through `StartupDialogState.operator` for rendering | State-driven rendering is a better fit than a special-case setter for one field | Completed in first refactor slice |
| _TBD_ | _TBD_ | _TBD_ | _Keep / Refactor / Defer_ | _TBD_ | _TBD_ | _TBD_ |

### Planned first classification targets
- `get_field_value(...)`
- `set_field_value(...)`
- `get_operator_value()`
- `set_operator_value(...)`
- callback registration methods in `StartupDialogViewProtocol`

---

## Review Outcome Tracking

### Confirmed review items
1. Review and reduce unnecessary getter/setter style in the startup dialog GUI seam.

### Completed first refactor slice
- Removed the special operator getter/setter seam.
- Operator prefill now flows through `StartupDialogState.operator` for rendering.
- Operator reads continue through `StartupDialogSubmission.operator`.

### Completed later small callback slice
- Consolidated the four equivalent submission-change callback setters into one `set_submission_changed_callback(...)` seam.
- Database-path edits, mode changes, target-source changes, and dialect changes now all route through the same presenter-rerender callback path.
- Intent-specific action callbacks (`submit`, `cancel`, `migrate`, browse actions, emergency reset) remain separate for now because they still represent distinct controller behavior.

### Completed later small action-wiring slice
- Replaced the controller-facing per-action callback setter list with one `set_action_callbacks(...)` registration seam carrying distinct action callbacks in a small bundle.
- Kept submission-change rerenders on their own seam instead of merging them into the action bundle.
- Left any old per-action setters as concrete-view compatibility wrappers only, so the controller/view protocol now reflects the smaller intended shape without forcing a wider removal slice immediately.

### Deferred until further classification starts
- exact replacement API shapes
- exact sequencing inside each phase

---

## Working Rule Until Refactor Starts

Until this plan is executed, treat new getter/setter additions in the startup dialog seam as suspicious by default and require justification before extending the pattern.


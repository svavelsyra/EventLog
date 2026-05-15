# Startup Dialog Rework Plan

**Status:** Approved direction, implementation pending  
**Purpose:** Preserve the startup-dialog audit findings, the agreed design direction, and a smallest-safe implementation order so this work does not drift or get forgotten.

---

## Why this document exists

The current startup dialog accumulated several contradictions between:
- the documented single-database security model,
- the documented presenter/view/controller ownership rules,
- the documented responsive-dialog requirements,
- and the actual implementation shape.

This document keeps the findings and the agreed repair direction in one place so future work does not only remember the final decision and forget the reasons.

---

## Summary of Agreed Direction

For the current local SQLite model, EventLog should use:

1. **One active database only**
2. **One fixed app-owned database location**
3. **No ordinary startup-time operator choice of database path**
4. **Create vs unlock inferred from whether the managed database exists**
5. **`Nollställ` returns the app to fresh startup state in-process**
6. **If the operator wants to preserve an old database, they manually move/copy it out of the managed location**

This direction intentionally prefers a coherent operator workflow and honest security boundary over contradictory half-restrictions.

---

## Findings To Preserve

These findings should remain visible during implementation so the work does not regress into the same problems.

### 1. The startup dialog currently violates the responsive-dialog rule

The current view hard-locks the startup dialog to a fixed size instead of following the documented responsive sizing and scrollbar-fallback direction.

Why this matters:
- the project explicitly requires accessible content on small screens,
- fixed-size dialogs without fallback are a documented anti-pattern,
- this is a real UI-contract violation, not just polish.

### 2. The controller currently owns startup-policy behavior that belongs in the presenter

The current controller contains remembered/manual-target behavior during browse/update flows.

Why this matters:
- startup flow decisions are supposed to be presenter-owned,
- the controller is meant to stay thin,
- this is a layer-boundary violation, not just a naming/style issue.

### 3. The current SQLite startup shape still carries dormant global mode-selector scaffolding

The code still includes UI/state scaffolding for a create/open selector even though the approved SQLite direction is to infer create vs unlock from current state instead of exposing a separate global mode choice.

Why this matters:
- hidden scaffolding still teaches the wrong seam to future work,
- it preserves the wrong product shape even when not visible,
- it should not be kept around just for convenience.

### 4. The startup dialog currently contradicts the single-database security model

The current implementation behaves like a general database chooser while the documented security/design direction says the app is single-database-only and that replacing the active database should happen through `Nollställ`.

Why this matters:
- this is the central contradiction,
- it affects both UX and security expectations,
- it is the main reason arbitrary target selection should be removed for the local SQLite path.

### 5. The startup seam still contains lower-value field-plumbing leftovers

Some public-ish field-level helper seams remain in the startup view shape even though the approved direction is whole-state rendering plus structured submission readback.

Why this matters:
- not the highest-priority bug,
- but it encourages future seam creep if left unaddressed after the main behavior is fixed.

### 6. One thing that was aligned should still be remembered

The earlier browse-database implementation used a save-style picker with `confirmoverwrite=False`, which matched the previously documented browse behavior.

Why keep this note:
- it avoids rewriting history as if everything about the startup slice was wrong,
- but this browse flow may become obsolete once ordinary startup path selection is removed.

---

## Product Rules Going Forward

### Managed SQLite location rule
- The local SQLite runtime has one app-owned managed database path.
- Ordinary operators do not choose arbitrary database locations during startup for this mode.
- Startup inspects that managed location and decides whether the app is in create or unlock flow.

### Startup state rule
- Managed database exists -> unlock/open flow.
- Managed database missing -> create flow.
- Managed database manually moved/deleted -> startup falls back to create flow automatically.

### Reset rule
- `Nollställ` clears the active app-owned state relevant to reset.
- After reset, the app returns to fresh startup/bootstrap state in the same running process.
- This is acceptable even though the Python process remains alive; the project does not promise full forensic-memory eradication.

### Preservation rule
- If the operator wants to keep an old database copy, they manually move/copy it out of the managed location.
- EventLog manages one active operational database, not an archive of startup-selectable databases.

---

## Implications For The Startup UI

### UI elements that should disappear for the local SQLite path
- remembered/manual target source selector
- arbitrary database browse button for normal startup
- operator-editable database path as a normal startup control
- wording that frames startup as choosing among databases
- controller/view seams that only exist to support multi-target switching

### UI elements that remain meaningful
- operator name
- password
- password confirmation in create flow
- key file input if required by the selected backend/state
- error/status messages
- `Nollställ`
- cancel/exit
- create/unlock primary action

---

## Implications For Ownership

### Presenter should own
- whether startup is currently create or unlock,
- state recomputation from managed-location existence,
- startup state after reset,
- any remaining dynamic visibility/requiredness decisions.

### Controller should own
- action wiring,
- render orchestration,
- close/restart/startup lifecycle hooks owned by the app shell.

### Controller should stop owning
- remembered/manual target policy,
- arbitrary path mutation for startup target selection,
- browse-driven startup policy changes.

---

## Implementation Sequence (Smallest Safe Order)

## Slice 1 - Lock the direction into docs

**Goal:** prevent future drift before code changes.

**Files:**
- `ai_instructions/design/security_design.md`
- `ai_instructions/design/gui_design.md`
- `docs/design/root_design.md`
- optionally `ai_instructions/architecture/gui_architecture.md`

**Change:**
- state the fixed managed SQLite location,
- remove local-SQLite manual-target framing,
- state that `Nollställ` returns to startup in-process,
- document manual preservation of old DB copies as an external operator workflow.

**Good stopping point:** confirm that the docs now describe the same product.

---

## Slice 2 - Introduce one source of truth for the managed SQLite path

**Goal:** stop startup from depending on operator-picked DB paths.

**Likely files:**
- `src/config/app_config.py`
- nearby bootstrap-target resolution code if that currently owns startup target resolution
- any config/bootstrap helper that needs to resolve the managed app-owned SQLite path

**Change:**
- define/resolve the fixed app-owned SQLite path in one place,
- make it available to startup logic without operator entry.

**Good stopping point:** confirm that startup code can answer "does the managed DB exist?" without UI input.

---

## Slice 3 - Move startup mode determination fully onto managed-location state

**Goal:** derive create vs unlock from app-owned state rather than target-selection UX.

**Likely files:**
- `src/gui/presenters/startup_dialog_presenter.py`
- any nearby startup-policy helper if needed

**Change:**
- presenter derives create/unlock from the managed location,
- presenter state shrinks away from target-source logic,
- multi-target state fields become removable or clearly transitional.

**Good stopping point:** confirm presenter state matches the chosen product model before major view removal.

**Temporary-debt warning:** if Slice 3 introduces presenter-side backend identity checks or other architecture-boundary shortcuts to reach the managed-target behavior, those shortcuts must be treated as transitional only and removed by an explicit later slice. They are not an acceptable final ownership shape.

---

## Slice 3.5 - Remove presenter-side backend hardcoding introduced during the managed-target transition

**Goal:** restore the intended database-agnostic ownership shape after Slice 3 product behavior is working.

**Likely files:**
- `src/gui/presenters/startup_dialog_presenter.py`
- backend-owned startup-policy/profile helpers near `src/db/repositories/bootstrap_backend_policy.py`
- any nearby startup-policy helper that should own managed-target capabilities
- direct presenter/controller tests if the generic policy seam changes

**Change:**
- remove presenter logic that branches on backend identity (for example `sqlite`) to decide startup behavior,
- move fixed-target/managed-target startup behavior behind backend-owned policy or capability seams,
- keep the presenter consuming backend-owned startup facts instead of teaching backend-specific rules,
- remove any transitional compatibility mapping that only exists because Slice 3 took a shortcut through the presenter.

**Good stopping point:** confirm startup behavior is still correct, but the presenter no longer treats SQLite-by-name as the way to express the product model.

---

## Slice 4 - Simplify the startup view to match the new model

**Goal:** remove UI that no longer matches product behavior.

**Files:**
- `src/gui/views/startup_dialog_view.py`
- `tests/unit/gui/views/test_startup_dialog_view.py`

**Change:**
- remove target-source controls,
- remove browse-database button,
- remove ordinary operator-edited DB-path startup field if no longer needed,
- update titles/summary copy,
- preferably fix the fixed-size dialog rule violation while already touching the view.

**Good stopping point:** confirm the view now reflects one managed SQLite database instead of a chooser workflow.

---

## Slice 5 - Thin the controller around the simplified startup model

**Goal:** remove policy logic that should never have lived there.

**Files:**
- `src/gui/startup_dialog_controller.py`
- `tests/unit/gui/test_startup_dialog_controller.py`

**Change:**
- remove browse-driven target mutation logic,
- remove remembered/manual target switching,
- keep controller limited to orchestration and GUI-side effects.

**Good stopping point:** confirm the controller is now thin again.

---

## Slice 6 - Implement unified in-process reset-to-startup lifecycle

**Goal:** make `Nollställ` return to startup instead of exiting the process.

**Likely files:**
- `src/gui/app_shell.py`
- related lifecycle/bootstrap ownership code if needed
- `tests/integration/security/test_reset_ui_slice.py`

**Change:**
- close/invalidate current active runtime state,
- clear startup-related runtime state as needed,
- route back to startup flow in-process,
- avoid split semantics between startup-reset and main-window-reset.

**Good stopping point:** confirm reset behavior feels correct before cleanup.

---

## Slice 7 - Final seam cleanup

**Goal:** remove leftover scaffolding after behavior is already correct.

**Possible files:**
- `src/gui/presenters/startup_dialog_presenter.py`
- `src/gui/views/startup_dialog_view.py`
- related tests
- optionally `docs/getter_setter_refactor_plan.md` if resolved items should be noted there

**Change:**
- remove obsolete state fields,
- remove dead mode-selector scaffolding,
- narrow or remove leftover field-plumbing seams that only survived as compatibility scaffolding.

---

## Recommended Minimal First Implementation

If only the highest-value behavioral contradiction should be fixed first, the best initial code focus is:

1. docs alignment,
2. presenter startup-state logic,
3. startup view simplification,
4. controller cleanup.

This already removes the worst contradiction even before the full in-process reset lifecycle is implemented.

---

## Caveats To Keep Visible

### Memory caveat after in-process reset
Returning to startup without terminating the process does not imply perfect memory eradication. This is acceptable because the project does not claim full forensic-recovery prevention.

### Why this is still consistent with the permissive operator philosophy
This design does not treat the operator as incapable. Instead, it makes the app's boundary explicit:
- EventLog manages one active database location.
- If the operator wants to preserve or archive another copy, that is a manual file operation outside the startup dialog.

That is clearer and more honest than exposing a permissive-looking chooser UI while still claiming a one-database security model.

---

## Related Documents

- `docs/design/root_design.md`
- `docs/getter_setter_refactor_plan.md`
- `ai_instructions/design/security_design.md`
- `ai_instructions/design/gui_design.md`
- `ai_instructions/architecture/gui_architecture.md`
- `ai_memory/gui_learnings.md`


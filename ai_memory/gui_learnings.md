# GUI Implementation Learnings

**Purpose**: Durable Tkinter, presenter/view, and GUI-testing guidance for this project.

**Last Updated**: 2026-05-13 (Session 121 - Main-window export/template actions should use explicit save dialogs)

---

## What Belongs In This File

- Keep reusable GUI rules, stable boundary decisions, and durable testing patterns here.
- Keep session-by-session narration, temporary migration notes, and "I changed X" history in `session_logs/`.
- Favor compact, high-signal rules over exhaustive historical context.
- Do not store one-off widget placements or task-local visual decisions here unless they express a broader cross-session preference the AI should reliably reuse.

---

## Tkinter Layout And Sizing

### Prefer simpler dynamic layout patterns over dense per-widget grid spacing when they fit the UI

- User preference: when a Tkinter slice is naturally linear or adaptive, prefer a dynamic `pack(...)`-oriented layout over a heavily hand-spaced `grid(...)` layout with many per-widget `padx` / `pady` tweaks.
- Do not treat `grid(...)` as the default just because a form has several controls; choose the layout manager that keeps the structure clearer and the code less noisy.
- If `grid(...)` is still the better fit for a form/table slice, keep spacing decisions as coarse and shared as practical instead of repeating many tiny manual spacing adjustments.

### Prefer grid weights and sticky expansion over fixed widths

**Problem**: Entry, Combobox, and Text widgets with fixed character widths often misalign or clip on small screens.

**Use this pattern**:
- Configure the input columns with grid weight before placing expanding widgets.
- Grid single-line inputs with horizontal sticky expansion and consistent field padding.
- For multi-line `Text`, keep the width minimal and let the grid cell provide the actual width.

**Key points**:
- Configure column weights before placing expanding widgets.
- Use `sticky=tk.W + tk.E` for horizontally stretchable inputs.
- Use `sticky=tk.NW` for labels beside multi-line fields.
- Keep padding consistent so labels and inputs read as one form.

### Size windows after creating widgets

**Problem**: Hard-coded geometry can clip content on the target small-screen hardware.

**Use this pattern**:
1. Set the minimum supported window size first.
2. Create the widgets.
3. Let Tk calculate required size with `update_idletasks()`.
4. Clamp the final size against the minimum supported dimensions.
5. Apply the resulting geometry only after that calculation.

**Rule**: Let Tk calculate required size after widget creation, then clamp to the minimum supported size.

---

## GUI Boundary Rules

### Prefer read-only structural protocols across GUI/app boundaries

- When the GUI consumes result objects from another layer, prefer read-only `@property` protocol members over writable protocol attributes.
- Prefer structural conformance over forcing app-layer value objects to inherit GUI-specific protocols.
- Keep advisory information separate from failure lists so the GUI can distinguish "warning/follow-up" from true operation failure.

### Keep startup flow ownership in the presenter

- If startup mode, visible fields, or remembered/manual target behavior depends on current operator input, that logic belongs in the presenter.
- The startup controller should stay thin: read `StartupDialogSubmission`, ask the presenter for state, render `StartupDialogState`, and manage UI-side effects such as focus or close behavior.
- Do not split initial startup resolution and later interactive recomputation across different layers.

### Prefer whole-state rendering and structured submission over per-field plumbing

- Treat `StartupDialogState` as the normal render seam.
- Treat `StartupDialogSubmission` as the normal readback seam.
- Do not add one getter/setter or hidden flag per field unless there is a clear lasting reason.
- If a value must survive presenter-driven rerenders, promote it into presenter-owned state instead of patching it into the view with a special setter.
- When presenter-owned field values must stay current even while a field becomes hidden, synchronize those state-backed values in one dedicated place during render instead of splitting the same field sync across multiple branches.
- In GUI state-to-widget synchronization, a small equality guard before writing a widget variable is acceptable defensive code even when it looks redundant; Tk/GUI code tends to accumulate side effects over time, so avoiding unnecessary writes can be the safer default when it does not complicate the seam.

### Do not duplicate field-contract facts or round-trip policy flags through the view

- If shared field metadata already describes requiredness, presence, or editability, let the view derive those facts from the field contract.
- Do not add extra presenter/view booleans for facts already present in the shared backend field contract.
- Treat administrator policy as presenter/config input and operator-entered values as submission input; do not send hidden policy booleans back through the view.

### Prefer intent-level seams over generic mutation seams

- Prefer narrow intent-specific methods when one write seam is genuinely needed.
- Avoid generic controller-facing field mutation APIs unless the controller truly needs unconstrained mutation.
- If several widget events all mean "submission changed, recompute presenter state", route them through one callback seam.
- Do not keep one private handler per widget/event when they all forward unchanged to the same action; that sets a precedent for callback-noise proliferation and teaches future work to copy ceremony instead of identifying the real seam.
- When one notifier can safely satisfy both `command=` and `bind(...)`, prefer wiring directly to that notifier over naming multiple identical pass-through wrappers.
- If several direct actions are distinct but belong to the same registration concern, bundle them in one stable action-callback contract.
- Once the final seam is adopted, remove obsolete compatibility wrappers instead of leaving dead transitional API behind.
- Do not add a helper that merely forwards to a Tkinter dialog or stdlib filesystem builtin with the same arguments; if the caller is the only place that knows the correct title/filetypes/behavior, keep that configuration at the caller and inject only the callable seam the tests actually need.
- Prefer monkeypatching Tk/stdlib side effects in tests over adding constructor parameters purely so tests can override `filedialog`, `messagebox`, or filesystem-existence calls. If an override hook only exists to avoid patching a standard library function, that is usually a bad production seam.

---

## Startup Dialog Specific Guidance

### Local SQLite startup now assumes one fixed app-owned active database location

- For the current local SQLite model, the startup UI should treat the application as having one active database only, stored at one fixed app-owned location.
- Do not present ordinary operators with arbitrary database-path selection during startup for this mode.
- If the managed database exists, startup should stay attached to that target and show the appropriate unlock/open flow.
- If the managed database is missing, startup should fall back to create flow for that same managed location.
- If the operator wants to preserve an old database copy, the expected workflow is manual file move/copy outside the managed location rather than keeping multiple active startup-selectable targets inside the app.

### Prefer one reset lifecycle: Nollställ returns to fresh startup state in-process

- Preferred product direction: after `Nollställ`, the app should return to the startup dialog / fresh bootstrap state instead of exiting the process.
- Treat this as acceptable even though the Python process remains alive; the project does not promise full forensic-memory eradication, and the simpler coherent operator flow is more important here.
- Avoid splitting reset semantics into separate "startup reset exits" versus "main-window reset restarts" behaviors unless there is a very strong reason.

### Infer SQLite create vs unlock from the selected path

- For the current SQLite flow, do not add a separate create/open selector in the UI.
- Infer create vs unlock from whether the selected database path already exists.
- Keep `show_mode_selector` only as a future backend-capability escape hatch, not as a dormant SQLite control.

### Database browse flow must support existing or new paths

- The startup database picker must allow selecting an existing database or specifying a new one from the same browse action.
- Prefer the save-style Tk dialog with `confirmoverwrite=False` so Windows does not show a misleading overwrite prompt during target selection.
- Keep nearby Swedish copy neutral so it does not promise only existing-database selection.

---

## Main-Window Lifecycle Guidance

- Keep destructive reset wired through app-owned callbacks, not widget-local cleanup code.
- Keep normal shell close on a separate app-owned seam from destructive reset.
- The shell view should stay thin: register callbacks, display coarse status, and let app ownership decide whether the window closes.
- For user-triggered template generation or exports, let the GUI ask for an explicit destination path with a save dialog instead of silently writing beside some internal config file; this makes the destination visible and keeps path-picking in the GUI layer.

---

## GUI Testing Patterns

### Model presenter-shaped states explicitly in view tests

- When a view test needs a narrow presenter-shaped state, build that state explicitly instead of relying on a broad helper whose defaults may hide contract drift.

### Prefer real GUI actions in integration slices

- For reset and other lifecycle coverage, prefer a small subprocess-backed Tk slice that clicks real buttons through app-owned callbacks.
- Keep scenario callables top-level and spawn-safe.
- Capture whether a dialog remained open immediately after the relevant action if that is part of the contract being tested.

### Favor durable test seams over convenience seams

- Test seams should reinforce the intended public GUI contract, not preserve temporary compatibility scaffolding.
- If a helper or fake still reflects a transitional API after production code has settled, clean it up rather than teaching future work the wrong shape.
- In controller tests that use a fake view, prefer intent-level driver helpers over exposing fake widget-like vars/attributes for tests to mutate directly; `select_dialect(...)`, `select_mode(...)`, or `set_operator(...)` teach a better seam than repeated `.set(...)` calls on fake Tk-style state.
- When a GUI refactor collapses several widget handlers into one shared notifier or dispatcher, update tests to drive the real widgets/bindings again rather than preserving the old event count by calling the shared internal helper repeatedly.
- In Tk view tests, prefer a realistic widget trigger with any needed focus/update steps over a bare `event_generate(...)` that only approximates the UI path and may silently miss the real binding behavior.
- When view state synchronization must preserve hidden values across rerenders, add at least one regression that drives a visible-to-hidden transition and confirms `get_submission()` returns the presenter-owned current value rather than stale previously visible widget text.

### During active UI-only polish, defer test churn until the layout stabilizes

- When the user is iterating on visual alignment/spacing/layout polish, prefer the lightest safe validation loop during intermediate steps.
- For those UI-only iterations, use `get_errors` as the default immediate guardrail and avoid broad `pytest` reruns after every small layout tweak unless the user explicitly asks for validation or the change is no longer purely visual.
- Likewise, defer updating fragile view-layout assertions until the user signals that the UI shape is stable enough to lock in.
- Before declaring the UI slice complete, still do one final round of the appropriate test updates and validation so the stabilized layout contract is recorded intentionally rather than churned on every micro-adjustment.


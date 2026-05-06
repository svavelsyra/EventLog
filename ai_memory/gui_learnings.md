# GUI Implementation Learnings

**Purpose**: Tkinter-specific lessons, common pitfalls, and implementation patterns learned during GUI development.

**Last Updated**: 2026-05-06 (Session 096 - Added GUI reset integration-test pattern)

## Tkinter Grid Layout

### Common Pitfall: Misaligned Form Fields

**Problem**: Entry, Combobox, and Text widgets with fixed character widths don't align properly in grid layout.

**Why it happens**:
- Different widget types have different default sizes and padding
- Fixed character widths (e.g., `width=20`) don't account for widget borders
- Without sticky parameters, widgets don't expand to fill columns
- Without column weights, columns use minimum size

**Solution Pattern**:
```python
# 1. Configure column weights FIRST
form_frame.columnconfigure(1, weight=1)  # Input column expands
form_frame.columnconfigure(3, weight=1)  # Input column expands

# 2. Remove fixed widths, use sticky parameter
ttk.Entry(form_frame).grid(row=0, column=1, sticky=tk.W+tk.E, padx=(2,5), pady=2)
ttk.Combobox(form_frame, values=...).grid(row=1, column=1, sticky=tk.W+tk.E, padx=(2,5), pady=2)

# 3. Text widgets need width=1 (minimum) then expand with sticky
tk.Text(form_frame, height=3, width=1).grid(row=2, column=1, columnspan=3, sticky=tk.W+tk.E, padx=(2,5), pady=2)
```

**Key Points**:
- `columnconfigure(col, weight=1)` → Column expands to fill space
- `sticky=tk.W+tk.E` → Widget expands horizontally within cell
- `sticky=tk.NW` → For labels next to multi-line Text widgets (top-align)
- Consistent padding: Labels `padx=(5,2)`, Fields `padx=(2,5)` creates visual grouping

## Window Sizing

### Common Pitfall: Fixed Window Size Clips Content

**Problem**: Using `geometry("500x300")` without checking if content fits.

**Solution Pattern**:
```python
# 1. Set minimum size
self.root.minsize(min_width, min_height)

# 2. Create widgets
self._create_widgets()

# 3. Let window calculate required size
self.root.update_idletasks()
width = max(min_width, self.root.winfo_reqwidth())
height = max(min_height, self.root.winfo_reqheight())

# 4. Set calculated size and position
self.root.geometry(f"{width}x{height}+{x}+{y}")
```

**Lesson**: Create widgets before sizing window, let Tkinter calculate required dimensions.

## Common Mistakes to Avoid

❌ **DON'T**:
- Use fixed character widths when you want responsive layout
- Place widgets without sticky parameter if they should expand
- Forget to configure column/row weights
- Size window before creating widgets
- Assume all widgets have same visual width with same character width

✅ **DO**:
- Configure grid weights before placing widgets
- Use sticky parameter on all input widgets
- Test on minimum target screen size (800x600)
- Size windows after widget creation
- Account for different widget padding/borders

## Future Learnings

## Session 062 - GUI/App Protocol Boundaries

- When the GUI layer consumes a minimal protocol from app-owned result objects, define protocol members as read-only `@property` accessors instead of writable data attributes. Static type checkers may reject frozen dataclasses or named tuples as satisfying writable protocol attributes even when the runtime behavior is effectively immutable.
- Prefer structural conformance across the GUI/app boundary over nominal inheritance from GUI protocols in app-layer value objects. The app should return a normal result object with read-only properties, and the GUI protocol should describe only the read operations it needs.
- When a caller result needs to warn about a manual operator action that is not itself a reset failure (for example possible external key files), keep that signal in a separate advisory field rather than smuggling it into the same follow-up issue list that drives `MISSLYCKADES` messaging. GUI copy can then decide when to show the advisory without corrupting the success/failure contract.

## Session 064 - Startup Dialog State Should Not Duplicate Field Contract Facts

- When startup state already carries a shared field contract like `backend_fields`, do not add extra booleans for field presence, requiredness, or editability. Let the view derive those facts from the field contract so presenter state has one source of truth.
- For startup dialogs, label text and hint visibility may still be GUI-owned, but they should be derived from stable field identities plus presenter-provided copy rather than mirrored through extra state flags.

## Session 065 - Startup Policy Flags Should Not Round-Trip Through the View

- If a startup requirement like key-file mandatory/optional status is already expressed by the shared `backend_fields` contract, do not add a hidden presenter/view submission boolean such as `require_key_file` just to carry policy through re-renders.
- Treat administrator-configured policy as presenter/config input and operator-entered values as submission input. The view should submit the chosen `key_file_path`, not a second hidden policy toggle.

## Session 065 - Startup Mode Inference and Review-Churn Guardrail

- For current SQLite startup flows, do not add an explicit create/open selector in the UI. Create vs unlock should continue to be inferred from the selected target path (`database_path` exists => unlock, otherwise create).
- Treat `show_mode_selector` as a future backend-capability escape hatch for technologies whose selected target cannot imply create vs unlock. It is not a dormant SQLite control that should be revived by default.
- When the startup area already has a known larger structural destination, avoid intermediate GUI cleanups that are likely to be replaced in the next session and therefore create extra review churn. Prefer the real structural slice instead.

## Session 066 - Startup Refactor Steps Should Land in the Final Structure

- The startup refactor has an explicit user-approved exception to the default small-step preference: do not manufacture temporary presenter/view/controller shapes purely to make the current patch smaller if those shapes are expected to be removed immediately by the next approved startup step.
- For this refactor, step size should be judged by lasting architectural value and review efficiency, not only by line-count minimization. Prefer a larger coherent slice when it lands directly in the intended field-driven structure.

## Session 067 - Startup Flow Ownership Belongs in the Presenter

- When startup mode or visible startup-state changes depend on current operator input (`dialect`, `database_path`, remembered/manual target choice), treat that as presenter-owned flow logic, not controller policy.
- The startup controller should remain a thin Tk adapter: read current view submission, call the presenter for recomputed state, render it, and manage browse/reset/close wiring.
- Avoid splitting initial startup-state resolution and later interactive recomputation across different layers. If the presenter owns ongoing startup state decisions, it should also own initial remembered-target resolution so there is one authoritative startup flow path.

## Session 068 - Do Not Leave Known Startup Architecture Mismatches To Grow

- When a remaining startup-area architectural mismatch is already identified and new work would otherwise accumulate on top of it, do not accept “works for now” as sufficient justification to leave it in place.
- For startup refactors, prefer the next durable ownership-alignment slice over a smaller tactical patch if the smaller patch would knowingly preserve a mismatch that future work will build on.
- The user wants restart-ready session guidance that names the exact next architectural slice, so a future AI can continue with a simple “go on” prompt instead of rediscovering the intended direction.

## Session 092 - Model Presenter-Shaped Neutral Startup States Explicitly In View Tests

- When a Tk view test needs to verify a narrow startup state that depends on presenter filtering (for example blank-path SQLite create showing only the target field), prefer constructing an explicit `StartupDialogState` over reusing a broad helper whose defaults may include extra fields.
- For startup view coverage, helper builders are still useful for common full-form states, but presenter-specific neutral states should be modeled directly so the test cannot accidentally drift away from the presenter contract.

## Session 094 - Startup Database Picker Must Allow Existing Or New Paths Without Save-Dialog Nagging

- For the startup database target picker, do not switch to `askopenfilename()` just to avoid the native overwrite prompt; that would break the create-new-database path selection flow.
- Prefer the save-style Tk dialog with `confirmoverwrite=False` so operators can select an existing database or specify a new database path from the same browse action without getting the misleading Windows "overwrite?" confirmation.
- When the same manual-target control supports both open and create inference, keep the nearby Swedish UI copy neutral (for example `Välj eller ange databas manuellt`) instead of promising only existing-database selection.

## Session 096 - Main-Window Shell Lifecycle Belongs To App-Owned Callbacks

- When the visible main window needs top-level lifecycle behavior such as `Nollställ` or `WM_DELETE_WINDOW`, keep the shell view thin: it should register button/protocol callbacks and display coarse status only.
- Destructive reset must continue to flow through the existing app-owned reset seam (`run_active_context_reset` or an equivalent wrapper), not a widget-local cleanup implementation.
- Normal shell close should use a separate app-owned invalidate/release seam from destructive reset so the GUI does not blur ordinary shutdown with data-destruction behavior.
- A practical small-slice pattern is: app builds lifecycle callbacks, `AppShell` passes them into `MainWindowShellView`, and the view treats a returned status string as coarse operator feedback while successful callbacks close through app-shell ownership.

## Session 096 - GUI Reset Integration Tests Should Drive Real Buttons Through App-Owned Callbacks

- For reset UI integration coverage, prefer one small Tk subprocess-backed slice that clicks the real GUI buttons and asserts filesystem/config side effects afterward from the parent test process.
- Use `tests.gui_support.run_isolated_tk_scenario` for Tk isolation, but keep scenario callables top-level and spawn-safe.
- For startup reset coverage, a durable seam is the real `StartupDialogController` with a captured real `StartupDialogView` plus the app-owned startup emergency-reset callback.
- For main-window reset coverage, a durable seam is `MainWindowShellView` with the real app-owned reset callback and a minimal shell spy that records whether close ownership was invoked.
- When scheduling one-shot Tk actions inside these subprocess scenarios, an explicit `after(..., callback, "scheduled")` argument shape can satisfy the type checker more reliably than a bare callback.
- For startup-dialog reset failures, make the integration scenario capture whether the dialog was still open immediately after the button click before any forced cleanup; otherwise the test can accidentally assert only its own teardown behavior instead of the real UI contract.
- A verified reset contract worth preserving in integration tests: after active-context access denial succeeds, remembered bootstrap selectors are still cleared even if a later backend-cleanup phase fails. Later cleanup failures should keep the shell open and report follow-up work, but they do not roll back the selector clear.


# GUI Architecture (AI)

**Layer**: User Interface  
**Last Updated**: 2026-05-07 (Session 100 - Documented startup dialog state/submission seam and seam-growth guardrails)

## Overview
GUI layer uses Tkinter with MVP (Model-View-Presenter) pattern for testability.

**Architecture Decision**: Tabbed interface with specialized presenters per tab.

**Reasoning**: Three entity types (Communication, Event, Personnel) have different workflows and UI requirements. Separate tabs provide focused interfaces without overwhelming single view.

## MVP Pattern

### View (Pure UI)
**Location**: `src/gui/views/`

**Responsibilities**:
- Render UI components
- Capture user input
- Display data (no formatting logic)
- NO business logic
- NO database access

### Presenter (Coordination)
**Location**: `src/gui/presenters/`

**Responsibilities**:
- Handle user interactions
- Coordinate between View and Core
- Format data for display
- Validate user input (basic UI validation)
- Call Core layer for business operations
- Update View based on Core responses

### Startup Dialog Pattern (State-Driven MVP Slice)

The startup dialog is the current reference pattern for a dynamic Tk dialog whose visible fields change as the operator edits inputs.

**Ownership split**:
- **View** owns Tk widgets, widget variables, layout, focus, and browse-button wiring.
- **Presenter** owns startup flow decisions, prefill values, dynamic field selection, and recomputed dialog state.
- **Controller** is a thin Tk/app adapter: it reads one structured submission from the view, calls presenter methods, renders the returned state, and wires app-owned callbacks such as close/reset/browse flows.

**Preferred seam objects**:
- `StartupDialogState` = presenter → view render contract
- `StartupDialogSubmission` = view → presenter readback contract
- backend startup field requirements = persistence → presenter/view technical field contract

**Required interaction loop**:
1. Controller asks the presenter for state.
2. View renders that state through `render_state(...)`.
3. Operator changes something in the dialog.
4. Controller reads one `StartupDialogSubmission` from `get_submission(...)`.
5. Presenter recomputes the next `StartupDialogState`.
6. Controller re-renders the dialog.

**Why this is the preferred pattern**:
- prefill flows through one render contract instead of special-case setters,
- user-entered values flow back through one submission contract instead of one getter per field,
- presenter logic stays the authority for mode/field visibility and remembered-target behavior,
- the view remains thin even when fields are backend-driven and dynamic.

### Startup Dialog Guardrails

For dynamic dialogs like startup, treat the following as exceptions that require strong justification rather than the default pattern:

- adding one getter/setter per field,
- adding hidden submission booleans that duplicate field-contract facts,
- adding one callback-registration method per widget event when a smaller binding seam would do,
- moving recomputation of visible fields or startup mode into the controller,
- leaking GUI presentation details such as labels or browse semantics downward into persistence contracts.

The startup dialog may still keep a few field-oriented helper methods where Tk-specific behavior genuinely benefits from that seam, but the architectural default is **render whole state, read whole submission, keep controller thin**.

### Model (Domain)
**Location**: `src/core/`

Not part of GUI layer - these are Core domain models that Presenters use.

## Technology: Tkinter

### Why Tkinter?
- Standard library (no dependencies)
- Cross-platform
- Sufficient for offline desktop app
- Well-documented

### Main Components
- Widgets for user input and display
- Container widgets for layout
- Event handling for user interactions

## Responsive Design & Scrollbars

### Critical Requirement: All Content Must Be Accessible

**Architecture Decision**: All widgets, dialogs, and modals MUST display all their content, regardless of screen size.

**Problem**: Application targets netbooks with small screens (~1024x600) but must work on various screen sizes.

**Solution Pattern**: Dynamic resizing with automatic scrollbar fallback.

### Scrollbar Strategy

**Primary Approach - Window Resizing**:
- Windows and modals should resize reasonably with screen size
- Minimum sensible sizes defined per window type
- Layout uses proper pack/grid with fill/expand for responsive behavior

**Fallback Approach - Automatic Scrollbars**:
- When content exceeds reasonable minimum window size → add scrollbars
- Apply to both windows and modal dialogs
- Never hide content by cutting it off

**Implementation Pattern**:
```python
# Pattern for scrollable content areas
scrollable_frame = ScrollableFrame(parent)
# Content goes inside scrollable_frame
# Scrollbars appear automatically when content exceeds visible area
```

### Where Scrollbars Are Required

**1. Modal Dialogs** (e.g., 7S Report, Column Config):
- Must display all form fields
- If dialog content > screen height → vertical scrollbar
- If dialog content > screen width → horizontal scrollbar
- User can always access all fields

**2. Entry Forms** (top sections of tabs):
- Dynamic field visibility (e.g., Radio method shows channel fields)
- If all fields visible > available space → scrollbar
- Common case: Should fit without scrolling on 1024x600
- Edge case: Scrollbar ensures accessibility

**3. Tables/TreeViews** (log views):
- Always have scrollbars (standard ttk.Treeview pattern)
- Vertical scrollbar: Always visible or auto-show
- Horizontal scrollbar: Auto-show if columns too wide

**4. Text Areas** (multi-line text entry):
- Always include scrollbar for long content (messages, notes)
- Standard pattern for tk.Text widgets

### Responsive Window Sizing

**Main Window**:
- Default: 1200x700 (comfortable for most use cases)
- Minimum: 800x600 (smallest usable size)
- Below minimum: Content scrollable, not cut off
- Maximizable to full screen

**Modal Dialogs**:
- Auto-size to content (preferred)
- Maximum: 80% of screen width/height
- If content exceeds 80% → scrollbar, not bigger window
- Always centered on parent window

**Design Philosophy**:
- Optimize for target (netbooks ~1024x600)
- Degrade gracefully on smaller screens (scrollbars)
- Improve gracefully on larger screens (more visible content)
- NEVER hide content without scrollbar access

### Implementation Requirements

**For All Views**:
- Test on minimum screen size (800x600 emulation)
- Verify scrollbars appear when needed
- Verify all buttons/fields accessible with scrolling
- Verify tab order works with scrollable areas

**For Modal Dialogs**:
- Wrap content in scrollable frame if > 80% screen height
- Buttons (OK/Cancel) always visible (outside scroll area or sticky footer)
- Test with long field lists (e.g., future complex report templates)

**For Entry Forms**:
- Use LabelFrame containers for logical grouping
- Proper pack/grid with fill/expand
- Test with all dynamic fields visible simultaneously
- Scrollbar in form area if exceeds tab height

### Tkinter Scrollable Patterns

**Pattern 1 - Canvas + Frame for Complex Layouts**:
```python
# For complex forms and modals
canvas = tk.Canvas(parent)
scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
scrollable_frame = ttk.Frame(canvas)

scrollable_frame.bind(
    "<Configure>",
    lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
)

canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
canvas.configure(yscrollcommand=scrollbar.set)
```

**Pattern 2 - Text Widget with Scrollbar** (for text areas):
```python
# Standard pattern already in use
text_widget = tk.Text(parent, height=10, width=50)
scrollbar = ttk.Scrollbar(parent, command=text_widget.yview)
text_widget.configure(yscrollcommand=scrollbar.set)
```

**Pattern 3 - Treeview with Scrollbar** (for tables):
```python
# Standard pattern already in use
tree = ttk.Treeview(parent, columns=columns)
scrollbar = ttk.Scrollbar(parent, orient="vertical", command=tree.yview)
tree.configure(yscrollcommand=scrollbar.set)
```

### Testing Checklist

**Manual Testing Requirements**:
- [ ] Test on 800x600 resolution (minimum)
- [ ] Test on 1024x600 resolution (target netbooks)
- [ ] Test on 1920x1080 resolution (modern desktop)
- [ ] Resize main window to smallest size - verify scrollbars
- [ ] Open all modal dialogs on small screen - verify scrollbars
- [ ] Fill all dynamic fields in forms - verify visibility
- [ ] Verify button accessibility in scrollable dialogs

**Automated Testing** (where feasible):
- Test window minimum size constraints
- Test scrollbar presence with large content
- Test that all widgets are accessible programmatically

### Common Pitfalls to Avoid

❌ **DON'T**:
- Use fixed window sizes without scrollbar fallback
- Cut off content at window edge
- Make dialogs bigger than screen
- Assume users have large screens
- Hide critical buttons inside scroll areas (footer buttons should be sticky)

✅ **DO**:
- Use responsive layouts (pack/grid with expand=True)
- Add scrollbars for content that might exceed screen
- Test on minimum screen size
- Keep action buttons visible (outside scroll or sticky)
- Use reasonable minimum window sizes

## Application Flow

### Startup
1. Create repository (database layer)
2. Create presenters (pass repository)
3. Create views (pass presenters)
4. Create toolbar and status bar
5. Setup status bar logging handler
6. Show main window

### User Action Flow
1. User interacts with View
2. View calls Presenter method
3. Presenter validates input
4. Presenter calls Core/Database
5. Presenter updates View with results

### Event Handling
- Event-driven architecture
- Callbacks for user actions
- Simple event handling (no complex event bus)

### Status Bar Logging Handler

**Pattern**: Custom logging handler that updates status bar in real-time.

**Location**: `src/gui/status_bar_handler.py`

**Architecture**:
- Subclass of `logging.Handler`
- Filters to WARNING+ (default, configurable in config.ini) level only
- Thread-safe: Uses queue and main thread callback
- Updates status bar label with last message

**Integration**:
```
Application Startup:
1. Create logging handlers (file, console, status bar)
2. Status bar handler holds reference to status bar widget
3. Logger emits WARNING/ERROR/CRITICAL → status bar updates
```

**Why Custom Handler**:
- Real-time feedback to operator
- No need to open log files for warnings
- Operational awareness (see issues immediately)
- Standard logging pattern (no special logging calls needed)

## Presenter Organization

### Three Tab Presenters

**Pattern**: One presenter per tab type, each handling its entity type.

**Presenters**:
- `CommunicationPresenter` - Handles Communication tab logic
- `EventPresenter` - Handles Events tab logic
- `PersonnelPresenter` - Handles Personnel tab logic

**Location**: `src/gui/presenters/`

### CommunicationPresenter

**Responsibilities**:
- Load communication systems, methods, channels from configuration
- Populate system/method/channel dropdowns dynamically
- Show/hide capability fields based on selected system
- Validate communication entry before save
- Create/update/delete CommunicationEntry entities
- Load and filter communication log table
- Handle search and column configuration

**Key Methods**:
```python
class CommunicationPresenter:
    def __init__(self, repository: EventLogAdapter, view: CommunicationView):
        ...
    
    def on_system_selected(self, system_name: str) -> None:
        # Load supported methods for selected system
        # Update method dropdown
        
    def on_method_selected(self, method_type: str) -> None:
        # Show/hide channel fields based on method
        # Load capability fields for system+method
        
    def on_save_clicked(self) -> None:
        # Gather form data
        # Validate
        # Create CommunicationEntry
        # Save via repository
        # Refresh table
        
    def on_table_row_selected(self, entry_id: int) -> None:
        # Load entry for editing
        # Populate form fields
        
    def load_communication_log(self, filters: dict | None = None) -> list[dict]:
        # Query repository
        # Format for table display (truncate long text, format dates)
        
    def search(self, search_text: str) -> None:
        # Search via repository
        # Update table view
```

### EventPresenter

**Responsibilities**:
- Manage event entry form and validation
- Handle priority/category dropdowns
- Open structured report modal dialog (generic for all report types)
- Create/update/delete EventEntry and StructuredReport entities
- Load and filter event log table
- Attach structured reports to events

**Key Methods**:
```python
class EventPresenter:
    def __init__(self, repository: EventLogAdapter, view: EventView):
        ...
    
    def on_attach_report_clicked(self, report_type: str | None = None) -> None:
        # If report_type is None: Show "Select Report Type" dialog first
        # Load template configuration for report_type (7S, 9-liner, SALUTE, etc.)
        # Open modal dialog with fields from template config
        # On save: Create StructuredReport linked to current EventEntry
        # Generic pattern - works for any report type without new methods
        
    def on_save_clicked(self) -> None:
        # Gather form data
        # Validate
        # Create EventEntry
        # If structured report attached, create StructuredReport
        # Save via repository
        # Refresh table
        
    def load_event_log(self, filters: dict | None = None) -> list[dict]:
        # Query repository
        # Include structured report auto_summary if present
        # Format for table display
```

### PersonnelPresenter

**Responsibilities**:
- Manage personnel entry form with alarm fields
- Handle active/inactive filtering
- Implement Update Status workflow (create new + mark old inactive)
- Implement Split/Merge wizards
- Track overdue alarms and notify
- Load personnel history for selected individual/group

**Key Methods**:
```python
class PersonnelPresenter:
    def __init__(self, repository: EventLogAdapter, view: PersonnelView):
        ...
    
    def on_update_status_clicked(self) -> None:
        # Get selected entry from table
        # Pre-fill "who" from selected entry
        # On save: Create new entry, mark old inactive, set supersedes field
        
    def on_split_clicked(self) -> None:
        # Open split wizard dialog
        # User enters names for sub-groups
        # Create new entries with supersedes pointing to selected entry
        # Mark old entry inactive
        
    def on_merge_clicked(self) -> None:
        # Check that multiple entries selected
        # Open merge wizard
        # Suggest group name (autocomplete from existing)
        # Create merged entry with supersedes = selected entry IDs
        # Mark old entries inactive
        
    def check_overdue_alarms(self) -> list[PersonnelEntry]:
        # Query repository for alarm_enabled=True, expected_checkin_time < now, alarm_triggered=False
        # Show notification if any overdue
        # Return list for tab badge/indicator
        
    def load_personnel_log(self, active_only: bool = True) -> list[dict]:
        # Query repository (filter by active=True if active_only)
        # Format for table display
        
    def load_history(self, who: str) -> list[dict]:
        # Query repository for all entries matching "who"
        # Walk supersedes chain to show lineage
        # Format for history view
```

### Shared Presenter Utilities

**Architecture Decision**: Composition over inheritance for shared presenter logic.

**Pattern**: `PresenterHelper` utility class provides shared functionality. Presenters use composition, not inheritance.

**Reasoning**:
- Small scale (3-4 specialized presenters, not many generic ones)
- Most logic is entity-specific (can't be abstracted)
- **Flat is better than nested** (Python philosophy)
- Easier to test and understand than inheritance hierarchies
- Flexible - use only what you need

**PresenterHelper** (`src/gui/presenters/presenter_helper.py`):
```python
class PresenterHelper:
    """Shared presenter utilities - static methods for common UI operations"""
    
    @staticmethod
    def show_delete_confirmation(entry_type: str, entry_description: str = "") -> bool:
        """Show confirmation dialog for delete operation"""
        # Returns True if user confirms
        
    @staticmethod
    def handle_validation_error(error: ValidationError, view) -> None:
        """Display validation error to user"""
        # Show error message, highlight problematic fields if possible
        
    @staticmethod
    def format_datetime(dt: datetime) -> str:
        """Format datetime for consistent display and editing"""
        # Returns: "2026-04-21 14:30"
        # Human-readable, compact, sortable, parseable by datetime.fromisoformat()
        
    @staticmethod
    def truncate_text(text: str, max_length: int = 50) -> str:
        """Truncate long text for table display"""
        # Returns "Long text here..." if exceeds max_length
        
    @staticmethod
    def save_column_config(table_name: str, config: dict, repository) -> None:
        """Save column configuration to user preferences"""
        # Stores visible columns, order, widths
        
    @staticmethod
    def load_column_config(table_name: str, repository) -> dict:
        """Load column configuration from user preferences"""
        # Returns config dict or defaults
```

**Usage Pattern**:
```python
class CommunicationPresenter:
    def __init__(self, repository: EventLogAdapter, view: CommunicationView):
        self.repository = repository
        self.view = view
        # No inheritance - just use helper where needed
    
    def on_delete_clicked(self):
        selected_id = self.view.get_selected_entry_id()
        entry = self.repository.get_communication_entry(selected_id)
        
        # Use helper for confirmation dialog
        if PresenterHelper.show_delete_confirmation("Communication", entry.message_content[:30]):
            self.repository.delete_communication_entry(selected_id)
            self.load_communication_log()
    
    def on_save_clicked(self):
        try:
            # Entity-specific logic here
            data = self.view.get_form_data()
            entry = CommunicationEntry(...)  # Create entry
            CommunicationEntryValidator.validate_all(entry, config)
            self.repository.create_communication_entry(entry)
            self.view.clear_form()
            self.load_communication_log()
        except ValidationError as e:
            # Use helper for error display
            PresenterHelper.handle_validation_error(e, self.view)
    
    def load_communication_log(self, filters: dict | None = None):
        entries = self.repository.get_all_communication_entries(filters)
        
        # Use helper for consistent formatting
        formatted_rows = []
        for entry in entries:
            formatted_rows.append({
                'id': entry.id,
                'time': PresenterHelper.format_datetime(entry.event_time),
                'message': PresenterHelper.truncate_text(entry.message_content, 50),
                # ... etc.
            })
        
        self.view.update_table(formatted_rows)
```

### Common Presenter Patterns

**Pattern**: All presenters implement similar methods, but with entity-specific logic.

**Common Methods** (each presenter implements for its entity type):
- `on_save_clicked()` - Validate and save entry (entity-specific)
- `on_clear_clicked()` - Reset form to defaults (call view.clear_form())
- `on_table_row_selected()` - Load entry for editing (entity-specific)
- `on_delete_clicked()` - Delete selected entry (uses PresenterHelper.show_delete_confirmation)
- `load_log()` - Query and format entries for table display (entity-specific)
- `search()` - Search entries, update table (entity-specific)
- `apply_filters()` - Filter table based on user criteria (entity-specific)
- `configure_columns()` - Show/hide, reorder columns (uses PresenterHelper for persistence)

**Why No Base Class**:
- Entity-specific logic dominates (90%+ of code)
- Only 5-10 lines of truly generic code per method
- Base class would require extensive overriding (defeating purpose)
- **Clarity over DRY**: Better to see the full flow in each presenter than hunt through inheritance

**Data Flow**:
1. View captures user input → calls Presenter method
2. Presenter validates input (basic UI validation: non-empty, format)
3. Presenter creates domain entity, calls Core validators
4. If validation passes: Presenter calls Repository to save
5. Presenter refreshes View with updated data or error messages

**Error Handling**:
- Catch `ValidationError` from Core validators
- Use `PresenterHelper.handle_validation_error()` for consistent display
- View highlights problematic fields
- Log technical errors for debugging

## Window Layout

### Main Window Structure

**Pattern**: Single window with toolbar, tabbed content area, and status bar.

**Layout**:
```
┌─────────────────────────────────────────────────────────┐
│ EventLog - Pluton Event Logger                          │
├─────────────────────────────────────────────────────────┤
│ Toolbar: [🗑️ Nollställ]  [Other buttons...]            │ <- Always visible
├─────────────────────────────────────────────────────────┤
│ [Kommunikation] [Händelser] [Personal]                  │ <- ttk.Notebook tabs
├─────────────────────────────────────────���───────────────┤
│                                                          │
│  Tab Content Area (changes per tab):                    │
│  ┌────────────────────────────────────────────────────┐ │
│  │ Entry Form (top section)                           │ │
│  ├────────────────────────────────────────────────────┤ │
│  │ Log Table (bottom section, TreeView)               │ │
│  └────────────────────────────────────────────────────┘ │
│                                                          │
├─────────────────────────────────────────────────────────┤
│ Status Bar: Last log: Application started | Operator: GC│ <- Always visible
└─────────────────────────────────────────────────────────┘
```

**Components**:
- **Main Window**: Root Tk window
- **Toolbar**: Frame at top with always-visible action buttons
- **Notebook**: ttk.Notebook widget with three tabs
- **Tab Content**: Each tab contains entry form + log table
- **Status Bar**: Frame at bottom showing log messages and status info
- **Memory Between Tabs**: Form state preserved when switching tabs

### Toolbar (Always Visible)

**Location**: Top of window, below title bar

**Purpose**: Critical actions that should always be accessible

**Pattern**: Frame with buttons, visually distinct styling for dangerous operations

**Buttons**:
- **🗑️ Nollställ** (Red/orange background, warning icon)
  - Swedish term matching current military equipment terminology
  - Always visible for instant emergency data clearing
  - **NO CONFIRMATION DIALOG** - Executes immediately when clicked
  - High contrast, clearly destructive appearance to prevent accidental clicks
  - Critical: Used when about to be overrun - must be instant
  - See logging_architecture.md for clear data workflow
  
- **Future buttons** (Phase 2+):
  - Export/backup
  - Settings/preferences
  - Help/documentation

**Design Notes**:
- Destructive button (Nollställ) has warning color and icon
- Sufficient spacing to prevent accidental clicks
- Tooltip on hover explains what each button does
- Buttons remain enabled/disabled based on app state

### Status Bar (Always Visible)

**Location**: Bottom of window

**Purpose**: Show real-time status information and last log message

**Pattern**: Frame divided into sections (left-to-right)

**Sections**:
1. **Last Log Message** (left, takes most space):
   - Shows log messages at configured level (default: WARNING+)
   - Format: "Last log: [message]"
   - Updates in real-time as logs are written
   - Configurable in config.ini (status_bar_log_level setting)
   - Default: Shows WARNING, ERROR, CRITICAL (not DEBUG/INFO)
   - Helps operator see issues without opening log files
   
2. **Current Operator** (right):
   - Shows currently logged-in operator
   - Format: "Operator: [name]"
   - Updates when operator changes
   
3. **Database Status** (right, optional Phase 2):
   - Shows database connection status
   - Format: "DB: Connected" or "DB: Error"

**Implementation Notes**:
- Status bar uses custom logging handler to capture WARNING+ messages
- Handler updates status bar label in main thread (thread-safe)
- Status bar sections separated by visual dividers (|)
- Log messages truncated if too long (with "..." tooltip shows full message)

### Tab Organization

**Communication Tab** (`CommunicationView`):
- Entry form: System selection, method, channel, message content, from/to, etc.
- Log table: Columns for time, system, method, from, to, message (truncated), operator
- Buttons: Save, Clear, Edit Selected

**Events Tab** (`EventView`):
- Entry form: Description, whom, priority, category, attach report button
- Log table: Columns for time, priority, category, whom, description (truncated), operator
- Buttons: Save, Clear, Edit Selected, Attach Report (dropdown/menu for report type selection)

**Personnel Tab** (`PersonnelView`):
- Entry form: Who, status, location, mission notes, alarm settings
- Log table: Columns for who, status, location, last contact, alarm indicator
- Filter: Active only (default) / Show all history
- Buttons: Save, Update Status, Split, Merge

### Common UI Patterns

**Entry Form Pattern** (top section of each tab):
- Input fields arranged in logical groups
- Smart defaults auto-populated (operator, time, etc.)
- Real-time validation feedback
- Character count for text areas
- Save/Clear buttons

**Log Table Pattern** (bottom section of each tab):
- ttk.Treeview widget with columns
- Sortable columns (click header)
- Row selection for editing
- Context menu (right-click): Edit, Delete, View Details
- Search/filter controls above table
- Configurable columns (show/hide, reorder)

**Modal Dialogs**:
- Structured Report Dialog (template-driven - renders fields based on report_type config)
- Edit Entry Dialog (full form with all fields)
- Column Configuration Dialog (checkboxes + drag-to-reorder)
- Split/Merge Wizards (multi-step dialogs)

**See**: `ai_instructions/design/gui_design.md` for detailed field layouts and workflows.

## Testing

### View Testing
- Minimal (Tkinter widgets are framework code)
- Test that views can be instantiated
- Test that callbacks are registered correctly
- Test that views can render without errors
- No deep widget testing (trust Tkinter)

### Presenter Testing

**Strategy**: Unit test all presenter logic with mock views.

**Test Organization**:
- `tests/unit/gui/presenters/test_communication_presenter.py`
- `tests/unit/gui/presenters/test_event_presenter.py`
- `tests/unit/gui/presenters/test_personnel_presenter.py`
- `tests/unit/gui/presenters/test_presenter_helper.py` - Test shared utilities

**Test Scenarios** (per presenter):

**CommunicationPresenter**:
- System selection updates method dropdown correctly
- Method selection shows/hides channel fields
- Capability fields populated based on system+method config
- Save creates CommunicationEntry with correct fields
- Validation errors displayed to view
- Table loads and formats entries correctly
- Search filters entries correctly

**EventPresenter**:
- Structured report dialog opens with correct template fields for report type
- Report type selection (if multiple types available)
- Save creates StructuredReport with correct report_type
- Priority/category dropdowns populated from config
- Save creates EventEntry with optional fields
- Structured report auto_summary displayed in table
- Filtering by priority/category works
- Generic report attachment works for any report type

**PersonnelPresenter**:
- Update Status creates new entry, marks old inactive, sets supersedes
- Split wizard creates multiple entries with correct supersedes
- Merge wizard combines entries with correct supersedes
- Alarm checking returns overdue entries
- Active-only filter works correctly
- History view shows supersedes chain

**Common Testing Patterns**:
- Mock view interface (simple class with method stubs)
- Use real Core validators and in-memory database
- Test validation error handling
- Test form-to-entity mapping
- Test entity-to-table formatting

**PresenterHelper Testing**:
- Unit test all static methods independently
- Test datetime formatting (None handling, timezone-naive, consistent output)
- Test text truncation edge cases (empty, None, very long)
- Test delete confirmation UI (mock messagebox)
- Test column config persistence (mock repository)

**Example Test**:
```python
def test_communication_presenter_save_creates_entry(in_memory_repository):
    mock_view = MockCommunicationView()
    presenter = CommunicationPresenter(in_memory_repository, mock_view)
    
    # Simulate user filling form
    mock_view.set_form_data({
        'message_content': 'Test message',
        'from_field': 'GC',
        'to_field': 'Pluton 2',
        'communication_system': 'RA180',
        'method_type': 'Radio',
        # ... etc.
    })
    
    # User clicks Save
    presenter.on_save_clicked()
    
    # Check entry created in repository
    entries = in_memory_repository.get_all_communication_entries()
    assert len(entries) == 1
    assert entries[0].message_content == 'Test message'
    
    # Check view updated
    assert mock_view.form_cleared
    assert mock_view.table_refreshed
```

### Integration Testing
- End-to-end flows with real views
- Real presenters + core + in-memory DB
- User scenarios (e.g., "create communication entry, edit it, delete it")
- May be flaky due to Tkinter threading
- Mark with `@pytest.mark.integration`
- Use `@pytest.mark.flaky(reruns=3)` if needed

### Manual Testing Checklist

**Functionality**:
- Tab switching preserves form state
- Column configuration persists across app restarts
- Alarms trigger notifications correctly
- Search and filtering work across all tabs
- Long text truncates correctly in tables
- Modal dialogs don't block main window incorrectly
- **Toolbar**: Nollställ button executes instantly (no confirmation), clears all data
- **Status Bar**: Shows WARNING+ log messages in real-time
- **Status Bar**: Shows current operator correctly
- **Status Bar**: Log messages truncate with tooltip for full text

**Responsive Design & Scrollbars** (Critical):
- [ ] Test on 800x600 resolution - all content accessible with scrollbars
- [ ] Test on 1024x600 resolution (target netbooks) - optimal layout
- [ ] Test on 1920x1080 resolution - efficient use of space
- [ ] Resize main window to minimum size - verify scrollbars appear
- [ ] Resize main window very small - verify content not cut off
- [ ] Open all modal dialogs on small screen - verify all fields visible with scrolling
- [ ] Fill all dynamic form fields - verify scrollbar appears if needed
- [ ] Verify action buttons (Save, Cancel) always accessible in scrollable dialogs
- [ ] Test 7S report modal on small screen - all fields accessible
- [ ] Test column configuration dialog on small screen - all options visible
- [ ] Verify horizontal scrollbars on tables when many columns visible
- [ ] Verify vertical scrollbars on tables with many entries

## Dependencies
- `tkinter` (stdlib) - Main GUI framework
- `tkinter.ttk` (stdlib) - Themed widgets (Notebook, Treeview, etc.)
- `logging` (stdlib) - For status bar logging handler
- Core layer (domain models: CommunicationEntry, EventEntry, PersonnelEntry, StructuredReport)
- Core layer (validators: CommunicationEntryValidator, etc.)
- Database layer (EventLogAdapter via Repository pattern)
- GUI layer (`PresenterHelper` - shared presenter utilities via composition)
- Logging layer (`StatusBarHandler` - custom logging handler for status bar)

## Widgets Used

**Primary Widgets**:
- `ttk.Notebook` - Tabbed interface
- `ttk.Treeview` - Log tables with sortable columns
- `ttk.Combobox` - Dropdowns (system, method, priority, category)
- `tk.Text` - Multi-line text entry (message content, notes)
- `ttk.Entry` - Single-line text entry (from, to, who, location)
- `ttk.Checkbutton` - Boolean fields (confirmed, encryption, alarm_enabled)
- `ttk.Button` - Actions (Save, Clear, Edit, Delete, etc.)

**Layout Widgets**:
- `ttk.Frame` - Container for grouping widgets
- `ttk.LabelFrame` - Titled container for logically grouped fields
- `ttk.PanedWindow` - Resizable split between form and table (if needed)
- `tk.Canvas` - For scrollable content areas (with scrollbar pattern)
- `ttk.Scrollbar` - Vertical/horizontal scrollbars for tables, text, and scrollable frames

**Dialogs**:
- `tk.Toplevel` - Modal dialogs (7S report, column config, split/merge wizards)
- `tkinter.messagebox` - Confirmations and error messages
- `tkinter.filedialog` - File attachment picker (Phase 2+)

## Potential Third-Party Libraries (Phase 2+)

**Evaluate against dependency philosophy** before adding:

- `tkcalendar` - Better date/time pickers (current plan: use ttk.Entry with validation)
- `tktable` - Enhanced table widget (current plan: ttk.Treeview sufficient)
- None needed for Phase 1 - stdlib Tkinter is sufficient

---

**Related**:
- Human version: `docs/architecture/root_architecture.md`
- Core architecture: `ai_instructions/architecture/core_architecture.md`
- GUI design: `ai_instructions/design/gui_design.md`





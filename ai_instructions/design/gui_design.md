# GUI Design (AI)

**User Interface Layout & Interactions**  
**Last Updated**: 2026-04-18 (Session 004 - Communication and Event Entry design complete)

## Technology: Tkinter

Standard library, cross-platform, sufficient for offline desktop app.

## Language

**Primary Language**: Swedish  
**Future**: English (and potentially other languages)  
**Current Focus**: Swedish UI text and nomenclature

**Impact**: All UI labels, buttons, messages, and documentation strings should be in Swedish.

## User Preferences Storage

**Decision**: Split preferences between config file and database based on when they're needed.

### Configuration File (Bootstrap Settings)
Saved in config file (e.g., `config.ini` or similar) - loaded before database connection:

1. **Window Position** - Last X, Y coordinates
2. **Window Size** - Last width, height
3. **Window State** - Windowed, Maximized, or Fullscreen
4. **Database Path** - Location of the SQLite database file

**Reasoning**: These settings must be available immediately at application startup, before database connection is established.

### Database Storage (User Preferences)
Saved in database `user_preferences` table - loaded after database connection established:

1. **Column Configuration per Tab** - Show/hide, order, widths for each tab's table
2. **Filter Defaults per Tab** - Last used filter values (optional)
3. **Other UI State** - Any other preferences that don't need to be available at bootstrap
4. **Language Preference** - If we add multi-language support in the future
5. **Last operator** - Who is currently operating the terminal (for logging purposes).

**Reasoning**: 
- Database will exist from Phase 1 anyway
- More structured than config file for complex data (column configurations, etc.)
- Easier to extend and query
- Config file stays minimal and focused on bootstrap

**Implementation**: Create `user_preferences` table with key-value or structured storage for these settings.

## Main Window Layout

### Structure: ttk.Notebook (Tabbed Interface)

**Design Decision**: Use `ttk.Notebook` widget with tabs for different views.

**Key Requirement**: Maintain state/memory when switching between tabs (tab content persists).

### Proposed Tabs (Organized by Information Type)

1. **"Communication"** - Radio messages, phone calls, written orders
2. **"Events"** - Operational events, incidents, status changes
3. **"Personnel"** - Personnel movements, status, tracking

**Future Tabs (Noted for Future Development)**:
- **"Maps"** - Tactical map view
- **"Orientations"** - Current and historic situation orientations

### Architecture Decision: Specialized Entities

**Decision**: Each tab type has its own specialized entity, table, and fields.

- **Communication Tab** → `CommunicationEntry` entity → `communication_entries` table
- **Events Tab** → `EventEntry` entity → `event_entries` table  
- **Personnel Tab** → `PersonnelEntry` entity → `personnel_entries` table

**Reasoning**: 
- Different information types have different required fields
- Cleaner domain model (no unused fields)
- Better data integrity and validation
- Each tab can have optimized UI for its specific purpose

**Impact**: This affects `core_design.md` (entities) and `db_design.md` (tables).

### Per-Tab Layout Pattern

Each tab contains both:
- **Entry form** (top or side) - For creating new entries of that type
- **Log view** (main area) - Table showing entries of that type with search/filter

This allows operators to see recent entries while logging new ones.

### Tab State Persistence Strategy

- Each tab is a separate frame that stays in memory
- Switching tabs does not destroy the previous tab's widgets
- Form data, table scroll position, and filter settings persist across tab switches
- ttk.Notebook handles this naturally - tabs are not destroyed on switch

### Tab Visual Notifications

**Design Decision**: Notebook tab headers can show visual alerts for important conditions.

**Personnel Tab - Overdue Check-in Alert**:
- **Condition**: One or more active personnel entries have overdue check-in alarms
- **Visual indicator**: 
  - Change tab text color to red: "Personnel" → red text
  - OR add icon/badge: "Personnel ⚠️" or "Personnel (2)" showing count
  - OR change tab background color (if supported by ttk.Notebook styling)
- **Purpose**: Alert operator of overdue check-ins even when working in Communication or Events tab
- **Clear condition**: When all overdue alarms are acknowledged or resolved

**Implementation Note**: 
- Background process/timer checks for overdue alarms periodically
- Updates tab appearance when conditions change
- Cross-tab notification ensures critical alerts aren't missed

**Future Enhancement**:
- Could apply to other tabs if needed (e.g., unconfirmed critical communications)
- Configurable alert thresholds

## Communication Entry Design

### Key Requirements (Use Cases)

The Communication Tab must support three critical workflows:

1. **Quickly add new entries** - Fast data entry is essential for operational tempo
2. **Overview of existing entries** - See recent communications at a glance
3. **View full details** - Open entries to see complete message content (messages can be long)

### Edit Functionality

**Decision**: Entries ARE editable after saving.

**Reasoning**: Users need to correct errors in operational logs.

**Implementation**:
- Add "Edit" action for existing entries
- When entry is modified after initial save, set `edited` flag to `true`
- Display "Edited" indicator in log view (e.g., small icon or text)
- Optional (future): Track edit history (who, when, what changed)

**CommunicationEntry Additional Field**:
- `edited`: Boolean (default: false)

### Communication Tab Layout Strategy

**Decision**: Top/bottom split layout.

**Top Section - Entry Form** (compact, ~30-40% of height):
- For quick data entry
- Remains visible while viewing log
- Clear/Save buttons easily accessible

**Bottom Section - Log View** (main area, ~60-70% of height):
- **Scrollable** table/grid showing entries
- **Sort order**: Latest entry at TOP (reverse chronological)
- Double-click entry → Opens full detail view dialog
- Right-click or button → Edit entry (loads into form or opens edit dialog)

**Keyboard Shortcuts**:
- Will be implemented for relevant actions (Save, Clear, etc.)
- Specific shortcuts to be decided during implementation (doesn't affect architecture)

**Reasoning**: Top/bottom split allows operators to see recent logs while entering new data, supporting fast operational tempo.

### Log View Filtering

**Requirement**: Users need to filter log entries to find specific communications quickly.

**Filter Logic - Simple (Default)**:
- Multiple filters use AND logic (all conditions must match)
- Easy for non-technical users to understand
- Example: "Radio" AND "Company Net" AND "2026-04-18" = Only radio messages on Company Net from that date

**Filter Options** (Phase 1):
1. **Date/Time Range** - From date/time to date/time
2. **Method Type** - Radio, Phone, In Person, Ordnance, Other
3. **Radio Net** - Specific channel designation (only when Method = Radio or other methods that have gotten a channel designation field)
4. **From** - Sender (free text or dropdown)
5. **To** - Recipient (free text or dropdown)

**Advanced Filtering** (Phase 2 - Future):
- Button: "Advanced Filter..." → Opens dialog with OR/NOT logic
- For power users who need complex queries
- Example: "(Radio OR Phone) AND NOT (From = 'HQ')"

**Filter UI Placement**:
- Above the log view table (below entry form)
- Compact filter bar with dropdowns/text fields
- "Clear Filters" button to reset all
- Active filters clearly visible

**Current Focus**: Implement simple AND filtering in Phase 1.

### Log View Table Columns

**Widget**: `ttk.Treeview` - Standard tkinter table widget with column support.

**Decision**: Display all important information, truncate message content if too long.

**Sorting Functionality**:
- **Column headers are clickable** to sort by that column
- **Default sort**: Date/Time, latest at top (descending)
- Click header once: Sort ascending
- Click header again: Sort descending (toggle)
- Visual indicator in header showing current sort column and direction (▲/▼)

**Columns** (left to right):
1. **Tid** (Time) - Event time (HH:MM or full datetime depending on space)
2. **Från** (From) - Sender/source
3. **Till** (To) - Recipient/destination
4. **Metod** (Method) - Method type, and if Radio: show channel designation
   - Example: "Radio - Kompl1"
   - Example: "Telefon"
5. **Meddelande** (Message) - Message content, **truncated if too long**
   - Example: "Pluton 2 rapporterar färdig..." (truncated with ellipsis)
6. **Bekr** (Confirmed) - ✓ or empty (checkbox or icon)
7. **Redigerad** (Edited) - Small indicator if edited (icon or "R")
8. **Operatör** (Operator) - Who logged it (may be hidden on very small screens)

**Message Truncation**:
- Truncate at word boundary
- Show ellipsis (...) when truncated
- Full message visible on double-click (detail dialog)

**Screen Size Handling** (Low-resolution netbooks):
- Target minimum: ~1024x600 or similar small netbook screens
- Columns resizable by user
- Horizontal scrollbar if needed
- Less critical columns (Operator) can be hidden/collapsed on very small screens
- Table should use all available space efficiently

**Column Width Strategy**:
- Fixed narrow: Confirmed (30-40px), Edited (30-40px)
- Fixed medium: Time (80-100px), Method (100-120px)
- Fixed medium: From (80-100px), To (80-100px)
- Flexible: Message (takes remaining space, minimum 150px)
- Optional: Operator (80px, can be hidden)

**Column Configuration** (User Customization):
- Button: "Kolumner..." (Columns...)  above or near the table
- Opens modal dialog with:
  - **Checkboxes**: Show/hide each column (except Time and Message which are always visible)
  - **Reorder controls**: Up/Down buttons or drag-and-drop to change column order
  - Preview of current column order
  - Buttons: "Spara" (Save), "Återställ standard" (Reset to default), "Avbryt" (Cancel)
- Configuration persists across sessions (saved in user preferences/config file)

**Reasoning**: 
- Users with small screens can hide less important columns
- Users can prioritize what's most important to them
- Different operational contexts may need different column visibility

### CommunicationEntry Fields

#### Core Fields
1. **Message Content** - The actual message text (multi-line text)
2. **From** - Sender/source
3. **To** - Recipient/destination
4. **Event Time** - When the communication occurred
5. **Logged Time** - When entered into system (auto-populated)
6. **Operator** - Who logged it (person at the terminal)
7. **Confirmed** - Was receipt acknowledged? (boolean/checkbox)

#### Communication Selection (Recursive Under the Hood)
This is the complex part - communication selection is driven by a recursive configuration tree beneath a top-level communication system/way.

### Communication System + Recursive Path Selection

**Design Philosophy - Recursive Underlying Model, Bounded Visible UI**:
- **Primary selection**: choose the top-level communication system/way (`RA180`, `Motorola`, `Rakel`, `Courier`, etc.)
- **Child selections**: choose the configured path beneath that system
- **Top-level qualifiers**: choose or accept qualifiers such as `encrypted` and possibly `data`
- The current GUI may still render only the first **three visible levels** for practical use, but the underlying structure is recursive and should not require redesign if a fourth visible level is ever needed later.

**Configuration Requirements**:
1. **Communication Systems/Ways**: configurable top-level list (`RA180`, `Motorola`, `Rakel`, `Courier`, etc.)
2. **Recursive Child Options**: each system can have zero or more child options; each option can in turn have zero or more child options
3. **Child Labels**: each system/option can define what the next visible selection level should be called
4. **Top-Level Qualifiers**: systems define whether qualifiers like `encrypted` or `data` are editable, forced, or hidden
5. **Practical UI Limit**: current operator workflow should stay bounded and simple even if the underlying configuration tree could go deeper later

**Example Scenario**:
- Today: `RA180` → `Company Net`
- Tomorrow: `RA180` → `Company Net` moves to a different channel/value underneath the same system tree
- Later: a deeper child option may be added under one channel/path without redesigning the overall GUI architecture

### Data Model for Communication (GUI-Relevant View)

**Configured Structure**:
- **Communication Systems Table**: top-level systems/ways
- **Communication Options Table**: recursive child options beneath a system
- **Communication Qualifiers Config Table**: defines top-level qualifier controls and behavior per system

**CommunicationEntry Storage Snapshot**:
- `communication_system`: `"RA180"`
- `communication_path`: `[ {"value": "5", "label": "Company Net"} ]`
- `communication_qualifiers`: `{"encrypted": true, "data": true}`

**Why store the selected path snapshot?** Historical accuracy - if labels or child structures change later, old logs still show what the operator actually chose at that time.

### UI Design for Communication Entry Form

**Decision**: Use dropdown selection (not free-text) for configured system/path choices to prevent spelling variations and maintain data consistency.

**UI Flow** (recursive underneath, bounded in presentation):
1. User selects **Communication System** from dropdown
   - Options: `RA180`, `Motorola`, `Rakel`, `Courier`, etc.
   - Special entry: `+ Lägg till ...` remains a future focused flow, not a full admin UI
2. GUI checks whether the selected system has active root child options
3. If yes, show the next configured dropdown using the system's `child_label`
4. When the user picks a child option, GUI checks whether that option has children
5. If yes, show the next dropdown using that option's `child_label`
6. Stop when:
   - no more child options exist, or
   - the current practical visible-depth limit is reached
7. Show top-level qualifier controls for the selected system
   - editable qualifier → normal control
   - forced qualifier → prefilled and non-editable or hidden depending on UX choice
   - hidden qualifier → not shown but still available to runtime/storage behavior if needed

**Current Phase 1 examples**:
- **RA180** → likely one visible child dropdown for channel selection + top-level `encrypted` and likely `data`
- **Motorola** → one visible child dropdown for channel selection + forced clear/no-encryption behavior
- **Rakel** → one visible child dropdown for channel selection + forced encrypted behavior
- **Courier** → no child dropdowns in Phase 1

**Quick Add Flow**:
- A focused quick-add dialog may later add a new child option at the currently relevant level in the tree
- This is not a full tree editor in Phase 1; it is a practical operational fast-add seam

### Dynamic Field Behavior

**Decision**: Show/hide recursive selection controls and qualifier controls based on configuration.

**Reasoning**: Cleaner UI - users should only see the currently relevant next step and the relevant qualifiers, not a large static block of irrelevant disabled fields.

**What Shows/Hides** (configuration-driven):
- When `communication_system` changes, GUI loads that system's root children and qualifier behavior
- When a child option changes, GUI loads that option's children for the next visible level
- If no children exist, no further selection dropdown is shown
- Qualifier controls show/hide or become read-only according to per-system configuration

**Future-proofing**:
- If later systems need deeper structures, the GUI logic should already be based on recursive traversal and a configurable maximum visible depth rather than a hardcoded `if tier_2` / `if tier_3` chain.

### Implementation Phases for Communication Configuration UI

**Phase 1 (Proof of Concept)**:
- Seed systems, recursive child options, and top-level qualifier definitions in the database
- GUI renders the first few visible levels from that configuration
- No full management UI yet - only selection and later small quick-add seams

**Phase 2+ (Future)**:
- Focused editing flows may allow broader operator/admin changes to the tree
- Visible UI depth can remain practically limited even if the underlying structure grows

**Phase 3 (Future - Full Customization)**:
- Add Settings/Admin tab with management UI:
  - Add/Edit/Delete method systems
  - Add/Edit/Delete channel designations
  - Create/Edit metadata configuration templates
  - Mark designations as inactive (for historical data integrity)
- Keep the quick-add dialog in the main form for on-the-fly channel additions

**Current Focus**: Design and implement Phase 1 - basic functionality with hardcoded test data specific to your unit.

## Event Entry Design

### Similarity to Communication Tab

**Key Insight**: Event Entry shares most of the same structure as Communication Entry, with different field names.

**Shared Characteristics**:
- Top/bottom split layout
- Entry form at top, log view at bottom
- Treeview table with sortable columns
- Edit functionality with `edited` flag
- Filter capability (simple AND logic)
- Column configuration
- Document attachments

### EventEntry Fields

#### Core Fields
1. **Event Description** - Operator's short memory note/summary (multi-line text)
   - Examples: "Fientlig patrull observerad", "Kontakt sektor Bravo"
   - Operator's quick note for context
   - If structured report attached, auto-populated summary can be inserted
2. **Whom** - Who is involved or affected (free text)
   - Examples: "Pluton 2", "Grupp 3", "Kompani", specific callsign
   - Free text allows flexibility for different unit designations
3. **Event Time** - When the event occurred
4. **Logged Time** - When entered into system (auto-populated)
5. **Operator** - Who logged it (person at the terminal)
6. **Priority** - Event priority/severity (dropdown: Low, Normal, High, Critical)
7. **Category** - Event type/category (dropdown from user-manageable list)
   - Examples: "Kontakt", "Förflyttning", "Underhåll", "Rapport", "Observation"
8. **Attachments** - File attachments AND structured reports (see Structured Reports below)
9. **edited** - Boolean flag (default: false)

### Structured Reports (7S, 9-liner, etc.)

**Design Decision**: Structured military reports are separate entities attached to EventEntry.

**Why Separate**:
- Avoids field duplication (7S has time/location, EventEntry already has event_time)
- Extensible to future report formats without changing EventEntry
- Keeps EventEntry simple and clean
- Multiple report types can coexist

**Workflow**:
1. Operator creates/selects EventEntry (fills basic fields: time, whom, priority, category, short description)
2. Operator clicks **"Lägg till rapport..."** (Add Report) button in entry form
3. Modal dialog opens: "Välj rapporttyp" (Choose report type)
   - Dropdown: "7S", "9-liner" (future), "SALUTE" (future), etc.
4. User selects "7S" → Opens 7S report form modal
5. User fills 7S fields (stund, ställe, styrka, slag, sysselsättning, symbol, sågesman)
6. User saves report → Attached to EventEntry
7. **Auto-summary generated** from 7S fields → Can be inserted into event_description or shown separately

**7S Report Fields** (in modal):
- **s1_stund** (datetime) - När (When) - Defaults to event_time from parent event
- **s2_stalle** (text) - Var (Where) - Grid, place name
- **s3_styrka** (text) - Hur många (Strength) - "ca 20 personer", "5 fordon"
- **s4_slag** (text) - Typ (Type) - "Soldater", "Stridsvagnar", with autocomplete
- **s5_sysselsattning** (text) - Aktivitet (Activity) - "Förflyttning", with autocomplete
- **s6_symbol** (text) - Kännetecken (Markings) - "Gröna uniformer"
- **s7_sågesman** (text) - Observatör (Observer) - "Grupp 2"

**Auto-Summary Generation**:
- Template configuration defines summary format
- Example: "14:30, Grid 12345678, 20 pers, Soldater, Förfl. öst"
- Shown in event log table in "Händelse" column when report attached
- **Option A** (user chose this): Auto-generate and show in table
  - event_description = operator's note
  - Table shows: event_description + " | " + report auto_summary
  - Or just auto_summary if event_description empty

**Editing Reports**:
- Double-click event → Detail view shows event + attached reports
- Can edit reports separately from event
- Report has own `edited` flag

**Multiple Reports**:
9. **edited** - Boolean flag (default: false)

### Structured Reports (7S and Future Templates)

**Design Decision**: Structured reports are separate attachments to EventEntry, not inline fields.

**Why Separate**:
- Avoids field duplication (7S has time/location, EventEntry already has event_time)
- Extensible to future report formats without changing EventEntry schema
- Keeps EventEntry simple and clean  
- Multiple report types can coexist
- Structured data queryable separately

**Workflow**:
1. Operator fills basic EventEntry form:
   - Event Time, Whom, Priority, Category
   - **Event Description**: Short operator note (e.g., "Fientlig patrull observerad")
2. Operator clicks **"Lägg till rapport..."** (Add Report) button in entry form
3. Modal opens: Select report type dropdown ("7S", future: "9-liner", "SALUTE")
4. User selects "7S" → 7S report form modal opens
5. User fills 7S fields (see below)
6. User saves → Report attached to EventEntry
7. **Auto-summary generated** from 7S fields → Combined with event_description for table display

**7S Report Modal Form**:
- **Title**: "7S Rapport" (7S Report)
- **Fields** (all optional, fill what's known):
  1. **Stund (När)** - When observation occurred (datetime, defaults to event_time from parent)
  2. **Ställe (Var)** - Where (text with autocomplete) - Grid, place name
     - Examples: "Grid 12345678", "Punkt Alpha", "Väg 23 vid bro"
  3. **Styrka (Hur många)** - Strength (text) - Quantity observed
     - Examples: "ca 20 personer", "5 fordon", "1 pluton"
  4. **Slag (Typ)** - Type observed (text with autocomplete from existing values)
     - Examples: "Soldater", "Stridsvagnar", "Civila", "Kor"
  5. **Sysselsättning (Aktivitet)** - Activity (text with autocomplete)
     - Examples: "Förflyttning österut", "Gräver skyttevärn", "Rastvila"
  6. **Symbol (Kännetecken)** - Markings/identification (text)
     - Examples: "Gröna uniformer", "FN-märkning", "Röd stjärna"
  7. **Sagesman (Observatör)** - Observer (text)
     - Examples: "Grupp 2 förpost", "Sgt. Andersson"
     - **Note**: Different from Operator (who logs it in system)
- **Buttons**: "Spara" (Save), "Avbryt" (Cancel)

**Auto-Summary Generation**:
- When 7S report saved, auto-generate summary text
- Format example: "14:30, Grid 12345678, 20 pers, Soldater, Förfl. öst"
- Template configuration defines which fields to include and order
- **Table Display**: Shows `event_description + " | " + report.auto_summary`
  - Example in table: "Fientlig patrull | 14:30, Grid 12345678, 20 pers, Soldater, Förfl. öst"
  - If no report attached: Just shows event_description
  - Truncated with ellipsis if too long

**Entry Form "Add Report" Button**:
- Located in entry form, near attachments area
- Can attach multiple reports to one event
- List of attached reports shown below button
- Edit/Remove buttons for each attached report

**Detail View** (double-click event):
- Shows EventEntry basic fields
- Shows attached file attachments
- Shows attached structured reports with all fields (not just summary)
- Can edit reports separately

**Benefits**:
- EventEntry stays simple (no 7S fields when not needed)
- No field duplication (7S stund separate from event_time)
- Extensible to other report formats
- Structured data stored properly for queries
- Table view gets auto-generated summary

**Phase 1**: 7S report only
**Phase 2+**: Add 9-liner, SALUTE, custom templates

### Differences from Communication

**Communication has**: From, To, Method (with radio net hierarchy), Confirmed  
**Events has**: Whom, Priority, Category, structured reports (7S, etc.)  

**Reasoning**: Events are about what happened and who was involved, not directional communication between parties.

### 7S Report UI Design

**Dynamic Form Behavior** (similar to Radio in Communication tab):

**UI Flow**:
0. User press button to attach report -> modal opens.
1. User selects Category = "7S" from dropdown
2. **7S structured fields appear** below Category field:
   - **Ställe** (Where) - Text field
   - **Styrka** (Strength) - Text field (free text or numeric)
   - **Slag** (Type) - Text field with autocomplete (Soldater, Stridsvagnar, Civila, etc.)
   - **Sysselsättning** (Activity) - Text field with autocomplete (Förflyttning, Gräver, Rastvila, etc.)
   - **Symbol** (Markings) - Text field
   - **Sagesman** (Observer) - Text field
   - **Note**: Stund (When) uses the Event Time field (already present)
3. All 7S fields are **optional** - operator fills what's known
4. If user changes Category to "Kontakt" or other → 7S fields hide

**Autocomplete for 7S Fields**:
- **Slag** (Type): Suggests from existing values (Soldater, Stridsvagnar, Civila, Fordon, etc.)
- **Sysselsättning** (Activity): Suggests from existing values (Förflyttning, Gräver, Patrullering, etc.)
- **Other fields**: No autocomplete (location, markings, observer are unique per report)

**7S vs Event Description Field**:
- **Event Description** remains available for additional context
- 7S fields provide structured data
- Example:
  - Event Description: "Observation från förpost nord"
  - 7S Ställe: "Grid 12345678"
  - 7S Styrka: "5 fordon"
**Phase 1**: 7S report only
**Phase 2+**: Add 9-liner, SALUTE, custom templates

### Differences from Communication

**Communication has**: From, To, Method (with radio net hierarchy), Confirmed  
**Events has**: Whom, Priority, Category, structured reports (7S, etc.)  

**Reasoning**: Events are about what happened and who was involved, not directional communication between parties.

### Event Log View Table Columns

**Widget**: `ttk.Treeview` (same as Communication tab)

**Sorting**: Clickable headers, default sort by Time descending (latest at top)

**Proposed Columns**:
1. **Tid** (Time) - Event time
2. **Vem** (Whom) - Who is involved/affected
3. **Prioritet** (Priority) - Low/Normal/High/Critical
4. **Kategori** (Category) - Event category/type
5. **Händelse** (Event) - Event description + structured report summary, **truncated if too long**
   - **No structured report**: Shows event_description
     - Example: "Pluton 2 rapporterar färdig"
   - **With structured report**: Shows event_description + " | " + report auto_summary
     - Example: "Fientlig patrull | 14:30, Grid 123, 20 pers, Soldater, Förfl. öst"
   - **Truncation**: At word boundary with ellipsis (...)
6. **Redigerad** (Edited) - Small indicator if edited
7. **Operatör** (Operator) - Who logged it
- Full 7S details visible in detail dialog on double-click

**Priority Color Coding** (Optional Feature):
- **Setting**: Enable/disable in column configuration dialog
- **Checkbox**: "Färgkoda prioritet" (Color code priority) in column config
- **Colors when enabled**:
  - Critical: Red background or red text
  - High: Orange/yellow background or orange text
  - Normal: Default (no special color)
  - Low: Gray text or subtle color
- **Reasoning**: Visual priority indicators help operators quickly identify critical events, but some users may prefer clean uncolored rows

**Column Configuration** (same as Communication):
- "Kolumner..." button opens config dialog
- Show/hide columns (except Time and Event always visible)
- Reorder columns
- **NEW**: "Färgkoda prioritet" checkbox for priority color coding
- Persists in database preferences

## Personnel Entry Design

### Core Purpose

Track personnel and groups who are away from camp, ensuring regular contact and monitoring their status.

**Key Operational Needs**:
1. Know who is out and where
2. Track when we last heard from them
3. Get reminders to check in with them
4. Follow status history over time

### PersonnelEntry Fields

#### Core Fields
1. **Who** (Vem) - Person name or group callsign (free text)
   - Examples: "Pluton 2", "Grupp A", "Sgt. Andersson"
2. **Status** - Current status (free text)
   - Examples: "Ute på patrull", "På väg tillbaka", "I skydd", "Återvänd"
   - **Free text reasoning**: Many possible statuses, operational flexibility needed
3. **Location** (Plats) - Where they are (free text, if known)
4. **Last Contact Time** (Senaste kontakt) - When we last heard from them
5. **Mission/Notes** (Uppdrag/Anteckningar) - What they're doing, mission details (multi-line)
6. **Check-in Alarm** - Optional reminder (see below)
7. **Logged Time** (Loggad tid) - When this entry was created (auto)
8. **Operator** - Who logged it
9. **Active** - Boolean: Is this the current status? (see Status Change Pattern below)
10. **Supersedes** - Optional entry ID(s) that this entry replaces/updates (see Relationship Tracking below)
11. **edited** - Boolean flag (default: false)

### Check-in Alarm/Reminder (Optional)

**Design**: Not all entries need alarms - only when you want to be reminded to contact someone.

**Fields when alarm is enabled**:
- **Expected Check-in Time** - When they should contact us (or when we should contact them)
- **Alarm Interval** - How long before expected time to trigger reminder
  - Examples: "5 min before", "15 min before", "30 min before"
  - Or specific time: "Alert at 14:30"

**UI Approach**:
- Checkbox: "Sätt påminnelse" (Set reminder)
- When checked → show alarm time fields
- When unchecked → no alarm fields

**Reasoning**: Flexible - some statuses need reminders ("patrol should check in every hour"), others don't ("returned to camp").

### Status Change Pattern - Historical Tracking

**Design Decision**: Create NEW entry for each status change, mark old entry as inactive.

**How it works**:
1. Pluton 2 leaves camp → Create entry: Status="Ute på patrull", Active=true
2. They check in from new location → Create NEW entry: Status="I skydd vid punkt Alpha", Active=true
   - Previous entry: Active=false (deprecated)
3. They return → Create NEW entry: Status="Återvänd till lager", Active=true
   - Previous entries: Active=false

**Benefits**:
- Complete history of status changes
- Clear "current state" (active entries only)
- Immutable records (edit flag still available for corrections)

**Data Model**:
- `active`: Boolean field (true = current status, false = historical/deprecated)
- All entries for same person/group remain in database
- Filter determines what's visible

### Personnel Log View - Default Filter

**Default View**: Show only ACTIVE entries (current status for each person/group)

**Toggle**: "Visa alla poster" (Show all entries) checkbox in filter bar
- Unchecked (default): Only active=true entries visible
- Checked: All entries visible (historical tracking)

**Reasoning**: 
- Operators primarily need current status ("who's out right now?")
- Historical view available when needed for investigation/review

### Personnel Log View Table Columns

**Widget**: `ttk.Treeview` (same as Communication and Events)

**Sorting**: Clickable headers, default sort by Last Contact Time or Logged Time (TBD)

**Proposed Columns**:
1. **Tid** (Time) - Logged time (when this status was recorded)
2. **Vem** (Who) - Person or group callsign
3. **Status** - Current status (free text)
4. **Plats** (Location) - Where they are
5. **Senaste kontakt** (Last Contact) - When we last heard from them
6. **Påminnelse** (Reminder) - Alarm/check-in time indicator (icon or time)
7. **Uppdrag** (Mission) - Mission/notes, **truncated if too long**
8. **Redigerad** (Edited) - Small indicator if edited
9. **Operatör** (Operator) - Who logged it

**Column Configuration** (same as other tabs):
- "Kolumner..." button for show/hide, reorder
- Persists in database preferences

### Visual Indicators for Overdue Check-ins

**Design Decision**: Red row highlighting for overdue alarms.

**Trigger**: If entry has alarm set AND current time > expected check-in time → Red row

**Contrast Consideration**:
- Use strong contrast (red background with dark text OR red text on light background)
- Ensure readability for colorblind users (contrast ratio matters more than specific hue)
- Test with accessibility tools

**Optional Enhancement** (Phase 2):
- Yellow/orange warning as check-in time approaches (e.g., 15 min before)
- Icon in Reminder column showing alarm status

**Reasoning**: Clear visual alarm ensures operators don't miss overdue check-ins.

### Personnel Filtering

**Active/All Toggle** (default filter):
- Checkbox: "Visa endast aktiva" (Show only active) - checked by default
- Shows only entries where Active=true
- Uncheck to see all historical entries

**Column Filters** (Phase 1):
- **Free text entry** for each relevant column (Who, Status, Location)
- **Active filtering as you type** - results update in real-time
- **Autocomplete/suggestions** from existing values in database
  - Example: Type "Plu" → suggests "Pluton 1", "Pluton 2", "Pluton 3"
- **Simple AND logic**: Multiple filters combine with AND

**Filter UI**:
- Compact filter bar above table (below entry form)
- Text fields for: Who, Status, Location
- "Rensa filter" (Clear filters) button
- Active/All toggle checkbox

**Autocomplete Behavior**:
- Dropdown appears below text field as user types
- Arrow keys to select suggestion
- Enter to accept
- Can also type free text (not forced to select suggestion)

**Reasoning**: 
- Free text with autocomplete balances flexibility and data consistency
- Real-time filtering provides immediate feedback
- Faster than dropdown selection for operators who know what they're looking for

### Status Update Workflow - Handling Entity Continuity

**Challenge**: With free text "Who" field, how to ensure consistent tracking across status changes and handle splits/merges?

**Solution**: Combination of "Update Status" button + Autocomplete in entry form.

#### "Update Status" Button/Action

**Location**: On each row in the table (right-click menu or button column)

**Behavior**:
1. User clicks "Uppdatera status" on row (e.g., "GC - Ute på patrull")
2. Entry form is pre-populated with data from selected row:
   - **Who**: "GC" (pre-filled, editable with autocomplete)
   - **Status**: Empty (user enters new status)
   - **Location**: Previous location (pre-filled, editable)
   - **Last Contact Time**: Current time (auto)
   - **Mission/Notes**: Previous notes (pre-filled, editable)
   - **Alarm**: Not set (user can optionally set)
3. User modifies as needed and saves
4. On save:
   - Creates NEW entry with updated fields
   - New entry: Active=true
   - Old entry: Active=false (deprecated)

**Benefits**:
- Quick status updates for same entity (most common case)
- Maintains consistent "Who" value automatically
- Pre-fills relevant fields to reduce data entry

#### Autocomplete in Entry Form

**"Who" field** (in both new entry and update status):
- Free text input with autocomplete
- Suggests from currently ACTIVE personnel entries
- User can accept suggestion OR type new/modified value

**Use Cases**:

**Normal Status Update** (via button):
- "GC" pre-filled → User just changes Status → Same entity tracked

**Group Split** (via button + manual edit):
1. Click "Update Status" on "GC"
2. Manually change "Who" to "GC-1"
3. Save → Creates new entity "GC-1", marks "GC" inactive
4. Repeat: Create new entry, type "GC-2" (or use "Update Status" on GC again)
5. Result: "GC" inactive, "GC-1" and "GC-2" both active

**Group Merge** (manual new entry):
1. Create new entry manually (not via Update Status)
2. Type "GC" in Who field (autocomplete may suggest it, or type fresh)
3. In Mission/Notes: "GC-1 och GC-2 sammanfogade"
4. Save → "GC" active again
5. Manually use "Update Status" on "GC-1" and "GC-2" to mark them with final status
6. Result: "GC" active, "GC-1" and "GC-2" inactive

**Edge Case Handling**:
- **Typos**: Autocomplete reduces but doesn't eliminate ("Pluton1" vs "Pluton 1")
- **Historical queries**: Can still filter/search across all entries (active + inactive)
- **Operator discretion**: Free text allows field-improvised callsigns

**Reasoning**: 
- "Update Status" button covers 80% of common cases (simple status change)
- Autocomplete helps maintain consistency
- Free text flexibility handles splits, merges, and unexpected scenarios

### Relationship Tracking - Supersedes Field

**Purpose**: Explicitly track which entries replace/update which other entries.

**Field**: `supersedes` - Can contain one or multiple entry IDs

**Data Storage**:
- **Single supersede**: `supersedes = "123"` (entry 456 replaces entry 123)
- **Multiple supersedes** (merge): `supersedes = "123,124"` (entry 456 replaces both 123 and 124)
- **None**: `supersedes = null` (new entity, doesn't replace anything)

**How It Works with "Update Status" Button**:
1. User clicks "Update Status" on entry #123 ("GC")
2. Creates new entry #456 with pre-filled data
3. **Automatically sets**: `supersedes = "123"` on the new entry
4. Marks entry #123 as Active=false

**Benefits of Having Both Workflows**:
- **"Update Status" button**: Automatic supersedes relationship, fast, correct 80% of the time
- **Manual "Supersedes" field**: Can fix relationships retroactively, handles complex cases

#### Retroactive Relationship Setting

**UI Approach**: Button or action on table rows: "Ange relation..." (Set Relationship)

**Modal Dialog**:
- **Title**: "Ange ersättningsrelation" (Set Replacement Relationship)
- **Field**: "Denna post ersätter:" (This entry supersedes:)
- **Input**: Text field with autocomplete or ID entry
  - Shows recently inactive entries for selection
  - Can enter multiple IDs (comma-separated) for merges
- **Buttons**: "Spara" (Save), "Ta bort relation" (Remove relationship), "Avbryt" (Cancel)

**Use Cases**:

**Forgot to Link Earlier** (retroactive correction):
1. Created entry #456 "GC - Återvänd" but forgot to use "Update Status"
2. Open "Set Relationship" modal on entry #456
3. Select or enter ID #123 (the previous "GC" entry)
4. Save → `supersedes = "123"` is set retroactively

**Complex Split** (manual relationship):
1. "GC" splits into "GC-1", "GC-2", "GC-3"
2. Create all three new entries
3. On each new entry, open modal and set `supersedes = "123"` (original GC ID)
4. Result: Clear lineage showing all three came from original GC

**Merge** (manual relationship):
1. "GC-1" and "GC-2" merge back to "GC"
2. Create new "GC" entry #789
3. Open modal, set `supersedes = "456,457"` (IDs of GC-1 and GC-2)
4. Result: Entry #789 explicitly replaces both previous entries

**Query Benefits**:
- Can find all entries that superseded entry #123
- Can trace full lineage: GC → GC-1 → GC-1-Alpha
- Can generate timeline/history view showing relationships

**Alternative UI** (simpler):
- Include "Supersedes" field directly in entry form
- Hidden by default, show with checkbox "Ange ersättningsrelation"
- Less clicks than modal, but more clutter in form

**Reasoning**:
- Explicit relationships = queryable data lineage
- Automatic (via Update Status) handles common case
- Manual (via modal or form field) handles edge cases and corrections
- Having both gives convenience AND data integrity

**Status**: Personnel Entry design complete with formal relationship tracking.


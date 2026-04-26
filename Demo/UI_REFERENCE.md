e# Demo UI to Implementation Reference

**Purpose**: Map demo app UI elements to actual implementation specifications in architecture/design docs.

## Demo vs Reality

**Demo = Visual Layout Reference**  
**Architecture/Design Docs = Implementation Requirements**

---

## Communications Tab

### Demo Shows:
```
TNR: [Entry] [Nu button]
System: [RA180 dropdown]
Metod: [Radio dropdown]
Kanal: [Company Net dropdown]
Från: [Entry] [AQ button]
Till: [Entry] [AQ button]
Meddelande: [Text area]
```

### Implement According To:
- **See**: `ai_instructions/design/gui_design.md` - "Communication Entry Design" (lines 120-440)
- **TNR (Tid)**: Event Time field - See gui_design line 260
  - "Nu" button: Fill with current DDHHMM format
- **System/Metod/Kanal**: Communication System & Method Selection - See gui_design lines 279-351
  - System-centric approach: System → Method → Channel
  - Stored in database, NOT config.ini
- **Från/Till with callsign buttons**: From/To fields - See gui_design lines 258-259
  - Unit call sign (e.g., "AQ") in database `unit_config` table
  - Button shows actual callsign (not "Min") - makes it clear what will be inserted
  - Från field starts empty (button fills it when clicked)
  - Till field starts empty (button fills it when clicked)
  - Till should be combobox with frequent contacts from database (demo uses simple entry)
- **Meddelande**: Message Content - See gui_design line 257
- **Table columns**: See gui_design lines 208-253

---

## Events Tab

### Demo Shows:
```
TNR: [Entry] [Nu button]
Vem: [Entry]
Prioritet: [Normal dropdown]
Kategori: [Observation dropdown]
Beskrivning: [Text area]
[Lägg till rapport button]
```

### Implement According To:
- **See**: `ai_instructions/design/gui_design.md` - "Event Entry Design" (lines 441-638)
- **TNR**: Event Time field - See gui_design line 466
- **Vem**: Whom field - See gui_design line 460
- **Prioritet**: Priority field - See gui_design line 469
- **Kategori**: Category field - See gui_design line 470
- **Beskrivning**: Event Description - See gui_design line 459
- **Lägg till rapport**: Structured Reports (7S, etc.) - See gui_design lines 476-592
- **Table columns**: See gui_design lines 640-678

---

## Personnel Tab

### Demo Shows:
```
Vem: [Entry]
Status: [Entry]
Plats: [Entry]
Senaste kontakt: [Entry]
Uppdrag/Anteckningar: [Text area]
[Sätt påminnelse checkbox]
```

### Implement According To:
- **See**: `ai_instructions/design/gui_design.md` - "Personnel Entry Design" (lines 678-964)
- **Vem**: Who field - See gui_design line 693
- **Status**: Status field - See gui_design line 695
- **Plats**: Location field - See gui_design line 698
- **Senaste kontakt**: Last Contact Time - See gui_design line 699
- **Uppdrag**: Mission/Notes - See gui_design line 700
- **Påminnelse**: Check-in Alarm - See gui_design lines 708-723
- **Important**: Active/Inactive pattern - See gui_design lines 725-754
- **Table columns**: See gui_design lines 760-776

---

## General UI Elements

### Login Window
- **Demo shows**: Basic mockup
- **Implement**: Per security design (keyfile + password)
- **See**: `ai_instructions/design/security_design.md`

### Main Window Structure
- **Demo shows**: Tabs with toolbar/status bar
- **See**: `ai_instructions/design/gui_design.md` lines 49-119
  - ttk.Notebook with tabs
  - Toolbar with Nollställ button
  - Status bar with operator and last log

---

## Key Demo Values Are Examples Only!

❌ **Do NOT implement these literally**:
- "AQ" - Example call sign (actual: from database)
- "RA180", "RA146" - Example systems (actual: configurable in database)
- "Radio", "Telefon" - Example methods (actual: per system configuration)
- "Company Net" - Example channel (actual: user-defined, stored in database)
- "Låg", "Normal", "Hög" - Example priorities (actual: could be configurable)

✅ **Demo shows the FIELD**, not the VALUES**

---

## Where Things Are Stored

### config.ini (Bootstrapping ONLY)
- Window position/size
- Last used database path
- **See**: `ai_instructions/design/gui_design.md` lines 21-30

### Database (Everything Else)
- Unit call sign
- Communication systems, methods, channels
- Frequent contacts
- User preferences (column config, etc.)
- **See**: `ai_instructions/design/gui_design.md` lines 32-47
- **See**: `ai_instructions/design/db_design.md` for schema

---

## Implementation Checklist

When implementing a tab from the demo:

1. ✅ Check gui_design.md for field specifications
2. ✅ Check core_design.md for entity definitions
3. ✅ Check db_design.md for database schema
4. ✅ Check gui_architecture.md for View/Presenter pattern
5. ✅ Use demo for visual layout and Swedish field names only
6. ✅ Don't copy demo code (monolithic, no architecture)
7. ✅ Don't use demo's hardcoded values

---

**Remember**: Demo is a UI sketch. Architecture/design docs are the requirements.


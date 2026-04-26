# Domain Knowledge - Military Operations Context

**Purpose**: Business domain knowledge for EventLog. Read when working on features or understanding requirements.

---

## Application Purpose

**EventLog** is a platoon staff event logger for military operations. It tracks:
1. **Radio communications** - Messages sent/received
2. **Operational events** - Things that happen during operations
3. **Personnel tracking** - Who is where, check-ins, status

**Users**: Squad/platoon/company staff members operating in field conditions

---

## Swedish Military Context

### 7S Report (SjuSrapport) - Standard Observation Format

**Used for**: Reporting observed enemy forces, outside forces, or civilians

**Seven elements** (Swedish → English):
1. **Stund** - When (time observation made)
2. **Ställe** - Where (location)
3. **Styrka** - Strength (how many)
4. **Slag** - Type (infantry, vehicle, etc.)
5. **Sysselsättning** - Activity (what they're doing)
6. **Symbol** - Markings (identifying symbols, insignia)
7. **Sagesman** - Observer (who reported it)

**Implementation**: EventEntry needs structured fields to support 7S reports

---

## Callsigns in the swedish military

- One can dicern the parent unit from the callsign, the group EA belongs to AQ platoon which belongs to QJ company. which belongs to the J<x> Batalion.
- Individuals EA01, EA02, EA03 belongs to Group E. AQ01 is Platoon leader, QJ01 is Company commander, J01 is Battalion commander
- Groups E,F,G,H belongs to Platoons.
- Platoons A,B,C,D,E belongs to Company.
- Companies Q,R,S,T,V belongs to Battalion.
- Battalions J,L,N,U is battalion 1 to 4 respectively.
- On battalion level, depending on unit it might be other callsigns but we are working with this as default.
- We are currently working with this for Company level and below, developer is part of platoon staff and has call sign AQ03, in QJ company.

## Radio Communication

### Communication Methods

**DART** - Data messages (digital)
**Speech** - Voice transmission

### Channel Information
- **System**: What radio system (tactical radio, cell phone, etc.)
- **Method**: DART vs Speech
- **Channel**: Frequency or channel number
- **Designation**: What the channel is called at time of logging

**Historical accuracy requirement**: Logs must preserve channel designations as they were at time of logging, because designations can change during operations.

---

## Unit Designations

### Swedish Military Organization
- **Pluton** - Platoon
- **Grupp** - Squad/section
- **Kompani** - Company.
- **Bataljon** - Battalion

### Callsigns
- Units have tactical callsigns
- Callsigns used in radio communications
- Need to track callsign along with formal designation

---

## Operational Context

### Field Conditions

**Hardware constraints**:
- Small screens (netbooks ~1024x600)
- Old, low-spec hardware common
- Must work reliably on "crappy hardware"

**Operational tempo**:
- Fast data entry critical
- Events happen quickly
- No time for complex workflows
- Stress conditions (combat, time pressure)

**Offline requirement**:
- No internet connectivity in field
- Everything local
- No cloud services
- No external dependencies

---

## Personnel Tracking

### Check-in System

**Purpose**: Track personnel away from camp who need regular contact

**Key data**:
- Who is away
- Where they went
- When they left
- When last contact was made
- When next check-in expected
- Alarm if overdue

### Status Categories
- Active duty
- On mission
- On leave
- Sick
- Other statuses as defined

### Contact Monitoring
- Regular check-ins required
- Alarm triggers if overdue
- Track location and status changes
- History of all status changes

---

## Event Logging Requirements

### Priority Levels
- Events have priority (Normal, High, Critical, etc.)
- Helps staff identify important events quickly
- Filter/sort by priority

### Event Categories
- Operational (mission-related)
- Administrative
- Logistics
- Personnel
- Other categories as configured

### Chronological Accuracy
- Logged time (when entered in system)
- Event time (when event actually occurred)
- May not be the same (delayed logging common)
- Both must be tracked

---

## Data Integrity Requirements

### Edit Tracking
- All entries can be edited
- System tracks if edited (edited flag)
- Preserve original logged_time
- Maintain audit trail

### Confirmation System
- Communications can be marked "confirmed"
- Differentiate between unconfirmed reports and confirmed information
- Important for intelligence/operations

---

## Operational Workflow

### Typical Use Cases

1. **Radio message received**:
   - Staff member logs communication
   - Records from, to, content, method, channel
   - Marks if confirmed or unconfirmed

2. **Event occurs**:
   - Staff member logs event
   - Records time, description, priority, category
   - Links to relevant personnel if applicable

3. **Personnel departs camp**:
   - Create personnel entry
   - Record who, where, mission, expected return
   - Set check-in alarm if needed

4. **Check-in monitoring**:
   - System shows active personnel away from camp
   - Highlights overdue check-ins
   - Staff can update status/location

5. **Search/review**:
   - Staff needs to find past communications/events
   - Search by time, operator, keywords
   - View history for specific person/unit

---

## User Experience Priorities

### Must Haves
- **Fast data entry** - Minimal clicks/typing
- **Clear display** - Works on small screens
- **Reliable** - No crashes, no data loss
- **Offline** - No internet required

### Key to Operations
- Staff are not computer experts
- Training time limited
- Interface must be intuitive
- Errors have operational consequences

---

**Last Updated**: 2026-04-23 (Session 013 - Created during AI memory refactor)


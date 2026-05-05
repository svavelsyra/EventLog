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
- **Important nuance**: Channels are **not** a radio-only concept in this project. The same broad idea of a channel/designation can appear in other communication systems too (for example Slack-style channels), even when the exact operational meaning differs.
- **Terminology warning**: "Channel", "designation", and related terms may be reused across different communication technologies with different semantics. Future design and implementation work must not hardcode radio-specific assumptions into generic communication configuration contracts.

### Communication Complexity and Modeling Guardrail

- The project has **many ways of communication**, and the user intentionally prefers the broader word **"ways"** because terms like "channel" and "method" carry domain-specific weight and can easily become misleading if used too generically.
- Example communication systems/ways already called out by the user:
  - **RA180** - can support spoken radio, data messaging, and connection into the telephone net; the user does not currently need fine-grained separation between DART and PCDART, only the meaningful distinction that it is **data**.
  - **RA146** - simple cleartext radio only.
  - **Motorola** - clear text close range group-platoon communication.
  - **RAKEL** - much more complex capability set and communication structure than simple radio modeling suggests.
  - **Telephone** - can be plain telephone, crypto telephone, or used for data transfer with separate crypto apparatus/app support.
  - **Courier** - an important non-radio communication way/example that should help keep the model from silently assuming every configured communication system is radio-based.
  - **Spoken word / in-person meeting** - direct human communication with no electronic system.
- **Crypto apparatus/app capability is cross-cutting**: some added technology such as a `krypapp` may ride on top of another communication way rather than being the base system itself. Example: the same base RA180 audio path might exist both with and without added crypto apparatus.
- **Modeling goal**: preserve important operational nuance without making day-to-day logging so complex that users will avoid or misuse it.
- **Design warning**: do not assume every meaningful difference must become a separate first-class base system. Some distinctions may be better expressed as optional capabilities or variants attached to a base way.
- **Configuration flexibility goal**: the initial default set should stay practical and fairly simple, but later admin/operator-defined configuration must be able to express richer combinations, such as one base way plus optional added technology/capabilities.
- **Current preferred modeling direction**: use a **three-tier selection model** for communication configuration with optional lower tiers, plus optional additional boolean-like flags/capabilities for simple cross-cutting distinctions such as clear/encrypted.
- **Important boundary**: the three tiers are primarily a practical runtime/UI selection shape, not proof that every communication way literally has the same real-world "channel" semantics at each level.
- **Design intent**: keep the operator-facing selection model stable and simple while allowing system-specific meaning for the tiers and a small set of optional qualifiers.
- **Current Phase 1 boolean direction**: start with **tier-1/system-level booleans only**, while leaving room for deeper/path-specific qualifiers later if real use demands it.
- **Top-level security qualifier importance**: `encrypted` / `clear` is important enough to be treated as a top-level per-communication qualifier because it matters operationally and should be filterable later.
- **Qualifier override rule**: even when a qualifier such as `encrypted` / `clear` exists at top level, an individual system may override how that qualifier behaves: selectable, forced to a fixed value, or hidden/uneditable when not meaningful for operator choice.
- **Current Phase 1 simplifications by key system**:
  - **RA180** - use channels; keep the selectable communication distinction to **Speech/Data** plus **encrypted/clear**.
  - **Motorola** - clear only; channels matter.
  - **Rakel** - treat as encrypted-only for the initial model; channels matter.
- **Courier side note**: courier is still a valuable non-radio example even though it may in some cases carry encrypted material on paper; the main modeling lesson is that the system can force or hide top-level qualifiers when operator choice is not the important part.
- **Operational implication**: encrypted/clear is not only display detail; it may affect how communications are reviewed and filtered later.
- **RA180 practical use clarification**:
  - In normal use, the operator typically sets an RA180 **mode** to either `clear` or `encrypted`.
  - The operator also selects a **channel** for send/receive.
  - A data sender such as **DART** may then be attached and the same configured radio is often used for both voice and data.
  - The most common practical setup is one selected channel, mode set to `encrypted`, DART connected, and the radio used for both voice and data.
  - Channel-specific data/voice restrictions can exist operationally (for example data only on one channel, data+voice on another, voice only on a third), but the app does **not** need to enforce those restrictions in Phase 1; they are important as domain context, not as a required hard validation rule.
  - When crypto data is attached to RA180, operators may still switch between `clear` and `encrypted` for speech use, while data use is effectively encrypted-only in practice.
  - For Phase 1 UX, a simple boolean-like `Data` flag may be acceptable if unchecked means ordinary speech/voice, but this remains a design choice rather than a finalized rule.

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


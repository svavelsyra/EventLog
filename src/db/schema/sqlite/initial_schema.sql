-- EventLog Database Schema
-- Database Version: 0.1.1 (Epic 001 core tables + Epic 003 communication config seed foundation)
-- Last Updated: 2026-05-05
--
-- This is the INITIAL schema for NEW databases.
-- New installations run this file directly and do not replay migrations.
-- When old migrations are cleaned up in the future, this file is updated
-- so it continues to represent the complete schema for a fresh database.
--
-- Scope note:
-- - Includes the three Epic 001 entity tables and the first Epic 003 communication configuration tables
-- - Communication configuration remains runtime metadata; saved communication entries still keep their own snapshot fields
-- - Excludes attachment and structured report tables
-- - Uses SQLite-compatible types only

-- ========== COMMUNICATION ENTRIES ==========
-- Stores radio messages, phone calls, in-person updates, and similar traffic.
CREATE TABLE IF NOT EXISTS communication_entries (
    -- Identity
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Timing
    event_time TEXT NULL,                         -- When the communication occurred (ISO 8601)
    logged_time TEXT NOT NULL CHECK (logged_time != ''),
                                                 -- When the operator logged it (ISO 8601)

    -- Message content
    message_content TEXT NOT NULL CHECK (message_content != ''),
    from_field TEXT NULL,                        -- Sender/source
    to_field TEXT NULL,                          -- Recipient/destination

    -- Operator metadata
    operator TEXT NOT NULL CHECK (operator != ''),
    confirmed INTEGER NOT NULL DEFAULT 0 CHECK (confirmed IN (0, 1)),
    edited INTEGER NOT NULL DEFAULT 0 CHECK (edited IN (0, 1)),

    -- System/method hierarchy
    communication_system TEXT NULL,              -- Hardware/system name, e.g. RA180
    method_type TEXT NULL,                       -- Usage type, e.g. Radio, Phone, Data
    method_channel TEXT NULL,                    -- Technical channel number/identifier
    channel_designation TEXT NULL,               -- Human-readable channel/net name
    system_capabilities TEXT NULL                -- JSON TEXT for system-specific settings
);

CREATE INDEX IF NOT EXISTS idx_comm_event_time
    ON communication_entries(event_time);
CREATE INDEX IF NOT EXISTS idx_comm_logged_time
    ON communication_entries(logged_time);
CREATE INDEX IF NOT EXISTS idx_comm_operator
    ON communication_entries(operator);
CREATE INDEX IF NOT EXISTS idx_comm_system
    ON communication_entries(communication_system);
CREATE INDEX IF NOT EXISTS idx_comm_method_type
    ON communication_entries(method_type);

-- ========== EVENT ENTRIES ==========
-- Stores incidents, observations, operational updates, and status changes.
CREATE TABLE IF NOT EXISTS event_entries (
    -- Identity
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Event content
    event_description TEXT NOT NULL CHECK (event_description != ''),
    whom TEXT NULL,                              -- Who is involved or affected

    -- Timing
    event_time TEXT NULL,                        -- When the event occurred (ISO 8601)
    logged_time TEXT NOT NULL CHECK (logged_time != ''),
                                                 -- When the operator logged it (ISO 8601)

    -- Classification
    operator TEXT NOT NULL CHECK (operator != ''),
    priority TEXT NULL DEFAULT 'Normal',
    category TEXT NULL,
    edited INTEGER NOT NULL DEFAULT 0 CHECK (edited IN (0, 1))
);

CREATE INDEX IF NOT EXISTS idx_event_event_time
    ON event_entries(event_time);
CREATE INDEX IF NOT EXISTS idx_event_logged_time
    ON event_entries(logged_time);
CREATE INDEX IF NOT EXISTS idx_event_operator
    ON event_entries(operator);
CREATE INDEX IF NOT EXISTS idx_event_priority
    ON event_entries(priority);
CREATE INDEX IF NOT EXISTS idx_event_category
    ON event_entries(category);

-- ========== PERSONNEL ENTRIES ==========
-- Stores personnel/group status, location, and check-in tracking history.
CREATE TABLE IF NOT EXISTS personnel_entries (
    -- Identity
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Personnel state
    who TEXT NOT NULL CHECK (who != ''),
    status TEXT NULL,
    location TEXT NULL,
    last_contact_time TEXT NULL,                 -- Most recent contact time (ISO 8601)
    mission_notes TEXT NULL,

    -- Timing and operator metadata
    logged_time TEXT NOT NULL CHECK (logged_time != ''),
                                                 -- When this status was logged (ISO 8601)
    operator TEXT NOT NULL CHECK (operator != ''),
    edited INTEGER NOT NULL DEFAULT 0 CHECK (edited IN (0, 1)),

    -- Historical tracking
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    supersedes TEXT NULL,                        -- Comma-separated entry IDs replaced by this row

    -- Alarm/check-in tracking
    alarm_enabled INTEGER NOT NULL DEFAULT 0 CHECK (alarm_enabled IN (0, 1)),
    expected_checkin_time TEXT NULL,             -- Required when alarm_enabled = 1
    alarm_triggered INTEGER NOT NULL DEFAULT 0 CHECK (alarm_triggered IN (0, 1)),

    CHECK (alarm_enabled = 0 OR expected_checkin_time IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS idx_personnel_who
    ON personnel_entries(who);
CREATE INDEX IF NOT EXISTS idx_personnel_active
    ON personnel_entries(active);
CREATE INDEX IF NOT EXISTS idx_personnel_logged_time
    ON personnel_entries(logged_time);
CREATE INDEX IF NOT EXISTS idx_personnel_last_contact
    ON personnel_entries(last_contact_time);
CREATE INDEX IF NOT EXISTS idx_personnel_alarm
    ON personnel_entries(alarm_enabled, expected_checkin_time);

-- ========== REPOSITORY SETTINGS ==========
-- Stores repository-managed runtime settings and migration metadata.
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    description TEXT NULL,
    modified_time TEXT NOT NULL CHECK (modified_time != '')
);

INSERT OR IGNORE INTO settings (
    key,
    value,
    description,
    modified_time
)
VALUES (
    'edited_flag_grace_period_seconds',
    '300',
    'Grace period in seconds before repository updates automatically mark entries as edited.',
    strftime('%Y-%m-%dT%H:%M:%f', 'now')
);

-- ========== COMMUNICATION CONFIGURATION ==========
-- Runtime configuration for communication systems, recursive option paths,
-- and top-level qualifier behavior. Communication log entries keep the values
-- actually used at log time; these tables drive current UI/validation only.

CREATE TABLE IF NOT EXISTS communication_systems (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    system_name TEXT NOT NULL UNIQUE CHECK (system_name != ''),
    system_type TEXT NOT NULL CHECK (system_type != ''),
    child_label TEXT NULL,
    sort_order INTEGER NULL,
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1))
);

CREATE INDEX IF NOT EXISTS idx_comm_systems_active
    ON communication_systems(is_active);
CREATE INDEX IF NOT EXISTS idx_comm_systems_type
    ON communication_systems(system_type);

CREATE TABLE IF NOT EXISTS communication_options (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    communication_system_id INTEGER NOT NULL,
    option_value TEXT NOT NULL CHECK (option_value != ''),
    option_label TEXT NOT NULL CHECK (option_label != ''),
    parent_option_id INTEGER NULL,
    child_label TEXT NULL,
    sort_order INTEGER NULL,
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    FOREIGN KEY (communication_system_id) REFERENCES communication_systems(id) ON DELETE CASCADE,
    FOREIGN KEY (parent_option_id) REFERENCES communication_options(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_comm_option_system
    ON communication_options(communication_system_id);
CREATE INDEX IF NOT EXISTS idx_comm_option_parent
    ON communication_options(parent_option_id);
CREATE INDEX IF NOT EXISTS idx_comm_option_active
    ON communication_options(is_active);
CREATE UNIQUE INDEX IF NOT EXISTS uq_comm_option_unique_path
    ON communication_options(communication_system_id, COALESCE(parent_option_id, 0), option_value);

CREATE TABLE IF NOT EXISTS communication_qualifiers_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    communication_system_id INTEGER NOT NULL,
    qualifier_key TEXT NOT NULL CHECK (qualifier_key != ''),
    label TEXT NOT NULL CHECK (label != ''),
    field_type TEXT NOT NULL CHECK (field_type IN ('enum', 'boolean', 'text')),
    valid_values TEXT NULL,
    default_value TEXT NULL,
    help_text TEXT NULL,
    visibility_mode TEXT NOT NULL DEFAULT 'editable' CHECK (visibility_mode IN ('editable', 'forced', 'hidden')),
    FOREIGN KEY (communication_system_id) REFERENCES communication_systems(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_comm_qualifiers_system
    ON communication_qualifiers_config(communication_system_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_comm_qualifiers_system_key
    ON communication_qualifiers_config(communication_system_id, qualifier_key);

INSERT OR IGNORE INTO communication_systems (
    system_name,
    system_type,
    child_label,
    sort_order,
    is_active
)
VALUES
    ('RA180', 'Radio System', 'Channel', 10, 1),
    ('Motorola', 'Radio System', 'Channel', 20, 1),
    ('Rakel', 'Radio System', 'Channel', 30, 1),
    ('Courier', 'Courier', NULL, 40, 1);

INSERT OR IGNORE INTO communication_options (
    communication_system_id,
    option_value,
    option_label,
    parent_option_id,
    child_label,
    sort_order,
    is_active
)
VALUES
    ((SELECT id FROM communication_systems WHERE system_name = 'RA180'), '1', 'Channel 1', NULL, NULL, 10, 1),
    ((SELECT id FROM communication_systems WHERE system_name = 'RA180'), '2', 'Channel 2', NULL, NULL, 20, 1),
    ((SELECT id FROM communication_systems WHERE system_name = 'RA180'), '3', 'Channel 3', NULL, NULL, 30, 1),
    ((SELECT id FROM communication_systems WHERE system_name = 'RA180'), '4', 'Channel 4', NULL, NULL, 40, 1),
    ((SELECT id FROM communication_systems WHERE system_name = 'RA180'), '5', 'Channel 5', NULL, NULL, 50, 1),
    ((SELECT id FROM communication_systems WHERE system_name = 'RA180'), '6', 'Channel 6', NULL, NULL, 60, 1),
    ((SELECT id FROM communication_systems WHERE system_name = 'RA180'), '7', 'Channel 7', NULL, NULL, 70, 1),
    ((SELECT id FROM communication_systems WHERE system_name = 'RA180'), '8', 'Channel 8', NULL, NULL, 80, 1),
    ((SELECT id FROM communication_systems WHERE system_name = 'Motorola'), '1', 'Channel 1', NULL, NULL, 10, 1),
    ((SELECT id FROM communication_systems WHERE system_name = 'Motorola'), '2', 'Channel 2', NULL, NULL, 20, 1),
    ((SELECT id FROM communication_systems WHERE system_name = 'Motorola'), '3', 'Channel 3', NULL, NULL, 30, 1),
    ((SELECT id FROM communication_systems WHERE system_name = 'Motorola'), '4', 'Channel 4', NULL, NULL, 40, 1),
    ((SELECT id FROM communication_systems WHERE system_name = 'Motorola'), '5', 'Channel 5', NULL, NULL, 50, 1),
    ((SELECT id FROM communication_systems WHERE system_name = 'Motorola'), '6', 'Channel 6', NULL, NULL, 60, 1),
    ((SELECT id FROM communication_systems WHERE system_name = 'Motorola'), '7', 'Channel 7', NULL, NULL, 70, 1),
    ((SELECT id FROM communication_systems WHERE system_name = 'Motorola'), '8', 'Channel 8', NULL, NULL, 80, 1),
    ((SELECT id FROM communication_systems WHERE system_name = 'Rakel'), 'X', 'Talkgroup X', NULL, NULL, 10, 1),
    ((SELECT id FROM communication_systems WHERE system_name = 'Rakel'), 'Y', 'Talkgroup Y', NULL, NULL, 20, 1);

INSERT OR IGNORE INTO communication_qualifiers_config (
    communication_system_id,
    qualifier_key,
    label,
    field_type,
    valid_values,
    default_value,
    help_text,
    visibility_mode
)
VALUES
    (
        (SELECT id FROM communication_systems WHERE system_name = 'RA180'),
        'encrypted',
        'Krypterad',
        'boolean',
        NULL,
        'false',
        'RA180 can be logged as clear or encrypted traffic.',
        'editable'
    ),
    (
        (SELECT id FROM communication_systems WHERE system_name = 'RA180'),
        'data',
        'Data',
        'boolean',
        NULL,
        'false',
        'Mark when the RA180 path was used with attached data equipment.',
        'editable'
    ),
    (
        (SELECT id FROM communication_systems WHERE system_name = 'Motorola'),
        'encrypted',
        'Krypterad',
        'boolean',
        NULL,
        'false',
        'Motorola is treated as clear-only in the Phase 1 defaults.',
        'forced'
    ),
    (
        (SELECT id FROM communication_systems WHERE system_name = 'Rakel'),
        'encrypted',
        'Krypterad',
        'boolean',
        NULL,
        'true',
        'Rakel is treated as encrypted-only in the Phase 1 defaults.',
        'forced'
    ),
    (
        (SELECT id FROM communication_systems WHERE system_name = 'Courier'),
        'encrypted',
        'Krypterad',
        'boolean',
        NULL,
        'false',
        'Courier keeps the shared qualifier model without exposing radio-only choices.',
        'hidden'
    );


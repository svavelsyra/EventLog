-- EventLog Database Schema
-- Database Version: 0.1.1 (Epic 001 - Core entity tables + repository settings)
-- Last Updated: 2026-04-28
--
-- This is the INITIAL schema for NEW databases.
-- New installations run this file directly and do not replay migrations.
-- When old migrations are cleaned up in the future, this file is updated
-- so it continues to represent the complete schema for a fresh database.
--
-- Scope note:
-- - Includes only the three Epic 001 entity tables
-- - Excludes configuration, attachment, and structured report tables
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


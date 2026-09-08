-- ============================================================
-- Service Desk Hub — Database Schema (PostgreSQL)
-- Run this once against a fresh database, e.g.:
--   psql -U sdhub_user -d sdhub -f schema.sql
-- ============================================================

-- ---------- Users & roles ----------
-- role: 'admin' (full access, manages users) | 'leadership' (edits roster/reports)
-- | 'agent' (view-only). Extend later when Active Directory is wired in —
-- ad_username stays NULL for local accounts and gets filled in once AD login exists.
CREATE TABLE users (
  id            SERIAL PRIMARY KEY,
  username      VARCHAR(80)  UNIQUE NOT NULL,
  display_name  VARCHAR(120) NOT NULL,
  password_hash TEXT,                          -- NULL once the user is AD-only
  ad_username   VARCHAR(120) UNIQUE,            -- filled in when AD login is added
  role          VARCHAR(20)  NOT NULL DEFAULT 'agent'
                  CHECK (role IN ('admin','leadership','agent')),
  is_active     BOOLEAN NOT NULL DEFAULT TRUE,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------- Team members (the people who appear in the roster — not necessarily app users) ----------
CREATE TABLE team_members (
  id          SERIAL PRIMARY KEY,
  full_name   VARCHAR(120) NOT NULL,
  username    VARCHAR(80),                      -- optional short handle, e.g. "mehdi.vali"
  is_active   BOOLEAN NOT NULL DEFAULT TRUE,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------- Roster columns (Day_1, Day_2, HQ, Night_1, Night_2, On-Call, Off, Leave Request, CAB, ...) ----------
-- Mirrors what the "manage shifts" panel in Shift_Roster.html lets leadership configure.
CREATE TABLE roster_columns (
  id           SERIAL PRIMARY KEY,
  key          VARCHAR(60) UNIQUE NOT NULL,      -- e.g. 'day1', 'hq', 'imp_telework'
  label_en     VARCHAR(120) NOT NULL,
  label_fa     VARCHAR(120) NOT NULL,
  color        VARCHAR(20)  NOT NULL DEFAULT '#DBEAFE',
  text_color   VARCHAR(20)  NOT NULL DEFAULT '#1D4ED8',
  is_multi     BOOLEAN NOT NULL DEFAULT TRUE,    -- multi = several names per cell, single = one (e.g. On-Call)
  is_builtin   BOOLEAN NOT NULL DEFAULT FALSE,
  sort_order   INTEGER NOT NULL DEFAULT 0
);

-- ---------- Roster entries: one row per (date, column), holding a list of team_member ids ----------
-- Using a join table (roster_entry_members) instead of a text array keeps it query-friendly
-- (e.g. "how many shifts did Mehdi work this month" is a simple JOIN, not array parsing).
CREATE TABLE roster_entries (
  id          SERIAL PRIMARY KEY,
  entry_date  DATE NOT NULL,
  column_id   INTEGER NOT NULL REFERENCES roster_columns(id) ON DELETE CASCADE,
  free_text   TEXT,                              -- for values typed free-hand that aren't a real team member
  UNIQUE (entry_date, column_id, free_text)
);

CREATE TABLE roster_entry_members (
  entry_id        INTEGER NOT NULL REFERENCES roster_entries(id) ON DELETE CASCADE,
  team_member_id  INTEGER NOT NULL REFERENCES team_members(id) ON DELETE CASCADE,
  PRIMARY KEY (entry_id, team_member_id)
);

-- ---------- Official holidays (leadership-maintained, since there's no reliable auto-feed for Iran's calendar) ----------
CREATE TABLE holidays (
  id           SERIAL PRIMARY KEY,
  holiday_date DATE UNIQUE NOT NULL,
  label        VARCHAR(120) NOT NULL
);

-- ---------- Audit log (who changed what — handy once more than one leader edits the roster) ----------
CREATE TABLE audit_log (
  id          SERIAL PRIMARY KEY,
  user_id     INTEGER REFERENCES users(id),
  action      VARCHAR(60) NOT NULL,              -- e.g. 'roster_entry_update', 'holiday_add'
  detail      JSONB,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_roster_entries_date ON roster_entries(entry_date);
CREATE INDEX idx_audit_log_created_at ON audit_log(created_at);

-- ---------- Report history (SDCM / AICC / SLA) ----------
-- Each row is a snapshot of one day's processed report — not the raw Excel file,
-- just the summary numbers the dashboard already computes client-side. This is
-- what lets leadership see trends over time instead of only "today's" numbers.
-- The exact shape of each report's breakdown varies, so it's stored as JSONB —
-- flexible now, and still fully queryable later (e.g. `summary->>'answerRate'`).

CREATE TABLE sdcm_reports (
  id            SERIAL PRIMARY KEY,
  report_date   DATE NOT NULL,
  uploaded_by   INTEGER REFERENCES users(id),
  summary       JSONB NOT NULL,      -- e.g. { totalCalls, registeredCount, registrationRate, byAgent: [...] }
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (report_date)
);

CREATE TABLE aicc_reports (
  id            SERIAL PRIMARY KEY,
  report_date   DATE NOT NULL,
  uploaded_by   INTEGER REFERENCES users(id),
  summary       JSONB NOT NULL,      -- e.g. { totalReceived, totalAnswered, answerRate, byAgent: [...] }
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (report_date)
);

CREATE TABLE sla_reports (
  id            SERIAL PRIMARY KEY,
  report_date   DATE NOT NULL,
  uploaded_by   INTEGER REFERENCES users(id),
  summary       JSONB NOT NULL,      -- e.g. { incidentTypes: {...}, oosla: [...] }
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (report_date)
);

CREATE INDEX idx_sdcm_reports_date ON sdcm_reports(report_date);
CREATE INDEX idx_aicc_reports_date ON aicc_reports(report_date);
CREATE INDEX idx_sla_reports_date ON sla_reports(report_date);

-- ---------- Seed data: the 9 default roster columns, matching the current tool exactly ----------
INSERT INTO roster_columns (key, label_en, label_fa, color, text_color, is_multi, is_builtin, sort_order) VALUES
('day1',         'Day_1 (07:00-19:00)',     'روز_۱ (۰۷:۰۰-۱۹:۰۰)',   '#DBEAFE', '#1D4ED8', TRUE,  TRUE, 1),
('day2',         'Day_2 (07:00-19:00)',     'روز_۲ (۰۷:۰۰-۱۹:۰۰)',   '#DBEAFE', '#1D4ED8', TRUE,  TRUE, 2),
('hq',           'Day - HQ Office (08-17)', 'حضور HQ (۰۸:۰۰-۱۷:۰۰)', '#FEF9C3', '#854D0E', TRUE,  TRUE, 3),
('night1',       'Night_1 (19:00-07:00)',   'شب_۱ (۱۹:۰۰-۰۷:۰۰)',    '#E0E7FF', '#3730A3', TRUE,  TRUE, 4),
('night2',       'Night_2 (19:00-07:00)',   'شب_۲ (۱۹:۰۰-۰۷:۰۰)',    '#E0E7FF', '#3730A3', TRUE,  TRUE, 5),
('oncall',       'Leadership On-Call',      'آنکال لیدرشیپ',         '#CCFBF1', '#0F766E', FALSE, TRUE, 6),
('off',          'Off',                     'آف',                    '#E9D5FF', '#6B21A8', TRUE,  TRUE, 7),
('leaveRequest', 'Leave Request',           'درخواست مرخصی',         '#FBCFE8', '#9D174D', TRUE,  TRUE, 8),
('cab',          'CAB',                     'CAB',                   '#E2E8F0', '#334155', TRUE,  TRUE, 9);

-- ---------- First admin account ----------
-- Password is set by scripts/create_admin.js (never store a plain-text default here).
